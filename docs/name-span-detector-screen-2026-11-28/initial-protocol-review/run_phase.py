"""External limits and complete resource samples for one owned detector phase."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

import psutil

from common import HERE, PLAN_SHA256, emit, read_plan, save, sha, utc, verify_freeze


def alive_owned(identities):
    result = []
    for pid, created in identities.items():
        try:
            process = psutil.Process(pid)
            if process.create_time() == created and process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                result.append(process)
        except psutil.NoSuchProcess:
            pass
    return result


def stop_owned(process, identities):
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        except ProcessLookupError:
            pass
    for child in alive_owned(identities):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, active = psutil.wait_procs(alive_owned(identities), timeout=3)
    for child in active:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(active, timeout=3)
    return not alive_owned(identities)


def monitor(command, environment, private_log, output, samples_path, limits, metadata):
    if output.exists() or samples_path.exists() or private_log.exists():
        raise ValueError("Refusing to repeat or overwrite a measured phase.")
    available = sorted(os.sched_getaffinity(0))
    if len(available) < 4:
        raise ValueError("The frozen four-CPU profile is unavailable.")
    cpus = available[:4]
    os.sched_setaffinity(0, cpus)
    report = {"schema_version": 1, "started_at": utc(), "complete": False, "passed": False,
              "limits": limits, "cpu_affinity": cpus, "events": [], "measurement_errors": [],
              "scope": "Owned monitor plus worker and descendants, deduplicated by PID, from spawn through exit.",
              "rss_scope": "Summed process RSS can double-count shared pages; excludes OS/browser/unrelated processes.",
              "pss_scope": "PSS apportions shared pages. System available memory is a separate uncontrolled observation.",
              "sampling_limit": "Sequential scans at 0.1-second intervals can miss transient peaks.", **metadata}
    process = None
    identities = {}
    parent = psutil.Process(os.getpid())
    started = time.monotonic()
    initialized = False
    case_started = None
    case_active = None
    buffer = b""
    count = 0
    peak_rss = None
    peak_pss = None
    minimum_available = None
    save(output, report)
    private_log.parent.mkdir(exist_ok=True)
    try:
        with private_log.open("xb") as log, samples_path.open("x", encoding="utf-8") as samples:
            process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            identities[process.pid] = psutil.Process(process.pid).create_time()
            selector = selectors.DefaultSelector()
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            last_checkpoint = 0.0
            while True:
                now = time.monotonic()
                elapsed = now - started
                try:
                    entries = []
                    processes = {p.pid: p for p in [parent, *parent.children(recursive=True)]}
                    if len(processes) > 32:
                        raise RuntimeError("Unexpectedly large owned process tree.")
                    for item in processes.values():
                        try:
                            memory = item.memory_full_info()
                            times = item.cpu_times()
                            if item.pid != parent.pid:
                                identities[item.pid] = item.create_time()
                            entries.append({"pid": item.pid, "name": item.name(), "rss_bytes": memory.rss,
                                            "pss_bytes": getattr(memory, "pss", None),
                                            "cpu_user_seconds": times.user, "cpu_system_seconds": times.system,
                                            "threads": item.num_threads()})
                        except psutil.NoSuchProcess:
                            pass
                    if parent.pid not in {entry["pid"] for entry in entries} or any(e["pss_bytes"] is None for e in entries):
                        raise RuntimeError("An owned-process resource sample is incomplete.")
                    system = psutil.virtual_memory()
                    sample = {"elapsed_seconds": round(elapsed, 6), "rss_bytes": sum(e["rss_bytes"] for e in entries),
                              "pss_bytes": sum(e["pss_bytes"] for e in entries), "processes": entries,
                              "system_available_bytes": system.available, "system_total_bytes": system.total,
                              "active_case": case_active}
                    samples.write(json.dumps(sample, separators=(",", ":"), allow_nan=False) + "\n")
                    samples.flush()
                    count += 1
                    if peak_rss is None or sample["rss_bytes"] > peak_rss["rss_bytes"]:
                        peak_rss = sample
                    if peak_pss is None or sample["pss_bytes"] > peak_pss["pss_bytes"]:
                        peak_pss = sample
                    minimum_available = min(minimum_available if minimum_available is not None else system.available,
                                            system.available)
                    if sample["rss_bytes"] > limits["rss_bytes"]:
                        report["stop_reason"] = "process_tree_memory_limit"
                except Exception as error:
                    report["measurement_errors"].append({"type": type(error).__name__, "message": str(error)})
                    report["stop_reason"] = "incomplete_resource_measurement"
                if elapsed > limits["total_seconds"]:
                    report["stop_reason"] = "aggregate_time_limit"
                if not initialized and elapsed > limits["initialization_seconds"]:
                    report["stop_reason"] = "initialization_time_limit"
                if case_started is not None and now - case_started > limits["case_seconds"]:
                    report["stop_reason"] = "source_case_time_limit"
                if report.get("stop_reason"):
                    stop_owned(process, identities)
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    log.write(chunk)
                    log.flush()
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line.startswith(b"PERSON_EVENT "):
                            event = json.loads(line[len(b"PERSON_EVENT "):])
                            event["observed_elapsed_seconds"] = round(time.monotonic() - started, 6)
                            report["events"].append(event)
                            if event["event"] == "initialized":
                                initialized = True
                            elif event["event"] == "case_start":
                                initialized = True
                                case_started = time.monotonic()
                                case_active = event["id"]
                            elif event["event"] in {"case_complete", "case_failed"}:
                                case_started = None
                                case_active = None
                            print(json.dumps(event, ensure_ascii=False), flush=True)
                if elapsed - last_checkpoint >= 1:
                    report.update({"sample_count": count, "peak_rss_sample": peak_rss, "peak_pss_sample": peak_pss})
                    save(output, report)
                    last_checkpoint = elapsed
                if process.poll() is not None and not selector.get_map():
                    break
            selector.close()
            report["worker_exit_code"] = process.wait()
            report["complete"] = not report.get("stop_reason") and process.returncode == 0
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["owned_processes_stopped"] = stop_owned(process, identities)
        report["owned_process_identities"] = [{"pid": pid, "created": created} for pid, created in identities.items()]
        report["sample_count"] = count
        report["sample_interval_seconds"] = 0.1
        report["peak_rss_sample"] = peak_rss
        report["peak_pss_sample"] = peak_pss
        report["peak_rss_mib"] = round(peak_rss["rss_bytes"] / 1024**2, 1) if peak_rss else None
        report["peak_pss_mib"] = round(peak_pss["pss_bytes"] / 1024**2, 1) if peak_pss else None
        report["minimum_system_available_bytes"] = minimum_available
        report["measurement_complete"] = count > 0 and not report["measurement_errors"]
        report["samples_file"] = samples_path.name
        report["samples_sha256"] = sha(samples_path) if samples_path.exists() else None
        report["elapsed_seconds"] = round(time.monotonic() - started, 6)
        report["finished_at"] = utc()
        report["passed"] = (report["complete"] and report["measurement_complete"]
                            and report["owned_processes_stopped"] and not report.get("error"))
        save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "infer"), required=True)
    args = parser.parse_args()
    plan = read_plan()
    freeze_name = "setup-freeze" if args.phase == "prepare" else "inference-freeze"
    verify_freeze(freeze_name)
    runtime = Path(plan["runtime"]["owned_root"])
    environment = os.environ.copy()
    environment.update(plan["runtime"]["environment"])
    environment.update({"PYTHONPATH": plan["runtime"]["owned_package_target"],
                        "HF_HOME": str(runtime / "hf-cache"), "TMPDIR": str(runtime / "tmp"),
                        "PYTHONDONTWRITEBYTECODE": "1"})
    limits = {"rss_bytes": plan["limits"]["process_tree_rss_bytes"],
              "initialization_seconds": plan["limits"]["initialization_seconds"],
              "case_seconds": plan["limits"]["per_case_seconds"],
              "total_seconds": plan["limits"]["aggregate_worker_seconds"]}
    output = HERE / (args.phase + "-resources.json")
    report = monitor([plan["runtime"]["python"], str(HERE / "native_worker.py"), "--phase", args.phase],
                     environment, runtime / "private" / (args.phase + ".log"), output,
                     HERE / (args.phase + "-samples.jsonl"), limits,
                     {"phase": args.phase, "plan_sha256": PLAN_SHA256,
                      "phase_freeze_sha256": sha(HERE / (freeze_name + ".json")),
                      "worker_sha256": sha(HERE / "native_worker.py"), "observer_sha256": sha(__file__),
                      "translation_calls": 0, "whole_app_memory_approval": False})
    phase_output = HERE / ("prepare.json" if args.phase == "prepare" else "execution.json")
    report["phase_report_sha256"] = sha(phase_output) if phase_output.exists() else None
    report["phase_report_complete"] = (json.loads(phase_output.read_text()).get("complete") is True
                                       if phase_output.exists() else False)
    report["passed"] &= report["phase_report_complete"]
    read_plan()
    verify_freeze(freeze_name)
    save(output, report)
    emit("supervisor_complete", phase=args.phase, passed=report["passed"], elapsed_seconds=report["elapsed_seconds"],
         peak_rss_mib=report["peak_rss_mib"], peak_pss_mib=report["peak_pss_mib"], report=str(output))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

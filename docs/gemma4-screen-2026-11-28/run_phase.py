#!/usr/bin/env python3
"""Externally stop and measure the one owned Gemma setup or inference phase."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import psutil
from experiment import HERE, ROOT, read_plan, save, sha
sys.path.insert(0, str(ROOT / "tests"))
from smoke_full_local_workflow import update_peaks
from measure_summary_memory import oom_deltas, oom_snapshot


def stop_owned(process):
    try:
        descendants = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except ProcessLookupError:
        pass
    # Native runners may create a process group of their own. Retain the
    # process objects captured from this worker's actual descendants only.
    for child in descendants:
        try:
            if child.is_running():
                child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(descendants, timeout=3)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=3)


def monitor(command, environment, private_log, output, phase, limits, metadata):
    report = {"schema_version": 1, "phase": phase, "started_at": datetime.now(timezone.utc).isoformat(),
              "complete": False, "passed": False, "semantic_quality": "unreviewed",
              "events": [], "limits": limits, **metadata}
    state = {"sample_count": 0, "sample_interval_seconds": 0.2,
             "pss_available_for_every_sample": True, "errors": [],
             "scope": "Concurrent monitor process tree, including its owned native worker and descendants, deduplicated by PID.",
             "excluded": "Operating system, browser, unrelated processes and filesystem cache outside process residency; not whole-machine approval.",
             "rss_interpretation": "Concurrent summed RSS may double-count shared pages.",
             "pss_interpretation": "PSS apportions shared memory and is available only for complete readable samples.",
             "sampling_limit": "Sequential process scans at 0.2-second intervals may miss transient peaks."}
    parent = psutil.Process(os.getpid())
    process = None
    before_oom = oom_snapshot([os.getpid()])
    started = time.monotonic()
    active_case_started = None
    initialized = False
    buffer = b""
    save(output, report)
    fd = os.open(private_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as log:
            process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            selector = selectors.DefaultSelector()
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            last_checkpoint = 0.0
            while True:
                now = time.monotonic()
                elapsed = now - started
                try:
                    processes = {item.pid: item for item in [parent, *parent.children(recursive=True)]}
                    entries = []
                    for item in processes.values():
                        try:
                            entries.append({"pid": item.pid, "name": item.name(),
                                            "rss_bytes": item.memory_info().rss,
                                            "pss_bytes": getattr(item.memory_full_info(), "pss", None)})
                        except psutil.NoSuchProcess:
                            pass
                    if parent.pid not in {entry["pid"] for entry in entries}:
                        raise RuntimeError("Required monitor process is missing from the sample.")
                    update_peaks(state, entries, elapsed)
                    available = psutil.virtual_memory()
                    host = report.setdefault("host_observation", {"total_mib": round(available.total / 1024**2, 1),
                                                                   "minimum_available_mib": round(available.available / 1024**2, 1),
                                                                   "scope": "Uncontrolled host observation; unrelated activity can affect it."})
                    host["minimum_available_mib"] = min(host["minimum_available_mib"], round(available.available / 1024**2, 1))
                except Exception as error:
                    state["errors"].append(type(error).__name__ + ": " + str(error))
                    report["stop_reason"] = "memory_measurement_failed"
                peak = state.get("peak_rss_sample", {}).get("rss_bytes", 0)
                if peak > limits["process_budget_mib"] * 1024**2:
                    report["stop_reason"] = "process_memory_budget_exceeded"
                if elapsed > limits["phase_seconds"]:
                    report["stop_reason"] = "phase_time_limit"
                if phase == "infer":
                    if not initialized and elapsed > limits["initialization_seconds"]:
                        report["stop_reason"] = "initialization_time_limit"
                    if active_case_started is not None and now - active_case_started > limits["case_seconds"]:
                        report["stop_reason"] = "case_time_limit"
                if report.get("stop_reason"):
                    stop_owned(process)
                for key, _mask in selector.select(timeout=0.2):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    log.write(chunk)
                    log.flush()
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line.startswith(b"GEMMA_EVENT "):
                            event = json.loads(line[len(b"GEMMA_EVENT "):])
                            event["observed_at_seconds"] = round(elapsed, 3)
                            report["events"].append(event)
                            if event["event"] == "case_start":
                                initialized = True
                                active_case_started = time.monotonic()
                            elif event["event"] in {"case_complete", "case_failed"}:
                                active_case_started = None
                            print(json.dumps(event), flush=True)
                report["memory"] = state
                if elapsed - last_checkpoint >= 1:
                    save(output, report)
                    last_checkpoint = elapsed
                if process.poll() is not None and not selector.get_map():
                    break
            selector.close()
            report["worker_exit_code"] = process.wait()
            report["complete"] = not report.get("stop_reason") and report["worker_exit_code"] == 0
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        report["complete"] = False
    finally:
        if process is not None:
            stop_owned(process)
            report["worker_exit_code"] = process.poll()
            report["owned_process_group_stopped"] = process.poll() is not None
        state["measurement_complete"] = state["sample_count"] > 0 and not state["errors"]
        peak = state.get("peak_rss_sample")
        state["peak_combined_rss_mib"] = round(peak["rss_bytes"] / 1024**2, 1) if peak else None
        peak = state.get("peak_pss_sample")
        state["peak_combined_pss_mib"] = (round(peak["pss_bytes"] / 1024**2, 1)
                                            if peak and state["pss_available_for_every_sample"] else None)
        report["memory"] = state
        after_oom = oom_snapshot([os.getpid()])
        report["oom_counters"] = {"before": before_oom, "after": after_oom,
                                   "deltas": oom_deltas(before_oom, after_oom)}
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["passed"] = (report["complete"] and state["measurement_complete"]
                            and state["peak_combined_rss_mib"] <= limits["process_budget_mib"]
                            and report.get("owned_process_group_stopped") is True)
        save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "infer"), required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    plan = read_plan()
    output = HERE / (args.phase + "-resources.json")
    if output.exists():
        raise ValueError("Refusing to overwrite previous resource evidence.")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("External stop.")))
    command = [sys.executable, str(HERE / "experiment.py"), "--phase", args.phase, "--runtime-dir", str(runtime)]
    limits = {"process_budget_mib": 6144,
              "phase_seconds": plan["limits"][args.phase + "_seconds"],
              "initialization_seconds": plan["limits"]["initialization_seconds"],
              "case_seconds": 240}
    report = monitor(command, environment, runtime / (args.phase + "-worker-private.log"), output,
                     args.phase, limits, {"plan_sha256": sha(HERE / "plan.json"),
                     "runner_sha256": sha(__file__), "worker_sha256": sha(HERE / "experiment.py"),
                     "whole_machine_resource_approval": False})
    report["frozen_inputs_unchanged"] = all(sha(ROOT / name) == expected for name, expected in plan["source_sha256"].items())
    phase_output = HERE / (args.phase + ".json")
    report["phase_report_sha256"] = sha(phase_output) if phase_output.exists() else None
    report["passed"] &= report["frozen_inputs_unchanged"]
    save(output, report)
    print(json.dumps({"phase": args.phase, "passed": report["passed"], "report": str(output),
                      "peak_rss_mib": report["memory"]["peak_combined_rss_mib"],
                      "elapsed_seconds": report["elapsed_seconds"]}), flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

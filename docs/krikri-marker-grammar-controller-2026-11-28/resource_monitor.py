"""Reviewed resource monitor, adapted only for this stage's event prefix and helpers."""
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

from context import common, utc
save = common.save
sha = common.sha


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


def owned_group(process, identities):
    """Find this worker's original session/group even after its leader exits."""
    if process is None:
        return []
    group = process.pid
    # Never reinterpret a reused leader PID as the original owned session.
    try:
        leader = psutil.Process(group)
        if leader.create_time() != identities[group]:
            raise RuntimeError("The original worker leader PID was reused; group ownership is ambiguous.")
    except psutil.NoSuchProcess:
        pass
    members = []
    for candidate in psutil.process_iter(["pid", "create_time", "status"]):
        try:
            if os.getpgid(candidate.pid) == group and os.getsid(candidate.pid) == group:
                identities[candidate.pid] = candidate.create_time()
                if candidate.status() != psutil.STATUS_ZOMBIE:
                    members.append(candidate)
        except (ProcessLookupError, psutil.NoSuchProcess):
            pass
    return members


def stop_owned(process, identities):
    members = owned_group(process, identities)
    # A native child may remain in the original group after the leader exits.
    # Group cleanup must therefore be independent of Popen.poll().
    if process is not None and members:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in alive_owned(identities):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, active = psutil.wait_procs(alive_owned(identities), timeout=3)
    if process is not None and owned_group(process, identities):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in active:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(active, timeout=3)
    if process is not None:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    return not owned_group(process, identities) and not alive_owned(identities)


def monitor(command, environment, private_log, output, samples_path, limits, metadata, policy_check=None):
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
                    processes = {p.pid: p for p in [parent, *parent.children(recursive=True),
                                                   *alive_owned(identities), *owned_group(process, identities)]}
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
                    if policy_check is not None:
                        sample["storage"] = policy_check()
                        if sample["storage"].get("violation"):
                            report["stop_reason"] = "storage_policy_limit"
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
                        if line.startswith(b"GEMMA_EVENT "):
                            event = json.loads(line[len(b"GEMMA_EVENT "):])
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
                    survivors = [item for item in owned_group(process, identities) if item.pid != process.pid]
                    survivors.extend(item for item in alive_owned(identities)
                                     if item.pid != process.pid and item.pid not in {p.pid for p in survivors})
                    if survivors:
                        report["survivors_at_leader_exit"] = [item.pid for item in survivors]
                        report["stop_reason"] = "owned_child_survived_worker_exit"
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
        if policy_check is not None:
            try:
                report["storage_after_cleanup"] = policy_check()
                if report["storage_after_cleanup"].get("violation"):
                    report["complete"] = False
                    report["stop_reason"] = "storage_policy_limit"
            except Exception as error:
                report["measurement_errors"].append({"type": type(error).__name__, "message": str(error)})
                report["measurement_complete"] = False
                report["complete"] = False
                report["stop_reason"] = "incomplete_storage_measurement"
        report["passed"] = (report["complete"] and report["measurement_complete"]
                            and report["owned_processes_stopped"] and not report.get("error"))
        save(output, report)
    return report


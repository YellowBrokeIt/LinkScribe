#!/usr/bin/env python3
"""Measure a fully live summary evaluator and existing Ollama process tree.

Starts only the evaluator child, never a model service or replay transport.
Atomic checkpoints preserve partial memory evidence if the child fails.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time

from smoke_full_local_workflow import ProcessMemory, file_sha, memory_budget

ROOT = Path(__file__).resolve().parents[1]
OOM_KEYS = {"oom", "oom_kill", "oom_group_kill"}


def cgroup_event_paths(pid, proc_root=Path("/proc")):
    """Resolve v2 membership against that process's actual cgroup mount."""
    memberships = (proc_root / str(pid) / "cgroup").read_text().splitlines()
    group = next((line.split(":", 2)[2] for line in memberships if line.startswith("0::")), None)
    if group is None:
        return []  # Do not invent v2 counters for a v1/unavailable environment.
    paths = []
    for line in (proc_root / str(pid) / "mountinfo").read_text().splitlines():
        before, separator, after = line.partition(" - ")
        fields = before.split()
        if not separator or not after.split() or after.split()[0] != "cgroup2" or len(fields) < 5:
            continue
        unescape = lambda value: value.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
        mount_root, mount_point = PurePosixPath(unescape(fields[3])), Path(unescape(fields[4]))
        try:
            relative = PurePosixPath(group).relative_to(mount_root)
        except ValueError:
            continue
        paths.extend(mount_point / str(relative) / name for name in ("memory.events", "memory.events.local"))
    return sorted(set(paths))


def oom_snapshot(pids, proc_root=Path("/proc")):
    result = {"files": {}, "unavailable": [],
              "interpretation": "Counters belong to the indicated host/cgroup scope. A change alone cannot attribute a kill to this run; missing counters do not prove zero OOM events."}
    paths = {proc_root / "vmstat": "host_global"}
    for pid in sorted(set(pids)):
        try:
            found = cgroup_event_paths(pid, proc_root)
            if not found:
                result["unavailable"].append(f"No resolvable cgroup-v2 event files for PID {pid}.")
            for path in found:
                paths[path] = "process_cgroup"
        except OSError as error:
            result["unavailable"].append(f"PID {pid} membership: {type(error).__name__}")
    for path, scope in paths.items():
        try:
            text = path.read_text()
            counts = {key: int(value) for line in text.splitlines() if len(parts := line.split()) == 2
                      for key, value in [parts] if key in OOM_KEYS}
            if not counts:
                raise ValueError("No OOM counters present")
            result["files"][str(path)] = {"scope": scope, "counters": counts}
        except (OSError, ValueError) as error:
            result["unavailable"].append(f"{path}: {type(error).__name__}")
    return result


def oom_deltas(before, after):
    deltas = {}
    for path, entry in before["files"].items():
        later = after["files"].get(path)
        if later is None:
            continue
        changes = {key: later["counters"][key] - value for key, value in entry["counters"].items()
                   if key in later["counters"]}
        deltas[path] = {"scope": entry["scope"], "counters": changes,
                        "counter_reset_or_scope_change": any(value < 0 for value in changes.values())}
    return deltas


def checkpoint(path, report):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, ensure_ascii=True, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def terminate_child(process, psutil):
    """Stop only this wrapper's evaluator and its recorded child processes."""
    try:
        descendants = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    process.terminate()
    for child in reversed(descendants):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(descendants, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(timeout=5)


def accepted(report):
    return (report["complete"] and report.get("evaluator_exit_code") == 0
        and report.get("summary_report_complete") is True and report.get("source_unchanged") is True
        and report.get("corpus_unchanged") is True
        and report.get("memory", {}).get("measurement_complete") is True
        and report.get("memory_budget_passed") is not False
        and not report.get("error") and not report.get("cleanup_errors"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "tests/fixtures/summary_quality_cases.json")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-pid", type=int, default=os.getenv("LINKSCRIBE_QA_OLLAMA_PID"))
    parser.add_argument("--memory-budget-mib", type=memory_budget)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout_seconds <= 7200:
        parser.error("--timeout-seconds must be between 1 and 7200.")
    if args.output.resolve() == args.summary_output.resolve() or args.output.exists() or args.summary_output.exists():
        parser.error("Use separate new output paths; previous evidence is never overwritten.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "complete": False, "passed": False,
              "evidence_type": "fully_live_summary_with_process_memory", "semantic_quality": "unreviewed",
              "created_utc": datetime.now(timezone.utc).isoformat(), "selected_cases": args.case,
              "summary_report_path": str(args.summary_output.resolve()), "monitor_pid": os.getpid(),
              "memory_budget_mib": args.memory_budget_mib, "sample_checkpoint_interval_seconds": 1}
    source_names = ("app.py", "enhancements.py", "library.py", "tests/evaluate_summary_quality.py",
                    "tests/measure_summary_memory.py", "tests/smoke_full_local_workflow.py")
    sampler = process = None
    sampler_started = False
    started = time.monotonic()
    log_path = args.output.with_suffix(".evaluator.log")
    checkpoint(args.output, report)
    try:
        if args.ollama_pid is None:
            raise ValueError("Supply the existing Ollama daemon PID or LINKSCRIBE_QA_OLLAMA_PID.")
        sampler = ProcessMemory(int(args.ollama_pid))
        sampler.start()
        sampler_started = True
        import enhancements
        sampler.verify_endpoint(enhancements.ollama_settings()[0])
        sampler.state["scope"] = "Monitor and descendants (actual evaluator/app and restart child), plus verified Ollama daemon and descendants, deduplicated by PID."
        report["source_sha256_before"] = {name: file_sha(ROOT / name) for name in source_names}
        report["corpus_sha256"] = file_sha(args.corpus)
        report["oom_before"] = oom_snapshot([os.getpid(), int(args.ollama_pid)])
        settings = ("LLAMA_ARG_CACHE_RAM", "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS",
                    "OLLAMA_CONTEXT_LENGTH", "OLLAMA_KEEP_ALIVE", "OLLAMA_NO_CLOUD")
        try:
            daemon_env = sampler.daemon.environ()
            report["observed_daemon_environment"] = {name: daemon_env.get(name) for name in settings}
        except Exception as error:
            report["observed_daemon_environment_error"] = type(error).__name__
        report["client_settings"] = {name: os.getenv(name) for name in
            ("LINKSCRIBE_OLLAMA_MODEL", "LINKSCRIBE_OLLAMA_THREADS", "LINKSCRIBE_OLLAMA_RETAIN_MODELS")}
        report["host_memory_bytes"] = sampler.psutil.virtual_memory().total
        command = [sys.executable, str(ROOT / "tests/evaluate_summary_quality.py"),
                   "--corpus", str(args.corpus.resolve()), "--output", str(args.summary_output.resolve())]
        for case in args.case:
            command.extend(["--case", case])
        report["command"] = command
        report["evaluator_log"] = str(log_path.resolve())
        with log_path.open("w") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            report["evaluator_pid"] = process.pid
            while process.poll() is None:
                report["memory"] = sampler.snapshot()
                report["elapsed_seconds"] = round(time.monotonic() - started, 3)
                checkpoint(args.output, report)
                if time.monotonic() - started > args.timeout_seconds:
                    raise TimeoutError("The full summary evaluation exceeded its total runtime limit.")
                time.sleep(1)
        report["evaluator_exit_code"] = process.returncode
        if args.summary_output.exists():
            summary = json.loads(args.summary_output.read_text())
            report["summary_report_sha256"] = file_sha(args.summary_output)
            report["summary_report_complete"] = summary.get("complete") is True
        report["evaluator_finished"] = True
        report["complete"] = report.get("summary_report_complete") is True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["cleanup_errors"] = []
        try:
            if process is not None and process.poll() is None:
                terminate_child(process, sampler.psutil)
                report["evaluator_exit_code"] = process.returncode
        except Exception as error:
            report["cleanup_errors"].append(f"Evaluator cleanup: {type(error).__name__}: {error}")
        if sampler_started:
            try:
                sampler.stop()
            except Exception as error:
                report["cleanup_errors"].append(f"Sampler cleanup: {type(error).__name__}: {error}")
        if sampler is not None:
            report["memory"] = sampler.snapshot()
            report["oom_after"] = oom_snapshot([os.getpid(), int(args.ollama_pid)])
            report["oom_deltas"] = oom_deltas(report.get("oom_before", {"files": {}}), report["oom_after"])
            peak = report["memory"]["peak_combined_rss_mib"]
            report["memory_budget_passed"] = (peak <= args.memory_budget_mib
                if peak is not None and args.memory_budget_mib is not None else None)
        try:
            report["source_sha256_after"] = {name: file_sha(ROOT / name) for name in source_names}
            report["source_unchanged"] = report.get("source_sha256_before") == report["source_sha256_after"]
            report["corpus_sha256_after"] = file_sha(args.corpus)
            report["corpus_unchanged"] = report.get("corpus_sha256") == report["corpus_sha256_after"]
        except OSError as error:
            report["cleanup_errors"].append(f"Final fingerprint: {type(error).__name__}: {error}")
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["passed"] = accepted(report)
        checkpoint(args.output, report)
    print(json.dumps({key: report.get(key) for key in ("complete", "passed", "evaluator_exit_code", "elapsed_seconds", "error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

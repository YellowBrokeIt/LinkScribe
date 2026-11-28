"""Validate the prepared plan; run its two bounded arms only with --execute.

The root coordinator must release the local model slot before execution.
This Linux-only controller stops its own process group at the frozen limits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def group_rss(group):
    total = 0
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(") ", 1)[1].split()
            if int(fields[2]) != group:
                continue
            row = next(line for line in (directory / "status").read_text().splitlines() if line.startswith("VmRSS:"))
            total += int(row.split()[1]) * 1024
        except (OSError, StopIteration, ValueError, IndexError):
            continue
    return total


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    assert sys.platform == "linux"
    assert sha(__file__) == plan["controller_sha256"]
    assert sha(plan["runner_path"]) == plan["runner_sha256"]
    assert sha(plan["model_bin_path"]) == plan["model_bin_sha256"]
    assert sha(Path(plan["candidate"]["source_root"]) / "app.py") == plan["candidate"]["app_sha256"]
    for film in plan["films"].values():
        assert sha(film["audio_path"]) == film["source_identity"]["media_sha256"]
        assert sha(film["fixture_manifest_path"]) == film["fixture_manifest_sha256"]
        assert sha(film["reference_path"]) == film["reference_sha256"]
    print(json.dumps({"plan_validated": True, "plan_sha256": sha(args.plan), "execute": args.execute}), flush=True)
    if not args.execute:
        return 0
    output = Path(plan["execution_output_directory"])
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    results = []
    for name in plan["execution_order"]:
        film = plan["films"][name]
        report_path = output / (name + "-report.json")
        command = [plan["python_executable"], plan["runner_path"], "--source-root", plan["candidate"]["source_root"],
                   "--plan", str(args.plan.resolve()), "--film", name,
                   "--manifest", film["fixture_manifest_path"], "--output", str(report_path),
                   "--model", "small", "--model-provenance", plan["model_provenance_path"],
                   "--language-mode", "auto", "--timeout", str(plan["per_inference_timeout_seconds"])]
        env = os.environ.copy()
        env.update(HF_HOME=plan["cache_root"], HF_HUB_OFFLINE="1", LINKSCRIBE_DEVICE="cpu",
                   PYTHONPATH=plan["candidate"]["source_root"])
        item = {"film": name, "started_at": datetime.now(timezone.utc).isoformat(), "command": command}
        started, peak, reason = time.monotonic(), 0, None
        with (output / (name + "-run.log")).open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            try:
                while process.poll() is None:
                    peak = max(peak, group_rss(process.pid))
                    if peak > plan["process_group_rss_limit_bytes"]:
                        reason = "process_group_rss_limit"
                    elif time.monotonic() - began >= plan["total_execution_timeout_seconds"]:
                        reason = "total_execution_time_limit"
                    elif time.monotonic() - started >= plan["per_process_wall_timeout_seconds"]:
                        reason = "process_time_limit"
                    if reason:
                        stop(process)
                        break
                    time.sleep(0.25)
            finally:
                stop(process)
        item.update(finished_at=datetime.now(timezone.utc).isoformat(), returncode=process.returncode,
                    observed_process_group_peak_rss_bytes=peak, stopped_at_limit=reason)
        if report_path.exists():
            measured = json.loads(report_path.read_text()).get("process_peak_rss_bytes")
            item["harness_process_peak_rss_bytes"] = measured
            if measured and measured > plan["process_group_rss_limit_bytes"]:
                item["stopped_at_limit"] = "reported_peak_exceeded_memory_limit"
        results.append(item)
        (output / "execution.json").write_text(json.dumps({"plan_sha256": sha(args.plan), "arms": results}, indent=2) + "\n")
        print(json.dumps(item), flush=True)
        if item["returncode"] != 0 or item["stopped_at_limit"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

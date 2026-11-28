#!/usr/bin/env python3
"""Apply the unchanged external memory monitor to one thinking-only attempt."""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import signal
import sys
from run_case import HERE, ROOT, ORIGINAL, common, read_freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    freeze, _candidate = read_freeze()
    output = HERE / "resources.json"
    if output.exists():
        raise ValueError("Refusing to repeat the retained single attempt.")
    spec = importlib.util.spec_from_file_location("unchanged_gemma_monitor", ORIGINAL / "run_phase.py")
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("External stop.")))
    command = [sys.executable, str(HERE / "run_case.py"), "--runtime-dir", str(runtime)]
    limits = {"process_budget_mib": 6144, "phase_seconds": 600,
              "initialization_seconds": 180, "case_seconds": 600}
    report = monitor.monitor(command, environment, runtime / (HERE.name + "-worker-private.log"), output, "infer", limits,
                             {"inference_freeze_sha256": common.sha(HERE / "inference-freeze.json"),
                              "runner_sha256": common.sha(__file__), "worker_sha256": common.sha(HERE / "run_case.py"),
                              "whole_machine_resource_approval": False})
    report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in freeze["source_sha256"].items())
    report["execution_report_sha256"] = common.sha(HERE / "execution.json") if (HERE / "execution.json").exists() else None
    report["passed"] &= report["frozen_inputs_unchanged"]
    common.save(output, report)
    print({"complete": report["complete"], "passed": report["passed"], "elapsed_seconds": report["elapsed_seconds"],
           "peak_rss_mib": report["memory"]["peak_combined_rss_mib"], "report": str(output)}, flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

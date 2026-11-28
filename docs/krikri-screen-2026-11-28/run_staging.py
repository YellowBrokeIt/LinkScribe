#!/usr/bin/env python3
"""Bound and measure the authorized cleanup/download workers."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
from staging import HERE, ROOT, ORIGINAL, common, read_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("cleanup", "download"), required=True)
    args = parser.parse_args()
    plan = read_plan()
    runtime = Path(plan["storage"]["owned_runtime_directory"])
    runtime.mkdir(parents=True, exist_ok=True)
    output = HERE / (args.action + "-resources.json")
    if output.exists():
        raise ValueError("Refusing to repeat a measured preparation phase.")
    spec = importlib.util.spec_from_file_location("retained_model_monitor", ORIGINAL / "run_phase.py")
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    limits = {"process_budget_mib": 6144, "phase_seconds": plan["limits"][args.action + "_seconds"],
              "initialization_seconds": 180, "case_seconds": 600}
    report = monitor.monitor([sys.executable, str(HERE / "staging.py"), "--action", args.action], env,
                             runtime / (args.action + "-worker-private.log"), output, args.action, limits,
                             {"plan_sha256": common.sha(HERE / "plan.json"), "runner_sha256": common.sha(__file__),
                              "worker_sha256": common.sha(HERE / "staging.py"), "whole_machine_resource_approval": False})
    report["phase_report_sha256"] = common.sha(HERE / (args.action + ".json")) if (HERE / (args.action + ".json")).exists() else None
    report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
    report["passed"] &= report["frozen_inputs_unchanged"]
    common.save(output, report)
    print({"action": args.action, "passed": report["passed"], "elapsed_seconds": report["elapsed_seconds"],
           "peak_rss_mib": report["memory"]["peak_combined_rss_mib"]}, flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

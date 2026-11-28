"""Reuse the proven external monitor with unchanged caps and new private logs."""
import argparse
import importlib.util
import os
import sys
from context import BASE, HERE, ROOT, PRIVATE, common, read_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "infer"), required=True)
    args = parser.parse_args()
    plan = read_plan()
    output = HERE / (args.phase + "-resources.json")
    if output.exists():
        raise ValueError("Refusing to repeat a measured instruction-only phase.")
    spec = importlib.util.spec_from_file_location("unchanged_tree_monitor", ROOT / "docs/gemma4-screen-2026-11-28/run_phase.py")
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    limits = {"process_budget_mib": 6144, "phase_seconds": 600 if args.phase == "prepare" else 1800,
              "initialization_seconds": 180, "case_seconds": 600}
    worker = HERE / ("prepare_native.py" if args.phase == "prepare" else "infer_native.py")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    report = monitor.monitor([sys.executable, str(worker)], environment,
                             PRIVATE / (args.phase + "-worker-private.log"), output, "infer", limits,
                             {"actual_phase": args.phase, "plan_sha256": common.sha(HERE / "plan.json"),
                              "runner_sha256": common.sha(__file__), "worker_sha256": common.sha(worker),
                              "whole_machine_resource_approval": False})
    phase_path = HERE / ("prepare.json" if args.phase == "prepare" else "execution.json")
    report["phase_report_sha256"] = common.sha(phase_path) if phase_path.exists() else None
    report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
    report["passed"] &= report["frozen_inputs_unchanged"]
    common.save(output, report)
    print({"phase": args.phase, "passed": report["passed"], "elapsed_seconds": report["elapsed_seconds"],
           "peak_rss_mib": report["memory"]["peak_combined_rss_mib"]}, flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

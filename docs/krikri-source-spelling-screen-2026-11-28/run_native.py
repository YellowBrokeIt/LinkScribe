"""Use the reviewed orphan-safe observer and retain every resource sample."""
import argparse
import os
import shutil
import sys

from context import HERE, PRIVATE, common, read_plan, storage_reserve
from resource_monitor import monitor
from execution_gate import authorize_phase


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "infer"), required=True)
    args = parser.parse_args()
    authorize_phase(args.phase)
    plan = read_plan()
    free_before = storage_reserve()
    output = HERE / (args.phase + "-resources.json")
    samples = HERE / (args.phase + "-samples.jsonl")
    worker = HERE / ("prepare_native.py" if args.phase == "prepare" else "infer_native.py")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    limits = {"rss_bytes": 6144 * 1024 ** 2, "total_seconds": 600 if args.phase == "prepare" else 1800,
              "initialization_seconds": 180, "case_seconds": 600}
    report = monitor([sys.executable, str(worker)], environment, PRIVATE / (args.phase + "-worker-private.log"),
                     output, samples, limits,
                     {"phase": args.phase, "plan_sha256": common.sha(HERE / "plan.json"),
                      "authorization_sha256": common.sha(HERE / (args.phase + "-authorization.json")),
                      "worker_sha256": common.sha(worker), "observer_sha256": common.sha(HERE / "resource_monitor.py"),
                      "free_disk_before_bytes": free_before, "whole_app_resource_approval": False})
    phase_output = HERE / ("prepare.json" if args.phase == "prepare" else "execution.json")
    report["phase_report_sha256"] = common.sha(phase_output) if phase_output.exists() else None
    report["frozen_inputs_unchanged"] = all(common.sha(HERE.parents[1] / p) == h for p, h in plan["source_sha256"].items())
    report["free_disk_after_bytes"] = shutil.disk_usage(HERE).free
    report["disk_reserve_retained"] = report["free_disk_after_bytes"] >= 1024 ** 3
    report["passed"] &= report["frozen_inputs_unchanged"] and report["disk_reserve_retained"]
    common.save(output, report)
    print({"phase": args.phase, "passed": report["passed"], "elapsed_seconds": report["elapsed_seconds"],
           "peak_rss_mib": report["peak_rss_mib"], "samples": report["sample_count"]}, flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

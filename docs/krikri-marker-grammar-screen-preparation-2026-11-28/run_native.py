"""Conditional one-shot controller; the source preparation grants no execution."""
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

import psutil

from context import HERE, ROOT, PRIVATE, common, storage_reserve, utc
from execution_gate import authorize_phase
from resource_monitor import monitor


def main():
    receipt, plan, native, freeze = authorize_phase("infer")
    if str(Path(sys.executable).absolute()) != plan["python_runtime"]["executable"]:
        raise ValueError("The screen requires the original existing interpreter.")
    for name in ("infer-claim.json", "infer-resources.json", "infer-samples.jsonl", "execution.json"):
        if (HERE / name).exists():
            raise ValueError("This original-six screen was already claimed or attempted; no retry.")
    free_before = storage_reserve()
    claim = {"phase": "infer", "controller_pid": os.getpid(), "controller_created": psutil.Process().create_time(),
             "created_at": utc(), "nonce": uuid.uuid4().hex, "plan_sha256": common.sha(HERE / "plan.json"),
             "authorization_sha256": common.sha(HERE / "infer-authorization.json")}
    with (HERE / "infer-claim.json").open("x", encoding="utf-8") as stream:
        json.dump(claim, stream, indent=2); stream.write("\n")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
                       GRAMMAR_CONTROLLER_PID=str(os.getpid()),
                       GRAMMAR_PHASE_CLAIM_SHA256=common.sha(HERE / "infer-claim.json"))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    output, samples = HERE / "infer-resources.json", HERE / "infer-samples.jsonl"
    worker = HERE / "infer_native.py"
    limits = {"rss_bytes": 6144 * 1024 ** 2, "total_seconds": 1800,
              "initialization_seconds": 180, "case_seconds": 600}
    report = monitor([sys.executable, "-B", str(worker)], environment,
                     PRIVATE / "infer-worker-private.log", output, samples, limits,
                     {"phase": "infer", "plan_sha256": common.sha(HERE / "plan.json"),
                      "authorization_sha256": common.sha(HERE / "infer-authorization.json"),
                      "native_evidence_freeze_sha256": common.sha(HERE / "native-evidence-freeze.json"),
                      "worker_sha256": common.sha(worker), "observer_sha256": common.sha(HERE / "resource_monitor.py"),
                      "free_disk_before_bytes": free_before, "whole_app_resource_approval": False})
    phase = HERE / "execution.json"
    value = json.loads(phase.read_text(encoding="utf-8")) if phase.exists() else {}
    report["phase_report_sha256"] = common.sha(phase) if phase.exists() else None
    report["phase_report_complete"] = value.get("complete") is True
    report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
    report["free_disk_after_bytes"] = shutil.disk_usage(HERE).free
    report["disk_reserve_retained"] = report["free_disk_after_bytes"] >= 1024 ** 3
    report["passed"] &= (report["phase_report_complete"] and report["frozen_inputs_unchanged"]
                         and report["disk_reserve_retained"] and value.get("owned_daemon_stopped") is True)
    common.save(output, report)
    print({"passed": report["passed"], "elapsed_seconds": report["elapsed_seconds"],
           "peak_rss_mib": report["peak_rss_mib"], "samples": report["sample_count"]}, flush=True)
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

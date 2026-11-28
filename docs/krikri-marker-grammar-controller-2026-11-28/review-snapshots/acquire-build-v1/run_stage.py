"""Root-receipted controller. There is deliberately no generation phase."""
import argparse
import os
from pathlib import Path
import resource
import signal
import sys
import uuid

import psutil

from context import (HERE, OWNED, PHASES, common, read, sha, save, utc, verify_tools,
                     require_storage, storage_policy, phase_limits, verify_files)
from execution_gate import authorize_phase
from resource_monitor import monitor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    phase = parser.parse_args().phase
    receipt, plan, native, completed_elapsed = authorize_phase(phase)
    if str(Path(sys.executable).absolute()) != plan["python_runtime"]["executable"]:
        raise ValueError("Controller must run in the exact declared existing interpreter.")
    verify_tools(plan["extra_tool_bindings"])
    before = require_storage()
    for suffix in (".json", "-resources.json", "-samples.jsonl", "-claim.json"):
        if (HERE / (phase + suffix)).exists():
            raise ValueError("This phase was already claimed or attempted; no retry.")
    claim = {"schema_version": 1, "phase": phase, "controller_pid": os.getpid(),
             "controller_created": psutil.Process().create_time(), "created_at": utc(),
             "nonce": uuid.uuid4().hex, "authorization_sha256": sha(HERE / (phase + "-authorization.json")),
             "plan_sha256": sha(HERE / "plan.json")}
    claim_path = HERE / (phase + "-claim.json")
    fd = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        import json
        json.dump(claim, stream, indent=2); stream.write("\n")
    OWNED.mkdir(exist_ok=True)
    private = OWNED / "logs"; private.mkdir(exist_ok=True)
    maximum_file = native["disk"]["maximum_file_bytes"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_file, maximum_file))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Controller terminated.")))
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                   "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "GRAMMAR_CONTROLLER_PID": str(os.getpid()),
                   "GRAMMAR_PHASE_CLAIM_SHA256": sha(claim_path)}
    limits = phase_limits(native, phase, completed_elapsed)
    worker = HERE / "phase_worker.py"
    result = monitor([sys.executable, "-B", str(worker), "--phase", phase], environment,
                     private / (phase + "-worker-private.log"), HERE / (phase + "-resources.json"),
                     HERE / (phase + "-samples.jsonl"), limits,
                     {"phase": phase, "plan_sha256": sha(HERE / "plan.json"),
                      "native_plan_sha256": sha(Path(plan["native_plan_path"])),
                      "authorization_sha256": sha(HERE / (phase + "-authorization.json")),
                      "claim_sha256": sha(claim_path), "worker_sha256": sha(worker),
                      "observer_sha256": sha(HERE / "resource_monitor.py"),
                      "free_disk_before_bytes": before["free_bytes"],
                      "completed_predecessor_active_seconds": completed_elapsed,
                      "generation_authorized": False}, policy_check=storage_policy)
    phase_output = HERE / (phase + ".json")
    result["phase_report_sha256"] = sha(phase_output) if phase_output.exists() else None
    result["phase_report_complete"] = phase_output.exists() and read(phase_output).get("complete") is True
    result["storage_final"] = storage_policy()
    result["active_aggregate_seconds"] = completed_elapsed + result["elapsed_seconds"]
    try:
        verify_files(plan["source_sha256"])
        result["frozen_inputs_unchanged"] = True
    except Exception as error:
        result["frozen_inputs_unchanged"] = False
        result["final_identity_error"] = str(error)
    result["passed"] &= (result["phase_report_complete"] and result["frozen_inputs_unchanged"]
                          and not result["storage_final"]["violation"]
                          and result["active_aggregate_seconds"] <= native["aggregate_seconds"])
    save(HERE / (phase + "-resources.json"), result)
    print({"phase": phase, "passed": result["passed"], "elapsed_seconds": result["elapsed_seconds"],
           "peak_rss_mib": result["peak_rss_mib"], "generation_calls": 0}, flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

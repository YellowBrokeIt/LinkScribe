"""Separate root authorization after actual grammar review; no receipt here."""
import os
from pathlib import Path
import psutil

from context import HERE, ROOT, common, read_plan
from native_gate import read, require_native_evidence

RUNTIME_FILES = ("plan.json", "context.py", "execution_gate.py", "native_gate.py",
                 "format_projection.py", "run_native.py", "infer_native.py", "resource_monitor.py")


def verify_receipt(value, plan_sha, review_sha, native_freeze_sha):
    if (value.get("phase") != "infer" or value.get("plan_sha256") != plan_sha
            or value.get("independent_review_sha256") != review_sha
            or value.get("native_evidence_freeze_sha256") != native_freeze_sha):
        raise ValueError("Generation receipt must bind this exact source and independently reviewed actual native evidence.")
    if (value.get("root_authorized") is not True or value.get("generation_authorized") is not True
            or value.get("local_model_slot_reserved") is not True
            or value.get("runner_author_self_approval") is not False):
        raise ValueError("Separate root generation authority and an exclusive model slot are absent.")


def authorize_phase(phase):
    if phase != "infer":
        raise ValueError("This conditional screen has only one original-six inference phase.")
    plan = read_plan()
    path = HERE / "infer-authorization.json"
    if common.sha(path) != (HERE / "infer-authorization.sha256").read_text(encoding="utf-8").strip():
        raise ValueError("Root generation receipt changed.")
    value = read(path)
    review = ROOT / value["independent_review_path"]
    verify_receipt(value, common.sha(HERE / "plan.json"), common.sha(review),
                   common.sha(HERE / "native-evidence-freeze.json"))
    bindings = value.get("files_sha256", {})
    for relative, digest in bindings.items():
        if common.sha(ROOT / relative) != digest:
            raise ValueError("A root-authorized file changed: " + relative)
    for name in (*RUNTIME_FILES, "native-evidence-freeze.json"):
        relative = str((HERE / name).relative_to(ROOT))
        if bindings.get(relative) != common.sha(HERE / name):
            raise ValueError("Root receipt omits an execution binding: " + name)
    native, freeze = require_native_evidence()
    return value, plan, native, freeze


def verify_controller_parent():
    claim_path = HERE / "infer-claim.json"
    claim = read(claim_path)
    if (common.sha(claim_path) != os.environ.get("GRAMMAR_PHASE_CLAIM_SHA256")
            or claim.get("phase") != "infer" or claim.get("controller_pid") != os.getppid()
            or str(claim["controller_pid"]) != os.environ.get("GRAMMAR_CONTROLLER_PID")
            or psutil.Process(os.getppid()).create_time() != claim["controller_created"]
            or os.getpgid(0) != os.getpid() or os.getsid(0) != os.getpid()
            or claim.get("plan_sha256") != common.sha(HERE / "plan.json")
            or claim.get("authorization_sha256") != common.sha(HERE / "infer-authorization.json")):
        raise ValueError("Worker is not the unique child of its measured, source-bound controller.")
    return claim

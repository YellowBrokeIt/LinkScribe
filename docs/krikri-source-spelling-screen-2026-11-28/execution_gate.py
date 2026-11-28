"""Require an independent review and a root receipt for each native phase.

This source-only preparation contains no authorization receipts. The candidate
author cannot approve either native preparation or generation by this helper.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_receipt(value, phase, plan_sha, independent_review_sha):
    if phase not in {"prepare", "infer"} or value.get("phase") != phase:
        raise ValueError("Root receipt names another native phase.")
    if (value.get("plan_sha256") != plan_sha
            or value.get("independent_review_sha256") != independent_review_sha):
        raise ValueError("Root receipt does not bind this exact plan and independent review.")
    if (value.get("root_authorized") is not True
            or value.get("local_model_slot_reserved") is not True
            or value.get("runner_author_self_approval") is not False):
        raise ValueError("Independent root authorization and an exclusive model slot are required.")


def authorize_phase(phase):
    path = HERE / (phase + "-authorization.json")
    if sha(path) != (HERE / (phase + "-authorization.sha256")).read_text().strip():
        raise ValueError("Root authorization receipt changed.")
    value = json.loads(path.read_text())
    review = ROOT / value["independent_review_path"]
    verify_receipt(value, phase, sha(HERE / "plan.json"), sha(review))
    bindings = value["files_sha256"]
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError("Root receipt contains no exact source bindings.")
    for relative, expected in bindings.items():
        if sha(ROOT / relative) != expected:
            raise ValueError("Root-authorized source changed: " + relative)
    required = ["plan.json", "context.py", "execution_gate.py", "source_context.py",
                "run_native.py", "prepare_native.py", "infer_native.py", "resource_monitor.py"]
    if phase == "infer":
        required += ["native-setup-freeze.json", "inference-freeze.json"]
        for name, key in (("native-setup-freeze.json", "native_setup_freeze_sha256"),
                          ("inference-freeze.json", "inference_freeze_sha256")):
            if value.get(key) != sha(HERE / name):
                raise ValueError("Generation receipt does not bind its reviewed native/execution freeze.")
    for name in required:
        if bindings.get(str((HERE / name).relative_to(ROOT))) != sha(HERE / name):
            raise ValueError("Root receipt omits an exact required runtime binding: " + name)
    return value

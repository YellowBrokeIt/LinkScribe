"""Separate root receipts; no self-authorization or generation phase exists."""
import os
from pathlib import Path
import psutil

from context import HERE, ROOT, NATIVE_PLAN, PHASES, read, sha, read_plan, verify_files

RUNTIME_FILES = ("plan.json", "context.py", "execution_gate.py", "run_stage.py", "phase_worker.py",
                 "resource_monitor.py", "process_io.py", "phase_actions.py", "native_actions.py",
                 "native_contract.py", "status_contract.py", "official-source-capsule.json")


def verify_receipt(value, phase, plan_sha, native_plan_sha, review_sha):
    if phase not in PHASES or value.get("phase") != phase:
        raise ValueError("Root receipt names an unsupported or different phase.")
    if (value.get("plan_sha256") != plan_sha or value.get("native_plan_sha256") != native_plan_sha
            or value.get("independent_review_sha256") != review_sha):
        raise ValueError("Root receipt does not bind the exact controller/native plan and independent review.")
    if (value.get("root_authorized") is not True or value.get("runner_author_self_approval") is not False
            or value.get("generation_authorized") is not False):
        raise ValueError("Independent root authorization without generation authority is required.")
    if phase == "native_prepare" and value.get("local_model_slot_reserved") is not True:
        raise ValueError("Root has not reserved the exclusive native model slot.")


def authorize_phase(phase):
    plan, native = read_plan()
    path = HERE / (phase + "-authorization.json")
    if sha(path) != (HERE / (phase + "-authorization.sha256")).read_text().strip():
        raise ValueError("Phase authorization receipt changed.")
    value = read(path)
    review = ROOT / value["independent_review_path"]
    verify_receipt(value, phase, sha(HERE / "plan.json"), sha(NATIVE_PLAN / "plan.json"), sha(review))
    bindings = value.get("files_sha256")
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError("Root receipt omits exact controller source bindings.")
    verify_files(bindings)
    for name in RUNTIME_FILES:
        relative = str((HERE / name).relative_to(ROOT))
        if bindings.get(relative) != sha(HERE / name):
            raise ValueError("Root receipt omits required controller file: " + name)
    elapsed = 0.0
    for predecessor in PHASES[:PHASES.index(phase)]:
        report_path, resources_path = HERE / (predecessor + ".json"), HERE / (predecessor + "-resources.json")
        expected = value.get("completed_phase_bindings", {}).get(predecessor)
        if not isinstance(expected, dict):
            raise ValueError("Root receipt does not bind a completed predecessor: " + predecessor)
        if (expected.get("report_sha256") != sha(report_path)
                or expected.get("resources_sha256") != sha(resources_path)):
            raise ValueError("A completed predecessor changed: " + predecessor)
        report, resources = read(report_path), read(resources_path)
        samples_path = HERE / resources["samples_file"]
        if (report.get("complete") is not True or resources.get("passed") is not True
                or resources.get("phase_report_sha256") != sha(report_path)
                or resources.get("samples_sha256") != sha(samples_path)
                or resources.get("plan_sha256") != sha(HERE / "plan.json")
                or resources.get("owned_processes_stopped") is not True):
            raise ValueError("A predecessor lacks successful observed execution/cleanup.")
        elapsed += resources["elapsed_seconds"]
    return value, plan, native, elapsed


def verify_controller_parent(phase):
    claim_path = HERE / (phase + "-claim.json")
    claim = read(claim_path)
    if (sha(claim_path) != os.environ.get("GRAMMAR_PHASE_CLAIM_SHA256")
            or claim.get("phase") != phase or claim.get("controller_pid") != os.getppid()
            or str(claim["controller_pid"]) != os.environ.get("GRAMMAR_CONTROLLER_PID")
            or psutil.Process(os.getppid()).create_time() != claim["controller_created"]
            or os.getpgid(0) != os.getpid() or os.getsid(0) != os.getpid()):
        raise ValueError("Worker is not the unique child of its observed controller claim.")
    return claim

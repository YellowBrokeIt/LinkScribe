"""Source-only continuation checks: no subprocess, native library or network calls."""
import sys


def deny_execution(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "ctypes.dlopen"}:
        raise RuntimeError("Execution/network/native loading is forbidden in source controls.")
    if event == "import" and args and str(args[0]).split(".")[0] in {
        "torch", "transformers", "tokenizers", "sentencepiece", "gliner", "onnxruntime", "llama_cpp", "numpy"}:
        raise RuntimeError("Model/tokenizer imports are forbidden in source controls.")


sys.addaudithook(deny_execution)

import ast
import copy
from pathlib import Path

from context import HERE, PHASES, NATIVE_PLAN, read, read_plan, save, sha, phase_limits
from continuation_contract import (verify_prior_stage, verify_exact_dependencies,
    require_phase_resources, require_successful_command)
import run_stage


def main():
    result_path = HERE / "source-control-results.json"
    if result_path.exists():
        raise ValueError("Controls already ran; no repeat or overwrite.")
    plan, native = read_plan()
    inputs = read(HERE / "continuation-inputs.json")
    previous = Path(inputs["previous_directory"])
    checks = []

    def check(name, fn, reject=False):
        try:
            value = fn()
            passed, detail = not reject and value is not False, None
        except (ValueError, RuntimeError, FileNotFoundError) as error:
            passed, detail = reject, {"type": type(error).__name__, "message": str(error)}
        checks.append({"id": name, "passed": passed, "expected_rejection": reject, "detail": detail})

    for p in sorted(HERE.glob("*.py")):
        check("parse-" + p.name, lambda p=p: ast.parse(p.read_text()))
    check("no-acquisition-phase", lambda: PHASES == ("build", "native_prepare", "validate"))
    check("exact-retained-stage-dispositions", lambda: verify_prior_stage()["spent_build_seconds"] == inputs["spent_build_seconds"])
    check("exact273-dependencies-and-five-bound-aliases", lambda: len(verify_exact_dependencies()) == 273)
    profile = read(HERE / "independent-prior-stage-review/actual-header-dependencies.json")
    for name, mutate in [
        ("missing-uapi-exception", lambda v: v["unexpected_resolved_headers"].pop()),
        ("duplicate-uapi-exception", lambda v: v["unexpected_resolved_headers"].__setitem__(1, v["unexpected_resolved_headers"][0])),
        ("changed-uapi-hash", lambda v: v["unexpected_resolved_headers"][0].update(sha256="0" * 64)),
        ("changed-alias-link", lambda v: v["unexpected_resolved_headers"][0]["system_include_alias"].update(link_text="other.h")),
        ("changed-alias-location", lambda v: v["unexpected_resolved_headers"][0]["system_include_alias"].update(path="/tmp/not-an-include-alias")),
        ("missing-dependency", lambda v: v["all_dependencies"].pop()),
        ("unobserved-dependency-path", lambda v: v["all_dependencies"][0].update(compiler_path="/usr/lib/unobserved/header.h")),
        ("wrong-original-classification", lambda v: v["all_dependencies"][0].update(allowed_by_original_gate=False)),
        ("changed-depfile-hash", lambda v: v["depfile"].update(sha256="0" * 64)),
    ]:
        altered = copy.deepcopy(profile); mutate(altered)
        check(name, lambda altered=altered: verify_exact_dependencies(altered), reject=True)

    built = read(previous / "build.json")
    receipt = read(Path(built["compile_receipt"]["path"]))
    command = read(NATIVE_PLAN / "build-command.json")
    for name, field, value in [("incomplete-retained-compile", "complete", False),
                               ("failed-retained-compile", "exit_code", 1),
                               ("changed-compile-argv", "argv", []),
                               ("changed-compile-environment", "environment", {})]:
        altered = copy.deepcopy(receipt); altered[field] = value
        check(name, lambda altered=altered: require_successful_command(altered, command["argv"], command["environment_allowlist"], command["cwd"]), reject=True)
    resources = read(previous / "build-resources.json")
    for name, field, value in [("prior-cleanup-absent", "owned_processes_stopped", False),
                               ("prior-memory-stop", "stop_reason", "process_tree_memory_limit"),
                               ("prior-phase-overrun", "elapsed_seconds", 121),
                               ("regraded-prior-build", "passed", True)]:
        altered = copy.deepcopy(resources); altered[field] = value
        check(name, lambda altered=altered: require_phase_resources(built, altered, previous / altered["samples_file"], False), reject=True)

    remaining = phase_limits(native, "build", inputs["carried_active_seconds"], inputs["spent_build_seconds"])
    check("previous-build-time-deducted", lambda: remaining["total_seconds"] == inputs["remaining_original_build_seconds"])
    check("exhausted-build-budget", lambda: phase_limits(native, "build", inputs["carried_active_seconds"], 120), reject=True)
    check("exhausted-aggregate-budget", lambda: phase_limits(native, "native_prepare", 900), reject=True)
    for phase in PHASES:
        argv = sys.argv; sys.argv = [str(HERE / "run_stage.py"), "--phase", phase]
        try:
            try:
                run_stage.main()
            except FileNotFoundError as error:
                passed = error.filename == str(HERE / (phase + "-authorization.json"))
            else:
                passed = False
            checks.append({"id": "actual-entrypoint-missing-root-receipt-" + phase,
                           "passed": passed and not (HERE / (phase + "-claim.json")).exists()})
        finally:
            sys.argv = argv
    for name in ["resource_monitor.py", "process_io.py", "native_actions.py", "native_contract.py", "status_contract.py", "official-source-capsule.json"]:
        check("unchanged-" + name, lambda name=name: sha(HERE / name) == sha(previous / name))
    def function(path, name):
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        return ast.dump(node, include_attributes=False)
    check("unchanged-285-probe-validator", lambda: function(HERE / "phase_actions.py", "validate") == function(previous / "phase_actions.py", "validate"))
    check("original-three-sanity-cases", lambda: len(read(NATIVE_PLAN / "validator-sanity.json")["cases"]) == 3)
    result = {"schema_version": 1, "passed": all(row["passed"] for row in checks), "checks": checks,
        "scope": "Read-only source, retained artifact and pure guard checks, with missing-receipt controller entrypoints only.",
        "subprocess_compiler_validator_native_tokenizer_model_network_calls": 0,
        "actual_phase_receipts_created": 0, "prior_build_regraded": False,
        "plan_sha256": sha(HERE / "plan.json")}
    save(result_path, result)
    print({"passed": result["passed"], "checks": len(checks), "native_calls": 0}, flush=True)
    if not result["passed"]:
        print([row for row in checks if not row["passed"]], flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

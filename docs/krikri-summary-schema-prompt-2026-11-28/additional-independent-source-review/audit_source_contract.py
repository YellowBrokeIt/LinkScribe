"""Independent bounded source audit; no real native/model/tokenizer calls."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "LinkScribe"
CANDIDATE = ROOT / "docs/krikri-summary-schema-prompt-2026-11-28"
BASELINE = ROOT / "docs/krikri-summary-screen-2026-11-28"
PLAN_SHA = "b908a3783109737c8a60080295ec2a8233138be1a0b3dc8eff333c3c987460fb"
FREEZE_SHA = "f43b9969ccc0bea12452e0458816857935c73591668395c397df97ed7bab96b7"
REPLACEMENTS = (
    ('JSON only: {"summary":"concise factual summary","key_points":["point"],"chapter_title":"short topical title"}.',
     "Return only JSON matching the supplied schema."),
    ('JSON only: {"notes":"concise factual notes","chapter_title":"short topical title"}.',
     "Return only JSON with the string fields `notes` and `chapter_title`."),
    ('JSON only: {"summary":"concise factual summary","key_points":["point"]}.',
     "Return only JSON matching the supplied schema."),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def ast_differences(before, after, path="module"):
    assert type(before) is type(after), (path, type(before), type(after))
    if isinstance(before, ast.AST):
        assert before._fields == after._fields
        result = []
        for field in before._fields:
            result.extend(ast_differences(getattr(before, field), getattr(after, field), path + "." + field))
        return result
    if isinstance(before, list):
        assert len(before) == len(after), path
        return [item for index, (left, right) in enumerate(zip(before, after))
                for item in ast_differences(left, right, path + f"[{index}]")]
    return [] if before == after else [{"ast_path": path, "before": before, "after": after}]


def main():
    assert sha(CANDIDATE / "plan.json") == PLAN_SHA
    assert sha(CANDIDATE / "preparation-freeze.json") == FREEZE_SHA
    assert (CANDIDATE / "plan.sha256").read_text().strip() == PLAN_SHA
    assert (CANDIDATE / "preparation-freeze.sha256").read_text().strip() == FREEZE_SHA
    plan = read(CANDIDATE / "plan.json")
    freeze = read(CANDIDATE / "preparation-freeze.json")
    assert freeze["plan_sha256"] == PLAN_SHA
    for binding in (plan["source_sha256"], freeze["files_sha256"]):
        for relative, expected in binding.items():
            assert sha(ROOT / relative) == expected, relative
    manifest = read(BASELINE / "evidence-manifest.json")
    assert sha(BASELINE / "evidence-manifest.json") == plan["prior_rejected_stage"]["manifest_sha256"]
    for item in manifest["files"]:
        path = BASELINE / item["path"]
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], str(path)
    differences = ast_differences(
        ast.parse((BASELINE / "enhancements-context4096.py").read_text()),
        ast.parse((CANDIDATE / "enhancements-context4096.py").read_text()),
    )
    assert len(differences) == 3
    matched = []
    for difference in differences:
        assert difference["ast_path"].endswith(".value")
        before, after = difference["before"], difference["after"]
        assert isinstance(before, str) and isinstance(after, str)
        matches = [index for index, (old, new) in enumerate(REPLACEMENTS)
                   if before.endswith(old) and after == before[:-len(old)] + new]
        assert len(matches) == 1
        matched.extend(matches)
    assert sorted(matched) == list(range(3))
    reused = ["source-cases.json", "review-criteria.json", "enhancements-production.py", "protocol.py",
              "native_preflight.py", "native_session.py", "prepare_native.py", "infer_native.py",
              "resource_monitor.py", "run_native.py", "request_contract.py", "test_protocol.py",
              "native-preflight-layout-only.patch"]
    assert all((CANDIDATE / name).read_bytes() == (BASELINE / name).read_bytes() for name in reused)
    assert (BASELINE / "context.py").read_text().replace(
        "/linkscribe-krikri-runtime/summary-screen", "/linkscribe-krikri-runtime/summary-schema-prompt"
    ) == (CANDIDATE / "context.py").read_text()
    baseline_plan = read(BASELINE / "plan.json")
    for key in ("model", "runtime", "python_runtime", "limits"):
        assert plan[key] == baseline_plan[key], key
    assert (CANDIDATE / "enhancements-production.py").read_bytes() == (ROOT / "enhancements.py").read_bytes()
    cases = read(CANDIDATE / "source-cases.json")
    criteria = read(CANDIDATE / "review-criteria.json")
    requests = read(CANDIDATE / "expected-requests.json")
    old_requests = read(BASELINE / "expected-requests.json")
    case_checks = []
    assert len(cases) == len(criteria) == len(requests) == len(old_requests) == 2
    for case, criterion, request, original in zip(cases, criteria, requests, old_requests):
        assert case["id"] == criterion["id"] == request["id"] == original["id"]
        expected = copy.deepcopy(original)
        text = expected["request"]["messages"][0]["content"]
        old, new = REPLACEMENTS[0]
        assert text.endswith(old)
        expected["request"]["messages"][0]["content"] = text[:-len(old)] + new
        assert request == expected
        excerpt = "\n".join(f"[{s['start']:.1f}s] {s['text']}" for s in case["segments"])
        assert request["request"]["messages"][1]["content"] == excerpt
        assert request["timestamped_excerpt_bytes"] == len(excerpt.encode("utf-8"))
        assert request["timestamped_excerpt_sha256"] == hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        assert case["segments"][0]["start"] == 0.5
        case_checks.append({"id": case["id"], "complete_excerpt_bytes": len(excerpt.encode("utf-8")),
                            "only_request_change": "request.messages[0].content", "unchanged_source_metadata": True})
    test_tree = ast.parse((CANDIDATE / "test_protocol.py").read_text())
    tests = [node.name for node in ast.walk(test_tree)
             if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    assert len(tests) == 9
    assert all(name in (CANDIDATE / "no-model-tests.txt").read_text() for name in tests)
    saved_tests = read(CANDIDATE / "no-model-tests.json")
    assert saved_tests["exit_code"] == 0 and saved_tests["model_calls"] == saved_tests["native_calls"] == 0
    assert sha(CANDIDATE / "no-model-tests.txt") == saved_tests["log_sha256"]
    for name, expected in saved_tests["source_sha256"].items():
        assert sha(CANDIDATE / name) == expected
    subsequent_phase_files = [path.name for path in CANDIDATE.iterdir()
                        if path.name.endswith("-authorization.json") or path.name in ("prepare.json", "english.json", "greek.json")]
    # Invoke only the reviewed synthetic controls; block even accidental native
    # process creation, network access and model/tokenizer imports in the child.
    harness = HERE / "run_nine_controls.py"
    command = [plan["python_runtime"]["executable"], "-B", str(harness)]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=30, check=False)
    with (HERE / "independent-nine-controls.txt").open("xb") as stream:
        stream.write(result.stdout)
    assert result.returncode == 0, result.stdout.decode(errors="replace")
    log = result.stdout.decode()
    assert "Ran 9 tests" in log and "\nOK\n" in log
    for binding in (plan["source_sha256"], freeze["files_sha256"]):
        assert all(sha(ROOT / relative) == expected for relative, expected in binding.items())
    audit = {
        "schema_version": 1, "passed": True, "scope": "Independent source-only review, no execution authorization.",
        "plan_sha256": PLAN_SHA, "preparation_freeze_sha256": FREEZE_SHA,
        "plan_bindings_verified": len(plan["source_sha256"]), "freeze_bindings_verified": len(freeze["files_sha256"]),
        "prior_manifest_files_verified": len(manifest["files"]),
        "whole_ast_differences": differences, "only_three_declared_prompt_endings_differ": True,
        "reused_files_verified": {name: sha(CANDIDATE / name) for name in reused},
        "context_only_private_path_change": True,
        "candidate_adapter_sha256": sha(CANDIDATE / "enhancements-context4096.py"),
        "source_cases_sha256": sha(CANDIDATE / "source-cases.json"),
        "review_criteria_sha256": sha(CANDIDATE / "review-criteria.json"),
        "expected_requests_sha256": sha(CANDIDATE / "expected-requests.json"), "cases": case_checks,
        "model_runtime_python_and_resource_limits_equal_original": True,
        "subsequent_phase_files_seen_without_inspecting_outputs": sorted(subsequent_phase_files),
        "subsequent_phase_scope": "Root independently issued the prepare receipt while this source review was in progress; outputs are outside this audit.",
        "controls": {"count": len(tests), "names": tests, "command": command, "exit_code": result.returncode,
                     "elapsed_seconds": time.monotonic() - start,
                     "log_sha256": sha(HERE / "independent-nine-controls.txt"),
                     "harness_sha256": sha(harness), "network_subprocess_and_model_tokenizer_imports_blocked": True,
                     "synthetic_cleanup_warning_expected": True},
        "frozen_inputs_unchanged_after_review": True,
        "new_model_native_tokenizer_detector_or_network_calls": 0,
        "independent_audit_script_sha256": sha(__file__),
    }
    save_new(HERE / "source-contract-audit.json", audit)
    print(json.dumps({"passed": True, "plan_bindings": len(plan["source_sha256"]),
                      "freeze_bindings": len(freeze["files_sha256"]), "controls": len(tests),
                      "audit_sha256": sha(HERE / "source-contract-audit.json")}))


if __name__ == "__main__":
    main()

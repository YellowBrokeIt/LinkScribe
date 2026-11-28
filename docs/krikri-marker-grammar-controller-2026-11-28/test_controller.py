"""One source-only control run; no compiler, native library, model or network."""
from __future__ import annotations
import sys


def forbid_native(event, args):
    if event.startswith("socket."):
        raise RuntimeError("Network is forbidden in source controls.")
    if event == "subprocess.Popen" and args[0] != sys.executable:
        raise RuntimeError("Only the declared Python interpreter may run harmless control children.")
    if event == "import" and args and str(args[0]).split(".")[0] in {
        "torch", "transformers", "tokenizers", "sentencepiece", "gliner", "onnxruntime", "llama_cpp", "numpy"}:
        raise RuntimeError("Model/tokenizer imports are forbidden in source controls.")


sys.addaudithook(forbid_native)

import ast
import copy
import hashlib
import os
from pathlib import Path

from context import (HERE, OWNED, NATIVE_PLAN, GRAMMAR_PREP, PRIOR, read, save, sha,
                     source_objects, storage_policy, verify_files)
from execution_gate import verify_receipt
from native_contract import NativeContract
from process_io import run_command
from resource_monitor import monitor
from status_contract import classify
import run_stage


def main():
    output = HERE / "source-control-results.json"
    if output.exists():
        raise ValueError("Source controls already retained; do not overwrite.")
    if OWNED.exists():
        raise ValueError("Build root must still be absent during source-only controls.")
    work = HERE / "control-results"; work.mkdir()
    checks = []

    def check(name, operation, reject=False):
        try:
            value = operation()
            passed = not reject and value is not False
            detail = None
        except (ValueError, RuntimeError, FileNotFoundError, TimeoutError) as error:
            passed = reject
            detail = {"type": type(error).__name__, "message": str(error)}
        checks.append({"id": name, "passed": passed, "expected_rejection": reject, "detail": detail})

    for path in HERE.glob("*.py"):
        check("parse-" + path.name, lambda path=path: ast.parse(path.read_text()))
    capsule = read(HERE / "official-source-capsule.json")
    inventory = read(NATIVE_PLAN / "source-acquisition.json")
    check("all-eleven-primary-git-objects", lambda: len(source_objects(capsule, inventory)) == 11)
    for name, mutate in [
        ("changed-body", lambda v: v["files"][0].update(content=v["files"][0]["content"] + "x")),
        ("missing-object", lambda v: v["files"].pop()),
        ("duplicate-object", lambda v: v["files"].append(v["files"][0])),
        ("path-escape", lambda v: v["files"][0].update(path="../outside")),
    ]:
        value = copy.deepcopy(capsule); mutate(value)
        check("capsule-" + name, lambda value=value: source_objects(value, inventory), reject=True)
    for row in read(NATIVE_PLAN / "status-parser-controls.json")["cases"]:
        def run(row=row):
            actual = classify(row["returncode"], row["stdout"].encode(), row["stderr"].encode())
            return actual == row["expected"]
        check("status-" + row["id"], run, reject=row["expected"] == "operational_error")
    receipt = {"phase": "acquire", "plan_sha256": "p", "native_plan_sha256": "n",
               "independent_review_sha256": "r", "root_authorized": True,
               "runner_author_self_approval": False, "generation_authorized": False}
    check("pure-receipt-fields", lambda: verify_receipt(receipt, "acquire", "p", "n", "r"))
    for key, value in [("root_authorized", False), ("runner_author_self_approval", True),
                       ("generation_authorized", True), ("plan_sha256", "changed")]:
        changed = {**receipt, key: value}
        check("receipt-" + key, lambda changed=changed: verify_receipt(changed, "acquire", "p", "n", "r"), reject=True)
    check("generation-phase-unavailable", lambda: verify_receipt({**receipt, "phase": "infer"}, "infer", "p", "n", "r"), reject=True)
    for phase in ("acquire", "build", "native_prepare", "validate"):
        before = sys.argv
        sys.argv = [str(HERE / "run_stage.py"), "--phase", phase]
        try:
            try:
                run_stage.main()
            except FileNotFoundError as error:
                passed = error.filename == str(HERE / (phase + "-authorization.json"))
            else:
                passed = False
            checks.append({"id": "actual-controller-missing-root-receipt-" + phase,
                           "passed": passed and not OWNED.exists() and not (HERE / (phase + "-claim.json")).exists(),
                           "execution_attempted": False})
        finally:
            sys.argv = before

    requests = read(GRAMMAR_PREP / "expected-requests.json")
    queries = read(GRAMMAR_PREP / "proposed-native-grammar-queries.json")["queries"]
    prior_prompts = read(PRIOR / "prepare.json")["prompts"]

    def ready_contract():
        c = NativeContract(requests, queries, requests[0]["request"]["model"])
        c.bind_port(12345)
        c.allow("/api/version", None, 11434); c.observe("version", {"version": "0.40.12"})
        c.allow("/api/show", {"model": c.model}, 11434); c.observe("show", {})
        for expected, previous in zip(requests, prior_prompts):
            c.allow("/api/chat", {**expected["request"], "_debug_render_only": True}, 11434)
            c.observe("render", previous["debug_response"])
            c.allow("/tokenize", {"content": previous["rendered_prompt"],
                    "add_special": previous["tokenize_add_special"], "parse_special": True}, 12345)
            c.observe("tokenize", {"tokens": previous["tokens"]})
        return c

    check("full-six-retained-render-contract", lambda: ready_contract().counts["tokenize"] == 6)
    for name, mutate in [("nonzero-prediction", lambda b: b.update(n_predict=1)),
                         ("nonempty-prompt", lambda b: b.update(prompt=[[1]])),
                         ("weakened-schema", lambda b: b.update(json_schema={"type": "string"})),
                         ("changed-response-field", lambda b: b.update(response_fields=[]))]:
        value = copy.deepcopy(queries[0]["request"]); mutate(value)
        check("native-" + name, lambda value=value: ready_contract().allow("/completion", value, 12345), reject=True)
    check("native-foreign-port", lambda: ready_contract().allow("/completion", queries[0]["request"], 12346), reject=True)
    check("native-generation-chat", lambda: ready_contract().allow("/api/chat", requests[0]["request"], 11434), reject=True)
    check("native-create", lambda: ready_contract().allow("/api/create", {"model": "x"}, 11434), reject=True)
    check("native-generated-content-rejected", lambda: ready_contract().observe("grammar", {"content": "answer"}), reject=True)
    check("native-prompt-evaluation-rejected", lambda: ready_contract().observe("grammar", {"timings": {"prompt_n": 1}}), reject=True)
    c = ready_contract()
    for query in queries:
        c.allow("/completion", query["request"], 12345)
        c.observe("grammar", {"generation_settings/grammar": 'root ::= "ok"'})
    c.allow("/api/chat", {"model": c.model, "messages": [], "keep_alive": 0, "stream": False}, 11434)
    c.observe("unload", {"done_reason": "unload"})
    c.allow("/api/ps", None, 11434); c.observe("residents", {"models": []})
    check("complete-zero-output-call-inventory", c.require_complete)
    check("native-query-repeat-refused", lambda: c.allow("/completion", queries[0]["request"], 12345), reject=True)

    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    check("bounded-subprocess-timeout", lambda: run_command([sys.executable, "-c", "import time; time.sleep(5)"],
          environment, work, work / "timeout", 0.2, 1024), reject=True)
    check("bounded-subprocess-capture", lambda: run_command([sys.executable, "-c", "print('x'*10000)"],
          environment, work, work / "capture", 2, 1024), reject=True)
    toy = work / "toy"; toy.mkdir()
    (toy / "small.txt").write_text("safe")
    check("disk-low-reserve", lambda: storage_policy(toy, reserve_bytes=10**30)["violation"] == "disk_free_reserve")
    check("disk-file-limit", lambda: storage_policy(toy, reserve_bytes=0, maximum_file_bytes=1)["violation"] == "owned_file_size_limit")
    check("disk-tree-limit", lambda: storage_policy(toy, reserve_bytes=0, maximum_tree_bytes=1)["violation"] == "owned_tree_size_limit")
    link = toy / "symlink"; link.symlink_to(toy / "small.txt")
    check("disk-symlink-rejection", lambda: storage_policy(toy, reserve_bytes=0)["violation"] == "nonregular_owned_tree_entry")
    link.unlink()  # Remove only this explicitly synthetic link; no cache or user data.

    observer_cases = [
        ("success", "import time; print('GEMMA_EVENT {\"event\":\"initialized\"}',flush=True); time.sleep(.25)", 5, 256, None, True, None),
        ("time-limit", "import time; time.sleep(5)", .35, 256, None, False, "aggregate_time_limit"),
        ("memory-limit", "import time; value=bytearray(96*1024*1024); time.sleep(5)", 5, 80, None, False, "process_tree_memory_limit"),
        ("orphan", "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)", 5, 256, None, False, "owned_child_survived_worker_exit"),
        ("disk-limit", "from pathlib import Path; import time; Path(" + repr(str(toy / "grown.bin")) + ").write_bytes(b'x'*65536); time.sleep(5)", 5, 256,
         lambda: storage_policy(toy, reserve_bytes=0, maximum_tree_bytes=1024), False, "storage_policy_limit"),
    ]
    original_affinity = os.sched_getaffinity(0)
    try:
        for name, program, seconds, memory, policy, expected_pass, expected_reason in observer_cases:
            prefix = work / ("observer-" + name)
            result = monitor([sys.executable, "-c", program], environment,
                             Path(str(prefix) + "-log.txt"), Path(str(prefix) + "-resources.json"),
                             Path(str(prefix) + "-samples.jsonl"),
                             {"rss_bytes": memory * 1024**2, "total_seconds": seconds,
                              "initialization_seconds": 10, "case_seconds": 10},
                             {"control": name, "harmless_python_program": program}, policy_check=policy)
            checks.append({"id": "observer-" + name,
                "passed": result["passed"] == expected_pass and result["owned_processes_stopped"]
                          and result.get("stop_reason") == expected_reason and result["measurement_complete"],
                "resource_report": record_for_control(Path(str(prefix) + "-resources.json")),
                "observed_stop_reason": result.get("stop_reason")})
    finally:
        os.sched_setaffinity(0, original_affinity)
    if OWNED.exists():
        raise RuntimeError("A source-only control unexpectedly created the real build root.")
    result = {"schema_version": 1, "passed": all(row["passed"] for row in checks), "checks": checks,
              "compiler_native_library_converter_tokenizer_model_calls": 0, "network_calls": 0,
              "harmless_process_controls_only": True, "actual_root_receipts_created": 0,
              "source_materialization_into_build_root": False,
              "synthetic_symlink_cleanup_only": True,
              "native_probe_matrix_not_executed": True}
    save(output, result)
    print({"passed": result["passed"], "checks": len(checks), "native_calls": 0}, flush=True)
    if not result["passed"]:
        print([row for row in checks if not row["passed"]], flush=True)
    return int(not result["passed"])


def record_for_control(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Evaluate one frozen corpus with the already frozen Gemma text adapter.

Every actual production request receives a native render/token preflight first.
This observer never rewrites, repairs, truncates or retries its model input/output.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = ROOT / "docs/gemma4-screen-2026-11-28"
sys.path.insert(0, str(ORIGINAL))
import experiment as common


def read_plan():
    if common.sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The expanded-screen plan changed.")
    plan = json.loads((HERE / "plan.json").read_text())
    for name, expected in plan["source_sha256"].items():
        if common.sha(ROOT / name) != expected:
            raise ValueError("Frozen expanded-screen source changed: " + name)
    original = common.read_plan()
    if common.sha(ORIGINAL / "plan.json") != plan["candidate"]["original_plan_sha256"]:
        raise ValueError("Original candidate plan changed.")
    if common.sha(ORIGINAL / "inference-freeze.json") != plan["candidate"]["original_inference_freeze_sha256"]:
        raise ValueError("Original native model/template/tokenization freeze changed.")
    return plan, original


def expected_fragments(module, case):
    output = []
    for index, segment in enumerate(case["segments"]):
        fragments = list(module._translation_fragments(segment["text"], module.MAX_JSON_TRANSLATION_INPUT_BYTES))
        if "".join(fragments) != segment["text"]:
            raise ValueError("Fragmentation dropped or changed original source characters.")
        output.extend({"source_segment_index": index, "text": text} for text in fragments if text.strip())
    return output


def source_fragments(body):
    if (body.get("think") is not False or body.get("stream") is not False
            or body.get("options") != {"temperature": 0, "num_ctx": 4096, "num_predict": 2048, "num_thread": 4}):
        raise ValueError("Actual request no longer has the frozen candidate profile.")
    messages = body.get("messages", [])
    if len(messages) != 2 or [x["role"] for x in messages] != ["system", "user"]:
        raise ValueError("Unexpected actual translation message layout.")
    marker = "JSON input: "
    if marker not in messages[1]["content"]:
        raise ValueError("Actual request has no complete JSON source.")
    source = json.loads(messages[1]["content"].split(marker, 1)[1])
    if (not isinstance(source, list) or not source
            or any(set(row) != {"id", "text"} or row["id"] != i or not isinstance(row["text"], str)
                   for i, row in enumerate(source))):
        raise ValueError("Unexpected actual source entries.")
    schema = {"type": "object", "properties": {"translations": {"type": "array", "items": {"type": "string"},
              "minItems": len(source), "maxItems": len(source)}}, "required": ["translations"], "additionalProperties": False}
    if body.get("format") != schema:
        raise ValueError("The production output schema changed.")
    return [row["text"] for row in source]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    plan, candidate = read_plan()
    output = HERE / "execution.json"
    if output.exists() or any((HERE / (name + ".json")).exists() for name in plan["evaluation"]["case_ids"]):
        raise ValueError("Refusing a repeated expanded screen.")
    common.verify_blob(runtime, candidate)
    old_setup = json.loads((ORIGINAL / "prepare.json").read_text())
    if common.cached_identity(runtime, candidate) != old_setup["cache"]:
        raise ValueError("The native model/config/template package differs from the six-case candidate.")
    corpus_path = ROOT / plan["evaluation"]["corpus"]
    corpus = json.loads(corpus_path.read_text())
    if [x["id"] for x in corpus["cases"]] != plan["evaluation"]["case_ids"]:
        raise ValueError("The expanded corpus selection changed.")
    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama",
                       "LINKSCRIBE_TRANSLATION_MODEL": candidate["model"]["local_name"],
                       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    spec = importlib.util.spec_from_file_location("enhancements", ORIGINAL / "enhancements-context4096.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["enhancements"] = module
    spec.loader.exec_module(module)
    import evaluate_translation_quality as qa
    original_source_identity = qa.source_identity
    def identity(path):
        value = original_source_identity(path)
        value["executed_enhancements_snapshot"] = {"path": str(ORIGINAL / "enhancements-context4096.py"),
                                                   "sha256": common.sha(ORIGINAL / "enhancements-context4096.py"),
                                                   "unchanged_from_six_case_screen": True}
        value["expanded_plan_sha256"] = common.sha(HERE / "plan.json")
        return value
    qa.source_identity = identity
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "plan_sha256": common.sha(HERE / "plan.json"), "semantic_quality": "unreviewed",
              "cases": [], "generation_calls": 0, "unused_v3_opened_or_run": False}
    common.save(output, report)
    process = None
    original_transport = module.local_ollama_json
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Supervisor stopped expanded screen.")))
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        descriptor = os.open(runtime / (HERE.name + "-daemon-private.log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as log:
            process = subprocess.Popen([str(Path(candidate["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != candidate["runtime"]["version"]:
                raise ValueError("Executing native runtime changed.")
            report["installed_model"] = next((x for x in common.api("/api/tags").get("models", [])
                                                if x.get("name") == candidate["model"]["local_name"]), None)
            if (not report["installed_model"]
                    or report["installed_model"].get("digest") != candidate["model"]["cache_manifest_sha256"]):
                raise ValueError("Actual API model identity differs from the frozen native import.")
            for case in corpus["cases"]:
                case_id = case["id"]
                common.event("case_start", id=case_id)
                fragments = expected_fragments(module, case)
                consumed = 0
                preflight_path = HERE / (case_id + "-preflight.json")
                preflight = {"id": case_id, "plan_sha256": common.sha(HERE / "plan.json"), "complete": False,
                             "expected_fragments": fragments, "original_segment_count": len(case["segments"]), "requests": []}
                common.save(preflight_path, preflight)
                def observed_transport(path, payload=None, timeout=1.5):
                    nonlocal consumed
                    if path != "/api/chat" or module.is_ollama_control_request(payload):
                        return original_transport(path, payload, timeout=timeout)
                    if payload.get("model") != candidate["model"]["local_name"] or timeout != 240:
                        raise ValueError("Model or per-request timeout differs from frozen profile.")
                    texts = source_fragments(payload)
                    expected = [x["text"] for x in fragments[consumed:consumed + len(texts)]]
                    if texts != expected:
                        raise ValueError("Actual request cropped, reordered or changed source fragments.")
                    entry = {"index": len(preflight["requests"]), "request": copy.deepcopy(payload),
                             "source_segment_indices": [x["source_segment_index"] for x in fragments[consumed:consumed + len(texts)]],
                             "generation_started": False}
                    preflight["requests"].append(entry)
                    common.save(preflight_path, preflight)
                    rendered = common.native_prompt(payload)
                    debug = common.api("/api/chat", {**payload, "_debug_render_only": True}, timeout=180)
                    entry["render_only_response"] = debug
                    if (debug.get("_debug_info", {}).get("rendered_template") != rendered
                            or debug.get("eval_count", 0) or debug.get("message", {}).get("content")):
                        raise ValueError("Native full-source rendering changed or generated an unexpected answer.")
                    runner = common.runner_identity(process)
                    command = runner["command"]
                    if Path(command[command.index("--model") + 1]) != common.model_blob(runtime, candidate):
                        raise ValueError("The native runner is not loading the pinned original text blob.")
                    if command[command.index("-t") + 1] != "4":
                        raise ValueError("The native runner changed the frozen four-thread setting.")
                    token_response = common.api("/tokenize", {"content": rendered, "add_special": False, "parse_special": True}, port=runner["port"])
                    tokens = token_response.get("tokens")
                    if (not isinstance(tokens, list) or not tokens or any(type(t) is not int for t in tokens)
                            or tokens[0] != 2 or tokens.count(2) != 1 or len(tokens) + 2048 + 1 > 4096):
                        raise ValueError("The entire actual request plus full maximum response cannot fit the fixed context.")
                    entry.update({"rendered_prompt": rendered, "native_tokens": tokens, "prompt_tokens": len(tokens),
                                  "max_output_tokens": 2048, "end_reserve_tokens": 1, "context_tokens": 4096,
                                  "complete_source_and_budget_fit": True, "runner": runner,
                                  "generation_started": True})
                    common.save(preflight_path, preflight)
                    consumed += len(texts)
                    return original_transport(path, payload, timeout=timeout)
                module.local_ollama_json = observed_transport
                case_path = HERE / (case_id + ".json")
                try:
                    value, status = qa.evaluate(corpus_path, case_path, case_ids=[case_id])
                finally:
                    module.local_ollama_json = original_transport
                result = value["cases"][0] if value.get("cases") else {}
                calls = [x for x in result.get("requests", []) if x["kind"] == "inference"]
                controls = [x for x in result.get("requests", []) if x["kind"] == "control"]
                checks = {"all_original_source_fragments_consumed": consumed == len(fragments),
                          "all_actual_requests_preflighted": len(calls) == len(preflight["requests"]) and bool(calls),
                          "structure_and_metadata_preserved": status == 0 and value.get("complete") is True and all(result.get("structural_checks", {}).values()),
                          "exact_request_identity": bool(calls), "normal_completion": bool(calls), "empty_reasoning": bool(calls),
                          "output_below_cap": bool(calls), "actual_prompt_count_matches_native_preflight": bool(calls),
                          "unload_acknowledged": bool(controls), "resident_models_empty": common.api("/api/ps").get("models") == []}
                for index, call in enumerate(calls):
                    response = json.loads(call.get("response_json", "{}"))
                    message = response.get("message", {})
                    prompt = preflight["requests"][index] if index < len(preflight["requests"]) else {}
                    checks["exact_request_identity"] &= call["request"] == prompt.get("request") and call["timeout_seconds"] == 240
                    checks["normal_completion"] &= response.get("done") is True and response.get("done_reason") == "stop" and bool(message.get("content"))
                    checks["empty_reasoning"] &= isinstance(message.get("thinking", ""), str) and not message.get("thinking", "").strip()
                    checks["output_below_cap"] &= type(response.get("eval_count")) is int and 0 < response["eval_count"] < 2048
                    checks["actual_prompt_count_matches_native_preflight"] &= response.get("prompt_eval_count") == prompt.get("prompt_tokens")
                for control in controls:
                    response = json.loads(control.get("response_json", "{}"))
                    checks["unload_acknowledged"] &= response.get("done") is True and response.get("done_reason") == "unload"
                preflight["complete"] = all(checks.values())
                preflight["consumed_fragment_count"] = consumed
                common.save(preflight_path, preflight)
                report["generation_calls"] += len(calls)
                report["cases"].append({"id": case_id, "report": case_path.name, "report_sha256": common.sha(case_path),
                                         "preflight_report": preflight_path.name, "preflight_sha256": common.sha(preflight_path),
                                         "checks": checks, "semantic_quality": "unreviewed"})
                common.save(output, report)
                common.event("case_complete" if all(checks.values()) else "case_failed", id=case_id, report=str(case_path), sha256=common.sha(case_path))
                if not all(checks.values()):
                    raise ValueError("First protocol/execution/resource failure; no retry or crop is allowed.")
            report["complete"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        module.local_ollama_json = original_transport
        if process is not None:
            common.stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        common.save(output, report)
    common.event("phase_complete", phase=plan["evaluation"]["stage"], complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""One frozen native-thinking telescope attempt; never repair or retry."""
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
PREVIOUS = ROOT / "docs/gemma4-exposed-v2-2026-11-28"
sys.path.insert(0, str(ORIGINAL))
import experiment as common


def read_freeze():
    frozen_path = HERE / "inference-freeze.json"
    if common.sha(frozen_path) != (HERE / "inference-freeze.sha256").read_text().strip():
        raise ValueError("The pre-output execution freeze changed.")
    freeze = json.loads(frozen_path.read_text())
    for name, expected in freeze["source_sha256"].items():
        if common.sha(ROOT / name) != expected:
            raise ValueError("Frozen executed input changed: " + name)
    # The historical plan identifies the same model/runtime. Its old live-
    # checkout check is not invoked: this experiment executes a pinned archive,
    # while root's current production checkout is recorded separately.
    candidate = json.loads((ORIGINAL / "plan.json").read_text())
    for name, expected in candidate["runtime"]["files_sha256"].items():
        if common.sha(Path(candidate["runtime"]["directory"]) / name) != expected:
            raise ValueError("Pinned runtime binary changed: " + name)
    return freeze, candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    freeze, candidate = read_freeze()
    case_id = freeze["case_id"]
    output = HERE / "execution.json"
    case_path = HERE / (case_id + ".json")
    preflight_path = HERE / "native-preflight.json"
    if any(p.exists() for p in (output, case_path, preflight_path)):
        raise ValueError("Refusing to overwrite or repeat the single attempt.")
    corpus_path = HERE / "one-case-corpus.json"
    corpus = json.loads(corpus_path.read_text())
    case = json.loads((HERE / "telescope-source-and-criteria.json").read_text())
    if corpus["cases"] != [case] or case["id"] != case_id:
        raise ValueError("The approved one-case source or criteria changed.")
    original_case = json.loads((PREVIOUS / "exposed-v2-corpus.json").read_text())["cases"][0]
    if case != original_case:
        raise ValueError("The original exposed telescope source/criteria changed.")
    expected = json.loads((HERE / "proposed-request.json").read_text())
    baseline = json.loads((PREVIOUS / (case_id + "-preflight.json")).read_text())["requests"][0]
    permitted = copy.deepcopy(baseline["request"])
    permitted["think"] = True
    if expected != permitted:
        raise ValueError("A request field other than the thinking switch changed.")
    source_rows = json.loads(expected["messages"][1]["content"].split("JSON input: ", 1)[1])
    if source_rows != [{"id": i, "text": s["text"]} for i, s in enumerate(case["segments"])]:
        raise ValueError("The complete original source no longer matches the actual request.")
    rendered = json.loads((HERE / "publisher-render-check.json").read_text())["thinking_render"]
    if rendered != baseline["rendered_prompt"].replace("<|turn>system\n", "<|turn>system\n<|think|>\n", 1):
        raise ValueError("The proposed native prompt changed beyond the thinking control.")

    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama",
                       "LINKSCRIBE_TRANSLATION_MODEL": candidate["model"]["local_name"],
                       "LINKSCRIBE_OLLAMA_THREADS": "4",
                       "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    adapter_path = HERE / "enhancements-thinking.py"
    spec = importlib.util.spec_from_file_location("enhancements", adapter_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["enhancements"] = module
    spec.loader.exec_module(module)
    import evaluate_translation_quality as qa
    original_identity = qa.source_identity

    def identity(path):
        value = original_identity(path)
        value["checkout_scope"] = "Observed current checkout only; live enhancements.py is not the executed adapter."
        value["executed_enhancements_snapshot"] = {"path": str(adapter_path), "sha256": common.sha(adapter_path),
                                                   "base_sha256": freeze["base_adapter_sha256"],
                                                   "only_change_from_archived_base": "body[think] False to True"}
        value["inference_freeze_sha256"] = common.sha(HERE / "inference-freeze.json")
        return value

    qa.source_identity = identity
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "complete": False, "semantic_quality": "unreviewed", "case_id": case_id,
              "proposal_sha256": freeze["proposal_sha256"],
              "inference_freeze_sha256": common.sha(HERE / "inference-freeze.json"),
              "generation_calls": 0, "unused_v3_opened_or_run": False}
    preflight = {"case_id": case_id, "complete": False, "generation_started": False,
                 "inference_freeze_sha256": common.sha(HERE / "inference-freeze.json"),
                 "original_source_segments": copy.deepcopy(case["segments"])}
    common.save(output, report)
    common.save(preflight_path, preflight)
    process = None
    original_transport = module.local_ollama_json
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Supervisor stopped the single attempt.")))
    try:
        common.verify_blob(runtime, candidate)
        report["cache"] = common.cached_identity(runtime, candidate)
        if report["cache"] != json.loads((ORIGINAL / "prepare.json").read_text())["cache"]:
            raise ValueError("The imported native model/config/parameters changed.")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        descriptor = os.open(runtime / (HERE.name + "-daemon-private.log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as log:
            process = subprocess.Popen([str(Path(candidate["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != candidate["runtime"]["version"]:
                raise ValueError("The executing runtime version changed.")
            report["installed_model"] = next((m for m in common.api("/api/tags").get("models", [])
                                                if m.get("name") == candidate["model"]["local_name"]), None)
            if not report["installed_model"] or report["installed_model"].get("digest") != candidate["model"]["cache_manifest_sha256"]:
                raise ValueError("Actual API model digest changed.")
            common.save(output, report)
            common.event("case_start", id=case_id)

            def observed_transport(path, payload=None, timeout=1.5):
                if path != "/api/chat" or module.is_ollama_control_request(payload):
                    return original_transport(path, payload, timeout=timeout)
                if payload != expected or timeout != 240:
                    raise ValueError("The actual request differs beyond the approved thinking switch.")
                if preflight["generation_started"]:
                    raise ValueError("A second generation attempt is forbidden.")
                preflight["request"] = copy.deepcopy(payload)
                common.save(preflight_path, preflight)
                debug = common.api("/api/chat", {**payload, "_debug_render_only": True}, timeout=180)
                preflight["render_only_response"] = debug
                if (debug.get("_debug_info", {}).get("rendered_template") != rendered
                        or debug.get("eval_count", 0) or debug.get("message", {}).get("content")
                        or debug.get("message", {}).get("thinking")):
                    raise ValueError("Native rendering differs or render-only generated output.")
                runner = common.runner_identity(process)
                command = runner["command"]
                if (Path(command[command.index("--model") + 1]) != common.model_blob(runtime, candidate)
                        or command[command.index("-t") + 1] != "4"):
                    raise ValueError("Native model path or thread setting changed.")
                tokens = common.api("/tokenize", {"content": rendered, "add_special": False, "parse_special": True},
                                    port=runner["port"]).get("tokens")
                if (not isinstance(tokens, list) or not tokens or any(type(t) is not int for t in tokens)
                        or tokens[0] != 2 or tokens.count(2) != 1 or len(tokens) + 2048 + 1 > 4096):
                    raise ValueError("Full prompt plus the unchanged shared output budget cannot fit.")
                preflight.update({"rendered_prompt": rendered, "native_tokens": tokens, "prompt_tokens": len(tokens),
                                  "shared_max_output_tokens": 2048, "end_reserve_tokens": 1, "context_tokens": 4096,
                                  "full_source_and_budget_fit": True, "runner": runner, "complete": True,
                                  "generation_started": True})
                common.save(preflight_path, preflight)
                common.event("generation_start", id=case_id, prompt_tokens=len(tokens), shared_output_cap=2048)
                return original_transport(path, payload, timeout=timeout)

            module.local_ollama_json = observed_transport
            try:
                value, status = qa.evaluate(corpus_path, case_path, case_ids=[case_id])
            finally:
                module.local_ollama_json = original_transport
            result = value["cases"][0] if value.get("cases") else {}
            calls = [c for c in result.get("requests", []) if c["kind"] == "inference"]
            controls = [c for c in result.get("requests", []) if c["kind"] == "control"]
            response = json.loads(calls[0].get("response_json", "{}")) if len(calls) == 1 else {}
            message = response.get("message", {})
            thoughts = message.get("thinking", "")
            checks = {"exactly_one_generation_request": len(calls) == 1 and preflight["generation_started"],
                      "exact_request_identity": len(calls) == 1 and calls[0]["request"] == expected and calls[0]["timeout_seconds"] == 240,
                      "structure_and_metadata_preserved": status == 0 and value.get("complete") is True and all(result.get("structural_checks", {}).values()),
                      "normal_completion": response.get("done") is True and response.get("done_reason") == "stop" and bool(message.get("content")),
                      "thinking_field_is_string": isinstance(thoughts, str),
                      "output_below_shared_cap": type(response.get("eval_count")) is int and 0 < response["eval_count"] < 2048,
                      "actual_prompt_count_matches_native_preflight": response.get("prompt_eval_count") == preflight.get("prompt_tokens"),
                      "unload_acknowledged": bool(controls),
                      "resident_models_empty": common.api("/api/ps").get("models") == []}
            for control in controls:
                reply = json.loads(control.get("response_json", "{}"))
                checks["unload_acknowledged"] &= reply.get("done") is True and reply.get("done_reason") == "unload"
            report.update({"generation_calls": len(calls), "control_calls": len(controls), "checks": checks,
                           "thinking_observed": isinstance(thoughts, str) and bool(thoughts.strip()),
                           "thinking_characters": len(thoughts) if isinstance(thoughts, str) else None,
                           "final_content": message.get("content"), "done_reason": response.get("done_reason"),
                           "prompt_eval_count": response.get("prompt_eval_count"), "eval_count": response.get("eval_count"),
                           "report": case_path.name, "report_sha256": common.sha(case_path),
                           "preflight_report": preflight_path.name, "preflight_sha256": common.sha(preflight_path)})
            common.save(output, report)
            common.event("case_complete" if all(checks.values()) else "case_failed", id=case_id,
                         report=str(case_path), sha256=common.sha(case_path))
            if not all(checks.values()):
                raise ValueError("The single attempt failed execution/protocol checks; no retry or repair is allowed.")
            report["complete"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        module.local_ollama_json = original_transport
        if process is not None:
            common.stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in freeze["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        common.save(output, report)
    common.event("phase_complete", phase="one_telescope_thinking_attempt", complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

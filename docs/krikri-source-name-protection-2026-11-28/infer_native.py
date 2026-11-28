"""Run the fixed six source-protected cases once through the archived app.

Actual response JSON is retained by the existing observer before app parsing or
script rejection. Native preflight counts must match each completed response.
"""
from __future__ import annotations
from datetime import datetime, timezone
import importlib.util
import copy
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from context import HERE, ROOT, PRIVATE, common, read_plan, cache_identity, native_preflight, storage_reserve, stop_daemon
from protection import build_protection, restore_segments, strict_response_strings


def verify_freeze():
    path = HERE / "inference-freeze.json"
    if common.sha(path) != (HERE / "inference-freeze.sha256").read_text().strip():
        raise ValueError("Pre-output inference freeze changed.")
    freeze = json.loads(path.read_text())
    for rel, expected in freeze["files_sha256"].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError("Frozen inference file changed: " + rel)
    if freeze.get("independent_native_contract_approved") is not True:
        raise ValueError("Independent before-output native contract review is absent.")


def run_cases(runtime, plan, process, report, output):
    setup = json.loads((HERE / "prepare.json").read_text())
    setup_resources = json.loads((HERE / "prepare-resources.json").read_text())
    if not setup["complete"] or not setup_resources["passed"]:
        raise ValueError("Measured native preparation did not pass.")
    if cache_identity(runtime, plan) != setup["cache"]:
        raise ValueError("Actual native import differs from the frozen prepared package.")
    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama", "LINKSCRIBE_TRANSLATION_MODEL": plan["model"]["local_name"],
                       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    spec = importlib.util.spec_from_file_location("enhancements", HERE / "enhancements-context4096.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["enhancements"] = module
    spec.loader.exec_module(module)
    import evaluate_translation_quality as qa
    source_identity = qa.source_identity

    def identity(path):
        value = source_identity(path)
        value["checkout_identity_scope"] = "Live checkout only; actual executed app adapter is the immutable snapshot below."
        value["executed_enhancements_snapshot"] = {"path": str(HERE / "enhancements-context4096.py"),
                                                  "sha256": common.sha(HERE / "enhancements-context4096.py"),
                                                  "published_source_sha256": plan["published_production_sha256"],
                                                  "only_code_changes": "num_ctx8192 to4096 plus generic marker instruction; source-only protection wrapper is separately bound",
                                                  "current_foreign_script_guard_preserved": True}
        return value

    qa.source_identity = identity
    cases = json.loads((HERE / "development-cases.json").read_text())["cases"]
    expected = json.loads((HERE / "expected-requests.json").read_text())
    protected_cases = json.loads((HERE / "protected-source-cases.json").read_text())["cases"]
    protections = json.loads((HERE / "protection-inputs.json").read_text())["cases"]
    report["cases"] = []
    original_transport = module.local_ollama_json
    native_translate = module.translate_segments
    for case, protected_case, protection, request, prepared in zip(cases, protected_cases, protections, expected, setup["prompts"]):
        case_started = time.monotonic()
        report["free_disk_before_case_bytes"] = storage_reserve()
        case_id = case["id"]
        if case_id != request["id"] or case_id != prepared["id"] or case_id != protected_case["id"] or case_id != protection["id"]:
            raise ValueError("Frozen case/request/native prompt order changed.")
        path = HERE / (case_id + ".json")
        preflight_path = HERE / (case_id + "-preflight.json")
        if path.exists() or preflight_path.exists():
            raise ValueError("Refusing to repeat an original case.")
        preflight = native_preflight(request["request"], protected_case, process, plan, setup["header"])
        for key in ("request", "rendered_prompt", "tokens", "prompt_tokens", "layout", "tokenize_add_special"):
            if preflight[key] != prepared[key]:
                raise ValueError("Actual source/native token contract changed from preparation: " + key)
        common.save(preflight_path, preflight)
        # On the first case this event follows verified actual native loading,
        # keeping the monitor's separate 180-second initialization gate active.
        common.event("case_start", id=case_id, prompt_tokens=preflight["prompt_tokens"])
        actual_call_count = 0
        protected_path = HERE / (case_id + "-protection.json")
        if protected_path.exists():
            raise ValueError("Refusing to repeat a protected translation case.")
        protection_report = {"id": case_id, "complete": False, "plan_sha256": common.sha(HERE / "plan.json"),
                             "source_protection_input_sha256": common.sha(HERE / "protection-inputs.json"),
                             "source_segments": copy.deepcopy(case["segments"]),
                             "bundle": copy.deepcopy(protection["bundle"]), "model_response_json": None,
                             "exact_source_only_restoration": False, "post_restoration_guard_accepted": False}
        common.save(protected_path, protection_report)

        def checked_transport(endpoint, payload=None, timeout=1.5):
            nonlocal actual_call_count
            if endpoint == "/api/chat" and not module.is_ollama_control_request(payload):
                actual_call_count += 1
                if actual_call_count != 1 or payload != request["request"] or timeout != 240:
                    raise ValueError("Actual production inference request differs from its exact frozen single request.")
                report["generation_calls"] += 1
                common.save(output, report)
            response = original_transport(endpoint, payload, timeout=timeout)
            if endpoint == "/api/chat" and not module.is_ollama_control_request(payload):
                # Retain returned JSON before any application/marker/script rejection.
                protection_report["model_response_json"] = json.dumps(response, ensure_ascii=True, allow_nan=True)
                common.save(protected_path, protection_report)
            return response

        def protected_translate(segments, target, source_language=None):
            try:
                if segments != case["segments"] or target != case["target_language"] or source_language != case["source_language"]:
                    raise ValueError("The actual application source differs from its frozen original case.")
                bundle = build_protection(segments, protection["raw_entities"], source_language)
                if bundle != protection["bundle"] or bundle["masked_segments"] != protected_case["segments"]:
                    raise ValueError("Actual source-derived protection differs from the frozen input representation.")
                masked_source = copy.deepcopy(bundle["masked_segments"])
                result = native_translate(masked_source, target, source_language=source_language)
                protection_report["masked_app_result"] = copy.deepcopy(result)
                common.save(protected_path, protection_report)
                if masked_source != bundle["masked_segments"] or segments != bundle["source_segments"]:
                    raise ValueError("Native translation mutated original or masked source metadata.")
                raw = json.loads(protection_report["model_response_json"])
                strings = strict_response_strings(raw["message"]["content"], len(segments))
                protection_report["raw_masked_translation_strings"] = strings
                protection_report["strict_raw_schema_accepted"] = True
                if [item["text"] for item in result] != [text.strip() for text in strings]:
                    raise ValueError("App text is not the raw translations with only baseline edge trimming.")
                restored, audit = restore_segments(bundle, result)
                protection_report["restoration_audit"] = audit
                protection_report["restored_before_guard"] = copy.deepcopy(restored)
                protection_report["exact_source_only_restoration"] = True
                common.save(protected_path, protection_report)
                # The frozen module has the exact current production guard.
                checked = module._translation_result(segments, restored, source_language, target)
                protection_report["post_restoration_guard_accepted"] = True
                protection_report["restored_app_result"] = copy.deepcopy(checked)
                protection_report["complete"] = True
                common.save(protected_path, protection_report)
                return checked
            except BaseException as error:
                protection_report["error"] = {"type": type(error).__name__, "message": str(error)}
                common.save(protected_path, protection_report)
                raise

        module.translate_segments = protected_translate
        module.local_ollama_json = checked_transport
        try:
            value, status = qa.evaluate(HERE / "development-cases.json", path, case_ids=[case_id], splits=["development"])
        finally:
            module.local_ollama_json = original_transport
            module.translate_segments = native_translate
        actual = value["cases"][0] if value.get("cases") else {}
        records = actual.get("requests", [])
        calls = [r for r in records if r["kind"] == "inference"]
        controls = [r for r in records if r["kind"] == "control"]
        checks = {"one_exact_declared_request": len(calls) == 1 and calls[0]["request"] == request["request"],
                  "request_timeout_240s": len(calls) == 1 and calls[0]["timeout_seconds"] == 240,
                  "structure_execution_and_guard_accepted": status == 0 and value.get("complete") is True,
                  "marker_restoration_and_post_guard_accepted": protection_report["complete"] is True,
                  "normal_completion": bool(calls), "empty_reasoning": bool(calls),
                  "nonempty_final_content": bool(calls), "output_below_cap": bool(calls),
                  "actual_prompt_count_matches_full_native_preflight": bool(calls),
                  "unload_acknowledged": bool(controls), "resident_models_empty": common.api("/api/ps").get("models") == [],
                  "case_below_600s": time.monotonic() - case_started <= 600}
        metrics = []
        for call in calls:
            response = json.loads(call.get("response_json", "{}"))
            message = response.get("message", {})
            checks["normal_completion"] &= response.get("done") is True and response.get("done_reason") == "stop"
            checks["empty_reasoning"] &= isinstance(message.get("thinking", ""), str) and not message.get("thinking", "").strip()
            checks["nonempty_final_content"] &= isinstance(message.get("content"), str) and bool(message.get("content", "").strip())
            checks["output_below_cap"] &= type(response.get("eval_count")) is int and 0 < response["eval_count"] < 2048
            checks["actual_prompt_count_matches_full_native_preflight"] &= response.get("prompt_eval_count") == preflight["prompt_tokens"]
            metrics.append({"done": response.get("done"), "done_reason": response.get("done_reason"),
                            "prompt_eval_count": response.get("prompt_eval_count"), "eval_count": response.get("eval_count"),
                            "reasoning_characters": len(message.get("thinking", "")),
                            "raw_evidence_available": call.get("raw_evidence_available"), "elapsed_seconds": call.get("elapsed_seconds")})
        for control in controls:
            response = json.loads(control.get("response_json", "{}"))
            checks["unload_acknowledged"] &= response.get("done") is True and response.get("done_reason") == "unload"
        entry = {"id": case_id, "report": path.name, "sha256": common.sha(path),
                 "preflight_report": preflight_path.name, "preflight_sha256": common.sha(preflight_path),
                 "protection_report": protected_path.name, "protection_report_sha256": common.sha(protected_path),
                 "checks": checks, "elapsed_seconds": round(time.monotonic() - case_started, 3),
                 "metrics": metrics, "semantic_quality": "unreviewed", "automatic_status": actual.get("automatic_status")}
        report["cases"].append(entry)
        common.save(output, report)
        common.event("case_complete" if all(checks.values()) else "case_failed", id=case_id, report=str(path), sha256=common.sha(path))
        if not all(checks.values()):
            raise ValueError("First execution/protocol/structure/script-guard/time failure; remaining fixed cases stop without retry.")
    report["complete"] = len(report["cases"]) == 6 and report["generation_calls"] == 6


def main():
    verify_freeze()
    plan = read_plan()
    runtime = Path(plan["storage"]["owned_runtime_directory"])
    output = HERE / "execution.json"
    if output.exists():
        raise ValueError("Refusing to repeat the frozen development screen.")
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "generation_calls": 0, "plan_sha256": common.sha(HERE / "plan.json"),
              "inference_freeze_sha256": common.sha(HERE / "inference-freeze.json"),
              "semantic_quality": "unreviewed", "unused_validation_opened": False}
    common.save(output, report)
    process = None
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("External supervisor stopped inference.")))
    try:
        report["free_disk_before_bytes"] = storage_reserve()
        common.verify_blob(runtime, plan)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        PRIVATE.mkdir(parents=True, exist_ok=True)
        fd = os.open(PRIVATE / "infer-daemon-private.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=False)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Actual runtime differs from the pinned release.")
            run_cases(runtime, plan, process, report, output)
    except BaseException as error:
        report["complete"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if process is not None:
            report["owned_daemon_stopped"] = stop_daemon(process) and process.poll() is not None
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        common.save(output, report)
    common.event("phase_complete", phase="infer", complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

"""Run exactly the frozen six original cases once through the archived app.

Actual response JSON is retained by the existing observer before app parsing or
script rejection. Native preflight counts must match each completed response.
"""
from __future__ import annotations
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from staging import HERE, ROOT, common, read_plan
from native_verify import cache_identity, native_preflight


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
                                                  "only_code_change": "num_ctx8192 to4096",
                                                  "current_foreign_script_guard_preserved": True}
        return value

    qa.source_identity = identity
    cases = json.loads((HERE / "development-cases.json").read_text())["cases"]
    expected = json.loads((HERE / "expected-requests.json").read_text())
    report["cases"] = []
    original_transport = module.local_ollama_json
    for case, request, prepared in zip(cases, expected, setup["prompts"]):
        case_started = time.monotonic()
        case_id = case["id"]
        if case_id != request["id"] or case_id != prepared["id"]:
            raise ValueError("Frozen case/request/native prompt order changed.")
        path = HERE / (case_id + ".json")
        preflight_path = HERE / (case_id + "-preflight.json")
        if path.exists() or preflight_path.exists():
            raise ValueError("Refusing to repeat an original case.")
        preflight = native_preflight(request["request"], case, process, plan, setup["header"])
        for key in ("request", "rendered_prompt", "tokens", "prompt_tokens", "layout", "tokenize_add_special"):
            if preflight[key] != prepared[key]:
                raise ValueError("Actual source/native token contract changed from preparation: " + key)
        common.save(preflight_path, preflight)
        # On the first case this event follows verified actual native loading,
        # keeping the monitor's separate 180-second initialization gate active.
        common.event("case_start", id=case_id, prompt_tokens=preflight["prompt_tokens"])
        actual_call_count = 0

        def checked_transport(endpoint, payload=None, timeout=1.5):
            nonlocal actual_call_count
            if endpoint == "/api/chat" and not module.is_ollama_control_request(payload):
                actual_call_count += 1
                if actual_call_count != 1 or payload != request["request"] or timeout != 240:
                    raise ValueError("Actual production inference request differs from its exact frozen single request.")
                report["generation_calls"] += 1
                common.save(output, report)
            return original_transport(endpoint, payload, timeout=timeout)

        module.local_ollama_json = checked_transport
        try:
            value, status = qa.evaluate(HERE / "development-cases.json", path, case_ids=[case_id], splits=["development"])
        finally:
            module.local_ollama_json = original_transport
        actual = value["cases"][0] if value.get("cases") else {}
        records = actual.get("requests", [])
        calls = [r for r in records if r["kind"] == "inference"]
        controls = [r for r in records if r["kind"] == "control"]
        checks = {"one_exact_declared_request": len(calls) == 1 and calls[0]["request"] == request["request"],
                  "request_timeout_240s": len(calls) == 1 and calls[0]["timeout_seconds"] == 240,
                  "structure_execution_and_guard_accepted": status == 0 and value.get("complete") is True,
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
        common.verify_blob(runtime, plan)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 11434))
        fd = os.open(runtime / "infer-daemon-private.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as log:
            process = subprocess.Popen([str(Path(plan["runtime"]["directory"]) / "bin/ollama"), "serve"],
                                       env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report["runtime"] = common.ready(process)
            if report["runtime"].get("version") != plan["runtime"]["version"]:
                raise ValueError("Actual runtime differs from the pinned release.")
            run_cases(runtime, plan, process, report, output)
    except BaseException as error:
        report["complete"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if process is not None:
            common.stop_owned(process)
            report["owned_daemon_stopped"] = process.poll() is not None
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["frozen_inputs_unchanged"] = all(common.sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
        report["complete"] &= report["frozen_inputs_unchanged"]
        common.save(output, report)
    common.event("phase_complete", phase="infer", complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

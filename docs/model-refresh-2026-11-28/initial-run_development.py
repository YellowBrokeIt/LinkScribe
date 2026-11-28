#!/usr/bin/env python3
"""One frozen, development-only model screen through unchanged production code.

The default action checks prepared files without starting a service. Pass
--execute only after the coordinator explicitly releases the inference slot.
The runner never downloads weights and never opens a heldout corpus.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from prepare_model import api, daemon_environment, ready, sha, stop_owned, verify_cached_model
import evaluate_translation_quality as qa
from measure_summary_memory import oom_deltas, oom_snapshot
from smoke_full_local_workflow import ProcessMemory


def check_plan(runtime):
    plan_path = HERE / "plan.json"
    if sha(plan_path) != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The frozen plan changed.")
    plan = json.loads(plan_path.read_text())
    for relative, expected in plan["source_sha256"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("Declared source or development data changed: " + relative)
    if sha(__file__) != plan["runner_sha256"] or sha(HERE / "prepare_model.py") != plan["setup_runner_sha256"]:
        raise ValueError("A frozen experiment runner changed.")
    if sha(runtime / "bin/ollama") != plan["runtime"]["binary_sha256"]:
        raise ValueError("Runtime binary differs from the verified release.")
    setup = json.loads((HERE / "model-setup.json").read_text())
    if (not setup.get("complete") or setup.get("inference_calls") != 0
            or not setup.get("owned_daemon_stopped")
            or setup.get("plan_sha256") != sha(plan_path)):
        raise ValueError("The declared pull-only setup did not complete.")
    verify_cached_model(runtime, plan["model"])
    corpus = qa.read_corpus(HERE / "development-cases.json")
    if ([case["id"] for case in corpus["cases"]] != plan["evaluation"]["case_ids"]
            or any(case["split"] != "development" for case in corpus["cases"])):
        raise ValueError("Unexpected case selection; only the six exposed development cases are allowed.")
    return plan


def request_checks(case, baseline, model):
    requests = case.get("requests", [])
    inference = [item for item in requests if item["kind"] == "inference"]
    controls = [item for item in requests if item["kind"] == "control"]
    original = [item for item in baseline["requests"] if item["kind"] == "inference"]
    protocol = bool(inference) and len(inference) == len(original)
    final_content = bool(inference)
    no_reasoning = bool(inference)
    for index, item in enumerate(inference):
        body = copy.deepcopy(item["request"])
        protocol = protocol and body.pop("model", None) == model and item["timeout_seconds"] == 240
        expected = copy.deepcopy(original[index]["request"]) if index < len(original) else {}
        expected.pop("model", None)
        protocol = protocol and body == expected
        protocol = protocol and body.get("think") is False and isinstance(body.get("format"), dict)
        protocol = protocol and body.get("options") == {
            "temperature": 0, "num_ctx": 8192, "num_predict": 2048, "num_thread": 4}
        response = json.loads(item.get("response_json", "{}"))
        message = response.get("message", {})
        final_content = (final_content and response.get("done") is True
                         and response.get("done_reason") == "stop"
                         and isinstance(message.get("content"), str) and bool(message["content"].strip()))
        thinking = message.get("thinking", "")
        no_reasoning = no_reasoning and isinstance(thinking, str) and not thinking.strip()
    cleanup = bool(controls)
    for item in controls:
        response = json.loads(item.get("response_json", "{}"))
        cleanup = (cleanup and item["request"].get("model") == model and not item.get("error")
                   and response.get("done") is True and response.get("done_reason") == "unload")
    return {"unchanged_production_requests_except_model": bool(protocol),
            "normal_completion_and_final_content": bool(final_content),
            "empty_reasoning_field": bool(no_reasoning), "unload_acknowledged": bool(cleanup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Run only after the parent releases the compute slot.")
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    plan = check_plan(runtime)
    if not args.execute:
        print(json.dumps({"check_only": True, "plan_sha256": sha(HERE / "plan.json"),
                          "case_count": len(plan["evaluation"]["case_ids"]), "model": plan["model"]["tag"],
                          "inference_calls": 0}))
        return 0
    output = HERE / "execution.json"
    if output.exists() or any((HERE / (case + ".json")).exists() for case in plan["evaluation"]["case_ids"]):
        raise ValueError("Refusing to overwrite previous experiment outputs.")
    baseline_report = json.loads((ROOT / plan["evaluation"]["retained_baseline"]).read_text())
    baseline = {case["id"]: case for case in baseline_report["cases"]}
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 11434))
    os.environ.update({"LINKSCRIBE_TRANSLATION_BACKEND": "ollama",
                       "LINKSCRIBE_TRANSLATION_MODEL": plan["model"]["tag"],
                       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"})
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    summary = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
               "plan_sha256": sha(HERE / "plan.json"), "runner_sha256": sha(__file__),
               "complete": False, "semantic_quality": "unreviewed", "cases": [],
               "heldout_cases_opened_or_run": False, "production_source_changed": False,
               "whole_machine_resource_approval": False}
    save = lambda: qa.atomic_checkpoint(output, summary)
    save()
    interruption = {}

    def interrupt(number, _frame):
        interruption["reason"] = "aggregate_time_limit" if number == signal.SIGALRM else "external_stop"
        raise KeyboardInterrupt

    signal.signal(signal.SIGALRM, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    signal.alarm(plan["limits"]["aggregate_seconds"])
    private_log = runtime / "model-refresh-inference-private.log"
    process = None
    meter = None
    original_checkpoint = qa.atomic_checkpoint
    try:
        descriptor = os.open(private_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as log:
            process = subprocess.Popen([str(runtime / "bin/ollama"), "serve"],
                                       env=daemon_environment(runtime), stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            summary["runtime"] = ready(process)
            tags = api("/api/tags")
            selected = next((item for item in tags.get("models", [])
                             if item.get("name") == plan["model"]["tag"]), None)
            if (summary["runtime"].get("version") != plan["runtime"]["version"] or not selected
                    or selected.get("digest") != plan["model"]["manifest_sha256"]):
                raise ValueError("The executing runtime/model identity differs from the plan.")
            summary["installed_model"] = selected
            meter = ProcessMemory(process.pid)
            meter.verify_endpoint("http://127.0.0.1:11434")
            before_oom = oom_snapshot([os.getpid(), process.pid])
            import psutil
            memory_before = psutil.virtual_memory()
            summary["host_before"] = {"total_mib": round(memory_before.total / 1024**2, 1),
                                      "available_mib": round(memory_before.available / 1024**2, 1)}
            meter.start()
            save()
            for case_id in plan["evaluation"]["case_ids"]:
                report_path = HERE / (case_id + ".json")

                def checkpoint(path, report):
                    report["experiment_memory_so_far"] = meter.snapshot()
                    report["experiment_plan_sha256"] = sha(HERE / "plan.json")
                    original_checkpoint(path, report)

                qa.atomic_checkpoint = checkpoint
                try:
                    report, status = qa.evaluate(HERE / "development-cases.json", report_path,
                                                 case_ids=[case_id], splits=["development"])
                finally:
                    qa.atomic_checkpoint = original_checkpoint
                case = report["cases"][0] if report.get("cases") else {}
                checks = request_checks(case, baseline[case_id], plan["model"]["tag"])
                checks["resident_model_unloaded"] = api("/api/ps").get("models") == []
                snapshot = meter.snapshot()
                checks["sampled_rss_within_process_budget"] = (
                    snapshot.get("peak_combined_rss_mib") is not None
                    and snapshot["peak_combined_rss_mib"] <= plan["limits"]["process_budget_mib"])
                entry = {"id": case_id, "report": report_path.name, "report_sha256": sha(report_path),
                         "exit_code": status, "complete": report["complete"], "checks": checks,
                         "automatic_status": case.get("automatic_status"), "semantic_quality": "unreviewed"}
                summary["cases"].append(entry)
                summary["memory"] = snapshot
                save()
                if status or not report["complete"] or not all(checks.values()):
                    summary["stop_reason"] = interruption.get("reason", "first_execution_or_resource_failure")
                    break
            meter.stop()
            summary["memory"] = meter.snapshot()
            after_oom = oom_snapshot([os.getpid(), process.pid])
            summary["oom_counters"] = {"before": before_oom, "after": after_oom,
                                       "deltas": oom_deltas(before_oom, after_oom)}
            summary["complete"] = (len(summary["cases"]) == len(plan["evaluation"]["case_ids"])
                                   and not summary.get("stop_reason")
                                   and summary["memory"]["measurement_complete"])
            summary["next_step"] = "Independent semantic review required; no summary or validation is authorized by execution success."
    except BaseException as error:
        summary["error"] = {"type": type(error).__name__, "message": str(error)}
        summary["stop_reason"] = interruption.get("reason", "execution_exception")
    finally:
        signal.alarm(0)
        qa.atomic_checkpoint = original_checkpoint
        if meter is not None:
            if not meter.snapshot()["sampler_stopped"]:
                meter.stop()
            summary["memory"] = meter.snapshot()
        if process is not None:
            stop_owned(process)
            summary["owned_daemon_stopped"] = process.poll() is not None
        summary["source_hashes_unchanged"] = all(sha(ROOT / path) == expected
                                                  for path, expected in plan["source_sha256"].items())
        if not summary["source_hashes_unchanged"]:
            summary["complete"] = False
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({"complete": summary["complete"], "cases": len(summary["cases"]),
                      "semantic_quality": "unreviewed", "stop_reason": summary.get("stop_reason"),
                      "report": str(output)}), flush=True)
    return int(not summary["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

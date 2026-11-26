#!/usr/bin/env python3
"""Replay exact recorded summary maps/reductions; run corrected finals live.

This is mixed replay/live regression evidence, never a fully live long-pipeline
benchmark or fresh validation. The unchanged repository evaluator still owns
the actual application, SQLite, exports and fresh-interpreter checks.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


LIVE_CASE = "summary-en-consent-and-roles"
REPLAY_CASES = ("summary-long-en-board-game-day", "summary-long-el-photo-archive")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def phase_of(payload):
    if payload.get("messages") == [] and payload.get("keep_alive") == 0:
        return "unload"
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or messages[0].get("role") != "system":
        raise ValueError("Unexpected summary request messages.")
    system = messages[0].get("content")
    if not isinstance(system, str):
        raise ValueError("Expected a textual summary system message.")
    return ("direct" if "chapter_title" in system and "key_points" in system
            else "map" if "chapter_title" in system
            else "synthesis" if "key_points" in system else "reduce")


def plans_from_baseline(baseline, corpus, live_ids, replay_ids):
    if not baseline.get("complete") or not baseline.get("corpus_complete"):
        raise ValueError("Replay requires an immutable completed full baseline report.")
    before_hashes = baseline.get("source_before", {}).get("sha256")
    if not isinstance(before_hashes, dict) or not before_hashes or before_hashes != baseline.get("source_after", {}).get("sha256"):
        raise ValueError("Baseline source hashes must be unchanged.")
    if baseline.get("runtime_before") != baseline.get("runtime_after"):
        raise ValueError("Baseline runtime must be unchanged.")
    current = {case["id"]: case for case in corpus["cases"]}
    previous = {case["id"]: case for case in baseline["cases"]}
    if set(live_ids) & set(replay_ids) or len(set(live_ids + replay_ids)) != len(live_ids + replay_ids):
        raise ValueError("Live and replay case selections must be distinct and unique.")
    plans = {}
    for case_id in live_ids + replay_ids:
        if case_id not in current or case_id not in previous:
            raise ValueError("Selected case is absent from the corpus or completed baseline.")
        case = previous[case_id]
        if not case.get("complete") or canonical(case.get("fixture")) != canonical(current[case_id]):
            raise ValueError("Selected fixture changed or its baseline case is incomplete.")
        if case_id in live_ids:
            plans[case_id] = {"mode": "live_direct", "events": [], "baseline_case": case}
            continue
        requests = case.get("requests", [])
        phases = [event.get("phase") for event in requests if event.get("kind") == "inference"]
        if (not case.get("checks", {}).get("all_source_characters_reached_source_requests")
                or not phases or phases[-1] != "synthesis" or phases.count("synthesis") != 1
                or phases != ["map"] * phases.count("map")
                            + ["reduce"] * phases.count("reduce") + ["synthesis"]):
            raise ValueError("A replay case lacks a complete ordered pre-final trace: " + case_id)
        events = []
        for index, event in enumerate(requests):
            if event.get("phase") not in {"map", "reduce"}:
                continue
            response = event.get("response_json")
            if (event.get("kind") != "inference" or event.get("error")
                    or not event.get("response_evidence_available") or not isinstance(response, dict)
                    or response.get("done") is not True or response.get("done_reason") != "stop"
                    or not isinstance(response.get("message", {}).get("content"), str)
                    or phase_of(event["request"]) != event["phase"]):
                raise ValueError("Only completed map/reduce responses can be replayed: " + case_id)
            parsed = json.loads(response["message"]["content"])
            if not isinstance(parsed, dict) or not isinstance(parsed.get("notes"), str) or not parsed["notes"].strip():
                raise ValueError("A recorded map/reduce response lacks usable notes.")
            events.append({"baseline_request_index": index, "event": deepcopy(event)})
        if not events:
            raise ValueError("A replay case needs at least one completed map request.")
        plans[case_id] = {"mode": "replayed_maps_reductions_live_final", "events": events,
                          "baseline_case": case}
    return plans


class ReplayController:
    def __init__(self, plans, baseline_runtime, transport, provenance):
        self.plans = plans
        self.baseline_runtime = deepcopy(baseline_runtime)
        self.transport = transport
        self.provenance = provenance
        self.cursors = {case_id: 0 for case_id in plans}
        self.live_attempts = {case_id: 0 for case_id in plans}
        self.active_case = None
        self.active_event = None
        self.runtime_verified = False
        self.failure = None
        self.report = None

    def verify_runtime(self, runtime):
        if canonical(runtime) != canonical(self.baseline_runtime):
            self.failure = "Selected model, digest, runtime or options differ from the baseline."
            raise ValueError(self.failure)
        self.runtime_verified = True

    def enrich(self, report):
        self.report = report
        report["execution_mode"] = "captured_map_reduction_replay_with_live_direct_and_final"
        report["replay_provenance"] = deepcopy(self.provenance)
        report["interpretation"] = (
            "Mixed replay/live regression on exposed cases. Long map/reduction responses are reused only "
            "after exact ordered request and timeout matches. Direct/final outputs are new local model "
            "inference. Application persistence, exports and fresh-interpreter retrieval are actual. "
            "Source coverage for replayed stages means constructed-request/code coverage, not fresh "
            "model processing of that source. Structure does not approve semantic quality.")
        report["measurement_scope"] = (
            "Elapsed time includes fast recorded-response replay plus new direct/final inference. "
            "It must not be reported as fully live long-summary latency.")
        report["request_kind_scope"] = (
            "kind=inference identifies a logical pipeline operation; evidence_origin distinguishes "
            "live_local_ollama from replayed_completed_response. inference_request_count counts live "
            "attempts only; logical and replayed request counts are recorded separately.")
        self.active_case = self.active_event = None
        for case in report.get("cases", []):
            case_id = case["id"]
            if case_id not in self.plans:
                self.failure = "The evaluator attempted an unselected case."
                raise ValueError(self.failure)
            case["execution_mode"] = self.plans[case_id]["mode"]
            case["baseline_full_case_elapsed_seconds"] = self.plans[case_id]["baseline_case"].get("elapsed_seconds")
            events = case.get("requests", [])
            logical = [event for event in events if event.get("kind") == "inference"]
            live = [event for event in logical if event.get("evidence_origin") == "live_local_ollama"]
            replayed = [event for event in logical if event.get("evidence_origin") == "replayed_completed_response"]
            blocked = [event for event in logical if event.get("evidence_origin") == "blocked_request"]
            case["logical_inference_request_count"] = len(logical)
            case["inference_request_count"] = case["actual_live_inference_attempt_count"] = len(live)
            case["replayed_inference_request_count"] = len(replayed)
            case["blocked_inference_request_count"] = len(blocked)
            case["fully_live_model_pipeline"] = self.plans[case_id]["mode"] == "live_direct"
            if not case.get("complete"):
                self.active_case = case_id
                self.active_event = events[-1] if events else None
        report["actual_live_inference_attempt_count"] = sum(case["actual_live_inference_attempt_count"] for case in report.get("cases", []))
        report["replayed_inference_request_count"] = sum(case["replayed_inference_request_count"] for case in report.get("cases", []))
        report["logical_inference_request_count"] = sum(case["logical_inference_request_count"] for case in report.get("cases", []))
        if self.failure:
            report["replay_contract_error"] = self.failure

    def block(self, message):
        self.failure = self.failure or message
        if self.active_event is not None:
            self.active_event["evidence_origin"] = "blocked_request"
            self.active_event["replay_contract_error"] = self.failure
        raise ValueError(self.failure)

    def __call__(self, path, payload=None, timeout=1.5):
        if path != "/api/chat":
            return self.transport(path, payload, timeout=timeout)
        if not isinstance(payload, dict):
            return self.block("A chat body must be a JSON object.")
        try:
            phase = phase_of(payload)
        except ValueError as exc:
            return self.block(str(exc))
        if self.active_case is None or self.active_event is None:
            return self.block("A chat request occurred outside an observed selected case.")
        event = self.active_event
        if (canonical(event.get("request")) != canonical(payload)
                or canonical(event.get("timeout_seconds")) != canonical(timeout)
                or event.get("phase") != phase):
            return self.block("Observer and delegated request do not match.")
        if phase == "unload":
            if payload.get("model") != self.baseline_runtime["configured_model"]:
                return self.block("Unexpected model in unload control.")
            event["evidence_origin"] = "live_unload_control"
            return self.transport(path, payload, timeout=timeout)
        if self.failure:
            return self.block(self.failure)
        if not self.runtime_verified:
            return self.block("Runtime identity was not verified before inference.")
        case_id = self.active_case
        plan = self.plans[case_id]
        if phase in {"map", "reduce"}:
            cursor = self.cursors[case_id]
            if plan["mode"] == "live_direct" or cursor >= len(plan["events"]) or self.live_attempts[case_id]:
                return self.block("No eligible next recorded map/reduction stage.")
            recorded = plan["events"][cursor]
            old = recorded["event"]
            if (old["phase"] != phase or canonical(old["request"]) != canonical(payload)
                    or canonical(old["timeout_seconds"]) != canonical(timeout)):
                return self.block("Recorded map/reduction request or timeout differs; no fallback allowed.")
            event.update({"evidence_origin": "replayed_completed_response",
                          "replay_source_case_id": case_id,
                          "replay_source_request_index": recorded["baseline_request_index"],
                          "replay_source_report_sha256": self.provenance["baseline_report_sha256"],
                          "replay_response_sha256": digest(canonical(old["response_json"])),
                          "replay_request_sha256": digest(canonical(old["request"])),
                          "replay_hash_scope": "Canonical parsed JSON: sorted keys, compact separators, ASCII escaping; not wire bytes.",
                          "original_inference_elapsed_seconds": old.get("elapsed_seconds")})
            self.cursors[case_id] += 1
            return deepcopy(old["response_json"])
        expected = "direct" if plan["mode"] == "live_direct" else "synthesis"
        if phase != expected or self.cursors[case_id] != len(plan["events"]) or self.live_attempts[case_id]:
            return self.block("Unexpected, early or repeated direct/final inference.")
        schema = payload.get("format")
        points = schema.get("properties", {}).get("key_points", {}) if isinstance(schema, dict) else {}
        if (not isinstance(schema, dict) or schema.get("type") != "object"
                or points.get("minItems") != 1 or points.get("maxItems") != 8
                or payload.get("model") != self.baseline_runtime["configured_model"]
                or canonical(payload.get("options")) != canonical(self.baseline_runtime["inference_options"])
                or canonical(timeout) != canonical(240)):
            return self.block("The live final request does not have the frozen eight-point contract/options.")
        event["evidence_origin"] = "live_local_ollama"
        self.live_attempts[case_id] += 1
        return self.transport(path, payload, timeout=timeout)

    def verify_finished(self):
        if self.failure:
            raise ValueError(self.failure)
        for case_id, plan in self.plans.items():
            if self.cursors[case_id] != len(plan["events"]) or self.live_attempts[case_id] != 1:
                raise ValueError("Missing replay or live final stage for " + case_id)


def load_harness(repo):
    path = repo / "tests/evaluate_summary_quality.py"
    spec = importlib.util.spec_from_file_location("summary_quality_observer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-case", action="append", dest="live_ids",
                        help="Case with fully live direct inference; default: the exposed consent case.")
    parser.add_argument("--replay-case", action="append", dest="replay_ids",
                        help="Case with exact pre-final replay and a live final; default: both exposed long cases.")
    args = parser.parse_args(argv)
    args.repo, args.baseline, args.output = (path.resolve() for path in (args.repo, args.baseline, args.output))
    if args.output.exists():
        parser.error("Refusing to overwrite an existing evidence report.")
    raw = args.baseline.read_bytes()
    if digest(raw) != args.baseline_sha256:
        parser.error("Baseline SHA-256 does not match the supplied frozen digest.")
    baseline = json.loads(raw)
    harness = load_harness(args.repo)
    corpus_path = args.repo / "tests/fixtures/summary_quality_cases.json"
    live_ids = args.live_ids if args.live_ids is not None else [LIVE_CASE]
    replay_ids = args.replay_ids if args.replay_ids is not None else list(REPLAY_CASES)
    selected_ids = live_ids + replay_ids
    corpus, _, corpus_sha = harness.read_corpus(corpus_path, selected_ids)
    if corpus_sha != baseline.get("corpus_sha256"):
        parser.error("The frozen corpus hash differs from the baseline.")
    plans = plans_from_baseline(baseline, corpus, live_ids, replay_ids)
    sys.path.insert(0, str(args.repo))
    import enhancements
    if enhancements.MAX_SUMMARY_KEY_POINTS != 8:
        parser.error("Expected the frozen eight-point production contract.")
    helper_sha = digest(Path(__file__).read_bytes())
    provenance = {"baseline_report_file": args.baseline.name, "baseline_report_sha256": digest(raw),
                  "corpus_sha256": corpus_sha, "model_digest": baseline["runtime_before"]["model"]["digest"],
                  "wrapper_sha256": helper_sha, "wrapper_file": Path(__file__).name,
                  "baseline_complete_required": True, "exact_ordered_request_matching": True,
                  "live_fallback_for_replay_mismatch": False,
                  "replayed_phases": ["map", "reduce"], "live_inference_phases": ["direct", "synthesis"],
                  "selected_cases": selected_ids}
    original_transport = enhancements.local_ollama_json
    original_runtime = harness.runtime_identity
    original_checkpoint = harness.checkpoint
    controller = ReplayController(plans, baseline["runtime_before"], original_transport, provenance)

    def checked_runtime(module):
        runtime = original_runtime(module)
        controller.verify_runtime(runtime)
        return runtime

    def labeled_checkpoint(path, report):
        controller.enrich(report)
        original_checkpoint(path, report)

    enhancements.local_ollama_json = controller
    harness.runtime_identity = checked_runtime
    harness.checkpoint = labeled_checkpoint
    code = 1
    try:
        arguments = ["--corpus", str(corpus_path), "--output", str(args.output)]
        for case_id in selected_ids:
            arguments += ["--case", case_id]
        code = harness.main(arguments)
        controller.verify_finished()
        if not controller.report.get("complete"):
            raise ValueError("The application/evaluator run did not complete its evidence checks.")
        if digest(args.baseline.read_bytes()) != args.baseline_sha256 or digest(Path(__file__).read_bytes()) != helper_sha:
            raise ValueError("Baseline or wrapper source changed during the run.")
        controller.report["replay_contract_verified"] = True
    except Exception as exc:
        code = 1
        if controller.report is None:
            controller.report = {"schema_version": 1, "complete": False, "cases": [],
                                 "created_utc": datetime.now(timezone.utc).isoformat()}
        controller.failure = str(exc)
        controller.report["replay_contract_verified"] = False
        controller.report["replay_wrapper_error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        enhancements.local_ollama_json = original_transport
        harness.runtime_identity = original_runtime
        harness.checkpoint = original_checkpoint
        if controller.report is not None:
            controller.enrich(controller.report)
            original_checkpoint(args.output, controller.report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

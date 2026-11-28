"""No-inference checks of replay provenance, matching and live-stage boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from contract_replay_runner import ReplayController, canonical, digest, plans_from_baseline


def body(phase):
    system = {"map": "chapter_title notes", "reduce": "Condense notes",
              "synthesis": "key_points summary", "direct": "key_points summary chapter_title"}[phase]
    result = {"model": "qwen3:4b", "stream": False, "think": False,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": "Owned source."}],
              "options": {"temperature": 0, "num_predict": 2048}, "format": "json"}
    if phase in {"direct", "synthesis"}:
        result["format"] = {"type": "object", "properties": {"key_points": {"minItems": 1, "maxItems": 8}}}
    return result


def setup():
    corpus = {"cases": [{"id": "short", "segments": [{"start": 0, "text": "Source."}]},
                         {"id": "long", "segments": [{"start": 0, "text": "Long source."}]}]}
    runtime = {"configured_model": "qwen3:4b", "model": {"digest": "a" * 64},
               "inference_options": {"temperature": 0, "num_predict": 2048}}
    response = {"done": True, "done_reason": "stop", "message": {"content": json.dumps({"notes": "Recorded notes."})}}
    events = [{"kind": "inference", "phase": phase, "request": body(phase), "timeout_seconds": 240,
               "response_json": deepcopy(response), "response_evidence_available": True, "elapsed_seconds": 12}
              for phase in ("map", "reduce", "synthesis")]
    baseline = {"complete": True, "corpus_complete": True,
                "source_before": {"sha256": {"code": "same"}}, "source_after": {"sha256": {"code": "same"}},
                "runtime_before": runtime, "runtime_after": deepcopy(runtime),
                "cases": [{"id": case["id"], "complete": True, "fixture": deepcopy(case),
                           "checks": {"all_source_characters_reached_source_requests": True},
                           "requests": deepcopy(events) if case["id"] == "long" else []}
                          for case in corpus["cases"]]}
    calls = []

    def live(path, payload=None, *, timeout=1.5):
        calls.append((path, deepcopy(payload), timeout))
        return {"done": True, "done_reason": "stop", "message": {"content": "LIVE NEW FINAL"}}

    plans = plans_from_baseline(baseline, corpus, ["short"], ["long"])
    controller = ReplayController(plans, runtime, live, {"baseline_report_sha256": "b" * 64})
    controller.verify_runtime(runtime)
    return baseline, corpus, controller, calls


def request(controller, case_id, payload, timeout=240):
    report = controller.report or {"cases": []}
    case = next((case for case in report["cases"] if case["id"] == case_id), None)
    if case is None:
        for previous in report["cases"]:
            previous["complete"] = True
        case = {"id": case_id, "complete": False, "requests": []}
        report["cases"].append(case)
    from contract_replay_runner import phase_of
    phase = phase_of(payload)
    event = {"kind": "control" if phase == "unload" else "inference", "phase": phase,
             "request": deepcopy(payload), "timeout_seconds": timeout}
    case["requests"].append(event)
    controller.enrich(report)
    result = controller("/api/chat", payload, timeout=timeout)
    event["response_json"] = deepcopy(result)
    event["response_evidence_available"] = True
    controller.enrich(report)
    return result


def test_exact_stages_replay_but_direct_and_final_are_live_with_separate_counts():
    baseline, _, controller, calls = setup()
    assert request(controller, "short", body("direct"))["message"]["content"] == "LIVE NEW FINAL"
    first = request(controller, "long", body("map"))
    first["message"]["content"] = "mutated caller copy"
    assert "Recorded notes" in baseline["cases"][1]["requests"][0]["response_json"]["message"]["content"]
    request(controller, "long", body("reduce"))
    assert request(controller, "long", body("synthesis"))["message"]["content"] == "LIVE NEW FINAL"
    controller.verify_finished()
    assert len(calls) == 2
    report = controller.report
    assert report["logical_inference_request_count"] == 4
    assert report["actual_live_inference_attempt_count"] == 2
    assert report["replayed_inference_request_count"] == 2
    event = report["cases"][1]["requests"][0]
    assert event["replay_response_sha256"] == digest(canonical(baseline["cases"][1]["requests"][0]["response_json"]))
    assert report["cases"][1]["fully_live_model_pipeline"] is False


@pytest.mark.parametrize("change", ["source", "model", "options", "format", "timeout_type"])
def test_changed_replay_request_fails_closed_without_live_fallback(change):
    _, _, controller, calls = setup()
    payload = body("map")
    timeout = 240
    if change == "source": payload["messages"][-1]["content"] += " Changed."
    if change == "model": payload["model"] = "other-model"
    if change == "options": payload["options"]["temperature"] = 0.1
    if change == "format": payload["format"] = {"type": "object"}
    if change == "timeout_type": timeout = 240.0
    with pytest.raises(ValueError, match="differs"):
        request(controller, "long", payload, timeout)
    with pytest.raises(ValueError, match="differs"):
        request(controller, "long", body("map"))
    assert calls == []


def test_early_synthesis_and_out_of_order_reduction_are_blocked():
    for phase in ("synthesis", "reduce"):
        _, _, controller, calls = setup()
        with pytest.raises(ValueError):
            request(controller, "long", body(phase))
        assert calls == []


def test_new_final_cannot_reuse_old_response_or_exceed_eight_point_contract():
    _, _, controller, calls = setup()
    request(controller, "long", body("map"))
    request(controller, "long", body("reduce"))
    payload = body("synthesis")
    payload["format"]["properties"]["key_points"]["maxItems"] = 9
    with pytest.raises(ValueError, match="eight-point"):
        request(controller, "long", payload)
    assert calls == []


def test_changed_runtime_blocks_inference_and_unload_remains_live_cleanup():
    _, _, controller, calls = setup()
    runtime = deepcopy(controller.baseline_runtime)
    runtime["model"]["digest"] = "c" * 64
    with pytest.raises(ValueError, match="digest"):
        controller.verify_runtime(runtime)
    with pytest.raises(ValueError, match="digest"):
        request(controller, "short", body("direct"))
    request(controller, "short", {"model": "qwen3:4b", "messages": [], "stream": False, "keep_alive": 0}, timeout=5)
    assert len(calls) == 1 and calls[0][1]["messages"] == []


@pytest.mark.parametrize("problem", ["incomplete_report", "missing_final", "incomplete_map", "changed_fixture"])
def test_ineligible_baseline_is_rejected_before_any_inference(problem):
    baseline, corpus, _, _ = setup()
    if problem == "incomplete_report": baseline["complete"] = False
    if problem == "missing_final": baseline["cases"][1]["requests"].pop()
    if problem == "incomplete_map": baseline["cases"][1]["requests"][0]["response_json"]["done"] = False
    if problem == "changed_fixture": corpus["cases"][1]["segments"][0]["text"] += " Changed."
    with pytest.raises(ValueError):
        plans_from_baseline(baseline, corpus, ["short"], ["long"])


def test_actual_app_observer_replay_and_fresh_process_hooks_with_synthetic_transport(monkeypatch, tmp_path):
    """Exercise real app/storage/export paths, with conspicuously fake model data."""
    import enhancements
    import contract_replay_runner as runner

    repo = Path(enhancements.__file__).resolve().parent
    phases = []
    model = "synthetic-summary-test:latest"

    def synthetic_transport(path, payload=None, *, timeout=1.5):
        if path == "/api/tags":
            return {"models": [{"name": model, "model": model, "digest": "d" * 64}]}
        if path == "/api/version":
            return {"version": "synthetic-test-no-model-inference"}
        assert path == "/api/chat"
        phase = runner.phase_of(payload)
        phases.append(phase)
        if phase == "unload":
            return {"done": True, "done_reason": "unload", "message": {"content": ""}}
        if phase == "map":
            output = {"notes": "Synthetic transport notes; no meaning assessment. " * 24,
                      "chapter_title": "Synthetic test section"}
        elif phase == "reduce":
            output = {"notes": "Synthetic reduction; no meaning assessment."}
        else:
            output = {"summary": "Synthetic transport output; no model inference occurred.",
                      "key_points": ["Only observer and application integration are tested."]}
            if phase == "direct":
                output["chapter_title"] = "Synthetic test section"
        return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(output)}}

    monkeypatch.setenv("LINKSCRIBE_OLLAMA_MODEL", model)
    monkeypatch.setattr(enhancements, "local_ollama_json", synthetic_transport)
    baseline_path = tmp_path / "synthetic-complete-baseline.json"
    observer = runner.load_harness(repo)
    assert observer.main(["--corpus", str(repo / "tests/fixtures/summary_quality_cases.json"),
                          "--output", str(baseline_path)]) == 0
    phases.clear()
    output_path = tmp_path / "synthetic-contract-replay.json"
    assert runner.main(["--repo", str(repo), "--baseline", str(baseline_path),
                        "--baseline-sha256", digest(baseline_path.read_bytes()),
                        "--output", str(output_path)]) == 0
    report = json.loads(output_path.read_text())
    assert report["complete"] and report["replay_contract_verified"]
    assert report["failed_case_count"] == 0
    assert phases.count("direct") == 1 and phases.count("synthesis") == 2
    assert phases.count("unload") == 3 and not {"map", "reduce"} & set(phases)
    assert report["actual_live_inference_attempt_count"] == 3
    assert report["replayed_inference_request_count"] > 0
    assert report["logical_inference_request_count"] == 3 + report["replayed_inference_request_count"]
    assert all(case["checks"]["fresh_interpreter_matches"] for case in report["cases"])
    # These temporary test artifacts deliberately identify their fake runtime;
    # they are never candidates for publication as actual-model evidence.
    assert report["runtime_before"]["version"]["version"] == "synthetic-test-no-model-inference"
    phases.clear()
    selected_path = tmp_path / "synthetic-english-only-replay.json"
    assert runner.main(["--repo", str(repo), "--baseline", str(baseline_path),
                        "--baseline-sha256", digest(baseline_path.read_bytes()),
                        "--replay-case", runner.REPLAY_CASES[0], "--output", str(selected_path)]) == 0
    selected = json.loads(selected_path.read_text())
    assert selected["selected_case_ids"] == [runner.LIVE_CASE, runner.REPLAY_CASES[0]]
    assert selected["actual_live_inference_attempt_count"] == 2
    assert phases.count("direct") == 1 and phases.count("synthesis") == 1
    assert not {"map", "reduce"} & set(phases)

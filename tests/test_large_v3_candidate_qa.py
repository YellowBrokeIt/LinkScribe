"""Historical large-v3 contract checks; current ASR timing has separate tests.

The published runner/plan stay immutable. Their source-policy preflight must not
claim that a later application policy generated the historical results.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

HELPER = Path(__file__).with_name("qa_large_v3_candidate.py")
SPEC = importlib.util.spec_from_file_location("large_v3_qa_test", HELPER)
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


@pytest.fixture
def historical_utf8(monkeypatch):
    """Reproduce the frozen runner's declared Ubuntu UTF-8 decoding environment.

    Only these historical checks adapt its implicit text reads; source bytes and
    the immutable runner itself remain unchanged on Windows as well as Linux.
    """
    original = Path.read_text
    def read(path, encoding=None, *args, **kwargs):
        return original(path, "utf-8" if encoding is None else encoding, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)


def test_frozen_plan_in_reconstructed_historical_function_view(tmp_path, monkeypatch, historical_utf8):
    plan = json.loads(qa.DEFAULT_PLAN.read_text(encoding="utf-8"))
    original_root = qa.ROOT
    for item in plan["source_files"]:
        source = original_root / item["path"]
        assert source.stat().st_size == item["bytes"] and qa.sha256(source) == item["sha256"]
        destination = tmp_path / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    policy = json.loads((tmp_path / plan["production_policy_path"]).read_text(encoding="utf-8"))
    # This is only the original function/constants, not the historical full app.py.
    declarations = "\n".join(f"{name} = {value!r}" for name, value in policy["constants"].items())
    (tmp_path / "app.py").write_text(declarations + "\n\n" + policy["function_source_lf"], encoding="utf-8")
    monkeypatch.setattr(qa, "ROOT", tmp_path)
    monkeypatch.setattr(qa.common, "ROOT", tmp_path)
    plan = qa.validate_plan(qa.DEFAULT_PLAN)
    assert plan["model_id"] == "Systran/faster-whisper-large-v3"
    assert len(plan["cases"]) == 8
    observed, _ = qa.production_policy()
    assert observed["function_ast_sha256"] == policy["function_ast_sha256"]
    assert observed["constants"] == {"MAX_SECONDS": 7200, "ASR_NO_SPEECH_THRESHOLD": 0.6}


def test_frozen_runner_rejects_the_current_changed_production_policy(historical_utf8):
    with pytest.raises(ValueError, match="production recognition policy changed"):
        qa.validate_plan(qa.DEFAULT_PLAN)


def test_policy_fingerprint_preserves_semantics_and_detects_beam_change():
    left = ast.parse("def f():\n    return run(beam_size=5)\n").body[0]
    windows = ast.parse("def f():\r\n    return run(beam_size=5)\r\n").body[0]
    changed = ast.parse("def f():\n    return run(beam_size=7)\n").body[0]
    assert qa.canonical_ast(left) == qa.canonical_ast(windows)
    assert qa.canonical_ast(left) != qa.canonical_ast(changed)


@pytest.mark.parametrize("times", [
    [{"start": float("nan"), "end": 1}],
    [{"start": 2, "end": 1}],
    [{"start": 1, "end": 3}, {"start": 0.5, "end": 4}],
    [{"start": 0, "end": 3}, {"start": 1, "end": 2}],
])
def test_invalid_native_times_are_rejected_without_replacement(times):
    qa.validate_native_segment_times([{"start": 0, "end": 1}, {"start": 1, "end": 2}])
    with pytest.raises(ValueError, match="finite and ordered"):
        qa.validate_native_segment_times(times)


@pytest.mark.parametrize("change", [
    {"language": "el"}, {"beam_size": 1}, {"vad_filter": True},
    {"word_timestamps": True}, {"initial_prompt": "reference"},
    {"condition_on_previous_text": True},
])
def test_observer_rejects_nonproduction_request(change):
    request = {"language": None, "beam_size": 5, "vad_filter": False,
               "no_speech_threshold": 0.6, "condition_on_previous_text": False}
    qa.validate_request(request)
    with pytest.raises(ValueError, match="request changed"):
        qa.validate_request({**request, **change})


@pytest.mark.skipif(sys.platform != "linux", reason="owned process-group sampler uses Linux /proc")
def test_controller_preserves_recomputable_rss_series_without_models(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    work, evidence = tmp_path / "work", tmp_path / "evidence"
    work.mkdir(); evidence.mkdir()
    for name in ("input-preparation.json", "model-download.json"):
        (evidence / name).write_text('{"complete": true}')
    plan = {"worker_environment": {}, "rss_limit_bytes": 128 * 1024**2,
            "startup_seconds": 10, "per_case_seconds": 10, "total_worker_seconds": 10}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    assert qa.execute(plan, path, work, evidence,
                      test_command=[sys.executable, "-c", "import time; data=bytearray(1024*1024); time.sleep(.15)"]) == 0
    record = json.loads((evidence / "execution.json").read_text())
    samples = [json.loads(line) for line in (evidence / "resource-samples.jsonl").read_text().splitlines()]
    assert len(samples) == record["sample_count"] >= 2
    assert max(s["rss_bytes"] for s in samples) == record["sampled_group_peak_rss_bytes"] > 0
    assert record["resource_samples_sha256"] == qa.sha256(evidence / "resource-samples.jsonl")
    assert record["cleanup"]["live_group_members_after_cleanup"] == []
    assert record["cleanup"]["leader_exited"]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux owned-group controller")
def test_exited_leader_cannot_hide_a_recorded_group_memory_violation(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    work, evidence = tmp_path / "work", tmp_path / "evidence"
    work.mkdir(); evidence.mkdir()
    for name in ("input-preparation.json", "model-download.json"):
        (evidence / name).write_text('{"complete": true}')
    plan = {"worker_environment": {}, "rss_limit_bytes": 1000,
            "startup_seconds": 10, "per_case_seconds": 10, "total_worker_seconds": 10}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    class ExitedLeader:
        pid = 123456789
        def poll(self): return 0
        def wait(self, timeout): return 0
    monkeypatch.setattr(qa.subprocess, "Popen", lambda *a, **k: ExitedLeader())
    monkeypatch.setattr(qa.common, "group_rss", lambda pid: 1001)
    monkeypatch.setattr(qa.common, "terminate_owned", lambda process: {
        "live_group_members_before_cleanup": [], "signals_sent": [],
        "live_group_members_after_cleanup": [], "leader_exited": True})
    assert qa.execute(plan, path, work, evidence, test_command=["never executed"]) == 1
    record = json.loads((evidence / "execution.json").read_text())
    assert record["stop_reason"] == "recorded_group_rss_exceeded"

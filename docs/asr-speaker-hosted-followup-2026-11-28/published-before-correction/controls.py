"""Hosted speaker harness controls use synthetic files/processes, never models."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import wave

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("speaker_hosted_qa_test", Path(__file__).with_name("qa_speaker_integration.py"))
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


def protocol():
    # Fixed declarations are reused, while source validation itself gets a
    # temporary owned source view. Later legitimate app edits must not make
    # ordinary unit tests certify an obsolete hosted source snapshot.
    return json.loads(qa.DEFAULT_PLAN.read_text(encoding="utf-8"))


def test_source_binding_accepts_its_view_and_rejects_changed_code_without_model_imports(tmp_path, monkeypatch):
    plan = protocol()
    source = tmp_path / "owned.py"
    source.write_text("accepted = True\n", encoding="utf-8")
    plan["source_files"] = [{"path": "owned.py", "sha256": qa.sha(source)}]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(qa.common, "ROOT", tmp_path)
    before = set(sys.modules)
    assert qa.validate(plan_path)["attempts"] == 1
    assert not ({"torch", "speechbrain", "faster_whisper", "ctranslate2"} & (set(sys.modules) - before))
    source.write_text("accepted = False\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen source changed"):
        qa.validate(plan_path)


def test_original_fixture_hash_and_annotations_match_retained_preexisting_evidence():
    plan = protocol()
    docs = Path(__file__).resolve().parents[1] / "docs/speaker-evaluation-2026-11-26"
    old = json.loads((docs / "speaker-app-initial.json").read_text(encoding="utf-8"))
    cohort = json.loads((docs / "speaker-fresh-holdout-v4.json").read_text(encoding="utf-8"))
    recorded = next(x for x in cohort["results"] if x["id"] == "two_speakers_returning")
    assert plan["fixture"]["sha256"] == old["audio"]["sha256"] == recorded["audio_sha256"]
    assert plan["fixture"]["reference_intervals"] == [x["reference"] for x in recorded["assessment"]["per_interval"]]


def test_entire_constructed_wave_preserves_clip_order_gaps_returning_identity_and_sample_count(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    rows = [{"speaker_id": s} for s in ["first", "second", "first", "second"]]
    lengths = [131520, 123760, 165680, 205520]
    clips = [np.full(n, value, dtype=np.float32) for n, value in zip(lengths, [.25, -.5, .75, -.25])]
    before = [clip.tobytes() for clip in clips]
    path = tmp_path / "synthetic-construction.wav"
    result = qa.construct_fixture(rows, clips, path)
    assert result["sample_count"] == 554160
    with wave.open(str(path), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 16000, 554160)
        actual = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    assert not actual[:8000].any()
    offset = 8000
    for i, (length, expected) in enumerate(zip([128000, 123760, 128000, 128000], [8191, -16383, 24575, -8191])):
        assert np.all(actual[offset:offset + length] == expected)
        assert result["reference_intervals"][i] == {"start": offset / 16000, "end": (offset + length) / 16000,
                                                   "speaker": rows[i]["speaker_id"], "short": False}
        offset += length
        assert not actual[offset:offset + 9600].any()
        offset += 9600
    assert offset == len(actual) and [clip.tobytes() for clip in clips] == before


def test_failed_download_is_retained_and_never_retried(tmp_path, monkeypatch):
    calls = []
    def response(*args, **kwargs):
        calls.append(args[0])
        return io.BytesIO(b"wrong owned bytes")
    monkeypatch.setattr(qa.urllib.request, "urlopen", response)
    target = tmp_path / "owned.bin"
    with pytest.raises(ValueError, match="identity"):
        qa.download_checked("https://example.org/owned", target, hashlib.sha256(b"expected").hexdigest(), 100)
    assert not target.exists() and target.with_suffix(".bin.partial").read_bytes() == b"wrong owned bytes"
    with pytest.raises(ValueError, match="already attempted"):
        qa.download_checked("https://example.org/owned", target, "unused", 100)
    assert len(calls) == 1


@pytest.mark.parametrize("unreadable", ["stat", "statm"])
def test_owned_group_accounting_never_silently_skips_an_unreadable_member(tmp_path, monkeypatch, unreadable):
    for pid, group, pages in ((321, 321, 7), (322, 321, 11), (999, 999, 100)):
        folder = tmp_path / str(pid)
        folder.mkdir()
        (folder / "stat").write_text(f"{pid} (synthetic) S 1 {group} 0\n", encoding="ascii")
        (folder / "statm").write_text(f"200 {pages} 0\n", encoding="ascii")
    complete = qa.strict_group_sample(321, proc_root=tmp_path, page_size=4096)
    assert complete["complete"] and complete["rss_bytes"] == 18 * 4096
    assert [row["pid"] for row in complete["members"]] == [321, 322]
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == tmp_path / "322" / unreadable:
            raise PermissionError("synthetic inaccessible process file")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    incomplete = qa.strict_group_sample(321, proc_root=tmp_path, page_size=4096)
    assert not incomplete["complete"] and incomplete["rss_bytes"] == 7 * 4096
    assert incomplete["read_errors"] == [{"pid": 322, "file": unreadable, "type": "PermissionError",
                                         "membership": "owned" if unreadable == "statm" else "unknown"}]


def test_malformed_native_return_is_saved_before_validation_without_changing_engine(tmp_path, monkeypatch):
    import asr_timing
    smoke_spec = importlib.util.spec_from_file_location("speaker_raw_observer_test", Path(__file__).with_name("smoke_real_speaker_app.py"))
    smoke = importlib.util.module_from_spec(smoke_spec)
    smoke_spec.loader.exec_module(smoke)
    output = tmp_path / "synthetic-raw-return.json"
    calls, snapshots = [], []
    malformed = SimpleNamespace(alignments=[(0, 0), (1, 1)], text_token_probs=[.8, .9])
    requests = []
    def native_align(*args, **kwargs):
        requests.append((args, kwargs))
        return [malformed]
    native = SimpleNamespace(align=native_align)
    engine = SimpleNamespace(model=native)
    def persist():
        smoke.save(output, {"calls": calls})
        snapshots.append(json.loads(output.read_text(encoding="utf-8")))
    init, align = smoke.alignment_observers(asr_timing._AlignOnly.__init__, asr_timing._AlignOnly.align, calls, persist)
    monkeypatch.setattr(asr_timing._AlignOnly, "__init__", init)
    monkeypatch.setattr(asr_timing._AlignOnly, "align", align)
    encoded = object()
    guard = asr_timing._AlignOnly(engine.model, encoded, SimpleNamespace(sot_sequence=[10, 11]), [20, 21], 6)
    with pytest.raises(asr_timing.TimingUnavailable, match="terminal boundary"):
        guard.align(encoded, [10, 11], [[20, 21]], 6)
    saved = json.loads(output.read_text(encoding="utf-8"))["calls"][0]
    assert engine.model is native and native.align is native_align and len(requests) == 1
    assert saved["native_returned"] and not saved["completed"] and not saved["contract_validated"]
    assert saved["native_results"] == [{"alignments": [[0, 0], [1, 1]], "text_token_probs": [.8, .9]}]
    assert saved["validation_failure"]["type"] == "TimingUnavailable"
    assert any(row["calls"][0].get("native_returned") and "validation_failure" not in row["calls"][0]
               for row in snapshots)


def test_speaker_yaml_cache_check_uses_nodes_and_rejects_unseeded_paths_without_construction(tmp_path, monkeypatch):
    import yaml
    from yaml.constructor import SafeConstructor
    names = ("embedding_model", "mean_var_norm_emb", "classifier", "label_encoder")
    text = "pretrained_path: speechbrain/spkrec-ecapa-voxceleb\n"
    text += "pretrainer: !new:speechbrain.utils.parameter_transfer.Pretrainer\n  loadables:\n"
    text += "".join(f"    {name}: !ref <{name}>\n" for name in names)
    text += "  paths:\n" + "".join(f"    {name}: !ref <pretrained_path>/{name}.ckpt\n" for name in names)
    path = tmp_path / "synthetic-hyperparams.yaml"
    path.write_text(text, encoding="utf-8")
    model = deepcopy(protocol()["models"]["speaker"])
    model["files"]["hyperparams.yaml"]["sha256"] = qa.sha(path)
    monkeypatch.setattr(SafeConstructor, "construct_object", lambda *a, **k: pytest.fail("A YAML object was constructed"))
    result = qa.speaker_cache_declarations(path, model)
    assert not result["object_construction_performed"]
    assert {row["seeded_filename"] for row in result["declarations"].values()} == {name + ".ckpt" for name in names}
    path.write_text(text.replace("<pretrained_path>/classifier.ckpt", "https://example.org/unseeded.ckpt"), encoding="utf-8")
    model["files"]["hyperparams.yaml"]["sha256"] = qa.sha(path)
    with pytest.raises(ValueError, match="checkpoint path"):
        qa.speaker_cache_declarations(path, model)


def completion_control(plan):
    model = plan["models"]["recognizer"]
    return {"complete": True, "audio": {"sha256": plan["fixture"]["sha256"]},
        "elapsed_seconds": 10.0, "peak_process_rss_bytes": 1000,
        "phases": [{"name": "recognition", "elapsed_seconds": 1.0}],
        "actual_transcribe_calls": [{"options": {"language": None, "beam_size": 5, "vad_filter": False,
             "no_speech_threshold": 0.6, "condition_on_previous_text": False, "word_timestamps": False}}],
        "upload_form": {"consent": "true", "speakers": "true", "target_language": "none", "summary": "false"},
        "model_initializations": [{"cpu_threads": 4, "num_workers": 1, "actual_device": "cpu", "actual_compute_type": "int8_float32"}],
        "model_resolutions": [{"revision_directory": model["revision"], "files": {
             name: {"bytes": row["bytes"], "sha256": row["sha256"]} for name, row in model["files"].items()}}],
        "acoustic_analysis_calls": [{"completed": True, "result": {"model": {
             "revision": plan["models"]["speaker"]["revision"], "sha256": {
             name: item["sha256"] for name, item in plan["models"]["speaker"]["files"].items()}}}}]}


@pytest.mark.parametrize("failure", ["rss", "total", "phase", "nan", "second_attempt", "guidance", "model"])
def test_final_recorded_limits_and_protocol_cannot_pass_from_exit_zero_alone(failure):
    plan = protocol()
    report = completion_control(plan)
    qa.completed_contract(plan, report)  # Explicit synthetic structural control only.
    if failure == "rss": report["peak_process_rss_bytes"] = plan["rss_limit_bytes"] + 1
    if failure == "total": report["elapsed_seconds"] = plan["total_worker_seconds"] + 0.01
    if failure == "phase": report["phases"][0]["elapsed_seconds"] = plan["phase_seconds"]["recognition"] + 0.01
    if failure == "nan": report["peak_process_rss_bytes"] = float("nan")
    if failure == "second_attempt": report["actual_transcribe_calls"] *= 2
    if failure == "guidance": report["actual_transcribe_calls"][0]["options"]["initial_prompt"] = "Source names"
    if failure == "model": report["model_resolutions"][0]["revision_directory"] = "different"
    with pytest.raises(ValueError):
        qa.completed_contract(plan, report)


def controller_fixture(tmp_path, monkeypatch):
    plan = protocol()
    evidence, work = tmp_path / "evidence", tmp_path / "work"
    (evidence / "inputs").mkdir(parents=True)
    work.mkdir()
    audio = evidence / "inputs" / plan["fixture"]["filename"]
    audio.write_bytes(b"synthetic controller input; never decoded")
    plan["fixture"]["sha256"] = qa.sha(audio)
    for model in plan["models"].values(): model["files"] = {}
    (evidence / "preparation.json").write_text(json.dumps({"complete": True}), encoding="utf-8")
    plan_path = tmp_path / "synthetic-controller-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(qa.common, "require_hosted", lambda: None)
    return plan, plan_path, work, evidence


def test_existing_attempt_marker_prevents_even_starting_another_worker(tmp_path, monkeypatch):
    plan, plan_path, work, evidence = controller_fixture(tmp_path, monkeypatch)
    (evidence / "execution-requested.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(qa.subprocess, "Popen", lambda *a, **k: pytest.fail("A repeated worker started"))
    with pytest.raises(FileExistsError):
        qa.execute(plan, plan_path, work, evidence, test_command=["never-start"])


@pytest.mark.skipif(sys.platform != "linux", reason="Owned Linux process-group controller")
def test_owned_group_cleanup_runs_even_after_successful_leader_exit(tmp_path, monkeypatch):
    plan, plan_path, work, evidence = controller_fixture(tmp_path, monkeypatch)
    code = "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])"
    assert qa.execute(plan, plan_path, work, evidence, test_command=[sys.executable, "-c", code]) == 1
    result = json.loads((evidence / "execution.json").read_text(encoding="utf-8"))
    assert result["returncode"] == 0 and result["cleanup"]["live_group_members_before_cleanup"]
    assert result["cleanup"]["leader_exited"] and not result["cleanup"]["live_group_members_after_cleanup"]
    assert not qa.common.live_group_members(result["owned_process_group_id"])
    assert result["sample_count"] > 0 and (evidence / "resource-samples.jsonl").stat().st_size > 0


@pytest.mark.skipif(sys.platform != "linux", reason="Owned Linux process-group controller")
def test_incomplete_group_sample_stops_worker_and_cannot_pass_exit_status(tmp_path, monkeypatch):
    plan, plan_path, work, evidence = controller_fixture(tmp_path, monkeypatch)
    original = qa.strict_group_sample
    def incomplete(pgid):
        sample = original(pgid)
        sample.update(complete=False, read_errors=[{"pid": pgid, "file": "statm", "type": "PermissionError", "membership": "owned"}])
        return sample
    monkeypatch.setattr(qa, "strict_group_sample", incomplete)
    assert qa.execute(plan, plan_path, work, evidence,
                      test_command=[sys.executable, "-c", "import time; time.sleep(30)"]) == 1
    result = json.loads((evidence / "execution.json").read_text(encoding="utf-8"))
    assert result["stop_reason"] == "incomplete_owned_group_accounting"
    assert not result["passed"] and not result["all_resource_samples_complete"]
    assert not qa.common.live_group_members(result["owned_process_group_id"])
    samples = [json.loads(line) for line in (evidence / "resource-samples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert samples and all(not row["complete"] and row["read_errors"] for row in samples)

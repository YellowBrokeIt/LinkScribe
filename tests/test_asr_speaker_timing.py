"""Fixed-text speaker timing controls; no model construction or inference."""
from copy import deepcopy
from functools import lru_cache
import gc
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import weakref

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app
import asr_timing as timing
import enhancements
import library


def fake_runtime(monkeypatch, *, mels=80, fail_window=None, malformed=None):
    """Run upstream Python timing methods over explicit synthetic native paths."""
    from faster_whisper.audio import pad_or_trim
    from faster_whisper.transcribe import WhisperModel
    from faster_whisper.utils import get_end
    audio = np.zeros(5 * 16000, dtype=np.float32)
    audio[0], audio[-1] = 0.1, 1e-30
    events = []
    texts = {1: " First", 2: " phrase.", 3: " Quiet", 4: " tail."}

    class Tokenizer:
        eot = 100
        sot_sequence = [101, 102, 103]
        def __init__(self, tokenizer, multilingual, *, task, language):
            assert tokenizer is engine.hf_tokenizer and multilingual and task == "transcribe" and language == "el"
            events.append(("tokenizer", language))
        def decode(self, tokens):
            return "".join(texts[token] for token in tokens if token < self.eot)
        def encode(self, text):
            pytest.fail("Fixed source text must not be reencoded")
        def split_to_word_tokens(self, tokens):
            return [texts.get(token, "<|endoftext|>") for token in tokens], [[token] for token in tokens]

    class Extractor:
        hop_length, sampling_rate, nb_max_frames, time_per_frame = 160, 16000, 300, 0.01
        def __call__(self, samples):
            assert samples is audio and samples[-1] == np.float32(1e-30)
            events.append(("frontend", len(samples)))
            return np.zeros((mels, len(samples) // 160 + 1), dtype=np.float32)

    class Native:
        n_mels, is_multilingual = mels, True
        def align(self, encoded, start_sequence, tokens, frames, **options):
            call = 1 + sum(event[0] == "align" for event in events)
            events.append(("align", deepcopy(tokens), frames))
            assert start_sequence == Tokenizer.sot_sequence and options == {"median_filter_width": 7}
            assert encoded is engine.encoded
            if fail_window == call:
                raise RuntimeError("Synthetic late native failure")
            count, frame_count = len(tokens[0]), frames // 2
            path = [(min(count, frame * count // (frame_count - 1)), frame) for frame in range(frame_count)]
            if malformed == "terminal":
                path.pop()
            if malformed == "missing_token":
                path = [(index, frame) for index, frame in path if index != 1]
            return [SimpleNamespace(alignments=path, text_token_probs=[0.9] * count)]
        def generate(self, *args, **kwargs):
            pytest.fail("Timing invoked recognition")
        def detect_language(self, *args, **kwargs):
            pytest.fail("Timing redetected language")

    raw = [{"start": 0.0, "end": 2.8, "text": " First phrase.", "tokens": [111, 1, 2, 112], "seek": 0},
           {"start": 3.0, "end": 5.0, "text": " Quiet tail.", "tokens": [111, 3, 4, 112], "seek": 300}]
    baseline = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in raw]

    class Engine:
        feature_extractor = Extractor()
        model = Native()
        hf_tokenizer = object()
        input_stride, frames_per_second, tokens_per_second = 2, 100, 50
        def transcribe(self, samples, **options):
            assert samples is audio and options["word_timestamps"] is False
            events.append(("transcribe", options))
            def generate():
                yield from (SimpleNamespace(**s, no_speech_prob=0.1) for s in raw)
                events.append(("consumed",))
            return generate(), SimpleNamespace(language="el")
        def encode(self, features):
            assert features.shape == (mels, 300)
            events.append(("encode", features.shape))
            self.encoded = object()
            return self.encoded

    engine = Engine()
    monkeypatch.setattr(timing, "_runtime", lambda: (WhisperModel, Tokenizer, pad_or_trim, get_end))
    return engine, audio, raw, baseline, events


@pytest.mark.parametrize("mels", [80, 128])
def test_actual_upstream_timing_methods_use_full_frontend_and_original_windows(monkeypatch, mels):
    engine, audio, raw, baseline, events = fake_runtime(monkeypatch, mels=mels)
    original = deepcopy(raw), deepcopy(baseline), audio.tobytes()
    result = timing.align_fixed_segments(engine, audio, "el", baseline, raw, bound=app._bounded_asr_interval)
    assert [s["text"] for s in result.segments] == [s["text"] for s in baseline]
    assert result.provenance["status"] == "complete" and result.provenance["word_timed_segments"] == 2
    assert [e for e in events if e[0] == "frontend"] == [("frontend", len(audio))]
    assert [e for e in events if e[0] == "align"] == [("align", [[1, 2]], 300), ("align", [[3, 4]], 200)]
    assert not any(e[0] == "transcribe" for e in events)
    assert (raw, baseline, audio.tobytes()) == original
    assert all(set(s) == {"start", "end", "text", "_words"} for s in result.segments)
    assert all("".join(w["word"] for w in s["_words"]).strip() == s["text"] for s in result.segments)


def test_sequential_state_uses_upstream_get_end_not_timing_method_return(monkeypatch):
    engine, audio, raw, baseline, _ = fake_runtime(monkeypatch)
    native_class, tokenizer, pad, get_end = timing._runtime()
    observed = []
    def postpass(adapter, groups, tokens, encoded, frames, prepend, append, state):
        observed.append({"before": state})
        native_class.add_word_timestamps(adapter, groups, tokens, encoded, frames, prepend, append, state)
        observed[-1]["actual_get_end"] = get_end(groups[0])
        return 9999.0  # Deliberately differs; never a valid sequential state.
    proxy = SimpleNamespace(transcribe=native_class.transcribe, find_alignment=native_class.find_alignment,
                            add_word_timestamps=postpass)
    monkeypatch.setattr(timing, "_runtime", lambda: (proxy, tokenizer, pad, get_end))
    result = timing.align_fixed_segments(engine, audio, "el", baseline, raw, bound=app._bounded_asr_interval)
    assert result.provenance["status"] == "complete" and len(observed) == 2
    assert observed[0]["before"] == 0 and observed[1]["before"] == observed[0]["actual_get_end"]


@pytest.mark.parametrize("change", ["text", "token", "seek", "seek_order", "empty_window"])
def test_incomplete_source_mapping_never_guesses_tokens_or_seeks(monkeypatch, change):
    engine, audio, raw, baseline, events = fake_runtime(monkeypatch)
    if change == "text": raw[0]["text"] = " Replacement text"
    if change == "token": raw[0]["tokens"] = [1, 1]
    if change == "seek": raw[0]["seek"] = 0.0
    if change == "seek_order": raw[0]["seek"], raw[1]["seek"] = 300, 0
    if change == "empty_window": raw[1]["seek"] = 500
    with pytest.raises(timing.TimingUnavailable):
        timing.align_fixed_segments(engine, audio, "el", baseline, raw, bound=app._bounded_asr_interval)
    assert not any(e[0] == "transcribe" for e in events)


@pytest.mark.parametrize("malformed", ["terminal", "missing_token"])
def test_native_path_requires_complete_text_and_terminal_boundary(monkeypatch, malformed):
    engine, audio, raw, baseline, _ = fake_runtime(monkeypatch, malformed=malformed)
    with pytest.raises(timing.TimingUnavailable):
        timing.align_fixed_segments(engine, audio, "el", baseline, raw, bound=app._bounded_asr_interval)


def test_terminal_row_is_a_boundary_and_zero_token_duration_is_not_fabricated():
    timing._validate_native_path([(0, 0), (1, 0), (1, 1), (2, 2)], [0.8, 0.9], 2, 6)
    with pytest.raises(timing.TimingUnavailable, match="probabilities"):
        timing._validate_native_path([(0, 0), (1, 1), (2, 2)], [0.8, 0.9, 0.7], 2, 6)


@pytest.mark.parametrize("speaker_timing", [False, True])
def test_one_baseline_pass_and_separate_timing_share_same_full_array(monkeypatch, tmp_path, speaker_timing):
    engine, audio, raw, baseline, events = fake_runtime(monkeypatch)
    decodes = []
    def decode(path, sampling_rate):
        decodes.append((path, sampling_rate))
        return audio
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    loads = []
    monkeypatch.setattr(app, "_whisper_model", lambda name: (loads.append(name), engine)[1])
    result = app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=speaker_timing)
    assert len(decodes) == len(loads) == 1 and loads == ["small"]
    calls = [e for e in events if e[0] == "transcribe"]
    assert len(calls) == 1 and calls[0][1]["word_timestamps"] is False
    assert result.segments == baseline and result.language == "el"
    if speaker_timing:
        assert result.speaker_segments and result.asr_provenance["speaker_timing"]["status"] == "complete"
        assert events.index(("consumed",)) < events.index(("frontend", len(audio)))
    else:
        assert result.speaker_segments is None and not any(e[0] == "frontend" for e in events)


def test_late_timing_failure_discards_partial_candidate_and_retains_entire_baseline(monkeypatch, tmp_path):
    engine, audio, raw, baseline, events = fake_runtime(monkeypatch, fail_window=2)
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", lambda *a, **k: audio)
    monkeypatch.setattr(app, "_whisper_model", lambda _: engine)
    result = app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=True)
    assert result.segments == baseline
    assert result.speaker_segments == [{**s, "_words": []} for s in baseline]
    assert len(result.warnings) == 1 and result.asr_provenance["speaker_timing"]["status"] == "unavailable"
    assert sum(e[0] == "transcribe" for e in events) == 1 and sum(e[0] == "align" for e in events) == 2


@pytest.mark.parametrize("failure", ["mutate_then_raise", "changed_text", "reordered", "missing", "out_of_bounds"])
def test_optional_helper_cannot_mutate_or_replace_authoritative_baseline(monkeypatch, tmp_path, failure):
    engine, audio, raw, baseline, events = fake_runtime(monkeypatch)
    original_raw = deepcopy(raw)
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", lambda *a, **k: audio)
    monkeypatch.setattr(app, "_whisper_model", lambda _: engine)
    def broken(engine, audio, language, items, native, **kwargs):
        native[0]["tokens"].clear()
        if failure == "mutate_then_raise":
            items[0]["text"] = "Corruption before exception"
            raise RuntimeError("Synthetic optional failure")
        if failure == "changed_text": items[0]["text"] = "Silent corruption"
        if failure == "reordered": items.reverse()
        if failure == "missing": items.pop()
        if failure == "out_of_bounds": items[-1]["end"] = 6
        return timing.TimingResult(items, [], {})
    monkeypatch.setattr(timing, "align_fixed_segments", broken)
    result = app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=True)
    assert result.segments == baseline and raw == original_raw
    assert result.speaker_segments == [{**s, "_words": []} for s in baseline]
    assert result.asr_provenance["speaker_timing"]["status"] == "unavailable" and result.warnings
    assert sum(e[0] == "transcribe" for e in events) == 1


def test_unreviewed_runtime_falls_back_before_frontend(monkeypatch, tmp_path):
    audio = np.ones(16000, dtype=np.float32)
    monkeypatch.setattr(timing, "version", lambda name: "unreviewed")
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", lambda *a, **k: audio)
    engine = SimpleNamespace(transcribe=lambda *a, **k: (iter([SimpleNamespace(
        start=0, end=1, text="Original source", tokens=[1], seek=0)]), SimpleNamespace(language="en")))
    monkeypatch.setattr(app, "_whisper_model", lambda _: engine)
    result = app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=True)
    assert result.segments == [{"start": 0, "end": 1, "text": "Original source"}]
    assert result.warnings and result.asr_provenance["speaker_timing"]["status"] == "unavailable"


@pytest.mark.parametrize("failure", ["empty", "no_speech", "invalid_bounds"])
def test_rejected_baseline_never_runs_optional_timing(monkeypatch, tmp_path, failure):
    audio = np.ones(16000, dtype=np.float32)
    source = [] if failure == "empty" else [SimpleNamespace(start=0, end=0 if failure == "invalid_bounds" else 1,
        text="Original", no_speech_prob=0.99, tokens=[1], seek=0)]
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", lambda *a, **k: audio)
    monkeypatch.setattr(importlib.import_module("faster_whisper.vad"), "get_speech_timestamps", lambda *a, **k: [])
    monkeypatch.setattr(app, "_whisper_model", lambda _: SimpleNamespace(
        transcribe=lambda *a, **k: (iter(source), SimpleNamespace(language="en"))))
    monkeypatch.setattr(timing, "align_fixed_segments", lambda *a, **k: pytest.fail("Rejected baseline reached timing"))
    with pytest.raises(app.ReadableError):
        app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=True)


def test_conflict_fallback_propagates_to_neighbors_without_changing_text_or_valid_metadata():
    baseline = [{"start": i * 2, "end": i * 2 + 1, "text": str(i)} for i in range(4)]
    candidates = [{**s, "_words": [{"word": s["text"], "start": s["start"], "end": s["end"]}],
                   "metadata": {"owned": i}} for i, s in enumerate(baseline)]
    candidates[0].update(start=0, end=2.1)
    candidates[1].update(start=2, end=4.5)
    candidates[2].update(start=4.6, end=5.0)
    original = deepcopy(candidates)
    result, reverted = timing.resolve_interval_conflicts(candidates, baseline, 8)
    # Restoring index 1 to [2,3] still conflicts with candidate0, while index2
    # remains independent; the conflicting pair alone is discarded here.
    assert reverted == {0, 1} and result[2:] == candidates[2:]
    assert candidates == original
    assert all(result[i]["_words"] == [] and result[i]["metadata"] == candidates[i]["metadata"] for i in reverted)


def test_restoring_a_conflict_can_force_another_neighbor_to_fall_back():
    baseline = [{"start": 0, "end": 2, "text": "a"}, {"start": 2, "end": 4, "text": "b"},
                {"start": 4, "end": 6, "text": "c"}]
    candidates = [{"start": 0, "end": 1, "text": "a", "_words": []},
                  {"start": 0.9, "end": 2.5, "text": "b", "_words": []},
                  {"start": 2.5, "end": 5.5, "text": "c", "_words": []}]
    result, reverted = timing.resolve_interval_conflicts(candidates, baseline, 6)
    assert reverted == {0, 1, 2} and result == [{**s, "_words": []} for s in baseline]
    with pytest.raises(timing.TimingUnavailable, match="baseline"):
        timing.resolve_interval_conflicts(candidates, candidates, 6)


def test_many_bad_word_intervals_have_bounded_durable_warnings(monkeypatch, tmp_path):
    baseline = [{"start": i, "end": i + 1, "text": "Owned source"} for i in range(250)]
    raw = [{**s, "tokens": [1], "seek": i * 100} for i, s in enumerate(baseline)]
    adjusted = [{**s, "words": [{"word": "Owned source", "start": s["start"], "end": s["start"]}]} for s in raw]
    result = timing.project_segments(baseline, raw, adjusted, [True] * 250,
        [(i, i + 1) for i in range(250)], 250, app._bounded_asr_interval)
    assert len(result.warnings) == 1 and result.provenance["word_timed_segments"] == 0
    assert result.provenance["original_timing_segments"] == 0  # Segment timing itself remained valid.
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    job = app._new_job("owned", "Many words")
    recognition = app.RecognitionResult(baseline, "en", result.segments, result.warnings,
        {"engine": "faster-whisper", "model": "small", "word_timestamps": False, "speaker_timing": result.provenance})
    def speakers(path, segments, **kwargs):
        labeled, warnings, _ = enhancements._word_speaker_alignment(segments, [])
        return {"segments": labeled, "warnings": warnings, "provenance": {"backend": "synthetic"}}
    monkeypatch.setattr(app, "assign_speakers", speakers)
    app._enhance_and_save(job.id, baseline, "en", "local_audio_ai", tmp_path / "owned.wav",
                          True, "none", False, recognition=recognition)
    saved = library.get(job.id)
    assert len(saved["segments"]) == 250 and job.status == "done"
    assert len(saved["processing_metadata"]["warnings"]) <= 5
    assert all(set(s) <= {"start", "end", "text", "speaker"} for s in saved["segments"])
    app.jobs.pop(job.id)
    with TestClient(app.app) as client:
        exported = client.get(f"/api/library/{job.id}/download/json")
        assert exported.status_code == 200 and exported.json()["processing_metadata"] == saved["processing_metadata"]
        assert client.get(f"/api/library/{job.id}").json()["processing_metadata"]["warnings"]


@pytest.mark.parametrize("error", [app.EnhancementError("Owned speaker failure"), RuntimeError("Owned bug")])
def test_speaker_failure_keeps_baseline_even_if_backend_mutated_candidate(monkeypatch, error):
    baseline = [{"start": 0, "end": 3, "text": "Every original word"}]
    candidate = [{"start": 1, "end": 2, "text": "Every original word", "_words": []}]
    result = app.RecognitionResult(deepcopy(baseline), "en", deepcopy(candidate), ["Owned timing warning"],
                                   {"word_timestamps": False})
    saved = []
    monkeypatch.setattr(app, "_set", lambda *a, **k: None)
    monkeypatch.setattr(app, "_write_exports", lambda *a, **k: saved.append(a))
    def fail(path, segments, **kwargs):
        segments[0]["text"] = "Corrupted input"
        raise error
    monkeypatch.setattr(app, "assign_speakers", fail)
    app._enhance_and_save("owned", result.segments, "en", "local_audio_ai", Path("owned.wav"),
                          True, "none", False, recognition=result)
    assert saved[0][1] == baseline and result.segments == baseline and result.speaker_segments == candidate
    assert "Owned timing warning" in saved[0][6]["warnings"]


def test_result_does_not_hold_audio_or_model_after_audio_phase_release(monkeypatch, tmp_path):
    references = []
    def decode(*args, **kwargs):
        audio = np.ones(16000, dtype=np.float32)
        references.append(weakref.ref(audio))
        return audio
    class Engine:
        def transcribe(self, audio, **kwargs):
            yield_result = [SimpleNamespace(start=0, end=1, text="Owned", tokens=[1], seek=0)]
            return iter(yield_result), SimpleNamespace(language="en")
    @lru_cache(maxsize=1)
    def load(model):
        engine = Engine()
        references.append(weakref.ref(engine))
        return engine
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    monkeypatch.setattr(app, "_whisper_model", load)
    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic exception traceback must not escape")
    monkeypatch.setattr(timing, "align_fixed_segments", fail)
    result = app._recognize(tmp_path / "owned.wav", "auto", "small", speaker_timing=True)
    assert result.segments and result.warnings
    app._release_audio_models()
    gc.collect()
    assert all(ref() is None for ref in references)


def test_production_projection_matches_all_five_retained_offline_results():
    """Replay retained JSON only; this neither reruns ASR nor regrades acoustics."""
    docs = Path(__file__).resolve().parents[1] / "docs"
    original = docs / "post-asr-alignment-diagnostic-2026-11-28/original-stage"
    cases = json.loads((original / "input-cases.json").read_text(encoding="utf-8"))["cases"]
    native = json.loads((original / "results/report.json").read_text(encoding="utf-8"))["case_results"]
    expected = json.loads((docs / "post-asr-local-projection-2026-11-28/results/report.json").read_text(encoding="utf-8"))["case_results"]
    assert len(cases) == len(native) == len(expected) == 5
    for case, retained, reviewed in zip(cases, native, expected):
        assert case["id"] == retained["id"] == reviewed["id"]
        duration = case["array"]["duration_seconds"]
        baseline = []
        for source in case["baseline_segments"]:
            start, end = app._bounded_asr_interval(source["start"], source["end"], duration)
            baseline.append({**source, "start": start, "end": end})
        adjusted, mapping, windows = [None] * len(baseline), [False] * len(baseline), [None] * len(baseline)
        for record in retained["windows"]:
            window = record["window"]
            words = [word for word in record["native_words_after_merge"] if word["word"]]
            assert [t for w in words for t in w["tokens"]] == window["text_tokens"]
            offset, boundaries = 0, {0}
            for word in words:
                offset += len(word["tokens"])
                boundaries.add(offset)
            for index, segment, span in zip(window["segment_indices"], record["upstream_adjusted_segments"], window["segment_token_spans"]):
                adjusted[index] = segment
                mapping[index] = span["start"] in boundaries and span["end"] in boundaries
                windows[index] = (window["seek"] / 100, min(duration, (window["seek"] + window["num_frames"]) / 100))
        result = timing.project_segments(baseline, case["raw_segments"], adjusted, mapping, windows,
                                          duration, app._bounded_asr_interval)
        assert result.segments == reviewed["candidate_segments"]
        assert result.provenance["original_timing_segments"] == len(reviewed["projection"]["fallback_segment_indices"])

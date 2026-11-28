"""Whole-recording corroboration must not remove quiet individual segments."""
import importlib
from types import SimpleNamespace

import numpy as np
import pytest

import app


def configure(monkeypatch, scores, *, speech=None, failure=None, word_timestamps=False):
    audio = np.array([0, 0.1, -0.1, 0, 1e-30], dtype=np.float32)
    before = audio.tobytes()
    events = []
    segments = [SimpleNamespace(start=float(i), end=float(i + 1), text=f"Owned phrase {i}",
                    no_speech_prob=score,
                    words=[SimpleNamespace(start=float(i), end=float(i + 1), word=f"word {i}")])
                for i, score in enumerate(scores)]

    def decode(path, sampling_rate):
        events.append(("decode", path, sampling_rate))
        return audio

    def transcribe(value, **options):
        assert value is audio and value.tobytes() == before
        assert options["vad_filter"] is False
        assert options["no_speech_threshold"] == app.ASR_NO_SPEECH_THRESHOLD
        assert options["condition_on_previous_text"] is False
        events.append(("transcribe", options))

        def generate():
            for segment in segments:
                events.append(("yield", segment))
                yield segment
            events.append(("consumed",))

        return generate(), SimpleNamespace(language="el")

    def vad(value, **options):
        assert value is audio and value.tobytes() == before
        assert events[-1] == ("consumed",), "Speech check ran before complete ASR consumption"
        assert options == {"sampling_rate": 16000}, "Unexpected tuned VAD settings"
        events.append(("corroborate",))
        if failure is not None:
            raise failure
        return speech or []

    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    monkeypatch.setattr(importlib.import_module("faster_whisper.vad"), "get_speech_timestamps", vad)
    monkeypatch.setattr(app, "_whisper_model", lambda _: SimpleNamespace(transcribe=transcribe))
    return audio, before, segments, events


def test_consistent_no_speech_without_corroboration_rejects_whole_output(monkeypatch, tmp_path):
    audio, before, segments, events = configure(monkeypatch, [0.991, 0.999])
    with pytest.raises(app.ReadableError, match=r"^No spoken words were detected in this recording\.$") as caught:
        app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert caught.value.__cause__ is None
    assert [e[0] for e in events] == ["decode", "transcribe", "yield", "yield", "consumed", "corroborate"]
    assert audio.tobytes() == before


@pytest.mark.parametrize("scores", [[0.1, 0.999], [0.999, 0.1], [0.6, 0.999]])
@pytest.mark.parametrize("word_timestamps", [False, True])
def test_one_asr_anchor_preserves_every_segment_without_loading_vad(monkeypatch, tmp_path, scores, word_timestamps):
    audio, before, segments, events = configure(monkeypatch, scores)
    result, language = app._recognize(tmp_path / "owned.wav", "el", "small", word_timestamps=word_timestamps)
    assert language == "el" and [s["text"] for s in result] == [s.text for s in segments]
    assert [s["start"] for s in result] == [s.start for s in segments]
    assert all(("_words" in s) is word_timestamps for s in result)
    assert not any(e[0] == "corroborate" for e in events)
    assert audio.tobytes() == before


def test_one_vad_interval_preserves_entire_output_without_cropping(monkeypatch, tmp_path):
    audio, before, segments, events = configure(monkeypatch, [0.99, 0.98], speech=[{"start": 1, "end": 2}])
    result, _ = app._recognize(tmp_path / "owned.wav", "auto", "small", word_timestamps=True)
    assert [s["text"] for s in result] == [s.text for s in segments]
    assert len(result) == 2 and result[-1]["_words"][0]["word"] == "word 1"
    assert [e[0] for e in events].count("corroborate") == 1
    assert audio.tobytes() == before


def test_diagnostic_failure_is_specific_and_retains_cause(monkeypatch, tmp_path):
    failure = RuntimeError("Owned VAD failure")
    configure(monkeypatch, [0.99], failure=failure)
    with pytest.raises(app.ReadableError, match=r"^Speech detection could not verify this recording\.") as caught:
        app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert caught.value.__cause__ is failure
    assert "could not decode" not in str(caught.value)


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), float("-inf"), "0.99"])
def test_invalid_score_cannot_establish_consistent_no_speech(monkeypatch, tmp_path, score):
    _, _, segments, events = configure(monkeypatch, [0.99, score])
    result, _ = app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert [s["text"] for s in result] == [s.text for s in segments]
    assert not any(e[0] == "corroborate" for e in events)


def test_blank_segments_never_supply_an_anchor(monkeypatch, tmp_path):
    _, _, segments, _ = configure(monkeypatch, [0.1, 0.99])
    segments[0].text = " \n "
    with pytest.raises(app.ReadableError, match="No spoken words"):
        app._recognize(tmp_path / "owned.wav", "auto", "small")


def test_empty_output_does_not_call_corroborator(monkeypatch, tmp_path):
    _, _, _, events = configure(monkeypatch, [])
    with pytest.raises(app.ReadableError, match="No spoken words"):
        app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert not any(e[0] == "corroborate" for e in events)


def test_threshold_cannot_drift_from_actual_transcribe_option(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "ASR_NO_SPEECH_THRESHOLD", 0.7)
    _, _, segments, events = configure(monkeypatch, [0.65, 0.99])
    result, _ = app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert [s["text"] for s in result] == [s.text for s in segments]
    assert not any(e[0] == "corroborate" for e in events)

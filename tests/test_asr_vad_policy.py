"""Protect the no-prefilter ASR boundary; speaker timing remains independent."""
from types import SimpleNamespace

import numpy as np
import pytest

import app


def stub_decode(monkeypatch, audio):
    import importlib
    calls = []

    def decode(path, sampling_rate):
        calls.append((path, sampling_rate))
        return audio

    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    return calls


@pytest.mark.parametrize("word_timestamps", [False, True])
def test_asr_preserves_full_input_and_optional_word_timing(monkeypatch, tmp_path, word_timestamps):
    calls = []
    audio = np.array([0, 0.1, -0.1, 0, 1e-30], dtype=np.float32)
    original = audio.copy()
    decodes = stub_decode(monkeypatch, audio)
    spoken = [SimpleNamespace(start=start, end=start + 1, text=text,
                words=[SimpleNamespace(start=start, end=start + 1, word=text)])
              for start, text in [(1.0, "Owned early speech"), (560.0, "Owned quiet tail")]]

    class Engine:
        def transcribe(self, path, **options):
            calls.append((path, options))
            # A prefilter request would recreate the boundary that lost real
            # later speech in the recorded hosted provider diagnosis.
            assert options["vad_filter"] is False
            return iter(spoken), SimpleNamespace(language="en")

    monkeypatch.setattr(app, "_whisper_model", lambda model: Engine())
    path = tmp_path / "owned.wav"
    segments, language = app._recognize(path, "auto", "small", word_timestamps=word_timestamps)
    assert decodes == [(str(path), 16000)]
    assert calls[0][0] is audio
    assert np.array_equal(audio, original)
    assert language == "en" and [s["text"] for s in segments] == [s.text for s in spoken]
    assert calls[0][1]["language"] is None
    assert calls[0][1]["condition_on_previous_text"] is False
    assert calls[0][1].get("word_timestamps", False) is word_timestamps
    assert calls[0][1].get("hallucination_silence_threshold") is None
    assert "temperature" not in calls[0][1]  # Fixed-zero fallback lost real dialogue.
    assert all(("_words" in segment) is word_timestamps for segment in segments)


@pytest.mark.parametrize("kind", ["empty", "positive_zero", "negative_zero"])
def test_digital_silence_rejected_before_any_model_request(monkeypatch, tmp_path, kind):
    audio = (np.empty(0, dtype=np.float32) if kind == "empty" else
             np.full(128, -0.0 if kind == "negative_zero" else 0.0, dtype=np.float32))
    decodes = stub_decode(monkeypatch, audio)
    monkeypatch.setattr(app, "_whisper_model", lambda *_: pytest.fail("Silence reached the model loader"))
    with pytest.raises(app.ReadableError, match=r"^No spoken words were detected in this recording\.$") as caught:
        app._recognize(tmp_path / "owned.wav", "auto", "small")
    assert caught.value.__cause__ is None
    assert len(decodes) == 1


@pytest.mark.parametrize("sample", [np.nextafter(np.float32(0), np.float32(1)),
                                   np.nextafter(np.float32(0), np.float32(-1))])
def test_tiniest_nonzero_float_is_preserved_and_reaches_model(monkeypatch, tmp_path, sample):
    audio = np.zeros(128, dtype=np.float32)
    audio[-1] = sample
    before = audio.tobytes()
    decodes = stub_decode(monkeypatch, audio)
    calls = []

    class Engine:
        def transcribe(self, samples, **options):
            calls.append((samples, options))
            return iter([SimpleNamespace(start=0, end=0.008, text="Synthetic tiny input result")]), SimpleNamespace(language="el")

    monkeypatch.setattr(app, "_whisper_model", lambda *_: Engine())
    result, language = app._recognize(tmp_path / "owned.wav", "el", "small")
    assert language == "el" and result[0]["text"] == "Synthetic tiny input result"
    assert len(decodes) == len(calls) == 1 and calls[0][0] is audio
    assert audio.tobytes() == before and calls[0][1]["vad_filter"] is False


@pytest.mark.parametrize("samples", [15999, 16000, 16001])
def test_decoded_duration_limit_is_exact_and_never_trims(monkeypatch, tmp_path, samples):
    monkeypatch.setattr(app, "MAX_SECONDS", 1)
    audio = np.zeros(samples, dtype=np.float32)
    audio[-1] = np.float32(1e-20)
    decodes = stub_decode(monkeypatch, audio)
    calls = []

    class Engine:
        def transcribe(self, value, **options):
            calls.append(value)
            assert value is audio and len(value) == samples
            return iter([SimpleNamespace(start=0, end=samples / 16000, text="Synthetic bounded input")]), SimpleNamespace(language="en")

    def load(_):
        assert samples <= 16000, "Over-limit decoded audio reached the model loader"
        return Engine()

    monkeypatch.setattr(app, "_whisper_model", load)
    if samples > 16000:
        with pytest.raises(app.ReadableError, match=r"^The recording exceeds the 2-hour limit\.$") as caught:
            app._recognize(tmp_path / "owned.wav", "auto", "small")
        assert caught.value.__cause__ is None and not calls
    else:
        assert app._recognize(tmp_path / "owned.wav", "auto", "small")[0]
        assert len(calls) == 1
    assert len(decodes) == 1 and len(audio) == samples


def test_real_pyav_silence_decode_runs_once_without_model_loading(monkeypatch, tmp_path):
    import importlib
    import wave
    module = importlib.import_module("faster_whisper.audio")
    original = module.decode_audio
    path = tmp_path / "owned-stereo-silence.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(bytes(800 * 2 * 2))
    calls = []

    def observed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(module, "decode_audio", observed)
    monkeypatch.setattr(app, "_whisper_model", lambda *_: pytest.fail("Real digital silence reached the model loader"))
    with pytest.raises(app.ReadableError, match=r"^No spoken words were detected in this recording\.$"):
        app._recognize(path, "auto", "small")
    assert len(calls) == 1 and calls[0].shape == (1600,) and not calls[0].any()


def test_decoder_failure_preserves_its_cause_without_loading_model(monkeypatch, tmp_path):
    import importlib
    failure = ValueError("Owned undecodable media")

    def decode(*args, **kwargs):
        raise failure

    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    monkeypatch.setattr(app, "_whisper_model", lambda *_: pytest.fail("Decoder failure reached the model loader"))
    with pytest.raises(app.ReadableError, match="speech model could not decode") as caught:
        app._recognize(tmp_path / "invalid.wav", "auto", "small")
    assert caught.value.__cause__ is failure

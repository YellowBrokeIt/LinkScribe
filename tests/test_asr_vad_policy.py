"""Protect the no-prefilter ASR boundary; speaker timing remains independent."""
from types import SimpleNamespace

import pytest

import app


@pytest.mark.parametrize("word_timestamps", [False, True])
def test_asr_preserves_full_input_and_optional_word_timing(monkeypatch, tmp_path, word_timestamps):
    calls = []
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
    assert language == "en" and [s["text"] for s in segments] == [s.text for s in spoken]
    assert calls[0][1]["language"] is None
    assert calls[0][1]["condition_on_previous_text"] is False
    assert calls[0][1].get("word_timestamps", False) is word_timestamps
    assert all(("_words" in segment) is word_timestamps for segment in segments)

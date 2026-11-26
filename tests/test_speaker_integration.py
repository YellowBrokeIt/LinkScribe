"""Default public speakers, explicit legacy routing, and honest text alignment."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

import diagnostics
import diarization
import enhancements


@pytest.fixture(autouse=True)
def speaker_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("LINKSCRIBE_SPEAKER_BACKEND", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_CACHE", str(tmp_path / "model"))


def analysis(turns):
    return {"turns": turns, "warnings": [], "backend": "speechbrain-ecapa-silero-cpu",
            "model": {"id": diarization.MODEL_ID, "revision": diarization.MODEL_REVISION,
                      "sha256": {"embedding_model.ckpt": "a" * 64}},
            "settings": {"cpu_threads": 2}, "embeddings": ["must-never-be-persisted"],
            "audio": "must-never-be-persisted"}


def stub_public(monkeypatch, turns):
    monkeypatch.setattr(diarization, "diarize_audio", lambda *_args, **_kw: analysis(turns))
    monkeypatch.setattr(enhancements, "_diarization_pipeline", lambda *_: pytest.fail("Default must not load a gated model"))


def test_default_needs_no_token_preserves_metadata_and_returns_safe_provenance(monkeypatch, tmp_path):
    stub_public(monkeypatch, [{"start": 0, "end": 3, "speaker": "alpha"},
                              {"start": 3, "end": 6, "speaker": "beta"},
                              {"start": 6, "end": 9, "speaker": "alpha"}])
    source = [{"start": i * 3, "end": i * 3 + 3, "text": text, "metadata": {"index": i}}
              for i, text in enumerate(("First utterance", "Reply", "Returning voice"))]
    before = deepcopy(source)
    report = enhancements.assign_speakers(tmp_path / "a.wav", source, include_report=True)
    assert source == before
    assert [item["speaker"] for item in report["segments"]] == ["Speaker 1", "Speaker 2", "Speaker 1"]
    assert [{key: value for key, value in item.items() if key != "speaker"} for item in report["segments"]] == source
    assert report["provenance"]["model"]["revision"] == diarization.MODEL_REVISION
    assert "must-never-be-persisted" not in json.dumps(report)
    assert any("simultaneous" in warning for warning in report["warnings"])
    assert isinstance(enhancements.assign_speakers(tmp_path / "a.wav", source), list)


def test_existing_token_does_not_silently_select_gated_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "private-token")
    stub_public(monkeypatch, [])
    result = enhancements.assign_speakers(tmp_path / "a.wav", [{"start": 0, "end": 2, "text": "Hi"}], include_report=True)
    assert result["provenance"]["backend"] == "speechbrain-ecapa-silero-cpu"
    assert "private-token" not in json.dumps(result)


def test_mixed_whole_segment_is_not_assigned_to_longest_speaker(monkeypatch, tmp_path):
    stub_public(monkeypatch, [{"start": 0, "end": 4, "speaker": "a"},
                              {"start": 4, "end": 10, "speaker": "b"}])
    original = {"start": 0, "end": 10, "text": "First person. Second person."}
    result = enhancements.assign_speakers(tmp_path / "a.wav", [original], include_report=True)
    assert result["segments"] == [{**original, "speaker": "Unknown speaker"}]
    assert any("multiple voices" in warning for warning in result["warnings"])
    assert "words" not in result["segments"][0]


@pytest.mark.parametrize("turns", [
    [{"start": 0, "end": 1, "speaker": "a"}],
    [{"start": 0, "end": 6, "speaker": "a"}, {"start": 6, "end": 10, "speaker": None}],
    [],
])
def test_sparse_or_unknown_evidence_abstains(monkeypatch, tmp_path, turns):
    stub_public(monkeypatch, turns)
    result = enhancements.assign_speakers(tmp_path / "a.wav", [{"start": 0, "end": 10, "text": "Speech"}], include_report=True)
    assert result["segments"][0]["speaker"] == "Unknown speaker"
    assert any("lacked enough" in warning for warning in result["warnings"])


def test_small_boundary_jitter_does_not_discard_clear_dominant_evidence(monkeypatch, tmp_path):
    stub_public(monkeypatch, [{"start": 0, "end": 2.9, "speaker": "a"},
                              {"start": 2.9, "end": 3, "speaker": "b"}])
    result = enhancements.assign_speakers(tmp_path / "a.wav", [{"start": 0, "end": 3, "text": "Speech"}])
    assert result[0]["speaker"] == "Speaker 1"


def test_explicit_pyannote_requires_authorized_token(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_BACKEND", "pyannote")
    with pytest.raises(enhancements.EnhancementError, match="HF_TOKEN"):
        enhancements.assign_speakers(tmp_path / "a.wav", [])


def test_pyannote_overlap_is_not_hidden_by_exclusive_timeline(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_BACKEND", "pyannote")
    monkeypatch.setenv("HF_TOKEN", "not-a-real-token")

    class Timeline:
        def __init__(self, labels):
            self.labels = labels

        def itertracks(self, yield_label):
            for label in self.labels:
                yield SimpleNamespace(start=0, end=5), label, label

    output = SimpleNamespace(speaker_diarization=Timeline(["a", "b"]),
                             exclusive_speaker_diarization=Timeline(["a"]))
    monkeypatch.setattr(enhancements, "_diarization_pipeline", lambda *_: lambda *_: output)
    result = enhancements.assign_speakers(tmp_path / "a.wav", [{"start": 0, "end": 5, "text": "Overlap"}], include_report=True)
    assert result["segments"][0]["speaker"] == "Unknown speaker"
    assert result["provenance"]["backend"] == "pyannote-community-1"
    assert "not-a-real-token" not in json.dumps(result)


@pytest.mark.parametrize("start,end", [(float("nan"), 1), (0, float("inf")), (-1, 1), (1, 1), (2, 1)])
def test_invalid_timestamps_never_receive_speaker_labels(start, end):
    with pytest.raises(enhancements.EnhancementError, match="timestamps"):
        enhancements._speaker_alignment([{"start": start, "end": end, "text": "Speech"}], [])


def test_public_dependency_failure_is_readable_and_does_not_fall_back(monkeypatch, tmp_path):
    def unavailable(*_args, **_kwargs):
        raise diarization.DiarizationError("Install requirements-speakers-free.txt for the optional CPU speaker backend.")
    monkeypatch.setattr(diarization, "diarize_audio", unavailable)
    monkeypatch.setattr(enhancements, "_diarization_pipeline", lambda *_: pytest.fail("No automatic fallback"))
    with pytest.raises(enhancements.EnhancementError, match="requirements-speakers-free"):
        enhancements.assign_speakers(tmp_path / "a.wav", [])


def fake_diagnostics(monkeypatch):
    monkeypatch.setattr(diagnostics, "local_ollama_json", lambda *_args, **_kwargs: {"models": []})
    monkeypatch.setattr(diagnostics, "_module_available", lambda *_: True)
    monkeypatch.setattr(diagnostics, "runtime_details", lambda: {"supported": True})


def test_diagnostics_separates_public_dependencies_cache_and_inference(monkeypatch, tmp_path):
    fake_diagnostics(monkeypatch)
    result = diagnostics.report()
    assert result["speakers_configured"]
    assert result["speakers"]["token_required"] is False
    assert result["speakers"]["model_cache_files_present"] is False
    assert result["speakers"]["inference_verified"] is False
    assert any("download on first use" in item for item in result["warnings"])
    cache = tmp_path / "model"
    cache.mkdir()
    for name in ("hyperparams.yaml", "embedding_model.ckpt", "classifier.ckpt", "mean_var_norm_emb.ckpt", "label_encoder.ckpt"):
        (cache / name).write_bytes(b"presence only; not a valid model")
    result = diagnostics.report()
    assert result["speakers"]["model_cache_files_present"] is True
    assert result["speakers"]["inference_verified"] is False


def test_missing_public_dependency_does_not_become_ready_via_pyannote(monkeypatch):
    fake_diagnostics(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "secret-must-stay-hidden")
    monkeypatch.setattr(diagnostics, "_module_available", lambda name: name != "speechbrain")
    result = diagnostics.report()
    assert not result["speakers_configured"]
    assert result["speakers"]["backend"] == "speechbrain"
    assert "secret-must-stay-hidden" not in json.dumps(result)
    assert any("requirements-speakers-free" in item for item in result["warnings"])


def test_bad_backend_configuration_is_visible_without_breaking_diagnostics(monkeypatch):
    fake_diagnostics(monkeypatch)
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_BACKEND", "unknown")
    result = diagnostics.report()
    assert not result["speakers_configured"]
    assert "LINKSCRIBE_SPEAKER_BACKEND" in result["speakers"]["error"]
    assert result["ollama"]["available"]


def test_explicit_blank_cache_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv("LINKSCRIBE_SPEAKER_CACHE", " ")
    with pytest.raises(enhancements.EnhancementError, match="LINKSCRIBE_SPEAKER_CACHE"):
        enhancements.speaker_cache_dir()


def test_actual_word_times_split_mixed_segment_without_losing_words(monkeypatch, tmp_path):
    stub_public(monkeypatch, [{"start": 0, "end": 2, "speaker": "a"},
                              {"start": 2, "end": 4, "speaker": "b"}])
    source = [{"start": 0, "end": 4, "text": "Hello there. Good morning.", "metadata": {"original": True},
               "_words": [{"start": 0.1, "end": 0.7, "word": " Hello"},
                          {"start": 0.8, "end": 1.4, "word": " there."},
                          {"start": 2.2, "end": 2.8, "word": " Good"},
                          {"start": 2.9, "end": 3.8, "word": " morning."}]}]
    before = deepcopy(source)
    result = enhancements.assign_speakers(tmp_path / "a.wav", source, include_report=True)
    assert source == before
    assert [(x["start"], x["end"], x["text"], x["speaker"]) for x in result["segments"]] == [
        (0.1, 1.4, "Hello there.", "Speaker 1"), (2.2, 3.8, "Good morning.", "Speaker 2")]
    assert all(x["metadata"] == {"original": True} and "_words" not in x for x in result["segments"])
    assert result["provenance"]["settings"]["alignment"]["segments_with_validated_word_times"] == 1


@pytest.mark.parametrize("words", [
    [{"start": 0, "end": 4, "word": "Different text"}],
    [{"start": 0, "end": float("nan"), "word": "Hello"}],
    [{"start": 0, "end": 5, "word": "Hello"}],
    [{"start": 2, "end": 2, "word": "Hello"}],
    [],
])
def test_invalid_word_evidence_preserves_whole_original_text(monkeypatch, tmp_path, words):
    stub_public(monkeypatch, [{"start": 0, "end": 2, "speaker": "a"},
                              {"start": 2, "end": 4, "speaker": "b"}])
    source = [{"start": 0, "end": 4, "text": "Hello", "_words": words}]
    result = enhancements.assign_speakers(tmp_path / "a.wav", source, include_report=True)
    assert result["segments"] == [{"start": 0, "end": 4, "text": "Hello", "speaker": "Unknown speaker"}]
    assert any("without guessed word boundaries" in item for item in result["warnings"])

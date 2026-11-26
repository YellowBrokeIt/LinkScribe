"""Deterministic contracts for the optional public-model speaker backend.

Model inference is exercised separately by smoke_real_speakers.py. These tests
must not fetch weights or require Torch/SpeechBrain in the base test environment.
"""
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diarization as speaker


def normalized(rows):
    values = np.asarray(rows, dtype=np.float32)
    return values / np.linalg.norm(values, axis=1, keepdims=True)


def test_telemetry_opt_out_is_set_before_optional_runtime_is_imported():
    environment = dict(os.environ, ORT_DISABLE_TELEMETRY="0")
    command = "import os, sys, diarization; assert os.environ['ORT_DISABLE_TELEMETRY']=='1'; assert 'onnxruntime' not in sys.modules"
    subprocess.run([sys.executable, "-c", command], cwd=Path(__file__).resolve().parents[1],
                   env=environment, check=True, timeout=10)


@pytest.mark.parametrize("changes", [
    {"window_seconds": float("nan")}, {"hop_seconds": 0},
    {"minimum_window_seconds": 8}, {"cpu_threads": True},
    {"max_cluster_windows": 401}, {"max_windows": 8001},
    {"max_audio_seconds": 7201}, {"minimum_cluster_windows": 1},
    {"minimum_similarity": -0.1}, {"embedding_batch_size": 17},
])
def test_configuration_is_bounded(changes):
    with pytest.raises(speaker.DiarizationError):
        replace(speaker.DiarizationConfig(), **changes).validate()


def test_windows_are_bounded_and_near_duplicate_tail_is_not_extra_support():
    config = speaker.DiarizationConfig()
    regions = [{"start": 0, "end": 41600}, {"start": 48000, "end": 56000},
               {"start": 64000, "end": 200000}]
    windows, short = speaker.make_windows(regions, config)
    assert sum(item["region"] == 0 for item in windows) == 1
    assert short == [1]
    assert all(item["end"] - item["start"] <= 40000 for item in windows)
    assert all(regions[item["region"]]["start"] <= item["start"] < item["end"] <=
               regions[item["region"]]["end"] for item in windows)
    assert windows == speaker.make_windows(regions, config)[0]
    with pytest.raises(speaker.DiarizationError, match="Too many"):
        speaker.make_windows(regions, replace(config, max_windows=2))


@pytest.mark.parametrize("regions", [
    [{"start": -1, "end": 20000}], [{"start": 0, "end": 0}],
    [{"start": 0, "end": 20000}, {"start": 19999, "end": 30000}],
    [{"start": 0.5, "end": 20000}],
])
def test_invalid_vad_regions_are_rejected(regions):
    with pytest.raises(speaker.DiarizationError):
        speaker.make_windows(regions, speaker.DiarizationConfig())


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
@pytest.mark.parametrize("voices", [1, 2, 3])
def test_cluster_count_is_discovered_and_returning_voice_is_consistent(voices):
    basis = np.eye(3, dtype=np.float32)
    sequence = list(range(voices)) + list(range(voices)) + [0]
    vectors = np.stack([basis[index] for index in sequence])
    decisions, count = speaker.cluster_windows(vectors, speaker.DiarizationConfig())
    assert count == voices
    assert decisions[0]["speaker"] == decisions[-1]["speaker"]
    assert len({decisions[index]["speaker"] for index in range(voices)}) == voices
    assert all(item["reason"] is None for item in decisions)


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
def test_ambiguous_and_unsupported_voice_is_not_forced_to_known_label():
    vectors = normalized([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 1, 0],
                          [0.7, 0.7, 0], [0, 0, 1]])
    decisions, count = speaker.cluster_windows(vectors, speaker.DiarizationConfig())
    assert count == 2
    assert decisions[-2]["speaker"] is None
    assert decisions[-2]["reason"] == "mixed_or_ambiguous_voice"
    assert decisions[-1]["speaker"] is None
    assert decisions[-1]["reason"] == "insufficient_speaker_evidence"


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
def test_unsupported_cluster_is_not_rescued_by_lower_assignment_threshold():
    vectors = normalized([[1, 0], [1, 0], [0.62, np.sqrt(1 - 0.62 ** 2)]])
    decisions, count = speaker.cluster_windows(vectors, replace(speaker.DiarizationConfig(), cluster_distance=0.36))
    assert count == 1
    assert decisions[-1]["similarity"] >= 0.60
    assert decisions[-1]["speaker"] is None
    assert decisions[-1]["reason"] == "insufficient_speaker_evidence"


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
def test_single_window_does_not_establish_a_speaker():
    decisions, count = speaker.cluster_windows(normalized([[1, 1]]), speaker.DiarizationConfig())
    assert count == 0
    assert decisions[0]["speaker"] is None
    assert decisions[0]["reason"] == "insufficient_speaker_evidence"


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
def test_cluster_limit_does_not_force_distinct_voices_to_merge():
    with pytest.raises(speaker.DiarizationError, match="no forced merge"):
        speaker.cluster_windows(np.repeat(np.eye(3), 2, axis=0),
                                replace(speaker.DiarizationConfig(), max_speakers=2))


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
@pytest.mark.parametrize("vectors", [np.array([1, 2]), np.array([[np.nan, 0]]),
                                     np.array([[0, 0]]), np.zeros((2, 0))])
def test_invalid_embedding_cannot_become_a_label(vectors):
    with pytest.raises(speaker.DiarizationError, match="invalid embeddings"):
        speaker.cluster_windows(vectors, speaker.DiarizationConfig())


@pytest.mark.skipif(importlib.util.find_spec("scipy") is None, reason="optional speaker clustering dependency")
def test_temporal_clustering_sample_is_bounded_and_deterministic():
    vectors = np.repeat(np.eye(2), 1000, axis=0)
    config = replace(speaker.DiarizationConfig(), max_cluster_windows=20)
    first = speaker.cluster_windows(vectors, config)
    assert first == speaker.cluster_windows(vectors, config)
    assert first[1] == 2


def test_acoustic_turns_preserve_short_unknown_and_never_invent_text():
    regions = [{"start": 0, "end": 100000}, {"start": 120000, "end": 128000}]
    windows, _ = speaker.make_windows(regions, speaker.DiarizationConfig())
    decisions = [{"speaker": "Speaker 1" if i < 2 else "Speaker 2", "similarity": 0.8,
                  "margin": 0.2, "reason": None} for i in range(len(windows))]
    turns = speaker.make_turns(regions, windows, decisions)
    assert turns[0]["start"] == 0
    assert turns[-2]["end"] == 6.25
    assert turns[-1]["start"] == 7.5
    assert turns[-1]["speaker"] is None
    assert turns[-1]["reason"] == "speech_too_short"
    assert all("text" not in item and "words" not in item for item in turns)
    assert all(a["end"] <= b["start"] for a, b in zip(turns, turns[1:]))


def test_decoder_resamples_real_stereo_wav_and_enforces_duration(tmp_path):
    path = tmp_path / "stereo.wav"
    samples = np.column_stack([np.full(22050, 1000, dtype=np.int16),
                               np.full(22050, -500, dtype=np.int16)])
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(samples.tobytes())
    decoded = speaker.decode_mono(path, 2)
    assert decoded.shape == (16000,)
    assert decoded.dtype == np.float32
    assert np.isfinite(decoded).all()
    with pytest.raises(speaker.DiarizationError, match="duration limit"):
        speaker.decode_mono(path, 0.5)


def test_corrupt_audio_gives_readable_failure(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not audio")
    with pytest.raises(speaker.DiarizationError, match="Cannot decode"):
        speaker.decode_mono(path, 3)


def test_silence_never_downloads_or_calls_speaker_model(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker, "decode_mono", lambda *_: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(speaker, "speech_regions", lambda *_: [])
    monkeypatch.setattr(speaker, "embed_windows", lambda *_: pytest.fail("silence must not load a speaker model"))
    result = speaker.diarize_audio(tmp_path / "silence.wav", cache_dir=tmp_path)
    assert result["speaker_count"] == 0 and result["turns"] == []
    assert "No speech" in result["warnings"][0]
    assert result["overlapping_speech_supported"] is False


def test_bad_vad_extent_does_not_reach_model(monkeypatch, tmp_path):
    monkeypatch.setattr(speaker, "decode_mono", lambda *_: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(speaker, "speech_regions", lambda *_: [{"start": 0, "end": 32000}])
    monkeypatch.setattr(speaker, "embed_windows", lambda *_: pytest.fail("bad timestamps reached inference"))
    with pytest.raises(speaker.DiarizationError, match="past the recording"):
        speaker.diarize_audio(tmp_path / "x.wav", cache_dir=tmp_path)


@pytest.mark.parametrize("duplicate_across_speakers", [False, True])
def test_real_fixture_harness_rejects_duplicate_source_recordings(monkeypatch, tmp_path, duplicate_across_speakers):
    specification = importlib.util.spec_from_file_location("free_speaker_smoke", Path(__file__).with_name("smoke_real_speakers.py"))
    smoke = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(smoke)
    monkeypatch.setattr(smoke, "decode_mono", lambda *_: np.zeros(64000, dtype=np.float32))
    identities = {}
    for identity in ("a", "b", "c"):
        entries = []
        for index in range(3):
            path = tmp_path / f"{identity}-{index}.wav"
            path.write_bytes(f"{identity}-{index}".encode())
            entries.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        identities[identity] = entries
    if duplicate_across_speakers:
        identities["b"][0] = identities["a"][0]
    else:
        identities["a"][1] = identities["a"][0]
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"license": "CC BY4.0", "attribution": "Fixture author", "speakers": identities}))
    with pytest.raises(ValueError, match="distinct audio hash"):
        smoke.prepare_fixtures(manifest, tmp_path / "fixtures")

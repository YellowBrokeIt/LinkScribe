"""Timing regressions replay retained native outputs without model inference."""
from copy import deepcopy
import hashlib
import importlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import enhancements
import library

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs/large-v3-hosted-results-2026-11-28/artifact"
REPORT = json.loads((ARTIFACT / "recognizer-report.json").read_text(encoding="utf-8"))


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    app.jobs.clear(); app.batches.clear()
    yield tmp_path
    app.jobs.clear(); app.batches.clear()


def replay(monkeypatch, path, audio, segments, *, language="en", words=False):
    calls, decodes = [], []
    def decode(filename, sampling_rate):
        decodes.append((filename, sampling_rate))
        return audio
    native = []
    for original in segments:
        item = deepcopy(original)
        if item.get("words") is not None:
            item["words"] = [SimpleNamespace(**word) for word in item["words"]]
        native.append(SimpleNamespace(**item))
    class Engine:
        def transcribe(self, waveform, **options):
            calls.append((waveform, options))
            return iter(native), SimpleNamespace(language=language)
    monkeypatch.setattr(importlib.import_module("faster_whisper.audio"), "decode_audio", decode)
    monkeypatch.setattr(app, "_whisper_model", lambda _: Engine())
    result = app._recognize(path, "auto", "large-v3", word_timestamps=words)
    assert decodes == [(str(path), 16000)]
    assert len(calls) == 1 and calls[0][0] is audio
    return result, calls[0][1]


def record(segments, **extra):
    return {"source": "retained-output-replay", "title": "Timing regression", "language": "en",
            "method": "static_native_output_replay", "segments": segments, **extra}


@pytest.mark.parametrize("case", REPORT["cases"], ids=lambda case: case["id"])
def test_all_retained_large_v3_outputs_keep_text_and_settings_with_only_actual_end_clipped(monkeypatch, tmp_path, case):
    assert hashlib.sha256((ARTIFACT / "recognizer-report.json").read_bytes()).hexdigest() == \
        "26098ab9a14bc328d7c9aea77e43defadbec57d1055f8190976ecd492fc6485f"
    audio = np.load(ARTIFACT / "inputs" / (case["id"] + ".npy"), allow_pickle=False)
    assert len(audio) == case["sample_count"]
    assert hashlib.sha256(audio.tobytes()).hexdigest() == case["pcm_sha256"]
    (segments, language), options = replay(monkeypatch, tmp_path / "retained.wav", audio,
        case["raw_segments"], language=case["detected_language"])
    assert options == case["actual_transcribe_request"]
    expected = deepcopy(case["production_segments"])
    if case["id"] == "fleurs-en_us-validation-0-1548":
        assert expected[0]["end"] == 7.0
        expected[0]["end"] = 6.54
    assert segments == expected and language == case["detected_language"]
    assert [s["text"] for s in segments] == [s["text"] for s in case["production_segments"]]
    assert all(0 <= s["start"] < s["end"] <= len(audio) / 16000 for s in segments)
    exports = app._exports(record(segments))
    assert "export-notes.txt" not in exports
    if case["id"] == "fleurs-en_us-validation-0-1548":
        assert b"00:00:06,540" in exports["transcript.srt"]
        assert b"00:00:06.540" in exports["transcript.vtt"]


@pytest.mark.parametrize("interval", [(0, float("nan")), (0, float("inf")), (-0.1, 1),
                                     (1, 2), (0.5, 0.5), (0.7, 0.6), (True, 2)])
def test_impossible_public_intervals_fail_with_specific_timestamp_error(monkeypatch, tmp_path, interval):
    audio = np.ones(16000, dtype=np.float32)
    with pytest.raises(app.ReadableError, match="timestamps") as error:
        replay(monkeypatch, tmp_path / "synthetic.wav", audio,
               [{"start": interval[0], "end": interval[1], "text": "Retain no fabricated interval"}])
    assert "could not decode" not in str(error.value)


def test_fractional_sample_duration_cannot_round_outward_in_srt_or_vtt(monkeypatch, tmp_path):
    audio = np.ones(104649, dtype=np.float32)
    (segments, _), _ = replay(monkeypatch, tmp_path / "synthetic.wav", audio,
                            [{"start": 6.5, "end": 7.0, "text": "A short final cue"}])
    assert segments == [{"start": 6.5, "end": 6.5405625, "text": "A short final cue"}]
    assert app._subtitle_interval_ms(segments[0]) == (6500, 104649 // 16)
    exports = app._exports(record(segments))
    assert b"00:00:06,500 --> 00:00:06,540" in exports["transcript.srt"]
    assert b"00:00:06.500 --> 00:00:06.540" in exports["transcript.vtt"]
    assert b"06,541" not in exports["transcript.srt"]


def test_valid_short_cue_is_not_extended_to_a_fabricated_hundred_ms():
    segment = {"start": 6.50, "end": 6.54, "text": "Keep all words"}
    assert "00:00:06,500 --> 00:00:06,540" in app._render_subtitles([segment], "srt")


def test_actual_historical_zero_duration_word_uses_whole_segment_fallback(monkeypatch, tmp_path):
    path = ROOT / "docs/asr-official-tail-2026-11-28/alignment-only-results/official_tears_of_steel-report.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "abf6ad93ec75a2a3c95138e3e8c2d9181e2daf52b01edc7a9c8eb5b57a384f17"
    events = json.loads(path.read_text(encoding="utf-8"))["alignment_only_protocol"]["events"]
    native = next(e["segment"] for e in events if e.get("kind") == "asr_segment_created" and
                  any(w["start"] == w["end"] for w in e["segment"].get("words", [])))
    assert native["text"] == " Oh, what have I done?"
    # Synthetic nonzero buffer supplies a valid physical bound; no new ASR occurs.
    (segments, _), _ = replay(monkeypatch, tmp_path / "synthetic.wav", np.ones(44 * 16000, dtype=np.float32),
                             [native], words=True)
    assert segments[0]["text"] == native["text"].strip() and segments[0]["_words"] == []
    labeled, warnings, timed = enhancements._word_speaker_alignment(
        segments, [{"start": 0.0, "end": 44.0, "speaker": "Speaker 1"}])
    assert labeled[0]["text"] == native["text"].strip() and timed == 0
    assert any("text was retained" in warning for warning in warnings)


def test_private_word_end_is_bounded_without_changing_its_start_or_string(monkeypatch, tmp_path):
    native = {"start": 0, "end": 7, "text": "Last word", "words": [
        {"start": 0, "end": 3, "word": " Last"}, {"start": 3, "end": 7, "word": " word"}]}
    (segments, _), _ = replay(monkeypatch, tmp_path / "synthetic.wav", np.ones(104640, dtype=np.float32),
                             [native], words=True)
    assert segments[0]["_words"] == [{"start": 0.0, "end": 3.0, "word": " Last"},
                                      {"start": 3.0, "end": 6.54, "word": " word"}]


def test_unrepresentable_sub_ms_interval_keeps_source_storage_downloads_and_warning(monkeypatch, local):
    native = [{"start": 6.5401, "end": 6.5405, "text": "Every original word"}]
    (segments, _), _ = replay(monkeypatch, local / "synthetic.wav", np.ones(104649, dtype=np.float32), native)
    assert segments == native  # Rounding may not erase the valid native interval.
    job = app._new_job("uploaded:synthetic.wav", "Sub-ms timing")
    translated = [{**segments[0], "text": "Κάθε λέξη"}]
    app._write_exports(job.id, segments, "en", "static_native_output_replay", translations={"el": translated})
    saved = library.get(job.id)
    assert saved["segments"] == native and job.status == "done"
    assert saved["processing_metadata"]["warnings"] and job.warnings
    client = TestClient(app.app)
    for route in [f"/api/jobs/{job.id}/download", f"/api/library/{job.id}/download"]:
        assert client.get(route + "/txt").status_code == 200
        data = client.get(route + "/json")
        assert data.status_code == 200 and data.json()["segments"] == native
        for fmt in ("srt", "vtt", "translation_srt", "translation_vtt"):
            response = client.get(route + "/" + fmt)
            assert response.status_code == 422 and "TXT and JSON remain available" in response.json()["detail"]
        archive = zipfile.ZipFile(io.BytesIO(client.get(route + "/zip").content))
        assert {"transcript.txt", "transcript.json", "translation_el.txt", "translation_el.json", "export-notes.txt"} <= set(archive.namelist())
        assert not any(name.endswith((".srt", ".vtt")) for name in archive.namelist())


def test_mixed_batch_keeps_available_exports_and_explains_missing_subtitles(monkeypatch, local):
    identifiers = ["1" * 32, "2" * 32]
    library.save(identifiers[0], "source-a", "Sub-ms legacy", "en", "saved",
                 [{"start": 0.0001, "end": 0.0005, "text": "Keep source A"}],
                 processing_metadata={"warnings": ["Preserved earlier warning"]})
    library.save(identifiers[1], "source-b", "Normal", "en", "saved",
                 [{"start": 6.50, "end": 6.54, "text": "Keep source B"}])
    stored = {"jobs": [{"id": identifier, "source": "source", "title": "Saved", "status": "done", "error": ""}
                       for identifier in identifiers]}
    monkeypatch.setattr(batch_store, "get", lambda _: stored)
    with zipfile.ZipFile(io.BytesIO(app._batch_archive("3" * 32))) as archive:
        names = set(archive.namelist())
        for prefix in ("01_11111111", "02_22222222"):
            assert {prefix + "/transcript.txt", prefix + "/transcript.json"} <= names
        assert "01_11111111/export-notes.txt" in names
        assert "01_11111111/transcript.srt" not in names and "02_22222222/transcript.srt" in names
        report = json.loads(archive.read("batch-report.json"))
        assert report["failed"] == 0
        assert "Preserved earlier warning" in report["items"][0]["warnings"]
        assert any("too close together" in warning for warning in report["items"][0]["warnings"])

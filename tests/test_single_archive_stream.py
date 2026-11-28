"""Single transcript ZIPs retain current edits, warnings and bounded transport."""
import io
import json
import tempfile
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import library


def members(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.fixture
def site(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    app.jobs.clear()
    app.batches.clear()
    with TestClient(app.app) as client:
        yield client
    app.jobs.clear()
    app.batches.clear()


def test_both_zip_routes_stream_latest_saved_components(site, monkeypatch):
    job = app._new_job("uploaded:clip.wav", "Original")
    segments = [{"start": 0, "end": 2, "text": "Καλημέρα", "speaker": "Speaker 1"}]
    app._write_exports(job.id, segments, "el", "local_audio_ai", translations={
        "en": [{**segments[0], "text": "Good morning"}]},
        highlights=app.select_highlights(segments, source_language="el"))
    original = library.get(job.id)
    assert members((job.workdir / "transcript.zip").read_bytes()) == app._exports(original, include_zip=False)
    tracked = []
    real = tempfile.TemporaryFile

    def track(*args, **kwargs):
        stream = real(*args, **kwargs)
        tracked.append(stream)
        return stream

    monkeypatch.setattr(app.tempfile, "TemporaryFile", track)
    render = app._exports

    def no_inner_zip(record, *, requested=None, include_zip=True):
        assert requested is None and include_zip is False
        return render(record, requested=requested, include_zip=include_zip)

    monkeypatch.setattr(app, "_exports", no_inner_zip)
    for edited in (False, True):
        if edited:
            result = site.put(f"/api/library/{job.id}", json={"title": "Διόρθωση",
                "segments": [{"text": "Καλησπέρα", "speaker": "Speaker 1"}],
                "expected_updated_at": original["updated_at"]})
            assert result.status_code == 200
        expected = render(library.get(job.id), include_zip=False)
        for prefix in (f"/api/jobs/{job.id}/download", f"/api/library/{job.id}/download"):
            response = site.get(prefix + "/zip")
            assert response.status_code == 200
            assert response.headers["content-length"] == str(len(response.content))
            assert response.headers["content-disposition"] == 'attachment; filename="transcript.zip"'
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["content-type"] == "application/zip"
            assert members(response.content) == expected
            assert tracked[-1].closed
            if edited:
                assert "Καλησπέρα" in expected["transcript.txt"].decode()
                assert "translation_en.txt" not in expected and "highlights.md" not in expected
    assert len(tracked) == 4


def test_archive_creation_failure_closes_owned_stream(site, monkeypatch):
    job = app._new_job("uploaded:clip.wav")
    app._write_exports(job.id, [{"start": 0, "end": 1, "text": "Keep"}], "en", "saved")
    seen = []

    def fail(contents, stream):
        seen.append(stream)
        stream.write(b"partial")
        raise OSError("simulated disk error")

    monkeypatch.setattr(app, "_write_transcript_zip", fail)
    for route in (f"/api/jobs/{job.id}/download/zip", f"/api/library/{job.id}/download/zip"):
        with pytest.raises(OSError, match="simulated disk error"):
            site.get(route)
        assert seen[-1].closed and library.get(job.id) is not None


def test_completed_job_compresses_once_and_publishes_warnings_atomically(site, monkeypatch):
    job = app._new_job("uploaded:clip.wav")
    segments = [{"start": 0.0001, "end": 0.0005, "text": "Original"}]
    written = []
    original_zip = app._write_transcript_zip
    original_set = app._set
    updates = []

    def track(contents, stream):
        written.append(set(contents))
        return original_zip(contents, stream)

    def observe(identifier, **changes):
        updates.append(changes)
        return original_set(identifier, **changes)

    monkeypatch.setattr(app, "_write_transcript_zip", track)
    monkeypatch.setattr(app, "_set", observe)
    app._write_exports(job.id, segments, "en", "saved", processing_metadata={"warnings": ["Earlier warning"]})
    assert len(written) == 1
    record = library.get(job.id)
    expected = app._exports(record, include_zip=False)
    assert members((job.workdir / "transcript.zip").read_bytes()) == expected
    assert "export-notes.txt" in expected and "transcript.srt" not in expected
    warnings = record["processing_metadata"]["warnings"]
    assert len(warnings) == 2 and warnings[0] == "Earlier warning"
    assert json.loads(expected["transcript.json"])["processing_metadata"]["warnings"] == warnings
    done = [update for update in updates if update.get("status") == "done"]
    assert len(done) == 1 and done[0]["warnings"] == warnings
    assert site.get(f"/api/jobs/{job.id}").json()["warnings"] == warnings
    assert site.get(f"/api/library/{job.id}/download/srt").status_code == 422
    # Recovery from a record with no warnings must clear stale in-memory values.
    app._complete_job(job.id, {**record, "processing_metadata": {}})
    assert job.warnings == []

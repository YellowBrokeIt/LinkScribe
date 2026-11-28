"""Demand-driven downloads preserve all component bytes and warning semantics."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import library


@pytest.fixture
def saved(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    app.jobs.clear()
    app.batches.clear()
    segments = [
        {"start": 0.0002, "end": 1.2349, "text": "Hello world. Keep the exact wording.", "speaker": "Speaker 1"},
        {"start": 2, "end": 3.99, "text": "The review will happen tomorrow.", "speaker": "Speaker 2"},
    ]
    translated = [{**segments[0], "text": "Γεια σου κόσμε."},
                  {**segments[1], "text": "Ο έλεγχος θα γίνει αύριο."}]
    summary = {"summary": "The review will happen tomorrow.",
               "key_points": ["The review is planned."],
               "chapters": [{"start": 0, "title": "Review"}]}
    highlights = app.select_highlights(segments, source_language="en")
    job = app._new_job("uploaded:fixture.wav", "Export regression")
    app._write_exports(job.id, segments, "en", "saved", translations={"el": translated},
                       summary=summary, processing_metadata={"warnings": ["Earlier warning"]},
                       highlights=highlights)
    yield job, library.get(job.id)
    app.jobs.clear()
    app.batches.clear()


def test_requested_files_equal_full_zip_members(saved):
    _, record = saved
    full = app._exports(record)
    components = {key: value for key, value in full.items() if key != "transcript.zip"}
    assert app._exports(record, include_zip=False) == components
    assert {"transcript.txt", "transcript.json", "transcript.srt", "transcript.vtt",
            "translation_el.txt", "translation_el.json", "translation_el.srt", "translation_el.vtt",
            "summary.md", "summary.json", "highlights.md", "highlights.json"} == set(components)
    for key, value in components.items():
        assert app._exports(record, requested=key) == {key: value}
    with zipfile.ZipFile(io.BytesIO(app._exports(record, requested="transcript.zip")["transcript.zip"])) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == components


def test_nonzip_api_never_builds_archive_or_unrequested_subtitles(saved, monkeypatch):
    job, record = saved
    components = app._exports(record, include_zip=False)
    def forbidden(*args, **kwargs):
        pytest.fail("Unrequested archive or subtitle rendering")
    client = TestClient(app.app)
    with monkeypatch.context() as patch:
        patch.setattr(app.zipfile, "ZipFile", forbidden)
        patch.setattr(app, "_render_subtitles", forbidden)
        for prefix in (f"/api/jobs/{job.id}/download", f"/api/library/{job.id}/download"):
            for route, key in (("txt", "transcript.txt"), ("json", "transcript.json"),
                               ("translation_txt", "translation_el.txt"), ("translation_json", "translation_el.json"),
                               ("summary_md", "summary.md"), ("summary_json", "summary.json"),
                               ("highlights_md", "highlights.md"), ("highlights_json", "highlights.json")):
                response = client.get(f"{prefix}/{route}")
                assert response.status_code == 200
                assert response.content == components[key]
    calls = []
    render = app._render_subtitles
    def counted(segments, fmt):
        calls.append(fmt)
        return render(segments, fmt)
    with monkeypatch.context() as patch:
        patch.setattr(app.zipfile, "ZipFile", forbidden)
        patch.setattr(app, "_render_subtitles", counted)
        for prefix in (f"/api/jobs/{job.id}/download", f"/api/library/{job.id}/download"):
            for route, key in (("srt", "transcript.srt"), ("vtt", "transcript.vtt"),
                               ("translation_srt", "translation_el.srt"), ("translation_vtt", "translation_el.vtt")):
                calls.clear()
                response = client.get(f"{prefix}/{route}")
                assert response.status_code == 200 and response.content == components[key]
                assert calls == [key.rsplit(".", 1)[1]]


def test_batch_creates_only_outer_zip_preserves_warnings(saved, monkeypatch):
    job, record = saved
    components = app._exports(record, include_zip=False)
    monkeypatch.setattr(batch_store, "get", lambda _: {"jobs": [
        {"id": job.id, "source": record["source"], "title": record["title"], "status": "done", "error": ""}
    ]})
    real_zip = zipfile.ZipFile
    opened = []
    def counted(*args, **kwargs):
        opened.append(True)
        return real_zip(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(app.zipfile, "ZipFile", counted)
        payload = app._batch_archive("3" * 32)
    assert len(opened) == 1
    with real_zip(io.BytesIO(payload)) as archive:
        prefix = "01_" + job.id[:8] + "/"
        assert {name[len(prefix):]: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix)} == components
        report = json.loads(archive.read("batch-report.json"))
        assert report["failed"] == 0
        assert report["items"][0]["warnings"] == ["Earlier warning"]

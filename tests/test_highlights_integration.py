"""Real source selection through jobs, durable storage, edits and backup boundaries."""
from copy import deepcopy
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import library
import library_backup
from source_highlights import select_highlights, validate_highlights


SEGMENTS = [
    {"start": 0.0, "end": 4.0, "text": "We considered spending 120 euros on Friday."},
    {"start": 4.0, "end": 8.0, "text": "Correction: the approved limit is 90 euros, and nothing has been paid."},
    {"start": 8.0, "end": 12.0, "text": "Proceed only if Maria approves. Otherwise cancel the purchase."},
]
URL = "https://www.youtube.com/watch?v=QaSuccess01"


@pytest.fixture
def site(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app.pool, "submit", lambda func, *args: func(*args))
    monkeypatch.setattr(app, "_captions", lambda *_args: (deepcopy(SEGMENTS), "en"))
    app.jobs.clear()
    app.batches.clear()
    with TestClient(app.app) as client:
        yield client
    app.jobs.clear()
    app.batches.clear()


def create(site):
    response = site.post("/api/link", data={"url": URL, "mode": "captions", "consent": "true", "highlights": "true"})
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    job = site.get(f"/api/jobs/{identifier}").json()
    assert job["status"] == "done", job
    return identifier


def edit(site, identifier, text="The corrected saved amount is 70 euros; payment is still pending."):
    segments = deepcopy(SEGMENTS)
    segments[0]["text"] = text
    response = site.put(f"/api/library/{identifier}", json={"title": "Edited transcript", "segments": segments})
    assert response.status_code == 200, response.text


def test_link_highlights_use_actual_source_and_all_exports_without_ollama(site, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Source highlights must not require an LLM")
    monkeypatch.setattr(app, "summarize_segments", forbidden)
    monkeypatch.setattr(app, "translate_segments", forbidden)
    identifier = create(site)
    record = site.get(f"/api/library/{identifier}").json()
    validate_highlights(record["highlights"], record["segments"])
    assert record["segments"] == SEGMENTS
    assert record["summary"] is None and record["translations"] == {}
    assert site.get(f"/api/jobs/{identifier}").json()["extras"]["highlights"] is True
    for root in (f"/api/library/{identifier}", f"/api/jobs/{identifier}"):
        actual = site.get(root + "/download/highlights_json")
        assert actual.status_code == 200 and actual.json() == record["highlights"]
        markdown = site.get(root + "/download/highlights_md").text
        assert "# Source highlights" in markdown and "nothing has been paid" in markdown
        with zipfile.ZipFile(io.BytesIO(site.get(root + "/download/zip").content)) as bundle:
            assert {"highlights.md", "highlights.json", "transcript.txt"} <= set(bundle.namelist())
            assert json.loads(bundle.read("highlights.json")) == record["highlights"]
        assert site.get(root + "/download/json").json()["highlights"] == record["highlights"]


def test_upload_highlights_survive_optional_summary_failure(site, monkeypatch):
    monkeypatch.setattr(app, "_check_uploaded_duration", lambda *_: None)
    monkeypatch.setattr(app, "_recognize", lambda *_args, **_kwargs: app.RecognitionResult(deepcopy(SEGMENTS), "en"))
    def fail_summary(*args, **kwargs):
        raise app.EnhancementError("Controlled unavailable model")
    monkeypatch.setattr(app, "summarize_segments", fail_summary)
    response = site.post("/api/upload", files={"file": ("owned.wav", b"controlled media fixture", "audio/wav")},
                         data={"consent": "true", "highlights": "true", "summary": "true"})
    identifier = response.json()["id"]
    job = site.get(f"/api/jobs/{identifier}").json()
    assert job["status"] == "done" and job["extras"]["highlights"] and not job["extras"]["summary"]
    assert "Controlled unavailable model" in " ".join(job["warnings"])
    assert not list(app.jobs[identifier].workdir.glob("input.*"))
    validate_highlights(library.get(identifier)["highlights"], SEGMENTS)


def test_selection_failure_preserves_original_transcript(site, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("Controlled source selection failure")
    monkeypatch.setattr(app, "select_highlights", fail)
    identifier = create(site)
    job = site.get(f"/api/jobs/{identifier}").json()
    assert not job["extras"]["highlights"] and "Controlled source selection failure" in " ".join(job["warnings"])
    assert library.get(identifier)["segments"] == SEGMENTS
    assert site.get(f"/api/library/{identifier}/download/txt").status_code == 200


def test_edit_invalidates_highlights_and_regeneration_uses_new_source(site):
    identifier = create(site)
    before = library.get(identifier)["highlights"]
    edit(site, identifier)
    assert library.get(identifier)["highlights"] is None
    assert site.get(f"/api/jobs/{identifier}").json()["extras"]["highlights"] is False
    for root in (f"/api/library/{identifier}", f"/api/jobs/{identifier}"):
        assert site.get(root + "/download/highlights_json").status_code == 404
    refreshed = site.post(f"/api/library/{identifier}/highlights")
    assert refreshed.status_code == 200, refreshed.text
    result = refreshed.json()
    validate_highlights(result["highlights"], result["segments"])
    assert result["highlights"]["source_sha256"] != before["source_sha256"]
    assert "70 euros" in result["highlights"]["excerpts"][0]["text"]
    assert site.get(f"/api/jobs/{identifier}").json()["extras"]["highlights"]


def test_concurrent_edit_cannot_save_stale_highlights(site, monkeypatch):
    identifier = create(site)
    def select_then_edit(segments, **kwargs):
        value = select_highlights(segments, **kwargs)
        changed = deepcopy(segments)
        changed[0]["text"] = "Concurrent correction: cancel everything."
        library.update(identifier, "Concurrent edit", changed)
        return value
    monkeypatch.setattr(app, "select_highlights", select_then_edit)
    response = site.post(f"/api/library/{identifier}/highlights")
    assert response.status_code == 409, response.text
    saved = library.get(identifier)
    assert saved["title"] == "Concurrent edit" and saved["highlights"] is None


def test_highlights_survive_database_reopen_and_backup_restore(site):
    identifier = create(site)
    original = library.get(identifier)
    backup, count = library_backup.make_backup()
    assert count == 1
    with zipfile.ZipFile(io.BytesIO(backup)) as bundle:
        assert json.loads(bundle.read("manifest.json"))["version"] == 2
    app.jobs.clear()
    assert site.get(f"/api/library/{identifier}/download/highlights_json").json() == original["highlights"]
    assert library.delete(identifier)
    assert library_backup.restore_backup(backup)["imported"] == 1
    assert library.get(identifier) == original


def backup(records, version=2):
    payload = json.dumps({"format": library_backup.FORMAT, "version": version, "records": records}).encode()
    manifest = {"format": library_backup.FORMAT, "version": version, "records": len(records), "sha256": hashlib.sha256(payload).hexdigest()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("transcripts.json", payload)
        bundle.writestr("manifest.json", json.dumps(manifest))
    return buffer.getvalue()


@pytest.mark.parametrize("field,value", [("text", "Fabricated replacement"), ("start", 999.0), ("segment_indices", [999])])
def test_valid_zip_checksum_cannot_import_fabricated_excerpts(site, field, value):
    identifier = create(site)
    first = library.get(identifier)
    first["id"] = "a" * 32
    bad = deepcopy(first)
    bad["id"] = "b" * 32
    bad["highlights"]["excerpts"][0][field] = value
    with pytest.raises(library_backup.BackupError):
        library_backup.restore_backup(backup([first, bad]))
    assert library.get("a" * 32) is None and library.get("b" * 32) is None
    assert library.get(identifier)["segments"] == SEGMENTS


def test_legacy_backup_still_imports_and_old_format_cannot_hide_new_highlights(site):
    identifier = create(site)
    old = library.get(identifier)
    old["id"] = "c" * 32
    with pytest.raises(library_backup.BackupError, match="version 2"):
        library_backup.restore_backup(backup([old], version=1))
    old.pop("highlights")
    assert library_backup.restore_backup(backup([old], version=1))["imported"] == 1
    assert library.get("c" * 32)["highlights"] is None


@pytest.mark.parametrize("damaged", ["not json", '{"excerpts":[]}'])
def test_damaged_optional_highlights_do_not_block_original_library_record(site, damaged):
    identifier = create(site)
    with library._connect() as connection:
        connection.execute("UPDATE transcripts SET highlights=? WHERE id=?", (damaged, identifier))
    record = site.get(f"/api/library/{identifier}").json()
    assert record["highlights"] is None and record["segments"] == SEGMENTS
    assert site.get(f"/api/library/{identifier}/download/txt").status_code == 200
    assert site.get(f"/api/library/{identifier}/download/highlights_json").status_code == 404


def test_recovered_batch_preserves_selected_highlights_option(site, monkeypatch):
    queued = []
    monkeypatch.setattr(app.pool, "submit", lambda *args: queued.append(args))
    response = site.post("/api/batch", data={"urls": URL, "mode": "captions", "consent": "true", "highlights": "true"})
    batch_id = response.json()["id"]
    assert batch_store.get(batch_id)["options"]["highlights"] is True
    app.jobs.clear()
    app.batches.clear()
    monkeypatch.setattr(app.pool, "submit", lambda callback, *args: callback(*args))
    app._restore_pending_batches()
    result = batch_store.get(batch_id)
    assert result["status"] == "done" and result["jobs"][0]["status"] == "done"
    record = library.get(result["jobs"][0]["id"])
    validate_highlights(record["highlights"], record["segments"])
    with zipfile.ZipFile(io.BytesIO(app._batch_archive(batch_id))) as bundle:
        assert any(name.endswith("/highlights.json") for name in bundle.namelist())


def test_highlights_api_respects_origin_guard_and_missing_records(site):
    identifier = create(site)
    assert site.post(f"/api/library/{identifier}/highlights", headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert site.post(f"/api/library/{'0' * 32}/highlights").status_code == 404

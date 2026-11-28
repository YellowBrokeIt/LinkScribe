"""Deletion removes live output caches as well as the durable library row."""
import pytest
from fastapi.testclient import TestClient

import app
import library

SEGMENTS = [{"start": 0, "end": 1, "text": "Ιδιωτική δοκιμή"}]


@pytest.fixture
def completed(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    app.jobs.clear()
    app.batches.clear()
    monkeypatch.setattr(app.pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(app, "_captions", lambda *args: (SEGMENTS, "el"))
    with TestClient(app.app) as client:
        r = client.post("/api/link", data={"url": "https://youtu.be/dQw4w9WgXcQ",
                         "mode": "captions", "consent": "true"})
        assert r.status_code == 200
        identifier = r.json()["id"]
        assert "Ιδιωτική" in client.get(f"/api/jobs/{identifier}").json()["preview"]
        assert (app.jobs[identifier].workdir / "transcript.zip").is_file()
        yield client, identifier, app.jobs[identifier].workdir
    app.jobs.clear()
    app.batches.clear()


def test_deleted_job_no_longer_exposes_preview_or_files(completed):
    client, identifier, workdir = completed
    assert client.delete(f"/api/library/{identifier}").status_code == 200
    detail = client.get(f"/api/jobs/{identifier}").json()
    assert detail["status"] == "error"
    assert not detail["preview"] and not detail["library_id"]
    assert not detail["extras"] and not detail["warnings"] and detail["segments"] == 0
    assert not workdir.exists()
    assert client.get(f"/api/jobs/{identifier}/download/txt").status_code == 404
    assert client.get(f"/api/library/{identifier}").status_code == 404


def test_delete_after_cache_loss_removes_old_disk_exports(completed):
    client, identifier, workdir = completed
    app.jobs.clear()
    unrelated = workdir.parent / "keep-me"
    unrelated.mkdir()
    (unrelated / "transcript.txt").write_text("unrelated")
    assert client.delete(f"/api/library/{identifier}").status_code == 200
    assert not workdir.exists()
    assert (unrelated / "transcript.txt").read_text() == "unrelated"


def test_failed_filesystem_cleanup_is_reported(completed, monkeypatch):
    client, identifier, workdir = completed
    def refuse(*args, **kwargs):
        raise PermissionError("test denial")
    monkeypatch.setattr(app.shutil, "rmtree", refuse)
    response = client.delete(f"/api/library/{identifier}")
    assert response.status_code == 200
    assert "cleanup_warning" in response.json()
    assert library.get(identifier) is None
    assert not client.get(f"/api/jobs/{identifier}").json()["preview"]
    assert workdir.exists()

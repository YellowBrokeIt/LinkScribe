"""Exercise restart boundaries with a real journal, library and ASGI lifespan."""
from __future__ import annotations

import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import library

FIRST = "https://vimeo.com/12345671"
SECOND = "https://vimeo.com/12345672"
SEGMENTS = [{"start": 0.25, "end": 1.5, "text": "Preserve this saved transcript."}]


@pytest.fixture
def restart_site(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    app.jobs.clear()
    app.batches.clear()
    monkeypatch.setattr(app.pool, "submit", lambda *args: None)
    yield TestClient(app.app)
    app.jobs.clear()
    app.batches.clear()


def queued_batch(client):
    response = client.post("/api/batch", data={
        "urls": FIRST + "\n" + SECOND, "consent": "true", "mode": "audio",
    })
    assert response.status_code == 200
    batch_id = response.json()["id"]
    first, second = batch_store.get(batch_id)["jobs"]
    return batch_id, first["id"], second["id"]


def save_first(identifier):
    library.save(identifier, FIRST, "Saved before restart", "en", "local_audio_ai", SEGMENTS)


def restart(monkeypatch):
    processed = []

    def process(job_id, source, *args):
        processed.append(source.url)
        app._write_exports(job_id, SEGMENTS, "en", "local_audio_ai")

    app.jobs.clear()
    app.batches.clear()
    monkeypatch.setattr(app, "_process_link", process)
    monkeypatch.setattr(app.pool, "submit", lambda fn, *args: fn(*args))
    return processed


@pytest.mark.parametrize("journal_state", ["done", "working"])
def test_restart_preserves_deliberate_deletion_and_continues_remaining_items(restart_site, monkeypatch, journal_state):
    batch_id, first, second = queued_batch(restart_site)
    save_first(first)
    batch_store.mark_item(first, journal_state, library_id=first)
    assert restart_site.delete(f"/api/library/{first}").status_code == 200

    processed = restart(monkeypatch)
    with TestClient(app.app) as client:
        status = client.get(f"/api/batches/{batch_id}").json()
        assert processed == [SECOND], "Restart must not recreate an intentionally deleted transcript"
        assert library.get(first) is None
        assert library.get(second) is not None
        assert status["status"] == "done" and status["completed"] == 2
        assert status["failed"] == 1
        assert "removed" in status["jobs"][0]["error"].lower()
        with zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{batch_id}/download").content)) as archive:
            report = json.loads(archive.read("batch-report.json"))
            assert report["failed"] == 1
            assert sum(name.endswith("/transcript.txt") for name in archive.namelist()) == 1


@pytest.mark.parametrize("terminal_state", ["saved_before_ack", "error"])
def test_recovered_terminal_jobs_remove_orphan_media_and_expire(restart_site, monkeypatch, terminal_state):
    batch_id, first, _second = queued_batch(restart_site)
    workdir = app.jobs[first].workdir
    for name in ("audio.webm", "audio.webm.part", "input.wav"):
        (workdir / name).write_bytes(b"leftover private audio from interrupted process")
    if terminal_state == "saved_before_ack":
        save_first(first)
        batch_store.mark_item(first, "working")
    else:
        batch_store.mark_item(first, "error", error="Source refused access")

    processed = restart(monkeypatch)
    with TestClient(app.app) as client:
        assert processed == [SECOND]
        recovered = app.jobs[first]
        assert recovered.finished_at > 0, "Recovered jobs must enter normal expiry handling"
        assert not list(workdir.glob("audio.*"))
        assert not list(workdir.glob("input.*"))
        if terminal_state == "saved_before_ack":
            detail = client.get(f"/api/jobs/{first}").json()
            assert detail["segments"] == 1 and detail["language"] == "en"
            assert "Preserve this saved transcript" in detail["preview"]
            assert client.get(f"/api/jobs/{first}/download/txt").status_code == 200
        else:
            assert recovered.error == "Source refused access"
        assert client.get(f"/api/batches/{batch_id}").json()["status"] == "done"
        recovered.finished_at = time.time() - app.JOB_TTL - 1
        app._cleanup_expired()
        assert first not in app.jobs and not workdir.exists()
        # Temporary job cleanup must not delete a successfully recovered transcript.
        assert (library.get(first) is not None) == (terminal_state == "saved_before_ack")

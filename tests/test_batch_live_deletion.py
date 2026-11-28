"""A deliberate library removal must survive a late worker acknowledgement."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import library

FIRST = "https://vimeo.com/12345671"
SECOND = "https://vimeo.com/12345672"
SEGMENTS = [{"start": 0, "end": 1, "text": "Καλημέρα"}]


@pytest.fixture
def queued(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    app.jobs.clear()
    app.batches.clear()
    work = []
    monkeypatch.setattr(app.pool, "submit", lambda fn, *args: work.append((fn, args)))
    with TestClient(app.app) as client:
        response = client.post("/api/batch", data={"urls": FIRST + "\n" + SECOND,
            "consent": "true", "mode": "audio"})
        assert response.status_code == 200
        bid = response.json()["id"]
        first, second = [x["id"] for x in batch_store.get(bid)["jobs"]]
        yield client, bid, first, second, work
    app.jobs.clear()
    app.batches.clear()


def assert_removed(client, bid, removed, kept):
    status = client.get(f"/api/batches/{bid}").json()
    assert status["status"] == "done" and status["completed"] == 2 and status["failed"] == 1
    item = next(x for x in status["jobs"] if x["id"] == removed)
    assert item["status"] == "error" and not item["library_id"]
    assert "removed" in item["error"].lower() and item["warnings"] == []
    assert library.get(removed) is None and library.get(kept) is not None
    assert client.get("/api/batches").json()["items"][0]["failed"] == 1
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{bid}/download").content)) as archive:
        report = json.loads(archive.read("batch-report.json"))
        assert report["failed"] == 1
        assert len([x for x in archive.namelist() if x.endswith("/transcript.txt")]) == 1
    app.jobs.clear()
    app.batches.clear()
    assert client.get(f"/api/batches/{bid}").json()["failed"] == 1


@pytest.mark.parametrize("when", ["before_ack", "after_batch"])
def test_live_deletion_matches_history_archive_and_restart(queued, monkeypatch, when):
    client, bid, first, second, work = queued
    def process(job_id, source, *args):
        app._write_exports(job_id, SEGMENTS, "el", "local_audio_ai",
                           processing_metadata={"warnings": ["Review this label."]})
        if job_id == first and when == "before_ack":
            assert client.delete(f"/api/library/{first}").status_code == 200
    monkeypatch.setattr(app, "_process_link", process)
    fn, args = work.pop()
    fn(*args)
    if when == "after_batch":
        assert client.delete(f"/api/library/{first}").status_code == 200
    assert_removed(client, bid, first, second)


def test_stale_recovery_snapshot_cannot_recreate_removed_later_item(queued, monkeypatch):
    client, bid, first, second, work = queued
    # A prior run saved the later item before its acknowledgement; the batch
    # worker has already taken its journal snapshot when the first item runs.
    library.save(second, SECOND, "Earlier saved", "el", "local_audio_ai", SEGMENTS)
    batch_store.mark_item(second, "working")
    seen = []
    def process(job_id, source, *args):
        seen.append(job_id)
        if job_id == first:
            assert library.update(second, "Edited before removal", SEGMENTS)
            assert client.delete(f"/api/library/{second}").status_code == 200
        app._write_exports(job_id, SEGMENTS, "el", "local_audio_ai")
    monkeypatch.setattr(app, "_process_link", process)
    fn, args = work.pop()
    fn(*args)
    assert seen == [first]
    assert batch_store.get(bid)["jobs"][1]["title"] == "Edited before removal"
    assert_removed(client, bid, second, first)

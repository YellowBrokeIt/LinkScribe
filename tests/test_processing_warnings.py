"""Persisted warnings must remain visible without changing transcript success."""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

import app
import library


def forbidden(*_args, **_kwargs):
    raise AssertionError("This persistence check must not perform inference or acquisition")


@pytest.fixture
def twenty_item_batch(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app.pool, "submit", lambda fn, *args: fn(*args))
    app.jobs.clear(); app.batches.clear()
    calls = []

    def captions(identifier, _language):
        calls.append(identifier)
        index = int(identifier[-3:])
        if index == 2:
            raise app.ReadableError("Controlled unavailable source")
        start, end = (0.0001, 0.0005) if index == 3 else (0.0, 2.0)
        return [{"start": start, "end": end, "text": f"Original source {index:03d}. Keep these words."}], "en"

    def translate(segments, _target, **_kwargs):
        if "source 001" in segments[0]["text"]:
            raise app.EnhancementError("Controlled translation failure; original transcript retained.")
        return [{**segment, "text": "Ελεγχόμενο δοκιμαστικό κείμενο."} for segment in segments]

    monkeypatch.setattr(app, "_captions", captions)
    monkeypatch.setattr(app, "translate_segments", translate)
    monkeypatch.setattr(app, "_download_source_audio", forbidden)
    monkeypatch.setattr(app, "_recognize", forbidden)
    monkeypatch.setattr(app, "_whisper_model", forbidden)
    with TestClient(app.app) as client:
        response = client.post("/api/batch", data={
            "urls": "\n".join(f"https://www.youtube.com/watch?v=WarnCase{i:03d}" for i in range(20)),
            "consent": "true", "mode": "captions", "target_language": "el",
        })
        assert response.status_code == 200, response.text
        batch_id = response.json()["id"]
        initial = client.get(f"/api/batches/{batch_id}").json()
        assert initial["status"] == "done"
        assert (initial["total"], initial["completed"], initial["failed"], initial["with_warnings"]) == (20, 20, 1, 2)
        assert len(calls) == 20
        assert initial["jobs"][1]["status"] == "done"
        assert "Translation:" in initial["jobs"][1]["warnings"][0]
        assert any("too close together" in w for w in initial["jobs"][3]["warnings"])
        assert initial["jobs"][2]["status"] == "error"
        original = {}
        for index, item in enumerate(initial["jobs"]):
            if item["status"] != "done":
                continue
            record = client.get(f"/api/library/{item['id']}").json()
            assert record["segments"][0]["text"] == f"Original source {index:03d}. Keep these words."
            original[item["id"]] = record
        assert original[initial["jobs"][1]["id"]]["translations"] == {}
        yield client, batch_id, initial, original, calls
    app.jobs.clear(); app.batches.clear()


@pytest.mark.parametrize("transition", ["expired_children", "new_lifespan"])
def test_twenty_item_batch_warnings_survive_expiry_and_restart(twenty_item_batch, monkeypatch, transition):
    client, batch_id, initial, original, calls = twenty_item_batch
    if transition == "expired_children":
        for job in app.jobs.values():
            job.finished_at = time.time() - app.JOB_TTL - 1
        app.batches[batch_id].finished_at = time.time() - app.JOB_TTL - 1
        app._cleanup_expired()
    else:
        app.jobs.clear(); app.batches.clear()
    assert not app.jobs and not app.batches
    monkeypatch.setattr(app.pool, "submit", forbidden)
    with TestClient(app.app) as reopened:
        restored = reopened.get(f"/api/batches/{batch_id}").json()
        assert (restored["status"], restored["completed"], restored["failed"], restored["with_warnings"]) == ("done", 20, 1, 2)
        assert [item["warnings"] for item in restored["jobs"]] == [item["warnings"] for item in initial["jobs"]]
        assert reopened.get("/api/batches").json()["items"][0]["with_warnings"] == 2
        for identifier, record in original.items():
            assert reopened.get(f"/api/library/{identifier}").json() == record
        with zipfile.ZipFile(io.BytesIO(reopened.get(f"/api/batches/{batch_id}/download").content)) as archive:
            report = json.loads(archive.read("batch-report.json"))
            assert report["failed"] == 1
            assert sum(name.endswith("/transcript.txt") for name in archive.namelist()) == 19
            assert sum(name.endswith("/transcript.json") for name in archive.namelist()) == 19
            assert sum(bool(item["warnings"]) for item in report["items"]) == 2
        assert len(calls) == 20, "Reading saved warnings must not repeat source work"


def test_fresh_process_reads_saved_warnings_without_rerunning_jobs(twenty_item_batch):
    _client, batch_id, initial, _original, _calls = twenty_item_batch
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve()), "--read-saved", str(library.DB_FILE), batch_id,
    ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    saved = json.loads(result.stdout)
    assert saved["runtime_jobs"] == 0 and saved["runtime_batches"] == 0
    assert saved["detail"]["with_warnings"] == 2
    assert [item["warnings"] for item in saved["detail"]["jobs"]] == [item["warnings"] for item in initial["jobs"]]
    assert saved["history"]["items"][0]["with_warnings"] == 2


def test_warning_polling_does_not_load_transcripts_or_build_exports(twenty_item_batch, monkeypatch):
    client, batch_id, _initial, _original, _calls = twenty_item_batch
    app.jobs.clear(); app.batches.clear()
    monkeypatch.setattr(library, "get", forbidden)
    monkeypatch.setattr(app, "_exports", forbidden)
    assert client.get(f"/api/batches/{batch_id}").json()["with_warnings"] == 2
    assert client.get("/api/batches").json()["items"][0]["with_warnings"] == 2


if __name__ == "__main__":
    assert len(sys.argv) == 4 and sys.argv[1] == "--read-saved"
    library.DB_FILE = Path(sys.argv[2])
    app.DATA_DIR = library.DB_FILE.parent / "fresh-process-jobs"
    app.pool.submit = forbidden
    app._captions = app._download_source_audio = app._recognize = forbidden
    app.translate_segments = app.summarize_segments = forbidden
    with TestClient(app.app) as client:
        print(json.dumps({"detail": client.get(f"/api/batches/{sys.argv[3]}").json(),
                          "history": client.get("/api/batches").json(),
                          "runtime_jobs": len(app.jobs), "runtime_batches": len(app.batches)}))

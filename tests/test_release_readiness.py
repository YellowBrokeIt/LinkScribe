"""Release-readiness regressions for optional-model errors and batch exports."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as module
import library

VIMEO_OK = "https://vimeo.com/12345678"
VIMEO_FAIL = "https://vimeo.com/12345679"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(module.pool, "submit", lambda callback, *args: callback(*args))
    module.jobs.clear()
    module.batches.clear()
    yield TestClient(module.app)
    module.jobs.clear()
    module.batches.clear()


def fake_audio(job_id, source):
    if source.video_id == "12345679":
        raise module.ReadableError("Source unavailable")
    file = module.jobs[job_id].workdir / "audio.mp3"
    file.write_bytes(b"synthetic")
    return file, "Example video"


def fake_recognize(path: Path, language: str, model: str, **_kwargs):
    return module.RecognitionResult([{"start": 0.0, "end": 1.5, "text": "This speech should be preserved."}], "en")


def test_unexpected_optional_model_errors_keep_transcript(client, monkeypatch):
    monkeypatch.setattr(module, "_download_source_audio", fake_audio)
    monkeypatch.setattr(module, "_recognize", fake_recognize)

    def fail(*args, **kwargs):
        raise RuntimeError("broken optional model")

    for function in ("assign_speakers", "translate_segments", "summarize_segments"):
        monkeypatch.setattr(module, function, fail)

    response = client.post("/api/link", data={"url": VIMEO_OK, "mode": "audio", "consent": "true",
                                              "speakers": "true", "target_language": "el", "summary": "true"})
    assert response.status_code == 200
    job_id = response.json()["id"]
    result = client.get(f"/api/jobs/{job_id}").json()
    assert result["status"] == "done"
    assert len(result["warnings"]) == 3
    assert all("original transcript retained" in warning for warning in result["warnings"])
    assert client.get(f"/api/library/{job_id}").json()["segments"][0]["text"] == "This speech should be preserved."
    assert "speech should be preserved" in client.get(f"/api/jobs/{job_id}/download/txt").text
    assert client.get(f"/api/jobs/{job_id}/download/summary_md").status_code == 404
    assert not (module.jobs[job_id].workdir / "audio.mp3").exists()


def test_batch_archive_documents_failures(client, monkeypatch):
    monkeypatch.setattr(module, "_download_source_audio", fake_audio)
    monkeypatch.setattr(module, "_recognize", fake_recognize)
    response = client.post("/api/batch", data={"urls": VIMEO_OK + "\n" + VIMEO_FAIL,
                                               "mode": "audio", "consent": "true"})
    assert response.status_code == 200
    batch_id = response.json()["id"]
    result = client.get(f"/api/batches/{batch_id}").json()
    assert result["status"] == "done" and result["failed"] == 1
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{batch_id}/download").content))
    assert "batch-report.json" in archive.namelist()
    report = json.loads(archive.read("batch-report.json"))
    assert report["total"] == 2 and report["completed"] == 2 and report["failed"] == 1
    assert [entry["status"] for entry in report["items"]] == ["done", "error"]
    assert report["items"][1]["error"] == "Source unavailable"
    assert sum(name.endswith("transcript.txt") for name in archive.namelist()) == 1


def test_all_failed_batch_still_includes_report(client, monkeypatch):
    monkeypatch.setattr(module, "_download_source_audio", fake_audio)
    response = client.post("/api/batch", data={"urls": VIMEO_FAIL, "mode": "audio", "consent": "true"})
    assert response.status_code == 200
    batch_id = response.json()["id"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{batch_id}/download").content))
    assert archive.namelist() == ["batch-report.json"]
    report = json.loads(archive.read("batch-report.json"))
    assert report["failed"] == 1 and report["items"][0]["library_id"] is None

def test_batch_download_is_lazy_and_reflects_current_edits(client, monkeypatch):
    monkeypatch.setattr(module, "_download_source_audio", fake_audio)
    monkeypatch.setattr(module, "_recognize", fake_recognize)
    original = module._write_batch_archive
    def forbidden(*args):
        pytest.fail("Batch completion must not generate an unused archive")
    with monkeypatch.context() as patch:
        patch.setattr(module, "_write_batch_archive", forbidden)
        response = client.post("/api/batch", data={"urls": VIMEO_OK + "\n" + VIMEO_FAIL,
                                                   "mode": "audio", "consent": "true"})
        assert response.status_code == 200
        batch_id = response.json()["id"]
        result = client.get(f"/api/batches/{batch_id}").json()
        assert result["status"] == "done" and result["failed"] == 1
        assert not (module.batches[batch_id].workdir / "batch.zip").exists()
    item_id = result["jobs"][0]["library_id"]
    changed = client.put(f"/api/library/{item_id}", json={
        "title": "Διορθωμένο", "segments": [{"text": "Νέο κείμενο."}]})
    assert changed.status_code == 200
    created = []
    real_temp = module.tempfile.TemporaryFile
    def track(**kwargs):
        handle = real_temp(**kwargs)
        created.append(handle)
        return handle
    with monkeypatch.context() as patch:
        patch.setattr(module.tempfile, "TemporaryFile", track)
        downloaded = client.get(f"/api/batches/{batch_id}/download")
    assert downloaded.status_code == 200
    assert int(downloaded.headers["content-length"]) == len(downloaded.content)
    assert len(created) == 1 and created[0].closed
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert archive.testzip() is None
        assert "Νέο κείμενο." in archive.read(f"01_{item_id[:8]}/transcript.txt").decode()
        report = json.loads(archive.read("batch-report.json"))
        assert report["items"][0]["title"] == "Διορθωμένο"
        assert report["items"][1]["error"] == "Source unavailable"
    assert module._write_batch_archive is original


def test_batch_archive_closes_on_generation_failure(client, monkeypatch):
    monkeypatch.setattr(module, "_download_source_audio", fake_audio)
    response = client.post("/api/batch", data={"urls": VIMEO_FAIL, "mode": "audio", "consent": "true"})
    assert response.status_code == 200
    handle = module.tempfile.TemporaryFile(mode="w+b")
    monkeypatch.setattr(module.tempfile, "TemporaryFile", lambda **kwargs: handle)
    def fail(*args):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(module, "_write_batch_archive", fail)
    with pytest.raises(OSError, match="simulated disk failure"):
        module.batch_download(response.json()["id"])
    assert handle.closed


@pytest.mark.parametrize("fail_send", [False, True])
def test_batch_archive_response_owns_file_and_bounds_chunks(fail_send):
    import asyncio
    import os

    payload = os.urandom(160000)
    handle = module.tempfile.TemporaryFile(mode="w+b")
    handle.write(payload)
    response = module._BatchArchiveResponse(handle, "b" * 32)
    chunks = []
    async def send(message):
        if message["type"] == "http.response.body":
            if fail_send:
                raise RuntimeError("simulated send failure")
            chunks.append(message["body"])
    async def receive():
        return {"type": "http.disconnect"}
    scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
    if fail_send:
        with pytest.raises(RuntimeError, match="simulated send failure"):
            asyncio.run(response(scope, receive, send))
    else:
        asyncio.run(response(scope, receive, send))
        assert b"".join(chunks) == payload
        assert max(map(len, chunks)) <= 65536
    assert handle.closed

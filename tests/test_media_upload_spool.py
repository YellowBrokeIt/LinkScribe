"""Real multipart upload transport tests, without model inference."""
import io
import tempfile
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.testclient import TestClient

import app


@pytest.fixture(autouse=True)
def isolated_jobs(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    monkeypatch.setattr(app, "jobs", {})
    monkeypatch.setattr(app, "batches", {})


def site():
    application = FastAPI()
    application.post("/api/upload")(app.submit_upload)
    return application


def post(client, payload, filename="clip.wav", **kwargs):
    data = kwargs.pop("data", {"consent": "true"})
    return client.post("/api/upload", data=data,
                       files={"file": (filename, payload, "audio/wav")}, **kwargs)


def test_real_multipart_copy_is_off_event_loop_and_preserves_bytes(monkeypatch):
    application = site()
    observed = {}
    payload = bytes(range(256)) * 8192

    @application.middleware("http")
    async def observe_loop(request, call_next):
        observed["loop"] = threading.get_ident()
        return await call_next(request)

    original = app._new_job

    def new_job(*args, **kwargs):
        observed["worker"] = threading.get_ident()
        return original(*args, **kwargs)

    def start(job, worker, target, *options):
        observed.update(data=target.read_bytes(), name=target.name,
                        title=job.title, options=options, worker_function=worker)
        return {"id": job.id}

    monkeypatch.setattr(app, "_new_job", new_job)
    monkeypatch.setattr(app, "_start_job", start)
    with TestClient(application) as client:
        response = post(client, payload, filename="δοκιμή.WAV", data={
            "consent": "true", "language": "el", "model": "base", "speakers": "true",
            "target_language": "en", "summary": "true", "highlights": "true"})
    assert response.status_code == 200, response.text
    assert observed["worker"] != observed["loop"]
    assert observed["data"] == payload
    assert observed["name"] == "input.wav"
    assert observed["title"] == "δοκιμή.WAV"
    assert observed["options"] == ("el", "base", True, "en", True, True)
    assert observed["worker_function"] is app._process_upload


def test_rejected_uploads_do_not_reserve_queue_slots(monkeypatch):
    monkeypatch.setattr(app, "MAX_BYTES", 4)

    def unexpected(*args, **kwargs):
        pytest.fail("Invalid upload reserved a queue slot")

    monkeypatch.setattr(app, "_new_job", unexpected)
    with TestClient(site()) as client:
        assert post(client, b"12345").status_code == 413
        assert post(client, b"").status_code == 400
        assert post(client, b"1", filename="clip.exe").status_code == 400
        assert post(client, b"1", data={"consent": "false"}).status_code == 400
        assert post(client, b"1", headers={"Origin": "https://evil.example"}).status_code == 403
    assert not app.jobs
    assert not list(app.DATA_DIR.iterdir())


def test_exact_limit_and_spool_closed_before_worker_submission(monkeypatch):
    monkeypatch.setattr(app, "MAX_BYTES", 4)
    with tempfile.SpooledTemporaryFile(max_size=1) as incoming:
        incoming.write(b"1234")
        upload = UploadFile(incoming, filename="clip.wav")

        def start(job, worker, target, *options):
            assert incoming.closed
            assert target.read_bytes() == b"1234"
            return {"id": job.id}

        monkeypatch.setattr(app, "_start_job", start)
        assert app.submit_upload(Request({"type": "http", "headers": []}), upload,
                                 "en", "small", True, False, "none", False, False)["id"]


def test_oversized_spool_rejected_without_reading_and_closed(monkeypatch):
    class NoRead(io.BytesIO):
        def read(self, *args, **kwargs):
            pytest.fail("Oversized upload was read")

    monkeypatch.setattr(app, "MAX_BYTES", 4)
    incoming = NoRead(b"12345")
    with pytest.raises(HTTPException) as error:
        app.submit_upload(Request({"type": "http", "headers": []}),
                          UploadFile(incoming, filename="clip.wav"),
                          "en", "small", True, False, "none", False, False)
    assert error.value.status_code == 413
    assert incoming.closed
    assert not app.jobs


def test_copy_failure_releases_job_directory_and_spool(monkeypatch):
    class FailingRead(io.BytesIO):
        def read(self, *args, **kwargs):
            raise OSError("simulated spool read failure")

    incoming = FailingRead(b"audio")
    with pytest.raises(OSError, match="simulated spool read failure"):
        app.submit_upload(Request({"type": "http", "headers": []}),
                          UploadFile(incoming, filename="clip.wav"),
                          "en", "small", True, False, "none", False, False)
    assert incoming.closed
    assert not app.jobs
    assert not list(app.DATA_DIR.iterdir())

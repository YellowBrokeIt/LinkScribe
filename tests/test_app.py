"""Network-free tests of link validation, exports and API flow."""
from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import app as module


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=24s",
    "https://youtu.be/dQw4w9WgXcQ?t=24",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://www.youtube.com/live/dQw4w9WgXcQ",
    "youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
])
def test_accept_video_link_types(url):
    assert module.youtube_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
    "https://youtube.com@localhost/watch?v=dQw4w9WgXcQ",
    "http://127.0.0.1/secret",
    "file:///etc/passwd",
    "https://www.youtube.com/playlist?list=PL12345",
    "https://www.youtube.com/watch?v=invalid",
    "https://youtube.com:81/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ/another",
])
def test_reject_unsafe_or_unsupported_links(url):
    with pytest.raises(ValueError):
        module.youtube_video_id(url)


def test_timestamp_and_subtitle_format():
    assert module._timecode(3661.023, "srt") == "01:01:01,023"
    assert module._timecode(1.002, "vtt") == "00:00:01.002"
    segments = [{"start": 1.0, "end": 3.4, "text": "Γεια σου & hello"}]
    assert "1\n00:00:01,000 --> 00:00:03,400\nΓεια σου & hello" in module._render_subtitles(segments, "srt")
    assert "WEBVTT\n\n00:00:01.000 --> 00:00:03.400" in module._render_subtitles(segments, "vtt")


def fake_captions(_video_id, _language):
    return ([{"start": 0.25, "end": 2.5, "text": "Hello and καλώς ήρθατε"},
             {"start": 2.5, "end": 4.1, "text": "Thank you!"}], "en")


def test_real_http_routes_with_stubbed_captions(monkeypatch):
    monkeypatch.setattr(module, "_captions", fake_captions)
    # Execute job synchronously to make the API test deterministic; no network.
    monkeypatch.setattr(module.pool, "submit", lambda fn, *args: fn(*args))
    client = TestClient(module.app)
    assert client.get("/health").json()["status"] == "ok"
    assert "LinkScribe" in client.get("/").text

    declined = client.post("/api/link", data={"url": "https://youtu.be/dQw4w9WgXcQ", "consent": "false"})
    assert declined.status_code == 400
    invalid = client.post("/api/link", data={"url": "http://localhost/secret", "consent": "true"})
    assert invalid.status_code == 400
    wrong_mode = client.post("/api/link", data={"url": "https://youtu.be/dQw4w9WgXcQ", "mode": "evil", "consent": "true"})
    assert wrong_mode.status_code == 400
    csrf = client.post("/api/link", data={"url": "https://youtu.be/dQw4w9WgXcQ", "consent": "true"}, headers={"Origin": "https://attacker.example"})
    assert csrf.status_code == 403

    response = client.post("/api/link", data={"url": "https://youtu.be/dQw4w9WgXcQ", "mode": "captions", "consent": "true"})
    assert response.status_code == 200, response.text
    job_id = response.json()["id"]
    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    doc = status.json()
    assert doc["status"] == "done"
    assert doc["segments"] == 2
    assert "καλώς" in doc["preview"]

    for ext in ["txt", "srt", "vtt", "json", "zip"]:
        download = client.get(f"/api/jobs/{job_id}/download/{ext}")
        assert download.status_code == 200
        assert len(download.content) > 0

    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/jobs/{job_id}/download/zip").content))
    assert set(archive.namelist()) == {"transcript.txt", "transcript.srt", "transcript.vtt", "transcript.json"}
    assert "καλώς" in archive.read("transcript.txt").decode("utf-8")
    assert "Γεια" not in archive.read("transcript.txt").decode("utf-8")


def test_upload_with_stubbed_speech_recognizer(monkeypatch):
    monkeypatch.setattr(module.pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(module, "_check_uploaded_duration", lambda p: None)
    monkeypatch.setattr(module, "_recognize", lambda p, lang, model: ([{"start":0, "end":1.4, "text":"Local recording"}], "en"))
    client = TestClient(module.app)
    wrong_file = client.post("/api/upload", data={"consent":"true"}, files={"file":("unsafe.exe",b"stuff")})
    assert wrong_file.status_code == 400

    result = client.post("/api/upload", data={"consent":"true", "model":"base"}, files={"file":("mic.mp3",b"dummy media data","audio/mpeg")})
    assert result.status_code == 200, result.text
    job_id = result.json()["id"]
    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "done"
    assert status["method"] == "local_audio_ai"
    assert "Local recording" in client.get(f"/api/jobs/{job_id}/download/txt").text
    assert not list(module.jobs[job_id].workdir.glob("input.*")), "Temporary uploaded inputs must be deleted after processing"


def test_expiration_deletes_files(monkeypatch):
    client = TestClient(module.app)
    job = module._new_job("uploaded:test.mp3")
    (job.workdir / "transcript.txt").write_text("expired")
    module._set(job.id, status="done", finished_at=time.time() - module.JOB_TTL - 10)
    resp = client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 404
    assert not job.workdir.exists()

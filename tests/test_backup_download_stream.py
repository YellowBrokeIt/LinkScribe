"""Browser backup downloads must be bounded, compatible and close owned files."""
import asyncio
import hashlib
import io
import json
import tempfile
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app
import library
import library_backup


@pytest.fixture
def saved(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    identifier = "a" * 32
    library.save(identifier, "uploaded:clip.wav", "Τίτλος", "el", "local_audio_ai",
                 [{"start": 0, "end": 1, "text": "Καλημέρα", "speaker": "Αλίκη"}],
                 {"en": [{"start": 0, "end": 1, "text": "Good morning"}]})
    return identifier


@pytest.fixture
def streams(monkeypatch):
    real_temporary_file = tempfile.TemporaryFile
    files = []

    def track(*args, **kwargs):
        stream = real_temporary_file(*args, **kwargs)
        files.append(stream)
        return stream

    monkeypatch.setattr(app.tempfile, "TemporaryFile", track)
    return files


@pytest.fixture
def site():
    application = FastAPI()
    application.get("/api/library/backup")(app.export_library_backup)
    with TestClient(application) as client:
        yield client


def members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        assert bundle.testzip() is None
        assert sorted(bundle.namelist()) == ["manifest.json", "transcripts.json"]
        return {name: bundle.read(name) for name in bundle.namelist()}


def test_http_download_matches_bytes_helper_and_restores(site, saved, streams):
    original = library.get(saved)
    expected, count = library_backup.make_backup()
    response = site.get("/api/library/backup")
    assert response.status_code == 200
    assert response.headers["content-length"] == str(len(response.content))
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == 'attachment; filename="linkscr-library-backup.zip"'
    assert streams and streams[-1].closed
    content = members(response.content)
    assert count == 1 and content == members(expected)
    assert json.loads(content["manifest.json"])["sha256"] == hashlib.sha256(content["transcripts.json"]).hexdigest()
    assert library.delete(saved)
    with io.BytesIO(response.content) as stream:
        assert library_backup.restore_backup_file(stream) == {"total": 1, "imported": 1, "already_present": 0}
    assert library.get(saved) == original


def test_exact_archive_cap_and_rejection_close_file(site, saved, streams, monkeypatch):
    archive, _ = library_backup.make_backup()
    monkeypatch.setattr(library_backup, "MAX_ARCHIVE_BYTES", len(archive))
    assert site.get("/api/library/backup").status_code == 200
    assert streams[-1].closed
    monkeypatch.setattr(library_backup, "MAX_ARCHIVE_BYTES", len(archive) - 1)
    assert site.get("/api/library/backup").status_code == 413
    assert streams[-1].closed
    assert library.get(saved) is not None


def test_unexpected_archive_error_closes_file(site, saved, streams, monkeypatch):
    def fail(stream):
        stream.write(b"partial")
        raise OSError("simulated write failure")

    monkeypatch.setattr(library_backup, "write_backup", fail)
    with pytest.raises(OSError, match="simulated write failure"):
        site.get("/api/library/backup")
    assert streams and streams[-1].closed


def test_streaming_chunks_and_transport_failure_close_owned_file():
    async def transfer(fail):
        stream = tempfile.TemporaryFile(mode="w+b")
        payload = b"x" * 150000
        stream.write(payload)
        response = app._ZipArchiveResponse(stream, "test.zip")
        chunks = []

        async def send(message):
            if message["type"] == "http.response.body":
                chunks.append(message["body"])
                if fail:
                    raise OSError("simulated disconnect")

        async def receive():
            await asyncio.sleep(60)

        scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
        if fail:
            with pytest.raises(Exception):
                await response(scope, receive, send)
        else:
            await response(scope, receive, send)
            assert b"".join(chunks) == payload
        assert chunks and max(map(len, chunks)) <= 65536
        assert stream.closed

    asyncio.run(transfer(False))
    asyncio.run(transfer(True))

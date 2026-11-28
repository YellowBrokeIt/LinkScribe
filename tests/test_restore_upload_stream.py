"""Exercise the real multipart restore transport and seekable archive contract."""
import hashlib
import io
import json
import tempfile
import threading
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app
import library
import library_backup


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")


def archive(count=1, text="Γεια σου Bitcoin!", version=2):
    records = [{"id": f"{index:032x}", "source": "uploaded:clip.wav",
                "title": "Ελληνικά", "language": "el", "method": "local_audio_ai",
                "segments": [{"start": 0, "end": 1, "text": text}],
                "created_at": 1, "updated_at": 1} for index in range(count)]
    payload = json.dumps({"format": library_backup.FORMAT, "version": version,
                          "records": records}, ensure_ascii=False).encode("utf-8")
    manifest = {"format": library_backup.FORMAT, "version": version,
                "records": count, "sha256": hashlib.sha256(payload).hexdigest()}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zipped:
        zipped.writestr("manifest.json", json.dumps(manifest))
        zipped.writestr("transcripts.json", payload)
    return output.getvalue()


def site():
    # Mount the actual production handler without starting unrelated job workers.
    application = FastAPI()
    application.post("/api/library/restore")(app.import_library_backup)
    return application


def post(client, data, **kwargs):
    return client.post("/api/library/restore",
                       files={"file": ("backup.zip", data, "application/zip")}, **kwargs)


@pytest.mark.parametrize("version", [1, 2])
def test_seekable_restore_preserves_input_ownership_and_existing_ids(version):
    content = archive(version=version)
    with tempfile.SpooledTemporaryFile(max_size=1) as incoming:
        incoming.write(content)
        assert incoming.tell() == len(content)
        assert library_backup.restore_backup_file(incoming) == {
            "total": 1, "imported": 1, "already_present": 0}
        assert not incoming.closed
        assert library_backup.restore_backup_file(incoming) == {
            "total": 1, "imported": 0, "already_present": 1}
        assert not incoming.closed
    assert library_backup.restore_backup(content)["already_present"] == 1


def test_multipart_restore_uses_spooled_file_in_worker_thread(monkeypatch):
    application = site()
    observed = {}

    @application.middleware("http")
    async def record_event_loop(request, call_next):
        observed["loop_thread"] = threading.get_ident()
        return await call_next(request)

    original = library_backup.restore_backup_file

    def inspect(incoming):
        observed.update(file=incoming, worker_thread=threading.get_ident(),
                        rolled=isinstance(incoming, tempfile.SpooledTemporaryFile)
                        and incoming._rolled)
        return original(incoming)

    monkeypatch.setattr(library_backup, "restore_backup_file", inspect)
    content = archive(80, "α" * 10000)
    assert len(content) > 1024 * 1024
    with TestClient(application) as client:
        response = post(client, content)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "total": 80, "imported": 80, "already_present": 0}
    assert observed["rolled"]
    assert observed["loop_thread"] != observed["worker_thread"]
    assert observed["file"].closed


def test_actual_upload_length_limit_and_invalid_archives(monkeypatch):
    content = archive()
    monkeypatch.setattr(library_backup, "MAX_ARCHIVE_BYTES", len(content))
    with TestClient(site()) as client:
        assert post(client, content).status_code == 200
        assert post(client, content + b"x").status_code == 413
        assert post(client, b"").status_code == 400
        assert post(client, b"not a ZIP").status_code == 400
        assert post(client, content, headers={"Origin": "https://example.com"}).status_code == 403
        assert post(client, content).json()["already_present"] == 1


def test_oversized_stream_rejected_before_read(monkeypatch):
    class NoRead(io.BytesIO):
        def read(self, *args, **kwargs):
            pytest.fail("Oversized archive was read")

    monkeypatch.setattr(library_backup, "MAX_ARCHIVE_BYTES", 3)
    with NoRead(b"four") as incoming:
        with pytest.raises(library_backup.BackupTooLarge):
            library_backup.restore_backup_file(incoming)
        assert not incoming.closed

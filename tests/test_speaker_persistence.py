"""Speaker provenance survives upgrades, exports and bounded v1 backups."""
import hashlib
import io
import json
import sqlite3
from types import SimpleNamespace
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import batch_store
import library
import library_backup


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    app.jobs.clear()
    app.batches.clear()
    yield tmp_path
    app.jobs.clear()
    app.batches.clear()


def metadata():
    return {"asr": {"engine": "faster-whisper", "model": "small", "word_timestamps": True},
            "speakers": {"backend": "speechbrain-ecapa-silero-cpu",
                         "model": {"id": "speechbrain/spkrec-ecapa-voxceleb", "revision": "0" * 40},
                         "settings": {"cpu_threads": 2, "distance": 0.65},
                         "warnings": ["Labels are estimates."]},
            "warnings": ["Labels are estimates."]}


def save_record(identifier="a" * 32, processing=None):
    library.save(identifier, "uploaded:voice.wav", "Original title", "en", "local_audio_ai",
                 [{"start": 0, "end": 1, "text": "Hello", "speaker": "Speaker 1"}],
                 processing_metadata=processing)


def backup_records(records):
    contents = json.dumps({"format": library_backup.FORMAT, "version": 1, "records": records}).encode()
    manifest = {"format": library_backup.FORMAT, "version": 1, "records": len(records),
                "sha256": hashlib.sha256(contents).hexdigest()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
        output.writestr("transcripts.json", contents)
    return buffer.getvalue()


def test_existing_database_gets_additive_metadata_migration(local):
    with sqlite3.connect(library.DB_FILE) as connection:
        connection.execute("""CREATE TABLE transcripts (id TEXT PRIMARY KEY,source TEXT NOT NULL,
          title TEXT NOT NULL,language TEXT NOT NULL,method TEXT NOT NULL,segments TEXT NOT NULL,
          plain_text TEXT NOT NULL,translations TEXT NOT NULL DEFAULT '{}',summary TEXT,
          created_at REAL NOT NULL,updated_at REAL NOT NULL)""")
        connection.execute("INSERT INTO transcripts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           ("b" * 32, "old-source", "Keep this title", "el", "old-method",
                            '[{"start":0,"end":1,"text":"Γεια"}]', "Γεια", "{}", None, 1, 2))
    first = library.get("b" * 32)
    assert first["processing_metadata"] == {}
    assert first["title"] == "Keep this title" and first["segments"][0]["text"] == "Γεια"
    assert library.get("b" * 32) == first  # Migration is idempotent.
    save_record(processing=metadata())
    assert library.get("a" * 32)["processing_metadata"] == metadata()


def test_metadata_roundtrips_backups_and_legacy_v1_still_imports(local):
    save_record(processing=metadata())
    original = library.get("a" * 32)
    backup, _ = library_backup.make_backup()
    library.delete("a" * 32)
    assert library_backup.restore_backup(backup)["imported"] == 1
    assert library.get("a" * 32) == original
    legacy = {**original, "id": "c" * 32}
    legacy.pop("processing_metadata")
    assert library_backup.restore_backup(backup_records([legacy]))["imported"] == 1
    assert library.get("c" * 32)["processing_metadata"] == {}


@pytest.mark.parametrize("bad", [
    [], {"settings": {"bad": float("nan")}}, {"embeddings": [0.1, 0.2]},
    {"audio": "encoded-audio"}, {"settings": {"HF_TOKEN": "secret"}},
    {"warnings": ["x"] * 101}, {"backend": "x" * 4097},
    {f"field{i}": "x" * 4096 for i in range(9)},
    {"key": {"key": {"key": {"key": {"key": {"key": {"key": {"key": {"key": 1}}}}}}}}},
])
def test_invalid_processing_metadata_rejects_whole_restore(local, bad):
    save_record()
    good = {**library.get("a" * 32), "id": "b" * 32}
    invalid = {**good, "id": "c" * 32, "processing_metadata": bad}
    with pytest.raises(library_backup.BackupError):
        library_backup.restore_backup(backup_records([good, invalid]))
    assert library.get("b" * 32) is None
    assert library.get("c" * 32) is None
    assert library.get("a" * 32) is not None


def test_edit_updates_saved_batch_title_and_keeps_original_provenance(local):
    save_record(processing=metadata())
    batch_store.create("d" * 32, [{"id": "a" * 32, "source": "source", "title": "Original title"}], {})
    batch_store.mark_item("a" * 32, "done", title="Original title", library_id="a" * 32)
    segments = [{"start": 0, "end": 1, "text": "Edited text", "speaker": "Alice"}]
    assert library.update("a" * 32, "Edited title", segments)
    assert batch_store.get("d" * 32)["jobs"][0]["title"] == "Edited title"
    saved = library.get("a" * 32)
    assert saved["processing_metadata"]["speakers"] == metadata()["speakers"]
    assert saved["processing_metadata"]["user_edited"] is True
    # A late worker acknowledgement must not restore a title from before the edit.
    batch_store.mark_item("a" * 32, "done", title="Original title", library_id="a" * 32)
    assert batch_store.get("d" * 32)["jobs"][0]["title"] == "Edited title"


def test_batch_title_and_transcript_edit_rollback_together(local):
    save_record()
    batch_store.create("d" * 32, [{"id": "a" * 32, "source": "source", "title": "Original title"}], {})
    with library._connect() as connection:
        connection.execute("CREATE TRIGGER reject_batch_title BEFORE UPDATE OF title ON batch_queue_items BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        library.update("a" * 32, "Should roll back", [{"start": 0, "end": 1, "text": "Changed"}])
    assert library.get("a" * 32)["title"] == "Original title"
    assert batch_store.get("d" * 32)["jobs"][0]["title"] == "Original title"


def test_app_requests_real_words_and_persists_speaker_report(local, monkeypatch):
    requests = []
    class Engine:
        def transcribe(self, path, **kwargs):
            requests.append(kwargs)
            word = SimpleNamespace(start=0.1, end=0.9, word=" Hello")
            return iter([SimpleNamespace(start=0, end=1, text="Hello", words=[word])]), SimpleNamespace(language="en")
    monkeypatch.setattr(app, "_whisper_model", lambda _size: Engine())
    segments, language = app._recognize(local / "audio.wav", "auto", "small", word_timestamps=True)
    assert requests[0]["word_timestamps"] is True
    assert segments[0]["_words"] == [{"start": 0.1, "end": 0.9, "word": " Hello"}]
    report_metadata = metadata()["speakers"]
    def labels(path, items, *, include_report):
        assert include_report and items[0]["_words"]
        return {"segments": [{**items[0], "speaker": "Speaker 1"}],
                "warnings": ["Labels are estimates."], "provenance": report_metadata}
    monkeypatch.setattr(app, "assign_speakers", labels)
    identifier = "e" * 32
    workdir = local / identifier
    workdir.mkdir()
    app.jobs[identifier] = app.Job(id=identifier, workdir=workdir, source="uploaded:voice.wav")
    app._enhance_and_save(identifier, segments, language, "local_audio_ai", local / "audio.wav",
                          True, "none", False, asr_model="small")
    saved = library.get(identifier)
    assert "_words" not in saved["segments"][0]
    assert saved["processing_metadata"]["speakers"] == report_metadata
    assert app.jobs[identifier].warnings == ["Labels are estimates."]
    app.jobs.clear()
    with TestClient(app.app) as client:
        exported = client.get(f"/api/library/{identifier}/download/json")
        assert exported.status_code == 200
        assert exported.json()["processing_metadata"] == saved["processing_metadata"]
        assert b"Speaker 1: Hello" in client.get(f"/api/library/{identifier}/download/srt").content

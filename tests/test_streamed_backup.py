"""Verify streamed backup payload, size limits, snapshot and restoration."""
import hashlib
import io
import json
import zipfile

import pytest

import library
import library_backup


@pytest.fixture
def saved(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    return library.DB_FILE


def add(index):
    identifier = f"{index:032x}"
    library.save(identifier, "uploaded:clip.wav", f"Τίτλος {index}", "el",
                 "local_audio_ai",
                 [{"start": 0, "end": 1, "text": "Γεια σου Bitcoin!", "speaker": "Αλίκη"}],
                 {"en": [{"start": 0, "end": 1, "text": "Hello Bitcoin!"}]},
                 {"summary": "Greeting", "key_points": ["Bitcoin"],
                  "chapters": [{"start": 0, "title": "Start"}]},
                 {"warnings": ["Review speaker labels."]})
    return identifier


def members(archive):
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert sorted(zipped.namelist()) == ["manifest.json", "transcripts.json"]
        assert zipped.testzip() is None
        return {name: zipped.read(name) for name in zipped.namelist()}


@pytest.mark.parametrize("count", [0, 1, 5])
def test_backup_exact_payload_and_roundtrip(saved, count):
    ids = [add(index) for index in reversed(range(count))]
    records = [library.get(identifier) for identifier in sorted(ids)]
    expected = library_backup._encode({"format": library_backup.FORMAT,
                                      "version": library_backup.VERSION,
                                      "records": records})
    archive, actual_count = library_backup.make_backup()
    content = members(archive)
    assert actual_count == count
    assert content["transcripts.json"] == expected
    assert json.loads(content["manifest.json"]) == {
        "format": library_backup.FORMAT, "version": library_backup.VERSION,
        "records": count, "sha256": hashlib.sha256(expected).hexdigest()}
    for identifier in ids:
        library.delete(identifier)
    assert library_backup.restore_backup(archive) == {
        "total": count, "imported": count, "already_present": 0}
    assert [library.get(identifier) for identifier in sorted(ids)] == records
    assert members(library_backup.make_backup()[0]) == content


def test_backup_json_limit_is_exact_and_rejection_leaves_db_usable(saved, monkeypatch):
    add(1)
    add(2)
    content = members(library_backup.make_backup()[0])
    length = len(content["transcripts.json"])
    monkeypatch.setattr(library_backup, "MAX_JSON_BYTES", length)
    assert members(library_backup.make_backup()[0]) == content
    monkeypatch.setattr(library_backup, "MAX_JSON_BYTES", length - 1)
    with pytest.raises(library_backup.BackupError, match="too large"):
        library_backup.make_backup()
    assert library.get(f"{2:032x}") is not None
    monkeypatch.setattr(library_backup, "MAX_JSON_BYTES", length)
    assert members(library_backup.make_backup()[0]) == content


def test_backup_and_restore_share_record_limit(saved, monkeypatch):
    add(1)
    add(2)
    archive, _ = library_backup.make_backup()
    monkeypatch.setattr(library_backup, "MAX_RECORDS", 1)
    with pytest.raises(library_backup.BackupError, match="too many records"):
        library_backup.make_backup()
    with pytest.raises(library_backup.BackupError, match="too many records"):
        library_backup.restore_backup(archive)
    monkeypatch.setattr(library_backup, "MAX_RECORDS", 2)
    assert library_backup.make_backup()[1] == 2


def test_backup_snapshot_is_consistent_during_concurrent_edit(saved, monkeypatch):
    first, second = add(1), add(2)
    baseline = members(library_backup.make_backup()[0])
    original_row = library._row

    def edit_during_read(row):
        if row["id"] == first:
            writer = library._connect()
            try:
                with writer:
                    writer.execute("UPDATE transcripts SET title=? WHERE id=?",
                                   ("Concurrent edit", second))
            finally:
                writer.close()
        return original_row(row)

    with monkeypatch.context() as patch:
        patch.setattr(library, "_row", edit_during_read)
        assert members(library_backup.make_backup()[0]) == baseline
    assert library.get(second)["title"] == "Concurrent edit"
    assert members(library_backup.make_backup()[0]) != baseline


@pytest.mark.parametrize("failure", ["invalid-last-row", "duplicate-existing", "duplicate-new"])
def test_restore_validates_all_records_before_opening_database(saved, monkeypatch, failure):
    existing = add(1)
    fresh = add(2)
    original = library.get(existing)
    incoming = library.get(fresh)
    library.delete(fresh)
    changed = dict(original, title="Must not overwrite my edit")
    invalid = dict(incoming, id=f"{3:032x}", segments=[])
    records = {
        "invalid-last-row": [incoming, changed, invalid],
        "duplicate-existing": [incoming, changed, changed],
        "duplicate-new": [incoming, changed, incoming],
    }[failure]
    payload = library_backup._encode({"format": library_backup.FORMAT,
                                      "version": library_backup.VERSION,
                                      "records": records})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("transcripts.json", payload)
        archive.writestr("manifest.json", library_backup._encode({
            "format": library_backup.FORMAT, "version": library_backup.VERSION,
            "records": len(records), "sha256": hashlib.sha256(payload).hexdigest()}))
    def no_connection():
        pytest.fail("Restore accessed SQLite before validation completed")
    with monkeypatch.context() as patch:
        patch.setattr(library, "_connect", no_connection)
        with pytest.raises(library_backup.BackupError):
            library_backup.restore_backup(output.getvalue())
    assert library.get(existing) == original
    assert library.get(fresh) is None
    assert library_backup.make_backup()[1] == 1

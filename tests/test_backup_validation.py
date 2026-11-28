"""Restore rejects records that would break exports or future library backups."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import app
import library
import library_backup


@pytest.fixture
def site(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    app.jobs.clear()
    app.batches.clear()
    with TestClient(app.app, raise_server_exceptions=False) as client:
        yield client
    app.jobs.clear()
    app.batches.clear()


def record(identifier="a" * 32):
    return {
        "id": identifier,
        "source": "uploaded:spoken.wav",
        "title": "Ελληνικά και Bitcoin",
        "language": "el",
        "method": "local_audio_ai",
        "segments": [{"start": 0.0, "end": 1.25, "text": "Γεια σου Bitcoin!", "speaker": "Αλίκη"}],
        "translations": {"en": [{"start": 0.0, "end": 1.25, "text": "Hello Bitcoin!", "speaker": "Alice"}]},
        "summary": {
            "summary": "A greeting about Bitcoin.",
            "key_points": ["Unicode and timing survive the backup."],
            "chapters": [{"start": 0.0, "title": "Η αρχή"}],
        },
        "created_at": 1700000000.25,
        "updated_at": 1700000100.5,
    }


def archive(records, transform_payload=None):
    payload = json.dumps({"format": library_backup.FORMAT, "version": 1, "records": records}).encode()
    if transform_payload:
        payload = transform_payload(payload)
    manifest = {"format": library_backup.FORMAT, "version": 1, "records": len(records),
                "sha256": hashlib.sha256(payload).hexdigest()}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("manifest.json", json.dumps(manifest))
        zipped.writestr("transcripts.json", payload)
    return output.getvalue()


def restore(site, content):
    return site.post("/api/library/restore", files={"file": ("backup.zip", content, "application/zip")})


@pytest.mark.parametrize("enhancement", [
    {"translations": {"en": [None]}},
    {"translations": {"en": [{"start": 0, "end": 1}]}},
    {"translations": {"en": [{"start": 1, "end": 0, "text": "Bad order"}]}},
    {"translations": {"en": [{"start": False, "end": 1, "text": "Boolean timestamp"}]}},
    {"translations": {"en": [{"start": 0, "end": 1, "text": "Text", "speaker": {}}]}},
    {"translations": {"en": []}},
    {"translations": {"fr": [{"start": 0, "end": 1, "text": "Unsupported export target"}]}},
    {"summary": {"summary": 17, "key_points": [], "chapters": []}},
    {"summary": {"summary": "Missing export fields"}},
    {"summary": {"summary": "Text", "key_points": [None], "chapters": []}},
    {"summary": {"summary": "Text", "key_points": [], "chapters": [None]}},
    {"summary": {"summary": "Text", "key_points": [], "chapters": [{"start": "0", "title": "Bad time"}]}},
    {"summary": {"summary": "Text", "key_points": [], "chapters": [{"start": -1, "title": "Bad time"}]}},
    {"summary": {"summary": "Text", "key_points": [], "chapters": [{"start": 0, "title": []}]}},
], ids=["null-translation", "missing-translation-text", "reversed-translation-time",
        "boolean-translation-time", "invalid-translated-speaker", "empty-translation",
        "unsupported-translation", "numeric-summary", "missing-summary-fields",
        "invalid-key-point", "null-chapter", "string-chapter-time", "negative-chapter-time",
        "invalid-chapter-title"])
def test_invalid_enhancement_rejects_the_entire_import(site, enhancement):
    library.save("f" * 32, "uploaded:kept.wav", "Keep my edit", "en", "local_audio_ai",
                 [{"start": 0.0, "end": 1.0, "text": "Existing text stays unchanged"}])
    before = library.get("f" * 32)
    good, bad = record(), record("b" * 32)
    bad.update(deepcopy(enhancement))

    response = restore(site, archive([good, bad]))

    assert response.status_code == 400, response.text
    assert library.get(good["id"]) is None, "A valid first row must not be partially imported"
    assert library.get(bad["id"]) is None
    assert library.get("f" * 32) == before
    assert site.get("/api/library/backup").status_code == 200
    assert site.get(f"/api/library/{'f' * 32}/download/zip").status_code == 200


@pytest.mark.parametrize("location", ["segments", "translations", "summary"])
@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_json_is_rejected_even_in_unused_metadata(site, location, token):
    bad = record()
    if location == "segments":
        target = bad["segments"][0]
    elif location == "translations":
        target = bad["translations"]["en"][0]
    else:
        target = bad["summary"]
    target["unused_metadata"] = "__NONFINITE__"
    content = archive([bad], lambda payload: payload.replace(b'"__NONFINITE__"', token.encode()))

    response = restore(site, content)

    assert response.status_code == 400, response.text
    assert library.get(bad["id"]) is None
    assert site.get("/api/library/backup").status_code == 200


@pytest.mark.parametrize("location", ["title", "translation-metadata"])
def test_invalid_unicode_cannot_poison_library_exports(site, location):
    bad = record()
    if location == "title":
        bad["title"] = "\ud800"
    else:
        bad["translations"]["en"][0]["metadata"] = "\ud800"
    response = restore(site, archive([bad]))
    assert response.status_code == 400, response.text
    assert library.get(bad["id"]) is None


def test_extreme_timestamp_is_a_validation_error_not_server_error(site):
    bad = record()
    bad["created_at"] = 10 ** 400
    response = restore(site, archive([bad]))
    assert response.status_code == 400, response.text
    assert library.get(bad["id"]) is None


def test_valid_backup_restores_all_exports_and_can_be_backed_up_again(site):
    original = record()
    library.save(original["id"], original["source"], original["title"], original["language"],
                 original["method"], original["segments"], original["translations"], original["summary"])
    before = library.get(original["id"])
    backup = site.get("/api/library/backup")
    assert backup.status_code == 200
    library.delete(original["id"])

    response = restore(site, backup.content)

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "total": 1, "imported": 1, "already_present": 0}
    assert library.get(original["id"]) == before
    for fmt in ["txt", "srt", "vtt", "json", "zip", "translation_txt", "translation_srt",
                "translation_vtt", "translation_json", "summary_md", "summary_json"]:
        exported = site.get(f"/api/library/{original['id']}/download/{fmt}")
        assert exported.status_code == 200, (fmt, exported.text)
        assert exported.content
    assert "Αλίκη: Γεια σου Bitcoin!" in site.get(f"/api/library/{original['id']}/download/txt").text
    assert "Alice: Hello Bitcoin!" in site.get(f"/api/library/{original['id']}/download/translation_txt").text
    assert "Η αρχή" in site.get(f"/api/library/{original['id']}/download/summary_md").text
    second_backup = site.get("/api/library/backup")
    assert second_backup.status_code == 200
    assert restore(site, second_backup.content).json()["already_present"] == 1


def test_backup_refuses_to_offer_an_archive_larger_than_restore_accepts(site, monkeypatch):
    valid = record()
    assert restore(site, archive([valid])).status_code == 200
    size = len(site.get("/api/library/backup").content)
    monkeypatch.setattr(library_backup, "MAX_ARCHIVE_BYTES", size - 1)
    response = site.get("/api/library/backup")
    assert response.status_code == 413, response.text
    assert "restore limit" in response.json()["detail"]

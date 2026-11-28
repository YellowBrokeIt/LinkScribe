"""Regression: a large searchable library must not silently hide older records."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app
import library


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    for i in range(121):
        monkeypatch.setattr(library.time, "time", lambda: float(i // 3))
        library.save(f"{i:032x}", "uploaded:clip.wav", f"Τίτλος {i}", "el", "local_audio_ai",
                     [{"start": 0.0, "end": 1.0, "text": "Καλημέρα %_" if i % 2 else "other"}])
    application = FastAPI()
    application.get("/api/library")(app.list_library)
    return TestClient(application)


def walk(client, query="", limit=50):
    params = {"q": query, "limit": limit}
    ids = []
    while True:
        response = client.get("/api/library", params=params)
        assert response.status_code == 200
        page = response.json()
        ids.extend(x["id"] for x in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            return ids
        assert len(ids) <= 121
        params.update(before_created_at=cursor["created_at"], before_id=cursor["id"])


def test_every_record(site):
    assert walk(site) == [f"{i:032x}" for i in reversed(range(121))]
    assert len(library.list_items()) == 50
    assert len(library.list_items(limit=999)) == 100


def test_unicode_and_literal_search(site):
    for q in ("ΚΑΛΗΜΈΡΑ", "Καλημε\u0301ρα", "%_"):
        assert walk(site, q, 7) == [f"{i:032x}" for i in reversed(range(121)) if i % 2]
    assert walk(site, "absent") == []


def test_deleted_cursor_and_new_insert(site, monkeypatch):
    page = site.get("/api/library", params={"limit": 3}).json()
    cursor = page["next_cursor"]
    assert library.delete(cursor["id"])
    monkeypatch.setattr(library.time, "time", lambda: 99.0)
    library.save("f" * 32, "uploaded:new.wav", "new", "en", "local_audio_ai",
                 [{"start": 0.0, "end": 1.0, "text": "new"}])
    next_page = site.get("/api/library", params={"limit": 3,
                         "before_created_at": cursor["created_at"], "before_id": cursor["id"]}).json()
    assert [x["id"] for x in next_page["items"]] == [f"{i:032x}" for i in (117, 116, 115)]


@pytest.mark.parametrize("params", [
    {"before_id": "a" * 32},
    {"before_created_at": 1},
    {"before_id": "bad", "before_created_at": 1},
    {"before_id": "a" * 32, "before_created_at": "nan"},
    {"before_id": "a" * 32, "before_created_at": "inf"},
])
def test_bad_cursor(site, params):
    assert site.get("/api/library", params=params).status_code == 400


def test_empty_library_installation_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "empty.sqlite3")
    application = FastAPI()
    application.get("/api/library")(app.list_library)
    with TestClient(application) as client:
        response = client.get("/api/library")
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}

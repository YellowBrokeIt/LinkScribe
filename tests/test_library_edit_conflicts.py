"""Protect edits from stale browser tabs and concurrent API saves."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app
import library

ID = "a" * 32
URL = "/api/library/" + ID


@pytest.fixture
def site(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "DB_FILE", tmp_path / "library.sqlite3")
    library.save(ID, "uploaded:clip.wav", "Original", "el", "local_audio_ai",
                 [{"start": 0.0, "end": 1.0, "text": "παλιό", "speaker": "Α"}],
                 translations={"en": [{"start": 0, "end": 1, "text": "Old"}]},
                 summary={"summary": "Old", "key_points": [], "chapters": []},
                 processing_metadata={"warnings": ["Review speaker labels."]})
    application = FastAPI()
    application.put("/api/library/{item_id}")(app.edit_library_item)
    observed = {}
    @application.middleware("http")
    async def event_loop(request, call_next):
        observed["event_loop"] = threading.get_ident()
        return await call_next(request)
    original = library.get
    def observed_get(identifier):
        observed["worker"] = threading.get_ident()
        return original(identifier)
    monkeypatch.setattr(library, "get", observed_get)
    return application, original, observed


def body(title, revision):
    return {"title": title, "expected_updated_at": revision,
            "segments": [{"text": "νέο κείμενο", "speaker": "Β"}]}


def test_stale_browser_edit_and_sequential_saves(site):
    application, get, observed = site
    original = get(ID)
    with TestClient(application) as client:
        first = client.put(URL, json=body("First", original["updated_at"]))
        assert first.status_code == 200
        revision = first.json()["updated_at"]
        assert revision == get(ID)["updated_at"]
        assert client.put(URL, json=body("Stale", original["updated_at"])).status_code == 409
        assert get(ID)["title"] == "First"
        second = client.put(URL, json=body("Second", revision))
        assert second.status_code == 200
        assert observed["event_loop"] != observed["worker"]
    saved = get(ID)
    assert saved["title"] == "Second"
    assert saved["segments"] == [{"start": 0.0, "end": 1.0, "text": "νέο κείμενο", "speaker": "Β"}]
    assert saved["translations"] == {} and saved["summary"] is None
    assert saved["processing_metadata"]["warnings"] == ["Review speaker labels."]
    assert saved["processing_metadata"]["user_edited"] is True


def test_two_workers_cannot_overwrite_same_snapshot(site, monkeypatch):
    application, get, _ = site
    revision = get(ID)["updated_at"]
    original = library.update_revision
    barrier = threading.Barrier(2)
    def simultaneous(*args, **kwargs):
        barrier.wait(timeout=10)
        return original(*args, **kwargs)
    monkeypatch.setattr(library, "update_revision", simultaneous)
    titles = ["First", "Second"]
    with TestClient(application) as client, ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda title: client.put(URL, json=body(title, revision)), titles))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(title for title, response in zip(titles, responses) if response.status_code == 200)
    assert get(ID)["title"] == winner


@pytest.mark.parametrize("field", ["title", "text", "speaker"])
def test_invalid_unicode_is_rejected_without_edit(site, field):
    application, get, _ = site
    original = get(ID)
    payload = body("Valid", original["updated_at"])
    (payload if field == "title" else payload["segments"][0])[field] = "\ud800"
    with TestClient(application) as client:
        response = client.put(URL, content=json.dumps(payload),
                              headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert get(ID) == original


def test_legacy_api_can_still_edit(site):
    application, get, _ = site
    payload = body("Legacy", get(ID)["updated_at"])
    del payload["expected_updated_at"]
    with TestClient(application) as client:
        assert client.put(URL, json=payload).status_code == 200
    assert get(ID)["title"] == "Legacy"


def test_same_clock_tick_changes_revision(site, monkeypatch):
    import math
    application, get, _ = site
    previous = get(ID)["updated_at"]
    monkeypatch.setattr(library.time, "time", lambda: previous)
    revision = library.update_revision(ID, "Next", get(ID)["segments"], expected_updated_at=previous)
    assert revision == math.nextafter(previous, math.inf)
    with pytest.raises(library.EditConflict):
        library.update_revision(ID, "Stale", get(ID)["segments"], expected_updated_at=previous)

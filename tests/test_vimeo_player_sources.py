"""Public Vimeo player links retain their endpoint without widening access."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app
from sources import parse_source


PLAYER = "https://player.vimeo.com/video/19934655"
PAGE = "https://vimeo.com/19934655"


@pytest.mark.parametrize("raw", [
    PLAYER,
    "http://player.vimeo.com/video/19934655",
    PLAYER + "/?autoplay=1#t=10s",
    PLAYER + "?h=not-forwarded&password=not-forwarded&referrer=https://example.com",
])
def test_player_url_survives_storage_and_parser_round_trip(raw):
    source = parse_source(raw)
    assert (source.provider, source.video_id, source.url) == ("vimeo", "19934655", PLAYER)
    # Stored batch sources are parsed again during recovery. No query, privacy
    # hash, password or caller-supplied referrer is carried into acquisition.
    assert parse_source(source.url) == source


@pytest.mark.parametrize("raw", [PAGE, "http://www.vimeo.com/19934655?autoplay=1"])
def test_regular_page_does_not_gain_an_automatic_player_fallback(raw):
    assert parse_source(raw).url == PAGE


@pytest.mark.parametrize("raw", [
    "https://player.vimeo.com.evil.example/video/19934655",
    "https://user:password@player.vimeo.com/video/19934655",
    "https://player.vimeo.com:443/video/19934655",
    "https://player.vimeo.com/video/19934655/privatehash",
    "https://player.vimeo.com/video/19934655%2Fprivatehash",
])
def test_player_endpoint_stays_strictly_allowlisted(raw):
    with pytest.raises(ValueError):
        parse_source(raw)


def test_download_uses_the_explicit_player_endpoint(monkeypatch, tmp_path):
    calls = []

    class Downloader:
        def __init__(self, options):
            self.options = options
            assert options["noplaylist"] is True
            assert options["max_filesize"] == app.MAX_BYTES
            assert not any(key in options for key in (
                "cookiefile", "cookiesfrombrowser", "username", "password", "videopassword",
                "http_headers", "proxy", "impersonate"))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def extract_info(self, url, download=False):
            calls.append(("metadata", url, download))
            return {"title": "Public source", "duration": 12, "filesize": 10}

        def download(self, urls):
            calls.append(("download", urls))
            Path(self.options["outtmpl"].replace("%(ext)s", "mp4")).write_bytes(b"fixture")

    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=Downloader))
    source = parse_source(PLAYER + "?h=not-forwarded")
    job = app._new_job(source.url)
    try:
        audio, title = app._download_source_audio(job.id, source)
        assert title == "Public source" and audio.read_bytes() == b"fixture"
        assert job.source == PLAYER
        assert calls == [("metadata", PLAYER, False), ("download", [PLAYER])]
    finally:
        app._cleanup_job_inputs(job)
        app.jobs.pop(job.id, None)


def test_embed_restriction_remains_a_failure_without_alternate_route(monkeypatch, tmp_path):
    calls = []
    denied = RuntimeError("Cannot download embed-only video without embedding URL.")

    class Downloader:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def extract_info(self, url, download=False):
            calls.append(url)
            raise denied

        def download(self, urls):
            raise AssertionError("Restricted media must not be downloaded.")

    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=Downloader))
    job = app._new_job(PLAYER)
    try:
        with pytest.raises(app.ReadableError) as caught:
            app._download_source_audio(job.id, parse_source(PLAYER))
        assert caught.value.__cause__ is denied
        assert calls == [PLAYER]
        assert not list(job.workdir.glob("audio.*"))
    finally:
        app.jobs.pop(job.id, None)


def test_regular_and_player_aliases_are_one_video_in_a_batch(monkeypatch):
    def must_not_queue(*_args, **_kwargs):
        raise AssertionError("Duplicate video aliases must be rejected before queueing.")

    monkeypatch.setattr(app, "_cleanup_expired", must_not_queue)
    response = TestClient(app.app).post("/api/batch", data={
        "urls": PAGE + "\n" + PLAYER, "consent": "true", "mode": "audio",
    })
    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"].lower()

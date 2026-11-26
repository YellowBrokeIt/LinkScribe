"""Exercise LinkScribe's runtime policy at the actual yt-dlp API boundary."""
from __future__ import annotations

import pytest
import yt_dlp

import runtime_check


@pytest.mark.parametrize("detected", [
    {"deno": "2.2.9", "node": "24.22.0"},
    {"deno": "unreadable version"},
    {},
])
def test_rejected_runtimes_are_not_reenabled_by_downloader_defaults(monkeypatch, detected):
    # Omitting js_runtimes lets yt-dlp re-enable Deno, even after our check
    # rejected it. Pass the real options to the real downloader (no network).
    monkeypatch.setattr(runtime_check, "runtime_details", lambda: {
        "runtime": None, "supported": False, "detected": detected,
    })
    with yt_dlp.YoutubeDL({"quiet": True, **runtime_check.yt_dlp_js_options()}) as downloader:
        assert downloader.params["js_runtimes"] == {}


def test_security_patched_node_fallback_does_not_enable_other_runtimes(monkeypatch):
    monkeypatch.setattr(runtime_check, "runtime_details", lambda: {
        "runtime": "node", "supported": True, "version": "24.22.1",
    })
    with yt_dlp.YoutubeDL({"quiet": True, **runtime_check.yt_dlp_js_options()}) as downloader:
        assert set(downloader.params["js_runtimes"]) == {"node"}


@pytest.mark.parametrize("setting", [None, "1", "0", "true", ""])
def test_system_certificate_store_requires_explicit_opt_in_without_disabling_tls(monkeypatch, tmp_path, setting):
    import app
    from sources import parse_source

    if setting is None:
        monkeypatch.delenv("LINKSCRIBE_USE_SYSTEM_CERTS", raising=False)
    else:
        monkeypatch.setenv("LINKSCRIBE_USE_SYSTEM_CERTS", setting)
    identifier = "c" * 32
    source = parse_source("https://www.dailymotion.com/video/xbvubxi")
    monkeypatch.setattr(app, "jobs", {identifier: app.Job(identifier, tmp_path, source.url)})
    observed = {}

    class Downloader:
        def __init__(self, options):
            observed.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, url, download):
            assert url == source.url and download is False
            return {"title": "Owned mocked downloader fixture", "duration": 1}

        def download(self, urls):
            assert urls == [source.url]
            (tmp_path / "audio.wav").write_bytes(b"Mocked transport output; no live media request.")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Downloader)
    path, _title = app._download_source_audio(identifier, source)
    assert path == tmp_path / "audio.wav"
    assert ("no-certifi" in observed.get("compat_opts", [])) is (setting == "1")
    assert not observed.get("nocheckcertificate")
    assert not observed.get("prefer_insecure")

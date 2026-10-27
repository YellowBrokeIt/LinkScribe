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

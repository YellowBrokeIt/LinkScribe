"""Exercise LinkScribe's runtime policy at the actual yt-dlp API boundary."""
from __future__ import annotations

import pytest
import yt_dlp

import runtime_check


def _provider_smoke():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).with_name("smoke_real_links.py")
    spec = importlib.util.spec_from_file_location("provider_smoke_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("explicit_rate", [False, True])
def test_real_decode_observer_preserves_audio_identity_and_measures_actual_samples(explicit_rate):
    from types import SimpleNamespace
    observed, calls = [], []
    audio = [0.1] * 480

    def decode_audio(input_file, sampling_rate=16000, split_stereo=False):
        calls.append((input_file, sampling_rate, split_stereo))
        return audio

    target = SimpleNamespace(decode_audio=decode_audio)
    _provider_smoke().observe_audio_decode(target, lambda kind, **data: observed.append((kind, data)))
    rate = 8000 if explicit_rate else 16000
    result = target.decode_audio("owned-job/audio.wav", **({"sampling_rate": rate} if explicit_rate else {}))
    assert result is audio
    assert calls == [("owned-job/audio.wav", rate, False)]
    assert observed == [("audio_decoded", {"job_id": "owned-job", "sampling_rate_hz": rate,
        "channel_sample_counts": [480], "decoded_duration_seconds": 480 / rate})]


def test_real_decode_observer_does_not_turn_a_decoder_error_into_success():
    from types import SimpleNamespace
    observed = []
    error = ValueError("Owned invalid audio fixture")

    def decode_audio(input_file, sampling_rate=16000):
        raise error

    target = SimpleNamespace(decode_audio=decode_audio)
    _provider_smoke().observe_audio_decode(target, lambda *args, **kwargs: observed.append((args, kwargs)))
    with pytest.raises(ValueError) as caught:
        target.decode_audio("owned-job/audio.wav")
    assert caught.value is error
    assert observed == []


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

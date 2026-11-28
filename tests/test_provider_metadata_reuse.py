"""Download validated provider metadata once; all media and extractors are owned fakes."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import app
from sources import parse_source


@pytest.fixture
def local_job(monkeypatch, tmp_path):
    source = parse_source("https://www.dailymotion.com/video/xbvubxi")
    job = app.Job("d" * 32, tmp_path, source.url)
    monkeypatch.setattr(app, "jobs", {job.id: job})
    return job, source


def install_downloader(monkeypatch, info, *, outputs=None, failure_stage=None, failure=None):
    state = {"calls": [], "options": None, "exited": False}
    if outputs is None:
        outputs = {"audio.webm": b"owned media"}

    class Downloader:
        def __init__(self, options):
            state["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, *_):
            state["exited"] = True

        def extract_info(self, url, download=False):
            state["calls"].append(("extract", url, download))
            assert sum(c[0] == "extract" for c in state["calls"]) == 1
            assert download is False
            if failure_stage == "metadata":
                raise failure
            return info

        def process_ie_result(self, selected, download=True):
            assert selected is info and download is True
            state["calls"].append(("download_validated", selected, download))
            directory = Path(state["options"]["outtmpl"]).parent
            for name, contents in outputs.items():
                (directory / name).write_bytes(contents)
            if failure_stage == "transfer":
                raise failure
            return selected

        def download(self, _urls):
            raise AssertionError("Downloading the URL would extract metadata again.")

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=Downloader))
    return state


def test_one_extraction_downloads_the_exact_validated_result(local_job, monkeypatch):
    job, source = local_job
    info = {"id": "owned", "title": "Owned metadata", "duration": 12, "filesize": 11,
            "url": "https://media.invalid/already-selected.webm"}
    state = install_downloader(monkeypatch, info)
    audio, title = app._download_source_audio(job.id, source)
    assert state["calls"] == [("extract", source.url, False), ("download_validated", info, True)]
    assert audio == job.workdir / "audio.webm" and audio.read_bytes() == b"owned media"
    assert title == "Owned metadata" and state["exited"]
    expected = {"format": "bestaudio/best", "outtmpl": str(job.workdir / "audio.%(ext)s"),
                "noplaylist": True, "quiet": True, "no_warnings": True,
                "socket_timeout": 25, "retries": 2, "max_filesize": app.MAX_BYTES,
                "overwrites": False}
    assert all(state["options"][key] == value for key, value in expected.items())


@pytest.mark.parametrize("info, message", [
    (None, "did not return video details"),
    ({}, "did not return video details"),
    ({"_type": "playlist", "entries": []}, "Only one video"),
    ({"_type": "multi_video"}, "Only one video"),
    ({"entries": [{"id": "one"}]}, "Only one video"),
    ({"additional_urls": ["https://media.invalid/extra"]}, "Only one video"),
    ({"additional_entries": [{"id": "extra"}]}, "Only one video"),
    ({"_type": "url", "url": "https://media.invalid/another-source"}, "resolved video"),
    ({"_type": "url_transparent", "url": "https://media.invalid/another-source"}, "resolved video"),
    ({"duration": app.MAX_SECONDS + 1}, "2-hour limit"),
    ({"filesize": app.MAX_BYTES + 1}, "150 MB input limit"),
    ({"filesize_approx": app.MAX_BYTES + 1}, "150 MB input limit"),
])
def test_rejected_metadata_never_starts_a_download(local_job, monkeypatch, info, message):
    job, source = local_job
    state = install_downloader(monkeypatch, info)
    with pytest.raises(app.ReadableError, match=message):
        app._download_source_audio(job.id, source)
    assert state["calls"] == [("extract", source.url, False)]
    assert not list(job.workdir.iterdir()) and state["exited"]


@pytest.mark.parametrize("stage", ["metadata", "transfer"])
def test_download_errors_keep_clear_public_message_and_original_cause(local_job, monkeypatch, stage):
    job, source = local_job
    failure = RuntimeError("Owned extractor or transport failure; no network request.")
    state = install_downloader(monkeypatch, {"title": "Owned", "duration": 1},
                               outputs={}, failure_stage=stage, failure=failure)
    with pytest.raises(app.ReadableError, match="Video audio could not be accessed") as caught:
        app._download_source_audio(job.id, source)
    assert caught.value.__cause__ is failure and state["exited"]
    assert sum(c[0] == "extract" for c in state["calls"]) == 1
    assert sum(c[0] == "download_validated" for c in state["calls"]) == (stage == "transfer")


def test_failed_transfer_keeps_existing_worker_cleanup(local_job, monkeypatch):
    job, source = local_job
    keep = job.workdir / "keep.txt"
    keep.write_text("Unrelated file", encoding="utf-8")
    state = install_downloader(monkeypatch, {"title": "Owned", "duration": 1},
                               outputs={"audio.webm.part": b"partial"}, failure_stage="transfer",
                               failure=OSError("Owned interrupted transfer"))
    app._guarded_worker(job.id, app._download_source_audio, source)
    assert job.status == "error" and "Video audio could not be accessed" in job.error
    assert not list(job.workdir.glob("audio.*")) and keep.is_file() and state["exited"]


@pytest.mark.parametrize("outputs", [{}, {"audio.exe": b"not accepted"}])
def test_missing_usable_output_remains_an_error(local_job, monkeypatch, outputs):
    job, source = local_job
    install_downloader(monkeypatch, {"title": "Owned"}, outputs=outputs)
    with pytest.raises(app.ReadableError, match="No usable audio stream"):
        app._download_source_audio(job.id, source)


def test_actual_download_size_is_still_checked(local_job, monkeypatch):
    job, source = local_job
    monkeypatch.setattr(app, "MAX_BYTES", 8)
    install_downloader(monkeypatch, {"title": "Owned", "filesize": 4},
                       outputs={"audio.webm": b"123456789"})
    with pytest.raises(app.ReadableError, match="downloaded audio is over 150 MB"):
        app._download_source_audio(job.id, source)


def test_native_yt_dlp_reuses_info_without_network_or_second_extractor(local_job, monkeypatch):
    """Exercise the installed processing API, replacing only extraction and media transfer."""
    import yt_dlp
    from yt_dlp.extractor.common import InfoExtractor

    job, source = local_job
    real_downloader = yt_dlp.YoutubeDL
    extracted, transferred = [], []

    class OwnedFixtureIE(InfoExtractor):
        _VALID_URL = r"https://www\.dailymotion\.com/video/xbvubxi$"

        def _real_extract(self, url):
            extracted.append(url)
            assert len(extracted) == 1, "A second metadata extraction is forbidden."
            return {"id": "owned", "title": "Native owned fixture", "duration": 2,
                    "formats": [{"format_id": "owned-audio", "url": "https://media.invalid/owned.webm",
                                 "ext": "webm", "acodec": "opus", "vcodec": "none"}]}

    def make_downloader(options):
        downloader = real_downloader(options, auto_init=False)
        downloader.add_info_extractor(OwnedFixtureIE())

        def forbid_network(*_args, **_kwargs):
            raise AssertionError("This contract test must not access a provider or media URL.")

        def owned_transfer(info):
            transferred.append({key: info[key] for key in ("id", "title", "duration", "format_id", "url")})
            Path(downloader.prepare_filename(info)).write_bytes(b"owned transfer")

        monkeypatch.setattr(downloader, "urlopen", forbid_network)
        monkeypatch.setattr(downloader, "process_info", owned_transfer)
        return downloader

    monkeypatch.setattr(yt_dlp, "YoutubeDL", make_downloader)
    audio, title = app._download_source_audio(job.id, source)
    assert extracted == [source.url]
    assert transferred == [{"id": "owned", "title": "Native owned fixture", "duration": 2,
                            "format_id": "owned-audio", "url": "https://media.invalid/owned.webm"}]
    assert title == "Native owned fixture" and audio.read_bytes() == b"owned transfer"

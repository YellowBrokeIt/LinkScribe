"""Opt-in live provider probe; never reports provider failures as passes.

Run from the repository root, for example::

    PYTHONPATH=. python tests/smoke_live_providers.py \
        --url https://www.youtube.com/watch?v=aqz-KE-bpKQ \
        --url https://vimeo.com/1084537

The default checks real metadata/stream extraction without downloading media.
Add --download only for media you are authorized to retrieve: this calls the
application's real download helper and validates the file with PyAV. --captions
checks YouTube captions separately. No login, cookies, proxies, or bypasses are
configured by this script. Each URL runs in an isolated child with a deadline.
This is outside pytest because availability depends on the hosting providers.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

from sources import parse_source
from runtime_check import runtime_details, yt_dlp_js_options


def probe(url: str, download: bool = False, captions: bool = False,
          system_certs: bool = False) -> dict[str, Any]:
    source = parse_source(url)
    started = time.monotonic()
    result: dict[str, Any] = {"source": source.url, "provider": source.provider,
                              "mode": "download" if download else "metadata"}
    try:
        if captions:
            if source.provider != "youtube":
                raise ValueError("Caption probing is supported only for YouTube.")
            import app
            segments, language = app._captions(source.video_id, "auto")
            result.update(mode="captions", language=language, segment_count=len(segments))
        elif download:
            import app
            import av
            import library
            with tempfile.TemporaryDirectory(prefix="linkscr-provider-qa-") as directory:
                app.DATA_DIR = Path(directory) / "jobs"
                library.DB_FILE = Path(directory) / "library.sqlite3"
                job = app._new_job(source.url)
                try:
                    path, title = app._download_source_audio(job.id, source)
                    app._check_uploaded_duration(path)
                    with av.open(str(path)) as media:
                        if not media.streams.audio:
                            raise AssertionError("Downloaded file contains no audio stream.")
                    result.update(title=title, bytes=path.stat().st_size, media_valid=True)
                finally:
                    app.jobs.clear()
        else:
            import yt_dlp
            options = {"quiet": True, "no_warnings": True, "noplaylist": True,
                       "socket_timeout": 15, "retries": 0, "extractor_retries": 0,
                       "geo_bypass": False, "cachedir": False,
                       "format": "bestaudio/best"}
            if system_certs:
                # Use the machine's trusted CA store, including SSL_CERT_FILE.
                # TLS certificate verification remains enabled.
                options["compat_opts"] = ["no-certifi"]
            if source.provider == "youtube":
                options.update(yt_dlp_js_options())
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(source.url, download=False)
                if not info or not info.get("formats"):
                    raise AssertionError("Provider returned no playable formats.")
                result.update(title=info.get("title"), duration=info.get("duration"),
                              format_count=len(info["formats"]))
        result["status"] = "passed"
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc)[:2000])
        if exc.__cause__ is not None:
            result["cause"] = f"{type(exc.__cause__).__name__}: {exc.__cause__}"[:2000]
    result["seconds"] = round(time.monotonic() - started, 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", required=True, help="Permitted, public video URL")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--captions", action="store_true")
    parser.add_argument("--timeout", type=int, default=120, help="Maximum seconds per source")
    parser.add_argument("--report", type=Path, help="Optional JSON results file")
    parser.add_argument("--system-certs", action="store_true",
                        help="Metadata only: validate TLS with system CAs instead of certifi")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    if args.system_certs and (args.download or args.captions):
        parser.error("--system-certs is available only for metadata probes")
    if args.child:
        result = probe(args.url[0], args.download, args.captions, args.system_certs)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "passed" else 1

    outcomes = []
    for url in args.url:
        # Validate before starting any external request.
        source = parse_source(url)
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--url", source.url]
        command += ["--download"] if args.download else ["--captions"] if args.captions else []
        if args.system_certs:
            command.append("--system-certs")
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=args.timeout, env=os.environ.copy(), check=False)
            # The download helper may write progress output before the JSON line.
            outcome = json.loads(completed.stdout.strip().splitlines()[-1])
            if completed.returncode and outcome.get("status") == "passed":
                outcome.update(status="failed", error="Probe process exited unsuccessfully")
        except subprocess.TimeoutExpired:
            outcome = {"source": source.url, "provider": source.provider, "status": "failed",
                       "error_type": "Timeout", "error": f"Exceeded {args.timeout} seconds"}
        except (IndexError, json.JSONDecodeError):
            outcome = {"source": source.url, "provider": source.provider, "status": "failed",
                       "error_type": "ProbeProcessError", "error": completed.stderr[-2000:]}
        outcomes.append(outcome)
        print(json.dumps(outcome, ensure_ascii=False), flush=True)
    report = {"yt_dlp": importlib.metadata.version("yt-dlp"), "runtime": runtime_details(),
              "certificate_store": "system" if args.system_certs else "default",
              "checks": outcomes, "all_passed": all(x["status"] == "passed" for x in outcomes)}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

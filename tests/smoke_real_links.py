"""Opt-in public-provider acceptance through the real local application.

Run from the repository root (the default is the 52-second licensed trailer)::

    PYTHONPATH=. python tests/smoke_real_links.py --output qa-real-links
    LINKSCRIBE_USE_SYSTEM_CERTS=1 PYTHONPATH=. python tests/smoke_real_links.py \
        --fixture youtube_sintel_trailer --fixture vimeo_sintel_trailer \
        --fixture dailymotion_tears_of_steel --output qa-real-links

The real HTTP API, queue, downloader, local Whisper, SQLite, and exporters run
unchanged. Observer wrappers record acquisition, decoding, and recognition evidence;
they call the original functions and never supply media, captions, or text.
The isolated server process is stopped and started again to check durable
library downloads and completed batch history. No account, cookies, alternate
proxy, or restricted-source workaround is configured here. Network/auth errors
are recorded as failures, never provider passes. This is not an ASR accuracy
benchmark and does not establish unrestricted access to a whole provider.

Fixtures are Blender CC BY 3.0 content; the evidence records attribution and
the original licence pages. Transcripts are machine-generated derivatives.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import inspect
import io
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
SOURCE_FILES = ("app.py", "sources.py", "runtime_check.py", "library.py", "batch_store.py",
                "enhancements.py", "tests/smoke_real_links.py")
FIXTURES = {
    "youtube_sintel_trailer": {
        "url": "https://www.youtube.com/watch?v=HOfdboHvshg", "provider": "youtube",
        "title_contains": "Sintel", "public_title": '"Sintel" Trailer, Durian Open Movie Project',
        "uploader": "Blender", "license": "CC BY 3.0",
        "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://durian.blender.org/news/sintel-teaser/",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
    },
    "youtube_tears_of_steel_teaser": {
        "url": "https://www.youtube.com/watch?v=WwHux5QZfC8", "provider": "youtube",
        "title_contains": "Tears of Steel", "public_title": "Tears of Steel - Teaser",
        "uploader": "MangoOpenMovie", "license": "CC BY 3.0",
        "license_evidence": "https://mango.blender.org/about/",
        "publication_evidence": "https://mango.blender.org/production/tears-of-steel-teaser/",
        "attribution": "(CC) Blender Foundation | mango.blender.org",
    },
    "vimeo_sintel_trailer": {
        "url": "https://vimeo.com/11721242", "provider": "vimeo",
        "title_contains": "Sintel", "public_title": "Sintel trailer!", "uploader": "Dykam",
        "license": "CC BY 3.0", "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://vimeo.com/11721242",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
        "note": "Uploader identifies this as a reupload of the licensed original trailer.",
    },
    "vimeo_sintel_rerendered": {
        "url": "https://vimeo.com/19934655", "provider": "vimeo",
        "title_contains": "Sintel", "public_title": "Sintel re-rendered", "uploader": "Teddl",
        "license": "CC BY 3.0", "license_evidence": "https://durian.blender.org/sharing/",
        "publication_evidence": "https://vimeo.com/19934655",
        "attribution": "© copyright Blender Foundation | www.sintel.org",
        "note": "Full film; the re-render's public description states the original licence.",
    },
    "dailymotion_tears_of_steel": {
        "url": "https://www.dailymotion.com/video/xbvubxi", "provider": "dailymotion",
        "title_contains": "Tears of Steel", "public_title": "فيلم 🎬 Tears of Steel | معركة المستقبل بدأت",
        "uploader": "MixTube", "license": "CC BY 3.0",
        "license_evidence": "https://mango.blender.org/about/",
        "publication_evidence": "https://www.dailymotion.com/video/xbvubxi",
        "attribution": "(CC) Blender Foundation | mango.blender.org",
        "note": "Repost with an Arabic title; the public description names the film and licence.",
    },
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_hashes():
    return {name: digest(ROOT / name) for name in SOURCE_FILES}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def exception_chain(error):
    chain, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        item = {"type": type(error).__name__, "message": str(error)}
        response = getattr(error, "response", None)
        if response is not None:
            item["http_status"] = getattr(response, "status", None)
            headers = getattr(response, "headers", {})
            item["response_headers"] = {key: headers.get(key) for key in (
                "Content-Type", "Server", "Date", "X-Mitmproxy-Blocked-Reason", "X-Proxy-Error", "X-Squid-Error")}
            url = urllib.parse.urlsplit(getattr(response, "url", "") or "")
            item["response_origin"] = f"{url.scheme}://{url.netloc}" if url.netloc else ""
            try:
                item["response_body_prefix"] = response.read(2048).decode("utf-8", errors="replace")
            except Exception as read_error:
                item["response_body_unavailable"] = type(read_error).__name__
        chain.append(item)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


def observe_audio_decode(module, event):
    """Measure the actual production decoder's return value without replacing it."""
    original = module.decode_audio
    signature = inspect.signature(original)

    def observed_decode(input_file, *args, **kwargs):
        arguments = signature.bind(input_file, *args, **kwargs)
        arguments.apply_defaults()
        audio = original(input_file, *args, **kwargs)
        rate = arguments.arguments["sampling_rate"]
        channels = audio if isinstance(audio, tuple) else (audio,)
        counts = [len(channel) for channel in channels]
        event("audio_decoded",
              job_id=Path(input_file).parent.name if isinstance(input_file, (str, os.PathLike)) else None,
              sampling_rate_hz=rate, channel_sample_counts=counts,
              decoded_duration_seconds=max(counts, default=0) / rate)
        return audio

    module.decode_audio = observed_decode


def serve(data_root, events_path):
    """Only data locations and evidence observers differ from normal app startup."""
    sys.path.insert(0, str(ROOT))
    import app
    import av
    import library
    import uvicorn

    app.DATA_DIR = data_root / "jobs"
    app.DATA_DIR.mkdir(parents=True, exist_ok=True)
    library.DB_FILE = data_root / "library.sqlite3"
    os.environ["LINKSCRIBE_DEVICE"] = "cpu"

    def event(kind, **details):
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "pid": os.getpid(), "kind": kind, **details},
                                    ensure_ascii=True, allow_nan=False) + "\n")

    versions = {}
    for package in ("yt-dlp", "curl-cffi", "faster-whisper", "ctranslate2", "av", "certifi"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    event("server_start", versions=versions, system_certificates=os.getenv("LINKSCRIBE_USE_SYSTEM_CERTS") == "1",
          device="cpu", source_sha256=source_hashes())

    # Observe the decoder that WhisperModel.transcribe actually calls. Its
    # returned array is passed through unchanged; no second decode is run.
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    observe_audio_decode(importlib.import_module("faster_whisper.transcribe"), event)

    download = app._download_source_audio
    recognize = app._recognize

    def observed_download(job_id, source):
        started = time.monotonic()
        event("acquisition_start", job_id=job_id, provider=source.provider, url=source.url)
        try:
            path, title = download(job_id, source)
        except Exception as error:
            event("acquisition_failed", job_id=job_id, errors=exception_chain(error),
                  elapsed_seconds=round(time.monotonic() - started, 3))
            raise
        details = {"bytes": path.stat().st_size, "sha256": digest(path)}
        try:
            with av.open(str(path)) as media:
                details["duration_seconds"] = media.duration / av.time_base if media.duration is not None else None
                details["audio_streams"] = len(media.streams.audio)
        except Exception as error:
            # Keep the original production recognizer responsible for whether
            # this file can be decoded; observation must not replace its path.
            details.update(audio_streams=0, media_inspection_errors=exception_chain(error))
        event("acquisition_done", job_id=job_id, title=title, **details,
              elapsed_seconds=round(time.monotonic() - started, 3))
        return path, title

    def observed_recognize(path, language, model):
        started = time.monotonic()
        job_id = Path(path).parent.name
        event("recognition_start", job_id=job_id, model=model, requested_language=language,
              audio_sha256=digest(path))
        try:
            segments, detected_language = recognize(path, language, model)
            event("recognition_done", job_id=job_id, model=model, language=detected_language,
                  segment_count=len(segments), elapsed_seconds=round(time.monotonic() - started, 3))
            return segments, detected_language
        except Exception as error:
            event("recognition_failed", job_id=job_id, errors=exception_chain(error),
                  elapsed_seconds=round(time.monotonic() - started, 3))
            raise

    app._download_source_audio = observed_download
    app._recognize = observed_recognize
    uvicorn.run(app.app, host="127.0.0.1", port=8765, log_level="warning")


def zip_members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate export ZIP members."
        return {name: archive.read(name) for name in names}


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "provider-report.json").exists():
        raise ValueError("Choose a new output directory to preserve the previous evidence.")
    (output / "downloads").mkdir(exist_ok=True)
    (output / "records").mkdir(exist_ok=True)
    (output / "executed-smoke-real-links.py").write_bytes(Path(__file__).read_bytes())
    selected = args.fixture or ["youtube_sintel_trailer"]
    if len(selected) != len(set(selected)):
        raise ValueError("Do not repeat a fixture.")
    report = {
        "schema_version": 1, "started_at": now(), "complete": False, "result": "running",
        "mode": "audio", "requested_model": args.model, "requested_language": args.language,
        "source_sha256_before": source_hashes(), "fixture_licenses": {key: FIXTURES[key] for key in selected},
        "provider_acquisition": "actual_yt_dlp", "speech_recognition": "actual_local_faster_whisper",
        "instrumentation": "observer_wrappers_only; originals called without replacement outputs",
        "asr_semantic_quality": "unreviewed", "subtitle_alignment_accuracy": "unreviewed",
        "system_certificates": os.getenv("LINKSCRIBE_USE_SYSTEM_CERTS") == "1",
        "fixtures": [{"fixture": key, "status": "pending"} for key in selected],
        "mixed_batch": {"status": "pending"}, "restart": {"status": "pending"},
    }
    checkpoint = lambda: write_json(output / "provider-report.json", report)
    checkpoint()
    events_path = output / "events.jsonl"
    server = None
    scratch = tempfile.TemporaryDirectory(prefix="linkscr-real-links-")
    data_root = Path(scratch.name)
    log = (output / "server.log").open("w", encoding="utf-8")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    successful_records = {}
    export_payloads = {}
    batch_archive = None
    batch_id = None

    def request(path, data=None, as_json=True):
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        headers = {"Origin": BASE_URL}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        with opener.open(urllib.request.Request(BASE_URL + path, data=body, headers=headers), timeout=30) as response:
            raw = response.read()
        return json.loads(raw) if as_json else raw

    def start_server():
        nonlocal server
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 8765))
        command = [args.server_python or sys.executable, str(Path(__file__).resolve()),
                   "--serve", str(data_root), "--events", str(events_path)]
        server = subprocess.Popen(command, cwd=data_root, stdout=log, stderr=subprocess.STDOUT,
                                  env={**os.environ, "PYTHONPATH": os.pathsep.join(
                                      [str(ROOT), os.environ.get("PYTHONPATH", "")])})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Isolated app exited during startup; see server.log.")
            try:
                request("/health")
                return server.pid
            except OSError:
                time.sleep(0.2)
        raise TimeoutError("Isolated app did not become ready.")

    def stop_server():
        nonlocal server
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
            server = None

    def events_for(identifier):
        if not events_path.exists():
            return []
        return [item for line in events_path.read_text(encoding="utf-8").splitlines()
                if (item := json.loads(line)).get("job_id") == identifier]

    def poll(path, item, timeout):
        deadline = time.monotonic() + timeout
        previous = None
        item["poll_count"] = 0
        item["transitions"] = []
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Server exited during a real job.")
            state = request(path)
            item["poll_count"] += 1
            signature = (state["status"], state.get("stage"), state.get("completed"))
            if signature != previous:
                item["transitions"].append({"at": now(), **state})
                previous = signature
                checkpoint()
            if state["status"] in {"done", "error"}:
                return state
            time.sleep(0.5)
        raise TimeoutError(f"Real job exceeded {timeout} seconds; no simulated success was substituted.")

    def verify_saved(identifier, expected_url, expected_title):
        record = request("/api/library/" + identifier)
        assert record["source"] == expected_url and record["method"] == "local_audio_ai", record
        assert expected_title.casefold() in record["title"].casefold(), record["title"]
        segments = record["segments"]
        assert segments and all(isinstance(s["text"], str) and s["text"].strip() for s in segments)
        assert all(math.isfinite(s["start"]) and math.isfinite(s["end"]) and 0 <= s["start"] <= s["end"] for s in segments)
        assert all(a["start"] <= b["start"] for a, b in zip(segments, segments[1:]))
        with sqlite3.connect(f"file:{data_root / 'library.sqlite3'}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT source,title,segments FROM transcripts WHERE id=?", (identifier,)).fetchone()
        assert row and row[0] == record["source"] and row[1] == record["title"] and json.loads(row[2]) == segments
        write_json(output / "records" / (identifier + ".json"), record)
        payloads = {}
        for code in ("txt", "srt", "vtt", "json", "zip"):
            job_data = request(f"/api/jobs/{identifier}/download/{code}", as_json=False)
            library_data = request(f"/api/library/{identifier}/download/{code}", as_json=False)
            if code == "zip":
                assert zip_members(job_data) == zip_members(library_data)
            else:
                assert job_data == library_data, f"Job and library {code} differ."
            payloads[code] = library_data
            (output / "downloads" / (identifier + "." + code)).write_bytes(library_data)
        exported = json.loads(payloads["json"])
        for key in ("source", "title", "language", "method", "segments"):
            assert exported[key] == record[key], key
        if record.get("processing_metadata"):
            assert exported.get("processing_metadata") == record["processing_metadata"]
        for code in ("txt", "srt", "vtt"):
            text, cursor = payloads[code].decode("utf-8"), 0
            for segment in segments:
                spoken = segment["text"].strip().replace("\r", " ").replace("\n", " ")
                position = text.find(spoken, cursor)
                assert position >= cursor, f"Saved words missing or reordered in {code}."
                cursor = position + len(spoken)
        assert payloads["vtt"].startswith(b"WEBVTT\n")
        assert payloads["srt"].count(b" --> ") == len(segments)
        assert payloads["vtt"].count(b" --> ") == len(segments)
        members = zip_members(payloads["zip"])
        for code in ("txt", "srt", "vtt", "json"):
            assert members["transcript." + code] == payloads[code]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and list((data_root / "jobs" / identifier).glob("audio.*")):
            time.sleep(0.1)
        assert not list((data_root / "jobs" / identifier).glob("audio.*")), "Downloaded audio was not cleaned."
        evidence = events_for(identifier)
        assert any(e["kind"] == "acquisition_done" and e["audio_streams"] > 0 for e in evidence), evidence
        decoded = [e for e in evidence if e["kind"] == "audio_decoded"]
        assert len(decoded) == 1 and decoded[0]["decoded_duration_seconds"] > 0, evidence
        assert any(e["kind"] == "recognition_done" and e["segment_count"] == len(segments) for e in evidence), evidence
        successful_records[identifier] = record
        export_payloads[identifier] = payloads
        return {"id": identifier, "title": record["title"], "language": record["language"],
                "segment_count": len(segments), "events": evidence,
                "decoded_duration_seconds": decoded[0]["decoded_duration_seconds"],
                "last_segment_end_seconds": max(s["end"] for s in segments),
                "maximum_segment_duration_seconds": max(s["end"] - s["start"] for s in segments),
                "exports": {code: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                            for code, data in payloads.items()},
                "sqlite_matches_saved_segments": True, "input_audio_cleaned": True,
                "export_text_order_preserved": True, "subtitle_time_accuracy": "not_evaluated"}

    try:
        report["initial_server_pid"] = start_server()
        for item in report["fixtures"]:
            fixture = FIXTURES[item["fixture"]]
            item.update(status="running", started_at=now(), url=fixture["url"])
            checkpoint()
            started = time.monotonic()
            try:
                posted = request("/api/link", {"url": fixture["url"], "mode": "audio",
                    "language": args.language, "model": args.model, "consent": "true"})
                item["job_id"] = posted["id"]
                final = poll("/api/jobs/" + posted["id"], item, args.timeout)
                item["final_job"] = final
                if final["status"] != "done":
                    raise RuntimeError(final.get("error") or "Actual provider job failed.")
                item["verification"] = verify_saved(posted["id"], fixture["url"], fixture["title_contains"])
                item["status"] = "pass"
            except TimeoutError:
                item["status"] = "incomplete"
                raise
            except Exception as error:
                item.update(status="fail", errors=exception_chain(error), traceback=traceback.format_exc())
            finally:
                if "job_id" in item:
                    item["events"] = events_for(item["job_id"])
                item["elapsed_seconds"] = round(time.monotonic() - started, 3)
                checkpoint()
                print(item["fixture"] + ": " + item["status"].upper(), flush=True)

        passed = next((item for item in report["fixtures"] if item["status"] == "pass"), None)
        failed = next((item for item in report["fixtures"] if item["status"] == "fail" and item.get("final_job", {}).get("status") == "error"), None)
        batch = report["mixed_batch"]
        if passed and failed:
            batch.update(status="running", fixtures=[passed["fixture"], failed["fixture"]])
            checkpoint()
            fixtures = [FIXTURES[name] for name in batch["fixtures"]]
            try:
                posted = request("/api/batch", {"urls": "\n".join(f["url"] for f in fixtures), "mode": "audio",
                    "language": args.language, "model": args.model, "consent": "true"})
                batch_id = posted["id"]
                batch["id"] = batch_id
                final = poll("/api/batches/" + batch_id, batch, args.timeout * 2)
                batch["final_batch"] = final
                assert final["status"] == "done" and final["completed"] == 2 and final["failed"] == 1, final
                good, bad = final["jobs"]
                assert good["status"] == "done" and bad["status"] == "error", final
                batch["successful_job"] = verify_saved(good["id"], fixtures[0]["url"], fixtures[0]["title_contains"])
                batch_archive = request(f"/api/batches/{batch_id}/download", as_json=False)
                (output / "downloads" / "mixed-batch.zip").write_bytes(batch_archive)
                manifest = json.loads(zip_members(batch_archive)["batch-report.json"])
                assert manifest["failed"] == 1 and len(manifest["items"]) == 2, manifest
                batch.update(status="pass", manifest=manifest)
            except TimeoutError:
                batch["status"] = "incomplete"
                raise
            except Exception as error:
                batch.update(status="fail", errors=exception_chain(error), traceback=traceback.format_exc())
        else:
            batch.update(status="not_exercised", reason="Requires one actual successful and one actually failing licensed fixture.")
        checkpoint()

        restart = report["restart"]
        restart["status"] = "running"
        stop_server()
        report["restarted_server_pid"] = start_server()
        assert report["initial_server_pid"] != report["restarted_server_pid"]
        verified = []
        for identifier, record in successful_records.items():
            assert request("/api/library/" + identifier) == record
            for code, before in export_payloads[identifier].items():
                after = request(f"/api/library/{identifier}/download/{code}", as_json=False)
                assert (zip_members(after) == zip_members(before)) if code == "zip" else (after == before)
            verified.append(identifier)
        if batch_id is not None and batch_archive is not None:
            restored = request("/api/batches/" + batch_id)
            assert restored["status"] == "done" and restored["failed"] == 1, restored
            assert zip_members(request(f"/api/batches/{batch_id}/download", as_json=False)) == zip_members(batch_archive)
            restart["completed_batch_history_and_exports_preserved"] = True
        restart.update(status="pass" if verified else "not_exercised", verified_record_ids=verified)
        report["complete"] = True
    except BaseException as error:
        report["fatal"] = {"errors": exception_chain(error), "traceback": traceback.format_exc()}
        for item in report["fixtures"]:
            if item["status"] in {"pending", "running"}:
                item["status"] = "incomplete"
        for key in ("mixed_batch", "restart"):
            if report[key]["status"] in {"pending", "running"}:
                report[key]["status"] = "incomplete"
    finally:
        stop_server()
        log.close()
        if (data_root / "library.sqlite3").exists():
            with sqlite3.connect(data_root / "library.sqlite3") as source, sqlite3.connect(output / "library.sqlite3") as target:
                source.backup(target)
        scratch.cleanup()
        report["source_sha256_after"] = source_hashes()
        report["source_files_unchanged"] = report["source_sha256_before"] == report["source_sha256_after"]
        report["finished_at"] = now()
        report["all_selected_providers_passed"] = all(item["status"] == "pass" for item in report["fixtures"])
        passed = (report["complete"] and report["all_selected_providers_passed"] and report["source_files_unchanged"]
                  and report["restart"]["status"] == "pass" and report["mixed_batch"]["status"] != "fail")
        if args.require_mixed_batch:
            passed = passed and report["mixed_batch"]["status"] == "pass"
        report["result"] = "pass" if passed else "fail"
        checkpoint()
    print(json.dumps({"result": report["result"], "complete": report["complete"],
                      "report": str(output / "provider-report.json")}), flush=True)
    return 0 if report["result"] == "pass" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="append", choices=sorted(FIXTURES))
    parser.add_argument("--model", choices=("tiny", "base", "small", "large-v3-turbo"), default="tiny")
    parser.add_argument("--language", choices=("auto", "en", "el"), default="auto")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", type=Path, default=Path("qa-real-links"))
    parser.add_argument("--server-python", help="Python executable containing the app's installed dependencies")
    parser.add_argument("--require-mixed-batch", action="store_true")
    parser.add_argument("--serve", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--events", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        if not args.events:
            parser.error("Private --serve entry requires --events")
        serve(args.serve, args.events)
        return 0
    if not 30 <= args.timeout <= 3600:
        parser.error("--timeout must be between 30 and 3600 seconds per source")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

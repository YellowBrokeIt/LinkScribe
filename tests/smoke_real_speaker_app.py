#!/usr/bin/env python3
"""Actual upload -> Whisper -> public speakers -> SQLite -> exports smoke.

Uses an isolated QA database and real model calls. No models are downloaded by
this harness itself. Optional --target/--summary also require the actual selected
local backends. Peak RSS describes this process, not an external Ollama process.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import uuid

os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def save(path, report):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=("none", "el", "en"), default="none")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 1800:
        parser.error("--timeout must be between1 and1800 seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_dir = args.output.parent / (args.output.stem + "-artifacts-" + uuid.uuid4().hex[:8])
    run_dir.mkdir()
    started = time.monotonic()
    names = ("app.py", "enhancements.py", "diarization.py", "library.py", "library_backup.py",
             "batch_store.py", "tests/smoke_real_speaker_app.py")
    report = {"schema_version": 1, "complete": False, "created_utc": datetime.now(timezone.utc).isoformat(),
              "audio": {"path": str(args.audio.resolve()), "sha256": sha(args.audio)},
              "source_sha256": {name: sha(ROOT / name) for name in names},
              "run_directory": str(run_dir.resolve()), "actual_recognizer_calls": [],
              "actual_speaker_calls": [], "semantic_quality": "unreviewed",
              "memory_scope": "Linux peak RSS of this app/ASR/speaker process; excludes external Ollama and other processes."}
    save(args.output, report)
    application = None
    original_recognize = original_speakers = None
    try:
        from fastapi.testclient import TestClient
        import app as application
        import library
        application.DATA_DIR = run_dir / "jobs"
        application.DATA_DIR.mkdir()
        library.DB_FILE = run_dir / "library.sqlite3"
        original_recognize = application._recognize
        original_speakers = application.assign_speakers

        def observe_recognize(*call_args, **call_kwargs):
            result = original_recognize(*call_args, **call_kwargs)
            report["actual_recognizer_calls"].append({"language_requested": call_args[1], "model": call_args[2],
                                                     "options": call_kwargs, "detected_language": result[1],
                                                     "segments": result[0]})
            save(args.output, report)
            return result

        def observe_speakers(*call_args, **call_kwargs):
            result = original_speakers(*call_args, **call_kwargs)
            report["actual_speaker_calls"].append({"include_report": call_kwargs.get("include_report"),
                                                 "result": result})
            save(args.output, report)
            return result

        application._recognize = observe_recognize
        application.assign_speakers = observe_speakers
        form = {"consent": "true", "speakers": "true", "target_language": args.target,
                "summary": "true" if args.summary else "false"}
        report["upload_form"] = form  # Language/model intentionally omitted: use real defaults.
        with TestClient(application.app) as client:
            response = client.post("/api/upload", data=form,
                                   files={"file": (args.audio.name, args.audio.read_bytes(), "audio/wav")})
            assert response.status_code == 200, response.text
            identifier = response.json()["id"]
            report["job_id"] = identifier
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                state = client.get(f"/api/jobs/{identifier}").json()
                if state["status"] in {"done", "error"}:
                    break
                time.sleep(0.2)
            report["job"] = state
            assert state["status"] == "done", state
            record = library.get(identifier)
            assert record and record["processing_metadata"]["speakers"]["backend"] == "speechbrain-ecapa-silero-cpu"
            assert len(report["actual_recognizer_calls"]) == len(report["actual_speaker_calls"]) == 1
            assert report["actual_recognizer_calls"][0]["options"]["word_timestamps"] is True
            before = " ".join(" ".join(item["text"].split()) for item in report["actual_recognizer_calls"][0]["segments"])
            after = " ".join(" ".join(item["text"].split()) for item in record["segments"])
            assert before == after, "Speaker alignment lost or changed recognized words."
            assert all("_words" not in item for item in record["segments"])
            labels = sorted({item["speaker"] for item in record["segments"] if item.get("speaker") != "Unknown speaker"})
            assert len(labels) >= 2, "The selected multi-reader fixture did not retain two supported labels."
            if args.target != "none":
                assert args.target in record["translations"], state["warnings"]
            if args.summary:
                assert record["summary"], state["warnings"]
            exports = {}
            for fmt in ("json", "srt", "vtt", "txt", "zip"):
                exported = client.get(f"/api/jobs/{identifier}/download/{fmt}")
                assert exported.status_code == 200 and exported.content
                target = run_dir / f"transcript.{fmt}"
                target.write_bytes(exported.content)
                exports[fmt] = {"path": str(target.resolve()), "sha256": sha(target)}
            exported_json = json.loads((run_dir / "transcript.json").read_text())
            assert exported_json["processing_metadata"] == record["processing_metadata"]
            application.jobs.clear()
            durable = client.get(f"/api/library/{identifier}/download/json")
            assert durable.status_code == 200 and durable.json() == exported_json
            backup = client.get("/api/library/backup")
            assert backup.status_code == 200
            (run_dir / "library-backup.zip").write_bytes(backup.content)
            report.update({"complete": True, "record": record, "known_speaker_labels": labels,
                           "exports": exports, "recognized_words_preserved": True,
                           "durable_download_after_job_eviction": True})
        assert {name: sha(ROOT / name) for name in names} == report["source_sha256"], "Source changed during inference."
    except Exception as exc:
        report["complete"] = False
        report["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "cause": repr(exc.__cause__) if exc.__cause__ else None}
    finally:
        if application is not None:
            if original_recognize is not None:
                application._recognize = original_recognize
            if original_speakers is not None:
                application.assign_speakers = original_speakers
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["peak_process_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
        save(args.output, report)
    print(json.dumps({key: report.get(key) for key in ("complete", "elapsed_seconds", "peak_process_rss_mib", "error")}), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Opt-in raw ASR diagnosis against an isolated source snapshot.

This invokes that snapshot's actual ``app._recognize`` on the supplied complete
media file, without a server or replacement model output. No reference is sent
to the decoder. A completed process is not a semantic-quality pass. Keep every
run in a new output directory; original results must remain available.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--audio-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--seed", type=int, default=20261128)
    args = parser.parse_args()
    tree, source, output = args.source_root.resolve(), args.audio.resolve(), args.output.resolve()
    if digest(source) != args.audio_sha256:
        raise ValueError("Input bytes do not match the explicitly expected source hash.")
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(tree))
    os.environ["LINKSCRIBE_DEVICE"] = "cpu"
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import ctranslate2
    import app
    assert Path(app.__file__).resolve() == tree / "app.py", "Wrong source snapshot imported."
    spec = importlib.util.spec_from_file_location("followup_observers", tree / "tests/smoke_real_links.py")
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    whisper = importlib.import_module("faster_whisper.transcribe")
    audio_module = importlib.import_module("faster_whisper.audio")
    vad_module = importlib.import_module("faster_whisper.vad")
    names = ("app.py", "sources.py", "tests/smoke_real_links.py")
    events = []
    started = time.monotonic()
    report = {
        "schema_version": 1, "started_at": observer.now(), "execution_status": "running",
        "semantic_quality": "unreviewed", "reference_supplied_to_decoder": False,
        "scope": "Direct isolated app recognition; not HTTP/provider/persistence acceptance.",
        "source_root": str(tree), "source_sha256_before": {name: digest(tree / name) for name in names},
        "probe_sha256": digest(__file__), "audio_sha256": args.audio_sha256,
        "audio_bytes": source.stat().st_size, "requested_model": args.model,
        "requested_language": args.language, "qa_random_seed": args.seed,
        "versions": {name: importlib.metadata.version(name) for name in (
            "faster-whisper", "ctranslate2", "av", "onnxruntime", "huggingface-hub")},
        "installed_source_sha256": {name: digest(importlib.import_module("faster_whisper." + name).__file__)
                                    for name in ("transcribe", "audio", "vad", "utils")},
    }

    def event(kind, **fields):
        value = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
        events.append(value)
        with (output / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n")

    observer.write_json(output / "report.json", report)
    job_id = lambda: "whole_recording_diagnostic"
    observer.observe_audio_decode(audio_module, event)
    observer.observe_audio_decode(whisper, event)
    observer.observe_transcribe(whisper, event, job_id)
    observer.observe_segment_creation(whisper, event, job_id)
    observer.observe_whole_recording_speech(vad_module, event, job_id)
    observer.observe_model_resolution(whisper, event, job_id)
    ctranslate2.set_random_seed(args.seed)
    print(json.dumps({"started": True, "snapshot": str(tree), "output": str(output)}), flush=True)
    try:
        segments, language = app._recognize(source, args.language, args.model)
        report.update(execution_status="completed", segments=segments, language=language)
    except Exception as error:
        report.update(execution_status="error", errors=observer.exception_chain(error))
    finally:
        report.update(finished_at=observer.now(), elapsed_seconds=round(time.monotonic() - started, 3),
                      source_sha256_after={name: digest(tree / name) for name in names},
                      audio_sha256_after=digest(source), events=events)
        report["source_files_unchanged"] = report["source_sha256_before"] == report["source_sha256_after"]
        report["audio_unchanged"] = report["audio_sha256_after"] == args.audio_sha256
        observer.write_json(output / "report.json", report)
    print(json.dumps({"execution_status": report["execution_status"],
                      "segments": len(report.get("segments", [])),
                      "report": str(output / "report.json")}), flush=True)
    return 0 if report["execution_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

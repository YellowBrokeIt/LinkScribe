"""One frozen official-film upload arm with unchanged full-audio observations.

This wraps the existing real upload/persistence/export harness. References remain
evaluation-only. It neither calls a video provider nor changes production ASR.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm", choices=("baseline", "aligned"), required=True)
    args, remaining = parser.parse_known_args()
    plan = json.loads(args.plan.read_text())
    tree = args.source_root.resolve()
    assert sha(tree / "app.py") == plan["arms"][args.arm]["app_sha256"]
    assert sha(__file__) == plan["runner_sha256"]
    sys.path.insert(0, str(tree))
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import ctranslate2
    import app
    assert Path(app.__file__).resolve() == tree / "app.py"
    observer = load("official_tail_observers", tree / "tests/smoke_real_links.py")
    harness = load("official_tail_upload_harness", tree / "tests/smoke_real_asr_quality.py")
    events, current = [], [None]
    output = Path(remaining[remaining.index("--output") + 1]).resolve()
    event_path = output.with_suffix(".events.jsonl")
    if output.exists() or event_path.exists():
        raise ValueError("Choose a new evidence output; preserve previous runs.")
    output.parent.mkdir(parents=True, exist_ok=True)

    def event(kind, **fields):
        fields.setdefault("job_id", current[0])
        item = {"at": observer.now(), "kind": kind, **fields}
        events.append(item)
        with event_path.open("a") as handle:
            handle.write(json.dumps(item, ensure_ascii=True, allow_nan=False) + "\n")

    whisper = importlib.import_module("faster_whisper.transcribe")
    observer.observe_audio_decode(importlib.import_module("faster_whisper.audio"), event)
    observer.observe_audio_decode(whisper, event)
    observer.observe_transcribe(whisper, event, lambda: current[0])
    observer.observe_segment_creation(whisper, event, lambda: current[0])
    observer.observe_model_resolution(whisper, event, lambda: current[0])
    observer.observe_whole_recording_speech(importlib.import_module("faster_whisper.vad"), event, lambda: current[0])
    original = app._recognize

    @functools.wraps(original)
    def recognize(path, *values, **options):
        current[0] = Path(path).parent.name
        assert sha(path) == plan["source_identity"]["media_sha256"]
        ctranslate2.set_random_seed(plan["qa_random_seed"])
        started = time.monotonic()
        event("recognition_start", audio_sha256=sha(path), qa_random_seed=plan["qa_random_seed"])
        result = original(path, *values, **options)
        event("recognition_done", segment_count=len(result[0]), language=result[1],
              elapsed_seconds=round(time.monotonic() - started, 3))
        return result

    app._recognize = recognize
    checkpoint = harness.checkpoint

    def observed_checkpoint(path, report):
        report["official_tail_protocol"] = {"arm": args.arm, "plan_sha256": sha(args.plan),
            "runner_sha256": sha(__file__), "qa_random_seed": plan["qa_random_seed"],
            "provider_gate_exercised": False, "reference_supplied_to_decoder": False,
            "production_options_changed_by_wrapper": False, "events": events}
        if any(item["kind"] == "recognition_done" for item in events):
            evidence = observer.transcription_evidence(events)
            assert evidence["decoded_array"]["pcm_sha256"] == plan["source_identity"]["pcm_sha256"]
            assert evidence["decoded_array"]["sample_count"] == plan["source_identity"]["sample_count"]
            assert evidence["normal_explicit_transcribe_kwargs"]["vad_filter"] is False
            report["official_tail_protocol"]["complete_audio_evidence"] = evidence
        return checkpoint(path, report)

    harness.checkpoint = observed_checkpoint
    sys.argv = [sys.argv[0], *remaining]
    return harness.main()


if __name__ == "__main__":
    raise SystemExit(main())

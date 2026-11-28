"""Actual ASR word evidence and downstream alignment contract, without voices.

The recognizer is real and receives word_timestamps=True, as requested by the
speakers=True application branch. The existing alignment function is exercised
with no acoustic turns, so every word must remain unassigned. This is not a new
speaker-model inference or speaker accuracy result.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve previous evidence; choose a new output file.")
    tree = args.source_root.resolve()
    sys.path.insert(0, str(tree))
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import ctranslate2
    import app
    import enhancements
    assert Path(app.__file__).resolve() == tree / "app.py"
    spec = importlib.util.spec_from_file_location("speaker_word_observers", tree / "tests/smoke_real_links.py")
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    wanted = {"fleurs-en_us-validation-0-1548", "fleurs-el_gr-validation-2-1528-quiet-minus20db"}
    cases = [case for case in manifest["cases"] if case["id"] in wanted]
    assert len(cases) == len(wanted)
    current, events = [None], []
    report = {"schema_version": 1, "complete": False, "started_at": observer.now(),
              "acoustic_speaker_inference_rerun": False, "reference_supplied_to_decoder": False,
              "alignment_scope": "No acoustic turns supplied: validate actual words and preserve text, with Unknown speaker labels.",
              "qa_random_seed": 1729, "probe_sha256": sha(__file__),
              "source_sha256": {name: sha(tree / name) for name in ("app.py", "enhancements.py")},
              "manifest_sha256": sha(args.manifest), "cases": []}

    def event(kind, **fields):
        events.append({"kind": kind, "case_id": current[0], **fields})

    whisper = importlib.import_module("faster_whisper.transcribe")
    observer.observe_model_resolution(whisper, event, lambda: current[0])
    observer.observe_transcribe(whisper, event, lambda: current[0])
    observer.observe_segment_creation(whisper, event, lambda: current[0])
    for case in cases:
        current[0] = case["id"]
        audio = args.manifest.parent / case["audio_file"]
        assert sha(audio) == case["audio_sha256"]
        ctranslate2.set_random_seed(1729)
        segments, language = app._recognize(audio, "auto", "small", word_timestamps=True)
        assert segments and all(isinstance(segment.get("_words"), list) and segment["_words"]
                                for segment in segments), "Actual private word evidence was lost."
        labeled, warnings, timed_segments = enhancements._word_speaker_alignment(segments, [])
        normalize = lambda items: " ".join(" ".join(item["text"].split()) for item in items)
        assert normalize(labeled) == normalize(segments), "Alignment changed recognized text."
        assert timed_segments > 0, "No actual word timings survived validation."
        assert all(item["speaker"] == "Unknown speaker" and "_words" not in item for item in labeled)
        report["cases"].append({"id": case["id"], "audio_sha256": case["audio_sha256"],
                                "language": language, "actual_asr_segments": segments,
                                "aligned_segments": labeled, "alignment_warnings": warnings,
                                "segments_with_validated_word_times": timed_segments,
                                "recognized_words_preserved": True,
                                "all_labels_unknown_without_acoustic_evidence": True})
    report.update(complete=True, finished_at=observer.now(), events=events,
                  source_files_unchanged=report["source_sha256"] == {
                      name: sha(tree / name) for name in report["source_sha256"]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    observer.write_json(args.output, report)
    print(json.dumps({"complete": report["complete"], "cases": len(cases),
                      "acoustic_speaker_inference_rerun": False, "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

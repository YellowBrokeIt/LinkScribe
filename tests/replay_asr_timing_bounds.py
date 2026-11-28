"""Replay retained native outputs through current timing/storage/export code.

This decodes the original local WAV files once, but substitutes the already
recorded native ASR outputs. It performs no model loading or acoustic inference.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import library
import library_backup


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def milliseconds(value):
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value)
    assert match
    h, m, s, ms = map(int, match.groups())
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    artifact = ROOT / "docs/large-v3-hosted-results-2026-11-28/artifact"
    source_report = artifact / "recognizer-report.json"
    assert sha(source_report) == "26098ab9a14bc328d7c9aea77e43defadbec57d1055f8190976ecd492fc6485f"
    source = json.loads(source_report.read_text(encoding="utf-8"))
    audio_module = importlib.import_module("faster_whisper.audio")
    real_decode = audio_module.decode_audio
    source_hash = sha(ROOT / "app.py")
    result = {"created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Actual original WAV decode plus recorded-output replay through current timing, SQLite, exports and backup restoration. No new recognition or semantic evaluation.",
        "model_loaded": False, "acoustic_inference_performed": False,
        "historical_run_id": 46102019808, "historical_commit": source["commit"],
        "historical_report_sha256": sha(source_report), "current_app_sha256": source_hash,
        "replay_script_sha256": sha(__file__), "complete": False, "cases": []}
    database = args.output / "replay-library.sqlite3"
    saved_records = {}
    with patch.object(library, "DB_FILE", database), patch.object(app, "DATA_DIR", args.output / "jobs"), \
            patch.dict(app.jobs, {}, clear=True):
        for case in source["cases"]:
            calls, decoded = [], []
            native = []
            for segment in case["raw_segments"]:
                item = deepcopy(segment)
                if item.get("words") is not None:
                    item["words"] = [SimpleNamespace(**word) for word in item["words"]]
                native.append(SimpleNamespace(**item))

            def observe_decode(path, sampling_rate):
                waveform = real_decode(path, sampling_rate=sampling_rate)
                decoded.append({"sample_count": len(waveform), "dtype": waveform.dtype.str,
                    "pcm_sha256": hashlib.sha256(waveform.tobytes()).hexdigest(), "sampling_rate": sampling_rate})
                return waveform

            class RecordedEngine:
                def transcribe(self, waveform, **options):
                    assert len(waveform) == case["sample_count"]
                    assert hashlib.sha256(waveform.tobytes()).hexdigest() == case["pcm_sha256"]
                    calls.append(options)
                    return iter(native), SimpleNamespace(language=case["detected_language"])

            with patch.object(audio_module, "decode_audio", observe_decode), \
                    patch.object(app, "_whisper_model", lambda _: RecordedEngine()):
                segments, language = app._recognize(artifact / "inputs" / (case["id"] + ".wav"),
                                                    "auto", "large-v3", word_timestamps=False)
            assert len(decoded) == len(calls) == 1
            assert decoded[0]["pcm_sha256"] == case["pcm_sha256"]
            assert calls[0] == case["actual_transcribe_request"]
            expected = deepcopy(case["production_segments"])
            if case["id"] == "fleurs-en_us-validation-0-1548":
                assert expected[0]["end"] == 7.0
                expected[0]["end"] = 6.54
            assert segments == expected
            identifier = hashlib.sha256(case["id"].encode()).hexdigest()[:32]
            directory = args.output / "cases" / case["id"]
            directory.mkdir(parents=True)
            job = app.Job(id=identifier, workdir=directory, source="retained-native-output:" + case["id"], title=case["id"])
            app.jobs[identifier] = job
            app._write_exports(identifier, segments, language, "retained_output_timing_replay", processing_metadata={
                "replay": {"historical_run": 46102019808, "acoustic_inference_performed": False}})
            saved = library.get(identifier)
            assert saved["segments"] == segments and job.status == "done"
            exported = json.loads((directory / "transcript.json").read_text(encoding="utf-8"))
            assert exported["segments"] == segments
            saved_records[identifier] = saved
            row = {"id": case["id"], "library_id": identifier, "decoded": decoded[0],
                "decode_calls": len(decoded), "recorded_engine_calls": len(calls), "actual_options": calls[0],
                "all_request_options_equal_historical": True, "text_and_order_unchanged": True,
                "historical_segments": case["production_segments"], "current_segments": segments,
                "source_duration_samples": case["sample_count"], "source_duration_seconds": case["sample_count"] / 16000,
                "saved_and_json_export_equal": True, "exports": {}}
            for fmt in ("srt", "vtt"):
                path = directory / ("transcript." + fmt)
                cues = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    if " --> " in line:
                        start, end = map(milliseconds, line.split(" --> "))
                        assert 0 <= start < end <= case["sample_count"] // 16
                        cues.append({"start_ms": start, "end_ms": end})
                assert len(cues) == len(segments)
                row["exports"][fmt] = {"sha256": sha(path), "cues": cues, "all_inside_physical_millisecond_bound": True}
            result["cases"].append(row)
        archive, count = library_backup.make_backup()
        assert count == len(saved_records) == 8
        (args.output / "backup.zip").write_bytes(archive)
        with patch.object(library, "DB_FILE", args.output / "restored-library.sqlite3"):
            restored = library_backup.restore_backup(archive)
            assert restored["imported"] == 8
            for identifier, original in saved_records.items():
                assert library.get(identifier) == original
        result["backup_records"] = count
        result["all_eight_restored_records_exactly_match"] = True
    assert sha(ROOT / "app.py") == source_hash and sha(source_report) == result["historical_report_sha256"]
    result["complete"] = True
    result["source_and_original_evidence_unchanged_during_replay"] = True
    (args.output / "replay-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(result["cases"]), "complete": True, "model_loaded": False,
                      "acoustic_inference_performed": False, "app_sha256": source_hash,
                      "report_sha256": sha(args.output / "replay-report.json")}))


if __name__ == "__main__":
    main()

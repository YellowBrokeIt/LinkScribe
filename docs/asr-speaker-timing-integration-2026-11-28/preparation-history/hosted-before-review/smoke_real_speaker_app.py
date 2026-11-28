#!/usr/bin/env python3
"""Actual upload -> Whisper -> public speakers -> SQLite -> exports smoke.

Uses an isolated QA database and real model calls. No models are downloaded by
this harness itself. Optional --target/--summary also require the actual selected
local backends. Peak RSS describes this process, not an external Ollama process.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from functools import wraps
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import uuid
import weakref

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
    names = ("app.py", "asr_timing.py", "enhancements.py", "diarization.py", "library.py", "library_backup.py",
             "batch_store.py", "tests/smoke_real_speaker_app.py")
    report = {"schema_version": 1, "complete": False, "created_utc": datetime.now(timezone.utc).isoformat(),
              "audio": {"path": str(args.audio.resolve()), "sha256": sha(args.audio)},
              "source_sha256": {name: sha(ROOT / name) for name in names},
              "run_directory": str(run_dir.resolve()), "actual_recognizer_calls": [],
              "actual_transcribe_calls": [], "fixed_text_timing_calls": [],
              "timing_encode_calls": [], "native_align_calls": [],
              "audio_model_release_calls": [],
              "acoustic_analysis_calls": [], "speaker_decode_calls": [],
              "model_initializations": [], "model_resolutions": [],
              "phase": {"name": "initialization", "started_monotonic": started},
              "phases": [{"name": "initialization", "started_monotonic": started}],
              "actual_speaker_calls": [], "semantic_quality": "unreviewed",
              "label_count_scope": "Execution check only; label count does not establish speaker attribution accuracy.",
              "memory_scope": "Linux peak RSS of this app/ASR/speaker process; excludes external Ollama and other processes."}
    save(args.output, report)
    application = None
    original_recognize = original_speakers = None
    original_transcribe = original_timing = original_encode = original_align = None
    original_release = None
    original_init = original_download = None
    original_analysis = original_speaker_decode = None
    native_class = timing_module = None
    native_module = None
    enhancements_module = diarization_module = None
    timing_active = False
    recognizer_refs = []
    try:
        from fastapi.testclient import TestClient
        import app as application
        import asr_timing as timing_module
        import library
        import enhancements as enhancements_module
        import diarization as diarization_module
        from faster_whisper import WhisperModel as native_class
        native_module = importlib.import_module("faster_whisper.transcribe")
        application.DATA_DIR = run_dir / "jobs"
        application.DATA_DIR.mkdir()
        library.DB_FILE = run_dir / "library.sqlite3"
        original_recognize = application._recognize
        original_speakers = application.assign_speakers
        original_transcribe = native_class.transcribe
        original_encode = native_class.encode
        original_timing = timing_module.align_fixed_segments
        original_align = timing_module._AlignOnly.align
        original_release = application._release_audio_models
        original_init = native_class.__init__
        original_download = native_module.download_model
        original_analysis = enhancements_module._public_speaker_analysis
        original_speaker_decode = diarization_module.decode_mono

        def phase(name):
            moment = time.monotonic()
            report["phases"][-1]["elapsed_seconds"] = moment - report["phases"][-1]["started_monotonic"]
            report["phase"] = {"name": name, "started_monotonic": moment}
            report["phases"].append(dict(report["phase"]))
            save(args.output, report)

        @wraps(original_speaker_decode)
        def observe_speaker_decode(path, *decode_args, **kwargs):
            audio = original_speaker_decode(path, *decode_args, **kwargs)
            report["speaker_decode_calls"].append({"source_sha256": sha(path), "waveform": waveform_identity(audio)})
            save(args.output, report)
            return audio

        @wraps(original_analysis)
        def observe_analysis(path):
            call = {"source_sha256": sha(path), "completed": False}
            report["acoustic_analysis_calls"].append(call)
            save(args.output, report)
            result = original_analysis(path)
            # Anonymous acoustic turns/settings only; the backend result exposes
            # no audio or voice-embedding vectors. References never reach it.
            call.update(completed=True, result=deepcopy(result))
            save(args.output, report)
            return result

        @wraps(original_init)
        def observe_init(engine, *init_args, **kwargs):
            bound = inspect.signature(original_init).bind(engine, *init_args, **kwargs)
            bound.apply_defaults()
            call = {"model": bound.arguments["model_size_or_path"],
                    "cpu_threads": bound.arguments["cpu_threads"], "num_workers": bound.arguments["num_workers"],
                    "requested_device": bound.arguments["device"], "requested_compute_type": bound.arguments["compute_type"],
                    "completed": False}
            report["model_initializations"].append(call)
            save(args.output, report)
            original_init(engine, *init_args, **kwargs)
            call.update(completed=True, engine_identity=hex(id(engine)), native_identity=hex(id(engine.model)),
                        actual_device=engine.model.device, actual_compute_type=engine.model.compute_type,
                        feature_rows=engine.model.n_mels)
            save(args.output, report)

        @wraps(original_download)
        def observe_resolution(*download_args, **kwargs):
            path = original_download(*download_args, **kwargs)
            report["model_resolutions"].append({"requested_model": download_args[0], "path": str(path),
                "revision_directory": Path(path).name,
                "files": {name: {"bytes": (Path(path) / name).stat().st_size, "sha256": sha(Path(path) / name)}
                          for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")}})
            save(args.output, report)
            return path

        def waveform_identity(audio):
            return {"shape": list(audio.shape), "dtype": str(audio.dtype), "sample_count": len(audio),
                    "sha256": hashlib.sha256(audio.tobytes()).hexdigest()}

        @wraps(original_transcribe)
        def observe_transcribe(engine, audio, *transcribe_args, **kwargs):
            recognizer_refs.append(weakref.ref(engine))
            phase("recognition")
            call = {"options": deepcopy(kwargs), "waveform": waveform_identity(audio), "raw_segments": [],
                    "engine_identity": hex(id(engine))}
            report["actual_transcribe_calls"].append(call)
            save(args.output, report)
            segments, info = original_transcribe(engine, audio, *transcribe_args, **kwargs)
            call["effective_options"] = asdict(info.transcription_options)
            call["detected_language"] = info.language
            def consumed():
                for segment in segments:
                    call["raw_segments"].append({"start": segment.start, "end": segment.end,
                        "text": segment.text, "seek": segment.seek, "tokens": list(segment.tokens)})
                    yield segment
                call["generator_exhausted"] = True
            return consumed(), info

        @wraps(original_encode)
        def observe_encode(engine, features):
            if timing_active:
                report["timing_encode_calls"].append({"feature_shape": list(features.shape),
                    "feature_sha256": hashlib.sha256(features.tobytes()).hexdigest()})
                save(args.output, report)
            return original_encode(engine, features)

        @wraps(original_align)
        def observe_align(guard, encoded, start_sequence, text_tokens, num_frames, **kwargs):
            call = {"start_sequence": list(start_sequence), "text_tokens": deepcopy(text_tokens),
                    "num_frames": num_frames, "options": kwargs, "completed": False}
            report["native_align_calls"].append(call)
            save(args.output, report)
            result = original_align(guard, encoded, start_sequence, text_tokens, num_frames, **kwargs)
            call.update(completed=True, native_results=[{"alignments": list(item.alignments),
                        "text_token_probs": list(item.text_token_probs)} for item in result])
            save(args.output, report)
            return result

        @wraps(original_timing)
        def observe_timing(engine, audio, language, baseline, raw_segments, **kwargs):
            nonlocal timing_active
            phase("speaker_timing")
            call = {"language": language, "waveform": waveform_identity(audio),
                    "baseline_segments": deepcopy(baseline), "raw_segments": deepcopy(raw_segments),
                    "engine_identity": hex(id(engine)), "completed": False}
            report["fixed_text_timing_calls"].append(call)
            save(args.output, report)
            timing_active = True
            try:
                result = original_timing(engine, audio, language, baseline, raw_segments, **kwargs)
                call.update(completed=True, segments=result.segments, warnings=result.warnings,
                            provenance=result.provenance)
                save(args.output, report)
                return result
            finally:
                timing_active = False

        def observe_recognize(*call_args, **call_kwargs):
            result = original_recognize(*call_args, **call_kwargs)
            report["actual_recognizer_calls"].append({"language_requested": call_args[1], "model": call_args[2],
                                                     "options": call_kwargs, "detected_language": result.language,
                                                     "segments": result.segments, "speaker_segments": result.speaker_segments,
                                                     "warnings": result.warnings, "asr_provenance": result.asr_provenance})
            save(args.output, report)
            return result

        def observe_speakers(*call_args, **call_kwargs):
            inputs = deepcopy(call_args[1])
            assert application._whisper_model.cache_info().currsize == 0, "Recognition cache remains resident before speakers"
            assert recognizer_refs and all(ref() is None for ref in recognizer_refs), "Recognizer object survived release"
            phase("speakers")
            result = original_speakers(*call_args, **call_kwargs)
            report["actual_speaker_calls"].append({"include_report": call_kwargs.get("include_report"),
                                                 "input_segments": inputs, "recognizer_released_before_call": True,
                                                 "result": result})
            save(args.output, report)
            phase("persistence")
            return result

        @wraps(original_release)
        def observe_release(**kwargs):
            def cached_models():
                counts = {"recognizer": application._whisper_model.cache_info().currsize}
                for module_name, function_name, label in (("diarization", "_encoder", "speaker"),
                                                          ("faster_whisper.vad", "get_vad_model", "vad")):
                    cached = getattr(sys.modules.get(module_name), function_name, None)
                    info = getattr(cached, "cache_info", None)
                    counts[label] = info().currsize if callable(info) else None
                return counts
            before = cached_models()
            original_release(**kwargs)  # Observe production clearing; do not clear in the harness.
            after = cached_models()
            report["audio_model_release_calls"].append({"options": kwargs, "before": before, "after": after,
                "recognizer_references_released": bool(recognizer_refs) and all(ref() is None for ref in recognizer_refs)})
            if kwargs.get("recognizer_only"):
                assert after["recognizer"] == 0 and before["speaker"] == after["speaker"] and before["vad"] == after["vad"]
            save(args.output, report)

        application._recognize = observe_recognize
        application.assign_speakers = observe_speakers
        application._release_audio_models = observe_release
        native_class.transcribe = observe_transcribe
        native_class.__init__ = observe_init
        native_module.download_model = observe_resolution
        native_class.encode = observe_encode
        timing_module.align_fixed_segments = observe_timing
        timing_module._AlignOnly.align = observe_align
        enhancements_module._public_speaker_analysis = observe_analysis
        diarization_module.decode_mono = observe_speaker_decode
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
            assert report["actual_recognizer_calls"][0]["options"]["speaker_timing"] is True
            assert len(report["actual_transcribe_calls"]) == len(report["fixed_text_timing_calls"]) == 1
            recognition_call, timing_call = report["actual_transcribe_calls"][0], report["fixed_text_timing_calls"][0]
            assert recognition_call["options"]["word_timestamps"] is False
            assert recognition_call["effective_options"]["word_timestamps"] is False
            assert recognition_call["generator_exhausted"] and timing_call["completed"]
            assert timing_call["waveform"] == recognition_call["waveform"]
            assert len(report["model_initializations"]) == len(report["model_resolutions"]) == 1
            assert report["model_initializations"][0]["completed"]
            assert timing_call["engine_identity"] == recognition_call["engine_identity"] == report["model_initializations"][0]["engine_identity"]
            assert timing_call["raw_segments"] == [s for s in recognition_call["raw_segments"] if s["text"].strip()]
            assert timing_call["baseline_segments"] == report["actual_recognizer_calls"][0]["segments"]
            assert timing_call["segments"] == report["actual_speaker_calls"][0]["input_segments"]
            assert timing_call["provenance"]["word_timed_segments"] > 0
            assert len(report["timing_encode_calls"]) == len(report["native_align_calls"]) > 0
            assert all(call["completed"] for call in report["native_align_calls"])
            assert record["processing_metadata"]["asr"]["word_timestamps"] is False
            assert record["processing_metadata"]["asr"]["speaker_timing"] == timing_call["provenance"]
            assert report["audio_model_release_calls"][0]["options"] == {"recognizer_only": True}
            assert report["audio_model_release_calls"][0]["recognizer_references_released"]
            assert len(report["acoustic_analysis_calls"]) == len(report["speaker_decode_calls"]) == 1
            assert report["acoustic_analysis_calls"][0]["completed"]
            assert report["speaker_decode_calls"][0]["source_sha256"] == report["audio"]["sha256"]
            assert report["speaker_decode_calls"][0]["waveform"] == recognition_call["waveform"]
            before = " ".join(" ".join(item["text"].split()) for item in report["actual_recognizer_calls"][0]["segments"])
            after = " ".join(" ".join(item["text"].split()) for item in record["segments"])
            assert before == after, "Speaker alignment lost or changed recognized words."
            assert all("_words" not in item for item in record["segments"])
            labels = sorted({item["speaker"] for item in record["segments"] if item.get("speaker") != "Unknown speaker"})
            assert len(labels) >= 2, "The selected fixture did not produce two distinct labels (execution check only)."
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
            # Read the actual stored row in a fresh, stdlib-only process. This
            # proves reload independently of the in-process library connection.
            reload_code = """import json, sqlite3, sys
from pathlib import Path
with sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    row = dict(db.execute('SELECT * FROM transcripts WHERE id=?', (sys.argv[2],)).fetchone())
for key in ('segments', 'translations', 'summary', 'highlights', 'processing_metadata'):
    row[key] = json.loads(row[key]) if row[key] is not None else None
print(json.dumps(row, ensure_ascii=True))
"""
            reloaded = subprocess.run([sys.executable, "-c", reload_code, str(library.DB_FILE), identifier],
                                      capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
            fresh_record = json.loads(reloaded.stdout)
            assert fresh_record == record, "Fresh-process SQLite row differs from the accepted saved result."
            report["separate_process_sqlite"] = {"record": fresh_record, "matches_saved_record": True,
                                                 "model_imports_or_calls": False}
            backup = client.get("/api/library/backup")
            assert backup.status_code == 200
            (run_dir / "library-backup.zip").write_bytes(backup.content)
            report.update({"complete": True, "record": record, "known_speaker_labels": labels,
                           "exports": exports, "recognized_words_preserved": True,
                           "durable_download_after_job_eviction": True})
            phase("complete")
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
            if original_release is not None:
                application._release_audio_models = original_release
        if original_transcribe is not None:
            native_class.transcribe = original_transcribe
        if original_encode is not None:
            native_class.encode = original_encode
        if original_timing is not None:
            timing_module.align_fixed_segments = original_timing
        if original_align is not None:
            timing_module._AlignOnly.align = original_align
        if original_init is not None:
            native_class.__init__ = original_init
        if original_download is not None:
            native_module.download_model = original_download
        if original_analysis is not None:
            enhancements_module._public_speaker_analysis = original_analysis
        if original_speaker_decode is not None:
            diarization_module.decode_mono = original_speaker_decode
        report["elapsed_seconds"] = time.monotonic() - started
        report["phases"][-1]["elapsed_seconds"] = time.monotonic() - report["phases"][-1]["started_monotonic"]
        report["peak_process_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        report["peak_process_rss_mib"] = round(report["peak_process_rss_bytes"] / 1048576, 1)
        save(args.output, report)
    print(json.dumps({key: report.get(key) for key in ("complete", "elapsed_seconds", "peak_process_rss_mib", "error")}), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

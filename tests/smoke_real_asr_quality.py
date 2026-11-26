"""Opt-in native-speech QA through the real upload, SQLite and export workflow.

This is not part of the fast mocked test suite. Supply a manifest containing
licensed, fixed-before-inference audio samples and references. References are
used only after recognition to compute diagnostic word-edit counts; they are
never passed to Whisper. No model calls or production processing are mocked.

Example (prepare the model cache separately before an offline run)::

    HF_HOME=/path/to/qa/hf-cache HF_HUB_OFFLINE=1 LINKSCRIBE_DEVICE=cpu \
      .venv/bin/python tests/smoke_real_asr_quality.py \
      --manifest /path/to/qa/fixtures.json --output /path/to/qa/small-result.json

Omitting --model intentionally omits the upload model form field and exercises
the application's default. Structural pass never certifies transcript meaning.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import inspect
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import sqlite3
import subprocess
import sys
import time
import unicodedata
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def checkpoint(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalized_words(text: str, *, ignore_diacritics: bool = False) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    if ignore_diacritics:
        text = "".join(c for c in unicodedata.normalize("NFD", text)
                       if unicodedata.category(c) != "Mn")
    # Delete punctuation rather than split abbreviations such as U.N. into U/N.
    text = "".join(c for c in text if unicodedata.category(c)[0] not in {"P", "S"})
    return text.split()


def word_edits(reference: str, hypothesis: str, *, ignore_diacritics: bool = False) -> dict:
    """Levenshtein word edits with a reproducible alignment, not a quality gate."""
    expected = normalized_words(reference, ignore_diacritics=ignore_diacritics)
    actual = normalized_words(hypothesis, ignore_diacritics=ignore_diacritics)
    costs = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    for i in range(len(expected) + 1):
        costs[i][0] = i
    for j in range(len(actual) + 1):
        costs[0][j] = j
    for i, source in enumerate(expected, 1):
        for j, target in enumerate(actual, 1):
            costs[i][j] = min(costs[i - 1][j] + 1, costs[i][j - 1] + 1,
                              costs[i - 1][j - 1] + (source != target))
    i, j = len(expected), len(actual)
    alignment = []
    while i or j:
        if i and j and costs[i][j] == costs[i - 1][j - 1] + (expected[i - 1] != actual[j - 1]):
            operation = "equal" if expected[i - 1] == actual[j - 1] else "substitution"
            alignment.append({"operation": operation, "reference": expected[i - 1], "hypothesis": actual[j - 1]})
            i -= 1
            j -= 1
        elif i and costs[i][j] == costs[i - 1][j] + 1:
            alignment.append({"operation": "deletion", "reference": expected[i - 1], "hypothesis": ""})
            i -= 1
        else:
            alignment.append({"operation": "insertion", "reference": "", "hypothesis": actual[j - 1]})
            j -= 1
    changes = [entry for entry in reversed(alignment) if entry["operation"] != "equal"]
    counts = Counter(entry["operation"] for entry in changes)
    return {"reference_words": len(expected), "hypothesis_words": len(actual),
            "substitutions": counts["substitution"], "deletions": counts["deletion"],
            "insertions": counts["insertion"], "word_errors": costs[-1][-1],
            "word_error_rate": costs[-1][-1] / len(expected) if expected else None,
            "edits": changes}


def media_details(path: Path) -> dict:
    import av
    with av.open(str(path)) as media:
        audio = media.streams.audio[0]
        seconds = float(media.duration / av.time_base) if media.duration is not None else float(audio.duration * audio.time_base)
        assert math.isfinite(seconds) and seconds > 0, "Invalid media duration"
        return {"duration_seconds": seconds, "container": media.format.name,
                "codec": audio.codec_context.name, "sample_rate": audio.rate,
                "channels": audio.channels}


def checked_response(response):
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:500]}"
    return response


def subtitle_cues(payload: bytes) -> list[tuple[float, float, str]]:
    def seconds(value: str) -> float:
        hours, minutes, remainder = value.replace(",", ".").split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(remainder)
    text = payload.decode("utf-8").replace("\r\n", "\n")
    pattern = re.compile(r"(?m)^(\d{2,}:\d{2}:\d{2}[.,]\d{3}) --> (\d{2,}:\d{2}:\d{2}[.,]\d{3})\n([^\n]*(?:\n(?!\n)[^\n]+)*)")
    return [(seconds(a), seconds(b), words.strip()) for a, b, words in pattern.findall(text)]


def check_exports(client, identifier: str, record: dict, duration: float, output_dir: Path) -> dict:
    segments = record["segments"]
    payloads = {fmt: checked_response(client.get(f"/api/library/{identifier}/download/{fmt}")).content
                for fmt in ("txt", "srt", "vtt", "json", "zip")}
    expected_texts = [segment["text"].strip().replace("\r", " ").replace("\n", " ") for segment in segments]
    assert payloads["txt"].decode("utf-8").splitlines() == expected_texts, "TXT changed stored words"
    exported = json.loads(payloads["json"])
    assert exported["segments"] == segments, "JSON changed stored segments"
    assert all(exported[key] == record[key] for key in ("source", "title", "language", "method"))
    assert payloads["vtt"].startswith(b"WEBVTT\n\n"), "Missing WebVTT header"
    for fmt in ("srt", "vtt"):
        cues = subtitle_cues(payloads[fmt])
        assert len(cues) == len(segments), f"{fmt}: incorrect cue count"
        for cue, segment, words in zip(cues, segments, expected_texts, strict=True):
            start, end, text = cue
            assert text == words, f"{fmt}: changed words"
            assert abs(start - segment["start"]) <= 0.0011, f"{fmt}: changed start"
            assert segment["end"] - 0.0011 <= end <= max(segment["end"], segment["start"] + 0.1) + 0.0011
            assert start <= end <= duration + 1.0, f"{fmt}: invalid time range"
    with zipfile.ZipFile(io.BytesIO(payloads["zip"])) as archive:
        assert set(archive.namelist()) == {f"transcript.{fmt}" for fmt in ("txt", "srt", "vtt", "json")}
        assert all(archive.read(f"transcript.{fmt}") == payloads[fmt] for fmt in ("txt", "srt", "vtt", "json")), "ZIP members differ from individual exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    for fmt, payload in payloads.items():
        (output_dir / f"transcript.{fmt}").write_bytes(payload)
    return {fmt: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for fmt, payload in payloads.items()}


def run_case(client, application, library, case: dict, manifest_dir: Path, run_dir: Path,
             model_override: str | None, language_mode: str, timeout: float) -> dict:
    audio_path = (manifest_dir / case["audio_file"]).resolve()
    assert sha256(audio_path) == case["audio_sha256"], "Audio fingerprint changed"
    media = media_details(audio_path)
    result = {"id": case["id"], "language": case["language"], "audio_sha256": case["audio_sha256"],
              "media": media, "reference": case["reference"], "review_criteria": case.get("review_criteria", []),
              "requested_language": case["language"] if language_mode == "explicit" else "auto",
              "language_form_field_omitted": language_mode == "auto",
              "semantic_quality": "unreviewed", "structural_status": "incomplete"}
    started = time.monotonic()
    # Deliberately only audio and ordinary user options; no reference text.
    form = {"consent": "true", "target_language": "none",
            "speakers": "false", "summary": "false"}
    if language_mode == "explicit":
        form["language"] = case["language"]
    if model_override:
        form["model"] = model_override
    with audio_path.open("rb") as media_file:
        submitted = checked_response(client.post("/api/upload", files={"file": (audio_path.name, media_file, case.get("audio_mime", "audio/wav"))}, data=form)).json()
    identifier = submitted["id"]
    result["job_id"] = identifier
    try:
        deadline = time.monotonic() + timeout
        while True:
            job = checked_response(client.get(f"/api/jobs/{identifier}")).json()
            if job["status"] in {"done", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Real recognition did not finish within {timeout:g} seconds")
            time.sleep(0.25)
        result["job_result"] = job
        assert job["status"] == "done", job.get("error") or job
        record = checked_response(client.get(f"/api/library/{identifier}")).json()
        segments = record["segments"]
        result["segments"] = segments
        hypothesis = " ".join(segment["text"] for segment in segments)
        result["hypothesis"] = hypothesis
        result["word_metrics"] = word_edits(case["reference"], hypothesis)
        result["diacritic_insensitive_word_metrics"] = word_edits(case["reference"], hypothesis, ignore_diacritics=True)
        assert record["language"] == case["language"], "Incorrect recognized language"
        assert record["method"] == "local_audio_ai" and not record.get("translations") and not record.get("summary")
        assert segments and all(isinstance(s["text"], str) and s["text"].strip() for s in segments)
        previous_end = 0.0
        for segment in segments:
            start, end = segment["start"], segment["end"]
            assert isinstance(start, (int, float)) and isinstance(end, (int, float))
            assert math.isfinite(start) and math.isfinite(end)
            assert 0 <= start <= end <= media["duration_seconds"] + 1.0, "Out-of-range segment time"
            assert start >= previous_end - 0.001, "Segments overlap or are out of order"
            previous_end = end
        with sqlite3.connect(library.DB_FILE) as database:
            row = database.execute("SELECT segments,plain_text,language,method FROM transcripts WHERE id=?", (identifier,)).fetchone()
        assert row and json.loads(row[0]) == segments, "SQLite lost or changed recognized segments"
        assert row[1] == "\n".join(s["text"].strip().replace("\n", " ") for s in segments)
        assert row[2:] == (case["language"], "local_audio_ai")
        result["exports"] = check_exports(client, identifier, record, media["duration_seconds"], run_dir / case["id"])
        # Job completion precedes the worker's cleanup finally block by a moment.
        cleanup_deadline = time.monotonic() + 5
        workdir = application.jobs[identifier].workdir
        while list(workdir.glob("input.*")) and time.monotonic() < cleanup_deadline:
            time.sleep(0.05)
        assert not list(workdir.glob("input.*")), "Uploaded input audio was not cleaned"
        with application.lock:
            application.jobs.pop(identifier)
        assert client.get(f"/api/jobs/{identifier}").status_code == 404
        restored = checked_response(client.get(f"/api/library/{identifier}")).json()
        assert restored["segments"] == segments, "Library depended on in-memory job"
        persisted_txt = checked_response(client.get(f"/api/library/{identifier}/download/txt")).content
        assert hashlib.sha256(persisted_txt).hexdigest() == result["exports"]["txt"]["sha256"]
        result["checks"] = {"real_upload_and_recognition": True, "finite_ordered_timestamps": True,
                            "sqlite_exact_segments": True, "all_five_exports": True,
                            "archive_members_match_exports": True, "library_survives_job_eviction": True,
                            "uploaded_audio_cleaned": True}
        result["structural_status"] = "pass"
    except Exception as error:
        result["structural_status"] = "error"
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["process_peak_rss_bytes_so_far"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=("tiny", "base", "small", "large-v3-turbo"), help="Omit to exercise the app's actual default")
    parser.add_argument("--model-provenance", type=Path, help="Model snapshot/file evidence; defaults to manifest-directory/model-provenance.json")
    parser.add_argument("--language-mode", choices=("explicit", "auto"), default="explicit",
                        help="explicit supplies each fixture language; auto omits the form field to exercise app language detection")
    parser.add_argument("--timeout", type=float, default=600, help="Per-clip timeout in seconds")
    args = parser.parse_args()
    manifest_path, output_path = args.manifest.resolve(), args.output.resolve()
    if output_path.exists():
        parser.error("Output already exists; choose a new evidence filename")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    assert cases and len({case["id"] for case in cases}) == len(cases), "Empty or duplicate fixture IDs"
    for case in cases:
        assert case["language"] in {"el", "en"} and case["reference"].strip()
        assert re.fullmatch(r"[a-zA-Z0-9_.-]+", case["id"]), "Unsafe fixture ID"
        assert sha256(manifest_path.parent / case["audio_file"]) == case["audio_sha256"]
    run_dir = output_path.parent / (output_path.stem + "-artifacts-" + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True)
    # Set startup opt-outs before ONNX Runtime or any model package imports.
    # The API call also covers runtimes supporting the older explicit control.
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    # Import once in this dedicated process, then isolate every persistent store
    # before the real FastAPI lifespan runs. batch_store also uses library's DB.
    from fastapi.testclient import TestClient
    import app as application
    import library
    application.DATA_DIR = run_dir / "jobs"
    application.DATA_DIR.mkdir()
    library.DB_FILE = run_dir / "library.sqlite3"
    assert not application.jobs and not application.batches, "Run in a fresh standalone process"
    default_model = inspect.signature(application.submit_upload).parameters["model"].default.default
    default_language = inspect.signature(application.submit_upload).parameters["language"].default.default
    assert (args.model or default_model) in application.MODELS, "The real app does not expose this model option"
    assert args.language_mode != "auto" or default_language == "auto", "App's omitted language field is no longer auto"
    sources = {name: sha256(ROOT / name) for name in ("app.py", "library.py", "batch_store.py", "tests/smoke_real_asr_quality.py")}
    versions = {}
    for name in ("faster-whisper", "ctranslate2", "av", "fastapi", "starlette", "huggingface-hub", "onnxruntime"):
        versions[name] = metadata.version(name)
    provenance_path = args.model_provenance or manifest_path.parent / "model-provenance.json"
    model_provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else None
    assert model_provenance is None or model_provenance["model"] == (args.model or default_model), "Provenance belongs to another model"
    report = {"schema_version": 1, "created_at": utc_now(), "complete": False,
              "semantic_quality": "unreviewed", "manifest_sha256": sha256(manifest_path),
              "manifest_path": str(manifest_path), "dataset": manifest.get("dataset"),
              "selection": manifest.get("selection"), "source_sha256": sources,
              "runtime": {"python": platform.python_version(), "packages": versions,
                          "device": os.getenv("LINKSCRIBE_DEVICE", "cpu"), "default_upload_model": default_model,
                          "model_override": args.model, "effective_model": args.model or default_model,
                          "language_mode": args.language_mode, "default_upload_language": default_language,
                          "language_form_field_omitted": args.language_mode == "auto",
                          "model_form_field_omitted": args.model is None, "model_provenance": model_provenance,
                          "HF_HOME": os.getenv("HF_HOME"), "offline": os.getenv("HF_HUB_OFFLINE") == "1",
                          "telemetry_opt_out": {"ORT_DISABLE_TELEMETRY": os.environ["ORT_DISABLE_TELEMETRY"],
                                                "HF_HUB_DISABLE_TELEMETRY": os.environ["HF_HUB_DISABLE_TELEMETRY"],
                                                "onnxruntime_disable_telemetry_events_called": True},
                          "recognizer_source": inspect.getsource(application._recognize),
                          "model_factory_source": inspect.getsource(application._whisper_model),
                          "reference_supplied_to_decoder": False},
              "measurement_notes": [
                  "Actual upload-to-export elapsed time includes initial model loading and polling; other QA may contend for CPU. This is not a controlled latency benchmark.",
                  "WER uses NFKC, casefold, punctuation/symbol deletion and whitespace tokens; a second score removes diacritics. Numeric words versus digits remain different tokens.",
                  "Word-edit counts and structural pass do not approve semantic fidelity, proper names, numerical values or negation. Review exact source references and uncorrected hypotheses separately.",
                  "Timestamp ordering/range is checked; no independently annotated word-timing reference is available.",
                  "Peak RSS is the maximum resident set of this QA process, including loaded model and application. It excludes other processes and is not a whole-machine or combined ASR/translation memory measurement.",
                  "Persistence checks query a new SQLite connection and evict in-memory jobs. A separate interpreter checks the final stored records; this is not a full browser/server-restart test."],
              "artifacts_directory": str(run_dir), "cases": []}
    checkpoint(output_path, report)
    started = time.monotonic()
    with TestClient(application.app) as client:
        for case in cases:
            print(f"Recognizing {case['id']} using {args.model or default_model}", flush=True)
            result = run_case(client, application, library, case, manifest_path.parent, run_dir, args.model, args.language_mode, args.timeout)
            report["cases"].append(result)
            checkpoint(output_path, report)
            print(json.dumps({"id": result["id"], "structural_status": result["structural_status"],
                              "elapsed_seconds": result["elapsed_seconds"], "hypothesis": result.get("hypothesis"),
                              "error": result.get("error")}, ensure_ascii=False), flush=True)
            if result.get("error", {}).get("type") == "TimeoutError":
                break
    # A separate process verifies that durable records do not rely on an open
    # Python connection or the application's in-memory jobs dictionary.
    verification_code = "import sqlite3,json,sys; c=sqlite3.connect(sys.argv[1]); print(json.dumps({r[0]:json.loads(r[1]) for r in c.execute('SELECT id,segments FROM transcripts')}))"
    verification = subprocess.run([sys.executable, "-c", verification_code, str(library.DB_FILE)], capture_output=True, text=True, timeout=30, check=True)
    persisted = json.loads(verification.stdout)
    report["separate_process_sqlite_matches"] = all(persisted.get(c.get("job_id")) == c["segments"] for c in report["cases"] if "segments" in c)
    report["source_sha256_after"] = {name: sha256(ROOT / name) for name in sources}
    report["source_files_unchanged_during_run"] = report["source_sha256_after"] == sources
    report["complete"] = len(report["cases"]) == len(cases)
    report["counts"] = dict(Counter(c["structural_status"] for c in report["cases"]))
    report["metrics_by_language"] = {}
    for language in ("el", "en"):
        completed = [c for c in report["cases"] if c["language"] == language and "word_metrics" in c]
        totals = {key: sum(c["word_metrics"][key] for c in completed) for key in ("reference_words", "word_errors", "substitutions", "deletions", "insertions")}
        totals["word_error_rate"] = totals["word_errors"] / totals["reference_words"] if totals["reference_words"] else None
        report["metrics_by_language"][language] = {"cases": len(completed), **totals}
    report["finished_at"] = utc_now()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    checkpoint(output_path, report)
    print(json.dumps({"output": str(output_path), "complete": report["complete"], "counts": report["counts"], "metrics_by_language": report["metrics_by_language"]}, ensure_ascii=False, indent=2), flush=True)
    return 0 if (report["complete"] and report["counts"] == {"pass": len(cases)}
                 and report["separate_process_sqlite_matches"] and report["source_files_unchanged_during_run"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Observe actual local summary inference, persistence and exports on owned text.

No model downloads, service startup or ASR is performed. A successful execution
checks plumbing and structure only; factual and language quality remain unreviewed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FORMATS = {"txt": "transcript.txt", "srt": "transcript.srt", "vtt": "transcript.vtt",
           "json": "transcript.json", "zip": "transcript.zip",
           "summary_md": "summary.md", "summary_json": "summary.json"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checkpoint(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, indent=2, ensure_ascii=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def safe_response(value):
    """Keep malformed non-finite outer JSON representable in a valid report."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_standard_json_number": repr(value)}
    if isinstance(value, dict):
        return {key: safe_response(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_response(item) for item in value]
    return value


def read_corpus(path, requested):
    raw = path.read_bytes()
    if len(raw) > 512 * 1024:
        raise ValueError("Summary corpus exceeds 512 KiB.")
    corpus = json.loads(raw)
    json.dumps(corpus, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if corpus.get("schema_version") != 1 or corpus.get("frozen") is not True:
        raise ValueError("Use a frozen schema_version 1 corpus.")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 16:
        raise ValueError("Expected 1–16 owned summary cases.")
    identifiers = set()
    for case in cases:
        identifier = case.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", identifier) or identifier in identifiers:
            raise ValueError("Case identifiers must be unique short ASCII names.")
        identifiers.add(identifier)
        if case.get("source_language") not in {"en", "el"}:
            raise ValueError("Summary QA cases must declare English or Greek source language.")
        segments = case.get("segments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= 100:
            raise ValueError("Each case needs 1–100 segments.")
        previous = -1
        for segment in segments:
            text, start, end = segment.get("text"), segment.get("start"), segment.get("end")
            if not isinstance(text, str) or not text.strip() or len(text) > 30000:
                raise ValueError("Invalid or oversized source text.")
            if (any(isinstance(number, bool) or not isinstance(number, (int, float))
                    or not math.isfinite(number) for number in (start, end))
                    or not 0 <= start <= end <= 7200 or start < previous):
                raise ValueError("Source timestamps must be finite, bounded and ordered.")
            previous = start
        if sum(len(item["text"]) for item in segments) > 50000:
            raise ValueError("A summary case exceeds 50,000 source characters.")
    if requested and (len(requested) != len(set(requested)) or set(requested) - identifiers):
        raise ValueError("--case identifiers must be known and unique.")
    selected = [case for case in cases if not requested or case["id"] in requested]
    return corpus, selected, sha(raw)


def source_identity(corpus):
    names = ("app.py", "enhancements.py", "library.py", "library_backup.py", "batch_store.py",
             "tests/evaluate_summary_quality.py")
    result = {"sha256": {name: sha((ROOT / name).read_bytes()) for name in names}}
    result["sha256"][str(corpus.resolve())] = sha(corpus.read_bytes())
    for key, command in (("git_commit", ["git", "rev-parse", "HEAD"]),
                         ("git_status", ["git", "status", "--porcelain"])):
        try:
            result[key] = subprocess.check_output(command, cwd=ROOT, text=True,
                                                  stderr=subprocess.DEVNULL, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            result[key] = None
    return result


def runtime_identity(enhancements):
    url, model = enhancements.ollama_settings()
    tags = enhancements.local_ollama_json("/api/tags")
    canonical = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
    selected = next((item for item in tags.get("models", [])
                     if item.get("name") in {model, canonical} or item.get("model") in {model, canonical}), None)
    if not selected or not selected.get("digest"):
        raise ValueError("The configured summary model is not installed with an identifiable digest.")
    return {"url": url, "configured_model": model, "model": selected,
            "version": enhancements.local_ollama_json("/api/version"),
            "inference_options": enhancements.ollama_inference_options()}


def export_identity(payloads):
    result = {name: sha(data) for name, data in payloads.items() if name != "transcript.zip"}
    if "transcript.zip" in payloads:
        with zipfile.ZipFile(io.BytesIO(payloads["transcript.zip"])) as archive:
            if len(archive.namelist()) > 16 or sum(info.file_size for info in archive.infolist()) > 4 * 1024 * 1024:
                raise ValueError("Unexpected export archive size.")
            result["zip_members"] = {name: sha(archive.read(name)) for name in archive.namelist()}
    return result


def fresh_main(argv):
    """Retrieve the saved data through actual routes in a fresh interpreter."""
    from fastapi.testclient import TestClient
    import app
    import library
    library.DB_FILE = Path(argv[0])
    app.DATA_DIR = library.DB_FILE.parent / "fresh-interpreter-jobs"
    result = {}
    with TestClient(app.app) as client:
        for identifier in json.loads(argv[2]):
            response = client.get(f"/api/library/{identifier}")
            response.raise_for_status()
            record = response.json()
            payloads = {}
            for fmt, name in FORMATS.items():
                if name.startswith("summary.") and not record.get("summary"):
                    continue
                response = client.get(f"/api/library/{identifier}/download/{fmt}")
                response.raise_for_status()
                payloads[name] = response.content
            result[identifier] = {"record": record, "exports": export_identity(payloads)}
    checkpoint(Path(argv[1]), result)


def source_coverage(case, chunks):
    """Reconstruct original text independently from observed, indexed fragments."""
    reconstructed = ["" for _ in case["segments"]]
    previous = -1
    for group in chunks:
        for part in group:
            index = part.get("source_index")
            if (isinstance(index, bool) or not isinstance(index, int)
                    or not 0 <= index < len(reconstructed) or index < previous
                    or part["start"] != case["segments"][index]["start"]):
                return False
            reconstructed[index] += part["text"]
            previous = index
    return reconstructed == [item["text"] for item in case["segments"]]


def inspect_case(case, record, requests, payloads, source_chunks):
    summary = record.get("summary") or {}
    starts = {item["start"] for item in case["segments"]}
    chapters = summary.get("chapters", [])
    source_calls = [item for item in requests if item["phase"] in {"map", "direct"}]
    expected = ["\n".join(f"[{item['start']:.1f}s] {item['text']}" for item in group) for group in source_chunks]
    actual = [item["request"]["messages"][-1]["content"] for item in source_calls]
    chapter_starts = list(dict.fromkeys(group[0]["start"] for group in source_chunks))[:100]
    phases = [item["phase"] for item in requests if item["kind"] == "inference"]
    phase_sequence = (phases == ["direct"] if len(source_chunks) == 1 else
                      phases == ["map"] * len(source_chunks) + ["reduce"] * phases.count("reduce") + ["synthesis"])
    text = "\n".join((f"{item['speaker']}: " if item.get("speaker") else "")
                     + item["text"].strip().replace("\r", " ").replace("\n", " ")
                     for item in case["segments"]) + "\n"
    identities = export_identity(payloads)
    checks = {"source_segments_preserved": record["segments"] == case["segments"],
              "all_source_characters_reached_source_requests": bool(source_chunks) and source_coverage(case, source_chunks) and actual == expected,
              "summary_nonempty": isinstance(summary.get("summary"), str) and bool(summary["summary"].strip()),
              "key_points_nonempty": bool(summary.get("key_points")) and all(isinstance(item, str) and item.strip() for item in summary["key_points"]),
              "chapters_use_source_starts": bool(chapters) and all(item.get("start") in starts and isinstance(item.get("title"), str) and item["title"].strip() for item in chapters),
              "chapter_order": [item["start"] for item in chapters] == sorted(item["start"] for item in chapters),
              "chapters_match_actual_chunk_starts": [item["start"] for item in chapters] == chapter_starts,
              "valid_summary_phase_sequence": phase_sequence,
              "transcript_txt_preserved": payloads.get("transcript.txt") == text.encode("utf-8"),
              "transcript_json_preserved": json.loads(payloads["transcript.json"])["segments"] == case["segments"],
              "summary_json_preserved": json.loads(payloads.get("summary.json", b"null")) == summary,
              "zip_contains_identical_exports": identities.get("zip_members") == {name: value for name, value in identities.items() if name != "zip_members"}}
    expected_markdown = None
    if summary:
        lines = ["# Summary", "", summary["summary"], "", "## Key points", ""]
        lines.extend("- " + point for point in summary["key_points"])
        lines.extend(["", "## Chapters", ""])
        for chapter in chapters:
            milliseconds = round(chapter["start"] * 1000)
            timestamp = f"{milliseconds // 3600000:02d}:{milliseconds // 60000 % 60:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}"
            lines.append(f"- {timestamp}: {chapter['title']}")
        expected_markdown = ("\n".join(lines) + "\n").encode("utf-8")
    checks["summary_markdown_preserved"] = expected_markdown is not None and payloads.get("summary.md") == expected_markdown
    for fmt in ("srt", "vtt"):
        rendered = payloads.get(f"transcript.{fmt}", b"").decode("utf-8")
        checks[f"{fmt}_source_text_preserved"] = all(item["text"].strip().replace("\r", " ").replace("\n", " ") in rendered for item in case["segments"])
    return checks, identities


def summary_request_phase(payload, *, control):
    """Describe the actual schema/task shape, independently of example values."""
    if control:
        return "unload"
    schema = payload.get("format")
    if isinstance(schema, dict) and "key_points" in schema.get("properties", {}):
        return "direct" if "chapter_title" in schema["properties"] else "synthesis"
    system = payload["messages"][0]["content"]
    if schema == "json" and system.startswith("Summarize a transcript excerpt factually."):
        return "map"
    if schema == "json" and system.startswith("Condense these chronological notes,"):
        return "reduce"
    return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "tests/fixtures/summary_quality_cases.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args(argv)
    args.corpus, args.output = args.corpus.resolve(), args.output.resolve()
    started = time.monotonic()
    run_id = uuid.uuid4().hex
    folder = args.output.parent / (args.output.stem + "-artifacts-" + run_id[:8])
    report = {"schema_version": 1, "run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(),
              "complete": False, "corpus_complete": False, "semantic_quality": "unreviewed",
              "requested_count": 0, "completed_count": 0, "cases": [], "run_directory": str(folder.resolve()),
              "capture_scope": "Parsed outer API response JSON, not wire bytes. Non-standard non-finite numbers are tagged; undecodable JSON text is retained when exposed by the transport.",
              "interpretation": "Execution/structure checks do not approve factual accuracy, omissions, roles, negation, chapter relevance or output language.",
              "privacy_environment": {key: os.environ[key] for key in ("ORT_DISABLE_TELEMETRY", "HF_HUB_DISABLE_TELEMETRY")}}
    application = library = enhancements = original_transport = original_chunker = None
    previous = None
    active = None
    job_ids = []
    checkpoint(args.output, report)
    try:
        corpus, cases, corpus_sha = read_corpus(args.corpus, args.case_ids)
        report.update({"corpus_sha256": corpus_sha, "corpus_version": corpus.get("corpus_version"),
                       "corpus_case_count": len(corpus["cases"]), "requested_count": len(cases),
                       "selected_case_ids": [case["id"] for case in cases],
                       "source_before": source_identity(args.corpus)})
        folder.mkdir(parents=True, exist_ok=False)
        from fastapi.testclient import TestClient
        import app as application
        import library
        import enhancements
        report["runtime_before"] = runtime_identity(enhancements)
        report["summary_input_limits_bytes"] = {"request": enhancements.MAX_SUMMARY_INPUT_BYTES,
                                                "map_notes": enhancements.MAX_SUMMARY_NOTE_BYTES,
                                                "reduced_notes": enhancements.MAX_SUMMARY_REDUCED_NOTE_BYTES}
        previous = (application.DATA_DIR, library.DB_FILE)
        application.DATA_DIR, library.DB_FILE = folder / "jobs", folder / "library.sqlite3"
        original_transport = enhancements.local_ollama_json
        original_chunker = enhancements._summary_source_chunks

        def observe_chunks(source):
            chunks = original_chunker(source)
            if active is not None:
                active["chunker_input"] = deepcopy(source)
                active["source_chunks"] = deepcopy(chunks)
                checkpoint(args.output, report)
            return chunks

        def observe(path, payload=None, timeout=1.5):
            if path != "/api/chat":
                return original_transport(path, payload, timeout=timeout)
            if active is None:
                raise RuntimeError("Inference occurred outside an active summary case.")
            control = enhancements.is_ollama_control_request(payload)
            phase = summary_request_phase(payload, control=control)
            event = {"kind": "control" if control else "inference", "phase": phase, "request": deepcopy(payload), "timeout_seconds": timeout,
                     "response_json": None, "response_evidence_available": False}
            active["requests"].append(event)
            checkpoint(args.output, report)
            call_started = time.monotonic()
            try:
                response = original_transport(path, payload, timeout=timeout)
                event["response_json"] = safe_response(response)
                event["response_evidence_available"] = True
                return response
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "message": str(exc)}
                if isinstance(exc, json.JSONDecodeError):
                    event["undecodable_response_text"] = exc.doc
                    event["response_evidence_available"] = True
                raise
            finally:
                event["elapsed_seconds"] = round(time.monotonic() - call_started, 3)
                checkpoint(args.output, report)

        enhancements.local_ollama_json = observe
        enhancements._summary_source_chunks = observe_chunks
        with TestClient(application.app) as client:
            for case in cases:
                active = {"id": case["id"], "fixture": deepcopy(case), "complete": False,
                          "semantic_quality": "unreviewed", "requests": [], "checks": {}}
                report["cases"].append(active)
                checkpoint(args.output, report)
                case_started = time.monotonic()
                try:
                    segments = deepcopy(case["segments"])
                    job = application._new_job("owned-summary-case:" + case["id"], title=case["id"])
                    job_ids.append(job.id)
                    active["job_id"] = job.id
                    application._enhance_and_save(job.id, segments, case["source_language"], "owned_test_text", None, False, "none", True)
                    active["job"] = {key: getattr(job, key) for key in ("status", "stage", "error", "warnings")}
                    record = library.get(job.id)
                    active["record"] = record
                    if record is None:
                        raise AssertionError("The actual app did not persist a transcript.")
                    payloads = {}
                    case_folder = folder / case["id"]
                    case_folder.mkdir()
                    for fmt, name in FORMATS.items():
                        if name.startswith("summary.") and not record.get("summary"):
                            continue
                        response = client.get(f"/api/jobs/{job.id}/download/{fmt}")
                        response.raise_for_status()
                        payloads[name] = response.content
                        (case_folder / name).write_bytes(response.content)
                    checks, identities = inspect_case(case, record, active["requests"], payloads, active.get("source_chunks", []))
                    checks.update({"input_unmodified": segments == case["segments"],
                                   "chunker_received_original_source": active.get("chunker_input") == case["segments"],
                                   "inference_inputs_byte_bounded": all(len(item["request"]["messages"][-1]["content"].encode("utf-8")) <= enhancements.MAX_SUMMARY_INPUT_BYTES for item in active["requests"] if item["kind"] == "inference"),
                                   "job_done_without_warnings": job.status == "done" and not job.warnings,
                                   "configured_model_used": bool(active["requests"]) and all(item["request"]["model"] == report["runtime_before"]["configured_model"] for item in active["requests"])})
                    application.jobs.pop(job.id)
                    reloaded = client.get(f"/api/library/{job.id}")
                    checks["database_reload_matches"] = reloaded.status_code == 200 and reloaded.json() == record
                    active.update({"checks": checks, "exports": identities, "complete": True,
                                   "structural_pass": all(checks.values())})
                except Exception as exc:
                    active["error"] = {"type": type(exc).__name__, "message": str(exc)}
                    active["structural_pass"] = False
                    active["complete"] = True
                finally:
                    active["elapsed_seconds"] = round(time.monotonic() - case_started, 3)
                    active["inference_request_count"] = sum(item["kind"] == "inference" for item in active["requests"])
                    active["control_request_count"] = sum(item["kind"] == "control" for item in active["requests"])
                    if active["complete"]:
                        report["completed_count"] += 1
                    checkpoint(args.output, report)
                    print(json.dumps({key: active.get(key) for key in ("id", "structural_pass", "elapsed_seconds", "error")}), flush=True)
            active = None
        reload_path = folder / "fresh-interpreter.json"
        code = "import sys; sys.path.insert(0, sys.argv[1]); from evaluate_summary_quality import fresh_main; fresh_main(sys.argv[2:])"
        completed = subprocess.run([sys.executable, "-c", code, str(ROOT / "tests"), str(library.DB_FILE),
                                    str(reload_path), json.dumps(job_ids)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        if completed.returncode:
            raise RuntimeError("Fresh interpreter retrieval failed: " + completed.stderr[-3000:])
        fresh = json.loads(reload_path.read_text())
        for result in report["cases"]:
            item = fresh.get(result.get("job_id"))
            passed = bool(item) and item["record"] == result.get("record") and item["exports"] == result.get("exports")
            result["checks"]["fresh_interpreter_matches"] = passed
            result["structural_pass"] = result["structural_pass"] and passed
        report["runtime_after"] = runtime_identity(enhancements)
        report["source_after"] = source_identity(args.corpus)
        if report["source_after"]["sha256"] != report["source_before"]["sha256"]:
            raise RuntimeError("Source or corpus changed during actual inference.")
        if report["runtime_after"] != report["runtime_before"]:
            raise RuntimeError("Model identity, runtime or configured inference options changed during the run.")
        report["complete"] = report["completed_count"] == report["requested_count"]
        report["corpus_complete"] = report["complete"] and len(cases) == len(corpus["cases"])
    except KeyboardInterrupt:
        report["error"] = {"type": "KeyboardInterrupt", "message": "Interrupted; partial evidence is retained."}
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if original_transport is not None:
            enhancements.local_ollama_json = original_transport
        if original_chunker is not None:
            enhancements._summary_source_chunks = original_chunker
        if previous is not None:
            application.DATA_DIR, library.DB_FILE = previous
        if application is not None:
            for identifier in job_ids:
                application.jobs.pop(identifier, None)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["failed_case_count"] = sum(not case.get("structural_pass", False) for case in report["cases"])
        checkpoint(args.output, report)
    return 0 if report["complete"] and not report["failed_case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

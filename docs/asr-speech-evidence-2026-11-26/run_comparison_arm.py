"""Actual isolated app upload -> ASR -> persistence/export comparison arm.

Observers return original values. References are retained for review only.
No artificial recognition result is supplied and no raw output is repaired.
"""
from pathlib import Path
import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", choices=("base", "candidate"))
    parser.add_argument("--run-suffix", default="actual", help="New evidence directory suffix; existing results are never overwritten")
    args = parser.parse_args()
    tree = ROOT / args.arm
    assert args.run_suffix.replace("-", "").isalnum()
    run = ROOT / (args.arm + "-" + args.run_suffix)
    run.mkdir(exist_ok=False)
    sys.path.insert(0, str(tree))
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import ctranslate2
    from fastapi.testclient import TestClient
    import app
    import library
    provider = load_module("provider_observers", tree / "tests/smoke_real_links.py")
    export_checks = load_module("asr_export_checks", tree / "tests/smoke_real_asr_quality.py")
    whisper = importlib.import_module("faster_whisper.transcribe")
    audio_module = importlib.import_module("faster_whisper.audio")
    vad_module = importlib.import_module("faster_whisper.vad")
    manifest_path = ROOT / "fixtures/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    provenance = json.loads((ROOT.parent / "asr-qa/model-provenance.json").read_text())
    source_names = ["app.py", "library.py", "batch_store.py", "tests/smoke_real_links.py", "tests/smoke_real_asr_quality.py"]
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "arm": args.arm,
              "complete": False, "semantic_quality": "unreviewed", "actual_asr": True,
              "reference_supplied_to_decoder": False, "manifest_sha256": sha(manifest_path),
              "sources_before": {n: sha(tree / n) for n in source_names},
              "harness_sha256": sha(__file__), "qa_random_seed": manifest["qa_random_seed"],
              "python_executable": sys.executable, "python_version": sys.version,
              "runtime_versions": {n: importlib.metadata.version(n) for n in ("faster-whisper", "ctranslate2", "av", "onnxruntime", "huggingface-hub", "socksio")},
              "installed_source_hashes": {n: sha(importlib.import_module("faster_whisper." + n).__file__) for n in ("transcribe", "vad", "audio", "utils")},
              "model_resolution": [], "cases": []}
    current = threading.local()
    events = []

    def checkpoint():
        provider.write_json(run / "report.json", report)

    def event(kind, **fields):
        item = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind,
                "case_id": getattr(current, "case_id", None), **fields}
        events.append(item)
        with (run / "events.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(item, ensure_ascii=True, allow_nan=False) + "\n")

    original_download = whisper.download_model

    def observed_download(*a, **kw):
        path = Path(original_download(*a, **kw))
        actual = {"requested_args": provider.evidence_value(a), "requested_kwargs": provider.evidence_value(kw),
                  "resolved_snapshot": str(path), "revision": path.name,
                  "files": {n: {"bytes": (path / n).stat().st_size, "sha256": sha(path / n)} for n in provenance["files"]}}
        report["model_resolution"].append(actual)
        checkpoint()
        assert path.name == provenance["revision"], "Actual resolver used another model revision"
        assert actual["files"] == provenance["files"], "Actual model bytes differ from the fixed manifest"
        return str(path)

    whisper.download_model = observed_download
    provider.observe_audio_decode(audio_module, event)
    provider.observe_audio_decode(whisper, event)
    provider.observe_transcribe(whisper, event, lambda: getattr(current, "job_id", None))
    provider.observe_segment_creation(whisper, event, lambda: getattr(current, "job_id", None))
    original_vad = vad_module.get_speech_timestamps

    def observed_vad(audio, *a, **kw):
        before = provider.array_evidence(audio)
        result = original_vad(audio, *a, **kw)
        event("whole_recording_corroboration", job_id=getattr(current, "job_id", None),
              input_array=before, input_unchanged=provider.array_evidence(audio) == before,
              explicit_kwargs=provider.evidence_value(kw), default_vad_options=provider.evidence_value(vad_module.VadOptions()),
              intervals=provider.evidence_value(result))
        return result

    vad_module.get_speech_timestamps = observed_vad
    recognize = app._recognize

    def observed_recognize(path, *a, **kw):
        current.job_id = Path(path).parent.name
        current.case_id = active_case[0]
        ctranslate2.set_random_seed(manifest["qa_random_seed"])
        event("recognize_start", job_id=current.job_id, input_sha256=sha(path))
        try:
            return recognize(path, *a, **kw)
        except Exception as error:
            event("recognize_error", job_id=current.job_id, error=provider.exception_chain(error))
            raise

    app._recognize = observed_recognize
    app.DATA_DIR = run / "jobs"
    app.DATA_DIR.mkdir()
    library.DB_FILE = run / "library.sqlite3"
    active_case = [None]
    checkpoint()
    with TestClient(app.app) as client:
        for case in manifest["cases"]:
            active_case[0] = case["id"]
            item = {"id": case["id"], "expected": case["expected"], "input_sha256": case["audio_sha256"],
                    "reference": case.get("reference"), "execution_status": "running", "gate_status": "incomplete"}
            report["cases"].append(item); checkpoint()
            started = time.monotonic()
            print(json.dumps({"arm": args.arm, "case": case["id"], "started": True}), flush=True)
            try:
                path = ROOT / "fixtures" / case["audio_file"]
                assert sha(path) == case["audio_sha256"]
                with path.open("rb") as source:
                    submitted = client.post("/api/upload", files={"file": (path.name, source, "audio/wav")},
                        data={"consent": "true", "target_language": "none", "speakers": "false", "summary": "false"})
                assert submitted.status_code == 200, submitted.text
                job_id = submitted.json()["id"]; item["job_id"] = job_id
                deadline = time.monotonic() + 240
                while True:
                    response = client.get(f"/api/jobs/{job_id}")
                    assert response.status_code == 200
                    job = response.json()
                    if job["status"] in {"done", "error"}:
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError("Actual app request exceeded 240 seconds")
                    time.sleep(0.2)
                item["job_result"] = job
                with sqlite3.connect(library.DB_FILE) as database:
                    row = database.execute("SELECT segments,plain_text FROM transcripts WHERE id=?", (job_id,)).fetchone()
                item["sqlite_record_present"] = row is not None
                if row:
                    item["segments"] = json.loads(row[0]); item["hypothesis"] = row[1]
                    record_response = client.get(f"/api/library/{job_id}")
                    assert record_response.status_code == 200
                    record = record_response.json()
                    provider.write_json(run / (case["id"] + "-record.json"), record)
                    item["exports"] = export_checks.check_exports(client, job_id, record,
                        export_checks.media_details(path)["duration_seconds"], run / "exports" / case["id"])
                else:
                    item["export_statuses"] = {fmt: client.get(f"/api/library/{job_id}/download/{fmt}").status_code for fmt in ("txt", "srt", "vtt", "json", "zip")}
                cleanup_deadline = time.monotonic() + 5
                workdir = app.jobs[job_id].workdir
                while list(workdir.glob("input.*")) and time.monotonic() < cleanup_deadline:
                    time.sleep(0.05)
                item["input_cleaned"] = not list(workdir.glob("input.*"))
                item["events"] = [e for e in events if e.get("case_id") == case["id"]]
                decoded = [e for e in item["events"] if e["kind"] == "audio_decoded"]
                requested = [e for e in item["events"] if e["kind"] == "transcribe_request"]
                assert len(decoded) == 1 and item["input_cleaned"]
                if case["id"] == "silence":
                    assert not requested and not any(e["kind"] == "asr_segment_created" for e in item["events"])
                else:
                    assert len(requested) == 1
                    assert requested[0]["audio_array"] == decoded[0]["decoded_arrays"][0]
                    assert requested[0]["resolved_options"]["vad_filter"] is False
                    assert not requested[0]["resolved_options"]["initial_prompt"] and not requested[0]["resolved_options"]["hotwords"]
                if case["expected"] == "no_speech":
                    passed = (job["status"] == "error" and job["error"] == "No spoken words were detected in this recording."
                              and not row and all(x == 404 for x in item["export_statuses"].values()))
                else:
                    passed = job["status"] == "done" and bool(row) and job["language"] == case["language"]
                item["gate_status"] = "pass" if passed else "fail"
                item["execution_status"] = "complete"
            except Exception as error:
                item["execution_status"] = "error"
                item["gate_status"] = "fail"
                item["error"] = provider.exception_chain(error)
                item["events"] = [e for e in events if e.get("case_id") == case["id"]]
            item["elapsed_seconds"] = round(time.monotonic() - started, 3)
            checkpoint()
            print(json.dumps({"arm": args.arm, "case": case["id"], "gate_status": item["gate_status"],
                              "execution_status": item["execution_status"], "elapsed_seconds": item["elapsed_seconds"],
                              "hypothesis": item.get("hypothesis"), "error": item.get("error")}, ensure_ascii=True), flush=True)
            if any(e.get("type") == "TimeoutError" for e in item.get("error", [])):
                break
    app.pool.shutdown(wait=True)
    app._release_audio_models()
    report["sources_after"] = {n: sha(tree / n) for n in source_names}
    report["sources_unchanged"] = report["sources_before"] == report["sources_after"]
    report["complete"] = len(report["cases"]) == len(manifest["cases"]) and all(c["execution_status"] == "complete" for c in report["cases"])
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    print(json.dumps({"arm": args.arm, "complete": report["complete"], "gate_passes": sum(c["gate_status"] == "pass" for c in report["cases"]), "cases": len(report["cases"])}), flush=True)


if __name__ == "__main__":
    main()

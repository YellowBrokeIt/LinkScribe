"""Captured-response regression only: no server, network, ASR or model inference."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import zipfile

os.environ.update(ORT_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_TELEMETRY="1",
                 HF_HUB_OFFLINE="1", LINKSCRIBE_OLLAMA_MODEL="qwen3:4b",
                 LINKSCRIBE_TRANSLATION_MODEL="qwen3:4b",
                 LINKSCRIBE_TRANSLATION_BACKEND="ollama", LINKSCRIBE_OLLAMA_THREADS="4")
os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
ROOT = Path(__file__).resolve().parents[2] / "LinkScribe"
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
import app
import enhancements
import library


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    folder = Path(__file__).resolve().parent
    captured_path = folder / "combined-qwen-vad-off.json"
    output = folder / "captured-translation-replay.json"
    if output.exists():
        raise RuntimeError("Refusing to overwrite prior replay evidence.")
    captured = json.loads(captured_path.read_text())
    captured_sha = sha(captured_path)
    events = [item for item in captured["ollama_requests"] if item["task"] == "translation"]
    source = deepcopy(captured["actual_translation_calls"][0]["source_segments"])
    assert len(source) == 21 and [item["kind"] for item in events] == ["inference", "inference", "control"]
    names = ("app.py", "enhancements.py", "library.py", "library_backup.py")
    source_hashes = {name: sha(ROOT / name) for name in names}
    report = {"schema_version": 1, "complete": False,
              "evidence_type": "captured_response_regression",
              "new_model_inference": False, "new_asr_or_speaker_inference": False,
              "network_or_service_start": False,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "captured_actual_report_sha256": captured_sha,
              "captured_actual_source_sha256": captured["source_sha256"],
              "current_source_sha256": source_hashes,
              "replay_script_sha256": sha(__file__),
              "source_segments": deepcopy(source), "phases": [], "checks": {}}
    artifacts = folder / "captured-replay-artifacts"
    artifacts.mkdir()
    app.DATA_DIR = artifacts / "jobs"
    app.DATA_DIR.mkdir()
    library.DB_FILE = artifacts / "library.sqlite3"
    original = enhancements.local_ollama_json
    active = None

    def checkpoint():
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
        temporary.replace(output)

    def replay(path, payload=None, timeout=1.5):
        assert path == "/api/chat" and active is not None, "Unexpected transport use."
        index = len(active["requests"])
        assert index < len(events), "Unexpected extra model/control request."
        expected = events[index]
        assert payload == expected["request"], "Replay request differs from the captured actual request."
        assert timeout == (5 if expected["kind"] == "control" else 240)
        active["requests"].append({"kind": expected["kind"], "captured_translation_event_index": index,
                                   "request": deepcopy(payload), "timeout_seconds": timeout,
                                   "request_exactly_matches_capture": True,
                                   "response_origin": "recorded decoded outer JSON object; no inference",
                                   "response_json": deepcopy(expected["response_json"])})
        checkpoint()
        return deepcopy(expected["response_json"])

    checkpoint()
    started = time.monotonic()
    try:
        enhancements.local_ollama_json = replay
        active = {"name": "direct_actual_adapter", "requests": []}
        report["phases"].append(active)
        try:
            enhancements.translate_segments(source, "el", source_language="en")
        except enhancements.EnhancementError as error:
            active["rejection"] = str(error)
        else:
            raise AssertionError("The real adapter accepted the captured whole-source copy.")
        assert "No separate Greek translation" in active["rejection"]
        assert len(active["requests"]) == 3 and source == report["source_segments"]
        assert enhancements._OLLAMA_PHASE.get() is None

        active = {"name": "actual_app_save_and_exports", "requests": []}
        report["phases"].append(active)
        with TestClient(app.app) as client:
            job = app._new_job("captured-response-regression", title="Captured two-reader source")
            app._enhance_and_save(job.id, source, "en", "captured_response_regression",
                                  None, False, "el", False)
            state = client.get(f"/api/jobs/{job.id}").json()
            record = library.get(job.id)
            assert state["status"] == "done" and not state["extras"]["translation_language"]
            assert any("No separate Greek translation" in warning for warning in state["warnings"])
            assert record["segments"] == source and record["translations"] == {}
            assert record["processing_metadata"]["warnings"] == state["warnings"]
            assert len(active["requests"]) == 3 and enhancements._OLLAMA_PHASE.get() is None
            with sqlite3.connect(library.DB_FILE) as connection:
                row = connection.execute("SELECT segments,translations,processing_metadata FROM transcripts WHERE id=?", (job.id,)).fetchone()
            assert json.loads(row[0]) == source and json.loads(row[1]) == {}
            assert json.loads(row[2])["warnings"] == state["warnings"]

            downloads = {}
            for fmt in ("txt", "srt", "vtt", "json", "zip"):
                response = client.get(f"/api/jobs/{job.id}/download/{fmt}")
                assert response.status_code == 200 and response.content
                path = artifacts / ("transcript." + fmt)
                path.write_bytes(response.content)
                downloads[fmt] = {"path": str(path), "sha256": sha(path)}
            assert json.loads((artifacts / "transcript.json").read_text())["segments"] == source
            baseline_exports = captured["workflow"]["exports"]
            for fmt in ("txt", "srt", "vtt"):
                assert (artifacts / ("transcript." + fmt)).read_bytes() == Path(baseline_exports[fmt]["path"]).read_bytes()
            with zipfile.ZipFile(io.BytesIO((artifacts / "transcript.zip").read_bytes())) as archive:
                assert set(archive.namelist()) == {"transcript." + fmt for fmt in ("txt", "srt", "vtt", "json")}
            for fmt in ("txt", "srt", "vtt", "json"):
                assert client.get(f"/api/jobs/{job.id}/download/translation_{fmt}").status_code == 404
                assert client.get(f"/api/library/{job.id}/download/translation_{fmt}").status_code == 404
            assert not list(job.workdir.glob("translation_*"))
            app.jobs.pop(job.id)
            assert client.get(f"/api/library/{job.id}").json() == record
            assert client.get(f"/api/library/{job.id}/download/txt").content == (artifacts / "transcript.txt").read_bytes()
            report.update(job=state, record=record, exports=downloads)
        report["checks"] = {
            "captured_requests_reproduced_exactly": True,
            "adapter_rejected_whole_source_copy": True,
            "source_exactly_preserved": source == report["source_segments"],
            "sqlite_and_library_preserve_original_and_warning": True,
            "original_txt_srt_vtt_bytes_match_actual_model_run": True,
            "translation_artifacts_absent_and_routes_404": True,
            "in_memory_eviction_preserves_library_result": True,
            "one_final_unload_control_replayed_in_each_phase": True,
            "transport_restoration_checked_in_finally": True,
            "captured_actual_report_unchanged": sha(captured_path) == captured_sha,
            "current_source_unchanged": {name: sha(ROOT / name) for name in names} == source_hashes}
        assert all(report["checks"].values())
        report["complete"] = True
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        enhancements.local_ollama_json = original
        assert enhancements.local_ollama_json is original
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        checkpoint()
    print(json.dumps({"complete": report["complete"], "new_model_inference": False,
                      "checks": report["checks"], "error": report.get("error")}, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

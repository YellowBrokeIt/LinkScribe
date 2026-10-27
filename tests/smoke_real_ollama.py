"""Real optional Ollama integration, using an already installed local model.

Run explicitly, not in the network-free pytest suite:
    PYTHONPATH=. .venv/bin/python tests/smoke_real_ollama.py

This exercises owned English/Greek text -> actual local inference -> SQLite ->
translated subtitle and summary exports. It does not claim to test audio ASR.
No models are downloaded, no service is started, and no credentials are used by
this script. Set LINKSCRIBE_OLLAMA_MODEL to choose the installed model.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import time
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

import app
import diagnostics
import enhancements
import library


EXAMPLES = [
    ("en", "el", [
        {"start": 0.5, "end": 4.0, "text": "Maria recorded 3 short videos in Athens.", "speaker": "Speaker 1"},
        {"start": 4.0, "end": 8.5, "text": "The videos explain how to save and translate a transcript.", "speaker": "Speaker 1"},
    ]),
    ("el", "en", [
        {"start": 1.0, "end": 4.5, "text": "Ο Νίκος έχει 2 βιβλία για το Bitcoin.", "speaker": "Speaker 2"},
        {"start": 4.5, "end": 9.0, "text": "Σήμερα διαβάζει στο σπίτι και κρατά σημειώσεις στα ελληνικά.", "speaker": "Speaker 2"},
    ]),
]


def main() -> None:
    readiness = diagnostics.report()["ollama"]
    assert readiness["available"] and readiness["model_available"], readiness
    version = enhancements.local_ollama_json("/api/version").get("version", "unknown")
    previous_jobs, previous_db = app.DATA_DIR, library.DB_FILE
    results = []
    created_jobs = []
    try:
        with tempfile.TemporaryDirectory(prefix="linkscr-qa-ollama-") as folder:
            root = Path(folder)
            app.DATA_DIR = root / "jobs"
            library.DB_FILE = root / "library.sqlite3"
            with TestClient(app.app) as client:
                for language, target, segments in EXAMPLES:
                    print(f"Testing real Ollama {version}, {readiness['model_configured']}: "
                          f"{language} -> {target}, summary and exports", file=sys.stderr, flush=True)
                    started = time.monotonic()
                    job = app._new_job(f"owned-test-text:{language}", title="Owned bilingual integration text")
                    created_jobs.append(job.id)
                    app._enhance_and_save(job.id, segments, language, "owned_test_text", None,
                                          False, target, True)
                    assert job.status == "done" and not job.warnings, vars(job)
                    response = client.get(f"/api/library/{job.id}")
                    assert response.status_code == 200, response.text
                    record = response.json()
                    translated = record["translations"][target]
                    assert record["segments"] == segments
                    assert len(translated) == len(segments)
                    for original, result in zip(segments, translated):
                        assert result["text"].strip() and result["text"] != original["text"]
                        for key in ("start", "end", "speaker"):
                            assert result[key] == original[key]
                    combined = " ".join(segment["text"] for segment in translated)
                    if target == "el":
                        assert re.search("[Α-ω]", combined), combined
                        assert "3" in combined or "τρία" in combined.lower(), combined
                    else:
                        assert "Bitcoin" in combined, combined
                        assert "2" in combined or "two" in combined.lower(), combined
                    summary = record["summary"]
                    assert summary["summary"].strip() and summary["key_points"]
                    assert summary["chapters"]
                    assert all(chapter["start"] in {item["start"] for item in segments}
                               for chapter in summary["chapters"])
                    for export in ("translation_txt", "translation_srt", "translation_vtt", "translation_json",
                                   "summary_md", "summary_json", "zip"):
                        exported = client.get(f"/api/library/{job.id}/download/{export}")
                        assert exported.status_code == 200 and exported.content, export
                    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                        assert f"translation_{target}.srt" in archive.namelist()
                        assert "summary.md" in archive.namelist()
                    results.append({"source": language, "target": target,
                                    "elapsed_seconds": round(time.monotonic() - started, 2),
                                    "translation": [item["text"] for item in translated],
                                    "summary": summary})
    finally:
        app.DATA_DIR, library.DB_FILE = previous_jobs, previous_db
        for job_id in created_jobs:
            app.jobs.pop(job_id, None)
    print(json.dumps({"result": "PASS", "ollama_version": version,
                      "model": readiness["model_configured"], "examples": results},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

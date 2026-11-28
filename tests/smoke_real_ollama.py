"""Real optional Ollama integration, using an already installed local model.

Run explicitly, not in the network-free pytest suite:
    PYTHONPATH=. .venv/bin/python tests/smoke_real_ollama.py

This exercises owned English/Greek text -> actual local inference -> SQLite ->
translated subtitle and summary exports. It does not claim to test audio ASR.
No models are downloaded, no service is started, and no credentials are used by
this script. LINKSCRIBE_OLLAMA_MODEL selects the summary model; the optional
LINKSCRIBE_TRANSLATION_MODEL override selects the translation model independently.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import time
import copy
from contextlib import contextmanager
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


def model_identities():
    """Identify both installed task models before exercising actual inference."""
    tags = enhancements.local_ollama_json("/api/tags")
    identities = {}
    for task in ("summary", "translation"):
        _url, model = enhancements.ollama_settings(task=task)
        names = {model}
        if ":" not in model.rsplit("/", 1)[-1]:
            names.add(model + ":latest")
        selected = next((item for item in tags.get("models", []) if isinstance(item, dict)
                         and (item.get("name") in names or item.get("model") in names)), None)
        assert selected and selected.get("digest"), f"No installed identity for {task} model {model}"
        identities[task] = {"configured_model": model, "model": copy.deepcopy(selected),
                            "profile": enhancements.translation_profile() if task == "translation" else "json"}
    return identities


@contextmanager
def observe_task_models(identities):
    """Verify which configured model each actual application task calls."""
    original_transport = enhancements.local_ollama_json
    original_translate, original_summary = app.translate_segments, app.summarize_segments
    requests = []
    active_task = None

    def task_wrapper(task, function):
        def wrapped(*args, **kwargs):
            nonlocal active_task
            previous = active_task
            active_task = task
            try:
                return function(*args, **kwargs)
            finally:
                active_task = previous
        return wrapped

    def observed(path, payload=None, timeout=1.5):
        if path == "/api/chat":
            assert active_task in identities, "Model call outside a recorded application task"
            assert payload["model"] == identities[active_task]["configured_model"], (
                active_task, payload["model"], identities[active_task]["configured_model"])
            requests.append({"kind": "control" if enhancements.is_ollama_control_request(payload) else "inference",
                             "task": active_task, "model": payload["model"],
                             "options": copy.deepcopy(payload.get("options", {})),
                             "format": copy.deepcopy(payload.get("format")),
                             "think": payload.get("think")})
        return original_transport(path, payload, timeout=timeout)

    enhancements.local_ollama_json = observed
    app.translate_segments = task_wrapper("translation", original_translate)
    app.summarize_segments = task_wrapper("summary", original_summary)
    try:
        yield requests
    finally:
        enhancements.local_ollama_json = original_transport
        app.translate_segments, app.summarize_segments = original_translate, original_summary


def main() -> None:
    readiness = diagnostics.report()["ollama"]
    assert readiness["available"] and readiness["model_available"] and readiness["translation_model_available"], readiness
    identities = model_identities()
    version = enhancements.local_ollama_json("/api/version").get("version", "unknown")
    previous_jobs, previous_db = app.DATA_DIR, library.DB_FILE
    results = []
    created_jobs = []
    try:
        with tempfile.TemporaryDirectory(prefix="linkscr-qa-ollama-") as folder:
            root = Path(folder)
            app.DATA_DIR = root / "jobs"
            library.DB_FILE = root / "library.sqlite3"
            with TestClient(app.app) as client, observe_task_models(identities) as requests:
                for language, target, segments in EXAMPLES:
                    print(f"Testing real Ollama {version}, translation={readiness['translation_model_configured']}, "
                          f"summary={readiness['model_configured']}: "
                          f"{language} -> {target}, summary and exports", file=sys.stderr, flush=True)
                    started = time.monotonic()
                    request_start = len(requests)
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
                    actual_requests = requests[request_start:]
                    assert {item["task"] for item in actual_requests} == {"translation", "summary"}
                    results.append({"source": language, "target": target,
                                    "elapsed_seconds": round(time.monotonic() - started, 2),
                                    "translation": [item["text"] for item in translated],
                                    "summary": summary,
                                    "inference_requests": [item for item in actual_requests if item["kind"] == "inference"],
                                    "control_requests": [item for item in actual_requests if item["kind"] == "control"]})
    finally:
        app.DATA_DIR, library.DB_FILE = previous_jobs, previous_db
        for job_id in created_jobs:
            app.jobs.pop(job_id, None)
    print(json.dumps({"result": "PASS", "ollama_version": version,
                      "model": readiness["model_configured"], "models": identities,
                      "semantic_quality": "unreviewed", "examples": results},
                     ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

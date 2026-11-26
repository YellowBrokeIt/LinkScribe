"""Safe, read-only local installation diagnostics. Never expose credentials."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import urllib.error
from typing import Any

from runtime_check import runtime_details
from enhancements import EnhancementError, local_ollama_json, ollama_settings, translation_profile


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def report() -> dict[str, Any]:
    libraries = {name: _module_available(name)
                 for name in ("fastapi", "uvicorn", "faster_whisper", "av", "yt_dlp",
                              "youtube_transcript_api")}
    # pyannote.core alone cannot run the optional audio diarization pipeline.
    libraries["pyannote"] = _module_available("pyannote.audio")
    ffmpeg = shutil.which("ffmpeg") is not None
    js = runtime_details()
    summary_model = os.getenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b").strip()
    ollama: dict[str, Any] = {
        "available": False, "model_available": False, "model_configured": summary_model,
        "translation_model_available": False,
        "translation_model_configured": os.getenv("LINKSCRIBE_TRANSLATION_MODEL", summary_model).strip(),
        "translation_profile": None,
    }
    selected: dict[str, str] = {}
    for task in ("summary", "translation"):
        field = "model_configured" if task == "summary" else "translation_model_configured"
        try:
            _url, selected[task] = ollama_settings(task=task)
            ollama[field] = selected[task]
            if task == "translation":
                ollama["translation_profile"] = translation_profile()
        except EnhancementError as exc:
            selected.pop(task, None)
            ollama[f"{task}_error"] = str(exc)
            if task == "summary":
                ollama["error"] = str(exc)  # Retain the existing summary diagnostic field.
    try:
        data = local_ollama_json("/api/tags")
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise EnhancementError("Ollama returned an invalid model list.")
        models = {item[key] for item in data["models"] if isinstance(item, dict)
                  for key in ("name", "model") if isinstance(item.get(key), str)}
        ollama["available"] = True
        for task, model in selected.items():
            canonical_model = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
            field = "model_available" if task == "summary" else "translation_model_available"
            ollama[field] = model in models or canonical_model in models
    except EnhancementError as exc:
        ollama["error"] = str(exc)
    except (OSError, ValueError, TypeError, KeyError, urllib.error.URLError):
        pass
    speaker_ready = libraries["pyannote"] and bool(os.getenv("HF_TOKEN", "").strip()) and ffmpeg
    warnings: list[str] = []
    if not libraries["faster_whisper"] or not libraries["av"]:
        warnings.append("Install the core speech packages from requirements.txt.")
    if not js["supported"]:
        warnings.append("Deno 2.3+ or a security-patched Node.js is recommended for some YouTube videos.")
    if not ffmpeg:
        warnings.append("FFmpeg is recommended for model and media compatibility.")
    if not ollama["available"]:
        warnings.append("Ollama is optional; translation and summaries need a local Ollama model.")
    for task in ("summary", "translation"):
        if f"{task}_error" in ollama:
            warnings.append(f"{task.title()}: {ollama[f'{task}_error']}")
    if ollama["available"]:
        missing = [task for task in selected if not ollama[
            "model_available" if task == "summary" else "translation_model_available"]]
        if len(missing) == 2 and selected["summary"] == selected["translation"]:
            warnings.append(f"The selected Ollama model is missing. Run `ollama pull {selected['summary']}`.")
        else:
            for task in missing:
                warnings.append(f"The {task} model is missing. Run `ollama pull {selected[task]}`.")
    if not speaker_ready:
        warnings.append("Speaker labeling is optional; it requires pyannote, FFmpeg and model access.")
    return {
        "app": "LinkScribe", "version": "0.3.0", "python": ".".join(map(str, sys.version_info[:3])),
        "libraries": libraries, "ffmpeg_available": ffmpeg,
        "js_runtime": js, "ollama": ollama, "speakers_configured": speaker_ready,
        "warnings": warnings,
    }

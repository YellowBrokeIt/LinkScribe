"""Safe, read-only local installation diagnostics. Never expose credentials."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from runtime_check import runtime_details


def report() -> dict[str, Any]:
    libraries = {name: importlib.util.find_spec(name) is not None
                 for name in ("fastapi", "uvicorn", "faster_whisper", "av", "yt_dlp",
                              "youtube_transcript_api", "pyannote")}
    ffmpeg = shutil.which("ffmpeg") is not None
    js = runtime_details()
    ollama: dict[str, Any] = {"available": False, "model_configured": os.getenv("LINKSCRIBE_OLLAMA_MODEL", "qwen3:4b")}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.5) as response:
            data = json.load(response)
        models = [item.get("name", "") for item in data.get("models", []) if isinstance(item, dict)]
        ollama["available"] = True
        ollama["model_available"] = ollama["model_configured"] in models
    except (OSError, ValueError, TypeError, KeyError, urllib.error.URLError):
        ollama["model_available"] = False
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
    if not speaker_ready:
        warnings.append("Speaker labeling is optional; it requires pyannote, FFmpeg and model access.")
    return {
        "app": "LinkScribe", "version": "0.3.0", "python": ".".join(map(str, sys.version_info[:3])),
        "libraries": libraries, "ffmpeg_available": ffmpeg,
        "js_runtime": js, "ollama": ollama, "speakers_configured": speaker_ready,
        "warnings": warnings,
    }

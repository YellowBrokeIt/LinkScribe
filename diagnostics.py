"""Safe, read-only local installation diagnostics. Never expose credentials."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import urllib.error
from typing import Any

from runtime_check import runtime_details
from enhancements import (EnhancementError, local_ollama_json, ollama_settings,
                          speaker_backend, speaker_cache_dir, translation_backend, translation_profile)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def report() -> dict[str, Any]:
    libraries = {name: _module_available(name)
                 for name in ("fastapi", "uvicorn", "faster_whisper", "av", "yt_dlp",
                              "youtube_transcript_api", "ctranslate2", "sentencepiece", "curl_cffi")}
    # pyannote.core alone cannot run the optional audio diarization pipeline.
    libraries["pyannote"] = _module_available("pyannote.audio")
    for name in ("speechbrain", "torch", "torchaudio", "scipy", "onnxruntime"):
        libraries[name] = _module_available(name)
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
    translation: dict[str, Any] = {"backend": None, "dependencies_available": False}
    try:
        translation["backend"] = translation_backend()
        if translation["backend"] == "marian":
            import marian_translation
            translation.update(marian_translation.cache_status())
            translation["dependencies_available"] = libraries["ctranslate2"] and libraries["sentencepiece"]
    except (EnhancementError, ValueError) as exc:
        translation["error"] = str(exc)
    tasks = ("summary", "translation") if translation["backend"] == "ollama" else ("summary",)
    for task in tasks:
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
    if translation["backend"] == "ollama":
        translation.update({"model_configured": ollama["translation_model_configured"],
                            "model_available": ollama["translation_model_available"],
                            "service_available": ollama["available"], "dependencies_available": True})
    speaker_details: dict[str, Any] = {"backend": None, "dependencies_available": False,
                                    "model_cache_files_present": False, "inference_verified": False}
    speaker_ready = False
    try:
        backend = speaker_backend()
        speaker_details["backend"] = backend
        if backend == "speechbrain":
            from diarization import MODEL_ID, MODEL_REVISION
            needed = ("speechbrain", "torch", "torchaudio", "scipy", "faster_whisper", "onnxruntime", "av")
            speaker_ready = all(libraries[name] for name in needed)
            cache = speaker_cache_dir()
            files = ("hyperparams.yaml", "embedding_model.ckpt", "classifier.ckpt",
                     "mean_var_norm_emb.ckpt", "label_encoder.ckpt")
            speaker_details.update({"dependencies_available": speaker_ready, "token_required": False,
                                    "model": MODEL_ID, "revision": MODEL_REVISION,
                                    "model_cache_files_present": all((cache / name).is_file() for name in files)})
        else:
            dependencies_ready = libraries["pyannote"] and ffmpeg
            speaker_ready = dependencies_ready and bool(os.getenv("HF_TOKEN", "").strip())
            speaker_details.update({"dependencies_available": dependencies_ready, "token_required": True,
                                    "model": "pyannote/speaker-diarization-community-1", "revision": None})
    except EnhancementError as exc:
        speaker_details["error"] = str(exc)
    warnings: list[str] = []
    if not libraries["faster_whisper"] or not libraries["av"]:
        warnings.append("Install the core speech packages from requirements.txt.")
    if not libraries["curl_cffi"]:
        warnings.append("The public-video download transport is missing. Install requirements.txt to enable the supported Dailymotion transport.")
    if not js["supported"]:
        warnings.append("Deno 2.3+ or a security-patched Node.js is recommended for some YouTube videos.")
    if not ffmpeg:
        warnings.append("FFmpeg is recommended for model and media compatibility.")
    if not ollama["available"]:
        warnings.append("Ollama is optional; summaries need a local Ollama model."
                        if translation["backend"] == "marian" else
                        "Ollama is optional; translation and summaries need a local Ollama model.")
    if "error" in translation:
        warnings.append("Translation: " + translation["error"])
    elif translation["backend"] == "marian":
        if not translation["dependencies_available"]:
            warnings.append("Install requirements.txt for the dedicated local English/Greek translator.")
        elif not all(translation["pairs_cached"].values()):
            warnings.append("The dedicated translator downloads its public model on first use (about 879 MB per direction, about 250 MB after setup). Preload with `python -m marian_translation --pair both`.")
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
    if "error" in speaker_details:
        warnings.append(speaker_details["error"])
    elif not speaker_ready:
        warnings.append("Speaker labeling is optional; install requirements-speakers-free.txt for the public CPU backend without a token."
                        if speaker_details["backend"] == "speechbrain" else
                        "The selected pyannote speaker backend requires pyannote, FFmpeg and authorized model access with HF_TOKEN.")
    elif speaker_details["backend"] == "speechbrain" and not speaker_details["model_cache_files_present"]:
        warnings.append("Speaker dependencies are configured; the pinned public model will download on first use. No access token is needed.")
    return {
        "app": "LinkScribe", "version": "0.3.0", "python": ".".join(map(str, sys.version_info[:3])),
        "libraries": libraries, "ffmpeg_available": ffmpeg,
        "js_runtime": js, "ollama": ollama, "translation": translation, "speakers_configured": speaker_ready,
        "speakers": speaker_details,
        "warnings": warnings,
    }

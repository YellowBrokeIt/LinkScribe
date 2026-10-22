"""LinkScribe: a local-first YouTube / media-to-transcript web app.

Run with: python -m uvicorn app:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import html
import json
import io
import math
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import library
import batch_store
import library_backup
import diagnostics
from sources import Source, parse_source
from runtime_check import runtime_details, yt_dlp_js_options
from enhancements import EnhancementError, assign_speakers, translate_segments, summarize_segments

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 150 * 1024 * 1024             # 150 MB per uploaded/downloaded input
MAX_SECONDS = 2 * 60 * 60                 # 2 hours per recording
JOB_TTL = 60 * 60                        # completed jobs retained locally for 1 hour
MAX_ACTIVE = 8
MAX_BATCH_SIZE = 20                          # queued + processing
ACCEPTED_SUFFIXES = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".mov", ".mkv", ".aac", ".opus"}
LANGUAGES = {"auto", "en", "el", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar"}
MODELS = {"tiny", "base", "small"}
MODES = {"smart", "audio", "captions"}
FORMATS = {"txt", "srt", "vtt", "json", "zip", "summary_md", "summary_json",
           "translation_txt", "translation_srt", "translation_vtt", "translation_json"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
JOB_ID_RE = re.compile(r"^[a-f0-9]{32}$")

@asynccontextmanager
async def _linkscr_lifespan(_application: FastAPI):
    # FastAPI 0.160+ uses lifespan contexts in place of the removed
    # add_event_handler API. Recovery is performed once per ASGI server start.
    _restore_pending_batches()
    yield


app = FastAPI(title="LinkScribe", version="0.3.0", docs_url=None, redoc_url=None,
              lifespan=_linkscr_lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkscr")
lock = threading.RLock()


@dataclass
class Job:
    id: str
    workdir: Path
    source: str
    title: str = "Transcript"
    status: str = "queued"
    stage: str = "Waiting for processing..."
    language: str = ""
    method: str = ""
    preview: str = ""
    error: str = ""
    segment_count: int = 0
    created_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    batch_id: str = ""
    warnings: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    library_id: str = ""


@dataclass
class Batch:
    id: str
    workdir: Path
    job_ids: list[str]
    status: str = "queued"
    completed: int = 0
    failed: int = 0
    stage: str = "Waiting for processing..."
    created_at: float = field(default_factory=time.time)
    finished_at: float = 0.0


jobs: dict[str, Job] = {}
batches: dict[str, Batch] = {}


class ReadableError(Exception):
    """Error that can be safely displayed in the browser."""


def youtube_video_id(raw_url: str) -> str:
    """Strictly allow YouTube video IDs, never pass an arbitrary URL to a downloader."""
    raw_url = raw_url.strip()
    if len(raw_url) > 2048:
        raise ValueError("Link is too long.")
    if raw_url.startswith(("youtube.com/", "www.youtube.com/", "m.youtube.com/", "youtu.be/")):
        raw_url = "https://" + raw_url
    try:
        url = urlsplit(raw_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.port:
            raise ValueError
    except ValueError:
        raise ValueError("Please provide a valid YouTube video link.") from None

    host = url.hostname.lower().rstrip(".")
    path = url.path.strip("/")
    if host == "youtu.be":
        candidate = path if "/" not in path else ""
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if path == "watch":
            candidate = parse_qs(url.query).get("v", [""])[0]
        elif path.split("/")[0] in {"shorts", "live", "embed"}:
            candidate = path.split("/")[1] if len(path.split("/")) == 2 else ""
        else:
            candidate = ""
    elif host == "www.youtube-nocookie.com" and path.startswith("embed/"):
        candidate = path[len("embed/"):]
    else:
        candidate = ""
    if not VIDEO_ID_RE.fullmatch(candidate):
        raise ValueError("For now, only individual YouTube video links are supported.")
    return candidate


def _cleanup_expired() -> None:
    old_jobs: list[Job] = []
    old_batches: list[Batch] = []
    with lock:
        for identifier, job in list(jobs.items()):
            if (job.finished_at and time.time() - job.finished_at > JOB_TTL
                    and (not job.batch_id or batches.get(job.batch_id) is None
                         or batches[job.batch_id].status in {"done", "error"})):
                old_jobs.append(job)
                del jobs[identifier]
        for identifier, batch in list(batches.items()):
            if batch.finished_at and time.time() - batch.finished_at > JOB_TTL:
                old_batches.append(batch)
                del batches[identifier]
    for job in old_jobs:
        shutil.rmtree(job.workdir, ignore_errors=True)
    for batch in old_batches:
        shutil.rmtree(batch.workdir, ignore_errors=True)


def _active_count() -> int:
    # Batch children consume their parent's queue slot, not twenty more slots.
    return (sum(job.status not in {"done", "error"} and not job.batch_id for job in jobs.values())
            + sum(batch.status not in {"done", "error"} for batch in batches.values()))


def _new_job(source: str, title: str = "Transcript", batch_id: str = "") -> Job:
    _cleanup_expired()
    with lock:
        if not batch_id and _active_count() >= MAX_ACTIVE:
            raise HTTPException(429, "The transcription queue is full; retry shortly.")
        identifier = uuid.uuid4().hex
        directory = DATA_DIR / identifier
        directory.mkdir(parents=True, exist_ok=False)
        job = Job(id=identifier, workdir=directory, source=source, title=title, batch_id=batch_id,
                  stage="Waiting for batch..." if batch_id else "Waiting for processing...")
        jobs[identifier] = job
        return job


def _set(job_id: str, **changes: Any) -> None:
    with lock:
        job = jobs[job_id]
        for field_name, value in changes.items():
            setattr(job, field_name, value)


def _check_browser_origin(request: Request) -> None:
    """Reject cross-site browser POSTs targeting the local-only service."""
    origin = request.headers.get("origin")
    if origin is not None:
        try:
            parsed = urlsplit(origin)
            allowed = (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
                       and parsed.port == 8765)
        except ValueError:
            allowed = False
        if not allowed:
            raise HTTPException(403, "Cross-site form submissions are not permitted.")


def _validate_common(language: str, model: str, consent: bool) -> None:
    if not consent:
        raise HTTPException(400, "Confirm that you have permission to process the media.")
    if language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language selection.")
    if model not in MODELS:
        raise HTTPException(400, "Unsupported local model size.")


def _start_job(job: Job, worker, *args: Any) -> dict[str, str]:
    try:
        pool.submit(_guarded_worker, job.id, worker, *args)
    except RuntimeError:
        with lock:
            jobs.pop(job.id, None)
        shutil.rmtree(job.workdir, ignore_errors=True)
        raise HTTPException(503, "The processing service is shutting down.") from None
    return {"id": job.id}


def _guarded_worker(job_id: str, worker, *args: Any) -> None:
    try:
        _set(job_id, status="working")
        worker(job_id, *args)
    except ReadableError as exc:
        _set(job_id, status="error", stage="Unable to transcribe", error=str(exc), finished_at=time.time())
    except Exception as exc:
        # Keep internal traceback and secrets out of the public response.
        print(f"[LinkScribe] Job {job_id} failed: {type(exc).__name__}: {exc}")
        _set(job_id, status="error", stage="Unable to transcribe", error="Processing failed. Check the terminal for details, or try an uploaded file.", finished_at=time.time())
    finally:
        # Delete inputs once output files exist (or the job has failed).
        for path in jobs[job_id].workdir.glob("input.*"):
            path.unlink(missing_ok=True)
        for path in jobs[job_id].workdir.glob("audio.*"):
            path.unlink(missing_ok=True)


def _captions(video_id: str, language: str) -> tuple[list[dict[str, Any]], str]:
    from youtube_transcript_api import YouTubeTranscriptApi

    tracks = list(YouTubeTranscriptApi().list(video_id))
    if language == "auto":
        # Prefer creator captions over machine-generated captions. Otherwise
        # favor English/Greek when the video has multiple separate tracks.
        tracks.sort(key=lambda track: (track.is_generated, track.language_code not in ("en", "el")))
    else:
        tracks = [track for track in tracks if track.language_code == language or track.language_code.startswith(language + "-")]
        tracks.sort(key=lambda track: track.is_generated)

    if not tracks:
        raise ReadableError("No accessible captions were found for the selected language.")
    track = tracks[0]
    result = track.fetch()
    segments = [
        {"start": round(float(s.start), 3), "end": round(float(s.start + max(s.duration, 0.1)), 3), "text": html.unescape(s.text).strip()}
        for s in result
        if s.text.strip()
    ]
    if not segments:
        raise ReadableError("The caption track is empty.")
    return segments, track.language_code


def _download_source_audio(job_id: str, source: Source) -> tuple[Path, str]:
    import yt_dlp

    job = jobs[job_id]
    video_url = source.url
    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(job.workdir / "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 25,
        "retries": 2,
        "max_filesize": MAX_BYTES,
        "overwrites": False,
    }
    # Prefer a supported Deno runtime (yt-dlp default); use supported Node as fallback.
    if source.provider == "youtube":
        options.update(yt_dlp_js_options())

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                raise ReadableError("YouTube did not return video details.")
            if info.get("_type") in {"playlist", "multi_video"} or info.get("entries"):
                raise ReadableError("Only one video per link is allowed, not playlists.")
            length = info.get("duration")
            if length and length > MAX_SECONDS:
                raise ReadableError("The video exceeds the 2-hour limit for this starter app.")
            expected_size = info.get("filesize") or info.get("filesize_approx")
            if expected_size and expected_size > MAX_BYTES:
                raise ReadableError("The audio exceeds the 150 MB input limit.")
            title = str(info.get("title") or f"{source.provider} video")[:180]
            ydl.download([video_url])
    except ReadableError:
        raise
    except Exception as exc:
        raise ReadableError(
            "Video audio could not be accessed. Check the source restrictions, update yt-dlp "
            "(and Deno/Node if required by YouTube), or upload media you are allowed to use."
        ) from exc

    candidate_paths = [p for p in job.workdir.glob("audio.*") if p.suffix.lower() in ACCEPTED_SUFFIXES and p.is_file()]
    if not candidate_paths:
        raise ReadableError("No usable audio stream was downloaded from this video.")
    audio_path = max(candidate_paths, key=lambda p: p.stat().st_size)
    if audio_path.stat().st_size > MAX_BYTES:
        raise ReadableError("The downloaded audio is over 150 MB.")
    return audio_path, title


def _download_youtube_audio(job_id: str, video_id: str) -> tuple[Path, str]:
    """Compatibility helper; safe canonical YouTube source."""
    return _download_source_audio(job_id, Source("youtube", video_id, f"https://www.youtube.com/watch?v={video_id}"))


def _check_uploaded_duration(path: Path) -> None:
    try:
        import av
        with av.open(str(path)) as container:
            if container.duration is not None and container.duration / av.time_base > MAX_SECONDS:
                raise ReadableError("The recording exceeds the 2-hour limit.")
    except ReadableError:
        raise
    except Exception as exc:
        raise ReadableError("Cannot open this media file. Try MP3, MP4, WAV or WebM.") from exc


@lru_cache(maxsize=3)
def _whisper_model(size: str):
    from faster_whisper import WhisperModel
    device = os.getenv("LINKSCRIBE_DEVICE", "cpu").lower()
    if device not in {"cpu", "cuda"}:
        device = "cpu"
    return WhisperModel(size, device=device, compute_type="int8" if device == "cpu" else "float16")


def _recognize(path: Path, language: str, model: str) -> tuple[list[dict[str, Any]], str]:
    engine = _whisper_model(model)
    try:
        segments, info = engine.transcribe(
            str(path),
            language=None if language == "auto" else language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        # transcribe() returns a generator, which must be consumed.
        output = [
            {"start": round(float(s.start), 3), "end": round(float(s.end), 3), "text": s.text.strip()}
            for s in segments if s.text.strip()
        ]
    except Exception as exc:
        raise ReadableError("The speech model could not decode this file. Try another recording or a smaller model.") from exc
    if not output:
        raise ReadableError("No spoken words were detected in this recording.")
    return output, str(info.language or language)


def _timecode(seconds: float, subtitle_format: str) -> str:
    ms = max(0, round(seconds * 1000))
    hours, rest = divmod(ms, 3_600_000)
    mins, rest = divmod(rest, 60_000)
    secs, msecs = divmod(rest, 1000)
    return f"{hours:02d}:{mins:02d}:{secs:02d}{',' if subtitle_format == 'srt' else '.'}{msecs:03d}"


def _shown_text(segment: dict[str, Any]) -> str:
    text = str(segment["text"]).strip().replace("\r", " ").replace("\n", " ")
    speaker = str(segment.get("speaker") or "").strip()
    return f"{speaker}: {text}" if speaker else text


def _render_subtitles(segments: list[dict[str, Any]], fmt: str) -> str:
    blocks = []
    for i, segment in enumerate(segments, start=1):
        start = _timecode(segment["start"], fmt)
        end = _timecode(max(segment["end"], segment["start"] + 0.1), fmt)
        index = f"{i}\n" if fmt == "srt" else ""
        blocks.append(f"{index}{start} --> {end}\n{_shown_text(segment)}\n")
    return ("WEBVTT\n\n" if fmt == "vtt" else "") + "\n".join(blocks)


def _exports(record: dict[str, Any]) -> dict[str, bytes]:
    """Single exporter for freshly completed jobs and saved/edited library items."""
    segments = record["segments"]
    text = "\n".join(_shown_text(segment) for segment in segments) + "\n"
    contents = {
        "transcript.txt": text.encode("utf-8"),
        "transcript.srt": _render_subtitles(segments, "srt").encode("utf-8"),
        "transcript.vtt": _render_subtitles(segments, "vtt").encode("utf-8"),
        "transcript.json": json.dumps({k: record[k] for k in ("source", "title", "language", "method", "segments")}, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    for lang, translated in record.get("translations", {}).items():
        if lang not in {"el", "en"}: continue
        contents[f"translation_{lang}.txt"] = ("\n".join(_shown_text(s) for s in translated) + "\n").encode("utf-8")
        contents[f"translation_{lang}.srt"] = _render_subtitles(translated,"srt").encode("utf-8")
        contents[f"translation_{lang}.vtt"] = _render_subtitles(translated,"vtt").encode("utf-8")
        contents[f"translation_{lang}.json"] = json.dumps({"language":lang,"segments":translated},ensure_ascii=False,indent=2).encode("utf-8")
    if summary := record.get("summary"):
        md = "# Summary\n\n" + summary["summary"] + "\n\n## Key points\n\n"
        md += "\n".join("- " + point for point in summary["key_points"])
        md += "\n\n## Chapters\n\n"
        md += "\n".join(f"- {_timecode(c['start'],'vtt')}: {c['title']}" for c in summary["chapters"]) + "\n"
        contents["summary.md"] = md.encode("utf-8")
        contents["summary.json"] = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in contents.items(): z.writestr(name,data)
    contents["transcript.zip"] = stream.getvalue()
    return contents


def _export_key(file_type: str, record: dict[str, Any]) -> str | None:
    if file_type in {"txt","srt","vtt","json","zip"}:
        return f"transcript.{file_type}"
    if file_type in {"summary_md","summary_json"}:
        return file_type.replace("_", ".") if record.get("summary") else None
    if file_type.startswith("translation_"):
        fmt = file_type[len("translation_"):]
        langs = list(record.get("translations", {}))
        if fmt in {"txt","srt","vtt","json"} and len(langs) == 1:
            return f"translation_{langs[0]}.{fmt}"
    return None


def _write_exports(job_id: str, segments: list[dict[str, Any]], lang: str, method: str,
                   translations: dict[str,Any] | None = None, summary: dict[str,Any] | None = None) -> None:
    job = jobs[job_id]
    record = {"source": job.source, "title": job.title, "language": lang, "method": method,
              "segments": segments, "translations": translations or {}, "summary": summary}
    for filename, payload in _exports(record).items():
        (job.workdir / filename).write_bytes(payload)
    library.save(job.id, job.source, job.title, lang, method, segments, translations, summary)
    _set(job_id, status="done", stage="Ready to download", language=lang,
         method=method, segment_count=len(segments),
         preview="\n".join(_shown_text(s) for s in segments)[:11000],
         extras={"translation_language": next(iter(translations or {}), ""), "summary": bool(summary),
                 "speakers": any(s.get("speaker") for s in segments)},
         library_id=job.id, finished_at=time.time())


def _enhance_and_save(job_id: str, segments: list[dict[str,Any]], language: str,
                      method: str, audio: Path | None, speakers: bool, target: str, summary_enabled: bool) -> None:
    # Feature problems must never destroy the original recognized transcript.
    warnings: list[str] = []
    if speakers:
        if audio is None:
            warnings.append("Speaker labels require speech audio; use Audio AI mode.")
        else:
            _set(job_id, stage="Identifying speaker turns with pyannote...")
            try: segments = assign_speakers(audio, segments)
            except EnhancementError as exc: warnings.append(str(exc))
            except Exception as exc:
                # Optional model bugs must never discard already recognized speech.
                print(f"[LinkScribe] Speaker labeling failed ({type(exc).__name__}) for job {job_id}")
                warnings.append("Speaker labeling failed unexpectedly; original transcript retained.")
    translations: dict[str, Any] = {}
    if target != "none":
        if language == target:
            translations[target] = [dict(s) for s in segments]
        else:
            _set(job_id, stage=f"Translating into {target} with local Ollama...")
            try: translations[target] = translate_segments(segments, target)
            except EnhancementError as exc: warnings.append("Translation: " + str(exc))
            except Exception as exc:
                print(f"[LinkScribe] Translation failed ({type(exc).__name__}) for job {job_id}")
                warnings.append("Translation failed unexpectedly; original transcript retained.")
    summary = None
    if summary_enabled:
        _set(job_id, stage="Creating chapters and AI summary locally...")
        try: summary = summarize_segments(segments)
        except EnhancementError as exc: warnings.append("Summary: " + str(exc))
        except Exception as exc:
            print(f"[LinkScribe] Summary failed ({type(exc).__name__}) for job {job_id}")
            warnings.append("Summary failed unexpectedly; original transcript retained.")
    _set(job_id, warnings=warnings, stage="Saving transcript to library...")
    _write_exports(job_id, segments, language, method, translations, summary)


def _process_link(job_id: str, source: Source, mode: str, language: str, model: str,
                  speakers: bool = False, target: str = "none", summary_enabled: bool = False) -> None:
    segments: list[dict[str, Any]] | None = None
    used_language = language
    method = "local_audio_ai"
    audio = None
    # Forced audio for diarization, so that speaker labels are evidence-based.
    if source.provider == "youtube" and mode != "audio" and not speakers:
        _set(job_id, stage="Checking available captions...")
        try:
            segments, used_language = _captions(source.video_id, language)
            method = "youtube_captions"
        except Exception as exc:
            if mode == "captions":
                raise ReadableError("Captions are not available for this link or language. Try Smart or AI audio mode.") from exc
    if segments is None:
        _set(job_id, stage="Fetching the video's audio...")
        audio, title = _download_source_audio(job_id, source)
        _set(job_id, title=title, stage="Recognizing speech locally...")
        segments, used_language = _recognize(audio, language, model)
    _enhance_and_save(job_id, segments, used_language, method, audio, speakers, target, summary_enabled)


def _process_upload(job_id: str, file_path: Path, language: str, model: str,
                    speakers: bool = False, target: str = "none", summary_enabled: bool = False) -> None:
    _set(job_id, stage="Checking media file...")
    _check_uploaded_duration(file_path)
    _set(job_id, stage="Recognizing speech locally...")
    segments, detected_language = _recognize(file_path, language, model)
    _enhance_and_save(job_id, segments, detected_language, "local_audio_ai", file_path,
                      speakers, target, summary_enabled)


def _batch_archive(batch_id: str) -> bytes:
    """Rebuild the archive from durable transcripts, even after a restart.

    Job workdirs and their temporary exports expire, but the library does not.
    """
    stored = batch_store.get(batch_id)
    if stored is None:
        raise ReadableError("Batch not found in persistent history.")
    stream = io.BytesIO()
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, item in enumerate(stored["jobs"], start=1):
            record = library.get(item["id"]) if item["status"] == "done" else None
            entry = {"number": index, "source": item["source"], "status": item["status"],
                     "title": record["title"] if record else item["title"],
                     "error": item["error"], "warnings": [],
                     "library_id": item["id"] if record else None}
            if record:
                prefix = f"{index:02d}_{item['id'][:8]}"
                for filename, content in _exports(record).items():
                    if filename.endswith((".txt", ".srt", ".vtt", ".json", ".md")):
                        archive.writestr(f"{prefix}/{filename}", content)
            elif item["status"] == "done":
                entry["status"] = "error"
                entry["error"] = "Transcript was removed from the library after processing."
            records.append(entry)
        manifest = {"batch_id": batch_id, "total": len(records),
                    "completed": sum(item["status"] in {"done", "error"} for item in records),
                    "failed": sum(item["status"] == "error" for item in records), "items": records}
        archive.writestr("batch-report.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return stream.getvalue()


def _process_batch(batch_id: str, items: list[Source], mode: str, language: str,
                   model: str, speakers: bool, target: str, summary_enabled: bool) -> None:
    batch = batches[batch_id]
    batch_store.mark_batch(batch_id, "working")
    batch.status = "working"
    persisted = batch_store.get(batch_id)
    assert persisted is not None
    previous = {item["id"]: item for item in persisted["jobs"]}
    for index, (job_id, source) in enumerate(zip(batch.job_ids, items)):
        job = jobs[job_id]
        old = previous[job_id]
        batch.stage = f"Processing {index + 1} of {len(items)}: {source.provider}"
        # If a crash occurred after the transcript was saved but before the
        # journal acknowledged it, skip costly retranscription on recovery.
        saved = library.get(job_id)
        if saved is not None:
            job.status, job.title, job.library_id = "done", saved["title"], job_id
            job.stage = "Restored completed transcript from library"
            batch_store.mark_item(job_id, "done", title=job.title, library_id=job_id)
        elif old["status"] == "error":
            # A definite per-video failure stays recorded; recovery does not
            # silently retry blocked or unauthorized sources forever.
            job.status, job.error, job.stage = "error", old["error"], "Previous attempt failed"
        else:
            batch_store.mark_item(job_id, "working")
            _guarded_worker(job_id, _process_link, source, mode, language, model,
                            speakers, target, summary_enabled)
            batch_store.mark_item(job_id, job.status, title=job.title, error=job.error,
                                  library_id=job.library_id)
        batch.completed += 1
        if job.status == "error":
            batch.failed += 1
    batch.stage = "Preparing batch archive..."
    payload = _batch_archive(batch_id)
    batch.workdir.mkdir(parents=True, exist_ok=True)
    (batch.workdir / "batch.zip").write_bytes(payload)
    batch_store.mark_batch(batch_id, "done")
    batch.status, batch.stage, batch.finished_at = "done", "Batch complete", time.time()


def _guarded_batch(batch_id: str, *args: Any) -> None:
    try:
        _process_batch(batch_id, *args)
    except Exception as exc:
        print(f"[LinkScribe] Batch {batch_id} failed: {type(exc).__name__}: {exc}")
        batch = batches[batch_id]
        batch.status, batch.stage, batch.finished_at = "error", "Batch failed; check server log", time.time()
        try: batch_store.mark_batch(batch_id, "error")
        except Exception as journal_exc:
            print(f"[LinkScribe] Unable to mark batch {batch_id} error: {type(journal_exc).__name__}")


def _restore_pending_batches() -> None:
    """Run at application startup to resume interrupted local video batches."""
    for stored in batch_store.unfinished():
        batch_id = stored["id"]
        with lock:
            if batch_id in batches:
                continue
        try:
            cfg = stored["options"]
            links = [parse_source(item["source"]) for item in stored["jobs"]]
            if any(item["source"] != source.url for item, source in zip(stored["jobs"], links)):
                raise ValueError("Non-canonical stored batch URL")
            mode, language, model = cfg["mode"], cfg["language"], cfg["model"]
            speakers, target, summary = cfg["speakers"], cfg["target"], cfg["summary"]
            _validate_common(language, model, True)
            if mode not in MODES or target not in {"none", "en", "el"}:
                raise ValueError("Unsupported stored batch options")
            for source in links:
                _validate_enhancements(mode, source.provider, speakers, target)
            directory = DATA_DIR / "batches" / batch_id
            directory.mkdir(parents=True, exist_ok=True)
            batch = Batch(id=batch_id, workdir=directory,
                          job_ids=[item["id"] for item in stored["jobs"]])
            with lock:
                batches[batch_id] = batch
                for item in stored["jobs"]:
                    identifier = item["id"]
                    workdir = DATA_DIR / identifier
                    workdir.mkdir(parents=True, exist_ok=True)
                    jobs[identifier] = Job(id=identifier, workdir=workdir,
                        source=item["source"], title=item["title"], batch_id=batch_id,
                        stage="Resuming interrupted batch...", status="queued")
            pool.submit(_guarded_batch, batch_id, links, mode, language, model,
                        speakers, target, summary)
        except Exception as exc:
            print(f"[LinkScribe] Cannot recover batch {batch_id}: {type(exc).__name__}: {exc}")
            batch_store.mark_batch(batch_id, "error")


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "LinkScribe", "js_runtime": runtime_details()}


@app.get("/api/diagnostics")
def local_diagnostics():
    return diagnostics.report()


def _validate_enhancements(mode: str, provider: str, speakers: bool, target: str) -> None:
    if mode not in MODES:
        raise HTTPException(400, "Invalid transcription mode.")
    if target not in {"none","en","el"}:
        raise HTTPException(400, "Translation target must be None, English or Greek.")
    if mode == "captions" and provider != "youtube":
        raise HTTPException(400, "Captions-only mode currently supports only YouTube.")
    if speakers and mode == "captions":
        raise HTTPException(400, "Speaker labeling needs audio. Select Smart or Audio AI.")


@app.post("/api/link")
def submit_link(request: Request, url: str = Form(...), mode: str = Form("smart"),
                language: str = Form("auto"), model: str = Form("small"),
                consent: bool = Form(False), speakers: bool = Form(False),
                target_language: str = Form("none"), summary: bool = Form(False)):
    _check_browser_origin(request)
    _validate_common(language, model, consent)
    try: source = parse_source(url)
    except ValueError as exc: raise HTTPException(400,str(exc)) from None
    _validate_enhancements(mode, source.provider, speakers, target_language)
    job = _new_job(source=source.url, title=f"{source.provider.title()} {source.video_id}")
    return _start_job(job, _process_link, source, mode, language, model, speakers, target_language, summary)


@app.post("/api/upload")
async def submit_upload(request: Request, file: UploadFile = File(...),
                        language: str = Form("auto"), model: str = Form("small"),
                        consent: bool = Form(False), speakers: bool = Form(False),
                        target_language: str = Form("none"), summary: bool = Form(False)):
    _check_browser_origin(request)
    _validate_common(language, model, consent)
    if target_language not in {"none","en","el"}:
        raise HTTPException(400,"Unsupported translation language.")
    original_name = (file.filename or "recording").replace("\\", "/").split("/")[-1]
    suffix = Path(original_name).suffix.lower()
    if suffix not in ACCEPTED_SUFFIXES:
        raise HTTPException(400,"Unsupported file type. Use audio or video such as MP3, WAV, MP4 or WebM.")
    job = _new_job(source=f"uploaded:{original_name[:140]}", title=original_name[:140])
    target = job.workdir / ("input" + suffix)
    try:
        total = 0
        with target.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(413,"The upload limit is 150 MB.")
                destination.write(chunk)
        if total == 0: raise HTTPException(400,"The uploaded file is empty.")
    except Exception:
        with lock: jobs.pop(job.id, None)
        shutil.rmtree(job.workdir,ignore_errors=True)
        raise
    finally:
        await file.close()
    return _start_job(job,_process_upload,target,language,model,speakers,target_language,summary)


@app.post("/api/batch")
def submit_batch(request: Request, urls: str = Form(...), mode: str = Form("smart"),
                 language: str = Form("auto"), model: str = Form("small"),
                 consent: bool = Form(False), speakers: bool = Form(False),
                 target_language: str = Form("none"), summary: bool = Form(False)):
    _check_browser_origin(request)
    _validate_common(language,model,consent)
    if len(urls) > 50000: raise HTTPException(400,"Batch input is too long.")
    strings=[line.strip() for line in urls.splitlines() if line.strip()]
    if not 1 <= len(strings) <= MAX_BATCH_SIZE:
        raise HTTPException(400,"Enter between 1 and 20 links, one per line.")
    try: items=[parse_source(link) for link in strings]
    except ValueError as exc: raise HTTPException(400,str(exc)) from None
    if len({source.url for source in items}) != len(items):
        raise HTTPException(400,"Remove duplicate video links from the batch.")
    for source in items: _validate_enhancements(mode,source.provider,speakers,target_language)
    _cleanup_expired()
    with lock:
        if _active_count() >= MAX_ACTIVE:
            raise HTTPException(429,"The processing queue is full; retry shortly.")
        batch_id=uuid.uuid4().hex
        directory=DATA_DIR / "batches" / batch_id
        directory.mkdir(parents=True,exist_ok=False)
        batch=Batch(id=batch_id,workdir=directory,job_ids=[])
        batches[batch_id]=batch
        for source in items:
            child=_new_job(source.url,f"{source.provider.title()} {source.video_id}",batch_id=batch_id)
            batch.job_ids.append(child.id)
    options = {"mode": mode, "language": language, "model": model,
               "speakers": speakers, "target": target_language, "summary": summary}
    try:
        batch_store.create(batch_id, [{"id": jobs[job_id].id,
                        "source": jobs[job_id].source, "title": jobs[job_id].title}
                        for job_id in batch.job_ids], options)
        pool.submit(_guarded_batch,batch_id,items,mode,language,model,speakers,target_language,summary)
    except (RuntimeError, OSError) as exc:
        with lock:
            batches.pop(batch_id,None)
            for identifier in batch.job_ids:
                job=jobs.pop(identifier,None)
                if job: shutil.rmtree(job.workdir,ignore_errors=True)
        shutil.rmtree(directory,ignore_errors=True)
        try: batch_store.mark_batch(batch_id, "error")
        except Exception: pass
        raise HTTPException(503,"Processing service is unavailable.") from None
    return {"id":batch_id,"count":len(items)}


@app.get("/api/batches")
def list_saved_batches():
    """Allow reconnecting to past batches after server restart."""
    return {"items": [{"id": batch["id"], "status": batch["status"],
                       "total": len(batch["jobs"]),
                       "completed": sum(j["status"] in {"done", "error"} for j in batch["jobs"]),
                       "failed": sum(j["status"] == "error" for j in batch["jobs"])}
                      for batch in batch_store.recent()]}


@app.get("/api/batches/{batch_id}")
def batch_status(batch_id: str):
    _cleanup_expired()
    if not JOB_ID_RE.fullmatch(batch_id): raise HTTPException(404, "Batch not found.")
    saved = batch_store.get(batch_id)
    if saved is None: raise HTTPException(404, "Batch not found.")
    with lock:
        batch = batches.get(batch_id)
        children = []
        for item in saved["jobs"]:
            child = jobs.get(item["id"])
            children.append({"id": item["id"], "title": child.title if child else item["title"],
                             "source": item["source"], "status": child.status if child else item["status"],
                             "stage": child.stage if child else "Restored from disk",
                             "error": child.error if child else item["error"],
                             "warnings": child.warnings if child else [],
                             "library_id": child.library_id if child else item["library_id"]})
        return {"id": batch_id, "status": batch.status if batch else saved["status"],
                "stage": batch.stage if batch else "Saved batch",
                "total": len(children),
                "completed": sum(child["status"] in {"done", "error"} for child in children),
                "failed": sum(child["status"] == "error" for child in children),
                "jobs": children}


@app.get("/api/batches/{batch_id}/download")
def batch_download(batch_id: str):
    if not JOB_ID_RE.fullmatch(batch_id): raise HTTPException(404, "Batch not found.")
    saved = batch_store.get(batch_id)
    if not saved or saved["status"] != "done":
        raise HTTPException(404, "Batch not ready.")
    payload = _batch_archive(batch_id)
    return StreamingResponse(io.BytesIO(payload), media_type="application/zip",
               headers={"Content-Disposition": f'attachment; filename="linkscr-batch-{batch_id[:8]}.zip"',
                        "Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    _cleanup_expired()
    if not JOB_ID_RE.fullmatch(job_id): raise HTTPException(404,"Job not found.")
    with lock:
        job=jobs.get(job_id)
        if not job: raise HTTPException(404,"Job expired or not found.")
        return {"id":job.id,"status":job.status,"stage":job.stage,
                "title":job.title,"language":job.language,"method":job.method,
                "preview":job.preview,"error":job.error,"segments":job.segment_count,
                "warnings":job.warnings,"extras":job.extras,"library_id":job.library_id}


@app.get("/api/jobs/{job_id}/download/{file_type}")
def download(job_id: str,file_type: str):
    _cleanup_expired()
    if not JOB_ID_RE.fullmatch(job_id) or file_type not in FORMATS:
        raise HTTPException(404,"File not found.")
    with lock:
        job=jobs.get(job_id)
        if not job or job.status != "done": raise HTTPException(404,"Transcript not ready or expired.")
        record=library.get(job.library_id)
    if not record: raise HTTPException(404,"Transcript was deleted from the library.")
    key=_export_key(file_type,record)
    if not key: raise HTTPException(404,"Requested enhancement was not generated.")
    contents=_exports(record)[key]  # Current saved edits, never stale temporary exports.
    mime="application/zip" if key.endswith(".zip") else ("application/json" if key.endswith(".json") else "text/plain; charset=utf-8")
    return StreamingResponse(io.BytesIO(contents),media_type=mime,
                             headers={"Content-Disposition":f'attachment; filename="{key}"',
                                      "Cache-Control":"no-store"})


@app.get("/api/library")
def list_library(q: str = "", limit: int = 50):
    if len(q) > 200: raise HTTPException(400,"Search query is too long.")
    return {"items":library.list_items(q,limit)}


@app.get("/api/library/backup")
def export_library_backup():
    try:
        content, _count = library_backup.make_backup()
    except library_backup.BackupError as exc:
        raise HTTPException(413, str(exc)) from None
    return StreamingResponse(io.BytesIO(content), media_type="application/zip",
               headers={"Content-Disposition": 'attachment; filename="linkscr-library-backup.zip"',
                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/api/library/restore")
async def import_library_backup(request: Request, file: UploadFile = File(...)):
    _check_browser_origin(request)
    buffer = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            buffer.extend(chunk)
            if len(buffer) > library_backup.MAX_ARCHIVE_BYTES:
                raise HTTPException(413, "Backup upload exceeds the 50 MB limit.")
        return {"ok": True, **library_backup.restore_backup(bytes(buffer))}
    except library_backup.BackupError as exc:
        raise HTTPException(400, str(exc)) from None
    finally:
        await file.close()


@app.get("/api/library/{item_id}")
def get_library_item(item_id: str):
    if not JOB_ID_RE.fullmatch(item_id): raise HTTPException(404,"Transcript not found.")
    record=library.get(item_id)
    if not record: raise HTTPException(404,"Transcript not found.")
    return record


@app.put("/api/library/{item_id}")
async def edit_library_item(item_id: str, request: Request):
    _check_browser_origin(request)
    if not JOB_ID_RE.fullmatch(item_id): raise HTTPException(404,"Transcript not found.")
    record=library.get(item_id)
    if not record: raise HTTPException(404,"Transcript not found.")
    try: data=await request.json()
    except ValueError: raise HTTPException(400,"Invalid JSON.") from None
    if not isinstance(data,dict): raise HTTPException(400,"Invalid edit body.")
    title=data.get("title")
    changes=data.get("segments")
    if not isinstance(title,str) or not title.strip() or len(title)>180:
        raise HTTPException(400,"Title must be 1–180 characters.")
    old=record["segments"]
    if not isinstance(changes,list) or len(changes)!=len(old):
        raise HTTPException(400,"Every segment must be preserved in the original order.")
    updated=[]
    for original,change in zip(old,changes):
        if not isinstance(change,dict): raise HTTPException(400,"Invalid segment.")
        text=change.get("text"); speaker=change.get("speaker",original.get("speaker",""))
        if not isinstance(text,str) or not text.strip() or len(text)>5000 or not isinstance(speaker,str) or len(speaker)>80:
            raise HTTPException(400,"Invalid segment text or speaker label.")
        updated.append({**original,"text":text.strip().replace("\r"," ").replace("\n"," "),
                        **({"speaker":speaker.strip()} if speaker.strip() else {})})
        if not speaker.strip(): updated[-1].pop("speaker",None)
    library.update(item_id,title.strip(),updated)
    return {"ok":True,"id":item_id,"message":"Edits saved. Previous translations and summaries were cleared because the transcript changed."}


@app.delete("/api/library/{item_id}")
def delete_library_item(item_id: str, request: Request):
    _check_browser_origin(request)
    if not JOB_ID_RE.fullmatch(item_id) or not library.delete(item_id):
        raise HTTPException(404,"Transcript not found.")
    return {"ok":True}


@app.get("/api/library/{item_id}/download/{file_type}")
def library_download(item_id: str, file_type: str):
    if not JOB_ID_RE.fullmatch(item_id) or file_type not in FORMATS:
        raise HTTPException(404,"File not found.")
    record=library.get(item_id)
    if not record: raise HTTPException(404,"Transcript not found.")
    name=_export_key(file_type,record)
    if not name: raise HTTPException(404,"Requested enhancement not available.")
    content=_exports(record)[name]
    mime="application/zip" if name.endswith(".zip") else ("application/json" if name.endswith(".json") else "text/plain; charset=utf-8")
    return StreamingResponse(io.BytesIO(content),media_type=mime,
                             headers={"Content-Disposition":f'attachment; filename="{name}"',
                                      "Cache-Control":"no-store"})


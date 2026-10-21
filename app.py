"""LinkScribe: a local-first YouTube / media-to-transcript web app.

Run with: python -m uvicorn app:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 150 * 1024 * 1024             # 150 MB per uploaded/downloaded input
MAX_SECONDS = 2 * 60 * 60                 # 2 hours per recording
JOB_TTL = 60 * 60                        # completed jobs retained locally for 1 hour
MAX_ACTIVE = 8                          # queued + processing
ACCEPTED_SUFFIXES = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".mov", ".mkv", ".aac", ".opus"}
LANGUAGES = {"auto", "en", "el", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar"}
MODELS = {"tiny", "base", "small"}
MODES = {"smart", "audio", "captions"}
FORMATS = {"txt", "srt", "vtt", "json", "zip"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
JOB_ID_RE = re.compile(r"^[a-f0-9]{32}$")

app = FastAPI(title="LinkScribe", version="0.1.0", docs_url=None, redoc_url=None)
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


jobs: dict[str, Job] = {}


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
    to_remove: list[Job] = []
    with lock:
        for identifier, job in list(jobs.items()):
            if job.finished_at and time.time() - job.finished_at > JOB_TTL:
                to_remove.append(job)
                del jobs[identifier]
    for job in to_remove:
        shutil.rmtree(job.workdir, ignore_errors=True)


def _new_job(source: str, title: str = "Transcript") -> Job:
    _cleanup_expired()
    with lock:
        active = sum(job.status not in {"done", "error"} for job in jobs.values())
        if active >= MAX_ACTIVE:
            raise HTTPException(429, "The transcription queue is full; retry shortly.")
        identifier = uuid.uuid4().hex
        directory = DATA_DIR / identifier
        directory.mkdir(parents=True, exist_ok=False)
        job = Job(id=identifier, workdir=directory, source=source, title=title)
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


def _download_youtube_audio(job_id: str, video_id: str) -> tuple[Path, str]:
    import yt_dlp

    job = jobs[job_id]
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
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
    # As of 2026 YouTube can require a JS challenge solver. Deno is enabled
    # by default; enable Node if it is the available local runtime.
    if not shutil.which("deno") and shutil.which("node"):
        options["js_runtimes"] = {"node": {}}

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if not info:
                raise ReadableError("YouTube did not return video details.")
            length = info.get("duration")
            if length and length > MAX_SECONDS:
                raise ReadableError("The video exceeds the 2-hour limit for this starter app.")
            expected_size = info.get("filesize") or info.get("filesize_approx")
            if expected_size and expected_size > MAX_BYTES:
                raise ReadableError("The audio exceeds the 150 MB input limit.")
            title = str(info.get("title") or "YouTube video")[:180]
            ydl.download([youtube_url])
    except ReadableError:
        raise
    except Exception as exc:
        raise ReadableError(
            "YouTube audio could not be accessed. Try the captions mode, "
            "update yt-dlp and install Deno or Node 22+, or upload media you may use."
        ) from exc

    candidate_paths = [p for p in job.workdir.glob("audio.*") if p.suffix.lower() in ACCEPTED_SUFFIXES and p.is_file()]
    if not candidate_paths:
        raise ReadableError("No usable audio stream was downloaded from this video.")
    audio_path = max(candidate_paths, key=lambda p: p.stat().st_size)
    if audio_path.stat().st_size > MAX_BYTES:
        raise ReadableError("The downloaded audio is over 150 MB.")
    return audio_path, title


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


def _render_subtitles(segments: list[dict[str, Any]], fmt: str) -> str:
    blocks = []
    for i, s in enumerate(segments, start=1):
        start = _timecode(s["start"], fmt)
        end = _timecode(max(s["end"], s["start"] + 0.1), fmt)
        text = s["text"].strip().replace("\r", " ")
        index = f"{i}\n" if fmt == "srt" else ""
        blocks.append(f"{index}{start} --> {end}\n{text}\n")
    return ("WEBVTT\n\n" if fmt == "vtt" else "") + "\n".join(blocks)


def _write_exports(job_id: str, segments: list[dict[str, Any]], lang: str, method: str) -> None:
    job = jobs[job_id]
    text_content = "\n".join(segment["text"].strip() for segment in segments) + "\n"
    (job.workdir / "transcript.txt").write_text(text_content, encoding="utf-8")
    (job.workdir / "transcript.srt").write_text(_render_subtitles(segments, "srt"), encoding="utf-8")
    (job.workdir / "transcript.vtt").write_text(_render_subtitles(segments, "vtt"), encoding="utf-8")
    (job.workdir / "transcript.json").write_text(
        json.dumps({"source": job.source, "title": job.title, "language": lang, "method": method, "segments": segments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with zipfile.ZipFile(job.workdir / "transcript.zip", "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for extension in ("txt", "srt", "vtt", "json"):
            bundle.write(job.workdir / f"transcript.{extension}", f"transcript.{extension}")
    _set(job_id, status="done", stage="Ready to download", language=lang,
         method=method, segment_count=len(segments), preview=text_content[:11000], finished_at=time.time())


def _process_link(job_id: str, video_id: str, mode: str, language: str, model: str) -> None:
    segments: list[dict[str, Any]] | None = None
    used_language = language
    method = "local_audio_ai"
    if mode != "audio":
        _set(job_id, stage="Checking available captions...")
        try:
            segments, used_language = _captions(video_id, language)
            method = "youtube_captions"
        except Exception as exc:
            if mode == "captions":
                raise ReadableError("Captions are not available for this link or language. Try Smart or AI audio mode.") from exc
    if segments is None:
        _set(job_id, stage="Fetching the video's audio...")
        audio, title = _download_youtube_audio(job_id, video_id)
        _set(job_id, title=title, stage="Recognizing speech locally (first use downloads the model)...")
        segments, used_language = _recognize(audio, language, model)
    _set(job_id, stage="Creating download files...")
    _write_exports(job_id, segments, used_language, method)


def _process_upload(job_id: str, file_path: Path, language: str, model: str) -> None:
    _set(job_id, stage="Checking media file...")
    _check_uploaded_duration(file_path)
    _set(job_id, stage="Recognizing speech locally (first use downloads the model)...")
    segments, detected_language = _recognize(file_path, language, model)
    _set(job_id, stage="Creating download files...")
    _write_exports(job_id, segments, detected_language, "local_audio_ai")


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "LinkScribe"}


@app.post("/api/link")
def submit_link(
    request: Request,
    url: str = Form(...),
    mode: str = Form("smart"),
    language: str = Form("auto"),
    model: str = Form("small"),
    consent: bool = Form(False),
):
    _check_browser_origin(request)
    _validate_common(language, model, consent)
    if mode not in MODES:
        raise HTTPException(400, "Invalid transcription mode.")
    try:
        video_id = youtube_video_id(url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    job = _new_job(source=canonical_url, title=f"YouTube video {video_id}")
    return _start_job(job, _process_link, video_id, mode, language, model)


@app.post("/api/upload")
async def submit_upload(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model: str = Form("small"),
    consent: bool = Form(False),
):
    _check_browser_origin(request)
    _validate_common(language, model, consent)
    original_name = (file.filename or "recording").replace("\\", "/").split("/")[-1]
    suffix = Path(original_name).suffix.lower()
    if suffix not in ACCEPTED_SUFFIXES:
        raise HTTPException(400, "Unsupported file type. Use audio or video such as MP3, WAV, MP4 or WebM.")
    job = _new_job(source=f"uploaded:{original_name[:140]}", title=original_name[:140])
    target = job.workdir / ("input" + suffix)
    try:
        total = 0
        with target.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(413, "The upload limit is 150 MB.")
                destination.write(chunk)
        if total == 0:
            raise HTTPException(400, "The uploaded file is empty.")
    except Exception:
        with lock:
            jobs.pop(job.id, None)
        shutil.rmtree(job.workdir, ignore_errors=True)
        raise
    finally:
        await file.close()
    return _start_job(job, _process_upload, target, language, model)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    _cleanup_expired()
    if not JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(404, "Job not found.")
    with lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job expired or not found.")
        return {
            "id": job.id, "status": job.status, "stage": job.stage,
            "title": job.title, "language": job.language, "method": job.method,
            "preview": job.preview, "error": job.error,
            "segments": job.segment_count,
        }


@app.get("/api/jobs/{job_id}/download/{file_type}")
def download(job_id: str, file_type: str):
    _cleanup_expired()
    if not JOB_ID_RE.fullmatch(job_id) or file_type not in FORMATS:
        raise HTTPException(404, "File not found.")
    with lock:
        job = jobs.get(job_id)
        if job is None or job.status != "done":
            raise HTTPException(404, "Transcript not ready or expired.")
        filename = job.workdir / f"transcript.{file_type}"
        if not filename.is_file():
            raise HTTPException(404, "File not found.")
    media = {"txt": "text/plain", "srt": "text/plain", "vtt": "text/vtt", "json": "application/json", "zip": "application/zip"}
    return FileResponse(filename, media_type=media[file_type], filename=f"linkscr-{job_id[:8]}.{file_type}")

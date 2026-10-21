# LinkScribe — video links to downloadable transcripts

A **local-first** web app: paste a YouTube video link or upload your own media, transcribe it, preview it, and download TXT, SRT, VTT, JSON, or a ZIP containing them all. The browser UI is mobile-friendly; the transcription runs on **your computer** rather than a commercial speech API.

## Quick start — Windows

1. Install Python 3.11, 3.12, or 3.13 from https://www.python.org/downloads/ (on Windows, ensure the Python launcher `py` is installed).
2. Extract the ZIP and double-click `start_windows.bat`.
3. Open http://127.0.0.1:8765 if your browser does not open automatically.
4. Paste a video link, choose a mode, confirm you have permission, and click **Transcribe**.

## Quick start — Ubuntu / Linux

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
unzip LinkScribe-starter.zip
cd LinkScribe-starter
./start_linux.sh
```

Open http://127.0.0.1:8765 . If launching from an IDE, you can use `.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8765`.

## Modes

- **Smart** (recommended for speed): fetch available YouTube captions. If absent or blocked, try downloading audio and transcribing it locally.
- **AI audio**: always recognize speech **from audio** with faster-whisper. This is the closest to “whatever is actually said,” although no speech recognizer is 100% accurate.
- **Captions only**: use existing subtitles, with no speech-model download. Useful if you want text quickly.
- **Upload media**: upload an audio/video file directly and transcribe the audio. This is the most robust option for media you control.

**Language** can be auto-detected, or pinned to Greek, English, and several other options. Whisper generally detects one dominant language per recording; a mixed-language video might need review.

## YouTube setup for audio mode

YouTube sometimes requires yt-dlp to solve JavaScript challenges. As of October 2026, yt-dlp recommends **Deno 2.3+**. **Node 22+** is another supported option; the app enables Node if Deno isn't found. Install either and keep `yt-dlp[default]` updated:

- Deno: https://docs.deno.com/runtime/getting_started/installation/
- yt-dlp setup: https://github.com/yt-dlp/yt-dlp/wiki/EJS

Even then, some videos may be inaccessible (copyright restrictions, age gates, bot restrictions, private streams, site changes). The app **does not** attempt to bypass such restrictions. Use the local upload route when you have a lawful copy and permission to process it.

**YouTube's official API cannot download transcripts for arbitrary videos:** the documented `captions.download` endpoint requires edit permission on the video. This starter uses a third-party package that accesses YouTube's undocumented caption endpoints; it can break when YouTube changes its implementation.

## Models / CPU vs GPU

- `tiny`: fastest, lower accuracy.
- `base`: faster, reasonable for quick drafts.
- `small` (default): generally a better accuracy/speed compromise on CPU, especially for multilingual speech.

The first audio-transcription request downloads the selected model from Hugging Face. Model downloads, YouTube fetching, and checking dependencies need network access. **Your uploaded media is not sent to a paid transcription API**; speech recognition runs locally. You can explicitly enable NVIDIA CUDA with `LINKSCRIBE_DEVICE=cuda` if you have a compatible CUDA setup, otherwise it uses CPU INT8.

On a modest CPU, an hour-long file may take a while. Using preexisting captions is much faster.

## Limits / privacy / safety

- **Starter is local only:** binds to `127.0.0.1:8765`, no accounts, billing, tracking, or database.
- Accepts **individual YouTube URLs only**, not arbitrary external URLs, livestream archives that cannot be accessed, or playlists. This helps prevent remote-server-side request forgery (SSRF).
- Uploaded files must be one of: MP3, WAV, M4A, MP4, WebM, OGG, FLAC, MOV, MKV, AAC, OPUS.
- Maximum audio input size **150 MB**, maximum audio recording duration **2 hours** (longer caption-only videos may still work), and up to 8 queued/active jobs (1 model-processing worker).
- After processing, original input audio is deleted. Transcript files are kept locally under `data/` for **1 hour**, then removed when the service handles a later request. Stopping the service also stops cleanup; delete `data/` manually if desired.
- The app uses local-only binding, a Host allowlist, and cross-origin POST checks. Anyone with direct access to the local web server during that hour can retrieve the generated outputs if they know the unguessable job ID; it has no user-authentication feature. **Do not expose this version directly to the public internet**. A hosted version needs authentication, per-user isolation, rate limits, abuse controls, retention policy, and separate worker servers.
- Transcribe only media you own or are authorized to process; YouTube downloads and reproductions may be restricted by platform terms and applicable law.

## Developer API

- `GET /health`
- `POST /api/link` as multipart form: `url`, `mode=smart|audio|captions`, `language=auto|en|el|...`, `model=tiny|base|small`, `consent=true`
- `POST /api/upload`: multipart `file`, `language`, `model`, `consent=true`
- `GET /api/jobs/{job_id}` for queue/stage/results.
- `GET /api/jobs/{job_id}/download/{txt|srt|vtt|json|zip}` for output.

## Tests

```bash
python -m pip install pytest httpx
python -m pytest -q
```

Unit tests use dummy segments to verify URL validation, subtitle exports, API job behavior, and permission checks, without downloading YouTube content or transcription models. End-to-end transcription **requires installation and a real permitted video/audio file**. This starter was tested with local unit/API tests and browser UI smoke tests, but it has not been validated against a live YouTube video or a downloaded Whisper model in the creation environment (network access was unavailable).

## Next steps for a public service

Separate web app + persistent queue (Redis/RQ or Celery) + GPU worker + object storage with auto-expiry + domain-specific link providers + subscription/pay-as-you-go billing. Optional paid speech API can be swapped in as another worker backend. Build platform permission checks and terms compliance into each provider.

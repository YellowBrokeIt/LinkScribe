# LinkScribe — local-first video transcription, translation and transcript library

LinkScribe is a **real, locally hosted** Python web app for downloading captions or transcribing permitted video/audio. The stable release lives on `master`. Reliability work for v0.3 is being reviewed on `feature/linkscribe-v03-reliability`; it must pass independent GitHub-hosted tests before merging.

## Features

- **Single links or batches of 1–20 links**: YouTube, Vimeo and Dailymotion, allowlisted/canonicalized; sequential processing and batch ZIP of successful results. Vimeo/Dailymotion currently use audio recognition, not pre-existing captions.
- **Speaker identification (opt-in)**: anonymous `Speaker 1`, `Speaker 2` labels from pyannote Community-1 diarization, aligned with Whisper segments. Requires extra dependencies and Hugging Face model access; labels are estimates and names must be assigned manually.
- **Translation**: English ⇄ Greek (and other source languages into English/Greek) with **local Ollama**; retains original segment times for translated subtitle exports.
- **AI summary and chapters**: local Ollama creates summaries, key points and chapter titles anchored to transcript segment timestamps. Review outputs for errors.
- **Persistent transcript library**: local SQLite store with full-text search by title/transcript, editing of segment text/speaker names, deletion and on-demand exports. Original audio is deleted after each processing job. Edit invalidates stale translation/summary so saved exports remain consistent.
- **Uploads**: MP3, WAV, MP4 and other accepted audio/video formats.
- **Exports**: TXT, SRT, VTT, JSON, ZIP, translated TXT/SRT/VTT/JSON, and summary MD/JSON.

No paid API keys are required for base transcription. Optional speaker labeling requires HF_TOKEN to download its model. Optional translation/summaries require an Ollama model installed locally.

## Quick start — Linux (Ubuntu)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ffmpeg
git clone https://github.com/YellowBrokeIt/LinkScribe.git
cd LinkScribe
bash start_linux.sh
```

Open `http://127.0.0.1:8765` **on the same machine** (by design it only listens on loopback). On a desktop, optional `bash launch.sh` starts the local server in the background and opens a browser if the venv is already installed. If you run Linux remotely, do not bind this app to `0.0.0.0`; use an authenticated tunnel/SSH port forwarding for personal access.

To inspect the **unreleased v0.3 candidate** separately from a stable clone, use `git switch feature/linkscribe-v03-reliability` before `bash start_linux.sh`. This is not required for the latest stable `master`.

## YouTube JS runtime — Deno preferred, Node fallback

yt-dlp needs a JavaScript runtime for some YouTube playback challenges. **Deno 2.3+** is recommended and enabled by default; **Node.js is permitted only on release lines patched against the October 21, 2026 security advisory**. This app checks installed major/minor/patch versions, prefers Deno when supported, and explicitly enables Node only if Deno is unavailable or outdated *and* Node meets its security floor. Older, end-of-life and unreviewed release lines are rejected. It does not force Node when Deno is working. The `/health` endpoint shows detected runtime and installation advice.

- Install Deno 2.3+ from https://docs.deno.com/runtime/getting_started/installation/
- Or install a supported **security-patched Node.js release** from https://nodejs.org/en/download:
  - **22.x:** `22.23.4` or newer within 22.x
  - **24.x:** `24.22.1` or newer within 24.x (**recommended Node LTS fallback**)
  - **26.x:** `26.12.1` or newer within 26.x
- Security advisory: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases (October 21, 2026). These are minimum patched versions **as of this advisory**; keep Node and Deno updated for future advisories. Do not assume an unreviewed newer Node major is permitted until LinkScribe's allowlist has been updated.
- Keep `yt-dlp[default]` updated with `./.venv/bin/python -m pip install -U 'yt-dlp[default]'`. The `[default]` extra installs matched EJS scripts.
- YouTube can block some videos, age-gated content, private links, or automated downloads despite valid setup. Do not bypass restrictions; upload an authorized recording instead.

Even without a JavaScript runtime, caption retrieval may still work. Non-YouTube sources may not require a JS runtime. LinkScribe will show a clear download error if access fails.

## Optional translation, summaries and chapters (Ollama)

1. Install Ollama from https://ollama.com/download and start the local daemon (`ollama serve` if it isn't already running).
2. Pull an instruction model with multilingual and JSON output support: `ollama pull qwen3:4b`.
3. Optionally set `LINKSCRIBE_OLLAMA_MODEL=qwen3:4b` (default) in the environment **before starting** LinkScribe.
4. Check **AI summary & chapters** and/or choose the English or Greek translation target.

Ollama must listen on `127.0.0.1:11434` or `localhost:11434`. Media/audio is not sent to Ollama; only transcript text is sent to the **local Ollama process**. These operations are optional. If Ollama fails, the original transcript and library record remain available, with warnings.

## Optional speaker identification (pyannote)

```bash
# from the repository root, after initial start_linux.sh created .venv
./.venv/bin/python -m pip install -r requirements-speakers.txt
```

1. Accept the model conditions at https://huggingface.co/pyannote/speaker-diarization-community-1 and create a Hugging Face access token at https://huggingface.co/settings/tokens.
2. Export it in the same shell **before** starting LinkScribe: `export HF_TOKEN=...` (replace dots with your token, and never commit it).
3. Enable **Speaker labels** when submitting a video or upload. For links, LinkScribe uses audio AI instead of existing captions when speaker labeling is selected.

Speaker identity estimates can be wrong, especially with simultaneous speech or short segments. Speaker names are anonymous labels, not real identification. pyannote and its ML dependencies are substantial; an appropriate CPU/GPU and extra disk space are needed.

## Batch jobs

Enter one supported video URL per line (1–20) in the **Batch links** tab. Jobs are processed sequentially to avoid overloading a small CPU machine. Each completed transcript is stored in the persistent library. If an individual video fails, subsequent links still run. At the end, download one ZIP for successful jobs; failures are listed in the browser.

In **v0.3**, a SQLite batch journal saves queued jobs and completion statuses. On server startup, interrupted link batches resume from their next unsaved item; completed transcripts are never retranscribed if their library record exists. Explicit per-video failures remain failures rather than retrying restricted sources forever. Saved batch reports and ZIP exports can be downloaded again after restart. Use only **one** local server process with a given data directory. Individual uploads do not resume after interruption.

## Back up and restore your library (v0.3)

In the **Library** tab, choose **Download backup** to save a versioned ZIP containing all saved transcripts, timestamps, your edits, translation outputs, and summaries. Only text and metadata are included; audio, API secrets, and active batch work are not exported. Keep the backup in a safe place: it may contain sensitive transcript text.

To restore, select the saved ZIP and choose **Restore backup**. LinkScribe checks its SHA-256 integrity hash and validates the records **before any insertion**. Existing IDs and edits are never overwritten; only missing transcripts are imported. ZIP entries are allowlisted and bounded to 50 MB compressed / 100 MB transcript data. This protects against accidental or malformed imports, but is not a substitute for protecting your device and backups.

**Check setup** in the Library tab reports installed dependencies and optional AI readiness without showing the Hugging Face token. The API is `GET /api/diagnostics` and stays on the local-only server.

## Local storage and limits

- 150 MB maximum input, 2 hours maximum audio recording, 8 queued/active slots and one worker. Larger batches can run for many hours.
- `data/library.sqlite3` stores transcript text, source URL, titles and optional enhancements **until manually deleted**. Back it up if you want to keep the transcripts. Avoid keeping sensitive recordings in the library unless your machine is secured.
- Original input audio is cleaned up after each job. Temporary exports and in-memory job details expire after 1 hour; saved library text and batch reports do not. Recovery of interrupted link batches does not store video audio.
- All services bind to localhost, with origin and Host checks. **This is a single-user app with no authentication, no per-user isolation and no public-web protections. Do not expose it to the Internet or serve it through GitHub Pages as a working backend.**
- Sources must be permitted and allowed by their hosting platform. Do not use for unlicensed content.
- Only YouTube, Vimeo and Dailymotion allowlisted individual URLs are accepted; this is not a general-purpose fetch-any-URL API.

## API

- `GET /health` — status and JS runtime diagnosis
- `POST /api/link` — form fields: `url`, `mode` (`smart`, `audio`, `captions`), `language`, `model`, `consent=true`, `speakers`, `target_language` (`none`, `el`, `en`), `summary`
- `POST /api/upload` — media file, plus model/language/enhancement fields
- `POST /api/batch` — newline-separated `urls` (1–20), plus link options
- `GET /api/jobs/{id}` and `/api/jobs/{id}/download/{format}`
- `GET /api/batches`, `GET /api/batches/{id}` and `/api/batches/{id}/download` (persistent batch history and exports)
- `GET /api/diagnostics` (dependency and supported-JS-runtime checks, no access-token disclosures)
- `GET /api/library/backup` (versioned transcript ZIP) and `POST /api/library/restore` (non-destructive validated import)
- `GET /api/library?q=...` and `GET /api/library/{id}`
- `PUT /api/library/{id}` — title/segments edit (segment timestamps fixed)
- `DELETE /api/library/{id}`
- `GET /api/library/{id}/download/{format}` — full export, even after server restart

## Run tests

```bash
./.venv/bin/python -m pip install pytest httpx
./.venv/bin/python -m pytest -q
```

Network-free tests exercise validation, queueing, journal recovery, backup integrity, imports, exports, CRUD and failure cases. GitHub Actions independently tests the real file-upload → PyAV → Whisper Tiny → SQLite → export path on a generated speech sample, plus fresh Linux installation. Browser UI controls are checked with simulated API responses. **Live YouTube/Vimeo/Dailymotion extraction and real Ollama/pyannote-model inference have not all been independently verified.**

## GitHub Pages

The `gh-pages` branch is a **separate UI demonstration**, not the Python backend. The real application and all its features run on your own computer/instance.

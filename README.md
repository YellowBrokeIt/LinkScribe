# LinkScribe — local-first video transcription, translation and transcript library

LinkScribe is a **real, locally hosted** Python web app for downloading captions or transcribing permitted video/audio. The stable release lives on `master`. Reliability work for v0.3 is being reviewed on `feature/linkscribe-v03-reliability`; it must pass independent GitHub-hosted tests before merging.

The published **0.3.0 integration checkpoint `929cf2d`** passed 678 automated tests
and 32 subtests in each of five hosted platform/Python configurations, fresh
Linux installation, installation from the actual candidate archive and an actual
audio-upload workflow. Chromium passed all **34 checks**, including preservation
of corrections during saves and navigation, highlights after editing, and backups
containing saved highlights. The
[integration record](docs/integration-2026-11-28/README.md) retains the preceding
31/32 and 33/34 harness failures, their corrections and actual editor fixes.
Generated meaning still requires approval. Provider access and speech-quality
regressions also leave release gates open. The
[28 November checkpoint recovery](docs/checkpoint-recovery-2026-11-28/README.md)
records the exact tested commit, completed runs and remaining work; these
results do not certify later revisions or constitute a v1.0 release.
The downloaded source archive also passed a fresh local installation during
recovery. The candidate-artifact workflow now verifies installation from its
actual generated ZIP, in addition to the checkout-based installation checks.

Optional **source highlights** and explicit public Vimeo player links are now
integrated. The separately frozen English/Greek highlights validation passed all
four cases. The integrated candidate protects edits during asynchronous operations
and declares the download transport previously installed only by provider QA.
The aligned decoder with a two-second silence heuristic failed broader dialogue
review and is rejected for release; an isolated comparison is investigating the
cause before the recognition policy is accepted.
Hosted results must be checked for the exact revision under review; this remains
a draft rather than a v1.0 approval.

## Features

- **Single links or batches of 1–20 links**: accepts allowlisted YouTube, Vimeo and Dailymotion URLs; sequential processing and batch ZIP of successful results. Accepted URL formats do not guarantee provider access. Vimeo/Dailymotion currently use audio recognition, not pre-existing captions. See [verified provider scope](#verified-provider-scope).
- **Speaker labels (opt-in)**: anonymous `Speaker 1`, `Speaker 2` labels from a public CPU model, with no account or access token. Extra dependencies are required. Actual Whisper word timestamps allow text to split at estimated speaker changes; uncertain speech remains `Unknown speaker`. Overlapping voices are not separated, and names must be assigned manually.
- **Experimental translation drafts**: English ⇄ Greek (and other source languages into English/Greek) with **local Ollama**; retains original segment times for translated subtitle exports. Actual evaluations found material meaning errors, so compare translations with the original transcript.
- **AI summary and chapters**: local Ollama creates summaries, key points and chapter titles anchored to transcript segment timestamps. Review outputs for errors.
- **Source highlights (opt-in)**: locally selects verbatim passages with original timestamps, without a language model or extra downloads. Open an excerpt's source segments to review context. Short sources may be retained completely, with an explicit notice. This is separate from the AI summary and does not promise complete coverage or correct recognition.
- **Persistent transcript library**: local SQLite store with full-text search by title/transcript, editing of segment text/speaker names, deletion and on-demand exports. Original audio is deleted after each processing job. Edits invalidate stale translation, summary and source highlights so saved exports remain consistent. Source highlights can be regenerated from a saved transcript after editing.
- **Uploads**: MP3, WAV, MP4 and other accepted audio/video formats.
- **Exports**: TXT, SRT, VTT, JSON, ZIP, translated TXT/SRT/VTT/JSON, summary MD/JSON, and source highlights MD/JSON.

No paid API keys are required for base transcription or the default public speaker backend. The optional legacy pyannote backend still requires authorized model access. Optional translation/summaries require their selected local model to be installed.

The standard requirements include `curl-cffi` for the public-video transport
used by yt-dlp's Dailymotion extractor. **Check setup** identifies a missing
transport in an older installation. Transport availability does not override a
provider's authentication, embedding or network restrictions.

The requirements also include `socksio` so model downloads can use an existing
SOCKS proxy. This fixes an observed missing-dependency startup failure while
retaining the machine's proxy configuration and normal certificate checks.

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

When no installed runtime meets those requirements, LinkScribe explicitly disables yt-dlp's runtime selection so an unsupported Deno installation cannot be re-enabled by downloader defaults.

- Install Deno 2.3+ from https://docs.deno.com/runtime/getting_started/installation/
- Or install a supported **security-patched Node.js release** from https://nodejs.org/en/download:
  - **22.x:** `22.23.4` or newer within 22.x
  - **24.x:** `24.22.1` or newer within 24.x (**recommended Node LTS fallback**)
  - **26.x:** `26.12.1` or newer within 26.x
- Security advisory: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases (October 21, 2026). These are minimum patched versions **as of this advisory**; keep Node and Deno updated for future advisories. Do not assume an unreviewed newer Node major is permitted until LinkScribe's allowlist has been updated.
- Keep `yt-dlp[default]` updated with `./.venv/bin/python -m pip install -U 'yt-dlp[default]'`. The `[default]` extra installs matched EJS scripts.
- YouTube can block some videos, age-gated content, private links, or automated downloads despite valid setup. Do not bypass restrictions; upload an authorized recording instead.

Even without a JavaScript runtime, caption retrieval may still work. Non-YouTube sources may not require a JS runtime. LinkScribe will show a clear download error if access fails.

### Verified provider scope

The [integrated hosted checks](docs/integration-2026-11-28/README.md)
and [earlier checkpoint recovery](docs/checkpoint-recovery-2026-11-28/README.md)
and [earlier browser/provider evidence](docs/browser-provider-2026-11-26/README.md)
separate accepted URLs from actual acquisition and transcription. These results
describe the tested clips and environment, not universal availability:

| Provider | Observed end-to-end status |
| --- | --- |
| Dailymotion | At `dc0985d` and `f12afd8`, the complete 734.15-second licensed film passed download, recognition, SQLite storage, exports, cleanup, a mixed success/failure batch, and retrieval after restart. The subsequent `79189b0` request returned “No video formats found!” before ASR. A separately acquired complete publisher-listed audio source is being used for speech regression diagnosis; it does not convert this provider failure into a pass. |
| YouTube | At `dc0985d`, both hosted audio attempts returned “This content isn’t available.” A separately identified official full-film follow-up returned metadata and 33 formats but failed actual media acquisition with HTTP 403 in the local environment. Earlier bot sign-in and caption `IpBlocked` errors remain separate observations. No successful YouTube transcript is claimed. |
| Vimeo | The original regular-page attempt failed with “The web client only works when logged-in.” Preserving a separately supplied public player link fixed an application URL rewrite: a different licensed 888.07-second recording then passed download, full Small recognition, SQLite, exports, cleanup and restart locally. Subsequent hosted player requests returned HTTP401. The exact baseline-plus-parser experiment and its first dependency failure are retained; suspicious transcript phrases mean speech accuracy is not approved. |

The [public-provider follow-up](docs/provider-followup-2026-11-28/README.md)
identifies every fixture and tested source hash. Explicit `player.vimeo.com/video/ID`
links retain their public player route. Regular pages remain regular pages, and
private hashes, credentials and embed restrictions are not bypassed. Additional
hosted fixtures preserve their results separately from the original failures.

The [VAD diagnosis](docs/browser-provider-2026-11-26/assistant-vad-diagnosis.json)
records that Small decoded the full 734.15-second Dailymotion input, but VAD kept
no samples after 423.184 seconds. Separate VAD-off excerpts recovered later
dialogue without replacing the normal saved transcript. The
[ordinary full-recording follow-up](docs/asr-vad-off-2026-11-26/README.md) now
retains that later dialogue. It also exposed two invented words from exact
digital silence. The exact-zero correction is now verified in the
[hosted follow-up](docs/asr-zero-noise-2026-11-26/README.md): no model inference,
library record or export was created. That same run exposed a separate saved
hallucination from nonzero white noise.

The current candidate keeps complete nonzero audio intact. If every returned
nonblank ASR segment exceeds Faster Whisper's existing no-speech threshold, a
separate whole-recording speech check must find some speech before the result
is saved. That corroboration does not crop audio or filter individual decoder
results. In the
[paired actual comparison](docs/asr-speech-evidence-2026-11-26/README.md), the
candidate rejected the same noise output that the baseline saved, while
preserving identical text and timings for ordinary and 20 dB quieter Greek
and English recordings. The quiet English clip required the second detector
and was correctly retained. These seven fixtures do not establish general
accuracy on music, noise or very faint speech. The
[unseeded hosted follow-up at `dc0985d`](docs/checkpoint-recovery-2026-11-28/README.md)
also passed complete-film processing and rejection of exact silence and white
noise, without claiming general ASR accuracy. The
[public-caption probe](docs/public-captions-2026-11-26/README.md) preserves the
separate caption-access denial. The overall three-provider
gate remains failed; successful processing and faithful exports do not establish
transcription accuracy or subtitle synchronization.

The follow-up decoder candidate computes word alignment and enables Faster
Whisper's two-second hallucination/silence heuristic while retaining the normal
temperature fallback and supplying the whole recording without input VAD.
This can suppress suspicious output around silence and change subtitle
boundaries; it cannot establish that every remaining word is correct. The
[Vimeo ASR investigation](docs/asr-vimeo-followup-2026-11-28/README.md) retains
rejected deterministic and Turbo-only alternatives, the full-film candidate,
ordinary/quiet English-Greek comparisons, word-alignment scope and local
Dailymotion acquisition failures. Hosted acquisition then failed before the exact
Dailymotion regression could run. On separately verified complete publisher-listed
audio, all four target late phrases survived, but broader review found two other
spoken commands missing. The combined alignment/two-second-heuristic policy is
therefore rejected for release. Its four-anchor pass is retained with the broader
failure; neither is treated as overall speech accuracy approval.

## Optional source highlights

Check **Source highlights** before processing a link, upload or batch. For an
existing saved transcript, open it from **Library** and choose **Create source
highlights**. Save pending edits first. Each passage links to its original source
segments; downloads include its original text and timestamp boundaries.

The selector uses bounded CPU work and does not call Ollama. It can omit distant
context, preserve recognition errors or include multiple speakers in one passage.
Consult the full transcript for speaker labels and context. If the whole modest
source is retained, the display and Markdown explicitly state that no condensation
was made. Editing invalidates the old selection; regenerating uses the new text.
Invalid or stale optional highlights never block downloading the original.

The [controlled English/Greek evaluation](docs/source-highlights-2026-11-28/README.md)
retains two development failures, their general fixes, and the first frozen
validation results. The final candidate passed six development and four previously
unseen cases, preserving all declared source goals and exact text/times. These
internal fixtures do not certify arbitrary meetings or replace the separate
AI-summary quality gate.

## Optional translation, summaries and chapters (Ollama)

1. Install Ollama from https://ollama.com/download and start the local daemon (`ollama serve` if it isn't already running).
2. Pull an instruction model with multilingual and JSON output support: `ollama pull qwen3:4b`.
3. Optionally set `LINKSCRIBE_OLLAMA_MODEL=qwen3:4b` (default) in the environment **before starting** LinkScribe.
4. Check **AI summary & chapters** and/or choose the English or Greek translation target.

Translation can use a different installed model: set `LINKSCRIBE_TRANSLATION_MODEL`
before starting the app. When this override is absent, translation inherits
`LINKSCRIBE_OLLAMA_MODEL`; summaries always use `LINKSCRIBE_OLLAMA_MODEL`.
**Check setup** reports each selected model separately. A missing or invalid
translation model does not disable summaries or discard the original transcript.

The experimental dedicated adapters support detected English and Greek source
languages, including regional caption tags. `translategemma:4b` uses its native
plain-text prompt. For the tested Hy-MT3 1.8B import, first run
`ollama create linkscribe-hy-mt3:1.8b -f models/hy-mt3-1.8b.Modelfile` from this
folder, then select `LINKSCRIBE_TRANSLATION_MODEL=linkscribe-hy-mt3:1.8b`.
The checked-in template corrects a malformed automatic import observed in
Ollama 0.40.12. These adapters are evaluation options, **not approved quality
defaults**; development examples still contain material meaning errors.

Ollama must listen on `127.0.0.1:11434` or `localhost:11434`. Media/audio is not sent to Ollama; only transcript text is sent directly to the **local Ollama process**, without environment proxies or HTTP redirects. **Check setup** distinguishes a running Ollama server from a missing selected model. These operations are optional. If Ollama fails or returns incomplete output, the original transcript and library record remain available, with warnings.

**Translation remains experimental.** The [original default-model evaluation](docs/evaluation-2026-11-26/README.md)
and [subsequent local-model comparisons](docs/translation-models-2026-11-26/README.md)
found material errors involving actors, objects, quantities, negation and
conditions, even when every request completed successfully. No replacement
translation default has been approved. The original transcript is retained for
comparison; timing, storage and export checks do not certify meaning.

When a known English-to-Greek or Greek-to-English request returns the entire
transcript unchanged, the app reports that no separate translation was generated
and keeps the original without a misleading translated download. Unchanged
names alone receive the same neutral notice; numbers and punctuation can remain
identical. This check catches a copied response, not other language or meaning
errors. The [complete-workflow evidence](docs/full-workflow-2026-11-26/README.md)
records the real model failure that prompted it.

**Summaries and chapters are drafts.** The
[actual summary evaluation](docs/summary-2026-11-26/README.md) preserves both
improvements and failed outputs. Source text is processed completely in bounded
requests, and short sources use a direct summary. The current candidate requests
one to eight key points with a matching model schema and local validation, after
a real long-summary response exceeded the old unstated point limit. Input
excerpts and intermediate notes are bounded by serialized UTF-8 size. Actual
evaluation still finds numerical errors and changes from planned to completed
actions. A faster experiment with stricter generated-note lengths was rejected
after factual regressions and unfinished sentences; it is not the production
summary path. Factual accuracy, permission limits and final decisions need review against the
original; failed enhancements retain that original with a visible warning.

For a CPU thread limit, set `LINKSCRIBE_OLLAMA_THREADS` before starting the app, for example `LINKSCRIBE_OLLAMA_THREADS=4`. Values from 1 through 32 are accepted. Leaving it unset or empty keeps Ollama's automatic choice; the other inference settings remain unchanged. The repeatable language QA uses four threads and records the actual request options.

### Model lifetime and memory

When a job needs translation or summary, the app releases already-loaded
Whisper, public SpeechBrain ECAPA and Silero VAD caches after audio analysis,
before starting text-model inference. Downloaded weights stay on disk. Jobs
with only transcription or speaker labeling retain those caches for reuse;
the next audio job after text enhancement reloads its models, adding some
loading time.

Each Ollama translation or summary operation keeps its selected model fixed.
After two returned inference responses, the app requires an explicit unload
acknowledgment before sending another request. This limits accumulation of
prompt state across a long operation, at the cost of reloading the model. If
that acknowledgment fails, the enhancement stops and the original transcript
remains available. Final cleanup is best effort, including after inference
failure; it cannot discard a completed result or replace the original error.
The app does not change global daemon settings or unload unrelated model tags.

Model residency is shared by all clients of an Ollama daemon. Unloading a model
can require another application using the same model to reload it. Set
`LINKSCRIBE_OLLAMA_RETAIN_MODELS=1` before starting LinkScribe to disable its
intermediate and final unload requests when that tradeoff is undesirable. The
[model-lifetime notes](docs/model-memory-lifecycle.md) explain the scope and
failure behavior. The [actual 34.635-second combined workflow](docs/full-workflow-2026-11-26/README.md)
completed in 59.202 seconds and peaked at 4584.3 MiB concurrent RSS / 4576.3 MiB
PSS across the app and Ollama. It passed a 6144 MiB process budget on a 9967.3 MiB
host; OS/browser headroom was outside that measurement. Translation and summary
quality failed in the same run. This is neither a whole-machine fit claim for
7.3 GiB nor evidence for long recordings or larger models.

The [v1.0 acceptance record](docs/V1-RELEASE-GATES.md) lists the workflows being
verified before a release. The version remains a draft candidate while those
gates are open.

### Experimental compact CPU translator

`LINKSCRIBE_TRANSLATION_BACKEND=marian` selects the dedicated local English↔Greek
candidate independently of Ollama. This is an evaluation option, not the default.
The initial paragraph-based implementation omitted text and degenerated on long
passages. Integrated sentence and quotation handling removed those catastrophic
coverage and repetition failures in the observed regression, but material
word-sense, measurement and actor errors remain. The
[retained comparison](docs/translation-models-2026-11-26/README.md) includes both
failed and corrected outputs; semantic quality is not approved. Keep and review
the original transcript.

Both public [English→Greek](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-el)
and [Greek→English](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-el-en) models
are from Helsinki-NLP's OPUS-MT project, under CC BY4.0. Setup downloads the pinned
original archive, verifies its SHA-256, converts the weights to int8 locally,
and retains the publisher's license and attribution. No transcript leaves the
computer. Each direction downloads about 879 MB once and needs about 2.2 GB of
temporary free space; the installed model occupies about 250 MB. The complete
setup path has been exercised for both directions.

```bash
./.venv/bin/python -m marian_translation --pair both
LINKSCRIBE_TRANSLATION_BACKEND=marian ./start_linux.sh
```

`LINKSCRIBE_TRANSLATION_THREADS` defaults to 4 (allowed range 1–32).
`LINKSCRIBE_TRANSLATION_CACHE` selects a different local cache folder.
`python -m marian_translation --pair en-el --repair` rebuilds a damaged cache from
the verified source without touching transcripts. Check setup inspects installed
dependencies and cached models without downloading or running inference.

## Optional speaker labels — public CPU backend

```bash
# from the repository root, after initial start_linux.sh created .venv
./.venv/bin/python -m pip install --no-cache-dir -r requirements-speakers-free.txt
```

Enable **Speaker labels** for a link or upload. Links then use audio recognition
instead of existing captions. The default `LINKSCRIBE_SPEAKER_BACKEND=speechbrain`
uses the public [SpeechBrain ECAPA model](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb),
pinned to revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`, plus bundled Silero
voice activity detection. No `HF_TOKEN` or model-conditions acceptance is needed.
Weights download on first use and are cached under
`~/.cache/linkscribe/speaker-ecapa`; `LINKSCRIBE_SPEAKER_CACHE` selects another
local directory. **Check setup** distinguishes installed dependencies from
present model files; it does not run inference or certify label accuracy.

The Linux CPU requirements explicitly select CPU-only Torch wheels. In the
isolated Linux test environment, dependencies occupied about 1.3 GiB and weights
plus their download cache about 170 MiB; allow additional installation/cache
space. A short real-voice validation run peaked at about 862 MiB for the speaker
process alone. Whisper, Ollama, longer audio and other running applications add
memory. The app cache retains at most one Whisper model for audio-only reuse;
switching model sizes can temporarily require both models to load. The
[text-enhancement cleanup policy](#model-lifetime-and-memory) releases the
public audio-model caches before translation or summary.

Speaker labels are estimates, not personal identification. The
[controlled real-voice evaluation](docs/speaker-evaluation-2026-11-26/README.md)
passed one-, two- and three-reader checks on fresh English audiobook voices,
including returning speakers. It does not establish Greek, noisy-meeting,
overlap, or exact-boundary accuracy. Short and ambiguous speech can remain
unassigned. Text is split only when actual ASR word strings/timestamps validate;
missing or inconsistent timing never leads to proportionally invented times.
Model/settings provenance and warnings are preserved in transcript JSON and
library backups; raw audio and voice embeddings are not stored.

For the existing **pyannote alternative**, install `requirements-speakers.txt`,
accept the [Community-1 model conditions](https://huggingface.co/pyannote/speaker-diarization-community-1),
set `HF_TOKEN` in the environment, and explicitly set
`LINKSCRIBE_SPEAKER_BACKEND=pyannote` before launch. Never commit the token.
There is no automatic fallback between backends. Gated Community-1 model
inference remains unverified in this project's current evidence.

ONNX Runtime telemetry is disabled before model-runtime initialization, with a
second API opt-out before VAD sessions. This does not remove the initial public
model download. If a managed machine needs its OS certificate store for permitted
media downloads, explicitly set `LINKSCRIBE_USE_SYSTEM_CERTS=1`; yt-dlp then uses
that trust store while certificate and hostname verification stay enabled.

## Batch jobs

Enter one supported video URL per line (1–20) in the **Batch links** tab. Jobs are processed sequentially to avoid overloading a small CPU machine. Each completed transcript is stored in the persistent library. If an individual video fails, subsequent links still run. At the end, download one ZIP for successful jobs; failures are listed in the browser.

In **v0.3**, a SQLite batch journal saves queued jobs and completion statuses. On server startup, interrupted link batches resume from their next unsaved item; completed transcripts are never retranscribed if their library record exists. Deleting a saved transcript records its removal atomically, so a restart cannot recreate it, even if the job had not yet acknowledged its save. Explicit per-video failures remain failures rather than retrying restricted sources forever. Recovery removes leftover media and partial downloads, and recovered completed jobs expire normally. Saved batch reports and ZIP exports can be downloaded again after restart. Use only **one** local server process with a given data directory. Individual uploads do not resume after interruption.

## Back up and restore your library (v0.3)

In the **Library** tab, choose **Download backup** to save a versioned ZIP containing all saved transcripts, timestamps, your edits, translation outputs, summaries and source highlights. Only text and metadata are included; audio, API secrets, and active batch work are not exported. Keep the backup in a safe place: it may contain sensitive transcript text.

New backups use format version 2 to preserve source highlights. This candidate
also imports older version 1 backups. Older app revisions cannot import version
2; use this revision or later to restore a new backup. Highlights are checked
against the exact source text, indices and timestamps before any record is inserted.

To restore, select the saved ZIP and choose **Restore backup**. LinkScribe checks its SHA-256 integrity hash and validates the records **before any insertion**, including translated segments, summaries, chapter times and finite numeric values. One invalid record rejects the whole import without partially adding transcripts. Existing IDs and edits are never overwritten; only missing transcripts are imported. ZIP entries are allowlisted and bounded to 50 MB compressed / 100 MB transcript data; generated backups obey the same limits. This protects against accidental or malformed imports, but is not a substitute for protecting your device and backups.

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
- `POST /api/link` — form fields: `url`, `mode` (`smart`, `audio`, `captions`), `language`, `model`, `consent=true`, `speakers`, `target_language` (`none`, `el`, `en`), `summary`, `highlights`
- `POST /api/upload` — media file, plus model/language/enhancement fields
- `POST /api/batch` — newline-separated `urls` (1–20), plus link options
- `GET /api/jobs/{id}` and `/api/jobs/{id}/download/{format}`
- `GET /api/batches`, `GET /api/batches/{id}` and `/api/batches/{id}/download` (persistent batch history and exports)
- `GET /api/diagnostics` (dependency and supported-JS-runtime checks, no access-token disclosures)
- `GET /api/library/backup` (versioned transcript ZIP) and `POST /api/library/restore` (non-destructive validated import)
- `POST /api/library/{id}/highlights` (select and save highlights from the current saved transcript)
- `GET /api/library?q=...` and `GET /api/library/{id}`
- `PUT /api/library/{id}` — title/segments edit (segment timestamps fixed)
- `DELETE /api/library/{id}`
- `GET /api/library/{id}/download/{format}` — full export, even after server restart

## Run tests

```bash
./.venv/bin/python -m pip install pytest httpx
./.venv/bin/python -m pytest -q
```

For the optional real annotation-alignment check without downloading the gated speaker model, also install `pyannote.core==6.1.0`. CI installs it as a test dependency; the base app does not require it.

Network-free tests exercise validation, queueing, journal recovery, backup integrity, imports, exports, CRUD and failure cases. The recovery suite kills a separate process immediately after a transcript's SQLite commit and starts a fresh process to verify recovery without duplicate transcription. Source media in that particular test is synthetic. GitHub Actions independently exercises the real file-upload → PyAV → Whisper Tiny → SQLite → export path on generated speech, checks recognizable source words, and verifies fresh Linux installation. A separate QA job runs the actual default `qwen3:4b` model for English↔Greek translation, summaries and subtitle/summary exports using owned text fixtures. Its structural success does not approve generated meaning.

Hosted Chromium runs passed 30 checks against the actual local app, including
real Whisper Tiny upload, desktop and 320/390px layouts, library editing,
downloads, backup/restore, validation, diagnostics and failure handling.
Screenshots were retained and visually inspected. Link and batch UI checks used
controlled caption fixtures; actual provider access is exercised by the
separate **LinkScribe live source QA** GitHub Actions workflow. That workflow
keeps successful and failed evidence and currently fails its complete provider
scope. See the [browser/provider record](docs/browser-provider-2026-11-26/README.md)
for exact commits, run links, screenshots and limitations.

Optional live probes can also be run explicitly:

```bash
PYTHONPATH=. ./.venv/bin/python tests/smoke_real_ollama.py
PYTHONPATH=. ./.venv/bin/python tests/smoke_live_providers.py --url https://www.youtube.com/watch?v=aqz-KE-bpKQ
```

The Ollama script requires the selected model to be installed and the local
daemon running. The lightweight `smoke_live_providers.py` probe checks metadata
and playable stream extraction by default; it is **not** a full transcription
test. The hosted workflow instead runs `tests/smoke_real_links.py` through the
actual app route, acquisition, recognition, persistence, exports, mixed batch
and fresh-process retrieval. Provider availability and restrictions can change;
the [verified scope](#verified-provider-scope) records the actual Dailymotion
functional pass, unresolved ASR defect, and YouTube/Vimeo access blockers.
Gated pyannote Community-1 inference remains unverified; the pyannote-core
alignment check does not imply that the gated model was run.

### Bilingual translation evaluation

The [original 26 November evaluation](docs/evaluation-2026-11-26/README.md) and
[later model and long-input comparisons](docs/translation-models-2026-11-26/README.md)
retain actual outputs and assistant reviews. Qwen, Gemma, TranslateGemma,
Hy-MT3 and Marian paths have completed structural checks while producing
material meaning errors. Later Marian input-processing fixes repaired observed
coverage failures without resolving its semantic errors. The general Ollama
prompt and `qwen3:4b` default remain unchanged; translation remains experimental.

The internally authored English/Greek corpus contains six development cases, four separate holdout cases, and two long passages that force production segment splitting. It covers terminology, names and roles, amounts, negation, conditions, uncertainty, quoted instructions, omissions, and continuity. References and review criteria are never sent to the model.

With the selected model already installed and Ollama running locally:

```bash
LINKSCRIBE_OLLAMA_THREADS=4 PYTHONPATH=. ./.venv/bin/python \
  tests/evaluate_translation_quality.py --output /tmp/linkscribe-translation-evaluation.json
```

Use `--split development` when adjusting a prompt, then evaluate the unchanged holdout and long passages. `--split` and `--case CASE_ID` can be repeated. Keep baseline and candidate reports separate and fix the candidate prompt before inspecting its holdout results.

Reports retain exact source and output text, reference wording, review criteria, actual model requests and returned JSON, source/corpus fingerprints, model digest, runtime version, and inference settings. They checkpoint atomically before and after each model request. `complete` describes the requested selection; `corpus_complete` requires every corpus case. An interrupted or failed setup remains explicitly incomplete.

Exit code zero means execution and structural checks passed. Lexical review flags do not certify errors or semantic quality: valid number formatting, transliteration and alternative wording can trigger them, while incorrect meaning can pass. Every automatic report therefore remains `semantic_quality: unreviewed`; compare full propositions and long-passage endings against the references. `--fail-on-review-flags` makes lexical misses fail the command when a stricter mechanical gate is useful.

The Independent LinkScribe QA workflow runs the full corpus against the actual local model and retains its JSON report alongside the integration output for 30 days, including available evidence from failed runs. These are reproducible internal fixtures, not an external language benchmark or a release approval.

## GitHub Pages

The `gh-pages` branch is a **separate UI demonstration**, not the Python backend. The real application and all its features run on your own computer/instance.

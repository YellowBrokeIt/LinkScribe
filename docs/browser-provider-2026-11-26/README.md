# Browser and live-provider evidence — 26 November 2026

**Browser: 30 checks passed on four published checkpoints. Live links: actual
Dailymotion acquisition, ASR, persistence, exports and completed-batch restart
work; the selected YouTube and Vimeo sources still fail. ASR quality: the
normal Tiny and Small transcripts omit later dialogue, and the measured VAD
step discards that audio before recognition.** Separate diagnostic outputs
support that finding without replacing the saved transcript.

These are assistant-operated checks on isolated test data. They do not establish
human approval, general recognition accuracy, universal provider access or
v1.0 readiness. No production correction is validated by this historical evidence.

## Runs and integrity

| Scope | Exact published commit | Run | Observed result |
| --- | --- | --- | --- |
| Browser after repairs | `a8c7b1bf0cc3fac30ab28cfbbb63083377df71ed` | [45878367338](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45878367338) | 30 passed |
| Browser after Windows QA import fix | `75cf261b1b6f7026628880874d364b249cb69414` | [45878887500](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45878887500) | 30 passed |
| Browser after decode observation | `01bfa720cd09f6541450fdf4f9e48136c923caea` | [45880209166](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45880209166) | 30 passed |
| Browser with diagnostic harness | `d1817885816bf06c4e16ab8826cf0dba59866280` | [45882031962](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45882031962) | 30 passed |
| Full provider scope, Tiny | `a8c7b1bf0cc3fac30ab28cfbbb63083377df71ed` | [45878367345](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45878367345) | Complete; all-provider scope failed |
| Full provider scope, Small | `01bfa720cd09f6541450fdf4f9e48136c923caea` | [45880209204](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45880209204) | Complete; same failed provider scope |
| Providers plus separate VAD diagnosis | `d1817885816bf06c4e16ab8826cf0dba59866280` | [45882031992](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45882031992) | Provider scope failed; diagnostic execution completed |

[manifest.json](manifest.json) records every retained file's SHA-256, its
original artifact member, archive digest, artifact ID and source verification.
Downloaded archives matched GitHub's digests. Every recorded source-file hash
in the hosted reports matched the corresponding Git commit's bytes. The
browser reports have identical hashes for the app, UI, library, backup, batch
and browser harness; this does not assert identity of unlisted dependencies.

Raw JSON reports and original PNGs are unchanged copies. Paths inside reports
refer to original artifact members; the manifest maps curated filenames to
those locations. The retained evidence survives the original artifacts' 30-day
retention. Start with the [latest browser report](browser-d1817885.json),
[Tiny provider report](providers-hosted-a8c7b1b.json),
[Small provider report](providers-small-01bfa720.json) and
[VAD-run provider report](providers-vad-d1817885.json).

## Browser: actual upload, controlled link fixtures

The browser exercised the actual app, origin guard, private SQLite database
and exports. The upload used owned FFmpeg/flite speech and **actual Whisper
Tiny**. Link/batch UI cases used explicitly controlled caption fixtures;
actual external acquisition is tested separately below.

The 30 checks cover desktop 1440px and mobile 390/320px layouts, source tabs,
consent, empty/malformed/corrupt inputs, polling and results, saved-edit refresh,
library search/pagination/exports, mixed batch UI/history, backup export/delete/
restore and invalid archives, diagnostics, origin rejection and JavaScript
errors. Inactive malformed URL input no longer blocks another source tab;
active native URL validation is restored when the link tab is selected.

An intentionally invalid summary-model setting checks enhancement failure:
the base transcript is retained and a visible warning explains the failure.
This browser test does not claim successful real translation or summarization.

The assistant visually inspected these **unaltered `a8c7b1b` screenshots**:

- [320px source form](screenshots/layout-320-link.png): header badge, tabs and
  controls fit without global overflow hiding.
- [320px real upload result](screenshots/upload-result-mobile-320.png): Copy,
  downloads, edit action, enhancement warning and AI-draft note remain readable.
- [320px editor](screenshots/library-edited-mobile-320.png): fields, pagination,
  Save and Delete fit; the draft note is visible.
- [Desktop result](screenshots/upload-result.png) and
  [controlled mixed batch](screenshots/batch-complete.png): successful actions,
  failed count and per-item errors are visible.

No new visual blocker was found in those screens. Coverage is Chromium, not
every browser or assistive technology. The corresponding 320px result from
`01bfa720` was also inspected and retained the repaired layout.

## Actual provider outcomes

All provider runs force audio mode and use real `/api/link`, yt-dlp and local
Whisper. Observers call the originals without substitute audio, captions or
text. TLS verification remains enabled; the hosted runner includes the
supported optional curl-cffi transport. Exact versions are retained in the
[event logs](provider-events.jsonl).

| Selected licensed source | Actual hosted outcome |
| --- | --- |
| [Blender Sintel trailer, YouTube](https://www.youtube.com/watch?v=HOfdboHvshg) | Acquisition fails: **“Sign in to confirm you’re not a bot.”** |
| [Tears of Steel teaser, YouTube](https://www.youtube.com/watch?v=WwHux5QZfC8) | Acquisition fails with the same bot sign-in requirement. |
| [Sintel trailer repost, Vimeo](https://vimeo.com/11721242) | Acquisition fails: **“The web client only works when logged-in.”** This is the extractor fallback, not proof that the rights holder made the source private. |
| [Tears of Steel repost, Dailymotion](https://www.dailymotion.com/video/xbvubxi) | Real acquisition, ASR execution, SQLite, exports and cleanup pass; content review finds major issues. |

The Dailymotion repost is titled `فيلم 🎬 Tears of Steel | معركة المستقبل بدأت`,
by MixTube. Across these runs its acquired bytes match SHA-256
`c8359f5278729091cab5b04d44b19eb4670553769ad2ca0e0097af2e91aef1b0`:
11,919,385 bytes with one audio stream and 734.191746 seconds of container duration.
The Small and diagnostic runs additionally measured 734.1453125 seconds of
actual decoded samples. Container duration alone did not prove full decoding
in the earlier Tiny run.

Successful records match actual SQLite and the API. The checks compare job and
library TXT/SRT/VTT/JSON bytes and ZIP members, preserve every saved segment in
export order, and verify media cleanup. They establish fidelity to the
recognized text, not accuracy of the recognition or subtitle synchronization.

Actual mixed batches contain one Dailymotion success and one YouTube failure.
After a fresh server process restart, successful records, individual export
bytes, completed batch history and ZIP members remain available. This is
completed-state persistence, not an interrupted-download recovery test.
Separate ZIPs are retained for [Tiny](mixed-batch-tiny.zip),
[Small](mixed-batch-small.zip) and [the VAD run](mixed-batch-vad-run.zip).

### Failure communication and local limitations

The app explains that audio could not be accessed, suggests checking source
restrictions and downloader/runtime versions, and offers a permitted local
upload. The batch view retains failed counts/errors and successful Open/export
actions. Both browser and real API checks confirm useful work survives a
failure. The user-facing message currently groups network, extractor and
access problems together; the QA evidence retains their distinct causes.

The [earlier local report](providers-local-working-tree.json) acquired none of
the four sources. Its YouTube CDN replies were HTTP 403 with `Server: envoy` and
an HTML `Site Unavailable` body, supporting a workspace/intermediary limitation.
Hosted requests instead reached YouTube's explicit bot response, and Dailymotion
worked. The local report's prepublication source hashes are preserved; its
changed enhancements-module hash is not relabeled as the hosted source. No
credentials, proxy rotation or disabled certificate checks were used.

## Content failure and VAD diagnosis

The [Tiny review](assistant-content-review.json) and
[Small review](assistant-small-review.json) compare raw output with published
subtitle text. Both receive **major content issues**: name/meaning errors,
missing later dialogue and very long spans for short utterances. There was no
human audio listening or formal WER/alignment score.

| Normal result | Segments | Last end | Largest segment span |
| --- | ---: | ---: | ---: |
| Tiny at `a8c7b1b` | 48 | 423.10s | At least 56.27s |
| Small at `01bfa720` | 53 | 423.24s | 68.90s |
| Small with VAD observation at `d1817885` | 43 | 423.46s | 56.72s |

The subtitle reference has later dialogue through 09:27; the provider page also
has later transcript entries. Wording/counts vary between Small runs, so these
are not claimed to be bit-reproducible model outputs. Their repeated stopping
point is the stable finding. Raw normal records and TXT/SRT exports remain
separate for [Tiny](dailymotion-tiny-record.json),
[Small](dailymotion-small-record.json) and
[the diagnostic run](dailymotion-vad-run-record.json).

The final run observes **25 actual VAD intervals totaling 1,899,520 samples /
118.72 seconds, with the last interval ending 423.184 seconds**. Its default
threshold is 0.5, minimum silence 2 seconds and padding 400ms. The collected audio
has exactly the same sample total. Therefore no later audio reaches normal
recognition despite the full 734.1453125 seconds being decoded.

After normal saving and cleanup, the same cached Small model processed copied
windows 424–434s, 502–522s and 553–571s: 48 seconds total, explicit English, VAD off,
no reference prompt. All requests completed and recovered recognizable later
dialogue: the time warning, world-change/Celia line and closing exchange.
They remain imperfect and do not recover every reference utterance.

The [separate diagnostic](tail-vad-off-d1817885.json) retains exact boundaries,
PCM hashes, kwargs, returned metadata and raw segments. The normal saved-record
fingerprint is identical before/after; no audio file is in the artifact. The
[assistant interpretation](assistant-vad-diagnosis.json) records strong evidence
of VAD selection loss. Cropping and explicit language also differ, so this is
post-hoc diagnosis, not an isolated parameter-quality benchmark or proof that
VAD off solves every recognition problem. The normal result still lacks the
tail; no diagnostic text is substituted into it.

## Platform and independent QA

Windows collection at `a8c7b1b` failed on indirect Linux-only `resource`
imports. `75cf261b` moves the two affected smoke-only imports into executable
entry points, without skipping tests or changing production behavior.
Actual platform logs show 444 passed per OS at `75cf261b`, 447 at `01bfa720` and
452 at `d1817885`; Python 3.11/3.13 independent jobs at the final checkpoint also
show 452 passed each. See [ci-verification.json](ci-verification.json) for exact
job IDs and observed log lines. Browser, fresh Linux installation and real
file-upload speech jobs pass.

**Independent QA at `d1817885` fails** because the real Qwen long EN→EL request
times out after 240.102 seconds, with no response JSON. Original source is
retained and no partial translation is accepted. All 12 cases were attempted:
5 automatic pass, 6 review, 1 execution error. Nearby earlier runs completed
without that error; a single green run does not establish reliable latency.
These automatic flags do not approve language semantics. See the
[exact failed job](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45882032001/job/140123751334).

## Attribution and reference limits

Sintel: © Blender Foundation, [www.sintel.org](https://durian.blender.org/),
[CC BY 3.0 sharing terms](https://durian.blender.org/sharing/).
Tears of Steel: (CC) Blender Foundation,
[mango.blender.org](https://mango.blender.org/),
[project/CC BY 3.0 terms](https://mango.blender.org/about/).
Repost pages identify the original film/license; their uploader is not named
as the original producer. Retained machine transcripts are imperfect derivatives.

The [official subtitle index](https://download.blender.org/demo/movies/ToS/subtitles/)
lists English subtitles, but those bytes were unavailable here. Review used
[Commons revision 188560225](https://commons.wikimedia.org/w/index.php?title=TimedText:Tears_of_Steel_in_4k_-_Official_Blender_Foundation_release.webm.en.srt&oldid=188560225).
No byte identity with the official SRT or independently verified exact-audio
reference for the repost is claimed.

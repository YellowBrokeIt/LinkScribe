# Working toward a usable v1.0

The project goal is a working local transcript application. A version number is
not a substitute for verified workflows. The user authorized continued building,
investigation and fixes on 26 November 2026, including assistant-run testing.
Testing on the user's Linux machines is not required for this work.

Development continues on `feature/linkscribe-v03-reliability` and draft PR #2.
The stable branch remains unchanged while the release gates below are open.

## Acceptance gates

| Area | Required evidence | Current position |
| --- | --- | --- |
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | Fresh Linux installation and launcher passed at `2760679`; Windows, macOS, Ubuntu and Python 3.11/3.13 each passed 550 tests. The retained ASR/model-lifetime implementation and stronger evidence observers pass 607 tests locally after rejecting the stricter summary experiment for actual meaning errors. Hosted verification of this next checkpoint remains pending. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Native development and fresh Auto/Turbo recordings passed integrated checks with retained word errors. Small VAD-off development remains two acceptable, three minor, three major; default Auto/Small also passed two Greek app workflows without changing those hypotheses. A seven-input paired comparison now rejects the identical noise hallucination while preserving all four ordinary/20 dB quieter English/Greek transcripts and timings. Quiet English genuinely exercised the second speech detector. This is narrow regression evidence, not an accuracy guarantee. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | No new default is approved. The 1000-byte source-JSON bound completed all 12 hosted cases through `2760679`, with five automatic passes/seven review flags and no execution errors. Meaning remains unapproved. Whole-result identity detection prevents copied English from being advertised as Greek. A final generic name-preservation experiment on native Hy-MT3 7B completed six development cases but retained three material errors, so it was rejected. Fresh v3 validation remains unused. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | The eight-point prompt/schema/local contract now passes two actual final/direct checks, with five earlier English map/reduction responses explicitly replayed. English long output was acceptable, but the direct consent output contained a malformed amount. The previous fully live Greek long run failed with HTTP500/runner EOF during prompt-cache saving after repeated weak reductions. The next actual run still misstated the consent amount and changed planned returns/feedback to completed actions. Its strict 700/399-character note experiment is rejected: Greek notes also end midword despite valid JSON/stop. The unchanged run continues to preserve full Greek/runtime evidence, while the main source retains only the model-lifetime fix. A separate source-excerpt selection design is being evaluated; fresh validation is unused. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Hosted Dailymotion full-audio processing retains later dialogue and passes storage/export/recovery checks. Exact-zero PCM rejection is verified at `2760679`; that run still saved text from white noise. The new whole-recording corroboration guard passed the paired seven-input actual regression; unseeded hosted noise/full-film follow-up is pending. YouTube still requires bot sign-in, a separate caption probe returned IpBlocked, and Vimeo hit an extractor login fallback. Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions pass. Hosted browser editing, refreshed result previews, exports, backup/restore and validation passed after the fixes. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Hosted Chromium passed 30 checks at `2760679`, with actual speech recognition, no JavaScript page errors and inspected desktop/320/390-pixel screenshots. The draft-summary control and source-check hint fit at 320 pixels. Link/batch UI fixtures were controlled, separate from actual provider evidence. The successful-summary heading was not exercised by the generated-speech screenshot. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Actual 34.635-second Small/public-speaker/default-Qwen workflow at `a3b8652` completed in 59.202 seconds, peaking at 4584.3 MiB concurrent RSS / 4576.3 MiB PSS. It passed a 6144 MiB process budget on a 9967.3 MiB host, with OS/browser headroom excluded; generated-text quality failed. The new long-summary run measures the two-response unload policy and available OOM counters. Earlier cache-save EOF is not a proven OOM kill; whole-machine 7.3 GiB fit and long-recording resource approval remain open. |

## Evidence rules

- A successful HTTP request or a nonempty model answer does not establish correct
  transcription, translation, summary, or speaker identity.
- Save actual outputs, configuration, model identities and source fingerprints.
  Keep structural checks separate from semantic review.
- Freeze validation inputs before candidate selection or output inspection. Once
  a case informs a fix, later runs are regression verification; use fresh cases
  for the next independent validation claim.
- Do not skip a failing provider or optional feature and report it as passed.
  Fix the cause, or document the verified scope and unresolved external blocker.
- Model access restrictions must be respected. Public, permissively licensed
  alternatives are acceptable; bypassing a gated model is not.
- Do not label the release v1.0 until the supported user workflows pass.

## Starting evidence

- [Published evaluation and limitations](evaluation-2026-11-26/README.md)
- [Real native speech evidence](asr-2026-11-26/README.md)
- [Public speaker model and integrated app evidence](speaker-evaluation-2026-11-26/README.md)
- [Actual browser, provider and VAD diagnosis](browser-provider-2026-11-26/README.md)
- [Full-recording VAD-off follow-up and exact-silence failure](asr-vad-off-2026-11-26/README.md)
- [Hosted exact-zero correction and nonzero-noise failure](asr-zero-noise-2026-11-26/README.md)
- [Paired no-speech guard and quiet-speech evidence](asr-speech-evidence-2026-11-26/README.md)
- [Default Auto/Small Greek path](asr-default-auto-2026-11-26/README.md)
- [Actual public-caption access attempt](public-captions-2026-11-26/README.md)
- [Local translation comparisons and retained failures](translation-models-2026-11-26/README.md)
- [Summary regressions and frozen validation](summary-2026-11-26/README.md)
- [Model lifetime and memory measurement scope](model-memory-lifecycle.md)
- [Complete actual workflow: resources, outputs and quality failures](full-workflow-2026-11-26/README.md)
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

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
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | Fresh Linux installation and launcher passed at `d181788`; Windows, macOS and Ubuntu each passed 452 tests at that checkpoint. The next integrated source passes 517 local tests; its hosted checks remain pending. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Eight native Small/Turbo development clips and eight fresh Auto/Turbo clips passed the integrated checks. Fresh review: five acceptable, two minor, one damaged uncertainty qualifier. Transcripts remain editable drafts; Small remains the default and Turbo is selectable. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | Bounded comparisons of Qwen, Gemma, TranslateGemma, Hy-MT3 and Marian found material errors. Marian sentence processing repaired observed omissions/repetition without approving meaning. A measured default-Qwen timeout prompted a smaller 1000-byte source-JSON budget; actual verification is pending. No new default is approved; fresh v3 validation remains unused. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | Actual baseline and corrected Qwen outputs are preserved. Direct summaries repaired a wrong operator and amount; long requests now use UTF-8 bounds. The first corrected run exposed overly strict intermediate-note limits and residual permission errors. The next candidate aligns note limits with the unchanged 3200-byte input bound and clarifies generic grounding; actual regression and fresh validation are pending. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Hosted Dailymotion completed actual acquisition, recognition, storage, exports and cleanup, but its VAD discarded all speech after about 7:03 in a fully decoded 12:14 film. Separate VAD-off excerpts recovered later dialogue. Default ASR now preserves the full audio; full-file and no-speech validation are pending. Hosted YouTube requires bot sign-in and Vimeo hits an extractor login fallback. Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions pass. Hosted browser editing, refreshed result previews, exports, backup/restore and validation passed after the fixes. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Hosted Chromium passed 30 checks at four checkpoints, including desktop and 320/390-pixel layouts; screenshots were inspected. Link/batch UI fixtures were controlled, separate from actual provider evidence. Latest source rerun is pending. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Actual Small + public speakers + app peaked at 1,279.6 MiB in the earlier measured process. Audio-cache release before text inference and bounded phase-end Ollama unload are implemented. Actual concurrent app-plus-Ollama RSS/PSS measurement is pending against a 6144 MiB process budget on a 9.73 GiB host; this is not a full 7.3 GiB-machine fit claim. |

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
- [Local translation comparisons and retained failures](translation-models-2026-11-26/README.md)
- [Summary regressions and frozen validation](summary-2026-11-26/README.md)
- [Model lifetime and memory measurement scope](model-memory-lifecycle.md)
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

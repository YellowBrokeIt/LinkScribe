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
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | Fresh Linux installation and launcher passed at `a3b8652`; Windows, macOS and Ubuntu each passed 517 tests there. The subsequent unchanged-translation handling passes 528 local tests; its hosted checks remain pending. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Eight native Small/Turbo development clips and eight fresh Auto/Turbo clips passed the integrated checks. Fresh review: five acceptable, two minor, one damaged uncertainty qualifier. Transcripts remain editable drafts; Small remains the default and Turbo is selectable. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | Bounded comparisons found material errors; no new default is approved. Marian sentence processing repaired observed omissions/repetition without approving meaning. A measured default-Qwen timeout prompted a 1000-byte source-JSON bound; the long hosted run remains pending. The actual combined job then exposed all 21 English strings copied as Greek. Whole-result identity now produces a warning and preserves the original without a false translation artifact. This does not solve semantic errors; fresh v3 validation remains unused. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | Actual baseline and corrected Qwen outputs are preserved. Direct summaries repaired a wrong operator and amount; long requests now use UTF-8 bounds. The first corrected run exposed overly strict intermediate-note limits and residual permission errors. The next candidate aligns note limits with the unchanged 3200-byte input bound and clarifies generic grounding; actual regression and fresh validation are pending. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Hosted Dailymotion completed actual acquisition, recognition, storage, exports and cleanup, but its VAD discarded all speech after about 7:03 in a fully decoded 12:14 film. Separate VAD-off excerpts recovered later dialogue. Default ASR now preserves the full audio; full-file and no-speech validation are pending. Hosted YouTube requires bot sign-in and Vimeo hits an extractor login fallback. Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions pass. Hosted browser editing, refreshed result previews, exports, backup/restore and validation passed after the fixes. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Hosted Chromium passed 30 checks at `a3b8652` and four earlier checkpoints, including desktop and 320/390-pixel layouts; screenshots were inspected. Link/batch UI fixtures were controlled, separate from actual provider evidence. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Actual 34.635-second Small/public-speaker/default-Qwen workflow at `a3b8652` completed in 59.202 seconds. App plus Ollama peaked at 4584.3 MiB concurrent RSS / 4576.3 MiB PSS; complete measurement passed a 6144 MiB process budget on a 9967.3 MiB host. This excludes whole-machine headroom and long-recording claims. Generated-text quality failed in the same run. |

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
- [Complete actual workflow: resources, outputs and quality failures](full-workflow-2026-11-26/README.md)
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

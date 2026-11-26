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
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | Linux installation passed at `d841d04`; final-code and other-platform checks remain. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Eight native Small/Turbo development clips and eight fresh Auto/Turbo clips passed the integrated checks. Fresh review: five acceptable, two minor, one damaged uncertainty qualifier. Transcripts remain editable drafts; Small remains the default and Turbo is selectable. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | Independent model routing is implemented. Initial Marian fresh validation found serious paragraph omissions/repetition; sentence/quotation processing is being corrected. TranslateGemma comparison continues. No new default is approved. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | Existing Qwen integration passed; final settings and longer factual examples need verification. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Actual local acquisition failed: the workspace gateway blocked YouTube media hosts, Vimeo hit a known upstream extractor issue, and Dailymotion exposed no playable formats. A separate hosted full-pipeline check is prepared; no provider pass is claimed from metadata alone. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests pass; a real mixed-source batch remains. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions pass. Real browser upload/exports passed; stale result-preview and hidden-input validation defects are fixed and await the next hosted run. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Actual Chromium found mobile overflow and form/result defects; fixes and expanded 320/390-pixel checks await hosted validation. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Actual Small + public speakers + app peaked at 1,279.6 MiB in the measured process. Turbo alone used about 1.65 GiB. The combined workflow including Ollama still needs process-tree measurement. |

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
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

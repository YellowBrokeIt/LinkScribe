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
| English and Greek ASR | Real licensed speech through upload, default Small model, reviewed words/names/numbers, ordered timestamps, persistence and exports | English generated-speech/Tiny integration passed; real Greek/default-model verification is in progress. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | Independent model routing is implemented. Dedicated model development runs still show material errors; no new default is approved. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | Existing Qwen integration passed; final settings and longer factual examples need verification. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | A public-model CPU implementation is being evaluated. Gated pyannote inference has not been verified. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Prior metadata/download probes are not full transcription evidence; provider checks remain. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests pass; a real mixed-source batch remains. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API coverage passes; actual browser journey remains. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Automated real-backend browser QA is being prepared. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Model file sizes are known; complete-workflow peak memory remains. |

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
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

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
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | Fresh Linux installation and launcher passed at `e2895f5`; Windows, macOS and Ubuntu each passed 528 tests there. The next combined ASR/output-contract candidate passes 550 local tests; its hosted checks remain pending. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Native development and fresh Auto/Turbo recordings passed integrated checks with retained word errors. The additional eight-clip default-Small VAD-off replay passed in 18.583 seconds; review remained two acceptable, three minor, three major, including a worsened Greek collision-word error. That replay used explicit source languages; a two-case Greek Auto/Small default-path check is prepared. Small remains the default and Turbo is selectable. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | Bounded comparisons found material errors; no new default is approved. The 1000-byte source-JSON bound completed all 12 hosted cases at both `a3b8652` and `e2895f5`, with five automatic passes/seven review flags and no execution errors. Meaning remains unapproved. The actual combined job exposed all 21 English strings copied as Greek; identity handling now warns and preserves the original without a false translated artifact. Fresh v3 validation remains unused. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | Direct summaries repaired observed operator/amount errors; byte-bounded maps and aligned note limits retain source coverage. The latest isolated regression improved the short permission case, but English long synthesis returned 36 key points and was rejected by the old unstated 30-point guard. The next candidate aligns an explicit eight-point prompt/schema/local guard. Current long-Greek evaluation and subsequent contract verification remain pending; fresh validation is unused. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | Hosted Dailymotion's ordinary VAD-off path now recovers previously omitted later dialogue and passes persistence/export/recovery checks. Exact 32-second zero PCM nevertheless produced two saved words; the current candidate rejects exact-zero audio and checks decoded duration before model inference, with actual follow-up pending. One white-noise case passed. Hosted YouTube requires bot sign-in, a local caption probe returns IpBlocked, and Vimeo hits an extractor login fallback. Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | Deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions pass. Hosted browser editing, refreshed result previews, exports, backup/restore and validation passed after the fixes. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | Hosted Chromium passed 30 checks through `e2895f5`, including desktop and 320/390-pixel layouts; screenshots were inspected. Link/batch UI fixtures were controlled, separate from actual provider evidence. The next candidate also labels the summary control and result as drafts. |
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
- [Full-recording VAD-off follow-up and exact-silence failure](asr-vad-off-2026-11-26/README.md)
- [Actual public-caption access attempt](public-captions-2026-11-26/README.md)
- [Local translation comparisons and retained failures](translation-models-2026-11-26/README.md)
- [Summary regressions and frozen validation](summary-2026-11-26/README.md)
- [Model lifetime and memory measurement scope](model-memory-lifecycle.md)
- [Complete actual workflow: resources, outputs and quality failures](full-workflow-2026-11-26/README.md)
- [Draft PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2)
- [Verified starting commit](https://github.com/YellowBrokeIt/LinkScribe/commit/d841d044dd00e58ab2ced4cd8ec26cae40f42ea8)

This file records work in progress. It is not a release approval.

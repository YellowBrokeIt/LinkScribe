# Working toward a usable v1.0

The project goal is a working local transcript application. A version number is
not a substitute for verified workflows. The user authorized continued building,
investigation and fixes on 26 November 2026, including assistant-run testing.
Testing on the user's Linux machines is not required for this work.

Development continues on `feature/linkscribe-v03-reliability` and draft PR #2.
The stable branch remains unchanged while the release gates below are open.
The application version remains **0.3.0**.

The [28 November checkpoint recovery](checkpoint-recovery-2026-11-28/README.md)
reconciles the completed hosted results for published commit
`dc0985dabaacdbeedd1d55daf0351ea6bda69d84`. At that status check there were no
queued or running repository workflows. These results apply to that commit;
they do not verify subsequent changes. Later conversational reports about
source highlights and a roughly 4.2 GiB combined workflow have not been
recovered as published source or evidence here and are not release-gate passes.

## Acceptance gates

| Area | Required evidence | Current position |
| --- | --- | --- |
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | At `dc0985d`, Windows, macOS, Ubuntu and independent Python 3.11/3.13 configurations each passed 607 tests. Fresh Linux checkout, actual launcher, health, homepage and library endpoint passed. During the 28 November recovery, the actual downloaded source archive also passed fresh Linux installation on Python 3.12.14, packaged launcher, health, diagnostics, homepage, empty library and dependency consistency. A new candidate-workflow job repeats this check on each generated archive. These results do not verify later revisions. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Native development and fresh Auto/Turbo recordings passed integrated checks with retained word errors. Small VAD-off development remains two acceptable, three minor, three major; default Auto/Small also passed two Greek app workflows without changing those hypotheses. A seven-input paired comparison now rejects the identical noise hallucination while preserving all four ordinary/20 dB quieter English/Greek transcripts and timings. Quiet English genuinely exercised the second speech detector. This is narrow regression evidence, not an accuracy guarantee. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | No new default is approved. At `dc0985d`, the actual default model completed all 12 hosted corpus cases with five automatic passes/seven review flags, no execution errors, and semantic quality explicitly unreviewed. Whole-result identity detection prevents copied English from being advertised as Greek. A final generic name-preservation experiment on native Hy-MT3 7B completed six development cases but retained three material errors, so it was rejected. Fresh v3 validation remains unused in the published evidence. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | The eight-point prompt/schema/local contract passes two actual final/direct checks, with five earlier English map/reduction responses explicitly replayed. English long output was acceptable, but the direct consent output contained a malformed amount. A fully live Greek long run failed with HTTP500/runner EOF during prompt-cache saving after repeated weak reductions. The next actual run still misstated the consent amount and changed planned returns/feedback to completed actions. Its strict 700/399-character note experiment was rejected: Greek notes also end midword despite valid JSON/stop. Published source retains the model-lifetime fix. The hosted text run at `dc0985d` completed but does not approve meaning. Later source-highlights and frozen-validation claims remain unrecovered and unverified here. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | At `dc0985d`, unseeded hosted processing of the complete 734.15-second Dailymotion film passed storage/export/recovery checks; silence and actual white noise were correctly rejected. The paired seven-input guard comparison remains narrow regression evidence. Both latest YouTube attempts returned “This content isn’t available.” Earlier bot sign-in and separate caption `IpBlocked` results remain historical evidence, not a diagnosis of these latest errors. Vimeo returned “The web client only works when logged-in.” Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | At `dc0985d`, deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | API/migration/backup regressions and hosted browser editing, refreshed result previews, exports, backup/restore and validation passed at `dc0985d`. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | At `dc0985d`, hosted Chromium passed 30 checks with actual speech recognition and no JavaScript page errors, including 1440/390/320-pixel layout checks. The artifact retains screenshots; this recovery verified the logged checks without claiming a new visual review. Link/batch UI fixtures were controlled, separate from actual provider evidence. These checks do not exercise the later unpublished source-highlights design. |
| Resource use | Measured CPU/memory for the default speech model plus optional enhancements on a modest machine | Actual 34.635-second Small/public-speaker/default-Qwen workflow at `a3b8652` completed in 59.202 seconds, peaking at 4584.3 MiB concurrent RSS / 4576.3 MiB PSS. It passed a 6144 MiB process budget on a 9967.3 MiB host, with OS/browser headroom excluded; generated-text quality failed. The published long-summary recorder measures the two-response unload policy and available OOM counters; a later reported approximately 4.2 GiB highlights workflow has not been recovered and verified here. Earlier cache-save EOF is not a proven OOM kill; whole-machine 7.3 GiB fit and long-recording resource approval remain open. |

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

- [Recovered exact-commit hosted status and remaining work](checkpoint-recovery-2026-11-28/README.md)
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

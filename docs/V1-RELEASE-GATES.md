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
they do not verify subsequent changes. Recovery commit `002d8fc` subsequently
passed 613 tests in all five hosted configurations, 30 browser checks, actual
speech and Ollama integrations, and installation from its actual candidate ZIP.
These structural results do not approve generated meaning.

Source highlights have now been rebuilt with independently frozen English/Greek
text cases and integrated through persistence, edits, exports, validated backups
and batch recovery. The integrated local suite passed 652 tests and 32 subtests.
The [new source-highlights record](source-highlights-2026-11-28/README.md) and
[Vimeo provider correction](provider-followup-2026-11-28/README.md) identify exact
tested files and limitations. Their subsequent hosted results are recorded below;
earlier unrecovered conversational resource claims still are not evidence.

At the next published checkpoint `f12afd8`, all five hosted configurations
passed 652 tests and 32 subtests; fresh installation from checkout and candidate
ZIP, actual upload and real-Ollama execution also completed. Chromium passed
31/32 checks and exposed a test-selector race before saved-highlight generation.
Independent editor review then found stale input handlers after generation and
edits lost during pending saves/opens. Those fixes and explicit browser cases
are being verified in the follow-up candidate. The
[integrated checkpoint record](integration-2026-11-28/README.md) preserves the
failed check and actual per-provider results.

The follow-up also declares the public-video transport that provider QA had
installed separately, and evaluates aligned speech decoding against the exact
Dailymotion late-dialogue regression. Local Vimeo and short quiet-speech results
are not substitutes for that hosted regression. The
[summary experiments](summary-followup-2026-11-28/README.md) and
[translation experiment](translation-followup-2026-11-28/README.md) retain newly
observed meaning/coverage errors and output-limit failures; no language candidate
was promoted and unused frozen validation sets remain unopened.

The corrected `929cf2d` browser run passed all **34 checks**, including actual
pending-open persistence, and all five hosted suites passed **678 tests and
32 subtests**. Fresh checkout, actual candidate ZIP and actual Tiny upload passed;
the default Ollama run completed twelve cases with five automatic passes and
seven review flags. These execution results do not approve generated meaning.

Broader independent review subsequently rejected both universal word-alignment
speech candidates: the two-second heuristic omitted real commands, and disabling
only that heuristic restored them but introduced other word/name errors and
punctuation-only output. Production restores the exact prior application file.
The [official-film and ablation record](asr-official-tail-2026-11-28/README.md)
retains all scoped successes and failures. The separate restored-policy tail
checker preserves the original windows and never approves the rejected candidate.
The next package also declares the previously missing SOCKS dependency. Local
combined verification passed **685 tests and 32 subtests**; the next exact source
checkpoint still requires its hosted results.

The [Qwen Instruct refresh](model-refresh-2026-11-28/README.md) completed all six
exposed development translations within its process budget, but independent
review found three major English-to-Greek errors. It is rejected as a translation
replacement; no summary or heldout validation followed that failure.

## Acceptance gates

| Area | Required evidence | Current position |
| --- | --- | --- |
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | At `929cf2d`, Windows, macOS, Ubuntu and independent Python 3.11/3.13 configurations each passed 678 tests and 32 subtests. Fresh Linux checkout and the actual generated candidate ZIP passed installation, launcher and endpoint checks. Ordinary requirements installed the public-video transport. The next package declares SOCKS support for an observed model-download failure and needs its own hosted verification. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Native development and fresh Auto/Turbo recordings passed integrated checks with retained word errors. Small VAD-off development remains two acceptable, three minor, three major; default Auto/Small also passed two Greek app workflows without changing those hypotheses. A seven-input paired comparison now rejects the identical noise hallucination while preserving all four ordinary/20 dB quieter English/Greek transcripts and timings. Quiet English genuinely exercised the second speech detector. This is narrow regression evidence, not an accuracy guarantee. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | No new default is approved. At `dc0985d`, the actual default model completed all 12 hosted corpus cases with five automatic passes/seven review flags, no execution errors, and semantic quality explicitly unreviewed. Whole-result identity detection prevents copied English from being advertised as Greek. A final generic name-preservation experiment on native Hy-MT3 7B completed six development cases but retained three material errors, so it was rejected. Fresh v3 validation remains unused in the published evidence. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | The eight-point prompt/schema/local contract passes two actual final/direct checks, with five earlier English map/reduction responses explicitly replayed. English long output was acceptable, but the direct consent output contained a malformed amount. A fully live Greek long run failed with HTTP500/runner EOF during prompt-cache saving after repeated weak reductions. The next actual run still misstated the consent amount and changed planned returns/feedback to completed actions. Its strict 700/399-character note experiment was rejected: Greek notes also end midword despite valid JSON/stop. Published source retains the model-lifetime fix. Hosted text runs completed but do not approve meaning. This gate remains separate from source highlights. |
| Source highlights | Verbatim text/time fidelity, useful selection on frozen English/Greek sources, complete storage/edit/export/backup path | Rebuilt selector passed six development cases (25/25 declared coverage goals) and four previously unseen frozen cases (18/18 goals), preserving original words/times with no declared context omissions. Both failed development iterations remain retained. At `929cf2d`, actual-upload and saved-highlight generation, source navigation, edits/regeneration and nonnull-highlight backup/restore passed Chromium. Short sources are explicitly uncondensed. These internal fixtures do not establish arbitrary-recording coverage, ASR accuracy or speaker attribution. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | At `dc0985d`, unseeded hosted processing of the complete 734.15-second Dailymotion film passed storage/export/recovery checks; silence and actual white noise were correctly rejected. Original YouTube/Vimeo access failures remain retained. A separate official YouTube full-film follow-up obtained metadata but media download failed HTTP403 locally. Preserving an explicitly supplied public Vimeo player route fixed an application rewrite bug; an 888.07-second permitted recording passed download/full Small ASR/SQLite/exports/cleanup/restart on frozen `002d8fc` plus that parser correction. Suspicious repeated phrases and low language confidence leave semantic accuracy open. Overall provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | At `dc0985d`, deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | Hosted integration covers source-hash validation, atomic rejection of fabricated excerpts, stale-data invalidation, damaged optional highlights, version2 backups and legacy version1 imports. At `929cf2d`, actual Chromium verified corrections after generation, preservation during saves/opens, saving to the original record while leaving another record unchanged, and backup/restore with actual nonnull highlights. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | At `929cf2d`, hosted Chromium passed 34/34 checks with actual speech recognition and no JavaScript page errors, including 1440/390/320-pixel layouts. Representative screenshots were independently reviewed. Prior 31/32 and 33/34 failures remain retained and their corrections were rerun. Link/batch UI fixtures remain controlled and separate from actual provider evidence. |
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
- [Rebuilt source-highlights development, first frozen validation and limitations](source-highlights-2026-11-28/README.md)
- [Vimeo player correction, actual full pipeline and precise remaining provider failures](provider-followup-2026-11-28/README.md)
- [Hosted integrated checkpoint, actual browser failure and editor race fixes](integration-2026-11-28/README.md)
- [Aligned-ASR comparison and explicit remaining tail verification](asr-vimeo-followup-2026-11-28/README.md)
- [Official-film comparisons and rejected alignment policies](asr-official-tail-2026-11-28/README.md)
- [Source-cited summaries, source-first repair and projection failures](summary-followup-2026-11-28/README.md)
- [Repeated baseline translation errors and rejected reasoning profile](translation-followup-2026-11-28/README.md)
- [Rejected Qwen Instruct translation refresh](model-refresh-2026-11-28/README.md)
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

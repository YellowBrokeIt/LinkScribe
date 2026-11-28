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

The restored-policy checkpoint `745554b` has now completed hosted verification:
all five platform/Python suites passed **685 tests and 32 subtests**, Chromium
passed **34/34**, and fresh checkout, actual candidate ZIP installation and actual
Tiny upload passed. The ZIP installed `socksio` through its base requirements.
Default Ollama completed all twelve cases with five automatic passes and seven
review flags; generated meaning remains unapproved. All six live provider
attempts failed during acquisition, leaving the restored speech-tail check
unexercised. Silence and actual white-noise rejection passed. The
[exact hosted record](integration-2026-11-28/hosted-745554b/checkpoint.json)
retains the underlying reports and artifact identities.

The separate [M2M100 screen](m2m100-followup-2026-11-28/README.md) also failed
translation acceptance. Native CPU execution completed within its resource
budget, but output changed transcription to translation and collapsed distinct
people while omitting a role. It was not integrated or sent to fresh validation.

The [Parakeet screen](parakeet-screen-2026-11-28/README.md) completed the eight
exposed speech cases within its CPU/memory bounds, but four had major meaning
errors. A separately frozen preprocessing comparison and single legacy-frontend
ablation preserved the same major-error count, although one Greek omission was
recovered. Neither recognition profile was adopted.

The [Gemma 4 six-case screen](gemma4-screen-2026-11-28/README.md) initially had
five acceptable translations and one minor issue. Its subsequent
[twelve-case exposed regression](gemma4-exposed-v2-2026-11-28/README.md) had
**seven major, three minor and two acceptable** outputs;
all four long cases had major errors. Standalone execution used 5870.6 MiB peak
sampled RSS and completed normally, which does not offset the meaning failures
or establish whole-application resource fit. Fresh v3 validation remains unused.

The new [translation-script guard](translation-script-guard-2026-11-28/README.md)
rejects newly introduced non-Latin/non-Greek words unless an exact normalized
letter run already occurs in the source. Replaying the twelve retained outputs
rejects three corrupted translations without any new model request or alteration
to the originals. This guard cannot identify the other meaning errors and does
not approve the candidate. Independent review also caught and fixed false
rejections of name apostrophes and mathematical notation. The combined local
suite, including the new hosted-speech harness controls, passed **717 tests and
54 subtests**. The subsequent exact-checkpoint hosted results are recorded below.

A [single native-thinking ablation](gemma4-thinking-ablation-2026-11-28/README.md)
also failed the original telescope loan/material criteria, despite a complete
normal response within the unchanged limits. No additional cases or production
switch followed that failure. The
[Qwen native speech preparation](qwen3-asr-screen-2026-11-28/README.md) froze eight
unchanged full recordings, pinned CPU runtime, raw token/EOS evidence and a
sampled process-group limit before the actual run described below.

The `a4ca88e` checkpoint completed all ordinary hosted application workflows:
Ubuntu and independent Python 3.11/3.13 passed **717 tests and 54 subtests**;
Windows and macOS passed **715 tests and 54 subtests**, skipping only two
Linux-specific owned-process-group harness controls. Chromium passed **34/34**
with no JavaScript page errors, fresh checkout and actual generated ZIP
installation passed, and the actual Tiny upload completed its pipeline. Default
Ollama completed all twelve cases with five automatic passes and seven review
flags; generated meaning remains unapproved. The [exact record and original
reports](integration-2026-11-28/hosted-a4ca88e/checkpoint.json) retain source and
artifact identities. No fresh provider attempt was made at this checkpoint.

The initial Qwen workflow failed expression validation before any job or model
attempt. A [separate path-setup correction](qwen3-asr-hosted-env-followup-2026-11-28/README.md)
left the original helper, inputs, model and decoder unchanged. Its isolated
`7ee0c7f2` hosted run then completed all eight clips, with 4545.9 MiB sampled
process-group RSS and 5025.7 MiB worker high-water RSS under the 6144 MiB cap.
Independent [meaning review](qwen3-asr-hosted-results-2026-11-28/README.md)
found **six major errors and two acceptable results**, including major errors
in all five Greek clips. It is rejected for adoption. This recognizer-only
screen does not establish timestamps, speaker integration, fresh validation or
whole-application resource fit.

The official [Krikri six-case translation screen](krikri-screen-2026-11-28/README.md)
completed all original cases with verified native prompts, normal stops and
unloads. Independent review found **five acceptable outputs and one major
error**: Nikos and Eleni became the localized names Nick and Helen. Their roles
and the distinction from Elena survived, but the name-preservation criterion
still fails. The standalone run took 110.945 seconds and peaked at 5533.7 MiB
sampled concurrent RSS under the 6144 MiB limit. It is not approved for promotion
or broader validation. The separate [generic name-instruction clarification](krikri-name-preservation-2026-11-28/README.md)
also completed all six cases but retained the identical Nick/Helen substitutions:
again **five acceptable and one major error**. The actual changed prompts were
verified. It took 113.511 seconds with 5538.5 MiB sampled concurrent RSS. Neither
profile progressed to broader validation; the original baseline, criteria and
failed setup-check attempt remain preserved.

The [full large-v3 hosted screen](large-v3-hosted-results-2026-11-28/README.md)
completed all eight original recordings on isolated commit `73b75b45`, using the
unchanged production recognition policy. It used 3096.65 MiB worker high-water
RSS and completed its recognition calls in 136.213 seconds. Independent review
found **four major, one minor and three acceptable** results: several meanings
improved, but three name errors and a malformed concessive relationship remain.
It is not approved for adoption. A native segment also ended at 7.0 seconds for
6.54 seconds of audio. The raw overrun remains unchanged in the evidence. The
separate [production timing correction](asr-timing-boundary-2026-11-28/README.md)
caps valid native endpoints at the full recording duration and quantizes subtitle
cues inward, removing the artificial 100-millisecond extension. It preserves
TXT/JSON and saved/batch warnings when a subtitle interval is unrepresentable.
The eight-record retained-output replay verified actual full WAV decoding,
unchanged text and decoder requests, 40 export files, SQLite persistence and
backup restoration. This is not new acoustic inference or meaning approval.
The combined local suite passed **753 tests and 54 subtests**. The subsequently
published `00567db` source passed all ordinary hosted workflows: Ubuntu and
Python 3.11/3.13 passed 753 tests plus 54 subtests; Windows/macOS passed 749 tests
plus 54 subtests with four Linux-only harness controls skipped. Chromium passed
34/34, and fresh checkout, actual ZIP installation and actual audio upload passed.
Default Ollama completed twelve cases with five automatic passes and seven review
flags; meaning remains unreviewed. All six live provider acquisitions failed,
while exact-silence and actual noise rejection passed. The [exact record](integration-2026-11-28/hosted-00567db/checkpoint.json)
retains these results and the upstream check confirming that the latest published
downloader was already installed. Later source edits need their own verification.

The [completed rejected Qwen workflow](qwen3-asr-workflow-retirement-2026-11-28/README.md)
is archived to prevent an identical expensive experiment from restarting merely
because its setup correction is integrated. Its original plans, helper, criteria,
inputs, outputs and published QA commit remain unchanged. Historical contract
tests verify the archived source; all ordinary application workflows remain active.

The [warning-visibility repair](processing-warnings-2026-11-28/README.md)
fixes a separate user-visible inconsistency: completed transcripts retained
enhancement/export warnings in SQLite, but batch history and the saved editor
hid them after restart. Batch detail/history now report completed items with
warnings, affected rows show their notes, and the editor restores and refreshes
them. Controlled 20-item expiry/restart and fresh-process checks passed without
repeating source or model work. Independent source review passed; the combined
local suite passed **757 tests and 54 subtests**. Actual hosted execution of the
new browser restart case is still required.

The [completed `7a53991` record](integration-2026-11-28/hosted-7a53991/checkpoint.json)
now verifies all ordinary workflows for that warning repair. Ubuntu and Python
3.11/3.13 passed 757 tests plus 54 subtests; Windows/macOS passed 753 plus 54 with
four Linux-only harness skips. All 35 browser checks passed, with the original
34 retained, actual server restart and independently inspected desktop/mobile
warnings. Fresh checkout, actual source ZIP, actual upload and default Ollama
execution passed. The twelve language cases remain five automatic passes and
seven review flags, with meaning unreviewed.

Of six individual provider fixtures, the complete 734.15-second Dailymotion
recording passed download, normal Small recognition, SQLite, exports, cleanup
and restart recovery. The other five failed acquisition. A subsequent actual
mixed batch could not reacquire Dailymotion and also failed its YouTube item.
The [independent diagnosis](live-source-diagnosis-7a53991-2026-11-28/README.md)
separates that acquisition failure from application batch logic. It also confirms
that the world-changed phrase exists in raw and saved output at 509.18–520.18 s,
while the unchanged broad 510–529 s full-containment anchor fails. The original
checker remains 27/28; a separate diagnostic reports four lexical matches without
regrading timing. No production timestamp shift or ASR repair is established.

The [next provider repair](provider-metadata-reuse-2026-11-28/README.md)
reuses the resolved metadata that passed the single-video, duration and size
checks, avoiding a second extraction. It rejects unresolved results and extra
URLs/entries before download. Independent review and 104 focused tests passed,
including the installed yt-dlp processing route with network access forbidden.
The combined local suite passed 777 tests plus 54 subtests with unchanged source
hashes. Hosted verification is required; no live-provider recovery is claimed.

The [source-name detector screen](name-span-detector-screen-2026-11-28/README.md)
tested one pinned multilingual PERSON detector on the original six development
sources, without translation or masking. All six calls completed in 17.558 seconds
with 2492.2 MiB sampled RSS and verified cleanup. Independent pre-output span
criteria matched five of six cases and twelve of thirteen person mentions. The
remaining span included the Greek article in `Η Μαρία`, so the raw profile is
rejected for masking. Its full inputs, raw outputs and pre-inference harness
corrections are preserved. This does not approve a translation candidate or
change production defaults; fresh validation remains unused.

The separate [source-boundary follow-up](name-boundary-normalizer-2026-11-28/README.md)
passed its limited offline development comparison: six sources and all thirteen
person mentions match the same pre-output annotations, with only the oversized
article/name span adjusted. All fifty mechanical controls and unchanged-source
checks passed. Four semantic ambiguity/limitation examples remain explicitly
unaccepted as safety claims; this is not approval of unattended name protection.
No detector rerun, masking, translation or production change occurred in that
follow-up. The raw detector rejection and earlier Krikri failures remain unchanged.

The completed [provider checkpoint `6de3fad`](integration-2026-11-28/hosted-6de3fad/checkpoint.json)
passed all ordinary hosted workflows: 777 tests plus 54 subtests on Ubuntu and
Python 3.11/3.13; 773 plus 54 with four Linux-only skips on Windows/macOS;
35 browser cases; fresh checkout/ZIP installations and actual upload. The full
Dailymotion recording passed both individually and in the mixed batch, with
restart recovery. Five other individual sources failed acquisition. The unchanged
single-source tail checker passed 28/28, while the prior 7a failure stays 27/28.
No ASR policy changed, so this does not establish a timing repair or consistent
provider recovery.

The [default-model meaning review](default-qwen-meaning-review-2026-11-28/README.md)
found nine major errors and three acceptable cases in the already-published
7a53991 twelve-case output. Five exact source/criterion/output comparisons bind
to 6de3fad: two retain major errors and three remain acceptable. Seven current
outputs differ and were not regraded. Two historical automatic-pass cases had
major meaning failures; execution and lexical flags do not approve translation.

The [source-name marker screen](krikri-source-name-protection-2026-11-28/README.md)
completed two calls before its required first-failure stop. The first restored
translation had a minor fluency issue without material meaning loss. The second
rewrote all six exact markers, so the strict guard rejected it and produced no
restored or accepted translation. Four cases were not run. The failed stage,
worker exit 1, 65.990-second duration, 5562.9 MiB sampled RSS and successful
owned-process cleanup are retained.
It is not a successful six-case screen or a production feature.

The separate [compact empty-tag screen](krikri-compact-tag-screen-2026-11-28/README.md)
completed all six original development cases once, retaining all thirteen name
mentions and passing its execution/resource contracts. Independent meaning
review found **two acceptable outputs, three minor errors and one major error**:
the explicitly feminine subject in the Greek negation passage became `he` in
two continuing propositions. Exact name restoration therefore did not preserve
all statements about that person. This candidate is rejected. Its 139.865-second
generation phase peaked at 5548.7 MiB sampled owned-process RSS, with successful
unload and cleanup; those measurements do not approve meaning or whole-app fit.
The [preparation record](krikri-compact-source-name-protection-2026-11-28/README.md)
also preserves the initially missed closing-tag guard and its reviewed fix.

A separate [summary feasibility proposal](krikri-summary-feasibility-2026-11-28/README.md)
has retained the first two already-exposed English/Greek summary sources and
their original criteria. Pure source/request-layout checks establish that both
complete timestamped excerpts fit the existing direct-summary branch. The
[independent prospective review](integration-2026-11-28/summary-feasibility-review.json)
finds no preparation blocker, but no native model execution or summary-quality
approval is recorded in that proposal. The planned English-first semantic gate
must pass before its Greek case may run. Fresh validation remains unused.

The subsequent [visible paired-name screen](krikri-visible-name-tag-screen-2026-11-28/README.md)
stopped after its first response changed the protected spelling of Maria. The
guard rejected it before restoration, and five cases remained unrun. The
separate [first actual summary screen](krikri-summary-screen-2026-11-28/RESULTS.md)
passed its native execution checks but failed independent English meaning
review: the paragraph copied `concise factual summary` from the prompt example,
and a key point weakened the requirement to check each quotation with its
speaker. Greek remained unrun. The original source, criteria and failures are
preserved while isolated source-only corrections are reviewed.

The [fixed-text timing stage](post-asr-alignment-diagnostic-2026-11-28/README.md)
completed five full retained inputs with zero new recognition calls, preserving
every source string. Its original global fallback reverted all 86 film segments
after a 0.26-second conflict. A separately frozen [offline correction](post-asr-local-projection-2026-11-28/README.md)
restores only the two incident segments and leaves four short results unchanged.
Independent review verified all exports, source identities and ordered physical
intervals: six of six existing segment anchors pass, while only three of six
word anchors pass. Eight film segments have no usable optional word evidence,
and large timing movements elsewhere still need acoustic assessment. This is
limited reliability evidence, not recognition-quality or production approval.

## Acceptance gates

| Area | Required evidence | Current position |
| --- | --- | --- |
| Installation | Fresh installation, actual launcher, health and homepage; supported-platform checks | At `6de3fad`, Ubuntu and independent Python 3.11/3.13 passed 777 tests and 54 subtests; Windows/macOS passed 773 tests and 54 subtests with four Linux-only harness controls skipped. Fresh Linux checkout and all six actual candidate ZIP installation/startup checks passed. Ordinary requirements provide both the public-video transport and SOCKS dependency. |
| English and Greek ASR | Real licensed speech through upload, reviewed words/names/numbers, ordered timestamps, persistence and exports | Native development and fresh Auto/Turbo recordings passed integrated checks with retained word errors. Small VAD-off development remains two acceptable, three minor, three major; default Auto/Small also passed two Greek app workflows without changing those hypotheses. A seven-input paired comparison now rejects the identical noise hallucination while preserving all four ordinary/20 dB quieter English/Greek transcripts and timings. Quiet English genuinely exercised the second speech detector. Later Parakeet profiles retained four major errors each; native Qwen retained six major errors; full large-v3 retained four major, one minor and three acceptable results. None is adopted. These are development regressions, not an accuracy guarantee. |
| Translation | Faithful actors, quantities, negation and conditions on frozen validation passages; original preserved on failure | No new default is approved. At `6de3fad`, the actual default model completed all 12 hosted corpus cases with five automatic passes/seven review flags, no execution errors, and no general semantic approval. A separate review found nine major errors/three acceptable outputs at 7a53991; five identical current outputs establish at least two major errors and three acceptable cases. The other seven current outputs were not regraded. Whole-result identity detection prevents copied English from being advertised as Greek; the new script guard rejects newly introduced unsupported writing systems while preserving the original transcript. Neither guard verifies meaning. The retained Hy-MT3, Qwen, M2M100 and expanded Gemma candidates all have material meaning failures. Fresh v3 validation remains unused in the published evidence. |
| Summaries and chapters | Actual model, factual source-grounded content, valid chapter times, complete storage/export path | The eight-point prompt/schema/local contract passes two actual final/direct checks, with five earlier English map/reduction responses explicitly replayed. English long output was acceptable, but the direct consent output contained a malformed amount. A fully live Greek long run failed with HTTP500/runner EOF during prompt-cache saving after repeated weak reductions. The next actual run still misstated the consent amount and changed planned returns/feedback to completed actions. Its strict 700/399-character note experiment was rejected: Greek notes also end midword despite valid JSON/stop. Published source retains the model-lifetime fix. Hosted text runs completed but do not approve meaning. This gate remains separate from source highlights. |
| Source highlights | Verbatim text/time fidelity, useful selection on frozen English/Greek sources, complete storage/edit/export/backup path | Rebuilt selector passed six development cases (25/25 declared coverage goals) and four previously unseen frozen cases (18/18 goals), preserving original words/times with no declared context omissions. Both failed development iterations remain retained. At `6de3fad`, actual-upload and saved-highlight generation, source navigation, edits/regeneration and nonnull-highlight backup/restore passed Chromium. Short sources are explicitly uncondensed. These internal fixtures do not establish arbitrary-recording coverage, ASR accuracy or speaker attribution. |
| Speaker labeling | Actual acoustic inference on repeated and distinct voices, silence, short and mixed turns; anonymous labels and honest uncertainty | Public-model inference passed fresh one-/two-/three-reader checks. Actual two-reader upload through Small ASR, conservative word alignment, SQLite and all exports passed; uncertain words retain warnings. Greek/noisy/overlapping-meeting accuracy is not established. |
| Sources | Actual link-to-transcript processing for advertised providers, recognizable content, persistence, exports and cleanup | At `dc0985d`, unseeded hosted processing of the complete 734.15-second Dailymotion film passed storage/export/recovery checks; silence and actual white noise were correctly rejected. Original YouTube/Vimeo access failures remain retained. A separate official YouTube full-film follow-up obtained metadata but media download failed HTTP403 locally. Preserving an explicitly supplied public Vimeo player route fixed an application rewrite bug; an 888.07-second permitted recording passed download/full Small ASR/SQLite/exports/cleanup/restart on frozen `002d8fc` plus that parser correction. Suspicious repeated phrases and low language confidence leave semantic accuracy open. At `7a53991`, one complete Dailymotion fixture passed the normal pipeline and restart; five other single-source fixtures failed acquisition, and Dailymotion could not be reacquired inside a later mixed batch. At `6de3fad`, Dailymotion passed both individually and in the mixed batch with restart recovery; the other five individual acquisitions failed. The provider gate remains open. |
| Batch recovery | Continued processing after one failed item; persistence and restart without duplicating saved work; correct batch downloads | At `dc0985d`, deterministic process-interruption tests and the actual hosted Dailymotion-success/YouTube-failure batch passed. Stored transcripts and batch ZIP contents survived a fresh-process restart. The latest `6de3fad` actual mixed batch also preserved the completed Dailymotion transcript alongside the failed YouTube item through restart and batch export. |
| Library and backups | Browser search/edit/download/delete, invalidation of stale AI output, backup/restore and malformed-backup handling | Hosted integration covers source-hash validation, atomic rejection of fabricated excerpts, stale-data invalidation, damaged optional highlights, version2 backups and legacy version1 imports. At `6de3fad`, actual Chromium verified corrections after generation, preservation during saves/opens, saving to the original record while leaving another record unchanged, and backup/restore with actual nonnull highlights. The additional actual-restart case preserves processing warnings in batches, editors and downloaded backups. |
| Browser usability | Desktop and mobile layout, consent/errors, job polling, result display, downloads and setup diagnostics | At `6de3fad`, hosted Chromium passed 35/35 checks with actual speech recognition and no JavaScript page errors, including 1440/390/320-pixel layouts. Persisted warning visibility and clean-record clearing after a real server restart also passed. All eight recorded source hashes match the checkpoint. The unchanged interface's representative `929cf2d` screenshots were independently reviewed. Prior 31/32 and 33/34 failures remain retained and their corrections were rerun. Link/batch UI fixtures remain controlled and separate from actual provider evidence. |
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
- [Rejected dedicated M2M100 translation screen](m2m100-followup-2026-11-28/README.md)
- [Rejected Parakeet recognition and frontend comparisons](parakeet-screen-2026-11-28/README.md)
- [Gemma 4 six-case development screen](gemma4-screen-2026-11-28/README.md)
- [Rejected expanded Gemma 4 translation regression](gemma4-exposed-v2-2026-11-28/README.md)
- [Rejected one-case native-thinking ablation](gemma4-thinking-ablation-2026-11-28/README.md)
- [Prepared native CPU Qwen speech screen](qwen3-asr-screen-2026-11-28/README.md)
- [Rejected actual Qwen speech run and independent meaning review](qwen3-asr-hosted-results-2026-11-28/README.md)
- [Completed application workflows at a4ca88e](integration-2026-11-28/hosted-a4ca88e/checkpoint.json)
- [Official Greek-specialist model research](greek-specialist-research-2026-11-28/README.md)
- [Krikri six-case translation screen and exact name-substitution failure](krikri-screen-2026-11-28/README.md)
- [Rejected generic name-instruction clarification](krikri-name-preservation-2026-11-28/README.md)
- [Full large-v3 actual outputs, independent review and native timing overrun](large-v3-hosted-results-2026-11-28/README.md)
- [Physical recording boundaries, subtitle exports and retained-output replay](asr-timing-boundary-2026-11-28/README.md)
- [Completed rejected Qwen workflow archive](qwen3-asr-workflow-retirement-2026-11-28/README.md)
- [Durable batch and saved-editor processing warnings](processing-warnings-2026-11-28/README.md)
- [Source-name detector research and frozen plan](name-span-protection-research-2026-11-28/README.md)
- [Rejected raw name-detector screen and independent exact-span review](name-span-detector-screen-2026-11-28/README.md)
- [Limited source-boundary follow-up and explicit ambiguity limits](name-boundary-normalizer-2026-11-28/README.md)
- [Hosted processing-warning behavior and selected screenshots](processing-warnings-hosted-2026-11-28/README.md)
- [Current full-source diagnosis without regrading its failed timing check](live-source-diagnosis-7a53991-2026-11-28/README.md)
- [Reuse of validated provider metadata and independent contract review](provider-metadata-reuse-2026-11-28/README.md)
- [Default-model meaning review and exact current-output comparison](default-qwen-meaning-review-2026-11-28/README.md)
- [Rejected source-name marker experiment with four cases unrun](krikri-source-name-protection-2026-11-28/README.md)
- [Rejected complete compact-tag translation screen](krikri-compact-tag-screen-2026-11-28/README.md)
- [Compact-tag preparation and preserved initial guard failure](krikri-compact-source-name-protection-2026-11-28/README.md)
- [Prospective English/Greek summary feasibility without model execution](krikri-summary-feasibility-2026-11-28/README.md)
- [Rejected visible paired-name screen, with five cases unrun](krikri-visible-name-tag-screen-2026-11-28/README.md)
- [Rejected actual English summary screen, with Greek unrun](krikri-summary-screen-2026-11-28/RESULTS.md)
- [Fixed-text timing stage and original global fallback failure](post-asr-alignment-diagnostic-2026-11-28/README.md)
- [Localized conflict fallback and complete retained-output review](post-asr-local-projection-2026-11-28/README.md)
- [Translation writing-system corruption guard and retained-output replay](translation-script-guard-2026-11-28/README.md)
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

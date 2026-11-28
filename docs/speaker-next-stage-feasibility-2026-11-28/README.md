# Next speaker acceptance stage: retained three-reader application case

**No additional production repair is justified by this inspection.** The highest
value bounded next speaker check is the already exposed 49.38-second
`three_speakers_returning.wav` through the current complete application path.
Its acoustic backend already passed the original criteria; the new fixed-text
timing and persistence path has actually been exercised only on the two-reader
fixture. This recommendation adds an integration observation, not a corpus,
model, threshold, or release requirement.

This record is source-only preparation. No model, native frontend, audio decode,
provider, network, or test execution occurred. Production and existing evidence
were not edited. [evidence-inspection.json](evidence-inspection.json) binds the
source and retained reports read during this inspection; its hashes identify
that snapshot, rather than asserting later live documents remain unchanged.

## Which failures the timing repair does and does not address

| Retained observation | Evidence-supported classification | Current implication |
| --- | --- | --- |
| Initial one/two/three-reader failures at clustering distance 0.36; second cohort failures at 0.45 | Actual acoustic clustering split returning readers into extra labels. These standalone reports never invoke speech recognition. | They are not failures of the ASR word-timing path. The v4 acoustic change already resolved the supported cases; no new threshold change is supported. |
| Final v4 one/two/three-reader cases across all three cohorts | Supported clean checks passed. The current `diarization.py` hash is exactly the final v4 hash. | Existing acoustic evidence remains relevant. It must not be described as a new effect of the fixed-text timing integration. |
| Final 0.55-second short-only and silence cases | Correct abstention; no speaker identity was established. Short-in-context and overlap cases were explicitly unsupported stress observations. | Do not reinterpret conservative abstention as a new failure or lower support requirements to force a label. |
| Fresh overlap case reported one speaker for two mixed readers | An actual limit of the acoustic backend, explicitly documented as unsupported. | Word alignment cannot unmix voices or repair their embeddings. The uncertainty/overlap warning remains necessary; no small evidence-supported patch is identified. |
| Official-film recognition with word timestamps and the 2.0-second heuristic omitted abort/memory commands; alignment-only restored those commands but introduced other action/name errors | Changes occurred in raw recognition output before persistence. The combined first comparison alone did not isolate every cause. The later ablation established specific recovery and separate regressions. | Baseline recognition and optional timing are now decoupled. The postpass preserves accepted words, but this does not turn an inaccurate baseline into correct speech or regrade the old rejected outputs. |
| Original fixed-text stage discarded all 86 film estimates after one 0.26-second crossing | A projection/fallback defect after fixed-text native alignment. | The reviewed local fallback restores only conflicting segments. It retains 78/86 word-bearing segments, with eight explicit optional-word fallbacks. This concrete reliability repair is already integrated. |
| Remaining film timing movements and absent optional words | Six broad segment anchors pass, only three word anchors pass. Oh/Sorry/I'm sorry show large movements needing acoustic assessment. | Do not add a reference-fitted maximum-shift rule, invent word boundaries, or treat the broad-window result as acoustic accuracy. Whole-segment fallback preserves text. |
| The 7a world-change anchor failed | The exact phrase exists at 509.18–520.18; its start falls 0.82 seconds outside the frozen full-containment window. | It is a timing-gate failure, not omitted dialogue. The original media is unavailable for a byte-matched postpass; the old failure remains unchanged. |
| Default Small development ASR had three major cases | Proper-name corruption, collision/concession errors and Lakkha/bhajans corruption are lexical or semantic recognition errors. | Fixed-token timing deliberately preserves these words. Neither speaker relabeling nor a text substitution is a legitimate repair. |
| f2 two-reader current application worker completed, but final controller rejected constructor zero | A checker expectation error, independently diagnosed against pinned native source. | The separately reviewed constructor correction preserves the actual failure and limited acoustic success; no speech rerun was needed. |

The initial and v2 speaker failures, final v4 cases and exact settings are
retained in [the original speaker evaluation](../speaker-evaluation-2026-11-26/README.md).
The current acoustic module remains SHA-256
`89e497f711c538413c3df79a77421c3ef5272bb63f784df2943ad1c5deccbe47`.
The Greek/English `speaker-words-report.json` was a word-preservation probe with
no acoustic turns and explicitly no acoustic inference; its Unknown labels are
not a Greek speaker-accuracy failure or success.

The [full-reference ASR comparisons](../asr-official-tail-2026-11-28/README.md),
[local fixed-text projection review](../post-asr-local-projection-2026-11-28/README.md),
[7a diagnosis](../live-source-diagnosis-7a53991-2026-11-28/README.md), and
[actual f2 application result](../hosted-speaker-f2ebd04-2026-11-28/README.md)
retain the separate observations and limitations.

## Single bounded prospective stage

Use the exact previously evaluated **three-reader** fixture:

- Filename: `three_speakers_returning.wav`.
- WAV SHA-256: `8ddce1f24ae57e9f3d5041fda7022c363f2cd31c6272e3d9ba98fa45d04747bf`.
- Recorded duration: **49.38 seconds**; derived expected sample count **790,080 at 16 kHz**.
- Original six-utterance order: reader 2961 utterance 0; 8455 utterance 0;
  4507 utterance 0; 2961 utterance 1; 4507 utterance 1; 8455 utterance 1.
- Original construction: 0.5-second initial silence, each source capped at the
  original eight seconds, and 0.6-second gaps including the final gap. This
  reproduces the existing fixture; the resulting complete WAV reaches the app.
- Original acoustic outcome: **3 speakers**, **329/364 assigned interior
  samples = 0.9038**, global permutation purity **1.0000**.

[prospective-stage.json](prospective-stage.json) binds the six original FLAC
hashes, exact public dataset revision/rows, original six intervals, construction
and original score. Four source clips are already retained with the f2 artifact;
the two 4507 clips still need exact-hash recovery if this stage is authorized.
No recovery was attempted here. A current complete decoded PCM hash is not yet
available and is not invented; exact WAV hash, format, sample count and decoded
identity are preparation checks before model initialization.

Retain the existing expected three-speaker acoustic count and original 0.80
coverage/0.95 permutation-purity thresholds. References and expected count are
used only after inference. Run one baseline transcription with word timing off,
then the same-engine fixed-text pass and actual acoustic backend. Observe
recognizer release, complete source/text/token binding, optional fallback
warnings, native returns, durable SQLite reload, exports and backup using the
same current structural contract. Review saved text/labels against the raw
turns; label count alone cannot establish attribution accuracy.

The existing four-CPU, 6 GiB, 180-second phase/90-second persistence and
600-second worker limits can remain unchanged. Keep one initialization and one
attempt, with no hints, alternate source, transcript repair, threshold tuning or
unobserved retry. Freeze its new helper/plan before any separately authorized
hosted execution.

The currently published two-reader helper deliberately requires four source
clips and its original fixture hash. It must not silently accept this different
case. The smallest preparation would be a separate reviewed case wrapper that
reuses its download/cache, monitor and actual-app observer, while independently
reconstructing the original six-clip fixture and applying the unchanged scorer
with the original expected count of three. Existing plans remain historical.

## What this would resolve

A successful stage would establish that the current integrated path handles
three distinct returning voices across six utterances and multiple recognizer
windows, preserves the baseline text and persists the actual speaker result.
It would directly extend the documented repeated/distinct-voice application
evidence beyond the single two-reader case.

It would not close Greek ASR meaning, natural-meeting/overlap speaker accuracy,
general acoustic word timing, long-recording memory or whole-machine headroom.
Those remain separate uncertainties. The retained evidence supports this small
next acceptance stage, rather than another acoustic threshold change or an
unsupported claim that all previous speech failures were fixed.

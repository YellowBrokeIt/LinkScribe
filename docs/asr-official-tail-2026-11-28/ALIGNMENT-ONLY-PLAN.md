# Prepared ablation: word alignment with the hallucination heuristic disabled

**Status at preparation: not run.** The preceding aligned/2.0 policy passed four
fixed late anchors but omitted two other published spoken commands. It is not
accepted as generally speech-preserving. This ablation separates word alignment
from the dependent silence heuristic; it is not a threshold search.

The executable [plan](alignment-only-plan.json) has SHA-256
`b7c8a2be6c40a5add4b6cf2a738819039ecde5d96f485a0b807af757958d22b1`.
The [isolated patch](alignment-only-proposed.patch) changes the actual recognizer
keyword to `hallucination_silence_threshold=None` and updates the corresponding
processing metadata. `word_timestamps=True`, Small, full decoded audio, VAD off,
automatic language, beam size 5, original temperature fallback and absence of
reference prompts remain unchanged. Production source and the frozen provider
checker have not been edited by this preparation.

## Frozen inputs and comparisons

| Film | Complete input | Seed | Comparison |
|---|---|---:|---|
| Official *Tears of Steel* | Previously downloaded 734.000 s stereo FLAC; same 11,744,000-sample decoded PCM | 1729 | The completed baseline and aligned/2.0 normal-upload arms in this folder |
| Retained Vimeo *Sintel* | Previously downloaded 888.070375 s media; same 14,209,126-sample decoded PCM | 20261128 | Prior aligned/2.0 full-recognizer run with the same seed; the unseeded original pipeline remains contextual evidence |

Both use Small revision `536b0662742c02347bc0e980a01041f333bce120` and model.bin
SHA-256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.
Media, PCM, reference, fixture-manifest, source, runner, controller and model-file
identities are pinned in the plan. The controller's validate-only invocation
passed without importing a model or starting inference.

The two films run sequentially through the existing real upload harness with
actual saved-record, export, in-memory eviction and independent-process SQLite
checks. Observers record actual input identity, model resolution, requested and
effective decoder options, and every raw segment/word construction. References
are supplied only to the evaluator. This remains separate from exact provider
acquisition; no blocked provider request is repeated.

## Review criteria fixed before execution

The four original official-film anchor patterns/windows are unchanged. The
exploratory omissions are now declared additional regressions before this new
run:

- Cue 70, 506–508 s: retain the captain/abort command, with a 501–513 s review
  window.
- Cue 73, 538–539 s: retain the memory-completion command, with a 533–544 s review
  window. The baseline's “override” spelling remains an explicitly reported
  lexical error rather than a corrected transcript.
- Cue 62's good-ad-lib phrase remains a named substitution to inspect, alongside
  the complete reference review.

Review all 76 official-film cues and all 26 published *Sintel* cues against the
uncorrected normal output. Record conspicuous new omissions, substitutions and
timing problems, rather than inferring success from four matches. For *Sintel*,
also inspect the previously unsupported 177.84–207.50 s burst, real quiet speech
around 207–233 s and 445–465 s, the 669.5–691.5 s ellipses, the character call,
and genuine late singing. Reference gaps alone are not evidence of silence;
the short published SRT is not a complete sung-word reference.

A lower segment count is not an acceptance criterion. Preserve all outputs and
failures. Do not promote the policy on the basis of a structurally successful
run or a passing anchor subset. Earlier quiet/noise results remain evidence for
their own recorded settings, not new tests of this unrun configuration.

## Fixed bounds and model coordination

There is one planned attempt per film: a 240-second harness recognition timeout,
a 255-second hard child-process wall bound, and 600 seconds for the two-film
execution. The Linux controller samples the owned process group's RSS every
0.25 seconds, terminates it above 2.5 GiB, and also rejects a completed harness
report whose recorded process peak exceeds that limit. Sampling can miss brief
aggregate peaks; this is not a whole-machine memory guarantee. No virtual-address
space limit is substituted for RSS.

The controller validates only by default:

```sh
python docs/asr-official-tail-2026-11-28/run_alignment_only.py \
  --plan /workspace/scratch/94360995dd61/asr-alignment-only-2026-11-28/plan.json
```

The root coordinator must review the plan and release the model slot before
adding `--execute`. That creates a fresh results directory, preserves both logs
and execution limits, and stops on a failed/limited arm. No retry or parameter
adjustment is part of this plan.

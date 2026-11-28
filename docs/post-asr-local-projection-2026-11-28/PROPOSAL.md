# Prepared offline conflict projection

This is one proposed correction to the completed fixed-text diagnostic. No
actual retained output has been replayed under this policy during preparation.
No model, encoder, alignment, recognizer, tokenizer, provider or network request
is involved. Production remains unchanged.

## Problem and preserved original outcome

The original one-shot five-input stage completed its declared 23 native windows
and kept every source string. Its full-film timing projection encountered one
0.26-second overlap between neighboring original windows. The frozen policy
reverted all 86 segment timings to baseline. The original profile therefore
failed its full-film improvement goal, with four of six final segment anchors
and no final private-word anchors passing. Its raw results, helper, plan and
independent review remain unchanged in the original experiment directory.

The new policy addresses the breadth of that fallback. It does not make the
native estimates acoustically accurate, remove baseline recognition errors or
change any reference window. The new policy and its replay require a separate
review; the original failed profile cannot be relabeled a pass.

## Generic interval policy

The existing per-segment projection is copied without a behavioral change. A
synthetic AST control compares its entire executable prefix with the frozen
original. It preserves fixed text and tokens, checks the original encoder
window and physical bounds, and clears unusable optional word evidence while
keeping all source text. Existing subtitle conversion remains unchanged.

Only the final conflict policy changes:

1. Require a physically valid, ordered baseline and equally complete candidate
   list. A source whose baseline already overlaps has no guaranteed ordered
   fallback; report that limitation instead of shifting or dropping text.
2. Detect every adjacent conflict with the original `1e-9` comparison tolerance.
   Inspect intervals only, without source IDs, words, phrase windows or scores.
3. Restore both participants of each conflict to their exact physically bounded
   baseline start and end, and clear all private word evidence for each restored
   segment. Preserve every other field, source string and list position.
4. Detect conflicts again. A restored baseline interval may overlap a neighboring
   candidate, so extend the fallback set and repeat. Each nonterminal round must
   add at least one segment. An ordered baseline guarantees convergence in at
   most the number of segments; the complete baseline is the conservative limit.
5. Preserve all unaffected candidate intervals and private words exactly. Do not
   clip, average, shift or interpolate the conflicting native estimates. Retain
   the original native output separately and record every fallback round.

The algorithm uses no reference material or source-specific constants. The
experiment wrapper binds the same five inputs only to keep the comparison
auditable. It reads retained JSON; it never recomputes an acoustic feature or
token. It keeps the original six phrase windows, all 76 publisher cues, original
recognition errors and missing-7a-audio limitation for later evaluation.

## Controls and replay contract

Synthetic controls cover a single conflict, disjoint conflicts, propagation to
a new neighbor, propagation in both directions to the whole baseline, finite
termination, equal boundaries, the existing float tolerance, exact fractional
physical duration, no text/order/metadata/input mutation, invalid baseline or
candidate intervals, unchanged per-segment policy and the existing whole-segment
fallback for zero-duration optional words. They do not project actual outputs.

The frozen plan binds this helper and its controls, the original helper/native
contract/timing view, complete input manifest, original report and all 51 raw
result files through the original raw manifest. `--validate-only` verifies these
identities without applying the new projection. `--replay` refuses an existing
output directory, writes one result per original case and retains any partial
failure. There is one proposed replay and no automatic retry.

After independent source review and root authorization, the command is:

```bash
python /workspace/scratch/94360995dd61/post-asr-local-projection-2026-11-28/replay_projection.py \
  --replay \
  --plan /workspace/scratch/94360995dd61/post-asr-local-projection-2026-11-28/plan.json \
  --output /workspace/scratch/94360995dd61/post-asr-local-projection-2026-11-28/results
```

Any later broad-window improvement must remain separate from word-level timing
accuracy. Restored conflict segments have no private-word timing. The current
experiment is standalone, with no application integration, speaker inference,
default change or v1 acceptance.

# Completed offline local-fallback projection

This separate candidate reused the original fixed-text stage's retained native
results. **No model, frontend, encoder, alignment, recognition, language detection,
provider or network call was performed.** The one authorized replay completed
in 0.119 seconds internally (0.182 seconds subprocess wall), exit zero, with no
retry. The original global-fallback stage remains rejected and unchanged.

## Reviewed outcome and limits

The new generic policy restored only the two conflicting segment indices 80 and
81 to their exact physically bounded baseline intervals, cleared their private
word evidence, and kept unaffected candidate estimates. All 86 original film
strings and order remained unchanged. The four ordinary/quiet short candidates
were exactly unchanged from the original stage's candidates.

The independent root audit found zero contract errors. The final film output
passed **6/6 original broad segment-anchor windows and 3/6 private-word windows**.
The Maybe phrase lacks usable word evidence; the final two anchors explicitly
use baseline conflict fallback. Overall **78/86 film segments** retain validated
private words. The review covered all 86 timeline segments and all 76 publisher
cues. Large movements around Oh, Sorry and I'm sorry remain; these broad-window
passes do not establish general acoustic word/speaker accuracy or ASR quality.
Original lexical errors and unsupported source text are deliberately preserved.

All **40 exported files** were verified: five inputs × baseline/candidate ×
TXT/JSON/SRT/VTT. This includes 20 subtitle files and 20 TXT/JSON files. The first
review audit used binary floating-point floor for an endpoint at 520.42, then
corrected the audit to the existing published Decimal quantization. Both audit
versions and that correction are retained; candidate code and outputs were not
changed to fit the review.

## Evidence

- [Prepared policy](PROPOSAL.md), [frozen plan](plan.json) and [helper](replay_projection.py).
- [Fourteen synthetic controls](synthetic-tests.txt), [validate-only record](validate-only.json)
  and [independent source contract review](independent-source-contract-review.json).
- [Actual replay execution](replay-execution.json), [raw report](results/report.json)
  and [46-file raw-output manifest](raw-results-manifest.json).
- [Independent completed timing review](independent-result-review/independent-timing-review.json)
  and its retained audit files.
- The [selected original-stage archive](../post-asr-alignment-diagnostic-2026-11-28/README.md)
  retains all original native results and separately identifies omitted PCM arrays.

This complete local-projection bundle contains code, JSON, controls, reviews and
exports; it contains no audio arrays, media or model weights. The frozen plan
and before-output manifest preserve their historical absolute dependency paths.
They are execution provenance, not a claim that those paths exist in a new clone.
No production source, default model, original reference window or historical
failed result was changed by this offline candidate or this archive operation.

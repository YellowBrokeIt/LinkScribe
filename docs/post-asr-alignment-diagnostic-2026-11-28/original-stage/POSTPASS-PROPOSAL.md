# Revised proposal: fixed text with the complete upstream timing postprocessor

**Preparation only. No model has been constructed or run.** This changes the
initial raw-alignment-only proposal and requires a new review. The original
proposal and its review remain frozen in the adjacent
`post-asr-alignment-feasibility-2026-11-28` directory. Production remains at
`6de3faddf88bb5da8ea35d985b33ad26e55e249f`.

## Why the initial raw-only route must not be run as the proposed repair

Pinned CTranslate2 4.9.1 source, commit
`88e735ac42a2a97c7c10daec4e7ce9db49edf562`, constructs an alignment matrix with
`N + 1` text rows for `N` recognized text tokens. The final row is a terminal
boundary. There are only `N` text probabilities. The ordinary DTW path spans
text indices `0..N` and starts at text index zero / time index zero.

Faster Whisper's `find_alignment` takes the first time at each text-index jump.
Its word-boundary array starts at cumulative token index zero. Therefore the
first word's raw start is the beginning of its encoder window. It is not an
independent estimate of speech onset after leading silence.

The retained official-film captain/abort and world-change phrases are first in
their original windows. Raw alignment alone would keep their starts at 485.0
and 508.8 seconds, respectively. These cannot be wholly contained in the
unchanged 501–513 and 510–529-second checks. No model call is needed to discover
this limitation.

The exact primary files are retained under `native-contract/`, with SHA-256 and
verified Git blob identities. `check_native_contract.py` demonstrates the source
recurrence using **synthetic matrices only** and validates the terminal-index
contract. Its four positive examples include a legitimate zero-duration token
span; seven malformed-result examples reject. These are code-contract controls,
not actual alignment outputs or acoustic quality evidence.

## Revised candidate

Use the entire installed Faster Whisper 1.2.1 `add_word_timestamps` function,
unchanged, **on copies of the already completed baseline segments**. Run it
outside `generate_segments`, after recognition is fixed. This uses the same
Small model and full source identified in the initial proposal.

The function can move an initial word boundary because it combines attention
alignment with ordinary upstream duration estimates. Those are estimates, not
measured speech boundaries. The rationale is to test a supported, complete
timing postprocessor without letting it alter subsequent recognition. It is
not to choose a threshold that fits the two known lines.

The five inputs, full audio hashes, original text, original 19 film windows and
four short full-clip windows, exact model/runtime identities and resource caps
remain as described by the initial audited proposal. No 7a Dailymotion audio is
available, so this remains a separate official-film/four-clip diagnostic. The
current 6de ordinary hosted tail check already passed 28/28; this proposal does
not regrade either historical provider run.

## Exact upstream transformations included

All of the following belong to the single pinned function. No subset will be
selected after seeing output, and no constant will be tuned.

| Upstream operation | Declared behavior |
| --- | --- |
| Fixed-token alignment | Flatten original per-segment text tokens within each original window; call native alignment once through `find_alignment`, with its default median filter width 7. |
| Word duration summary | Use the median nonzero aligned word duration, capped at 0.7 s; maximum ordinary word duration is twice that median. |
| Sentence-boundary adjustment | Shorten overlong punctuation timing, or move a word start after sentence punctuation, using the calculated maximum duration. |
| Punctuation merging | Apply the exact native prepend/append punctuation sets from the retained effective decoder configuration, retaining token/string reconstruction evidence. |
| Global coordinate conversion | Add the original seek offset and use the function's normal two-decimal timing representation. |
| Long first/second word after a pause | Use the upstream four-median pause condition and two-median duration limits; its calculation can move the first word start away from window zero. |
| Coarse segment boundary preference | Use the function's existing 0.5 s comparisons and median-duration estimates when a first/last word is implausibly long relative to its original segment boundary. |
| Sequential timing state | Begin `last_speech_timestamp` at zero. Ignore the method's return for state, as `generate_segments` does; obtain `get_end(current_segments)` on the raw adjusted copies, and update state only when it is non-None. The helper prefers the last actual word end, then the last segment end when there are no words. Retain both values for audit. |

The preceding duration and boundary adjustments are now an explicit part of the
candidate. They were excluded from the initial proposal. This is the material
protocol change requiring review.

## Operations excluded and invariants enforced

No recognizer, `transcribe`, `generate`, new language detection, decoder fallback,
recognition `seek` update, hallucination-silence filtering, VAD crop or source-text
repair is permitted. The worker must make forbidden entry points fail and log
the actual encode/alignment calls. References, subtitle cue text/windows, names,
glossaries and other hints remain outside the worker's alignment inputs.

The original segment list, order, text strings and complete native token arrays
are immutable. Work on deep copies, then assert exact preservation. The output
must copy the original source string, never reconstruct or replace it from a
newly interpreted word list. The four quiet-clip controls have only saved strings;
their pinned re-encoding is explicitly labelled and must round-trip exactly.
It is not claimed to be their original decoder token segmentation.

Keep three distinct timing layers: raw native token path/probabilities; native
word boundaries before the duration/punctuation operations; complete upstream
adjusted word/segment times. Instrument the one real call to retain these layers
without running a second alignment. Native terminal index `N` is required for
the last endpoint but must never become a generated text token. Token-to-segment
spans must be complete and nonoverlapping. Punctuation merging may not silently
move an unassignable word across an original segment boundary.

## Invalid timing and fallback

The diagnostic preserves the complete original transcript regardless of optional
timing failure. It must retain raw failures, not repair them to pass the gate.

- Missing/reordered tokens, changed source text, malformed native paths or a
  nonfinite sequential timing state are structural failures of that input's
  candidate. Preserve its original complete result and report the failure; do
  not invent the missing endpoint or retry alignment.
- Candidate segment intervals require finite ordered endpoints, a positive
  duration, the correct original window and the full source's physical bounds.
  An invalid interval retains that original whole segment and its baseline
  timing, with an explicit alignment warning. Report fallback coverage; a
  fallback is not an improved timing result.
- Optional word validity is separate from segment validity. Zero-duration or
  otherwise unusable word timing invalidates the whole segment's private word
  evidence. Keep all text and the existing speaker fallback. The real historical
  zero-duration words remain controls. Do not reject otherwise valid source text
  or pad a word to an invented positive duration.
- Apply the current production full-duration endpoint cap and inward subtitle
  quantization to both baseline and candidate projections. Preserve the original
  raw records. An unrepresentable subtitle cue keeps TXT/JSON and a warning.
- Validate the final sequence after local fallbacks. If it becomes crossed or
  unordered, retain the complete baseline timing rather than sorting the text,
  shifting boundaries or silently creating overlap. Raw candidate evidence stays
  available for diagnosis.

The raw upstream `get_end` sequential timing state is retained for the experiment;
downstream fallback projections do not silently alter it. If that state becomes
nonfinite or physically impossible, stop that input's candidate. This makes
future timing behavior auditable instead of introducing a hidden tuned state.
The earlier draft incorrectly described carrying the method return. That draft
is preserved in `preparation-history/`; independent source review identified the
difference before any worker implementation or model call.

## Controls, review and stops

Before any real call, verify all model/runtime files, complete PCM identities,
full-source mel settings, original seek/frame mapping, per-segment token spans
and exact source strings. Malformed-result controls cover the terminal boundary,
missing/reordered tokens, wrong audio/window/frame identity, nonfinite and
reversed intervals, zero word spans, cross-segment punctuation mappings,
physical endpoint limits and subtitle intervals that cannot be represented.
Use the actual current bound/export functions in a source-bound isolated view;
do not claim that a copied imitation certifies the application.

Actual results require full text retention on all five inputs, all original
official-film phrase windows unchanged, and review across all reference-covered
dialogue, not just the target line. Keep source-text preservation, interval
containment, fallback coverage and independent acoustic accuracy as distinct
results. Publisher subtitles are coarse evaluation evidence, not a source of
candidate boundaries. No acoustic-timing approval follows automatically from
broad window passes.

Preserve the five full arrays, raw paths and timing layers, source/model/runtime
hashes, every warning, RSS sample series, high-water measure and owned-process
cleanup. The prospective limits remain one initialization, one attempt per
input, CPU int8, one worker, at most four available threads, 2.5 GiB owned RSS,
120 s startup, 240 s per input and 600 s overall. Resource success is unmeasured
until an authorized actual run. No speaker or language model is loaded in this
diagnostic, and the production/default policy remains unchanged.

Even a successful result would only support further integration work. This
postprocessor can place wrong words in time; all baseline lexical mistakes and
unsupported output remain untouched. It cannot establish speech truth, fix ASR
meaning, certify speakers, or close the release gates by itself.

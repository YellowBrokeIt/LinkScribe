# Whole-recording speech corroboration candidate

Base: published `2760679cdcd5bf2fdd0f18589e821a89d2bd9b90`.
The main repository is untouched; `base/` and `candidate/` are independent
exports of that Git tree. The patch manifest identifies the exact changed bytes.

## Fixed policy

The complete decoded ndarray still reaches ordinary Faster Whisper with VAD
prefiltering disabled. The existing no-speech value, 0.6, is explicit and shared
between the normal call and the whole-output check. Only when every nonblank
returned segment has a finite numeric no-speech score greater than 0.6 does the
candidate call the existing Silero detector with its default settings on that
same complete array. Zero speech intervals rejects the complete result before
persistence. One interval preserves every original segment; no interval is used
to crop audio, filter a segment, adjust a timestamp, or rewrite text. An exception
in this diagnostic yields a specific cannot-verify error with its original cause.

Missing/nonfinite scores do not establish the all-high predicate. A score or
Silero interval is supporting model evidence, not proof that words are correct.
The exact-zero and decoded-duration checks remain intact. This candidate does
not claim to remove hallucinations inside otherwise genuine recordings.

## Evidence and bounded rationale

The hosted 32-second noise output had no-speech probability 0.9914, but its
average log probability −0.9115 overrode the decoder's existing −1.0 threshold.
The hosted film had 72/64 segments, with only 1/2 individually above 0.6 and
whole-recording minima 0.0503/0.0480. Retained late dialogue had scores between
0.0480 and 0.1659. This supports testing a whole-recording conjunction without
per-segment rejection. It does not establish calibrated probabilities.

Temperature zero is not this candidate. The original fallback repairs some
repetitive or weak hypotheses; its selected noise output came from temperature
0.8, but the saved evidence lacks the earlier attempts. A final recorded
temperature of 1.0 can also label a result selected from an earlier failed
attempt, because the fallback returns its final attempted temperature.

Primary implementation:
https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py

## Frozen actual comparison

`fixtures/manifest.json` was written before inference. Its seven inputs are the
identical hosted exact-zero and deterministic white-noise WAVs; one new owned
16-second 440 Hz tone; the first Greek and English clips in the existing FLEURS
development manifest; and complete-length float32 copies multiplied by 0.1
(−20 dB amplitude). These are development regression cases, not fresh accuracy
validation. References never reach the recognizer.

`run_comparison_arm.py` runs actual app upload, decoding, default Small/auto
recognition, SQLite and exporters in separate processes and private stores for
base and candidate. The CTranslate2 seed is explicitly reset to 1729 on each
recognition worker, identically in both arms; this declared QA setting is not a
bitwise determinism guarantee. Normal temperatures and model options are intact.
Every checkpoint preserves raw constructed segments, scores, actual transcribe
options, complete-array identity/hash, and any full-recording Silero intervals.
Rejected inputs must have the exact no-words error, no database record, 404 on
all library exports, and cleaned input. Positive inputs must retain a record and
matching exports; their wording still requires review.

The original hosted tail excerpts existed only in RAM and are not cached. A new
hosted full-film test remains necessary, including the prior late dialogue,
mixed batch and restart checks. No restricted provider access is attempted.

## Model identity

The actual production resolver is called unchanged and its returned directory
is checked before construction against Small revision
`536b0662742c02347bc0e980a01041f333bce120`, with all four model file lengths and
SHA-256 values verified. The model.bin SHA is
`3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.
Both processes use the existing isolated cache with HF_HUB_OFFLINE set before
imports. This is stronger than merely attaching a supplied manifest.

For future hosted runs, observe that same resolver result and preserve actual
file hashes. Preflight the default resolution against an expected revision in
an isolated cache, then start the app in a fresh offline process; if upstream
main has changed, fail preparation for review rather than silently comparing
different weights. Faster Whisper also exposes an explicit revision argument
for a later deliberate production pin; no such production change is included.

## Acceptance and limits

43 focused synthetic regressions passed before inference. Both arms and every
failure are retained. If the new guard rejects a positive clip, the candidate
is not ready. If noise passes only because ordinary ASR already returned no
words, record that distinction: it does not exercise the new conjunction.
When the candidate actually invokes the conjunction, its input must match the
uncropped ASR array exactly. No threshold will be adjusted to rescue this run.

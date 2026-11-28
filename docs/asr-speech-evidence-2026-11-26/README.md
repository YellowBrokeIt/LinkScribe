# Whole-recording speech evidence: bounded ASR regression

The isolated candidate rejected the known noise hallucination while preserving
all four real speech outputs. The production baseline completed seven cases
with six expected outcomes; the candidate completed the same seven with seven
expected outcomes. This is a fixed-seed development comparison, not a general
noise-rejection or transcription-accuracy claim.

The base is published commit `2760679cdcd5bf2fdd0f18589e821a89d2bd9b90`.
The candidate changes only the recognizer's whole-recording acceptance rule and
its tests. Its actual app.py SHA-256 was
`86d9765a3e03d08953cbd118ee921eef8e630f4b61fc3e7c38de04adae279955`;
the base was
`41386cfc78938c8d8a03837e02be7ed4a7a53cbc5525947a73da651304d8c671`.
Later integration with other application changes requires its own checks.

## What changed

The candidate sends the identical complete decoded audio to ordinary Faster
Whisper, with audio prefiltering still disabled. It uses the decoder's existing
0.6 no-speech threshold explicitly in both the request and an aggregate check.
Only when **every nonblank returned segment** has a finite score above that
threshold does it ask the bundled Silero detector whether any speech exists
anywhere in the complete recording. Zero intervals rejects the entire result
before saving. One interval preserves every original segment and word time.
The check never crops audio, removes individual segments, or rewrites text.

A detector failure produces a specific cannot-verify error. The earlier exact
digital-zero and decoded-duration checks remain intact. A score below the
threshold or a Silero interval is supporting model evidence, not a guarantee
that the recognized words are correct. Missing/nonfinite scores do not establish
the all-high predicate.

## Actual paired results

| Input | Baseline | Candidate | What the candidate actually did |
|---|---|---|---|
| 32-second exact-zero WAV | Correct rejection | Correct rejection | No recognizer inference or Silero call |
| Identical 32-second deterministic white noise from hosted QA | Incorrectly saved text | Correct rejection | Full ASR followed by one full-recording Silero call with zero intervals |
| Predeclared 16-second owned 440 Hz tone | Correct rejection | Correct rejection | ASR returned no segments; new guard was not exercised |
| Original native Greek clip | Saved | Saved unchanged | ASR supplied supporting evidence; no Silero call |
| Complete Greek clip at −20 dB | Saved | Saved unchanged | ASR supplied supporting evidence; no Silero call |
| Original native English clip | Saved | Saved unchanged | ASR supplied supporting evidence; no Silero call |
| Complete English clip at −20 dB | Saved | Saved unchanged | ASR score was above 0.6, but Silero found speech and preserved the whole transcript |

Every raw ASR segment, score and timestamp was exactly identical between the
two completed arms. The four positive saved segment lists also match exactly.
Only the noise hallucination's persistence changed. The same actual input array,
shape, sample count and PCM hash were observed at decoding, ASR and the separate
speech check.

The white-noise decoder produced ten repeated Georgian characters in a
30–32-second segment. Its no-speech score was **0.8953**, while its average log
probability was **−0.4230**, and its recorded temperature was **0.0**. This is a
concrete counterexample to assuming that disabling sampled fallback alone would
remove noise hallucinations. The candidate's Silero result was empty. The job
returned the exact no-words error, saved no SQLite record, returned 404 for all
five library exports, and cleaned the input.

The quiet English recording is the useful counterexample to rejecting solely on
the ASR score: its no-speech value was **0.6520**, although it contained
recorded speech. Silero returned the interval **14,592–104,640 samples** at
16 kHz. The candidate retained the complete original transcript, including its
unchanged timestamps and all exports. The Greek and English controls remain
machine drafts; spelling/recognition errors in the Greek output were preserved,
not corrected or counted as semantic approval.

## Reproducibility and evidence

The seven-case [fixture manifest](fixtures.json) was frozen before inference.
The Greek/English sources are the first respective clips in the existing FLEURS
development manifest, licensed CC BY 4.0. Quiet variants multiply every decoded
float32 sample by 0.1 and retain the full recording. The noise and tone are owned
generated data. References were retained for inspection and never supplied to
the recognizer. The new tone was fixed before any candidate result was inspected.

Both complete arms used the actual app upload route, default Small/Auto options,
private databases, actual CPU inference and production exporters. Both set the
CTranslate2 RNG seed to 1729 on the recognition worker before each case. This
declared QA setting differs from the ordinary unseeded production path and does
not promise bitwise reproducibility on every machine.

The unchanged production resolver returned Small snapshot
`536b0662742c02347bc0e980a01041f333bce120`. All four model files were hashed and
checked against the fixed [model provenance](model-provenance.json) before model
construction; model.bin SHA-256 was
`3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.
Both arms used Faster Whisper 1.2.1, CTranslate2 4.9.1, PyAV 16.1.0, ONNX Runtime
1.32.0, Hugging Face Hub 2.5.0 and socksio 1.0.0, with the cache offline and
telemetry opt-outs enabled. Installed inference-source hashes are in each report.

The first baseline attempt encountered a missing optional socksio dependency
before model inference on its nonzero inputs. It remains intact under
`raw/base-actual/`. The rerun used the existing speaker-QA interpreter that already
contained socksio; no package, proxy, certificate or TLS setting was changed.
This preparation failure is not counted as a model-quality result.

Directly reviewable reports and complete raw packages are retained:

- [Baseline report](raw/base-actual-supported-runtime/report.json) and
  [complete baseline package](raw/base-actual-supported-runtime.zip).
- [Candidate report](raw/candidate-actual-supported-runtime/report.json) and
  [complete candidate package](raw/candidate-actual-supported-runtime.zip).
- [Initial setup-failure report](raw/base-actual/report.json) and
  [complete failed-attempt package](raw/base-actual.zip).
- [Exact comparison](comparison.json), [assistant review](assistant-review.json),
  [candidate patch](whole-recording-guard.patch), and [patch manifest](patch-manifest.json).
- [Frozen plan](PLAN.md), [fixture preparation script](prepare.py), and
  [comparison harness](run_comparison_arm.py).

Packages contain the original SQLite databases, saved records, all generated
exports, job files and exact executed harnesses. The baseline database has five
rows including the hallucination; the candidate has the four positive speech
rows. These counts and exact segment equality were checked independently using
new read-only SQLite connections. Raw copies are byte-identical. No source audio
or model weights are packaged. [Artifact provenance](artifact-provenance.json)
and [file manifest](manifest.json) record the checksums.

## Remaining checks

The unseeded hosted run must still verify the complete licensed film, recovered
late dialogue, actual noise rejection, mixed batch, exports and restart. Earlier
tail excerpts deliberately existed only in RAM, so they were unavailable for
this local comparison. The new hosted observer should distinguish a whole-audio
corroboration call from ASR VAD filtering and capture the actual model revision
and hashes.

This policy can still retain hallucinations within a recording that contains
speech, and it may reject very quiet recordings if both models miss the speech.
Two negative fixtures and two attenuated clips cannot bound those risks for all
recordings. The 43 focused synthetic tests establish the intended code boundary;
the actual results above establish only this fixed, disclosed regression sample.

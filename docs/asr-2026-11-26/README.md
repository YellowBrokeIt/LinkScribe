# Archived ASR evidence — 26 November 2026

These are sanitized copies of the native-speech QA evidence. **Existing report,
manifest and source-report checksum fields identify the original raw files.**
The exact original and archived SHA-256 values are mapped in
`artifact-index.json`; sanitized files necessarily have different hashes.

Only documentation, manifests, provenance, review, reports and the confidence
probe source are included. Audio, model weights/caches, SQLite stores, generated
export directories and raw dataset-viewer snapshots are excluded. Machine-local
cache/extraction paths and any signed asset URL parameters are removed. Exact
source references, raw hypotheses, judgments and measured results are retained.

The manifests retain public dataset URLs, source-row identifiers and audio
SHA-256 values so the licensed clips can be obtained and verified separately.
Paths in reproduction commands are placeholders for a separate QA workspace.
The confidence probe is preserved for provenance; use a separate output directory
for another run rather than overwriting the archived evidence.

---

# Native speech integration and quality evidence

This directory contains an opt-in diagnostic check of LinkScribe's real local
speech recognition workflow. It uses recorded native speech from Google FLEURS,
not text-to-speech or mocked recognition. The repository harness is
`tests/smoke_real_asr_quality.py`.

## What was checked

Every reported case goes through the actual FastAPI upload endpoint, PyAV media
validation, faster-whisper recognition, isolated SQLite persistence, and TXT,
SRT, VTT, JSON and ZIP downloads. The harness verifies exact stored segments and
export payloads, finite ordered timestamps, removal of the uploaded temporary
audio, library access after in-memory job eviction, and a separate interpreter's
read of the SQLite records. It does not edit recognition outputs.

Structural success does not certify transcript meaning. `assistant-review.json`
contains separate assistant review against the official dataset references; it
does not claim independent human listening validation. No reference words,
names or expected answers are passed to Whisper.

## Fixtures and provenance

- `fixtures.json`: five Greek and three English clips, 52.44 seconds in total.
  These were fixed before the first small-model run. They are now development
  cases because their observed errors inform model selection.
- `derived-fixtures.json`: all five Greek clips concatenated in their original
  order with 0.75 seconds of silence between them, 36.84 seconds in total. This
  was created after the first run to exercise multiple subtitle cues. PyAV
  rewrapped the mono source samples in a dual-mono float32 WAV. It is technical
  regression coverage, not an additional independent accuracy sample.
- `fresh-fixtures.json`: five new Greek and three new English clips, 76.58
  seconds in total. All source sentence IDs differ from development and from
  one another. Selection was frozen before inference on these clips and before
  the selector inspected Turbo's development outputs. The test-preview API
  returned HTTP 500, so previously unselected validation-split rows were used.
  The manifest remains unchanged after freezing.
- `audio/`: exact downloaded dataset-viewer renditions, identified by SHA-256
  in the manifests; the derived recording is explicitly identified separately.
- `model-provenance.json`: original default `small` model snapshot and file
  hashes. `model-provenance-large-v3-turbo.json` records the larger candidate.

The dataset revision is `70bb2e84b976b7e960aa89f1c648e09c59f894dd`. Audio is
unaltered except for the explicitly described derived recording. These are
purposively selected short read-speech examples, not a representative benchmark
of conversation, long recordings, background noise or all Greek/English accents.

### Attribution and license

FLEURS: *Few-shot Learning Evaluation of Universal Representations of Speech*,
Alexis Conneau and collaborators, Google Research, 2022. Dataset distribution:
[google/fleurs](https://huggingface.co/datasets/google/fleurs), licensed under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The [maintainer's license clarification](https://huggingface.co/datasets/google/fleurs/discussions/2)
confirms the license. The [Google Research publication page](https://research.google/pubs/fleurs-few-shot-learning-evaluation-of-universal-representations-of-speech/)
provides the original paper. Preserve this attribution when redistributing the
selected audio or references, and identify the derived recording as changed.

Raw dataset API snapshots are preparation evidence. Public artifacts should use
the sanitized provenance URLs in the manifests, which omit signed asset queries.

## Current results

| Run | Integrated structural result | Assistant semantic review |
| --- | --- | --- |
| `small-result.json` | 8/8 pass; default model form field omitted | 2 acceptable, 3 minor issues, 3 major errors |
| `small-derived-result.json` | 1/1 pass; five ordered recognition segments | Technical coverage only; substantial word errors remain |
| `turbo-development-result.json` | 8/8 pass; explicit `large-v3-turbo` | 3 acceptable, 3 minor issues, 2 major errors |
| `turbo-fresh-auto-result.json` | 8/8 pass; explicit Turbo, language field omitted (Auto) | 5 acceptable, 2 minor issues, 1 major error |
| `small-development-rss-replay.json` | 8/8 pass; default Small, explicit language | Same hypotheses as original Small run; RSS now measured |

The initial small and Turbo runs both supplied the fixture language (`el` or
`en`). They do not demonstrate the app's default automatic language detection.
Turbo reduced Greek word errors and restored a concessive relationship, while
proper-name/domain-content errors remained. Numeric words versus digits,
contractions, accepted Greek spellings and transliterations can inflate literal
WER without changing meaning; the review explains these cases.

Turbo's observed upload-to-export elapsed time was 49.461 seconds for 52.44
seconds of audio, including initial model loading. Its process peak RSS was
1,762,025,472 bytes (about 1.64 GiB). This is not a controlled speed benchmark or
a whole-machine memory measurement; any concurrent translation model is excluded.
Small's first run took 18.182 seconds without RSS instrumentation. Its later
development replay took 19.956 seconds and peaked at 694,067,200 bytes (about
0.646 GiB), with identical hypotheses. The fresh Auto/Turbo run took 98.525
seconds for 76.58 seconds of new audio and peaked at 1,776,443,392 bytes (about
1.654 GiB). Input lengths, language mode, source version and concurrent workload
differ, so these observations do not isolate every cause of runtime differences.

The fresh Auto run detected all eight languages correctly. It preserves ordinary
speech, the six-mile value, the 1767 date and the tap-water prohibition. One
material qualifier is damaged: Greek ενδέχεται (may/might) becomes αντέχεται.
This is evidence for a useful editable draft, with a visible review expectation,
and does not establish unattended faithful transcription.

The first three runs predated explicit ONNX Runtime telemetry opt-outs. They
used `HF_HUB_OFFLINE=1`, but no network capture was performed, so those reports
are not whole-process privacy validation. The current harness sets
`ORT_DISABLE_TELEMETRY=1` and `HF_HUB_DISABLE_TELEMETRY=1` before ML imports and
calls `onnxruntime.disable_telemetry_events()` before the VAD session can start.
The fresh run and the Small memory replay record all three controls explicitly.

### Confidence probe

`turbo-confidence-diagnostic.json` is a separate postselection replay of two
material-error examples and two accurate controls. Word timestamps were enabled
to expose actual word probabilities; all four texts matched their production
outputs exactly. It is not a calibration or additional fresh-validation set.

The damaged Greek qualifier has word probability 0.77983, while the incorrectly
spelled μολύθηκαν has 0.93635. Correctly rendered Dr./Moll scores are lower than
the erroneous qualifier. The damaged Greek sentence also has a less negative
average log probability (-0.0692) than the accurate English control (-0.1572).
The severe English name/content error has lower confidence (-0.5968), showing
that scores can help with some cases while missing others. Four selected probes
do not justify a production threshold or an accuracy percentage. Keep review of
names, amounts, negation and uncertainty visible even when scores are high.

## Reproduction

Use the project virtual environment and an isolated cache. Download the selected
model once, then use an offline recognition run. Do not overwrite an existing
evidence report; the harness requires a new output filename.

```bash
HF_HOME=/path/to/asr-qa/hf-cache HF_HUB_DISABLE_TELEMETRY=1 \
  .venv/bin/python -c "from faster_whisper.utils import download_model; download_model('large-v3-turbo')"

HF_HOME=/path/to/asr-qa/hf-cache HF_HUB_OFFLINE=1 \
ORT_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_TELEMETRY=1 LINKSCRIBE_DEVICE=cpu \
  .venv/bin/python tests/smoke_real_asr_quality.py \
  --manifest /path/to/asr-qa/fixtures.json \
  --model large-v3-turbo \
  --model-provenance /path/to/asr-qa/model-provenance-large-v3-turbo.json \
  --language-mode explicit \
  --output /path/to/asr-qa/turbo-reproduction.json
```

Omit `--model` to exercise the actual default model. Use `--language-mode auto`
to omit the language form field and exercise the app's default detection; the
harness then verifies the detected language against the fixture metadata. Both
choices are recorded. Model identity is never silently substituted under the
name `small`.

Reports retain source-file hashes before and after execution, model revision and
weight hashes, runtime versions, raw hypotheses, exact segments, diagnostic word
edits, and export fingerprints. If source files change during a run, the harness
returns failure and the hashes must be reconciled before making an exact-source
validation claim. The recorded fresh run followed the parent's candidate and
configuration freeze; later reuse is regression or diagnostic work, not another
untouched validation.

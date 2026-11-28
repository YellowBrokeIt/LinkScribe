# Prepared Parakeet CPU development screen

**Preparation state: no Parakeet model has been initialized and no recognition
has run.** The coordinator must release the shared model slot and the prepared
contract must receive its pre-output review before execution. The immutable
[plan](plan.json) records this preparation state; eventual execution and raw
outputs belong in separate result files.

This is a recognizer-only screen of a different acoustic architecture. It uses
the same eight previously exposed native-speech development clips from
[26 November](../asr-2026-11-26/README.md), preserving all original references
and semantic criteria. It does not exercise the LinkScribe application, exports,
storage, provider acquisition, speakers, a full film, or a fresh validation set.
Core application code and requirements are unchanged by this experiment.

## Exact model and isolated runtime

The model is NVIDIA's
[Parakeet-TDT-0.6B-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), a
FastConformer/token-duration-transducer recognizer supporting Greek and English
among its declared languages. The CPU screen uses Ilya Stupakov's public
[ONNX conversion](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx)
at immutable revision `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce`.

| File | Bytes | SHA-256 |
|---|---:|---|
| `encoder-model.int8.onnx` | 652,183,999 | `6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09` |
| `decoder_joint-model.int8.onnx` | 18,202,004 | `eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70` |
| `vocab.txt` | 93,939 | `d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d` |
| `config.json` | 97 | `666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466` |

The separately created `parakeet-screen-venv` pins `onnx-asr==0.12.0`,
`onnxruntime==1.32.0`, `numpy==2.5.5`, `huggingface-hub==2.5.0` and
`socksio==1.0.0`. Its complete installed versions are retained in
[installed-packages.txt](installed-packages.txt); `pip check` passed.
[runtime-provenance.json](runtime-provenance.json) records installed source/data
and native runtime hashes. The executable plan pins these files, every model
file, original WAV and decoded input array, plus the helper itself.

The CPU frontend is the pinned package's normal NumPy
`NemoPreprocessorNumpy` with 128 mel features, its packaged filter bank and one
preprocessing worker. The separately downloaded `nemo128.onnx` file is retained
by digest but is not selected by this NumPy configuration. Model-prescribed
feature processing remains unchanged; no user-defined denoising, VAD, crop,
volume scaling or speech-selection rule is added.

### Attribution and licenses

NVIDIA publishes the base model under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The conversion is attributed to Ilya Stupakov and retains CC BY 4.0, as shown in
the unchanged [conversion model card](model-card.md). This screen uses the
already-published int8 conversion; it does not fine-tune or modify model weights.
The `onnx-asr` runtime is separately MIT-licensed. Preserve the model and runtime
attributions and their applicable license notices when redistributing them.

The audio/reference source is *FLEURS: Few-shot Learning Evaluation of Universal
Representations of Speech*, Alexis Conneau and collaborators, Google Research,
2022, distributed as [google/fleurs](https://huggingface.co/datasets/google/fleurs)
under CC BY 4.0. The original dataset revision is
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`. No selected recording is edited.

## Full audio and original semantic criteria

All eight recovered WAVs match the original archived byte hashes. The unchanged
[development manifest](development-fixtures-original.json) contains their
source-row identities, original audio digests, references and criteria. The
[semantic review contract](semantic-criteria.json) copies the original criteria
and classification definitions; none is relaxed for Parakeet.

| Exposed case | Language | Complete duration | Original semantic focus |
|---|---|---:|---|
| Validation row 2, sentence 1528 | Greek | 6.66 s | Family camping provision and young children |
| Validation row 5, sentence 1515 | Greek | 6.00 s | Fifth council, four years and Μαρτελί |
| Validation row 6, sentence 1577 | Greek | 4.20 s | Both negative propositions |
| Validation row 7, sentence 1598 | Greek | 6.96 s | Three people, collision and nobody injured |
| Validation row 11, sentence 1590 | Greek | 10.02 s | Number One, Manta and the negated description |
| Validation row 0, sentence 1548 | English | 6.54 s | Distant phone-call condition and satellite claim |
| Validation row 2, sentence 1510 | English | 7.92 s | U.N., fund, affected countries and intended help |
| Validation row 3, sentence 1578 | English | 4.14 s | Lakkha Singh, leading role and bhajans |

Total input is **52.44 seconds**. [input-arrays.json](input-arrays.json) binds each
complete mono float32 array to its original WAV. Audio-only preparation used
the unchanged `faster_whisper.audio.decode_audio(..., sampling_rate=16000)`
conversion also used by prior application runs. This decoder performs its usual
sample-format conversion; no Whisper model or transcript participates. The full
sample count must equal the original dataset count, and every array's SHA-256,
shape and duration are frozen before Parakeet sees it.

During recognition the observer checks the exact full array again at the
Parakeet frontend, with batch size one and no omitted samples. Normal feature
shapes and digests are recorded. It also verifies that the original input array
remains unchanged after recognition. There is no VAD wrapper or chunking in this
short-speech screen.

### Language, decoding and timestamp behavior

The pinned runtime's source-language option applies to Whisper/Canary, and its
target-language option applies to Canary. Neither is a Parakeet TDT control.
The helper therefore supplies **no source or target language argument**. Greek
or English is expected-language metadata for later review only. The runtime
does not return a detected-language field, so no such field is invented.

The unmodified TDT decoder uses its normal greedy token and duration choices.
No prompt, glossary, reference text, Whisper hypothesis, token override, text
correction, confidence deletion or language-model rescoring is supplied.
References and prior hypotheses remain evaluator data outside the recognizer.

The `.with_timestamps()` interface retains token strings, emission timestamps
and log probabilities. Its timestamp is the emitted encoder-frame index times
`0.01 * 8 = 0.08` seconds. These are token emission times, without independently
validated word boundaries or word-end times. The helper retains the original
token IDs, frame indices and unmodified returned result. It does not manufacture
word intervals, forced alignment or subtitle cues. Structural checks require
matching field counts, finite values and monotone timestamps within the recording
with at most one encoder-frame tolerance. They do not establish timing accuracy.

## One bounded execution after review

The [helper](run_screen.py) validates identities by default and constructs models
only in a fresh worker when explicitly invoked with `--execute` after the model
slot is released. A new results directory is required, preventing accidental
reuse of the attempt. The intended single worker initializes the model once,
then processes the eight complete clips sequentially, once each.

The worker is pinned to four available logical CPU cores. Every ONNX session
must actually report CPU execution, four intra-op threads and one inter-op
thread, with sequential graph execution. NumPy/BLAS uses one thread and the
frontend uses one worker. The QA seed is fixed at 1729 before model construction.

Bounds fixed before output:

- **90 seconds** for initialization/startup.
- **30 seconds** per complete clip.
- **300 seconds** for the whole worker.
- **2.5 GiB** observed process-group RSS, sampled every 0.1 second, with recorded
  process peak RSS checked as well.

On a limit or structural failure, stop and preserve completed outputs; do not
retry or change settings after seeing the text. The controller terminates only
its owned process group and records the reason. Sampled RSS is not a guarantee
about unsampled aggregate peaks or whole-machine memory.

Inference uses only the existing local model directory. `HF_HUB_OFFLINE=1`,
Hugging Face/ONNX telemetry opt-out variables and `DO_NOT_TRACK=1` are set before
ML imports. `onnxruntime.disable_telemetry_events()` is called before any session
construction. The worker also rejects Python DNS/socket-connect attempts. These
controls are recorded; this is not a packet-capture privacy claim.

After completion, review all eight exact raw hypotheses using the original
semantic criteria, retaining names, numerical facts, negation and qualifications.
The prior Small comparison is specifically the completed
[VAD-off replay](../asr-2026-11-26/small-vad-off-regression-replay.json), interpreted
by its [original review](../asr-2026-11-26/small-vad-off-review.json). The similarly
named `small-vad-off-regression.json` records the earlier failed SOCKS setup
attempt and is retained only as failure context. The successful prior
Small/Turbo runs used explicit source-language requests and the normal
app pipeline, whereas this prototype uses Parakeet's native recognition path;
resource figures are not a controlled backend benchmark. No model adoption,
general accuracy claim or app workflow approval follows from structural passes
or aggregate word-edit counts. Full-film work is a separate decision only if
this bounded screen warrants it.

## Preserved preparation observations

[preparation-downloads.json](preparation-downloads.json) preserves the first
attempt: every pinned model file downloaded and verified, but an archived
unsigned dataset-viewer asset URL returned HTTP 403. The earlier archive had
intentionally stripped temporary URL signatures. The separate
[fixture recovery](fixture-recovery.json) obtained fresh URLs from the same
public rows API, required the same row/recording identities and verified all
original WAV hashes. No authentication or proxy changes, alternate recording,
or fresh fixture selection was used.

The audio-only decoder import emitted a local UCX VFS-socket warning in this
environment; extraction still completed with all eight expected sample counts.
The warning is recorded in [preparation-notes.json](preparation-notes.json).
No ASR model or ONNX session was constructed by that preparation step.

Audio, model weights and the isolated virtual environment remain outside the
repository. The evidence files identify them by immutable paths and digests.

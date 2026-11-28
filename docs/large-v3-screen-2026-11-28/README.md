# Full large-v3 hosted development screen — pre-output plan

This is one authorized test of the **full** `Systran/faster-whisper-large-v3` model, not the previously tested Turbo variant. It uses the same eight already exposed native English/Greek development recordings and original meaning criteria. No new source, held-out validation, production default or application model option is introduced. No model weights are downloaded or initialized locally.

## Why this candidate and exact source

The tested Whisper timing/silence-policy alternatives lost real speech; production returned to its earlier conditional-word policy. The isolated Parakeet int8 and Qwen native FP32 screens also failed original meaning criteria. Full large-v3 has not been run here. It is a different model-size candidate within the already used native production runtime, preserving the existing native segment-timestamp and long-form decoding route rather than adding an unsupported Greek aligner.

The frozen source is [`Systran/faster-whisper-large-v3`](https://huggingface.co/Systran/faster-whisper-large-v3/tree/edaa852ec7e145841d8ffdb056a99866b5f0a478), revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`. The public, ungated model card declares MIT. Published `model.bin` is 3,087,284,237 bytes, SHA256 `69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1`. Stored weights are FP16; native loading requests CPU `int8`. The hosted worker verifies every downloaded model and companion file before loading it. [Model identities](model-files.json) explicitly distinguish the published LFS weight identity from actually downloaded and independently hashed small companions; there has been no local weight download.

The seven direct native runtime versions are the versions already installed and used by this project's ASR work: faster-whisper 1.2.1, CTranslate2 4.9.1, av 16.1.0, ONNXRuntime 1.32.0, NumPy 2.5.5, huggingface-hub 2.5.0 and tokenizers 0.23.3. [The independent runtime review](runtime-pin-review.json) binds official Python 3.12/Linux wheels and dependency constraints. Requirements use exact wheel URLs and SHA256 fragments; the complete actual pip resolution and installation report will be artifacts.

## Unchanged production recognition policy

The helper extracts and executes the current `app.py::_recognize` function unchanged in an isolated namespace, with the pinned native model instance supplied by its model factory. It does not import or launch the UI/server. [production-policy.json](production-policy.json) contains the exact observed function text, its canonical AST identity and literal numeric constants. Runtime validation checks that narrow AST identity and constants; the full module digest records provenance without making unrelated app edits invalidate this experiment. All ordinary plan-bound file identities remain exact byte hashes, with explicit LF checkout rules.

The actual call is `_recognize(original_wav, "auto", "large-v3", word_timestamps=False)`. The original WAV is decoded by faster-whisper exactly as production does. Observers check the complete float32, mono, 16 kHz PCM array both at `transcribe` entry and at the native frontend against the already frozen full-array hash. No crop, VAD preprocessing, amplitude change, resampling change, sample selection or replacement input is allowed.

The production request remains auto language, beam 5, VAD off, no-speech threshold 0.6 and `condition_on_previous_text=False`. The conditional `word_timestamps` option is omitted, leaving its native default false. The usual native temperature fallback `[0, .2, .4, .6, .8, 1]`, compression/log-probability thresholds and suppression rules remain intact. Initial prompt, prefix, hotwords, forced language, translation task, hallucination-silence threshold and word alignment are absent. The production exact-zero and all-output-no-speech corroboration branches remain unchanged; the latter can consult the packaged Silero model without trimming individual segments. Seed 1729 is declared before seeing results, and case order is unchanged.

## Bounded hosted execution and retained evidence

The isolated workflow is limited to `qa/large-v3-*` push branches or explicit dispatch. It uses `contents: read`, checkout without persisted credentials, no secrets, no model cache reuse and no external write operation. The controller sanitizes its worker environment; offline Hub and telemetry flags are set before ML imports. Model loading is from verified local files. A Python network audit hook rejects connect/address-resolution attempts during initialization and inference.

- Exactly one Whisper initialization and one production recognition attempt per clip, with no automatic retry.
- CPU `int8`, one native model worker, and up to four threads bounded by available CPU affinity. Constructor values, actual CPU compute type, native worker count and affinity are recorded. Thread-count settings are not mislabeled as a complete operating-system thread census.
- 6 GiB owned-process-group RSS limit, sampled every 100 ms; 180 seconds for startup, 180 seconds per clip, 1,800 seconds total worker time.
- Retained `resource-samples.jsonl`, exact sampled peak, worker OS high-water RSS, elapsed times and owned-process cleanup records. A sampled or recorded violation rejects the run; no live owned process group may remain afterward. Sampling is a measured stop policy, not an assertion of continuous kernel-enforced memory containment.
- Every CTranslate2 decoding/fallback call records actual prompt token IDs, generation arguments, full returned sequences, token strings, scores and no-speech probability. Native segment text, tokens, confidence/repetition data and segment times are retained before production whitespace trimming. The complete production result is retained separately.
- Actual effective transcription arguments and native `TranscriptionInfo` are retained before and after full iterator exhaustion. Full source-array identity, single frontend use, native iteration completion, text/token consistency and absence of a sequence reaching the native length cap are checked. CTranslate2 does not promise a terminal EOS token in returned sequences, so this is not called an EOS proof.
- Native segment times must be finite, positive-duration and ordered by start and end. Overruns beyond the original recording's duration are recorded for review. There is no replacement timing, word-time fabrication, subtitle-accuracy claim or speaker approval.

The controller and input preparation reuse the previously reviewed Qwen helper's hash verification, exact WAV/PCM recovery, model download and owned-group cleanup utilities without changing them. The native worker is dedicated to the production Whisper function. The new controller retains the RSS series that the Qwen artifact lacked. All success, rejection, partial progress and setup error files are uploaded with `always()`; model weights and runtime directories are excluded.

## Decision after the one actual run

Independent reviewers will grade all eight raw native hypotheses against the unchanged original criteria, including negations, names, numbers and specific relationships. A successful workflow is only protocol/resource evidence. Any major meaning loss blocks promotion; an eight-clip pass would justify a separately planned broader check, not establish full-film, speaker, subtitle or release readiness.

The FLEURS source remains the original CC BY 4.0 Google/Conneau et al. dataset revision and URLs already bound by the project fixture inventory. The eight clips are development material; no held-out set is opened here. The current plan contains no candidate output.

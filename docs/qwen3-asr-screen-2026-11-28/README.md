# Qwen3-ASR native CPU development screen — prepared, not yet executed

This prepares one hosted recognition screen of the public native
[`Qwen/Qwen3-ASR-0.6B-hf`](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf/tree/7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c)
checkpoint. It is a recognizer prototype on the same eight already exposed
English/Greek recordings. There is no candidate accuracy result, application
integration, fresh validation, or release approval in this preparation checkpoint.
The application's existing ASR policy and dependencies are unchanged.

The preceding [Parakeet experiments](../parakeet-screen-2026-11-28/README.md)
preserved important semantic errors under both tested frontends. Qwen is a
different public multilingual recognizer worth one bounded measurement, rather
than another Whisper threshold adjustment. Greek recognition is advertised in
the [native model documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_asr).
The same documentation's forced-alignment language subset excludes Greek, so this
screen produces text without claiming segment or word timestamps.

## Frozen execution contract

The machine-readable [plan](plan.json) binds the helper, workflow, model inventory,
runtime requirements, original recordings, complete PCM identities and unchanged
semantic criteria. The [model inventory](model-files.json) distinguishes actual
small-file hashes from the publisher's large-file LFS identities. Hosted download
must verify every actual byte size and SHA256 before loading anything.

| Item | Declared value |
| --- | --- |
| Model | Native Qwen3-ASR-0.6B-hf, revision `7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c` |
| Weight file | 1,564,928,088 bytes; SHA256 `d3f212dd20abecd315d830bc54ae3865e56ebfc3276484e57b771288ba27fd35` |
| Runtime | Python 3.12; official CPU Torch `2.15.0+cpu`; native Transformers `5.13.0`; exact wheel hashes |
| Numerics | All floating parameters FP32, eager attention, CPU autocast disabled |
| Inputs | Eight complete original 16 kHz recordings, 52.44 seconds total; exact WAV and full float32 PCM hashes |
| Guidance | Automatic source-language identification; native audio-only request; no reference, language hint, glossary, custom prompt or correction |
| Decoder | Greedy, one beam, publisher maximum 512 new tokens; native EOS IDs `151643` and `151645` |
| Execution | One model initialization and one recognition attempt per clip; fixed QA seed 1729 |
| CPU | At most four CPUs from the runner's actual affinity; one Torch inter-op thread |
| Limits | 6 GiB owned process-group RSS; 180 seconds initialization, 90 seconds per clip, 900 seconds worker total |
| Failure handling | Stop on runtime/identity/resource failure, retain partial token stream and logs; no automatic retry or fallback |

The monitor samples the owned process group every 100 ms and terminates only that
group when a limit is observed. The worker also checks its recorded peak RSS and
completed timings, so a completed operation cannot pass merely because it finished
between controller polls. These are monitored limits with termination grace,
not a claim of a kernel-enforced memory allocation ceiling.

The [runtime provenance](runtime-metadata-provenance.json) records the inspected
primary metadata. The selected native Transformers source is pinned to commit
`6af945f436d85f2b0c5dff9b14feccd27b1d470b`. An initial metadata lookup for
`tokenizers==0.23.0` returned HTTP 404; the prepared runtime uses the existing
`0.22.2` release within Transformers' declared bounds. No installation or inference
was attempted with the unavailable version. Direct recognition dependencies are
pinned; the actual transitive environment is retained by the hosted pip report,
`pip freeze`, and `pip check`.

## What the evidence must establish

The helper observes the exact full waveform reaching native feature extraction.
There is no VAD, trimming, audio chunk selection, or cached-feature substitution.
It checks the full mel frame count, right-padding mask and audio placeholder count,
then binds those same features and mask to the actual native audio encoder call.
Original recordings and decoded arrays are retained with the hosted evidence.

For every attempt it preserves the native rendered request, prompt token IDs,
incrementally streamed tokens, complete returned sequence, generated token strings,
raw decoded output and separate native parsed output. It requires the original
prefix, identical streamed/returned IDs and a terminal native EOS within the
declared token budget. A response stopped by the token limit without EOS fails.

The native parser includes repetition repair. Independent semantic review must
use `raw_transcript_without_repetition_repair`; the parsed result and whether it
changed the raw text are retained separately. The original
[eight semantic criteria](../parakeet-screen-2026-11-28/semantic-criteria.json)
cover every reference, including names, counts, negation and relationships.
Successful loading, plausible output or a low edit distance cannot substitute for
that review. The completed Small comparator is
[`small-vad-off-regression-replay.json`](../asr-2026-11-26/small-vad-off-regression-replay.json);
the earlier report without `-replay` contains setup failures and is context only.

## Hosted workflow and local preparation

The [dedicated workflow](../../.github/workflows/qwen3-asr-candidate-qa.yml) runs on
the development branch when its declared execution inputs change, or by manual
dispatch. It has `contents: read`, does not persist checkout credentials, and passes
no credentials or secrets to recognition. It installs into a fresh runner-local
environment and downloads only public pinned files. The model worker then uses
verified local files with `trust_remote_code=False`, offline/telemetry settings,
a sanitized environment and Python socket audit denial.

The final artifact is named `qwen3-asr-native-fp32-<commit>`. It includes preflight,
installation, input recovery, model-file verification, raw recognition, partial
tokens, process-resource records and logs even if a later step fails. Weight files
and the runtime environment remain outside the uploaded evidence directory.
Updating result documentation alone does not automatically repeat recognition.

Local validation uses only the standard-library helper tests and the existing
audio decoder to verify all eight original retained WAVs against their prior full
PCM hashes. No Qwen weights, large tokenizer JSON, Torch wheel or Transformers
wheel were downloaded locally, and no local Qwen model was constructed or run.
The [local input record](local-input-preparation.json) and
[non-model validation record](non-model-validation.json) state that scope explicitly.

Pre-execution review found one real harness defect: an exited worker leader could
leave a live child in its owned process group. The
[original cleanup probe](pre-review-cleanup-probe.json),
[initial helper](pre-review-helper.py) and [initial plan](pre-review-plan.json)
are preserved unchanged. The current helper terminates and checks the whole owned
group even after leader exit, and its added regression reproduces that lifecycle.
All 14 non-model tests now pass. Scoped repository attributes preserve LF for the
plan-bound byte identities on Windows as well as Linux and macOS.
The [final independent contract review](independent-contract-review.json) and
[corrected cleanup probe](independent-cleanup-corrected-probe.json) found no remaining
material pre-execution blocker. This approves the prepared measurement contract,
without asserting that Qwen has loaded, stayed within resources or produced an
acceptable transcript. The [manifest](manifest.json) freezes this preparation state.

## Attribution and scope

Qwen3-ASR's model metadata declares Apache-2.0; the exact publisher model card is
included in the hosted pinned inventory. The source recordings are the Google
FLEURS dataset by Conneau and colleagues (2022), revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`, under
[CC BY 4.0](https://huggingface.co/datasets/google/fleurs).
Their original dataset identifiers, references, download provenance and recording
hashes remain in the [original fixture manifest](../asr-2026-11-26/fixtures.json).
This reuses existing development exposure; it does not open fresh validation data
or establish long-audio behavior, provider access, persistence or application UX.

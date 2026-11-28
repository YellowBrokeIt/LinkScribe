# Fidelity questions after the rejected int8 screen

This is primary metadata/source inspection plus the separately authorized
frontend-only comparison. No extra ASR weights or full-precision model were
downloaded for this research. It does not approve a model family or production
change.

## Runtime and exporter compatibility

The installed loader, NeMo decoder and NumPy preprocessing sources match
`onnx-asr` release `v0.12.0`, commit
`b9e0ce0ae3223b3d24ce5a22a5e701a726ca35fc`. That release selects NumPy processing
by default on CPU and supports the recorded NumPy/ONNX Runtime versions in its
package constraints. Its
[NeMo preprocessing tests](https://github.com/istupakov/onnx-asr/blob/b9e0ce0ae3223b3d24ce5a22a5e701a726ca35fc/tests/preprocessors/test_nemo.py)
cover 80/128 features and NumPy/current ONNX implementations against NeMo. Those
tests do not compare every older preprocessor distributed with existing model
repositories.

Static parsing of the existing files, retained in
[onnx-static-metadata.json](onnx-static-metadata.json), found ONNX IR 8/opset 17
and `onnx.quantize` producer metadata for the int8 encoder/decoder. The encoder
contains 77 `ConvInteger` and 217 `MatMulInteger` nodes; the decoder contains
two `com.microsoft::DynamicQuantizeLSTM` nodes and three `MatMulInteger` nodes.
The supplied frontend records OnnxScript 0.3.2/IR 8, while the runtime's current
bundled frontend records OnnxScript 0.7.1/IR 10. These metadata explain file
identity and numerical-path differences; they do not authenticate parity with
the trained model.

The [conversion card](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/tree/8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce)
shows the normal NeMo export route and tokenizer export, but does not record the
exact NeMo/PyTorch versions used. That missing provenance prevents a claim that
the inspected runtime is the one uniquely correct inference implementation.

## The frontend difference is observed and intentional

The [full-array comparison](../frontend-parity/README.md) failed all eight cases
at its predeclared tolerance. The model-supplied older graph uses one additional
valid frame and differs in shared-frame normalization. Current NumPy features
exactly reproduce those recorded during the original int8 recognition.

The maintainer's [25 November 2025 commit](https://github.com/istupakov/onnx-asr/commit/726dd55a74a6223abd333810b2ddc6438e8fe2a0)
explicitly updates preprocessing for NeMo 2.5: reflect padding changes to constant
padding, valid-length calculation loses the added frame, and waveform-length
masking is added. NVIDIA's
[NeMo 2.4 source](https://github.com/NVIDIA/NeMo/blob/v2.4.0/nemo/collections/asr/parts/preprocessing/features.py)
and [NeMo 2.5 source](https://github.com/NVIDIA/NeMo/blob/v2.5.0/nemo/collections/asr/parts/preprocessing/features.py)
confirm these version-dependent behaviors. No dither is applied by either
compared frontend. This is an observed compatibility question, without proof
that the old or current path better preserves these Greek recordings.

The authorized completed diagnostic changed only the frontend, kept the same
published int8 weights, and required no extra weight download. Its
[frozen plan and patch](../legacy-frontend-ablation/README.md) retain the same
eight complete recordings, seed, decoder, CPU settings, original semantic
criteria and limits. No values were tuned to individual clips. The full review
found one restored proposition and a new product-name failure, with four major
errors still present. It remains rejected; the numerical difference alone was
not an acceptable quality fix.

## Quantization remains a separate, unproven explanation

The exact canonical int8 files quantize convolutions and recurrent decoder
operations in addition to matrix multiplications. Another conversion publisher,
[Solda Labs](https://huggingface.co/SoldaLabs/parakeet-tdt-0.6b-v3-onnx-int8-mm),
reports its own 50-clip Italian FLEURS experiment using this same upstream export
revision: clean WER was 2.03% for fp32 and 2.86% for canonical int8; its separately
quantized MatMul-only copy reported 2.03%. This is first-hand, limited Italian
evidence that quantization can affect this export. It is not NVIDIA or the
original converter confirming a Greek defect, and was not reproduced here.

A [discussion on the original conversion](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/discussions/3)
also links another publisher's quantization work. It contains no original
maintainer diagnosis establishing the cause of our cases. The runtime
maintainer's [English/Russian comparison](https://istupakov.github.io/onnx-asr/comparison/)
shows close original/ONNX results on those datasets; it does not certify our
Greek int8 configuration.

A same-export fp32 comparison could isolate quantization after the frontend
question is understood, but is not authorized or executed. Its
[metadata-only inventory](fp32-metadata-only.json) contains exact published
hashes for 2,549,711,919 additional bytes across the encoder graph/external data
and decoder. That publisher reports roughly 2.7 GB RAM for fp32 on its machine;
this is not a measured local limit and does not establish safe operation under
the original 2.5 GiB cap. Disk space must also be rechecked after concurrent
language-model preparation.

## One distinct multilingual alternative researched

The independent [Qwen3-ASR findings](qwen3-asr-findings.md) and
[exact metadata](qwen3-asr-findings.json) identify public, ungated Apache-2.0
`Qwen/Qwen3-ASR-0.6B-hf` with official Greek recognition support and a native
Transformers CPU code path. Native weights are 1,564,928,088 bytes, and FP32
parameters alone occupy approximately 2.915 GiB before runtime/activation
overhead. Actual CPU speed, peak memory and quality have not been measured.

Its official forced aligner excludes Greek. The recognizer's text/language
output therefore cannot be promoted to supported Greek word timestamps. The
native Transformers model and original `qwen-asr` package also use different
runtime registrations; their versions must not be mixed. Short recognition
could be screened under a separately declared resource budget, but it would
leave subtitle timing and full-film processing unresolved.

As a repository-context check, only Small and `large-v3-turbo` completed prior
larger-model experiments here; no full `large-v3` result was found. SYSTRAN's
[full large-v3 conversion](https://huggingface.co/Systran/faster-whisper-large-v3)
is public, declares MIT, and uses the existing CTranslate2/faster-whisper route,
including normal long-form segmentation. Its published `model.bin` is
3,087,284,237 bytes at revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`.
No download or execution was performed. This is a known integration path, not
an accuracy guarantee or a second active model experiment.

[source-index.json](source-index.json) records retrieved primary URLs and hashes.
Small source snapshots remain in the research workspace; the repository keeps
the conclusions, identifiers and actual local evidence without duplicating
upstream source trees or weights.

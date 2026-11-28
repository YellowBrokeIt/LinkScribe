# Qwen3-ASR: bounded metadata and CPU-runtime review

**Conclusion:** `Qwen/Qwen3-ASR-0.6B-hf` is a plausible distinct candidate for a separately declared short CPU transcription screen under the available **6 GiB process cap**. Use a fixed FP32 profile initially. This is a research recommendation, not an executed feasibility result or production approval. No weights, packages or models were downloaded/installed/executed; only small public metadata and source files were retrieved.

## Exact candidate and comparisons

All four queried model repositories are public, ungated and declare Apache-2.0. Metadata was retrieved anonymously. Published hashes identify future downloads; no weight file has been locally verified.

| Official checkpoint | Current immutable revision | Published BF16 weight-file bytes |
|---|---|---:|
| [Qwen/Qwen3-ASR-0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B/tree/5eb144179a02acc5e5ba31e748d22b0cf3e303b0) | `5eb144179a02acc5e5ba31e748d22b0cf3e303b0` | 1,876,091,704 |
| [Qwen/Qwen3-ASR-0.6B-hf](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf/tree/7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c) | `7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c` | 1,564,928,088 |
| [Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B/tree/7278e1e70fe206f11671096ffdd38061171dd6e5) | `7278e1e70fe206f11671096ffdd38061171dd6e5` | 4,698,521,512 |
| [Qwen/Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B/tree/c7cbfc2048c462b0d63a45797104fc9db3ad62b7) | `c7cbfc2048c462b0d63a45797104fc9db3ad62b7` | 1,835,544,544 |

The proposed native 0.6B weight SHA256 is `d3f212dd20abecd315d830bc54ae3865e56ebfc3276484e57b771288ba27fd35`. Its API reports **782,426,112 stored BF16 tensor elements**, versus 938,008,576 in the original package. Native configuration/code tie input and output embeddings; the storage difference is consistent with tied-weight serialization. It is not evidence that the trained model was newly reduced or that the two inference implementations are numerically identical.

## Greek and timestamp limitation

The [publisher card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf) and [native Transformers documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_asr) explicitly support **Greek/el and English/en ASR**, including automatic language detection. The separate forced aligner supports only Chinese, English, Cantonese, French, German, Italian, Japanese, Korean, Portuguese, Russian and Spanish. **Greek is excluded.** The native processor rejects an explicit unsupported alignment language; bypassing that check would not create supported Greek alignment.

The recognizer produces text/language, not native word timestamps. Processing-window offsets could later describe coarse source intervals, but would need a separately reviewed complete chunking strategy. They must not be presented as recognized word boundaries. A successful text-only screen would leave subtitle timing, speaker boundaries and long-film coverage gates unresolved.

## Exact native runtime and CPU precision

The model card requires **Transformers >=5.13.0**. Version **5.13.0** exists; its exact source commit is `6af945f436d85f2b0c5dff9b14feccd27b1d470b`, and wheel SHA256 is `8adbc1d20bd5463cd6876b2eb7cb31971e1065788e7dc6bc12bab597a7c504b7`. The inspected stable source supports eager/SDPA attention and CPU-default feature extraction. It does not require FlashAttention or vLLM for ordinary generation.

Transformers' package metadata declares `torch>=2.4` for its Torch extra; the publisher does **not** require a unique PyTorch commit. A concrete available pin for this Python 3.12/Linux host is **torch 2.15.0+cpu**, `manylinux_2_28_x86_64`, published CPU-wheel SHA256 `0955c7e3446326293f48af18fad67872fa31dee5a36a87690eb9e5be8b465be3`. This pairing has not been installed or validated by this review. The wheel URL and all metadata identities are in `findings.json`.

The original **qwen-asr 0.0.6** package instead pins **Transformers 4.57.6** and registers its original architecture. Keep original-package and native-HF configurations/runtimes separate.

[PyTorch 2.15](https://docs.pytorch.org/docs/2.15/amp.html) documents CPU BF16 autocast for the main convolution, linear, matrix-multiply and SDPA operators, with FP32 behavior for sensitive operations such as STFT. The host reports `avx512_bf16` support. However, no reviewed official Qwen source demonstrates or guarantees this entire model in CPU BF16; its reported speed examples use CUDA/A100. Generic operator support is weaker evidence than an actual model run. [PyTorch's CPU BF16 guidance](https://pytorch.org/blog/empowering-pytorch-on-intel-xeon-scalable-processors-with-bfloat16/) also distinguishes explicit BF16 weights from FP32 weights under autocast: autocast does not automatically halve parameter memory and may retain casts/caches.

**Resource inference:** Native 0.6B stored parameters occupy approximately **2.915 GiB in FP32**, or **1.457 GiB in BF16**, before interpreter, activations, KV cache and load overhead. FP32 therefore has a plausible but unmeasured margin inside 6 GiB. This does not inherit Parakeet's 2.5 GiB cap. A BF16 profile, if chosen, must be frozen as its own numerical experiment rather than used as an automatic fallback. The larger original 1.7B tensors would expand to about 8.752 GiB in FP32 and are not the proposed screen.

## Long audio and evidence capture

At pinned official source `7c6daf77a2421100f5fb066495372c00129d39ff`, the original wrapper splits near **1,200 seconds** without timestamps or **180 seconds** when alignment is requested, using a low-energy cut within a five-second search neighborhood. It keeps chunk offsets and concatenates text; short tails can be padded. These are processing intervals, not speech alignment. The native Transformers feature extractor defaults to `truncation=False`; its 30-second padding setting does not establish automatic long-file transcription. The original wrapper's chunk/merge behavior must not be assumed for the native interface.

For any later authorized screen, use the original complete short development clips, unchanged meaning criteria, no transcript hints/hotwords, one attempt each, fixed CPU/precision/cap, and raw generated token/EOS capture before parsing. Capture the complete waveform and actual feature masks. The original package parser includes repeated-text cleanup, so parsed text alone cannot establish untouched native output. No long-file implementation or alignment workaround is proposed in this research.

## Retained evidence

`findings.json` contains exact revisions, published weight hashes, runtime/package metadata, limitations and every retrieved source URL/hash. The fetch indexes and small official source snapshots are retained alongside it. No candidate output or heldout data was inspected.

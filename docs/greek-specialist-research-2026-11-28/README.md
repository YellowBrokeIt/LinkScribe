# One Greek-specialized model candidate: ILSP Llama-Krikri 8B

## Recommendation

There is one concrete, materially different candidate worth a bounded local
feasibility and development test: **the publisher's Llama-Krikri-8B-Instruct
Q4_K_M GGUF**. It combines a Greek-adapted Llama 3.1 model, Greek vocabulary
expansion and explicit bilingual/translation training. It is not another
unchanged version of the Qwen, Gemma, Hy-MT, Marian or M2M100 profiles already
tested.

The official quantized payload is public and ungated. Its 4.695 GiB file plus
an estimated 0.5 GiB of f16 KV cache at 4096 context leaves about 824 MiB for
remaining processes and runtime buffers under the 6 GiB process limit. That is
plausible enough to measure, not an observed memory pass. Four-thread latency,
actual English/Greek meanings, summary correctness and whole-app memory fit
remain unknown.

This record contains metadata/source research only. No Krikri weight bytes or
header ranges were fetched, no model was imported or loaded, no inference was
performed, no cache was removed and no production file was changed. The unused
validation set remains untouched. A download or experiment requires a separate
concrete preparation plan and authorization.

## Exact candidate and provenance

| Item | Verified public metadata |
| --- | --- |
| Publisher | ILSP, Athena Research Center |
| Official repository | [ilsp/Llama-Krikri-8B-Instruct-GGUF](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-GGUF) |
| Immutable quantized repository revision | `3c1ce101a3e0d783a0f2223f212ccc35b4657532` |
| Selected complete text file | `llama-krikri-8b-instruct-q4_k_m.gguf` |
| File bytes | 5,041,147,264, approximately 4.695 GiB |
| Published LFS SHA256 | `e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f` |
| Native format | Publisher-produced single-file GGUF, Llama architecture |
| Access | Both base and GGUF repositories report `private:false`, `gated:false` without credentials |
| License | Llama 3.1 Community License Agreement |

The full payload hash has not been verified locally because the payload has not
been downloaded. This is a pin for a future integrity check, not a claim of
already verified weights. The publisher explicitly recommends its official
quantizations, noting that third-party conversions may use older weights.

The newer base repository revision
`5b6f2625e9b329ec70ab8cb6cbea7a06629b431f` initially appeared to postdate the
quantization. An independent comparison of complete published objects resolves
that ambiguity: the current base differs from its October 2025 state only in
README.md. All four weight objects and tokenizer/config/generation/index objects
match the February 9 model upload. The selected Q4 object is unchanged since
its February 14 first upload. This checks published object identity; it does not
reproduce quantization numerically.

The independent access/format audit is retained verbatim in
[`access-format-audit/findings.json`](access-format-audit/findings.json), with
the small public metadata, historical objects and exact source files it used.

## Why the Greek specialization matters

The [publisher's paper](https://arxiv.org/html/2505.13772v2) describes continued
training with 56.7 billion Greek tokens, 21 billion English tokens, 5.5 billion
parallel-data tokens and 7.8 billion math/code tokens before upsampling. It adds
20,992 vocabulary entries; reported Greek token fertility improves from 2.73
to 1.65 tokens per word relative to its Llama 3.1 base. Its post-training also
uses Greek and English instruction/preference data and sentence/document
translation examples.

The [model card](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct) reports
Greek IFEval strict-average scores of 67.5% for Krikri versus 32.7% for Meltemi
7B v1.5, and explicitly describes document translation and summarization among
the intended tasks. These facts support choosing this specialist rather than
the older Meltemi candidate for one test.

These are training descriptions and publisher evaluations. They are not a
semantic pass on LinkScribe's English/Greek cases, a Q4-specific score, or a
four-CPU performance measurement. Instruction following, general chat ratings
and token efficiency do not establish correct actors, quantities, negations,
technical terms or summary coverage. The paper also acknowledges remaining
reasoning/hallucination limitations and limitations of translated benchmarks.

## Resource feasibility and storage

The pinned [base configuration](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct/resolve/5b6f2625e9b329ec70ab8cb6cbea7a06629b431f/config.json)
specifies 32 layers, eight KV heads and a head dimension of 128. For one sequence
at 4096 context and two-byte f16 cache elements, the architectural calculation is:

`2 (K,V) × 4096 × 32 × 8 × 128 × 2 bytes = 536,870,912 bytes = 512 MiB`.

| Budget component | Size |
| --- | ---: |
| Complete Q4_K_M file | 4807.6 MiB |
| Calculated f16 KV cache, 4096 context | 512.0 MiB |
| File plus calculated KV | 5319.6 MiB |
| Remaining before runtime overhead under 6144 MiB | 824.4 MiB |

Tokenizer/metadata allocations, compute and activation buffers, native/daemon
and observer processes, load-time peaks and residual ASR/speaker memory are not
included in that arithmetic. The budget must be enforced and measured during
the actual import/load/request lifecycle. No larger context or whole-app claim
follows from this estimate. The existing verified CPU Ollama runtime offers a
native [single-file GGUF import route](https://docs.ollama.com/import), so a new
training framework or local conversion is unnecessary. Four-thread throughput
still needs measurement under the original request timeout.

The workspace currently has approximately 2.87 GiB free, insufficient for this
file and working reserve. Removing the reproducible rejected Gemma text payload
would free about 4.80 GiB, but that cleanup has not been performed or authorized
by this research task. Any later cleanup must preserve all rejected evidence,
model identities, scripts and shared runtime/Qwen files. Import should reuse one
verified payload allocation rather than retain two physical copies.

## Native template and limits that must be explicit

The base tokenizer and the repository-level GGUF metadata report identical
Llama 3.1 Jinja templates, SHA256
`e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65`.
The template uses BOS, system/user/assistant headers, end-of-turn markers and
fixed default date/system framing. The GGUF API's size field corresponds to the
Q3 file, so this does not yet verify the chosen Q4 header. Its actual embedded
template and native runtime rendering must be inspected before a generation.

The publisher also supplies separate `params` and `system` files. Its defaults
are **131072 context**, temperature 0.5, top-p 0.95, stop markers for header and
end-of-turn tokens, and a Greek assistant persona. Inheriting that context would
break the intended resource profile. A future setup must explicitly bind 4096
context, temperature 0, 2048 output, four threads and all existing time/resource
stops before any load or render preflight. It must also preserve the complete
intended application system/user messages and record the actual native date,
persona and stop behavior. No source-specific translation hints are justified.

This is an ordinary Llama chat-format candidate rather than a native hybrid
thinking profile. The pinned Ollama 0.40.12 handler accepts `think:false` for
models without thinking support. That is a protocol compatibility observation,
not a guarantee of translation quality. Full prompt/token accounting and final
JSON/completion checks remain necessary.

## License scope

The [upstream Llama 3.1 agreement](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE)
permits use, modification and distribution under a custom community license.
It is not an Apache/MIT or research-only release. Redistribution and related
products have agreement-copy, attribution and Built with Llama display
conditions; the acceptable-use policy, derivative-model naming provisions and
the stated greater-than-700-million monthly-active-user commercial threshold
also apply. Public, ungated access does not remove these terms. The actual
license and use policy are retained in the independent audit for a later
product decision.

## Decision boundary

The constraints leave one justified next experiment, subject to explicit cache
space preparation and actual native-format/resource verification: the single
pinned official Q4_K_M candidate above. They do not establish that it will pass.
A future trial should retain the complete original exposed cases and semantic
criteria, preserve all raw failures and stop at a declared resource/execution
limit. Fresh validation, summaries, whole-app tests and production adoption
must follow demonstrated quality and fit rather than this metadata review.

[`metadata-and-feasibility.json`](metadata-and-feasibility.json) records the
exact API observations, file/config identities, memory calculation and untested
assumptions. The independent audit's findings SHA256 is
`6c26bfa156364335d6722cba7f6cb7593856ca913abecc983a7e741f18e34d87`.

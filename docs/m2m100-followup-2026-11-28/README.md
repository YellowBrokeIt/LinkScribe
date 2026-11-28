# M2M100 418M translation screen — 28 November 2026

**This float32 candidate is rejected for translation-quality promotion.** Preparation, conversion and all six native development calls completed within the declared resource limits. Independent review nevertheless found decisive meaning errors: completed transcription became translation, and two distinct people were merged while a role was omitted. No production translator was changed, and no summary, heldout or retry followed the screen.

## What actually ran

The experiment used the [publisher's M2M100 418M checkpoint](https://huggingface.co/facebook/m2m100_418M), revision `55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636`. The model card declares MIT licensing and explicitly includes English and Greek. The originating [MIT license text](model-license.txt), pinned model-card identity and all downloaded-file checks are retained in [source provenance](source-provenance.json).

The original `pytorch_model.bin` was 1,935,796,948 bytes, SHA256 `d907ea45e4e4b9db163382a6674f6218b3c59566fe06d77f4055c208b4e87ed1`. It was converted locally with CTranslate2 to float32, without half-precision loading or an integer quantization step. The converted `model.bin` was 1,939,590,694 bytes, SHA256 `80470c1a7f3c38e253853e957c51363d37120de71298116f38a49d2c0195746c`. [Converted identity](converted-identity.json) also binds its configuration and vocabulary.

The isolated environment used CPU PyTorch 2.11.0, CTranslate2 4.9.1, Transformers 4.57.6 and SentencePiece 0.2.1. [Dependency identity](dependency-identity.json) records the remaining package versions and distribution hashes. These packages were installed in a separate experiment environment; core application dependencies were not changed. Conversion and inference used verified local files with offline mode and `trust_remote_code=False`.

## Frozen protocol and inputs

The [plan](plan.json), SHA256 `f89aa5300a047429c8bc136ab60527d7c45ef4956219358249869438bd529f94`, preceded conversion and inference. The later [inference freeze](inference-freeze.json), SHA256 `ec186e54596808d1dd7664b28fbf044b794aa6b9bef4ef13d967236902dbbc81`, binds the actual converted files, conversion resource report and complete source tokenization before the first translation.

The [six-case corpus](development-cases.json) is byte-identical to the previously exposed development-only copy, with the original sources, references and criteria unchanged. No unused validation corpus was opened. References and criteria are report data; the native model receives only source tokens and the required target-language token.

Each complete original segment was tokenized without truncation. The twelve inputs contained 17–36 tokens, including the correct native source-language marker and EOS. No unknown source tokens occurred. [Source tokenization](source-tokenization.json) preserves the exact text, token strings, token IDs and language markers. The standard tokenizer's native normalization is separate from the runner, which performed no glossary replacement, source rewriting or sentence splitting.

The actual runtime was CPU float32, one translator, four intra-operation/PyTorch threads and one inter-operation worker. It used beam width 5, one returned hypothesis, no sampling search or word replacement, and exactly one native batch call per case. Native batching retained the original segment order and limited internal batch size to one. Input truncation was disabled; the runner rejected any source over its predeclared 512-token bound.

Output acceptance required the exact target-language prefix, returned terminal EOS, nonempty content, no unexpected special content tokens and a raw length strictly below 512 tokens. Raw hypotheses and scores were saved before validation. Only the expected language prefix/EOS and outer whitespace were removed during ordinary decoding. All twelve observed outputs were 13–33 tokens long, so none approached the cap. These checks establish execution and completion, not semantic fidelity.

## Independent semantic result

A separate agent froze the [original source/criteria snapshot](source-criteria-before-output.json) and [plan binding](plan-binding.json) before output review. The [independent review](independent-review.json), SHA256 `2074cfa4205f8f8455eaae64362cd371ff8a55518601992d5b29639dc2ab007f`, is retained byte for byte. It records every criterion, source/output string, raw-token reconstruction and exact report hash.

| Development case | Reviewer's classification | Finding | Native call seconds |
| --- | --- | --- | ---: |
| Transcript terminology | Major error | The source says transcription took 12 minutes. The output says translation took 12 minutes, then says translation has not started. | 2.765 |
| People and roles | Major error | Eleni and Elena become the same name, producing “to Elena, not to Elena”; a translator role is omitted. | 2.089 |
| Receipt and Bitcoin amounts | Minor issue | Values, separate-transfer relationship and distinct units remain; some nouns are imprecise. | 3.057 |
| Negation scope | Major under global actor preservation | Negation and uncertainty criteria pass, but the output uses “it” in place of the person/“she”. | 2.430 |
| Conditional publication | Acceptable | People, necessary approval condition and Friday/Monday timing are preserved. | 2.619 |
| Uncertain question | Major under global name preservation | Question and uncertainty criteria pass, but Maria becomes Mary. | 2.066 |

The reviewer therefore classified four cases as major, one as minor and one as acceptable. The last two major classifications rely on the declared global actor/name constraint; their narrower negation/question criteria pass. The terminology error and collapsed people/omitted role independently block promotion even if a reader assigns less severity to those latter name/pronoun issues.

The terminology case passes the automatic lexical indicators despite its incorrect relationship between transcription, translation and elapsed time. This demonstrates why complete tokens, valid structure and matching vocabulary cannot certify the required meaning. These six owned, already exposed scenarios are a development screen, not a general error-rate estimate.

## Resource observations

Conversion and inference ran in separate owned worker processes under an external monitor. The monitor enforced a sampled concurrent RSS limit of 6,144 MiB, a 600-second conversion limit, a 900-second inference limit and a 240-second per-case limit. Small infrastructure controls independently exercised normal completion, a forced timeout and a forced memory stop before model execution. Their reports are retained separately from actual model evidence.

| Phase | Elapsed seconds | Peak concurrent RSS | Peak concurrent PSS |
| --- | ---: | ---: | ---: |
| Float32 conversion | 12.934 | 2,709.3 MiB | 2,703.9 MiB |
| Native six-case screen | 23.586 | 2,288.1 MiB | 2,282.5 MiB |

Both measurements completed, both owned workers exited, and frozen source hashes remained unchanged. The native translator explicitly unloaded after the screen. [Conversion resources](convert-resources.json), [inference resources](infer-resources.json) and [request metrics](request-metrics.json) preserve the underlying observations and available OOM-counter scope.

The memory scope includes the monitor and its worker/descendants. It excludes the operating system, browser, unrelated processes and filesystem cache outside process residency. RSS can double-count shared pages; 0.2-second sampling may miss brief peaks. Files were hashed before launching each worker, so the timings are not a cold-storage benchmark. This isolated result does not approve the full application workflow or the 7.3 GiB whole-machine goal.

## Cache cleanup and reproduction

After the immutable source/output/resource evidence was [frozen](immutable-evidence-before-cache-cleanup.json), the coordinator authorized removal of only the two reproducible rejected weight payloads. Their full hashes and sizes were checked again before deletion. [Cache cleanup](cache-cleanup.json) records removal of 3,875,387,642 bytes and about 7.71 GiB of workspace space available afterward. Configurations, tokenizers, license, isolated dependencies, scripts, plans, every output and resource report, and all original/converted identities remain. Shared Ollama models, application data and user data were untouched.

Reproduction therefore requires reacquiring the pinned original weights and recreating the converted weight file. The retained `prepare_source.py`, `native_worker.py` and `run_phase.py` implement the source checks, conversion, native protocol and bounded process accounting. They refuse to overwrite prior evidence. A replay needs a fresh experiment/output location and its own declared freeze; deleting these retained failure reports to retry silently is not a reproduction procedure.

The engineering decision is to keep this exact profile out of production and leave the current language-quality gate unresolved. There was no adjustment of precision, language tokens, beam width, segmentation, glossary, output budget or semantic criteria after observing an output.

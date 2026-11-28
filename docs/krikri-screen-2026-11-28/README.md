# Official Krikri Q4 development screen

**Result: rejected for promotion.** Independent review found five acceptable translations and one major name-preservation error. The model changed Νίκος to “Nick” and Ελένη to “Helen.” These are substitute English names, not faithful transliterations. The roles and distinction from Elena survived; this is not an actor reversal or a recipient mix-up. The existing semantic criteria were not relaxed.

This isolated experiment evaluates the original six already exposed English/Greek translation development cases. It does not change the app's production model, dependencies, prompts, release status, or unused validation corpus. The published production adapter is archived byte for byte, and the executed copy changes only the context allocation from 8192 to 4096. The production foreign-script guard is preserved.

## Actual six-case result

All six original cases ran exactly once. Every call completed normally, had empty reasoning, retained complete source/segment metadata, matched its native preflight prompt count, stayed below the output limit, passed the existing app structure/script checks and acknowledged unload. Those operational successes did not prevent the material name substitutions.

| Original case | Independent meaning review | Prompt / output tokens |
| --- | --- | ---: |
| Transcript terminology | Acceptable; text/audio/process distinctions, completion and not-started translation preserved | 151 / 56 |
| People and roles | Major error: Nikos and Eleni replaced by Nick and Helen; separate roles otherwise preserved | 156 / 47 |
| Bitcoin amounts | Acceptable; values, units, receipt and separate transfer preserved | 167 / 67 |
| Negation scope | Acceptable; both negation scopes and the undecided future sale preserved | 153 / 50 |
| Conditional publication | Acceptable; actors, only-if approval, Friday and Monday preserved | 147 / 50 |
| Uncertain question | Acceptable; question alternatives, Maria and insufficient title evidence preserved | 152 / 52 |

The complete execution stage took 110.945 seconds, with 518 external samples, peak concurrent RSS 5533.7 MiB and PSS 5524.9 MiB. The owned worker and daemon stopped with exit code 0. Measured RSS headroom was 610.3 MiB. The standalone screen does not establish full-app or long-passage quality/resource fit. No previously unused validation, summary, whole-app test or additional model was run.

`execution-freeze.json` preserves every complete case and native preflight before semantic review. `independent-output-review.json` is the reviewer's exact artifact, SHA256 `c562821a070b756937adacf28f270f284c3e0ad69945cb804082746c5477adca`, including exact output/report hashes and each original criterion. Any separately authorized instruction follow-up must retain this failed baseline unchanged.

## Fixed candidate and protocol

The publisher's public `ilsp/Llama-Krikri-8B-Instruct-GGUF` repository supplies the selected `llama-krikri-8b-instruct-q4_k_m.gguf` at revision `3c1ce101a3e0d783a0f2223f212ccc35b4657532`. Its complete payload is 5,041,147,264 bytes with SHA256 `e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f`. The applicable Llama 3.1 Community License and use policy are retained alongside the official metadata; this is not an MIT or Apache-licensed model.

The fixed runtime is verified Ollama 0.40.12. Each application request uses temperature 0, `think:false`, four CPU threads, a 4096-token context, the original JSON schema, a complete original source, at most 2048 response tokens, and a 240-second request timeout. The sampled external supervisor stops at 6144 MiB of concurrent process-tree RSS, including its own process, worker, daemon and native runner. Initialization is bounded at 180 seconds; each case is bounded at 600 seconds and the generation stage at 1800 seconds. Sampling may miss transient peaks. This is not a kernel memory limit or a whole-app/whole-machine resource certification.

`plan.json` was frozen before cleanup or download, with SHA256 `8842cceae54741a0999977db8f4e4584007eecebb95f0aaab2cc9d47cef4aeff`. The original six-case corpus and global/case-specific semantic criteria remain unchanged. The independent reviewer bound them before observing any candidate output. Raw final response JSON is retained before app parsing and script rejection. An execution, structure, script-guard, protocol, resource or time failure stops remaining cases without retry; semantic errors in an otherwise complete response are preserved for independent assessment.

## Verified storage and native preparation

Only the explicitly authorized, reproducible rejected Gemma weight payload was unlinked. Its full hash, size, inode, allocation, single link, prior owned-process cleanup and accessible namespace conflicts were checked first. The exact cleanup report, resource measurement and freeze remain here. No app/user data, shared runtime, other model, prior report, manifest, template or script was removed.

The Krikri payload and its publisher tokenizer reference were each downloaded once, verified in full, and retained in the experiment's own cache outside the repository. The complete download stage took 146.417 seconds and peaked at 42.7 MiB RSS. Native import reused the same payload inode and 5,041,152,000 allocated bytes. Imported metadata added only small blobs; no second physical weight copy was created.

The actual selected Q4 header was inspected, not inferred from the repository's default GGUF metadata. All 149,248 ordered vocabulary entries and 301,139 ordered merges match the pinned publisher tokenizer. The 292 tensor descriptors contain 8,202,227,776 parameters. The embedded template hash matches the publisher template, `e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65`. Actual BOS/EOS identities and the expanded vocabulary are retained in `selected-gguf-header.json`.

The publisher's optional Greek persona and 131072-context default were not imported. The native import contains the exact selected text model, fixed 4096 context, temperature 0, top-p 0.95 and the publisher's three stop strings. Native execution uses the embedded Llama 3.1 Jinja template; observed runtime rendering supplies its date header and preserves the complete original system/user messages, followed only by the empty assistant header. Native token accounting includes exactly one BOS token and reserves all 2048 potential response tokens plus an end-token margin. The six prompt counts are 151, 156, 167, 153, 147 and 152. Each actual generation must match its immediately preceding native preflight count.

Preparation generated no answer. It completed in 21.833 seconds with sampled RSS 5525.6 MiB and PSS 5517.0 MiB, then acknowledged model unload and stopped the owned daemon. This leaves 618.4 MiB of measured RSS headroom for that preparation phase; it does not prove full application fit. `native-setup-freeze.json` binds all selected-header, import, rendering, token-count and resource artifacts before the independent protocol review.

## Scope of the separate v1.5 metadata check

The authorized candidate remains the original Krikri Q4. The separate newer `Llama-Krikri-8B-Instruct-v1.5` has different weights, not merely the original repository's documentation update. The checked official inventory listed full safetensors and a separate 4-bit MLX package for v1.5, with no publisher GGUF for that version. The supplementary inventory is retained without changing the selected candidate or downloading another model.

## Evidence navigation

- `plan.json`, archived adapters and `context-only.patch`: pre-output scope and exact executed app code.
- `cleanup*.json`, `download*.json`: exact authorized unlink, one-attempt downloads, full identities and storage/resource evidence.
- `native-preparation-freeze.json`, `selected-gguf-header.json`, `prepare.json`, `prepare-resources.json`, `native-setup-freeze.json`: actual selected-Q4 native preparation and zero-generation checks.
- `independent-criterion-binding.json`, `independent-plan-binding.json`, and original source/criteria copies: independent pre-output bindings.
- `inference-freeze.json`, `execution.json`, `infer-resources.json`, six case reports and their native preflights, `execution-freeze.json`, and `independent-output-review.json`: complete original execution, resource evidence and independent semantic rejection.
- `native_verify.py`, `prepare_native.py`, `infer_native.py`, `run_native.py`: isolated native checks, actual app evaluation and unchanged external monitor reuse. Logs that could contain runtime environment details remain private outside the repository.

## Primary publisher sources

- [Official selected GGUF repository](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-GGUF/tree/3c1ce101a3e0d783a0f2223f212ccc35b4657532)
- [Official base model and tokenizer](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct/tree/5b6f2625e9b329ec70ab8cb6cbea7a06629b431f)
- [Publisher research paper](https://arxiv.org/abs/2505.13772)
- [Verified Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.12)

Publisher training and benchmark claims motivate this experiment; they do not establish that it preserves the meanings in these cases.

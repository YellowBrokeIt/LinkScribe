# Small-model refresh screen — 28 November 2026

**This candidate is rejected for quality promotion.** Qwen3-4B-Instruct-2507 Q4_K_M completed all six development translations through the unchanged production path within the existing limits, but independent review found three major meaning errors. This is a completed experiment with retained failures, not a production default or a completed language-quality gate. The original plan preceded setup; the narrowly corrected setup identities were frozen before inference. No summary or unused validation work followed this stage.

## Observed result

The fixed six-case screen ran once in 73.21 seconds. Every request finished normally, with nonempty final text, zero reasoning characters and an acknowledged unload. Actual request bodies matched the retained baseline after removing only model name. The [execution report](execution.json) and [request metrics](request-metrics.json) preserve those observations separately from semantic judgment. A separate agent's [independent review](independent-review.json) records every original criterion, source/output string and judgment, with full response/report hashes. Its [pre-output inputs](review-inputs.json) and [review provenance](review-provenance.json) are retained byte for byte.

| Exposed development case | Independent meaning review | Material finding | Elapsed seconds |
| --- | --- | --- | ---: |
| Transcript terminology, English → Greek | Major error | Original recording becomes original reading; completed transcription becomes reading that lasts 12 minutes. | 16.669 |
| People and roles, Greek → English | Acceptable | Nikos, Eleni and Elena remain distinct, with the correct roles and excluded recipient. | 9.222 |
| Receipt and Bitcoin amounts, English → Greek | Major error | Values are preserved with valid Greek numeric formatting, but receipt prose becomes nonsensical and the separate-transfer relationship is altered. | 14.710 |
| Negation scope, Greek → English | Acceptable | Denial, no sales yesterday and today's undecided possibility retain their distinct scope. | 8.968 |
| Conditional publication, English → Greek | Major error | People and approval condition remain, but waiting until Monday becomes waiting until Thursday. | 13.850 |
| Uncertain question, Greek → English | Acceptable | The two alternatives remain a question, with uncertainty and insufficient title evidence preserved. | 9.000 |

All three English-to-Greek examples in this small exposed set have material errors; the three Greek-to-English examples preserve their required propositions. These are six internally authored development scenarios, not an error-rate estimate or a claim about every input in either direction. Correct numeric tokens, valid JSON and plausible-looking text do not establish the missing meaning relationships.

The full sampled process-tree peak was **3,699.8 MiB RSS / 3,696.7 MiB PSS**, below the declared 6,144 MiB isolated-process screen. Measurement completed, source/data hashes remained unchanged, and the owned daemon stopped. The available host-global OOM-kill counter did not increase; cgroup counters were unavailable. The sampler excludes the operating system, browser, unrelated processes and filesystem cache outside process residency, can miss brief peaks, and is not whole-machine approval.

No retry, sampling change, output-limit increase, summary run or heldout run was used to rescue these outputs. The result supports rejecting this exact candidate profile for promotion under the current criteria; it does not identify training, quantization, decoding or another single property as the ultimate cause. Production `enhancements.py` and the selected default model remain unchanged.

## Why this candidate

The [publisher's model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) describes a refreshed, non-thinking-only 4B instruction checkpoint with general instruction and multilingual improvements. The [official Qwen3 language list](https://qwenlm.github.io/blog/qwen3/) includes English and Greek. Neither source establishes fidelity on the application's Greek names, amounts, negation or conditional actions. Those claims justify a bounded experiment, not quality approval.

The [official Ollama package](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) uses Apache 2.0 licensing and a 2,497,280,480-byte Q4_K_M weight layer. Its registry Go-template layer uses an ordinary assistant prefix without a thinking branch. The executing runtime exposes a separate embedded Jinja template, as documented below. This differs from the previously evaluated hybrid `qwen3:4b` package; it is not another request to enable reasoning on those same weights.

The exact candidate manifest is `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, compared with the retained control's `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. The [registry manifest](official-manifest.json) and [metadata verification](registry-metadata.json) bind the model, template, parameters, configuration and license. The setup script independently hashes every installed blob after the official pull.

Qwen3.5 4B and several translation specialists already have rejected development evidence elsewhere in this repository. The bounded research did not identify an officially verified small Qwen3.6 package within this memory budget. This refresh was absent from the recorded previous candidate identities.

## Frozen controls

The final pre-inference [plan](plan.json) has SHA256 `834c5add5ce8d8a6dbf3f52bb1b03368a46f9b2c0321b5269ae345286646b953`; [plan.sha256](plan.sha256) records the same value. It fixes the six exposed development cases, their order, the exact unchanged production source, the verified Ollama 0.40.12 binary, the package identities, and the runner hashes.

### Setup failure and bounded correction

The initial pull succeeded, but an overly strict cache check rejected the installed manifest before inference. Ollama 0.40.12 appends one provenance layer containing the exact original official manifest; that changes the local manifest's hash while the public model digest and every original descriptor remain unchanged. The [initial plan](initial-plan.json), [failed setup](initial-model-setup.json), and initial runner files retain that failure without alteration. No candidate response existed at that point.

The corrected verifier pins the exact local manifest hash `6214d088d3846e16c9fe00adcbabdbfddc61ce4a70daacc46cb2310c38603054`, requires parsed equality with the original manifest plus only that provenance descriptor, checks every blob's full SHA256 and size, and compares the added blob with the frozen original manifest bytes. It does not accept arbitrary extra layers or replace the public package identity.

The [read-only runtime inspection](setup-layout-inspection.json) also found that `/api/show` returns a 4,040-byte embedded Jinja template with SHA256 `40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541`, distinct from the legacy Go-template layer and current publisher template. Its prior-assistant-history branches include thinking wrappers, but its generation prefix is plain. All six actual requests contain only system/user messages. Their [offline rendered-prompt checks](template-render-verification.json) match the [pinned publisher template](publisher-template-verification.json) byte for byte, preserve complete messages, and add no thinking prefix. This is an offline formatting check, not a captured runtime prompt or a conclusion about assistant-history conversations. Actual response reasoning must still be empty.

The [revised setup](model-setup-v2.json) verified the already downloaded cache, native effective template and empty resident-model list, then stopped its daemon. No weights, prompts, model parameters, quality criteria or output budgets changed during this setup correction. The revised plan was frozen before the first candidate inference.

The request profile remains `think: false`, temperature 0, four CPU threads, 8,192 context tokens, 2,048 response tokens and the production 240-second request timeout. The existing prompts, JSON schema, source fragmentation and unload policy are unchanged. Native template and parameter defaults belong to the model package; this is a package comparison rather than a claim to isolate weights from every runtime detail. There is no sampling search, glossary, case-specific instruction, retry or reference answer in the prompts.

Only the [development-only copy](development-cases.json) is passed to the runner. It contains the same six already exposed scenarios and criteria, with the source corpus hash recorded. The retained baseline is reused for request equality checks; no new baseline inference is performed. Every candidate inference request must match its retained baseline after removing only the declared model name.

The screen stops on the first execution, structure, protocol, cleanup or sampled process-budget failure. Normal completion, final response text, empty reasoning and explicit model unload are checked independently of the production parser. Lexical review flags do not certify or reject meaning on their own. The total screen is bounded to 900 seconds, and every raw returned JSON object or execution failure is preserved.

The process screen uses concurrent evaluator/owned-daemon RSS with a 6,144 MiB rejection limit; PSS is also recorded. Sampling is not a kernel-enforced memory cap. The same architecture and quantization class as the measured control make this a plausible fit; a theoretical 8,192-token F16 K/V cache alone is about 1.125 GiB before graph/runtime overhead. This isolated screen cannot establish the 7.3 GiB whole-machine goal or the full ASR/speaker/browser workflow.

## Execution and review

`prepare_model.py` performs an official pull, validates all blob hashes and native template identity, verifies that no model became resident, then stops its owned daemon. `run_development.py` defaults to file/hash checks without starting a service. With `--execute`, it starts one owned loopback daemon, runs each case exactly once through the existing evaluator, and stops that daemon on completion or failure. Startup logs remain private outside the repository.

Before candidate inference, the request checker was exercised on six retained baseline cases with only the model name substituted, plus three negative mutations: a larger output allowance, unexpected reasoning and an absent unload acknowledgement. All expected decisions held. This is an offline protocol check, not evidence of candidate translation quality.

Actual model outputs must receive independent review against every predeclared meaning criterion before summary or validation work is considered. A material omission, invention, role/name substitution, quantity/relationship error or changed condition blocks quality promotion. Even a successful six-case screen would remain development evidence rather than an arbitrary-recording error rate or v1.0 approval.

## Commands

The runtime/model directory is outside the repository. The authorized setup invocation is:

```bash
python3 docs/model-refresh-2026-11-28/prepare_model.py \
  --runtime-dir /workspace/scratch/94360995dd61/linkscribe-model-runtime
```

After the verified setup and coordinator's compute-slot release:

```bash
python3 docs/model-refresh-2026-11-28/run_development.py \
  --runtime-dir /workspace/scratch/94360995dd61/linkscribe-model-runtime
python3 docs/model-refresh-2026-11-28/run_development.py \
  --runtime-dir /workspace/scratch/94360995dd61/linkscribe-model-runtime --execute
```

The runner refuses to overwrite existing results. Reproduction requires a clean experiment directory containing these frozen inputs and runners, together with matching production source and verified cached weights; retained outputs must not be deleted to retry this candidate silently.

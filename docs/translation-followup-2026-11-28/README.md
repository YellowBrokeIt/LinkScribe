# Translation follow-up — 28 November 2026

**The tested reasoning profile is rejected under the current application limits.** The existing Qwen3:4b baseline reproduced its earlier development outputs, including three major meaning errors. Turning on reasoning with the publisher's suggested thinking sampling settings consumed the entire 2,048-token output allowance on each of the first two cases, without producing final translation text. The original transcript remained available and neither response became an accepted translation.

This investigation made **no production translation change**. It did not open or run the unused v3 validation set. The exact candidate patch is retained as rejected experimental evidence, not a recommended production patch.

## Diagnosis supported by the earlier evidence

The prior terminology, amount and approval failures each occurred in a single request containing the complete short source. Those requests finished normally after only 150–160 generated tokens; their prompts used 127–153 tokens. The expected output structure and source metadata were valid. Missing source context, output truncation and JSON parsing therefore cannot fully explain those particular meaning errors. [The diagnostic record](diagnosis-before-inference.json) identifies the earlier report, its hash and the request observations.

The current control run reproduces all twelve translated segment strings from those six earlier development cases exactly. Examples include “original recording” becoming `το αρχικό αυτοκινητάκι` (“the original little car”), transcription and translation becoming `μετάλλαξη` (“mutation”), `5,000` becoming `5,00.000`, and Giannis being replaced by Antonios in an approval condition. These observations locate a semantic generation failure; they do not establish whether training data, quantization, decoding or another model property is its ultimate cause.

## Frozen comparison

The [pre-inference plan](plan.json) fixes the development corpus, exact production and experimental source hashes, runtime identity, request limits and decision rule. The [baseline snapshot](baseline-enhancements.py), [candidate snapshot](thinking-enhancements.py) and [two-change patch](thinking-profile.patch) are retained.

Both profiles use Ollama 0.40.12 and the same `qwen3:4b` Q4_K_M model, whose full digest is `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. Both use four CPU threads, an 8,192-token context, a 2,048-token response limit, the production 240-second request timeout, identical translation prompts and JSON schema, identical source batching, and the production unload policy.

| Setting | Baseline | Experimental candidate |
| --- | --- | --- |
| Thinking | Disabled | Enabled |
| Temperature | 0 | 0.6 |
| Top-p / top-k / min-p | Runtime defaults | 0.95 / 20 / 0 |
| Explicit sampling seed | None; temperature 0 | 0 |
| Output and context limits | 2,048 / 8,192 | 2,048 / 8,192 |

The [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B) supports both modes and recommends the candidate's sampling settings for thinking. [Ollama's thinking documentation](https://docs.ollama.com/capabilities/thinking) describes the separate reasoning and final-content fields. The observed responses confirm that reasoning was actually enabled; this is not inferred solely from the requested flag.

This is a comparison of two complete profiles. Thinking and sampling changed together, so the result does not isolate their individual effects. There was one fixed seed, no retries, no selection of the best response, and no source-specific glossary or reference answer in the prompts. The recorded paired requests have identical messages, schema and model after removing the declared profile fields. [Request metrics and comparison checks](request-metrics.json) preserve that verification.

## Observed development results

| Development case | Baseline semantic review | Reasoning-profile result |
| --- | --- | --- |
| Transcript terminology | Major meaning error | 2,048 tokens; length limit after 169.6 seconds; no final content |
| People and roles | Minor issue: Eleni becomes “Ele,” while the roles remain distinct | 2,048 tokens; length limit after 176.7 seconds; no final content |
| Bitcoin and amounts | Major amount and wording errors | Request interrupted; no response captured |
| Negation scope | Acceptable | Not run |
| Conditional publication | Major actor/approval error | Not run |
| Uncertain question | Acceptable | Not run |

The baseline completes all six cases. Its separate [assistant review](baseline-review.json) classifies two as acceptable, one as having a minor issue and three as having major errors. Automatic lexical indicators pass the faulty approval case, illustrating why those indicators cannot certify meaning.

The reasoning profile provides **zero accepted translations**. Its first two responses contain 5,152 and 6,698 reasoning characters respectively, but empty final content and `done_reason: length`. Production correctly rejects both. The reasoning text is not treated as a substitute translation, and its plausibility is not graded as a successful answer. [Candidate assessment](thinking-review.json) records the execution failures separately from the unassessed meaning quality.

These six previously exposed, internally authored development cases are diagnostic examples, not a general translation benchmark or a measured error rate for arbitrary recordings. No fresh-validation conclusion follows from this experiment.

## Early stop and incomplete evidence

The original plan allowed up to 900 seconds for both profiles. After the second identical output-limit failure established that this exact candidate could not pass the execution gate, the owned executor session was interrupted to free the shared runtime. A third request had already started; it has no captured response. Three further cases were never started. The response budget was not increased.

The executor returned exit code 130 before the normal runner finalizer completed. The raw [candidate checkpoint](thinking-development.json) and [execution checkpoint](execution-both.json) are preserved in that incomplete state, rather than rewritten to look like normally completed runs. The separate [early-stop record](early-stop.json) binds their hashes, lists all six planned case states and explains the interruption. The complete [baseline report](baseline-development.json) and [daemon log](daemon-both.log) are also retained.

Before publication, the daemon log's startup environment mapping was removed because it contained proxy configuration unrelated to translation evidence. The [redaction record](evidence-redactions.json) records the original and sanitized hashes, the affected line and the transparent manifest update. The original log is retained only outside the repository. The raw JSON checkpoints, inference outputs and timing rows were not changed.

The unused v3 corpus remained byte-for-byte unchanged, with SHA256 `e6917b37e1bc738086bdb4e7b8248c22f29002964eaa33824beb6ca3a4cc3d14`. Only its hash was read. The production translation file and experimental source snapshot also retain their declared hashes.

## Resource observations and limits

This was a CPU run on Python 3.12.14 and Linux, with about 9,967 MiB total host memory. [The preflight observation](resources-before.json) records available storage and memory while the preceding experiment still owned the inference slot. Translation started only after that slot was released. The runtime and 2.50 GB model cache were reused; this follow-up downloaded no model.

The completed baseline's sampled process-tree peak was 3,711.9 MiB RSS and 3,708.7 MiB PSS. The last saved candidate checkpoint observed 3,687.1 MiB RSS and 3,683.9 MiB PSS. The latter is an **incomplete measurement**, not a final whole-run maximum: the interrupt prevented the candidate's final memory and OOM-counter collection.

The sampler covers the evaluator and its descendants plus the owned Ollama daemon and its descendants. It excludes the operating system, browser, unrelated processes and filesystem cache outside process residency; RSS can double-count shared pages, and interval sampling can miss transient peaks. These numbers do not establish whole-machine suitability for an 8 GB computer. The complete scope and sampling limitations remain in the raw reports.

## Engineering decision

Keep the existing strict rejection of length-limited responses and preserve the original transcript. Do not apply the experimental thinking patch or promote translation quality on this evidence. The bounded thinking profile has an observed output-budget failure, while the baseline retains observed semantic errors. Changing the response budget or choosing another model would create a new candidate requiring its own declared resource and development checks before unused validation is considered; this run supplies no evidence that either change would repair the meaning errors.

The supported result is therefore a narrowed diagnosis and a rejected candidate, with intact evidence. It is not a successful translation-quality fix or a completed v1.0 language gate.

## Reproduction

The [isolated runner](run_development.py) starts and stops its own loopback-only daemon in the same executor namespace, verifies the runtime binary and model digest, imports the retained source snapshot, and invokes the existing production-path development evaluator. It refuses to overwrite existing reports. Use the matching production source checkout and a fresh sibling directory under `docs/` containing only `plan.json`, the two source snapshots and `run_development.py` when replaying the comparison.

The original invocation was:

```bash
python docs/translation-followup-2026-11-28/run_development.py \
  --runtime-dir /workspace/scratch/94360995dd61/linkscribe-model-runtime \
  --models-dir /workspace/scratch/94360995dd61/linkscribe-model-runtime/models \
  --profile both --max-seconds 900
```

The early external stop is documented separately; it was not an unrecorded change to the candidate or the runner.

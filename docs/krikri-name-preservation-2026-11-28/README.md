# Krikri generic name-preservation follow-up

**Result: rejected.** The single generic instruction clarification did not fix the name substitutions. Independent review again found five acceptable cases and one major error, with no minor issues. No broader evaluation or production switch follows from this result.

This separate experiment addresses one observed mechanism in the frozen Krikri baseline: it substituted “Nick” and “Helen” for the source names Νίκος and Ελένη. The baseline's independent result remains five acceptable cases and one major error. Its reports, classification and manifest are unchanged in `../krikri-screen-2026-11-28/`.

## Actual follow-up outcome

All six original cases ran once through the archived app adapter after independent native review and explicit root authorization. Actual requests contained the added instruction; each native prompt gained 23 tokens, and every returned prompt count matched the corresponding complete native preflight. All responses stopped normally below the output limit, had empty reasoning, passed app structure/script checks, preserved segment metadata and acknowledged model unload.

The people-and-roles case still returned exactly the baseline's “Nick” and “Helen” substitutions. The actor roles and distinction from Elena remained correct. Five complete final response strings were byte-identical to baseline. The amounts case changed the receipt noun to the acceptable Greek `παραστατικό` and added a natural article before Bitcoin, while preserving all numerical values, units, separate transfer and negation. Those small differences did not repair the material name error.

| Original case | Independent result | Prompt / output tokens |
| --- | --- | ---: |
| Transcript terminology | Acceptable; identical final content to baseline | 174 / 56 |
| People and roles | Major name-preservation error; identical final content to baseline | 179 / 47 |
| Bitcoin amounts | Acceptable; ordinary wording changed without changing required meanings | 190 / 69 |
| Negation scope | Acceptable; identical final content to baseline | 176 / 50 |
| Conditional publication | Acceptable; identical final content to baseline | 170 / 50 |
| Uncertain question | Acceptable; identical final content to baseline | 175 / 52 |

The generation stage took 113.511 seconds. Its 526 complete external samples recorded peak RSS 5538.5 MiB and PSS 5529.6 MiB. The owned worker and daemon stopped with exit code 0; measured RSS headroom was 605.5 MiB. No whole-app memory or long-passage approval is implied. There were no additional generation attempts, cases, summaries, model downloads or production changes.

`independent-output-review.json` is the exact independently authored review, SHA256 `212f55fd08245ef1598c49add30fdc53f03ebc6facdc409a9ead4eb72d260b28`. It binds the original criteria, every complete raw/final/app output, native preflight, actual prompt count, unload and resource record. `baseline-output-comparison.json` provides a separate mechanical byte comparison, not a semantic approval. `execution-freeze.json` preserved all execution evidence before final semantic review.

## Single candidate change

The baseline system instruction remains intact. The only added application instruction is:

> Preserve personal names with faithful transliteration when changing scripts. Do not translate or localize personal names into culturally equivalent names.

The exact source diff is `name-instruction-only.patch`. The candidate adapter SHA256 is `be1e36c614bd1d89ad35b96f3d4c7bda7b58ff66302734efdfc08a592cfff3c6`. It retains the current production foreign-script guard and the previously fixed 4096 context. No named example, expected translation, glossary, extra source hint, repair pass or postprocessing is added.

All six original development source texts, segment metadata and semantic criteria are unchanged. Each expected request differs from baseline only in that system instruction. Model, native template, source messages, schema, temperature 0, `think:false`, four threads, 4096 context, 2048 response cap and 240-second request limit remain fixed. The same 6144 MiB external sampled process-tree stop includes loading; initialization is bounded at 180 seconds, each case at 600 seconds and generation at 1800 seconds. There is no new model download or native import mutation.

## Retained setup failure and narrow correction

The initial plan was frozen as `d3e7eca8758e83fba2b74537b7a87849957a356a8e92de8d2253ba9f5957ef84`. Its first preparation stopped before model loading because the helper compared the human-readable `/api/show` parameter display as a raw string. Ollama listed the same `top_p` line first instead of last. The exact native cache descriptors, template and all parameter values matched baseline; no model response or native create call occurred.

That unsuccessful attempt is retained byte for byte under `initial-setup-failure/`, including its original plan/helper, raw `/api/show` values, resource report and manifest `41acd5ab4bd826ee82bf1f385d26154b9b6c0098bab525c3d021ffbb1a8af600`. It lasted 10.747 seconds, peaked at 70.9 MiB RSS and stopped its owned daemon.

The separately approved setup correction compares the complete semantic parameter mapping. It ignores only independent key display order, rejects missing/unexpected keys and duplicate singleton values, verifies numeric types/exact values, and preserves the exact order of the three stop strings. Nine focused probes demonstrate both the observed valid reordering and rejection of malformed/different settings. A fresh private log directory preserves the initial attempt's logs. `setup-revision-only.patch` contains the complete helper correction.

The revised pre-preparation plan is `0c85ff2378b1afa6df76778042392660a40ddd6f3de68aa92818af750620c887`. The candidate instruction, original source/criteria, native model and all resource limits remain unchanged across that setup revision. The independent reviewer checked this distinction before the corrected native preparation.

Corrected native preparation generated no answer and reused the existing native cache without import mutation. It completed in 14.631 seconds with 74 samples, peak RSS 5487.3 MiB and PSS 5479.0 MiB, then unloaded and stopped cleanly. The six complete prompt counts were 174, 179, 190, 176, 170 and 175. `native-setup-freeze.json` binds that preparation as `e0b225e9174d082bb7cb4326b86414564e5e894aab7a4d0190971ff3d7331a8a`.

## Required stage boundaries

Native preparation only renders and counts the six complete prompts, then unloads and stops its daemon. Final preparation reports and their resource measurement must be frozen and reviewed independently. Actual generation additionally requires root authorization and an inference freeze binding the reviewed files. One attempt per original case is permitted only after that boundary; any operational/protocol/script/resource failure stops the remaining cases without retry.

That boundary was satisfied by independent native review `a2c3ceb59dd66a0829f3bc229fddf9273db4272fc375ea9d6eef39ae97bd287e`, the retained `generation-authorization.json`, and final inference freeze `b9fafd0d4ade3de65de1d718093fb23809a02be6053cfa5d07cc8f5a2a5eb099`. The initial unsuccessful setup was never erased or reclassified as a successful attempt.

A six-case success would not approve the production default, long passages, summaries, whole-app memory fit or unused validation. No v2/v3, summary, full-app run or production switch is part of this stage. Meaning is reviewed independently from valid JSON, script acceptance and normal completion.

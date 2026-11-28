# Krikri source-name protection: rejected marker profile

## Result

The authorized six-case development stage **stopped after its second native
response**, following the frozen first-failure rule. There were two model calls,
no retries, and four original cases were not run.

| Original development case | Independent result |
| --- | --- |
| English → Greek transcription terminology | Minor fluency issue; all meaning, chronology and original name preserved |
| Greek → English people and roles | Exact-marker protocol rejection; no restored or accepted result |
| Amounts, negation, conditional publication, uncertain question | Not run after the second-case failure |

The first output preserved its one opaque marker, and exact restoration copied
`Maria` from source. The Greek phrase without its article was judged a minor
fluency defect; recording/text distinctions, completed transcription duration
and translation-not-yet-started remained intact.

In the second output, the model rewrote **all six** expected
`__LSNP_<nonce>_<segment>_<occurrence>__` markers into `Person` or `person` followed
by the digest/index suffix. These were normal, complete JSON responses. The
once-only exact-marker check correctly rejected the altered identifiers. No
name was guessed, no mangled marker was repaired, and no partial or final
restored translation was accepted. The readable raw role structure is retained
for review, separately from acceptance.

The candidate is rejected. The successful source-span replay and strict failure
handling do not establish that this translation profile works. All prior model,
name-instruction and detector decisions remain unchanged.

## Fixed experiment and evidence

`plan.json` froze the same official Krikri Q4_K_M payload, Ollama 0.40.12,
context 4096, temperature 0, non-thinking mode, 2048 output tokens, four CPU
threads and 240-second request timeout. The source-only code reused actual
retained detector outputs and the unchanged reviewed boundary normalizer. It
created distinct source-derived markers, preserved complete original metadata,
proved exact source reconstruction, and appended only one generic instruction
to the baseline context-4096 adapter. No model or dependency was downloaded.

All 24 generic source/marker/schema/guard controls passed. Their explicit
within-segment actor-reversal counterexample remains a semantic limitation.
`protected-source-cases.json`, `protection-inputs.json`, `expected-requests.json`
and `input-build-report.json` retain the complete original and masked bindings
for the planned six sources. No reference answer or name lexicon entered a
native request.

Native preparation generated no translation and verified complete prompt counts
of 229, 323, 223, 229, 276 and 228. All fit the 4096 context with the full 2048
output allowance and end reserve. `native-setup-freeze.json` binds those real
observations. The independent native contract review passed before the
`inference-freeze.json` was written and generation began.

For each attempted case, the ordinary evaluation report retains the original
source/criteria, exact request and raw native response. The companion
`*-protection.json` retains the same native response before guard rejection,
the raw masked strings, unchanged source map, and any accepted restoration and
final production-guard result. The original production script/copy guards ran
without modification; exact marker validation was an additional gate.

The two actual responses had matching full prompt counts **229 and 323**, with
**78 and 147** generated tokens and normal `stop` completion. Both explicit
unloads were acknowledged, with empty resident-model lists. The failure was
marker fidelity, not truncation, missing source, exhausted context, inference
timeout or a resource stop.

## Resources and cleanup

The generation phase lasted **65.989885 seconds**. Its 507 complete resource
samples recorded peak summed RSS **5562.9 MiB** and PSS **5554.0 MiB**, below
the 6144 MiB process-tree stop. The monitor includes loading and retains the
full sample series; sampling can miss short transients and is not a kernel cap
or whole-app approval. The owned daemon, native runner and worker were stopped.
Disk reserve remained above 1 GiB.

`infer-resources.json` deliberately retains `passed: false`, and the worker
exit code remains **1**, because the candidate failed the required output
protocol. Staying below the resource limit does not turn that functional
failure into success. `execution.json`, the raw reports and all prior files are
unchanged.

## Independent review and next scope

`independent-output-review.json` classifies the first case as a minor fluency
issue without material loss, the second as protocol-rejected without a restored
result, and the last four as not run. Its audit separately checks all 70
inference bindings, both raw-response routes, actual request/token/unload
records and all 507 resource samples. The native and final review scripts and
artifacts are archived unchanged.

Root authorized preparation only of a separate compact, neutral marker
follow-up after this rejection is frozen. Any such work belongs in another
directory, with a new plan and no new generation until separately reviewed and
authorized. This profile is not promoted. The normalizer's article-like-name,
undotted-initial and ordinary-prose limitations remain explicit; unattended
protection, broader validation, summaries and production integration are not
approved by this experiment.

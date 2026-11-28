# Gemma 4 E4B QAT: complete exposed v2 translation screen

## Decision

**Rejected for translation quality.** The independent review found seven major
errors, three minor issues and two acceptable cases. All four longer passages
contained major errors. The complete sources reached the model, every request
stopped normally, and the measured process tree stayed below the fixed memory
limit. Those execution checks did not establish correct meaning.

The unused v3 corpus remains unopened. No summary, whole-app resource test or
production-default change follows from this failed profile. The earlier six-case
screen remains preserved separately under
[`../gemma4-screen-2026-11-28/`](../gemma4-screen-2026-11-28/); its promising result
does not override this broader failure.

## Semantic findings

| Original v2 case | Independent assessment | Preserved meaning and material defects |
| --- | --- | --- |
| Telescope ownership, English → Greek | Major error | Brass becomes gold; borrowing becomes giving and the denied-gift actor is unclear. Return obligation and early-finish condition survive. |
| Ferry counterfactual, Greek → English | Acceptable | Counterfactual cancellation and actual departure remain distinct; Zoi is a valid transliteration of Ζωή. |
| Measurement readings, English → Greek | Minor issue | Greek grammar is imperfect, but quantities, units, dimensions and negated reading remain intact. |
| Alarm evidence, Greek → English | Major error | The concluding device-off condition becomes device-locked. No-sound and not-confirmed distinctions survive. |
| Questionnaire permission, English → Greek | Minor issue | An Arabic word replaces quotation and the Greek is awkward. The complete two-sentence output still preserves consent scope, actual refusal and photograph exclusion. |
| Pottery transcript, Greek → English | Major error | The name Νεφέλη becomes The Cloud. Audio, transcript and summary distinctions remain intact. |
| Theatre cue, English → Greek | Minor issue | Awkward Greek wording and grammar; both quoted actions, the female speaker and absence of a software-action request survive. |
| Maintenance quotation, Greek → English | Acceptable | The quotation, speaker attribution and distinction from a live instruction survive. |
| Weather-station passage, English → Greek | Major error | Probe becomes piston, sketch and canvas-bag descriptions are corrupted, and Persian/Russian words intrude. All five paragraphs, central quantities, loan/return roles, hypothetical wind, unperformed reset, privacy and final Saturday time survive. |
| Textile-exhibition passage, English → Greek | Major error | Extensive mixed-script and malformed prose prevents reliable interpretation of withdrawal and support collection, despite retained dates and amounts. |
| Model-railway passage, Greek → English | Major error | Giving away becomes lending, controller ownership becomes workshop ownership, and exhibition opening becomes report opening. Prices, no-purchase, counterfactual route and privacy survive. |
| Garden audio-tour passage, Greek → English | Major error | Ηλέκτρα changes to Eleftheria and Hélètra; a garden sign becomes a license plate twice. Directions, causal relation, distance, audio not yet replaced, 35 minutes, dry-weather hypothetical and privacy survive. |

[`independent-review.json`](independent-review.json) retains every original
criterion, the full actual outputs, successful and failed judgments, and exact
report/raw-response/output hashes. The reviewer copied and bound all sources and
criteria before inspecting outputs. The eight short cases keep their historical
`holdout` labels, but all twelve v2 inputs were already exposed by earlier trials;
this is development/regression evidence, not fresh heldout validation.

The retrospective audit used the actual frozen adapter. The production checkout
changed afterward, and the adapter's existing assembly strips outer whitespace
from each translated fragment. The reviewer preserved these audit-preparation
corrections explicitly in
[`independent-audit-preparation-note.json`](independent-audit-preparation-note.json).
They did not change any model request, result, source or criterion.

## Fixed candidate and execution

The candidate is unchanged from the six-case screen: Google's public Apache-2.0
`google/gemma-4-E4B-it-qat-q4_0-gguf` at revision
`4b4a2c1d584be7264f87aac328a1bc739ce81b6c`, using the original text-only Q4_0 file
with SHA256
`676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`.
The native Ollama 0.40.12 Gemma 4 small renderer/parser and imported manifest
`a3a7b071ffebe5e80b0979707cdcf7c27c5cae6cfd7e4f349ccee1546fee9627`
are unchanged. No projector, draft, download, conversion or alternative
quantization was introduced.

The exact archived `enhancements-context4096.py` has SHA256
`819568e7dd6939ffc9b9eb91130109235b97fb1cfee6192838645dc4e34aa178`.
It retains the original production translation prompts, JSON schema, fragmentation,
metadata handling, output limit and unload behavior, with the previously frozen
4096-token context. Each original case ran once at temperature 0, `think:false`,
2048 maximum generated tokens and four CPU threads. No glossary, replacement,
repair, retry, source cropping or expected-answer hint was used.

| Observed measure | Result |
| --- | ---: |
| Complete original cases | 12 / 12 |
| Actual generation requests | 21 |
| Unload control requests | 15 |
| Elapsed supervised stage | 385.056 s |
| Peak concurrent process-tree RSS | 5870.6 MiB |
| Peak concurrent process-tree PSS | 5861.7 MiB |
| Complete memory samples | 1724 |
| RSS margin below the 6144 MiB stop | 273.4 MiB |
| Actual prompt-token range | 123–308 |
| Actual generated-token range | 33–426 |
| Normal response stops | 21 / 21 |
| Actual prompt counts equal native preflight | 21 / 21 |

Before every generation, the observer checked the actual complete system/user
messages, schema and options, rendered them through the native runtime and
tokenized the full rendered prompt with the loaded native tokenizer. Complete
prompt plus the full 2048-token output allowance and an end reserve fit within
4096. Every original source character is reconstructed from the ordered request
fragments; original segment metadata is preserved; all actual raw final outputs
reassemble exactly to the application's translated text using its original trim.
The longer passages use the existing bounded fragmentation rather than any new
context-cropping rule. Their failures remain meaningful output-quality evidence.

The supervisor sampled the concurrent monitor, worker, owned Ollama daemon and
native runner tree every 0.2 seconds, with a 6144 MiB sampled RSS stop, 240 seconds
per generation, 600 seconds per case and 1800 seconds for the stage. No limit was
hit; the worker exited zero, every case confirmed unload, and the owned process
group stopped. Sampling can miss brief peaks and summed RSS can double-count
shared pages. This is neither a kernel-enforced memory ceiling nor a whole-app,
8192-context or whole-machine resource approval. The narrow remaining margin is
recorded without extrapolation.

## Evidence and reproduction

- [`plan.json`](plan.json) froze model, adapter, exact inputs and controls before
  inference; SHA256 `10e0d72feff41bbb9bbbeb8bbe8df2095ab1a12f0423d27c01b52ef375beb4b7`.
- [`screen.py`](screen.py) executes the frozen adapter and records each actual
  request, render and native-token preflight; [`run_stage.py`](run_stage.py) owns
  and measures the isolated process tree. Their source identities are bound in
  the plan and resource report.
- [`execution.json`](execution.json) retains completion checks as observed during
  execution. Its original `unreviewed` semantic label is unchanged; the later
  independent review is the semantic decision.
- [`resources.json`](resources.json) retains the measured process tree, limits,
  event timeline, exits and host/cgroup observation scope.
- [`request-metrics.json`](request-metrics.json) binds all raw responses, source
  coverage, segment metadata and final application outputs.
- Each case's report and companion `-preflight.json` retain the original data,
  exact requests, actual outputs, full native token sequence and runner identity.
- [`stage-sequencing.json`](stage-sequencing.json) preserves the subsequent
  instruction to require full-app resource evidence before fresh validation even
  if this stage had passed. This stage failed, so neither next step occurred.
- [`evidence-manifest.json`](evidence-manifest.json) freezes this directory,
  including the independent review and its original input/plan bindings.

The runner's historical source checks intentionally refer to the checkout that
was actually evaluated. A later production change must not be represented as
the same candidate or accommodated by rewriting these immutable artifacts.
Any subsequent experiment requires its own plan and frozen executable identity.

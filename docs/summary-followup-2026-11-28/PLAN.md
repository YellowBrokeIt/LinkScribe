# AI summary follow-up: single-generation statements with source evidence

This is a development experiment, separate from source highlights. The desired
result remains a useful generated summary with faithful key points and chapters.
The production summary implementation is not changed by this experiment.

## Observed problem and one candidate change

The retained `qwen3-eight-point-mixed-regression.json` consent result has the
correct approved budget `€84.75` in its paragraph, but the independently generated
key point says `€8:84.75`. The existing grounding prompt already asks the model to
preserve quantities, actors, permission scope and pending versus completed work.
More repetitions of that general instruction are not independent evidence of a fix.

Candidate v1 generates one ordered set of factual summary statements, each with
source IDs and exact quoted evidence. A validator rejects nonexistent IDs,
non-verbatim quotes and digit/currency tokens missing from the statement's own
quoted evidence. The same statement strings form the summary paragraph and its
key points, preventing those two display fields from disagreeing through separate
generation. A generated topical chapter title retains the first real start time.

This candidate does **not** check entailment: a correct quote can still be cited
for an incorrect assertion. It also cannot verify spelled-out quantity relations,
actors, tense, ownership, permission scope, complete coverage or title semantics.
Those remain explicit review requirements. A caught error is a rejected result,
not a successful user-facing summary. No silent fallback converts source
highlights into an approved AI summary.

## Fixed development comparison

Before inspecting candidate output, run the existing direct-summary baseline and
candidate on the first two already published development cases:

1. `summary-en-consent-and-roles`: ownership versus operation, limited permission
   categories, corrected amount, pending booking and interviews.
2. `summary-el-workshop-counts`: inspected versus ready quantities, pending order
   and payment, total versus unit price, conditional delivery and separate roles.

Use the same verified Ollama runtime, `qwen3:4b` model identity, temperature zero,
8192 context, 2048 generated-token bound, four CPU threads, and production unload
policy. Run sequentially. Retain complete prompts, raw responses, every rejection,
timings and concurrent process-tree RSS/PSS measurements. Save candidate, baseline,
runner and development-corpus hashes before the first response.

Acceptance requires actual useful output: all important facts and every relevant
qualifier in the fixed source review criteria must survive, no prohibited claim
may appear, Greek stays Greek, and chapter titles must not invent an outcome.
Review paragraph and points, with the visible quoted support, against each source.
The validator alone never earns semantic approval. The initial pair is a
diagnostic comparison, not a sufficient release validation sample.

If this candidate is promising, evaluate the remaining two short development
cases unchanged before designing a separate bounded approach for long inputs.
The long-source implementation currently makes freeform notes and reduces those
notes again; this can lose roles, exceptions and final corrections. Candidate v1
does not solve that path and explicitly refuses sources above 3200 UTF-8 bytes.
Any further candidate must retain failed outputs and state which general change
responds to the failure. Do not inspect unused frozen summary validation or
weaken its criteria before a final candidate is frozen.

## Practical scope

These are owned fictional text fixtures with known source language. They do not
validate real ASR, speaker attribution, UI persistence, export behavior, unrelated
languages, natural meetings or cross-machine performance. Measured process memory
excludes unrelated programs and the operating system. This follow-up can justify
further engineering; it cannot by itself close LinkScribe's v1 summary gate.

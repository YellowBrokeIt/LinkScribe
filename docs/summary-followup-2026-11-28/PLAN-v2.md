# Candidate v2: one bounded revision against the complete original source

Candidate v1's English output passed exact evidence and quantity validation but
asserted that Beatrice owned the recorder while its exact quote said Rowan owned
it. It also omitted the planned return. This is a material semantic failure, not
a passing summary. The copied quotes made the contradiction inspectable but did
not prevent it.

The next general experiment retains the entire v1 first pass, then makes one
source-first revision request. The second request marks the first draft as
untrusted and supplies the complete original short source again. It asks the
model to compare each clause with the source, remove unsupported relationships,
restore important omissions, and return the same evidence-backed statement
schema. The original exact quote and quantity validators apply to the result.
All outputs from both calls remain in the report.

This is an actual model revision, **not** a reliable semantic verification
algorithm. It can preserve an error or introduce a new one. Source/output review
still decides usefulness, actor/action relationships, tense, permission scope,
numbers and completeness. No result is approved merely because the revision
ran, its quotes matched or its JSON passed validation.

The original source remains bounded to 3200 UTF-8 bytes. Source plus untrusted
draft is bounded to 6400 decoded UTF-8 bytes in the revision call; oversized input
is rejected intact. This explicit larger second-call input permits source plus
draft to coexist without cropping either. Context remains 8192, generated tokens
2048, temperature zero and four CPU threads. Every model phase uses the existing
unload policy. This adds latency, which must be measured together with process
memory before assessing feasibility.

Run both passes live on the same two fixed development cases first; do not replay
earlier outputs or inspect unused frozen summary validation. Existing source
review criteria and all v1 failures remain unchanged. If the final outputs are
useful and faithful, expand only to the two remaining short development cases.
The separate long-source map/reduction problem remains open.

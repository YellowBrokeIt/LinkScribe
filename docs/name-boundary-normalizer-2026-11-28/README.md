# Source-only Greek article boundary follow-up

## Result

The independent replay review found **6/6 original source cases and 13/13 PERSON
mentions at the exact predeclared boundaries**. One proposal changed from
`[0,7) Η Μαρία` to `[2,7) Μαρία`. The other twelve spans remained unchanged.
The removed `Η ` remains in the unchanged original source, outside the proposed
protected name. Original segment text, times, speakers, offsets and raw scores
were retained. No detector, translation or masking call occurred.

This is a limited development improvement. The original raw detector screen
remains rejected. Article-like name components and undotted initials remain
ambiguous; stripping an article cannot fix descriptive prose wrongly included
inside a person span or a missed person. Every proposal still requires independent
source review. This result does not approve unattended protection or translation.

## Evidence and method

The frozen plan and implementation are in `plan.json`, `proposal.md` and
`boundary_normalizer.py`. The plan fixes the thirteen definite-article forms
from two official Greek grammar tables, exact whole-token matching, no accent or
punctuation repair, same-segment containment and a source-exact suffix. A raw
single-token span stays unchanged; a multi-token span may leave a one-token name.

All **50** predeclared mechanical controls passed, including nine invalid-input
rejections. Four explicit semantic-limit cases are retained as limitations even
when their mechanical outcomes match the specification. Their results are not
a semantic safety certificate. The reviewer checked the complete controls and
all six actual proposals against the unchanged annotations frozen before the
original detector run.

`execution-freeze.json` binds the exact plan, code, controls and pre-replay review.
`execution.json` records one replay per case, 0.005695 seconds elapsed and
12.691 MiB process peak RSS, bounded by 30 seconds, 10 CPU seconds, four-CPU
affinity and a 512 MiB address-space ceiling. All six original source/report
bindings were rehashed unchanged. This tiny offline operation makes no model or
whole-app resource claim.

`independent-pre-replay-contract-review.json` and
`independent-replay-review.json` retain the independent decisions exactly.
`results-summary.json` records the limited decision. `evidence-manifest.json`
checksums the deliverable files and excludes compiled Python bytecode.

## Evidence wording correction

The frozen replay code checksum-reads the prior independent raw-output review,
which contains expected-span annotations, to verify that prior evidence remains
unchanged. It does not parse that review or supply annotation/reference data to
the pure normalizer. Therefore the broad proposal statement and the frozen
`annotation_input_read: false` flag must not be interpreted as a literal claim
that the process read no annotation-containing bytes. The narrower verified
claim is that the algorithm received only actual source segments, actual raw
predictions and source language. The original record is preserved, and this
clarification is also in the independent review and results summary.

## Scope of any later work

Root has conditionally authorized a separate, reviewed six-case masked
translation experiment. Its preparation/results belong in another directory.
No such output is included here. The model baselines, failed name-instruction
follow-up, rejected raw detector and this bounded replay remain separate and
immutable. No fresh validation or production integration is approved by this
replay.

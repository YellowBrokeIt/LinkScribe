# AI summary follow-up — 28 November 2026

**Neither source-cited candidate met the unchanged acceptance criteria.** The
first removed an observed
numeric disagreement between paragraph and key points, but invented recorder
ownership despite quoting the correct source. A second source-first revision
corrected that owner, then dropped required actions and a publication condition.
Exact citations and literal number
validation are useful checks; they do not prove a generated statement is true.
Production summary code remains unchanged, and the v1 summary/chapters gate stays
open. A separate offline point projection also proved unsuitable as a global
replacement because some existing points contain facts missing from their
paragraph. Source highlights remain a separate feature.

## Why this experiment was chosen

The existing production short-source path already sends the original transcript
directly to the model. Its prompt explicitly asks for correct actors, quantities,
permission scope and completed-versus-planned actions. The retained
[eight-point regression](../summary-2026-11-26/qwen3-eight-point-mixed-regression.json)
nevertheless contains `€84.75` in a consent-case paragraph and `€8:84.75` in an
independently generated key point. The current experiment's actual baseline
reproduced that exact defect with the same model digest.

Candidate v1 generates one ordered set of factual statements with exact quoted
support and source IDs. The validator checks IDs, verbatim quotes and whether
digit/currency tokens occur in the statement's own evidence. Both the paragraph
and its key points are then derived from those same statements. The intent is to
eliminate independent copies drifting apart and make supporting source text
inspectable. It does not claim to verify actors, tense, entailment or coverage.

[Deliberately false validator probes](lexical-validator-limits.json) make that
boundary concrete without running a model: wrong ownership, a future action
changed to completed, a quote chosen after a negation, and a removed negative
sign all pass this lexical checker. Its numeric pattern covers digit/currency
tokens, not complete mathematical meaning, signed values, spelled-out quantities
or what a number describes. These probes are recorded as limitations, not passes
on a quality benchmark.

The [plan](PLAN.md) and [candidate freeze](candidate-freeze-v1.json) were written
before inspecting candidate model output. The two selected cases come from the
already published development corpus, whose source and review criteria were not
changed. The unused frozen summary validation file was not opened.

## Actual paired results

All four requested calls completed live, without response replay or retries.
Each model phase used the existing unload policy. The
[complete report](development-pair-v1.json) retains every request and raw response,
delivered fields, model settings, source/code hashes, controls and memory samples.
The separate [assistant review](review-v1.json) compares those fields with the
fixed source criteria.

| Development case | Profile | Wall time | Generated tokens | Peak process PSS | Observed result |
| --- | --- | ---: | ---: | ---: | --- |
| English consent and roles | Production baseline | 27.476 s | 226 | 3728.5 MiB | Correct paragraph amount, malformed `€8:84.75` key point |
| English consent and roles | Candidate v1 | 50.412 s | 436 | 3746.4 MiB | Exact quotes/numbers pass; invents Beatrice ownership |
| Greek bicycle workshop | Production baseline | 101.087 s | 949 | 3808.3 MiB | Facts substantially preserved; rough Greek grammar |
| Greek bicycle workshop | Candidate v1 | 219.057 s | 1789 | 3812.4 MiB | Mostly faithful statements; omitted non-cancellation, weak condensation and run-on paragraph |

The candidate's first English statement is:

> Beatrice owns the recorder lent by Rowan, who remains its owner; Hana operates it during the event but is not responsible for publishing interview selections.

Its exact evidence says Rowan lends the recorder and remains its owner. No
Beatrice ownership is stated. This failure passed every lexical evidence check.
The planned return by Hana was also omitted from the delivered text despite
being present in a quoted evidence span.

The Greek candidate retains the price's total-versus-unit distinction, lack of
payment, pending order, separate roles and conditional delivery. It omits the
explicit no-cancellation decision required by the fixed review criteria. Its
paragraph is 1513 UTF-8 bytes versus 1584 source-text bytes, so it provides little
condensation. Eight statements without terminal punctuation became one run-on
paragraph when joined with spaces. These findings are preserved rather than
scoring the output as successful merely because it contains valid citations.

## Runtime and resource scope

[Runtime provenance](runtime-provenance.json) records an actual official Ollama
0.40.12 binary and the installed `qwen3:4b` Q4_K_M model. The downloaded official
archive was hashed in full and matched the repository's existing pin:

```text
Ollama archive SHA-256:
f8adcb7e08d272283a4bd3abc18cf581afe37e64b2aee04fda4f407f215485ba

Installed model digest:
359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7
```

Settings are temperature zero, `think:false`, 8192 context, 2048 generated tokens
and four CPU threads. The source and candidate input/outputs are real; no model
result is substituted. Model weights live outside the repository.

The existing `ProcessMemory` sampler observed the evaluator and its descendants
plus the verified Ollama daemon and its descendants, deduplicated by PID. Every
run has complete measurements with a verified listener and stopped sampler.
PSS peaks were around 3.7–3.8 GiB; summed RSS was 3734.8–3818.0 MiB. These are
text-only process measurements, excluding unrelated programs, the operating
system and filesystem cache outside process residency. They do not establish
whole-machine memory fit with speech recognition and speakers also loaded.

The Greek candidate took more than twice its baseline latency and approached the
240-second request limit. Keeping memory bounded does not by itself make the
workflow practical for long recordings.

## The source-first repair also failed acceptance

[Candidate v2](candidate_v2.py) and its [plan](PLAN-v2.md) were frozen before any v2
model call. It retains the first pass, then supplies the original complete source
and an explicitly untrusted draft to one revision call. The revision must return
the same evidence-backed schema, with the same lexical guards. Source stays
bounded to 3200 UTF-8 bytes; source plus draft is explicitly bounded to 6400 bytes
without cropping. Model context and output caps stay unchanged.

The [English screening run](development-repair-v2-en.json) performed both calls
live, including a newly generated first draft that reproduced the wrong owner.
The source-first revision corrected Rowan's ownership and sharpened the explicit
permission categories. It retained the monetary correction and conditional
booking. It nevertheless dropped Beatrice's assigned room-confirmation action
and her requirement to check quotations with their speakers before publication;
the latter was present in the first draft. Hana's assigned return was still
missing. The [separate review](review-v2.json) records these omissions.

The pair took 104.034 seconds, peaked at 3764.5 MiB process PSS, and produced 436
then 482 tokens with normal stops. The revision input was 1580 bytes, comfortably
inside its declared bound. Every exact quote and quantity check passed. Neither
resource exhaustion nor malformed JSON explains the missing actions: this is a
content-selection failure after an apparently successful repair.

Under the predeclared English-first rule, that material coverage failure stopped
the branch before another expensive Greek run. Greek and remaining cases are
unevaluated by v2, not counted as passes or failures. A second model pass is not
a semantic validation algorithm, and these results do not justify a production
patch or held-out validation.

## Offline point projection: coherent text, incomplete representation

The [bounded projection](canonical_points.py) leaves an existing generated
paragraph and its chapters unchanged, then derives points from complete ordered
punctuated spans. Adjacent spans are merged to fit at most eight points, each at
most 900 characters. Decimal amounts, initial/title context and closing quotes
are retained. An oversized indivisible span is rejected intact. The normalized
concatenation of all points must equal the complete paragraph. This is a small
conservative boundary heuristic, not universal sentence analysis.

The [predeclared plan](PLAN-projection.md), [six non-model regressions](projection_checks.py)
and [five-output projection report](projection-results.json) make this scope
explicit: **zero new model calls**, with outputs from their identified original
contracts. All reconstruction, count and length checks pass. On the two fresh
baselines, projecting the paragraph adds no new omission relative to their old
points; the malformed English amount disappears because the paragraph already
has the correct amount.

The [source review](projection-review.json) finds a decisive limitation. In the
retained English quoted-command output, the original points supply the
**written** approval condition and the reminder's organiser recipients, which
the paragraph does not state. In the retained long-English result, points alone
carry the six-confirmed/four-interested volunteer distinction, Harun's access
checks before publication, and separate photograph permission for recognizable
visitors. Replacing those points with sentences from the paragraph would remove
material information.

The projection therefore is not proposed as a global production replacement.
It prevents independent disagreement, but the current paragraph is not always a
complete canonical representation. A future one-representation model contract
must demonstrate the required coverage first; mechanical reconstruction cannot
provide that evidence. This outcome also does not prove that a different local
model contract cannot work.

## Why long summaries remain separate work

The current long-source path creates freeform map notes, may rewrite those notes
in repeated reductions, then generates the final paragraph and points. Each
rewrite can lose a condition, change an actor, confuse a proposed amount with a
final one, or turn a plan into a completed event. Source character coverage and
shrinking note byte counts do not prove those meanings survived. A subsequent
stage cannot recover an omitted qualifier from the notes alone.

Keeping original evidence references through reduction is a plausible way to
make later generation refer back to the actual source. Selecting source passages
can also preserve their words. Neither establishes that a bounded selection kept
all important corrections and conditions, nor that a final rewrite used them
correctly. Those approaches require their own actual development results before
touching frozen validation. The present two-case experiment does not implement
or approve a replacement for the long-source path.

## Files and reproduction

The frozen [baseline](baseline-enhancements.py), [candidate v1](candidate_v1.py)
and [runner](experiment.py) are self-contained experiment code using the existing
local Ollama transport and memory observer. A daemon must run in the same process
and network namespace as the evaluator. With a verified local daemon and its PID:

```bash
LINKSCRIBE_OLLAMA_THREADS=4 LINKSCRIBE_OLLAMA_SERVER_PID=DAEMON_PID \
python docs/summary-followup-2026-11-28/experiment.py \
  --output /tmp/new-summary-development-pair.json \
  --case summary-en-consent-and-roles \
  --case summary-el-workshop-counts
```

The runner refuses to overwrite an existing report. Exit zero means the requested
experiment finished with unchanged code/source hashes, not that its generated
meaning is approved. The raw report deliberately retains
`semantic_quality: "unreviewed"`; source comparison is recorded separately.

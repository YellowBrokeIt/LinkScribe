# Source-highlights selection — actual evaluation

The rebuilt source-highlights feature selects verbatim transcript passages with
their original timestamps. It does not run a language model, generate headings,
translate speech or replace the existing draft AI summary. This record concerns
text selection; app, audio, persistence, export and browser checks are separate.

## Result

The fixed candidate passed all six development cases and then all four
separately frozen validation cases. Every selected passage matched complete
original segments and actual timestamp boundaries. The final development run
covered all **25** predeclared source goals; the first validation run covered all
**18**, with no applicable context-dependency flags. Separate assistant review
of the delivered validation excerpts found no invented contradiction or missing
declared qualifier in those four controlled sources.

This is narrow internal evidence. Exact text copying does not guarantee useful,
balanced or complete selection, and the original transcript can contain speech
recognition errors. The output retains that limitation. These results do not
approve the separate AI summary or translation quality gates and are not a v1.0
release approval.

## Source and freeze boundaries

The [evaluation plan](PLAN.md) set fidelity, coverage and context rules before
candidate output was read. Both corpora are internally authored fictional
English/Greek text, with no personal recordings or borrowed source passages.
The [corpus freeze](corpus-freeze.json) records their exact hashes. The earlier
summary development notes informed failure categories; their held-out source
cases were not opened or reused.

The implementation agent could inspect the six development cases. Four other
cases remained unavailable to implementation tuning until the candidate was
fixed. The [candidate freeze](candidate-freeze.json) binds selector SHA-256
`aeca9cd24343fa67ffdf00077ae0591846110ebcc71dc4c224181e57ff8cc17a`
before the first validation execution. Code and corpus hashes remained
unchanged during every recorded run.

Expected source groups and context requirements are evaluator metadata only.
The actual selector received only the source segments and source language.
No expected fact, quantity, decision or answer was added to its inputs.

## Retained development failures and corrections

| Run | Exact text/time checks | Reference coverage | Observed selection behavior |
| --- | --- | --- | --- |
| [Development v1](development-v1.json) | 6/6 cases passed | 24/25 goals | Greek long output omitted the four stations awaiting repair and included a long repeated procedural tail. The final eight usable stations were still present. |
| [Development v2](development-v2.json) | 6/6 cases passed | 24/25 goals | Novelty accounting and bounded passage centers repaired both long cases. A short Greek case then retained nine of ten segments while omitting its unapproved, unpaid total price. |
| [Development v3](development-v3.json) | 6/6 cases passed | 25/25 goals | A general near-full-source fallback retained a modest source completely when the small reduction would leave isolated gaps. Both long cases retained all declared facts with substantially less procedural filler. |

The v1 context checker conservatively flagged the opening twelve-station
proposal because the dedicated inspection segment was missing. Assistant
review distinguishes this from a fabricated contradiction: the selected final
decision already stated eight usable stations. The actual defect was loss of
the four-repair detail and poor use of the selection budget.

The v2 correction tracks novelty across all returned context, limits selected
centers and recognises ordinary bilingual replacement/revision wording. It
does not encode fixture-specific names, quantities or source indices. The v3
fallback applies to sources no larger than 6,000 UTF-8 bytes when the proposed
selection already retains at least 80% of the source text but leaves gaps. It
does not expand the long-source hard limit. A full source must be displayed as
such, rather than presented as successful condensation.

[Development review](development-review.json) records the separate assessment.
Exact historical selector bytes are retained as [candidate v1](candidate-v1.py),
[candidate v2](candidate-v2.py) and [candidate v3](candidate-v3.py); these are
evidence snapshots, not production imports. The v1 snapshot was reconstructed
by reversing the known v2 patch and verified against its original recorded
SHA-256 before it was retained.

## First frozen validation

[validation-v1.json](validation-v1.json) contains complete inputs, actual
outputs, fidelity reconstruction, reference coverage and execution metadata.
[Validation review](validation-review.json) records the subsequent source/output
assessment by the assistant, not an independent human review.

| Fresh case | Source segments selected | Coverage | Review |
| --- | --- | --- | --- |
| English costume loan | 10/10 | 4/4 | Complete source retained, including the actual available count, conditional release, corrected total and photo limits. No compression claim. |
| Greek fragmented poster discussion | 14/14 | 4/4 | Complete source retained, keeping the corrected quantity, photo-permission continuation, pending payment and future sending together. No compression claim. |
| English long telescope demonstration | 18/82 | 5/5 | Keeps borrowed-stock quantities, signed release requirement, corrected refundable deposit, revised route and the final fragile-lens exception. |
| Greek long exhibition | 17/68 | 5/5 | Keeps sale versus loan consent, approved-but-unpaid expense, roles, conditional opening and the closing privacy/return limits. |

All four pass exact-source and context checks. The long outputs still include
adjacent procedural text to preserve local context. A six-passage selection
cannot guarantee that all distant context or every topic is present. The
validation corpus has now been exposed; later runs are regressions, not fresh
independent validation.

## Practical limitations

- Four short development cases and both short validation cases retain the whole
  source. This preserves meaning but does not shorten those transcripts.
- Long sources deliberately include repeated procedural wording and sparse
  decisive facts. Success on these stress fixtures does not estimate performance
  on natural meetings, podcasts or lectures.
- These checks bypass ASR, speakers and translation. Exact excerpt words can
  therefore preserve an incorrect original transcript. This evaluation does not
  certify speaker attribution or source-truth accuracy.
- The evaluator reports mechanical source coverage separately from semantic
  quality. All automatic reports keep `semantic_quality: unreviewed`; the
  separate assistant reviews are limited to the stated controlled cases.
- Storage, edits, backup validation, restart retrieval, downloads and desktop/
  mobile rendering need their own actual app evidence before release. The local
  integration checks below cover deterministic API behavior; hosted rendering
  and actual audio checks remain separate.

## Integrated app checkpoint

[integration-local.json](integration-local.json) records the exact candidate
source hashes and the local Python 3.12.14 result: **652 tests and 32 subtests
passed in 8.77 seconds**. Python/JavaScript/shell syntax, dependency consistency
and patch whitespace checks also passed.

The new integration cases exercise link/upload options with controlled source
acquisition, an actual deterministic selector, SQLite storage and reopening,
source-bound Markdown/JSON/ZIP exports, edit invalidation and regeneration,
concurrent-edit rejection, damaged optional data, batch-option recovery, version2
backup round trips, legacy version1 imports and atomic rejection of fabricated
excerpts. Optional summary or highlight failure preserves the original transcript.

The browser harness now checks highlights from an actual Tiny-ASR upload,
downloaded content, original-segment navigation and library regeneration after
editing. Local browser installation was unavailable, so those checks require
the hosted Chromium run for the final integrated commit; they are not counted
as passed here. Desktop/mobile screenshots must also be inspected. The UI and
Markdown explicitly label complete-source selections and avoid attributing a
multi-speaker excerpt to one speaker.

## Reproduction

Run `tests/evaluate_source_highlights.py` with `--split development` or
`--split validation` and a new output filename. `--fail-on-review-flags` makes
reference omissions return a nonzero exit code. The evaluator preserves prior
files, rejects a corpus that no longer matches its freeze record, checks for
code/input changes during execution, and independently reconstructs each
excerpt from its declared original indices and timestamps.

# Source-highlights evaluation plan — 28 November 2026

This plan and both corpora were prepared before inspecting any candidate
selection output. The [freeze record](corpus-freeze.json) binds their exact bytes.
These are internally authored fictional diagnostics, not real-user transcripts
or an external quality benchmark. The earlier summary development notes were
read for failure categories; their held-out cases were not opened or reused.

## What the feature must establish

Source highlights are selected excerpts, separate from generated AI summaries.
The selector receives only transcript segments and their language. Reference
goals, context dependencies, expected decisions and review questions are never
selector inputs.

Every delivered excerpt must contain complete, unmodified source segment text
in its original order, with a newline between adjacent source segments. Its
start and end must come from actual source boundaries. The selection cannot
invent a heading, speaker, quantity, timestamp or completed action. These
properties are independently reconstructed by the evaluator rather than being
accepted solely because the production validator accepts the output.

Verbatim copying does not establish semantic safety. A quotation of an obsolete
plan can mislead when its correction is omitted. An unfinished ASR segment can
lose a condition stated in the next segment. Each diagnostic therefore declares
important coverage groups and source-context dependencies before execution.

## Corpora

- Development: six English/Greek cases covering inventory and ownership,
  corrected numbers, total versus unit prices, pending actions, publication
  limits, a rejected quoted command, and fragmented unpunctuated speech. Two
  long sources contain repeated procedural discussion and sparse decisive
  information, with 72 and 60 segments and more than 24 KiB of source text.
- Validation: four separately authored fresh cases, including two long cases.
  Their contents must remain unseen by implementation tuning until a candidate
  is fixed after development review. Once validation informs a change, that
  case becomes regression evidence rather than fresh validation.

The repeated long passages are deliberate stress fixtures. They test whether
repetition displaces decisions, conditions, exceptions or ending information;
they are not representative estimates of natural meeting quality. All sources
have ordered real fixture timestamps, and no ASR or translation is performed.

## Assessment fixed before output

1. All source-fidelity, index, count, chronology and timestamp checks must pass.
2. Each reference coverage goal is marked present only if at least one of its
   predeclared sufficient source-segment groups is wholly selected. All listed
   goals are intended to be achievable within the feature's passage budget.
3. A context dependency applies only when its triggering source material is
   selected. At least one complete companion group must then also be selected.
   Missing a correction, condition or continuation is explicitly flagged.
4. Every missing coverage goal or applicable context dependency requires review.
   No threshold is lowered after seeing an output. Assistant review considers
   the actual excerpts together; it may distinguish a harmless omission from
   a materially misleading selection, with the reason recorded.
5. Even a mechanically clean result retains `semantic_quality: unreviewed`
   until that separate source/output review. Ten deliberate fixtures do not
   certify general usefulness, balance, noisy ASR, natural meeting performance,
   or factual truth of the original transcript.

The evaluator retains complete sources, outputs, reference results, execution
times and source-code/corpus hashes. It rejects changed corpus bytes and checks
that observed code and corpus remain unchanged during execution. Output files
are not overwritten, so failed and corrected runs can be compared.

## Reproduction

From the repository root, with only standard-library Python:

```bash
python tests/evaluate_source_highlights.py --split development \
  --output docs/source-highlights-2026-11-28/development-v1.json
```

Only after freezing the candidate, use `--split validation` and a separate
output filename. `--case` may select named cases; the report distinguishes a
complete requested selection from a complete corpus.

Exit zero means execution and exact-source checks passed. Review flags remain
visible; `--fail-on-review-flags` makes them return exit code two. Neither exit
code nor a nonempty result is a release-quality approval. App storage, editing,
backup/restore, exports and browser behavior require separate integration checks.

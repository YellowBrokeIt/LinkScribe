# One visible-name paired-tag profile — preparation only

## Concrete change and hypothesis

Wrap each reviewed actual PERSON source slice in a unique request-local pair:
`<x0>exact original source name</x0>`, then `<x1>…</x1>`, and so on. Every source
name character stays visible to the translation model. The only inserted text
is the matching opening and closing wrapper. Source offsets, original full
segments, times, speakers, raw detector scores and external source/map hashes
remain separately bound.

The frozen compact empty-tag stage restored all 13 names correctly but failed
meaning review: 2 acceptable, 3 minor and 1 major. In the major case, continuing
references to a person explicitly marked feminine in the Greek source became
`he`. Its manifest is
`4b6bb26a9c5118692e3178566ac74902ef7213fbf1c04969fe47adf8384094cd`.
That result is unchanged. The source article was already left outside the empty
tag; this preparation does not claim that the article was missing, or that
hidden name text has been proven to cause the pronoun error.

The distinct hypothesis is that keeping the actual name's lexical content in
the complete grammatical context may reduce this regression while a strict
whole-span copying requirement prevents the earlier Nick/Helen localization.
No gender is inferred or attached by the wrapper, and no gender lookup, name
dictionary, glossary, reference translation, case-specific example or output
repair is introduced. The model may still generate the wrong pronoun or decline
to copy a span. This is one testable representation, not a syntax search.

The sole added system instruction is:

> Treat paired tags as exact-copy source spans. Copy every whole tagged span,
> including both tags and all text between them, exactly once, character for
> character, into the translation for its original input entry. Translate all
> surrounding ordinary text. Do not change the text inside a span, nest spans,
> or add, remove, split, or move a span to another entry.

The existing application's system/user messages, JSON schema and production
guards otherwise remain fixed. The adapter is the same frozen production
snapshot with only context 8192→4096 and this generic instruction. The added
instruction includes no actual source name or expected translated wording.

## Exact validation and wrapper-only removal

The source-only builder consumes the same complete original six sources,
retained actual detector predictions and unchanged reviewed boundary normalizer.
It must reproduce the prior 13 exact source mentions and retain every segment's
metadata. The normalizer's excluded article stays ordinary source text. A raw
span that is unresolved, overlaps, crosses a source segment, has invalid
offsets or no longer equals the source fails before a request is prepared.

Before wrapping, refuse any source containing the reserved opening or closing
x-tag prefix. The existing conservative scanner includes spacing,
NFKC/casefold equivalents and format characters, for comparison only. It never
normalizes source/output text. Existing genuine markup in that namespace is
also refused. There is no alternate namespace, escaping fallback or retry.

For every translated entry, require exactly the expected complete paired
strings, each once in its original entry. Opening and closing indices must
match. Unknown, malformed, unmatched, nested, crossing, duplicated, moved or
altered pairs fail. Leftover opening/closing namespace prefixes fail, including
the previously observed extra-closing-tag counterexample. Strict JSON rejects
extra or duplicate properties, nonstandard constants and wrong array types or
counts. Complete original source/map hashes and metadata must remain unchanged.

**A changed inner name is rejected.** Transliteration, localization, accent or
case changes, Unicode recomposition, added whitespace and partial copying all
fail the exact whole-pair requirement. No rejected name is replaced with the
source name. After the response's inner text is checked against its exact
original source slice and the full expected pair, removal returns the inner
text from that validated response itself. Only its wrappers are stripped;
ordinary prose and name characters are untouched. The historical API field
`masked_segments` is retained for compatibility with the reviewed helper, but
its contents now include the original visible names.

This protocol is stricter than the meaning rule, which permits reasonable
transliteration. A semantically sound but non-verbatim tagged name will be an
operational rejection, not repaired. Exact source-script personal names are
already allowed by the existing six-case criteria; this is no new exception.

After wrapper removal, the unchanged production translation guard is applied
against the complete original source. Full native responses must be retained
before all guards in any later authorized run. Guard success still cannot
establish whether the translated facts, roles or pronouns are correct.

## Scope, counterexamples and no-model preparation

The controls are synthetic source/response strings, never model prompts or
fixture-name lists. They exercise exact source reconstruction, repeated
mentions, Unicode/inflection/apostrophe preservation, source and map corruption,
metadata, all paired-tag failure modes, strict JSON and the existing production
guards. They also retain cases where mechanically valid pairs accompany a
within-entry actor swap, a wrong ordinary pronoun or an extra unwrapped name.
Those are semantic failures/limitations, not candidate successes.

Tag ordinals remain request-local. Even a complete identical name pair can
recur in two requests with different surrounding content; exact external
request/source/map binding remains necessary. Tags alone do not authenticate
cross-request meaning. Whole-pair checks likewise cannot authenticate the role
assigned to an exact name inside its original segment.

The detector and normalizer are unchanged. Missed entities, false PERSON spans,
article-like actual name components, undotted initials and residual ordinary
prose inside a detector span remain explicit limitations. Original inflected
name forms remain exact even when that makes target grammar awkward. This
development preparation does not approve unattended name protection.

Only local source helpers, generic controls and the existing pinned reference
tokenizer may run now. No new model or detector is loaded; no native API, model
download or translation call is permitted. The unchanged offline request
capture verifies that each complete protected source fits the application's
1000-byte JSON source budget and stays in one request. It checks exact original
metadata and source roundtrip. Previously frozen review bytes are read only for
checksums; annotation/reference data is not supplied to the builder or request.

The tokenizer estimator must first reproduce all six complete retained native
token vectors from the rejected compact screen. It then replaces only the two
complete messages in that retained native layout and counts the new full
requests. It reserves all 2048 output tokens plus one end token within 4096,
records the paired spans' token costs and rejects native boundary tokens inside
those spans. This is an estimate using the pinned official tokenizer, not an
observed new native render/count. No source cropping or output-budget change
is allowed. The estimated costs and actual source byte sizes are retained in
the preparation reports and summarized after this one offline pass.

## A possible later stage requires separate authorization

If the concrete preparation review has no blocker and root authorizes native
work, keep exactly the verified Krikri Q4_K_M payload, Ollama 0.40.12/native
template/stops, temperature 0, non-thinking operation, four CPU threads,
4096 context and 2048 output cap. Keep 180-second initialization, 240-second
request, 600-second case and 1800-second total limits; externally monitor the
owned process group against 6144 MiB summed RSS from loading through cleanup,
retain PSS/sample series and at least 1 GiB free disk. No detector can remain
resident. Actual native source/render/token verification and independent
execution review must precede any generation.

The potential screen would be the same original six cases once, unchanged order
and meaning criteria, stopping on the first operational failure without repair
or retry. Independent raw/final meaning review would remain mandatory. No
native preparation or generation is authorized by this document. No expanded
or fresh corpus, summaries, whole-app approval or production integration is
part of this proposal.

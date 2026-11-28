# Krikri with source-derived personal-name protection

## Fixed development question

The unmodified Krikri screen and the generic name-instruction follow-up each
produced five acceptable translations and one major name-preservation failure:
personal names were replaced with culturally equivalent names. Both rejected
bundles remain immutable. This stage asks whether reversible protection of
actual source name spans can avoid that behavior in the same original six
development cases, without changing the translation model or weakening any
meaning criterion.

The detector is **not run again**. The stage reuses its complete retained raw
outputs and the frozen, source-only Greek article boundary rule. That rule's
independently reviewed six-case replay produced 13/13 exact spans, but the raw
detector remains rejected and the boundary ambiguity counterexamples remain
limitations. This is a supervised development screen, not a general approval
for unattended name protection.

## Source-only data flow

`protection.py` receives only original segments, their raw PERSON predictions
and the declared source language. It calls the unchanged frozen normalizer and
must reproduce the independently reviewed actual replay exactly. It derives a
nonce from the exact source text and proposed offsets, then assigns a distinct
ASCII marker to **every mention**, including repeated mentions of one person.
No name dictionary, transliteration table, reference answer, fixture criterion
or case ID enters the marker derivation or native request.

Markers have the fixed grammar
`__LSNP_<16 lowercase hex source/span digest>_<4 digit segment>_<4 digit occurrence>__`.
The reserved prefix is rejected if it already appears in source, including its
NFKC/casefold or format-character variants. Exact collision checks accompany
generation. A source collision fails before any model call; it is not escaped,
deleted or silently retried with another marker format.

Only exact name source slices are replaced. All other source characters stay
unchanged, including grammatical articles removed from a proposed PERSON span.
Full original text, times, speakers and additional metadata are retained
separately. The complete masked representation must restore byte-for-byte text
and identical metadata before a request is permitted. Each masked source must
also fit the existing 1,000-byte serialized input limit as a single unfragmented
request; no span or marker may cross a segment or fragment boundary.

The only change inside the archived context-4096 app adapter is a generic
instruction describing opaque personal-name markers, requiring them once in
their original entry, and asking that all surrounding ordinary prose be
translated. There are no actual names, hints, answer examples or case-specific
rules in that instruction. `marker-instruction-only.patch` retains the exact
source diff. The prior unsuccessful extra transliteration instruction is not
part of this candidate.

## Fail-closed output handling

Every returned native response is retained before the application or wrapper
can reject it. The ordinary application parsing, output limit and script guard
still run. The wrapper additionally requires an exact JSON object containing
only the `translations` string array, with correct count and no duplicate keys
or nonstandard values. The app strings must equal the raw array strings after
the app's existing edge whitespace trim; no other response repair is allowed.

Before restoration, every expected marker must appear **exactly once in the
same original segment**. Missing, repeated, altered, unknown, malformed or
cross-segment markers reject the case. The protection map is hash-bound, and
each restoration value must still equal its exact original source slice.
Restoration replaces only complete validated markers with those original name
characters. It preserves inflections, diacritics, script and punctuation without
guessing a nominative form or converting a name. All original segment metadata
is copied unchanged.

The complete restored result then passes through `_translation_result` again,
against the original source. Its copied-transcript and foreign-script checks
are the **exact current production implementation**, which is byte-identical
to the archived Krikri baseline production snapshot at preparation time. A
guard rejection remains an operational failure even if raw text is informative.
Raw content, marker accounting, restoration and guard result are separate
evidence fields. There is no fallback, retry or post-hoc textual replacement.

## Fixed native and resource profile

Reuse the already verified official Krikri Q4_K_M payload and existing imported
package with Ollama 0.40.12. There are no downloads, conversions, imports,
dependency changes, model changes, template changes, personas or sampling
changes. Native settings remain temperature 0, `think:false`, context 4096,
maximum output 2048 and four threads, with the same JSON schema and 240-second
request timeout. Full actual native prompt tokens, including one BOS and the
entire protected representation, must leave space for all 2048 response tokens
and an end-token reserve. Actual response prompt counts must match the native
preflight; no context cropping is allowed.

`prepare_native.py` renders/counts the six frozen requests without generation,
verifies the exact existing package/template/stops/parameters and then unloads
and stops its owned daemon. Independent review of the exact plan, code, source
maps, controls and actual native preparation is required before generation.
Root has already authorized one six-case run once that contract has no blocker.

The external monitor includes its own process, worker, native daemon and runner
from loading through exit, with a 6,144 MiB summed-RSS stop, four-CPU affinity,
180-second initialization limit, 600-second case limit and 1,800-second total
generation-stage limit. Preparation is bounded at 600 seconds. Every 0.1-second
resource sample is retained, with PSS and host observations distinguished from
the process budget. Sampling can miss brief peaks and is not a kernel cap or
whole-app approval.

The monitor reuses the already reviewed orphan-safe detector observer functions,
with only helper/event-prefix adaptation. A retained AST comparison confirms
those four functions are otherwise identical. Native daemons inherit the owned
worker's process group, so the monitor's original-group discovery also covers
children after leader exit. A small no-model probe verifies the daemon cleanup
helper. Models are explicitly unloaded after each case; the daemon is stopped
at stage end. The detector's completed resource/cleanup record is retained, and
this stage imports no detector or neural-runtime library. Disk reserve must
remain at least 1 GiB; no cache deletion is authorized or performed.

## Meaning gate and known limits

All original source, criterion and global name/actor/number/unit/relationship/
negation/uncertainty/condition/chronology/completeness rules remain unchanged.
The independent reviewer judges full raw and restored outputs. Exact source
script names are compatible with the pre-existing criterion, but ordinary
prose still has to be translated faithfully. Five successful short cases cannot
excuse a failed sixth case.

Markers cannot prove that a person fills the correct role within a sentence.
The generic controls deliberately include a role-reversal example whose marker
counts are valid. False or missed detector spans, article-like name components,
undotted initials and inflected-name grammar remain unresolved in general.
Source-derived identifiers do not eliminate prompt injection: source remains
untrusted data, strict structural checks reject detectable marker corruption,
and independent semantic review is still necessary.

One execution/structure/schema/marker/guard/resource/cleanup failure stops the
remaining cases without retry. A completed semantic failure is retained and
does not change the fixed later inputs or settings. Any expanded corpus, fresh
validation, summary task, whole-app test or production integration requires a
separate decision. None is authorized by this six-case result.

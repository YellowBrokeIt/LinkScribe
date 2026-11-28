# One compact-tag profile with separate source-spelling context

## Mechanism and reason to consider it

Reuse the exact compact `<xN/>` representation and output guards from the
completed six-case compact screen. Those tags survived every response, and all
13 actual source-name mentions were restored exactly. Meaning still failed:
the model used `he` for continuing references to the explicitly feminine source
actor. The later visible paired-tag profile failed its first exact-copy check
because it translated the inner name. Both rejected bundles stay unchanged.

This one proposal separates **input context** from **output-copy requirements**.
Keep compact tags in the source entries. Supply a separate JSON array containing
only each tag and its exact original source spelling. The model can read the
original lexical content without having to generate that spelling. Its output
must still copy the compact tags, which the existing strict guard validates
before exact source-name restoration. This is an unproved hypothesis about
lexical/anaphoric context, not a finding that the preceding pronoun error was
caused by hidden names or has been fixed.

The only new generic system text is:

> The source-spelling context is input data for interpreting the tags. Keep
> every tag in the translations as instructed. Do not output that context or
> substitute a source spelling for a tag.

The existing compact-tag instruction remains byte-for-byte intact. Before the
existing `JSON input:` source array, add one clearly labelled JSON data block
with records containing exactly `tag` and `spelling`. The spellings are copied
from the existing source-bound detector/normalizer spans, never from a reference
translation, fixture-name list or earlier model output. No genders, roles,
pronouns, translations, definitions or inferred relationships are added.

## Complete-source and output contract

Use only the same six exposed sources and the same reviewed 13 mentions.
Revalidate the frozen compact map, its source slices and the full original
text/metadata roundtrip before constructing context. The extra data records
contain exactly two fields, with unique source-derived tags. JSON escaping
preserves the original name characters. A context value that collides with the
existing source delimiter is refused, with no alternate syntax or fallback.

The original source array remains exact and complete. The proposal conservatively
requires the combined encoded source entries **and** spelling map to fit the
existing 1000-byte source budget, even though the application normally counts
only its source array. The full new system/user messages must also fit context
4096 with all 2048 output tokens plus an end-token reserve. No source cropping,
long-context change or output-budget increase is proposed.

The source-only helper inserts this context at the `_ollama` payload boundary,
before the unchanged adapter constructs and exposes its native HTTP request.
Offline transport capture therefore records the complete proposed request,
including the map, with the same model/options/schema. A future authorized
runner must observe that actual request and compare it exactly with the frozen
proposal; modifying payloads invisibly inside the transport would not suffice.

Output remains a JSON translations array with the original entry count. Keep
the reviewed compact source-collision, unknown/open/closing-prefix,
once-only/same-entry, metadata and raw-response checks unchanged. If the model
outputs a source spelling in place of a required tag, the marker is missing and
the result is rejected. A malformed/altered tag is never repaired. Only an exact
accepted compact tag is replaced with its original source slice; no modified
inner name is accepted or corrected. Apply the unchanged production guard
against the original source afterward and independently review all meaning.

## Feasibility scope and limitations

This is a source-only feasibility proposal. It may capture the six complete
requests offline and use the existing pinned reference tokenizer, first matching
all six prior complete native token vectors. It may not load a model, call a
native endpoint, rerun the detector, download weights, generate translations or
try another marker syntax. No production file changes. Actual native rendering,
resource measurement and a separately approved one-shot screen would still be
needed if this proposal is accepted.

The map could cause the model to echo spellings, leak the context block, omit
tags or attach a correct tag to the wrong role. Even intact tags cannot certify
pronouns, agreement, omissions or additional ordinary prose. Source inflections,
unisex names and grammatical context can remain difficult; the helper infers
no gender. Repeated mentions remain distinct occurrence tags, and request-local
IDs require the existing exact external source/request binding. Detector and
article-normalizer false positives/misses and semantic ambiguities remain.

Only actual personal-name spans may remain in their original script after
restoration, as the original criteria already allow. All ordinary prose, actors,
numbers, units, relationships, negation, conditions, chronology and completeness
must still pass the unchanged independent review. The current short-source
feasibility result cannot approve long passages, fresh validation, summaries,
whole-app memory fit, unattended protection or any production default.

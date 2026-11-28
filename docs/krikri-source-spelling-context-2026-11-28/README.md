# Separate source-spelling context: feasibility proposal only

One concrete source-only proposal is feasible within the existing short-source
byte/token budgets: reuse the unchanged compact `<xN/>` output mechanics, while
giving the model a separate input map with only each tag and its exact original
source spelling. This adds lexical source context without requiring the output
to copy a visible inner name. It is an untested hypothesis; no translation or
native setup has run for this profile.

The plan was frozen before offline request capture and reference tokenization:
`9a227797a2da2514de48b0dd9e822e3b699e322ecce7f0e2054cc552f3e24904`.
All 16 bound sources remain unchanged. The complete proposed requests are in
`expected-requests.json`, with exact original text/metadata and source-derived
maps in `source-context-maps.json`.

| Original case | Entries + map JSON bytes | Complete prompt estimate | Capacity after 2048 output + 1 end token |
| --- | ---: | ---: | ---: |
| Transcript terminology | 277 | 261 | 1786 |
| People and roles | 585 | 350 | 1697 |
| Amounts | 254 | 262 | 1785 |
| Negation scope | 369 | 266 | 1781 |
| Conditional publication | 365 | 302 | 1745 |
| Uncertain question | 365 | 264 | 1783 |

Every complete source plus its map fits the unchanged 1000-byte source budget.
All 13 actual source-name mentions and full original source/metadata roundtrips
remain exact. The existing pinned reference tokenizer first matched all six
retained native token vectors, then estimated these complete new messages.
Actual native rendering and counting are still required before any authorized
generation. No cropping, output-budget change, new model, detector call,
download or production edit occurred.

Only the generic context instruction and exact source-data block change. The
source helper captures the complete adapter request after projection at the
`_ollama` payload boundary, before native request construction/observation.
The compact tags, source-collision checks, same-entry once-only requirements,
exact source restoration, JSON schema and production guards are unchanged.
A name emitted instead of its required tag fails; it is not repaired.

No gender, role, definition, reference translation, case-specific hint or
external name lexicon enters the map. The model may still echo the map, replace
tags, introduce an extra name, or misassign roles/pronouns despite copying every
tag correctly. Detector/normalizer ambiguity and inflected target names remain
limits. All original meaning criteria and prior rejected results stay fixed.

`proposal.md` describes the single mechanism, strict output contract and limits.
`feasibility-results.json` records the completed no-model work. This bundle is
ready for source-only review and a separate execution decision; it does not
authorize native/model calls, another marker variant, expanded or fresh
validation, summaries, whole-app approval or integration.

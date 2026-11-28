# Visible-name paired tags: source-only preparation

This prepares **one** distinct follow-up to the rejected compact empty-tag
profile. Actual source names remain visible inside matching `<xN>…</xN>` tags.
The response must copy each entire paired span exactly once in its original
entry. Any changed inner name is rejected. Final removal returns the already
validated response's inner text and strips only its wrappers; it cannot replace
a changed name from the source map.

The plan was frozen before the offline controls, input capture and token
estimation at SHA256
`dcab0f9ef25ad365c915a44f287a3bdc607ef5856027215ed81b9325bcff893d`.
All 30 bound source files remain unchanged. **No language model or detector was
loaded, no native API or translation call occurred, and no weights were
downloaded.** Actual native preparation and generation need a separate decision
after independent review.

## Why this is a distinct candidate

The completed empty-tag screen had 2 acceptable outputs, 3 minor errors and
1 major error despite exact restoration of all 13 names. In the major case,
continuing references to explicitly feminine Άννα became `he`. Its complete
frozen evidence remains at
`../krikri-compact-tag-screen-2026-11-28/evidence-manifest.json`, SHA256
`4b6bb26a9c5118692e3178566ac74902ef7213fbf1c04969fe47adf8384094cd`.

Visible source-name text may help the model retain lexical and grammatical
context. That is a hypothesis, not a proven explanation of the regression.
The original article was already visible in the empty-tag input. This candidate
adds no gender inference, gender label, name dictionary, fixture hint or
reference translation. It uses the same reviewed actual source spans and
normalizer. The generic exact-copy instruction and entire candidate source are
in `proposal.md`, `marker-instruction.txt` and `protection.py`.

## Completed offline checks

All **47** synthetic mechanical controls passed. They cover altered inner names
(localization, case, whitespace, Unicode recomposition and repetition), exact
inflection and punctuation, matching tag indices, missing/nested/crossing tags,
unknown/open/closing namespace prefixes, duplicates, same-entry ownership,
source collisions, metadata/map corruption, strict JSON and the unchanged
production guard after wrapper removal.

Four controls explicitly preserve limitations: intact spans can accompany a
within-entry role reversal, a wrong pronoun or an extra unwrapped name, and an
identical pair can recur in a different request. Their structural conformance
does not count as semantic success. Detector misses/false positives and the
normalizer's article-like-name and initial ambiguities remain unresolved outside
the already reviewed development inputs. There is no unattended protection
approval.

All **six original full sources** reconstruct exactly with their original
metadata and all **13 reviewed name mentions** unchanged. The source-only input
helper is byte-identical to the previously reviewed helper. It captured the
actual adapter requests without making HTTP calls; only the generic system
instruction and reversible source wrapping differ from the baseline.

| Original case | Tagged source JSON bytes | Complete prompt estimate | Capacity after 2048 output + 1 end token |
| --- | ---: | ---: | ---: |
| Transcript terminology | 212 | 231 | 1816 |
| People and roles | 370 | 284 | 1763 |
| Amounts | 217 | 240 | 1807 |
| Negation scope | 304 | 236 | 1811 |
| Conditional publication | 210 | 251 | 1796 |
| Uncertain question | 300 | 234 | 1813 |

Every full source fits the unchanged 1000-byte single-request source limit.
The existing pinned official tokenizer first reproduced every token in all six
retained compact-screen native prompts, then estimated the complete new
messages in the retained native wrapper. Individual whole name pairs use
8–10 ordinary tokens here. These are reference estimates, not new observed
native counts or guarantees of output completeness. The estimator took
1.002 seconds with 223.75 MiB process peak RSS. Full source and the maximum
output budget are retained; no cropping or limit increase is proposed.

## Evidence and later decision

`preparation-results.json` records the completed no-model work;
`preparation-freeze.json` binds the exact inputs, code, requests, controls and
estimates for independent review. The candidate source is SHA256
`ca9316ec3387fa58d12460ae0ee076162990234183a0bc703da277205db7c4a5`;
the adapter is
`c494160b01ce72632e0bf276c0c7205e4b23227840efa194a2bc96422d389ae4`.
All original meaning criteria remain unchanged. Reasonable transliteration is
still allowed by those criteria, but a transliterated tagged name would fail
this deliberately stricter copying protocol rather than be repaired.

Any later authorized screen must retain the existing Krikri Q4_K_M payload,
native template, context 4096, output 2048, temperature 0, non-thinking mode,
four CPU threads, 6144 MiB externally sampled owned-process limit, complete
resource series and all existing timeouts. Actual native rendering, complete
token accounting, cleanup and independent execution review must precede one
six-case generation stage. No such stage has occurred here. Expanded or fresh
validation, summaries, whole-app fit and production changes remain outside this
preparation.

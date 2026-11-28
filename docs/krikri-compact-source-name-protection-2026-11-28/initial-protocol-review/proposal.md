# One compact neutral-tag follow-up — preparation only

## Proposed change

Use one fixed marker syntax: **`<x0/>`, `<x1/>`, …**, with a distinct occurrence
number for each actual source mention in a request. Tags are opaque and carry no
personal-name category, source name, digest or segment-number wording. The exact
source/map hashes, original offsets, original spellings and segment ownership
remain in the external protection record and never need to be copied by the
language model.

The frozen previous profile failed on its second response: all six
`__LSNP_<digest>_<segment>_<occurrence>__` markers became `Person`/`person` plus the
digest/index suffix. Normal completion, full input, correct token accounting and
ample output budget were confirmed. The strict guard rejected the response and
no restoration was accepted. That failure bundle remains immutable at manifest
`05694da4132ed7aba9f319a907d8051de684b32119a6b011aadb0a0a79089e23`.

This follow-up changes the representation that the model must copy. In these
six inputs, a 35-character digest/underscore marker becomes a five-character,
three-token tag. The instruction also stops describing the tokens as personal
names and instead requires exact copying of opaque self-closing tags. This is
a specific hypothesis about the observed rewriting mechanism, not evidence
that the new syntax will work. It does not repeat a stronger version of the
same failed name-preservation prompt, and it does not repair a failed output.

The sole added instruction is:

> Treat self-closing tags as opaque tokens. Copy every tag exactly once,
> character for character, into the translation for its original input entry.
> Translate all surrounding ordinary text. Do not add, remove, split, or move
> a tag to another entry.

The original application system instruction, JSON schema, model and decoding
settings remain unchanged. No actual name, case-specific hint, glossary,
expected translation or replacement dictionary enters that instruction.

## Preserved source and rejection contract

The candidate still consumes only the original six complete sources, their
retained actual PERSON predictions and the unchanged source-only boundary
normalizer. The generated spans must reproduce the prior independently reviewed
13 exact source mentions. Full original text, times, speakers and all other
segment metadata stay separate and unchanged. Only exact source name slices are
masked; the article excluded by the normalizer remains ordinary source text.
Input reconstruction must equal the original exactly before any later model
request.

`<x` is a reserved namespace. The source is rejected before masking if that
prefix occurs, including NFKC/casefold/format-character-equivalent spellings.
Generated tags are checked for collision and uniqueness. The namespace check
is deliberately conservative: real source markup or mathematical text beginning
with `<x` would also be refused. There is no automatic alternative namespace,
escape, source rewrite or retry in this candidate.

The strict JSON schema, exact once-only tag accounting in the same original
segment, unknown/malformed-prefix rejection, map integrity, source-exact
restoration and final production translation guard all remain in place.
`<x0 />`, `<X0/>`, a missing tag, a duplicated tag or a tag moved to another
entry fails rather than being normalized or repaired. Ordinary prose may
reorder naturally around intact tags; the code cannot certify that the model
assigned the right actor to each role. The existing independent meaning gate
therefore remains mandatory.

Tags are **request-local**, not globally unique. Two different requests can
both contain `<x0/>`; their source/map hashes and actual request bindings differ.
The later execution wrapper must continue to compare its exact original source,
fresh source-derived bundle and actual native request with the frozen mapping
for that case. The tags alone do not authenticate the meaning of a response
from another request. This tradeoff is explicit, and a new no-model control
checks the different external bindings rather than claiming global tag identity.

## Offline checks completed

All **25** generic source/marker/schema/guard controls passed. These include
collisions, repeated mentions, missing/altered/duplicated/cross-segment tags,
source and map corruption, inflected/decomposed original spellings, exact
metadata preservation, final production guards and strict JSON failures.
The within-segment actor reversal and request-local identity examples remain
limitations even when structural checks pass. The normalizer's article-like
name, undotted initial and residual-prose counterexamples also remain unchanged.

All six original protected inputs reconstruct exactly and fit the unchanged
1,000-byte single-request input limit. Their JSON source sizes are **203, 286,
217, 292, 172 and 286 bytes**. No source segmentation, context cropping or output
budget increase is proposed.

The existing pinned official tokenizer was loaded locally without model
weights or native API calls. Before estimating new prompts, its entire token
vectors matched all six retained actual native prompts using the observed
single-BOS policy. It then counted the new complete messages inside the retained
native wrapper. These are **reference-tokenizer estimates**, not newly observed
native counts:

| Original case | Previous native prompt | New prompt estimate | Remaining after 2048 output + 1 end token |
| --- | ---: | ---: | ---: |
| Transcription terminology | 229 | 203 | 1844 |
| People and roles | 323 | 222 | 1825 |
| Amounts | 223 | 217 | 1830 |
| Negation | 229 | 206 | 1841 |
| Conditional publication | 276 | 206 | 1841 |
| Uncertain question | 228 | 205 | 1842 |

Every proposed tag in these sources encodes to three ordinary tokens and none
of the verified native BOS/EOS/turn-boundary IDs. Actual runtime rendering,
complete source binding, token accounting and cleanup would still be required
before any later generation. The estimator took 1.030 seconds with 223.8 MiB
process peak RSS; it loaded no language model and made no network request.

## Proposed later experiment, not executed

If root authorizes it after review, use exactly the original six development
cases once, in the same order, with the same source/meaning criteria. Reuse the
existing official Krikri Q4_K_M model, Ollama 0.40.12, temperature 0,
`think:false`, context 4096, output cap 2048, four CPU threads, 240 seconds per
request, 600 seconds per case, 1800 seconds total, 6144 MiB externally monitored
process budget and at least 1 GiB disk reserve. The detector remains unloaded.
The reviewed worker/observer and native verifier can be reused with only new
paths and these frozen inputs; any adaptation must be bound and reviewed.

Retain complete native raw content before any guard, then independently review
raw and restored meanings. Stop on the first execution, schema, marker,
resource or cleanup failure without repair or retry. There is no change to the
original acceptable/minor/major thresholds. A name kept in its original script
is allowed under the existing rule; ordinary prose and full facts still must
be translated faithfully.

**No new model loading, native preparation or generation is authorized by this
preparation bundle itself.** No such operation was performed. No new runner for
native execution is included. Expanded or fresh validation, summaries,
whole-app approval and production integration remain outside this proposal.

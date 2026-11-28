# Bounded native marker-grammar proposal

**Ready for source review; native conversion and generation remain unauthorized.**
The previous source-spelling screen remains rejected: its first translation was
acceptable, its second removed every marker and substituted names, and four
cases were not run. This proposal changes the mechanism that constrains output,
while preserving that screen's exact six complete inputs and all meaning rules.

## Exact candidate change

Change only each existing request's `format` object. Keep both messages, the
separate exact source-spelling context, all source text/metadata, model,
temperature, context, output limit, threads and compact restoration code intact.
The historical translation adapter remains the execution reference. The current
production file has three separately approved summary-example removals;
`current-source-observation.json` and its patch record that fact without making
the live file a dependency of this historical translation comparison.

The schema uses the pinned converter's older array-valued `items` tuple. Each
position has an anchored string pattern derived only from that entry's marker
IDs. All permutations of those IDs are alternatives, with free generated prose
before, between and after them. Every alternative includes each ID once.
No spelling, name lexicon, gender, role, criterion or expected translation is
inserted into the schema. The exact source-spelling map already present in the
previous messages is unchanged.

The fixed profile accepts **two original entries and at most three markers per
entry**. It refuses inputs outside that scope; it does not split, crop or select
another profile. The six cases contain 1/0, 3/3, 0/0, 1/0, 2/2 and 1/0 markers.
The largest entry has six order alternatives. This is no long-transcript or
deployment claim.

| Source order | Marker counts | Schema bytes | Prior native prompt tokens | Remaining tokens after full 2048 output + one terminal |
| --- | --- | ---: | ---: | ---: |
| 1 | 1, 0 | 380 | 261 | 1786 |
| 2 | 3, 3 | 3179 | 350 | 1697 |
| 3 | 0, 0 | 313 | 262 | 1785 |
| 4 | 1, 0 | 380 | 266 | 1781 |
| 5 | 2, 2 | 943 | 302 | 1745 |
| 6 | 1, 0 | 380 | 264 | 1783 |

These token counts are retained observations of the identical prior messages,
not new tokenization or conversion results. The schema is not appended to those
messages. Actual complete native rendering and accounting must still be
observed for the new stage, including its effective date/BOS/template framing.

## What was checked without a model

`build_preparation.py` verified the complete preceding failure manifest and
source/map bindings, constructed the six proposed requests, and confirmed that
only `format` changed. It also wrote a **285-case raw JSON acceptance matrix**:
all tag-order combinations, fixed tuple arity, missing/duplicated/unknown/moved
tags, opening/closing residues, JSON quoting and short escapes, hidden escaped
tags, invalid documents, and documented structural-versus-meaning limits.

An independent small character scanner and Python regex evaluation agree with
all 285 declared expectations. Fourteen construction controls reject invalid
IDs, over-limit layouts, changed source/metadata/spellings, weakened schemas and
unsupported keywords/patterns. These checks test the proposed language and its
input binding; **they do not execute or certify the native converter**.

Eighteen additional controls use the unchanged frozen compact guard. They show
that normalization-lookalike marker residues still fail the postguard, while
exact marker accounting can accept synthetic prose with unsupported claims.
The initial default-Python command lacked the existing `regex` dependency; its
failure is retained. The unchanged helper then passed under the already
declared isolated interpreter. No package, model or candidate source was
changed to resolve that control environment issue.

## Required separate native gate

Source inspection establishes the supported route but also exposes a concrete
failure mode: unsupported patterns can become unrestricted strings with only a
warning. General JSON-schema libraries and Python regex matches are therefore
insufficient evidence.

Before any generation, root would need to authorize and review a **zero-output
native converter/preflight stage**, with these requirements:

1. Resolve a reproducible validator built from the same pinned native grammar
   parser. The official `test-gbnf-validator.cpp` consumes raw UTF-8 using
   `llama_grammar_init_impl(nullptr, ...)` and needs no model vocabulary. The
   validator is not in the retained Ollama distribution, and no build or new
   source acquisition is authorized by this proposal. Its final executable,
   build inputs and behavior must be independently bound before use.
2. Use the already pinned owned Ollama/native runtime. Extract each exact
   schema's actual GBNF through the existing empty-prompt, `n_predict:0`,
   `json_schema`, `response_fields:["generation_settings/grammar"]` route.
   The query bodies are frozen separately. No source prompt is evaluated or
   translated by these conversion queries.
3. Preserve the complete returned grammar and converter diagnostics. Reject
   empty grammar, a different backend, unrestricted-string fallback, any
   unsupported-pattern warning on a real schema, or source/runtime drift.
   Also require the exact approved schema object at the observed request
   boundary; no extra or ignored keywords can be supplied later.
4. Feed **all 285 frozen raw JSON probes** to the actual emitted grammars with
   the pinned native validator. Require every positive and negative expectation
   to match. The official validator returns exit code zero even for rejected
   input, so the gate must read its explicit acceptance/rejection result and
   treat ambiguous output or initialization errors as failure.
5. Run one separately labelled unsupported-lookahead sentinel with no model
   generation. If the converter refuses it, retain that closed failure. If it
   falls back, the missing-marker probes must make the enforcement gate reject
   that grammar. This tests the gate's ability to detect the documented silent
   weakening; the sentinel is never a candidate profile or model request.
6. Bind the six complete native message renderings and token vectors. Keep the
   exact 4096 context, 2048 output, temperature zero, non-thinking mode, four
   threads and 6144 MiB externally sampled process-group limit. The existing
   initialization/preflight limits and at least 1 GiB disk reserve still apply.
   Record every actual load, grammar call, resource sample, unload and cleanup.

The exact native setup helper, validator acquisition/build method and phase
authorization must be reviewed before this stage. Until those are concrete and
approved, no native call is ready to run. There is no implicit request to
download a new model, change an installed runtime or enlarge any budget.

## Conditional translation stage

Only after the native gate and an independent review pass could root authorize
one original-six screen. It would reuse the exact existing adapter, source
projection, compact guard and observer, adding the bound schema after source
projection and before native request observation. Raw output is retained before
all guards. Require normal stop, the actual prompt count, complete strict JSON,
same-entry once-only tags, exact source-derived restoration, unchanged metadata,
and the existing post-restoration production guard. Stop on the first
operational failure; no retries, response repair, alternate schema, detector
rerun or new source exposure. A completed structurally valid run still requires
independent review of every original meaning criterion.

## Limits that remain decisive

The free-text gaps operate on serialized JSON bodies. They allow literal
Unicode and standard short escapes, but exclude raw `<` outside required tags
and all `\\uXXXX` escapes. This prevents escaped tags bypassing literal marker
accounting. Ordinary angle-bracket prose is outside the bounded profile; it
must not be silently rewritten or dropped. Actual JSON escaping must be tested
against the native grammar. Unicode normalization-equivalent marker prefixes
can still reach, and be rejected by, the unchanged broader postguard.

Exact marker counts cannot preserve pronouns, gender, roles, negation,
quantities, dates, conditions or ordinary wording. Tag-only output can satisfy
the grammar. Extra unmarked names and omitted meaning remain possible. All tag
orders are permitted, so the grammar also cannot prove within-entry actor
relationships. The previous detector-boundary ambiguity and absence of
unattended protection approval remain unchanged. Grammar construction,
validation, runtime overhead and translation behavior have not been measured.

## Primary source basis

The sealed feasibility record binds Ollama
`f067033f9126993b6172bdfffa71a74ad693fda4`, its `b11901` pin, and llama.cpp
`5320c87ff0d994845b44ce7976f10055ec697447`.

- [Ollama schema extraction and routing](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llm/llama_server.go#L1480-L1540)
- [Native tuple parser](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema.cpp#L186-L220)
- [Native pattern fallback and conversion](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema-to-grammar.cpp#L414-L655)
- [Native tuple emission](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema-to-grammar.cpp#L944-L982)
- [Official model-free raw-character validator](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/tests/test-gbnf-validator.cpp)

The validator source was read, not executed or compiled. No native converter,
tokenizer, detector or model was called in this preparation, no new runtime or
weights were downloaded, no production file or previous evidence was changed,
and fresh validation remains unopened.

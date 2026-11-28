# Marker-constrained decoding: source-only feasibility

**Decision: a bounded candidate is technically supported by the pinned source.**
Use fixed-position array schemas and anchored marker patterns to constrain each
translated string during decoding. The actual emitted grammar and its acceptance
language have not been tested. This note authorizes no execution or production
change.

## What the pinned implementation supports

Ollama 0.40.12's frozen source commit selects llama.cpp `b11901`, resolved to
`5320c87ff0d994845b44ce7976f10055ec697447`. Its `format` schema reaches the native
converter on both completion and chat paths. The retained local Ollama routing
source matches the pinned Git blob. [Ollama pin](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/LLAMA_CPP_VERSION)
· [Native routing](https://github.com/ollama/ollama/blob/f067033f9126993b6172bdfffa71a74ad693fda4/llm/llama_server.go)

The parser accepts the older `items: [schema0, schema1, ...]` tuple form. Its
converter emits exactly one required child rule at each position and then closes
the array. This directly binds a distinct pattern to each original source entry.
Use this supported branch; modern `prefixItems` combined with `items:false` is
unsafe because this parser gives `items` precedence. [Parser](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema.cpp#L186-L220)
· [Tuple converter](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema-to-grammar.cpp#L944-L982)

Patterns support anchored literals, character classes, groups, alternatives,
repetition and hex escapes. Lookarounds, named groups and other unsupported
constructs can fall back to an unrestricted string with a warning. Therefore a
lookahead such as “must contain every tag” is not a reliable solution. Also,
`pattern` takes precedence over `minLength`; combining them does not establish
minimum prose content. [Pattern converter](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/json-schema-to-grammar.cpp#L414-L655)
· [Documented limitations](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/grammars/README.md#L203-L223)

The native sampler applies the grammar during token selection, including
resampling an otherwise invalid candidate. This supplies a mechanism beyond
the existing prompt instruction. [Sampling](https://github.com/ggml-org/llama.cpp/blob/5320c87ff0d994845b44ce7976f10055ec697447/common/sampling.cpp#L639-L686)

## One concrete bounded proposal

Keep the failed source-spelling profile's complete messages, source maps,
compact tags, model and settings. Change only its per-request response schema:

1. Give each original source entry its own tuple-item string pattern.
2. Build that pattern solely from the entry's already-bound marker IDs. List all
   tag-order permutations, placing model-generated text gaps before, between
   and after the required tags. Each alternative contains each tag exactly once.
3. Refuse more than three markers per entry. The six existing sources have
   per-entry counts `[1,0]`, `[3,3]`, `[0,0]`, `[1,0]`, `[2,2]`, `[1,0]`, so the
   largest current permutation set has six alternatives. This avoids forcing
   source word order and makes no scalability claim for long sources.

`illustrative-schema.json` is an **unexecuted, name-free example**. Its free-text
atom allows literal Unicode and ordinary JSON short escapes. It excludes raw
`<`, unescaped quotes/backslashes/control characters, and Unicode JSON escapes
that could hide an extra tag. The patterns target the converter's serialized
JSON-string grammar; quoting and escaping must be verified against the actual
emitted grammar, not inferred from a Python regex or general JSON validator.
Literal angle-bracket prose is outside this bounded profile and must not be
silently rewritten or dropped.

No names, genders, roles, translations or expected answers appear in the schema.
The model still generates all ordinary prose. The current exact marker,
metadata, strict JSON and post-restoration production guards remain unchanged.
Normalization-equivalent malformed prefixes may still reach those guards and
be rejected; the grammar does not replace their broader namespace checks.

## Required next gate and remaining limits

Before any generated translation, separately authorize a measured zero-output
inspection of each actual native grammar. Reject missing positional rules,
unsupported-pattern warnings, unrestricted-string fallback or an unexpected
grammar backend. Independently verify positive and negative strings covering
all allowed orders, missing/duplicate/unknown/cross-entry tags, array lengths,
quotes, backslashes, short escapes, hidden Unicode-escaped tags and truncation.
The pinned Ollama source exposes a native schema-grammar query, but it was **not
called** in this investigation. Actual prompt/source/token and resource checks
would still be required under the unchanged 4096/2048/four-CPU/6144-MiB limits.

Even perfect marker enforcement permits tag-only output, wrong pronouns,
swapped roles, missing conditions, incorrect quantities or extra ordinary names.
It cannot certify translation meaning, fix detector/normalizer ambiguity or
turn a localized name into an accepted result through repair. Grammar overhead,
timeouts and output-cap failures remain unmeasured. Full independent meaning
review and all original criteria must remain decisive.

Only retained source and official pinned primary text were read. No model,
tokenizer, native endpoint, converter or validator was executed; no software or
weights were downloaded; no production file or prior failed bundle was changed;
no fresh validation was opened. `findings.json` retains exact source identities,
the bounded design and these qualifications.

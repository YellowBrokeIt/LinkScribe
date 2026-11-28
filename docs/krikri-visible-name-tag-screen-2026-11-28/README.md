# Visible-name paired-tag screen: rejected at the first case

The one authorized development stage generated **one response**, then stopped
at the first whole-span integrity failure. The model kept the opening/closing
tags but changed the visible source name inside them:

| Expected whole source span | Actual raw span |
| --- | --- |
| `<x0>Maria</x0>` | `<x0>Mαρία</x0>` |

The first character of the actual name is Latin `M` (U+004D); the remaining
characters are Greek α, ρ, ί, α (U+03B1/U+03C1/U+03AF/U+03B1). This differs from
the exact Latin source string. The frozen guard rejected the complete pair
before wrapper removal. **No restored or accepted final translation exists.**
There was no name correction, replacement from the source map or retry. The
five remaining original cases were not run, as required by the frozen
first-operational-failure rule.

This candidate is rejected for failure to satisfy its predeclared copying
protocol. The unchanged semantic rubric permits reasonable transliteration;
that does not waive this candidate's stricter verbatim requirement or permit
repair. Raw wording and accepted application output are assessed separately.
The independent completed-output review is the authority for the raw response's
meaning classification; no automatic pass or source-name accounting substitutes
for that review.

Root's completed independent review confirms the rejection and preserves the
successful raw facts: the text file was saved, the original recording was not,
transcription took 12 minutes, and Greek translation had not started. It does
not grade the five unrun cases. The exact archived review is
`independent-root-independent-failed-output-review.json`, SHA256
`5c8787f23ae3a68785db1b84e4f83a45497e57e7d5edc9f0f1d869c8f8806858`.
It independently verifies all 99 frozen bindings, the actual request/raw
response/native preflight, guard rejection, all 303 resource samples and owned
cleanup. Its audit script and pre-output source/criteria snapshot are retained.

## Actual response and preservation

The complete raw response, including its unchanged JSON representation, is
retained in both the original evaluator report and its protection companion.
The first raw string contains `Η <x0>Mαρία</x0> …`; the second discusses the
12-minute transcription and translation not yet started. The final response is
not silently altered to make the experiment pass. The codepoint explanation in
`first-case-exact-name-failure.json` records the exact source and observed
strings without any model call or output repair.

The case completed with a **normal stop**, empty reasoning, **231 prompt tokens
and 65 output tokens**. Its actual request and prompt count matched the frozen
full native preflight. It did not reach the 2048-token output limit. The
whole-span check raised the retained `ValueError`; the final guard against the
restored original source was not reached because no restoration was accepted.

| Original case | Executed status |
| --- | --- |
| Transcript terminology | One normal raw response; exact inner-name copying rejected |
| People and roles | Not run |
| Amounts | Not run |
| Negation scope | Not run |
| Conditional publication | Not run |
| Uncertain question | Not run |

The proposed benefit for pronouns and grammatical agreement therefore remains
unestablished. In particular, the negation case that failed the previous empty
tag profile was not reached. Neither that earlier rejection nor any other
baseline is regraded.

## Fixed profile and verified setup

The candidate was independently reviewed before any native work. It retains
the original six complete development sources and criteria, actual retained
PERSON spans and unchanged source-only boundary normalizer. Each name remains
visible inside its own paired exact-copy tag. Whole source/map hashes,
once-only same-entry counting, unknown/open/closing/nested/crossing tag
rejection, strict JSON, exact metadata and the unchanged production guards
remain active. A changed inner name cannot be repaired; successful removal can
only strip wrappers around already-exact response text.

The model remains the official Krikri Q4_K_M payload, SHA256
`e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f`,
with verified Ollama 0.40.12, its selected native template and ordered stops.
Temperature 0, non-thinking mode, four CPU threads, context 4096, maximum output
2048, a 240-second request timeout and all prior process/time limits remain
unchanged. No detector was loaded, and no model, runtime package or new weights
were downloaded.

The zero-generation setup completed once in **22.218790 seconds**, with
**212 complete samples**, peak **RSS 5502.5 MiB / PSS 5493.3 MiB**, acknowledged
unload, empty resident models and successful owned cleanup. All six full native
renders and every token matched the prior complete-message estimates:
**231, 284, 240, 236, 251, 234**. Each reserved all 2048 output tokens plus one
terminal token within the 4096-token context. Source cropping was unnecessary
and prohibited. Root's independent native audit verified all 82 plan bindings,
92 completed setup bindings and all 212 samples before authorizing generation.

## Measured failed generation phase

The one-response phase took **36.034252 seconds**, with **303 complete samples**
and peak summed **RSS 5545.0 MiB / PSS 5536.1 MiB**. No measured resource or time
limit was reached. The worker exited **1**, and the supervisor's `passed:false`
remains preserved because the operational guard failed. Resource measurements
were complete; explicit model unload, an empty resident-model list, owned
daemon shutdown and process-group cleanup all passed. Free disk after the
phase was **1,672,527,872 bytes**.

The limits remain 6144 MiB sampled owned-process RSS, 180 seconds for
initialization, 600 seconds per case and 1800 seconds total. All sequential
samples are retained. These samples may miss transient peaks and do not
establish whole-app or whole-machine memory fit.

## Immutable evidence and scope

The runtime plan is SHA256
`8878b61813184629abb2ffb4814d250fe85f05e8f2a94be09065c5854e32ac74`.
The actual native setup freeze is
`6898861ce1ded9d8233fb123a50b65e39d0340934e63ae5a5d0624d8f6d2128d`;
the pre-generation freeze is
`d08480222ac83a11cc6aa1cb181a67bb000ff3ef2c5967755327658765c1d069`.
All 99 pre-generation bindings were rechecked unchanged after the failure.
Original responses, execution records and sample series remain untouched.
All eight earlier evidence bundles referenced by this plan were also rechecked
unchanged. The independent review's initial default-Python `regex` import error
is preserved separately; using the already declared virtual environment
resolved that review-only issue without a model attempt, dependency change or
alteration to the actual failed application response.

`runtime-preparation.md` and the plan's initial authorization/status fields are
historical records from the code-only stage. They remain frozen. The later
authorization files and actual setup/execution reports separately record the
authorized progression. The separately reviewed source-only preparation remains
immutable at manifest
`3a27888d2e84ee6a9e88e2cb77b68abb5bd13699348a6bb981726e8aad63e1b8`.

No second marker variant, model retry, expanded or fresh validation, summary,
whole-app test, default switch or production integration followed this failure.
The detector/normalizer ambiguities, inflected-name grammar and limits of
within-entry role/pronoun checking remain. This experiment gives no unattended
name-protection approval.

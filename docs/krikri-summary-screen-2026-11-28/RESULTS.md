# Rejected original direct-summary screen

The English case was executed once and rejected by the independent meaning
review. **Greek was not run.** The original preparation README, adapter, prompts,
sources, criteria, plan, native records and raw output remain unchanged.

The native/runtime contract passed: the actual 384-token English prompt matched
the complete native preflight; the model returned 135 tokens with a normal stop,
the app accepted the structured object, unload was acknowledged, and all owned
processes stopped. Those mechanical checks do not approve the content.

## Independent findings

The returned `summary` field is exactly **“concise factual summary”**, copied
from an example value in the original system prompt. It contains no source
facts. Eight substantive key points do not supply the missing paragraph.

The last point also weakens the source requirement to check **each quotation
with its speaker** before publication into generic verification of speaker
permissions. That specific check was already required by the unchanged source
and review criteria. The independent review records two material findings in
one rejected case; it does not introduce a new criterion.

The points otherwise preserve recorder ownership, operation and return roles;
the 12/8/4 interview and permission categories; the corrected €84.75 equipment
budget rather than €847.50; the pending Friday room confirmation; and the fact
that no interview has occurred. The chapter topic is source-grounded and starts
at the authentic 0.5 seconds. The complete raw and delivered output remains in
`english.json`, and the independent review retains the full judgments rather
than just a pass/fail label.

## Actual execution

| Phase | Generation calls | Wall time | Complete samples | Peak owned RSS / PSS |
| --- | ---: | ---: | ---: | ---: |
| Native preparation | 0 | 20.262521 s | 193 | 5493.4 / 5484.2 MiB |
| English | 1 | 47.673790 s | 387 | 5578.5 / 5569.6 MiB |
| Greek | 0; unrun | — | — | — |

Total measured model-stage time was 67.936311 seconds. Both executed phases
unloaded the model, verified an empty resident list, exited with code zero and
stopped all owned processes. Complete raw native traces and resource streams
are retained. The sampled resource result is not full-application approval.

`independent-english-meaning-review.json` binds the exact output, resource stream,
original criteria and prior authorization. It sets
`approved_to_run_greek: false`. There was no retry, output repair, model change,
production change, criteria relaxation or fresh validation.

Any later removal of example JSON values belongs to a separately frozen
prompt-only candidate. This rejected baseline is not regraded by that follow-up.

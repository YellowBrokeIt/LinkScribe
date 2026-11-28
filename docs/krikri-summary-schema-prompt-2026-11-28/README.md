# Summary schema instruction: one prompt-only preparation

This is a **source-only candidate**, prepared after the original Krikri English
summary was independently rejected. No native preparation, model load,
tokenization or generation has run for this candidate. Root must independently
review the exact new sources before authorizing any actual phase.

## Observed problem and unchanged baseline

The original returned summary paragraph was the literal example value
`concise factual summary`. Its key points also weakened the required check of
each quotation with its speaker into generic permission verification. The
original English output remains rejected and Greek remained unrun.

The complete prior stage, including that independent decision, is sealed in
`docs/krikri-summary-screen-2026-11-28/evidence-manifest.json` with SHA256
`be5bbd6ad8ac62fced8eb072c2fd8c4847db7e74e38b80fb9c396e9ac5a6847a`.
The new preparation does not modify, repair or regrade it.

## Exact proposed correction

The existing structured schemas already specify the response fields. The
candidate removes example **values** from three system-prompt endings:

| Existing path | New ending |
| --- | --- |
| Direct summary | `Return only JSON matching the supplied schema.` |
| Excerpt notes, without a structured schema | `Return only JSON with the string fields notes and chapter_title.` The literal prompt puts backticks around the field names. |
| Final summary of notes | `Return only JSON matching the supplied schema.` |

The note-reduction prompt already names its single `notes` string field without
example content, so it remains unchanged. `prompt-only.patch` is the complete
minimal diff against the rejected context-4096 adapter. There is no new factual
instruction, case name, quotation, name dictionary, reference answer or output
repair. Removing example values is a hypothesis about the copied filler; it
does not establish that either material error is repaired.

The entire application AST matches the original after exactly these three
literal replacements. All schemas, grounding and language rules, maximum point
count, source chunking, output validation, chapter construction and unload logic
remain unchanged. Translation code is untouched. Production files are not edited.

## Original inputs and actual request capture

The same two exposed development cases and their original review criteria are
copied byte-for-byte. English remains first. The complete timestamped excerpts
are still 957 and 1618 UTF-8 bytes; the authentic chapter start remains 0.5 seconds.

`request_contract.py` captured the actual decorated application requests with
network connections blocked before any native transport. For each of the two
complete requests, the **only changed path** is the system-message content
described above. User source, model, JSON schema, temperature 0, `think:false`,
context 4096, output cap 2048, four threads, 240-second timeout and exact unload
request are unchanged. The capture provides no new native token count. A new
complete native render/token check remains required before generation.

`check_prompt_only.py` verifies the sealed prior stage, exact whole-adapter AST
difference, copied source/criteria and request changes. Its result is retained
in `prompt-only-verification.json`.

## Reused execution gates

The phase controller, resource observer, native session/preflight, raw-response
observer, English-before-Greek semantic gate and nine no-model controls are
byte-identical to the reviewed original implementation. `context.py` changes
only the private log directory. The new phase directory has no authorization
receipts or execution artifacts.

The previously reviewed runtime contract remains:

- Separate zero-generation preparation, one English call, and—only after a
  successful independent English meaning review—one Greek call. No automatic
  next case, retry or output repair.
- Actual selected-model template/stops/BOS/full request token vectors; the
  complete prompt plus all 2048 output tokens and terminal reserve must fit
  4096. The actual generated-response prompt count must match the preflight.
- Full raw native envelope, raw summary fields and actual delivered paragraph,
  every point and chapter retained before any rejection.
- Four CPUs/threads, 6144 MiB sampled owned RSS, full RSS/PSS samples every
  100 ms, 180-second initialization, 240-second request, 600-second case and
  900 seconds cumulatively across this candidate's measured phases. Review idle
  time is excluded because no owned model remains resident between phases.
- At least 1 GiB free disk; exact existing model/runtime only; no downloads,
  imports, installations or cache cleanup; explicit unload, empty resident list
  and stopped owned process group.

Root independently authors the same phase authorization, native setup review
and English semantic receipts specified in the original preparation README.
Every receipt must bind **this new plan and these new actual reports**. No prior
approval is reused as execution approval for the changed prompt.

## Source-only validation and scope

The exact prompt-only comparison and all nine unchanged model-free controls
pass. Tests preserve malformed JSON and rejected native-render observations,
reject missing review/budget/cleanup gates and retain a returned summary even
when the synthetic unload acknowledgment fails. That deliberate fake failure
prints the existing cleanup warning; no real model is involved.

This preparation is one concrete response to observed prompt filler, not a
prompt search. Its three literal changes include notes/final paths, but the
proposed actual screen remains only the two original direct-source cases. There
is no long-summary result, fresh validation, application integration, semantic
approval or production/default-model change.

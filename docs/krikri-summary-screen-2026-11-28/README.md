# Krikri direct-summary screen: executable preparation only

This directory prepares the two-case experiment proposed in
`docs/krikri-summary-feasibility-2026-11-28`. It contains **no native setup,
model loading, tokenization, generation or semantic result**. The runner author
has not approved execution. Root must independently review this implementation,
then separately authorize each measured phase and provide the required receipts.

## Fixed application path and inputs

`enhancements-context4096.py` is byte-identical to the original Krikri baseline
adapter. Its only change from the published production snapshot is context 8192
to 4096. The actual decorated `summarize_segments` function supplies the complete
source, original grounding/language instructions, structured schema, output
validation, chapter construction and final unload. No name tags, detector,
normalizer, citation prompt, repair pass or translation path is used.

The first two original, already-exposed summary development cases remain exact:

| Phase | Original case | Complete timestamped excerpt |
| --- | --- | ---: |
| English | `summary-en-consent-and-roles` | 957 UTF-8 bytes |
| Greek | `summary-el-workshop-counts` | 1618 UTF-8 bytes |

Each source contains four timed segments and follows the existing single direct
summary call. The authentic chapter start is 0.5 seconds. Source objects and
review criteria are separate, byte-identical copies of the feasibility inputs.
The code hashes criterion-containing files for integrity, but does not parse
their answers or supply them to the model. No unused validation input is read.

`request_contract.py` captured both actual application requests with all network
connections blocked and a transport sentinel before any native call. It records
the exact system/user/schema/options and application unload request in
`expected-requests.json`. No synthetic summary was supplied during that capture.
Native prompt token counts are **not yet known**; UTF-8 fit is not a token-budget
claim.

## Three independently gated phases

`run_native.py --phase prepare` would run zero-generation render/token preparation
for both full requests. It verifies the complete existing official GGUF and
native descriptors, exact template/stops, no imported persona/projector/draft,
runtime identity, context 4096 and four native threads. The complete rendered
prompt and native token vector must have exactly one BOS and leave room for all
2048 output tokens plus one terminal reserve. Every render/token response is
checkpointed before validation, including a failed preflight. The owned model
must unload, the resident-model list must be empty, and the owned daemon/group
must stop.

After independent review of that actual setup, `--phase english` would make
exactly one real direct summary call. Before that call it repeats the complete
native preflight and requires equality with the reviewed rendered prompt and
token vector. The actual response prompt count must equal this complete count.
The full returned native JSON envelope and exact final content string are saved
before the app validates the content. This is the parsed native envelope, not
HTTP wire bytes; an invalid envelope's `JSONDecodeError.doc` is retained when
available. Transport errors without returned bytes are reported honestly.

The report retains the raw summary object and the actual delivered paragraph,
all key points and chapter. Existing app edge trimming and its 120-character
chapter-title bound remain unchanged and are compared explicitly with the raw
object. Missing, duplicate or unexpected JSON fields fail this declared
structured-response contract. A valid returned summary is still retained when
unload fails. No output repair follows any failure.

The English process exits and the model unloads before meaning review. The code
never queues Greek. `--phase greek` requires a separate, hash-bound independent
English decision covering the paragraph, every point and chapter against the
unchanged original criteria. It must report zero major errors, all original
criteria satisfied and explicit permission to run Greek. A missing or empty
execution check set, changed report hash, failed resources, incomplete review,
self-approval or English material error blocks Greek. If authorized, Greek uses
its already-frozen source and the same one-call profile once.

## Runtime and resource contract

Reuse the verified official Krikri Q4_K_M payload and Ollama 0.40.12. No new
download, cache deletion, native import/create or installation exists in this
runner. The exact existing Python interpreter is named in the plan. Each phase
starts its own owned daemon; an occupied loopback port 11434 refuses startup.

- Four CPU affinity slots and four native threads; temperature 0, `think:false`,
  context 4096, output cap 2048, unchanged structured schema and 240-second app
  transport timeout.
- 6144 MiB sampled aggregate RSS for the observer, worker and all owned native
  descendants; complete RSS/PSS samples are retained every 100 ms. Shared pages
  may be counted more than once in RSS, and transient peaks can occur between
  samples. This does not measure full-app/browser/system headroom.
- 180 seconds for initialization and 600 seconds per source case. A final
  observed initialization-time check and worker case-duration check complement
  the sampled deadlines.
- **900 seconds cumulatively across preparation, English and any Greek phase**.
  Completed external resource reports determine the remaining allowance; an
  invocation cannot reset it. Time waiting for independent human/agent review
  is excluded because no owned model process remains resident during that wait.
- At least 1 GiB free disk before and after every phase. No retries or overwrite
  of a completed or interrupted phase. The copied orphan-safe observer cleans
  the owned process group even if a leader exits before a descendant.

`resource_monitor.py` is byte-identical to the previously reviewed compact-tag
observer; its prior process-tree controls are retained evidence, not a new
cleanup test. New final phase checks also require the correct result identity,
complete source order, exact generation count, successful unload, empty model
residency, unchanged sources and complete stopped owned processes.

## Required independently authored receipts

No receipt below is present at preparation freeze. The runner author must not
create self-approvals. Root can copy its independent reviews into this directory
and then write these small JSON receipts with companion SHA256 text files:

1. `<phase>-authorization.json` and `<phase>-authorization.sha256` name the exact
   phase and plan SHA, set `root_authorized` and `local_model_slot_reserved` to
   true and `runner_author_self_approval` to false, and bind an
   `independent_review_path`/`independent_review_sha256`. `files_sha256` maps
   repository-relative reviewed dependency paths to their exact hashes.
2. Before either generation phase, `native-setup-freeze.json` and its `.sha256`
   bind the plan, actual prepare report/resources/full samples and independent
   native review path/hash. The receipt records `generation_calls: 0` and
   `independent_native_review_approved: true`. Each generation authorization
   names this exact `native_setup_freeze_sha256`.
3. Greek authorization additionally binds `english_semantic_decision_path` and
   its SHA. That independent decision names the exact plan, English report,
   English resource report, source cases and original review criteria hashes;
   it records the original case ID, complete independent review, zero major
   errors, original criteria satisfied, paragraph/points/chapter reviewed and
   explicit `approved_to_run_greek: true`.

The concrete field checks are in `protocol.py` and `context.py`. These receipts
cannot substitute for the substantive independent reviews. Root sequences the
exclusive model slot; this source-only preparation grants no execution.

## Source-only validation and limits

Nine model-free controls pass. They exercise exact real request capture,
authorization identity/slot failures, the English semantic gate, shared budget
exhaustion, final completion/time checks, preservation of raw invalid JSON,
actual application trimming/title behavior, failed unload with a retained
summary, and a rejected native-render response retained before validation.
The fake unload test intentionally prints the app's cleanup warning; no real
model was involved. The original eight-control checkpoint is preserved.

The source reuse record and plan bind all implementation files. These controls
verify the harness contract; they provide no evidence that Krikri can summarize
either source accurately. Any later result remains a two-case exposed
development screen, not fresh validation, long-summary approval, application
integration or a default-model change. The earlier failed summary and
translation experiments remain immutable.

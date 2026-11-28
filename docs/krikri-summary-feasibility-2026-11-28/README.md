# Greek-specialist summary feasibility: source-only preparation

## Question and evidence boundary

The current default-model summary path still has material failures on the
existing English consent/roles case and on longer sources. Source-cited and
second-pass Qwen experiments did not resolve those failures. The already
available Krikri model has not been evaluated on this summary task. Its
translation results do not establish summary quality, but its existing verified
runtime makes one small, separate summary screen technically feasible without
another model download.

This directory is a **prospective preparation**, not a model result or execution
authorization. No summary workflow, native API, frontend, model or network call
was run. Only the production source-grouping functions were called, with network
connections forbidden, to check two already-exposed development inputs.

## Fixed inputs and unchanged criteria

Use the first two original cases from `tests/fixtures/summary_quality_cases.json`
(SHA256 `0b241fc12d8a86e4fab50ecb8a3371588c6e8bc67754c782fcc5ef996001c830`):

| Case | Complete timestamped input | Existing path |
| --- | ---: | --- |
| English consent and roles | 957 UTF-8 bytes | One direct source request |
| Greek workshop counts | 1618 UTF-8 bytes | One direct source request |

Each contains four original timed segments. The pure grouping check preserved
every source character and original segment object; both fit the unchanged
3200-byte summary input bound. The chapter start remains the original 0.5-second
start. [source-only-feasibility.json](source-only-feasibility.json) records the
source and application identities and exact excerpt hashes.

[The selected source file](selected-development-sources.json) contains only
case identity, source/preferred language and original segments. [Original review
criteria](selected-review-criteria.json) are retained separately. Important facts,
forbidden claims and expected answers are review material and must never enter
the model request. No fresh summary validation file was opened.

## Proposed later execution contract

Reuse the verified official Krikri Q4_K_M payload, revision
`3c1ce101a3e0d783a0f2223f212ccc35b4657532`, GGUF SHA256
`e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f`,
with the existing Ollama 0.40.12 runtime. Use the archived context-4096 baseline
adapter, whose only production request-policy change is context 8192 to 4096.
Do not use either name-marker instruction, detector, normalizer, source-cited
candidate, repair pass or output projection for this distinct task.

The actual `summarize_segments` direct-source path, grounding/language prompt,
eight-point schema, output guards and chapter construction must otherwise stay
unchanged. Keep temperature 0, `think:false`, 2048 output tokens and four threads.
An executable proposal must capture the exact full native system/user/schema
request, bind the runtime/template/model identities, and demonstrate that every
full prompt plus the complete output allowance and terminal reserve fits the
4096-token context before generation. Source-byte fit alone is not that proof.

Use an English-first screen. Retain one actual raw response before application
validation, every delivered paragraph/point/chapter, full request/token data,
source hashes and resource evidence. Unload the model and obtain independent
meaning review. If the first case has a structural/resource/cleanup failure or
major meaning error, stop without retry; the Greek case remains unrun. Only if
the English case meets the unchanged development criterion should the exact
already-frozen Greek case run once. Preserve normal application trimming and
validation; do not repair numbers, names, prose or JSON after a failure.

Proposed bounds are the existing 6144 MiB sampled owned-process RSS budget,
four-CPU affinity, 180-second initialization, 240-second transport timeout,
600 seconds per case and 900 seconds of total model-stage execution. Retain
complete resource samples and owned-process cleanup. Require at least 1 GiB
free disk, no new weights/downloads and no overlapping speech/detector/other
language-model residency. These are prospective limits, not new measurements.

## Review and next decision

Judge paragraph and key points together against the original important facts
and prohibited distortions. Check the actor/operator/owner distinctions,
permission scope, corrected quantities, assigned actions and conditional versus
completed events. Check the chapter title against its actual source and assess
requested language and useful condensation separately from factual fidelity.
Valid JSON, exact numbers somewhere in the result and a normal stop are not
semantic approval.

The complete executable, native setup and criterion binding need independent
review before root authorizes either model call. This preparation leaves the
current compact-tag translation and speech-timing work unchanged. It does not
authorize long summaries, remaining development cases, fresh validation,
application integration or a default-model change. The existing failed summary
experiments remain immutable.

# Future hosted speaker constructor contract

This is a new, source-bound preparation plan for the narrow checker correction
reviewed after the completed application run at `f2ebd04`. It does not claim that
a future hosted workflow has run or passed. The original run remains failed and
its complete actual evidence is preserved in
[the f2 archive](../hosted-speaker-f2ebd04-2026-11-28/README.md).

The unchanged production recognizer factory uses faster-whisper's constructor
default `cpu_threads=0`. Pinned CTranslate2 resolves zero through its normal
environment/default path. The controller already supplies the source-enforced
CPU-affinity and OMP/MKL limits. The corrected check expects the actual default
zero, while retaining the existing single initialization, single worker, CPU,
int8-family, source/model identity, full-waveform, time/memory, cleanup and
acoustic criteria. Effective native thread count and worker-side affinity
readback are not claimed as measured observations.

The maintained patch also updates the synthetic completion fixture from four
to zero and adds five negative cases for changed constructor, worker, device
and compute settings. The exact prior controller and failed report remain in
the closed evidence archive. Production application code is unchanged.

## New source binding

`tests/qa_speaker_integration.py` now defaults to
[hosted-plan.json](hosted-plan.json). All four plan references in the speaker
workflow, including the path trigger, point to this new file. The old d62 and f2
plans remain unchanged; they correctly reject current controller/workflow bytes
when treated as current-source preflights.

Only the maintained controller and workflow identities change among the 21
execution-source bindings. All corpus, model revision/file, runtime, decoder,
acoustic threshold and resource declarations are equal to the preceding plan.
[source-change-audit.json](source-change-audit.json) records the exact changed
identities and unchanged declarations. The new plan is parent-bound to the
historical f2 preparation plan, rather than replacing it.

## Local verification

- [Maintained hosted QA controls](focused-controls.txt): **35 passed in 0.46 seconds**.
- [Source validation](preflight/preflight.json): valid, with `model_constructed:false`
  and `inference_performed:false`.
- [Commands and source identities](local-verification.json): both commands exited zero.

No provider, model, recognition, alignment or speaker inference was performed
for this preparation. Publication and any future hosted invocation are separate
steps. The limited original fixture success and the open broader v1 quality
gates are unchanged.

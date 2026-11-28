# Native grammar controller preparation

This is source-only implementation of the separately frozen tiny validator and
zero-generation plan. It is **not authorized to acquire into the build root,
compile, call native libraries, load/tokenize with a model, or generate text**.
Each actual phase needs a root receipt bound to the final controller, independent
review and successful predecessor receipts. No generation phase exists.

The four proposed phases are `acquire`, `build`, `native_prepare` and `validate`.
The original six complete requests, seven zero-output schema queries, all 285
native probe expectations and all semantic criteria remain unchanged.

## Implementation

- `official-source-capsule.json` retains the already-read official connector
  text for source review. All 11 objects match the pinned byte counts and Git
  hashes. Only an authorized `acquire` phase may materialize those exact bytes
  into the still-absent owned build root; no new network dependency is needed.
- `execution_gate.py` and `run_stage.py` require exact root/review/source
  bindings, ordered completed predecessor reports and full sample hashes.
  Exclusive phase claims refuse retries. The worker verifies its actual
  controller parent identity and owned session before dispatching any action.
- `resource_monitor.py` reuses the previously reviewed sampler, process-group
  discovery and cleanup. Its only algorithm addition is an optional per-sample
  and final disk-policy callback. It records the 1 GiB free reserve, 64 MiB owned
  tree and 16 MiB file ceiling; `RLIMIT_FSIZE` also bounds child writes. All
  existing memory/time/child-survival checks remain in force.
- `phase_actions.py` verifies the source capsule and saved source bytes, runs
  the one exact frozen compiler command, verifies actual ELF/dependency/header
  receipts and the three model-free sanity cases, then later checks every
  frozen probe against the actual emitted grammars. It does not revise schemas
  or repair output. `process_io.py` retains bounded raw stdout/stderr even on
  timeout or capture failure. The unchanged strict status parser never treats
  exit zero or a loose `valid` substring as acceptance.
- `native_contract.py` allows only version/show, six complete render-only
  requests and their exact full tokenizations, seven ordered empty-prompt
  `n_predict:0` schema queries, and unload/resident checks. Normal chat
  generation, changed or repeated requests, import and downloads are refused.
  `native_actions.py` binds the actual owned PID/port/binary, preserves raw HTTP
  bytes before parsing, uses the existing verified native template/source
  helpers, and records explicit unload and group cleanup. The subsequent
  validator phase cannot start while native cleanup is incomplete.

The actual current home environment value is inherited unchanged only by the
native phase, matching the previously used daemon setup. It is never redirected
to a task directory. Compiler and validator commands use the frozen small
environment from the reviewed build plan. Logs use private file creation.

## Review and controls

`review-snapshots/acquire-build-v1` preserves the exact partial foundation root
read while the native actions were being finished. It is a read-only snapshot,
not a runnable directory. The final controller uses its live directory paths;
later changes are recorded separately rather than rewriting that snapshot.

`test_controller.py` is restricted to source data, pure contract checks and
harmless Python subprocesses. It blocks network operations, model/tokenizer
imports and non-Python executable launches. Controls cover missing root
receipts, altered source objects, exact validator status, attempted generation
and nonzero predictions, subprocess timeout/capture, disk constraints, measured
memory/time stops and a leader-exits/child-survives cleanup case. The actual 285
native grammar probes are **not** run by these source controls.

A source-control result, when present, records only that scope. It cannot approve
a build, prove a native grammar, establish translation meaning or grant runtime
authorization. Prior preparation, plans and rejected translations stay frozen.

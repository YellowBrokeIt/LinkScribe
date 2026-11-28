# Same weights, published legacy frontend diagnostic

This is a controlled test of sensitivity to the frontend version published with
the model. **It is not a fix for a proven implementation bug and is not approved
for production.** The once-only run has completed after the language agent released the shared
model slot and the independent pre-output contract review passed. Independent all-case review is complete: **four major errors, one minor issue
and three acceptable transcripts**. This candidate remains rejected.

The original int8 screen has four major semantic errors. The separate
[frontend comparison](../frontend-parity/README.md) found an intentional
NeMo-version difference between the normal runtime NumPy frontend and the older
model-supplied ONNX frontend. Exact model training/export version provenance is
not available, so neither frontend is declared ground truth.

## Frozen intervention

The [plan](plan.json) has SHA-256
`f9b47352771a31ee354640e2e534d58cf01685cea9cfda642a7ef93e1ba6a44c`.
The [helper](run_screen.py) has SHA-256
`411bcc94bc3776f3a727be480b8b5bf569b289c7e543697f778f158caabe7a72`.
The exact [patch from the original helper](helper.diff) is retained with SHA-256
`2c361a3c4307cfa0183fb85b2058a19c850ff874e5bf662f890ee622d0f9b3d6`.

Normal pinned runtime and int8 model construction remain unchanged. Before the
first recognition, the worker replaces only the uncalled NumPy frontend with a
small adapter that executes the exact existing `nemo128.onnx` file. It performs
no additional feature normalization, array edits or text repairs. Actual feature
tensors are checked against the complete saved output of the same published
graph. That earlier frontend-only comparison used one ONNX thread; this
recognition diagnostic preserves the original four-thread contract, so the
release's numerical tolerance is used and exact hash equality is also recorded.

All other inputs, runtime files, weights, source/target language handling,
timestamp behavior, semantic criteria and resource limits are unchanged. The
helper compares all original protocol fields and file pins before execution.
There are eight full clips, one model initialization and one attempt per clip,
with four CPU cores, a 2.5 GiB RSS bound, 90-second startup, 30 seconds per clip
and 300 seconds total. There are no prompts, language hints, VAD, crops, retries,
glossaries, postprocessing corrections or additional ASR weight downloads.

## Completed execution and independent rejection

The [raw report](results/recognizer-report.json) has SHA-256
`5cebad8176f649a43a17ced5efc6114d8fb27a9ffe6ac63a3e374903ff574f0e`.
The [controller](results/execution.json) recorded completion at
2026-11-28 01:58:03.327194 UTC, exit 0, **10.566833 seconds** total and
**1,462,734,848 bytes** sampled process-group peak RSS. Recorded worker peak was
1,462,198,272 bytes. Model initialization took 5.136743 seconds, recognition
summed to 3.640302 seconds, and the slowest clip took 0.713617 seconds. No limit
was reached, and the owned worker exited.

All eight complete input hashes and structural checks passed. All eight actual
legacy frontend tensors exactly matched the saved corresponding frontend-only
tensor hashes, including equal lengths and shapes, despite the thread-count
difference noted above. Raw token IDs, emission frames, native result objects,
sessions and every successful/failed check remain in the report.

The [paired observations](paired-observations-before-semantic-review.json)
preserve every exact baseline/candidate text and resource comparison. The
fairness case now retains its missing word; council-name, collision/three and
Lakkha/bhajans problems remain. The beer description now changes Number One to Nummer One, a new major identity
error under the original criteria, and omits the main-beer qualifier. Camping
remains a minor issue; the two previously clear English cases remain acceptable.

The [independent complete review](../independent-review/legacy-frontend-independent-review.json)
has SHA-256
`68614e0f4d6d6f9d87d03a8dc395e6e324d5a41b8095f1474ef617e90d74fc9b`.
Its [mechanical audit](../independent-review/legacy-output-binding-audit.json)
verified every full decoded array, vocabulary-to-text mapping, native frame time,
log probability, file pin and actual legacy frontend hash. Review classification
is **four major, one minor and three acceptable**, versus four major, two minor
and two acceptable in the original NumPy screen. Restoring one proposition while
introducing a new identity error does not justify adoption.

This establishes sensitivity to the published frontend version. It does not
establish that the old frontend is correct for training/export, that quantization
is the remaining cause, or that the model family has been evaluated in its
original NVIDIA runtime. No further inference or full-precision download was
performed.

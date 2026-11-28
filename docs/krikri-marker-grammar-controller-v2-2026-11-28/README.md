# Native grammar controller: final phase-time enforcement

This separate source-only revision closes the independent review's concrete
late-finalization false-pass path. The original controller and its 57 controls
remain sealed in `../krikri-marker-grammar-controller-2026-11-28`.

Only the observer's finalization changes: elapsed time is taken after owned
cleanup and the final storage check, and an elapsed time beyond the existing
phase limit makes the phase incomplete and unsuccessful. An existing failure
reason is retained. Requests, source files, the 285 native probes, all budgets,
receipt enforcement and the rest of the executable controller are unchanged.

The paired harmless regression uses the same instant-exit Python child and a
bounded 1.25-second cleanup delay under a 1-second toy phase limit. It retains
the original observer's late success and the revised observer's rejection.
The unchanged source-control suite checks for regressions in all prior guards.
Neither control runs a compiler, native library, converter, tokenizer or model.

No actual phase is authorized by this revision. Separate root receipts and
independent executable review are still required before acquisition, compilation,
zero-generation native preparation or native grammar validation. No generation
phase exists. The actual owned build directory remains absent before controls.

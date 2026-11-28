# Source-spelling context: isolated runtime preparation

This directory prepares the single compact-tag profile already described in
`docs/krikri-source-spelling-context-2026-11-28`. **No native preparation,
model load, tokenization or translation generation has run in this stage.**
The parent authorized source-only runtime preparation. Independent source
review and a separate root receipt are required before either actual phase.

## Exact runtime delta

The compact adapter, `protection.py`, original six-case corpus, actual retained
detector spans, normalized compact source maps, production script guard and
resource observer are copied byte-for-byte from the rejected compact screen.
The existing baseline native preflight is reused without modification. The six
new expected request bodies and source-spelling maps are copied byte-for-byte
from the independently reviewed source-only proposal.

`source_context.py` reuses that proposal's exact `project_payload` function. For
each case it verifies the entire original source/metadata/map roundtrip, then
temporarily wraps the application's `_ollama` payload builder. The wrapper adds
only the already-reviewed generic instruction and the separate JSON array of
`tag` / exact source `spelling` records. The original builder then constructs
the native request. Consequently, the unchanged transport observer sees the
complete new request and must match it exactly against the frozen proposal.
No hidden transport mutation supplies the extra context.

The inference worker retains both original and projected application payloads,
the exact context map, its combined source-byte count, the full original source,
the actual raw native response, and any rejected/restored application output.
The payload builder is restored even if construction or translation fails.
Exactly one projection is allowed; a fragmented or repeated request is rejected
before its second builder call. A six-way length/order check binds original
cases, compact cases, protections, spelling maps, expected requests and actual
native preflights.

The original output contract is unchanged: strict JSON array shape; exact
once-only compact markers in their original source entry; no unknown, malformed
or closing-tag residue; unchanged metadata; exact source-slice restoration; and
the existing production guard applied again against the original source. A
source spelling returned in place of its marker is a missing marker and is
rejected. There is no localized-name correction, gender inference, role label,
external lexicon, output repair or retry.

The other worker/controller changes add explicit root receipt checks and report
the receipt identity. `context.py` changes only the private log directory. The
three worker diffs and private-path diff are retained for independent review.

## Inputs and fixed limits

Only the original six exposed translation development cases are in scope.
The original criteria and allowance for exact source-script personal names are
unchanged. The full source entries plus spelling data remain below the existing
1000-byte JSON input budget. Copied estimates are **261, 350, 262, 266, 302 and
264** full prompt tokens; this stage has not rerun a tokenizer or verified new
native counts. The future native phase must render all complete messages and
bind every actual token vector, with 2048 response tokens plus a terminal reserve
fitting within 4096. Generation must reproduce each reviewed vector/count.

The proposed native profile remains the exact existing Krikri Q4_K_M / Ollama
0.40.12 package, temperature 0, `think:false`, four CPU threads and four-CPU
affinity. The unchanged observer measures the supervisor, worker and owned
daemon/runner from loading through exit, with a 6144 MiB sampled RSS stop and
retained RSS/PSS samples. Limits remain 180 seconds for initialization, 240 for
each request, 600 per case, 600 for preparation and 1800 for the six-case screen.
Every phase requires at least 1 GiB free disk. There are no downloads,
installations, imports into the model cache, cache deletions or detector calls.

## Explicit phase receipts

`execution_gate.py` requires a root-authored `prepare-authorization.json` or
`infer-authorization.json` and its exact `.sha256` companion. The receipt must
name its phase, this exact plan, an exact independent review, reserved model
slot, `root_authorized:true`, and `runner_author_self_approval:false`. Its
`files_sha256` must bind the plan, context, gate, projection helper, workers,
controller and observer. Generation additionally binds both the reviewed
`native-setup-freeze.json` and final `inference-freeze.json`. The existing
inference freeze still requires independent native-contract approval.

No receipt is supplied by the candidate author. The controller and each worker
check the appropriate receipt before starting their work. No phase is started
automatically, and no current approval covers actual native or generation work.
Root will sequence any authorized phase with other model work.

## Source-only checks and limits

Eleven no-model controls pass. They capture all six actual application requests
before transport; reject altered spelling maps, source metadata, cross-case
bindings, partial sources, delimiter collisions, excess input bytes and repeated
builder calls; verify hook restoration on failure; and retain the existing raw
schema, closing-prefix, marker and post-restoration script rejection. The tests
also check missing/incorrect/self-approved phase receipts. Native subprocesses,
network operations and neural/tokenizer imports are blocked by an audit hook.
No translation answer is supplied in the six real-source captures.

A separate synthetic counterexample intentionally passes the mechanical marker
guard despite changing a pronoun and adding ordinary prose. Source-spelling
context may still be ignored, echoed, attached to the wrong role or produce
incorrect agreement. The detector and article-boundary normalizer's known
ambiguities remain. This preparation does not certify unattended protection,
useful translation, long passages, fresh validation, summary quality, full-app
memory fit, production integration or a new default. All prior failed profiles
and independent judgments remain unchanged.

# Visible-name paired-tag runtime: code preparation only

This directory prepares the existing measured Krikri runner for the separately
reviewed visible-name paired-tag profile. It contains **no new native setup or
generation result**. Root authorized this source-code adaptation while speech
holds the local model slot. Actual native preparation requires a later explicit
authorization and verified slot release.

The candidate and complete inputs are byte-identical to
`../krikri-visible-name-tag-preparation-2026-11-28`, whose final manifest is
`3a27888d2e84ee6a9e88e2cb77b68abb5bd13699348a6bb981726e8aad63e1b8`.
Its independent preparation review is
`c6ead55c4c1f8877e3cb004cf4f9ea27b49d6622b546e539c79a8268a102d9c8`.
The unchanged original six criteria and 13 actual source mentions are preserved.

`prepare_native.py`, `infer_native.py`, `run_native.py` and
`resource_monitor.py` are byte-identical to the reviewed compact-screen runtime.
Only `context.py`'s private log directory changes. The reuse record and exact
one-line patch are retained. Existing orphan-safe group/resource tracking,
strict parameter mapping, raw response retention, request-count checks,
full-source native preflight, original-case order, first-failure stop, explicit
unload and cleanup logic remain unchanged. The former cleanup-control report is
retained as prior evidence, not represented as a new probe.

The source protection API keeps its existing field names, so the runtime needs
no tag parser or recovery change. `protection.py` requires each entire
`<xN>source name</xN>` pair to remain exact in its original entry. A changed name
fails; successful removal only returns validated response inner text. The
runtime still saves complete raw JSON before guards, checks it against the
actual app strings, then applies the unchanged production guard against the
full original source after wrappers are removed.

Any later native phase must verify the same original Q4_K_M payload, native
template/stops and 4096-token context. Actual prompt counts must be obtained;
the retained 231/284/240/236/251/234 values are reference estimates only. The full
2048-token response budget remains reserved. Four CPU threads, 6144 MiB sampled
owned-process RSS, existing timeouts, sequential sample retention and 1 GiB free
disk reserve remain fixed. No detector, new weights, altered quantization,
prompt repair or new corpus is involved.

No inference freeze exists yet. Actual native setup and resource/cleanup
evidence must be independently reviewed before any later generation decision.
All rejected earlier profiles remain immutable. Successful source-only review
does not establish name copying, pronoun/role fidelity, translation quality,
whole-app memory fit or production readiness.

# Retained successful compile and original dependency-gate failure

The reviewed V2 grammar controller acquired the exact eleven pinned official
source objects and compiled the small native validator once. Its C++ compiler,
ELF and dynamic-library inspections succeeded. The next verification step
rejected five system-header paths and stopped before any parser sanity, native
model preparation or generation.

The exact existing binary, dependency file, source objects and command output
are retained in `runtime-snapshot/`. The independent stage review verifies all
273 actual include dependencies and identifies the five existing system aliases
whose resolved paths were omitted by the original allowlist. It is in
`independent-stage-review/`. Original phase reports and raw resource samples are
retained in the sibling `krikri-marker-grammar-controller-v2-2026-11-28/` directory.

The original failed build has not been converted into a successful historical
result. A separate prospective continuation can verify the exact observed
headers and reuse this binary, avoiding another compile. The original three
sanity cases, actual grammar probes and translation accuracy remain unapproved
by this snapshot. No model or provider request was made here.

`snapshot.json` binds each copied byte to the original phase output. The original
source/license capsule and native build plan retain the upstream provenance.

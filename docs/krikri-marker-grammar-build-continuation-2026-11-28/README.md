# Verify the retained validator build, then finish its unrun checks

The v2 compilation succeeded and produced a 23,152-byte validator. Its ELF and
dynamic-loader receipts matched the frozen configuration and libraries. The
following header check rejected five real system UAPI headers because their
canonical paths sit outside the original allowlist. That failed phase remains
unchanged and unsuccessful.

This separate continuation reuses the exact binary and all original raw command
receipts. It adds no compiler invocation, acquisition or download. The independent
273-entry dependency audit binds every actual file and exactly five resolved
UAPI paths, including each existing `/usr/include` symlink and its precise link
text. There is no general `/usr/lib` exception. Only after these checks may the
three original, previously unrun native validator sanity probes execute.

`build.json`, if eventually successful, is a new build-verification wrapper. It
records zero recompilations and the original failed report, actual reused binary,
complete dependency verification and new sanity receipts. It does not rewrite
or regrade the first build attempt. The `acquire` CLI phase is unavailable.

The previous acquisition's 0.188254 seconds and failed build's 1.062938 seconds
are carried into the same 900-second aggregate. The build verification receives
only the remaining 118.937062 seconds of the original 120-second build budget.
Memory, CPU, capture, disk and native limits are unchanged. Private worker logs
use a separate directory to preserve the first attempt.

The actual native preparation, its allowlist, the corrected final-time observer,
the strict validator status parser and the full 285-probe validation action are
unchanged. Their future reports keep `native_prepare.json` and `validate.json`
with their complete resource and raw-output records. Every phase still needs its
own reviewed root receipt; this preparation authorizes no native execution or
translation generation.

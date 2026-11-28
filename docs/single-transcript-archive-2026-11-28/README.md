# Single transcript ZIP and atomic completion — 2026-11-28

Parent `17538a92083584bb9434918a117f94a5ccdcd225` (draft PR #2). Version remains 0.3.0.

The parent's [actual candidate ZIP installation](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46175600785) completed both archive and installation jobs successfully. Its [PR platform tests](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46175606843) passed Ubuntu, Windows and macOS. These are exact-parent results, not new checkpoint claims.

## Actual source recovery

Downloaded the parent's candidate source artifact 15275590897 through the authorized GitHub connection. Inner archive SHA-256 `3fcca3aa88cc40ce7c15b34fc46dfe8b453fd8e0dfc07acfc42d9a5e0217a473` matched the manifest and exact commit archive comment. Parent app.py blob `7f29e585336721b7577e82b9330d8aadf7e794c4` matched the repository. This enabled full application imports and real SQLite/HTTP tests locally, rather than extracted-function substitutes.

## Changes

Both single transcript ZIP download routes now render the current persisted components and compress into an owned temporary file, with bounded 64 KiB transport and cleanup on construction or transport error. Non-ZIP exports retain their demand-driven behavior. Job completion retains the existing per-job disk components and archive for diagnostics, but writes that archive directly to disk and does not compress twice when subtitle warnings are generated. The final done status and saved warnings are now set in one locked update; recovery from a clean record clears stale warnings. No provider, recognition, translation, summary or subtitle criterion changed.

## Verification

Actual application tests: `python -m pytest -q tests/test_single_archive_stream.py tests/test_export_selection.py tests/test_processing_warnings.py tests/test_backup_download_stream.py tests/test_library_paging.py tests/test_batch_recovery_regressions.py` — **27 passed in 4.37 s**. Three new cases exercise both HTTP routes, latest Greek edits with invalidated enhancements, on-disk/archive equivalence, failure cleanup, once-only compression and atomic warnings. The same new cases on the parent produced three failures (one direct route assertion and two absent new helper interfaces). Full local suite cannot be verified: yt_dlp is missing at collection and faster_whisper/PyAV are not installed; a broader attempt excluding provider-runtime collection encountered missing ML runtime failures and timed out. Direct GitHub clone DNS also failed. No complete local suite claim; ordinary hosted checks will cover native dependencies.

Exact tested app.py SHA-256 `6b51bba935e58b8e91e910c35296bec6e9e81fbae696b46fbe51eac7e53cf096`; new test SHA-256 `58ed47531e817080473f21574279734b950d8532ddf400897387adda46beb1f3`.

Synthetic generation-only benchmark, actual parent and replacement functions, 3,600 two-second segments with 650 deterministic mixed-script characters each and 3,600 translated segments of the same length (random.Random(42), ASCII letters, digits, space, Greek lower-case letters excluding final sigma). Both produced 18,151,410-byte archives; SHA-256 matched for all eight decompressed members. Parent peak Python allocation 51,342,967 bytes / 2.4700 s; new generation 35,540,452 bytes / 2.5116 s (30.8% lower traced allocations). Measurement excludes loading source records and HTTP transmission, actual model inference and whole-machine RAM; no speed gain claimed.

## Open recognition failure

Downloaded the actual failed provider artifact 15273578020 (run 46170180187, parent of the current parent). The unchanged tail report confirms acquisition, complete PCM, same measured Small weights, decoder policy, persistence and restart; at least the late-dialogue world-changed anchor is false. This is an actual recognition regression, not an install/export bug. No acceptance threshold or decoder was adjusted and no manual rerun was queued. English/Greek semantic accuracy, provider access, broader speaker accuracy and whole-machine long-recording resource fit remain open. Fresh validation sets remain unopened.

No version bump or release.

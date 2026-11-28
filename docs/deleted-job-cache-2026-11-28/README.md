# Delete cached transcript output — 2026-11-28

Parent `2ee8bddcbe46a421fffd670bea82fda6e017a78a`, draft PR #2, version remains 0.3.0. Read V1-RELEASE-GATES.md and the previous batch-live-deletion record before choosing this work.

## Reproduced and corrected

Three new actual SQLite/ASGI regressions failed on the exact parent: the job endpoint still returned deleted Greek text, a cache-free deletion left temporary ZIP/text files on disk, and a simulated filesystem denial returned success without any cleanup warning. The deletion route now clears the live job result, removes its exact UUID work directory (including after losing the in-memory cache), and reports a filesystem cleanup failure separately from successful database deletion. Saved-row publication and recovered-job publication are serialized against deletion using the existing application lock. The browser clears the matching current result and editor, prevents a superseded asynchronous result from reappearing, and displays cleanup warnings. This is application-level deletion, not forensic erasure of SQLite pages, already downloaded exports, backups or another browser's earlier copy.

## Evidence and verification

Recovered actual candidate artifact 15278988794, inner archive SHA-256 ebe1cae66e6ff0e3fc662d10494c34fdd418e603e750b7ad684f9e429eb63ba3, archive comment equals exact parent. Source blobs matched GitHub before modification.

Three new tests failed on the parent; after correction, local command:

    python -m pytest -q tests/test_deleted_job_cache.py tests/test_batch_live_deletion.py tests/test_batch_recovery_regressions.py tests/test_library_edit_conflicts.py tests/test_features.py tests/test_app.py tests/test_single_archive_stream.py tests/test_processing_warnings.py

77 passed in 2.91 seconds on actual application code, SQLite, HTTP and ZIP operations with controlled provider/speech fixtures. JavaScript syntax and Python browser harness compilation passed. Local Chromium navigation failed with ERR_BLOCKED_BY_ADMINISTRATOR; no attempt to bypass that policy. The additional maintained real-browser deletion case is published for normal hosted verification; browser execution is not yet verified.

Tested blobs: app.py 2b00ae8b7f4bc44d3deae90f89dc154aa28a0fa4; static/index.html 7c4f253cc7b4607314395ee522e53b42c067bd9e; tests/test_deleted_job_cache.py 8aa1d2771c6ce90f0a8e3e3522786d01bba4e134; tests/smoke_browser.py 6f560392c8c4897d7fd148e89ce84392f0e9676d.

## Previous checkpoint hosted verification and external blockers

The parent platform run 46185924412, candidate/installation run 46185917951, browser run 46185917969, independent QA run 46185917992 all completed successfully. Actual live-source run 46185917954 failed acquisition acceptance. Retrieved artifacts 15279702564 and 15279542625 and examined their actual provider reports and server logs: three YouTube fixtures require sign-in/bot verification, ordinary Vimeo requires login and the separate player fixture returned HTTP 401. Dailymotion passed full acquisition/transcription/export and the mixed batch succeeded with its blocked YouTube item. The four retained late-dialogue anchors passed the restored-policy checker this time, without approving semantic accuracy. No restriction was bypassed or repeated provider run requested.

All release gates remain unchanged. Bilingual meaning, summary accuracy, wider speaker accuracy, provider availability and whole-machine long-recording resource fit remain open. No fresh validation inputs consumed, no version bump or release.

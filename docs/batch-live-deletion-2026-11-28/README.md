# Batch deletion and recovery consistency — 2026-11-28

Parent `cb8cd153718f540ae0958128d4a98e5e30a96f50`, draft PR #2. Its [platform test run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46180816061) is completed successfully. Version remains 0.3.0.

## Reproduced problem

Three real SQLite/ASGI regressions failed on the exact parent: deleting a saved record just before the worker acknowledged it restored a false success journal state; deletion after batch completion was hidden by the live job cache; deleting a later previously saved item during recovery caused its source to be processed again from a stale journal snapshot. The final case also protects the latest edited title. No real provider requests are made by these deterministic regressions.

## Correction

A pending-item claim now checks its current terminal journal state in an immediate transaction. Completion checks for the durable transcript under the same transaction as journal acknowledgement, serializing edits/deletion. Missing transcripts cannot be recorded as successful. Prior deletion errors and titles are retained. Batch polling uses the terminal journal status, title and library ID instead of stale in-memory state. Other items continue normally. No speech, translation, summary, provider or acceptance criterion changed.

## Verification

The previous candidate source archive (artifact 15275590897) has SHA-256 3fcca3aa88cc40ce7c15b34fc46dfe8b453fd8e0dfc07acfc42d9a5e0217a473 and exact archive comment 17538a92083584bb9434918a117f94a5ccdcd225. Reapplied the next commit's app.py patch and confirmed blob 865cb9204eb0242f1b84145b02336f939a9f6181 and SHA-256 6b51bba935e58b8e91e910c35296bec6e9e81fbae696b46fbe51eac7e53cf096; batch_store.py and library.py matched their parent blobs. The initial three new tests failed on that baseline (two false zero-failure counts; one duplicate processing call).

Local command: python -m pytest -q tests/test_batch_live_deletion.py tests/test_batch_recovery_regressions.py tests/test_v03_reliability.py tests/test_processing_warnings.py tests/test_library_paging.py tests/test_speaker_persistence.py -k 'not test_app_requests_separate_timing_and_persists_speaker_report'

**43 passed, 1 deselected in 3.41 seconds.** The excluded test requires the missing faster_whisper runtime. Tests exercise actual application endpoints, SQLite, journal transactions and ZIP downloads; transcription/provider calls are controlled fixtures. Cache clearing checks the durable read path; existing recovery tests additionally enter ASGI lifespan. This is not a fresh acoustic test, actual network-provider check, full native suite or whole-machine resource approval.

Tested blobs: app.py 6d537eaa8986156c6151e6cb166517ba444024ea; batch_store.py 9a71721133d2509d060522d9539ed550c9ab089f; tests/test_batch_live_deletion.py 7e48246e6d706160c64807a5f792511cf4d064aa.

Release gates remain unchanged: faithful bilingual ASR/translation/summary, provider access, broader speaker accuracy and long-recording whole-machine resource fit are open. No fresh validation inputs used. No version bump or release.

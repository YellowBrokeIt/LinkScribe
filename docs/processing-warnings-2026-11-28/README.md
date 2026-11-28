# Persistent processing warnings in batch and library views

This change makes existing warnings visible when a transcript succeeds but a requested optional feature is unavailable or rejected. It preserves source text, successful transcript status, fatal-source failure counts, and the original warning metadata. It does not change any speech or language model, decoder, source provider, release version, or acceptance criterion.

## Concrete gap at the starting checkpoint

At baseline [`00567db099c05f2abe1f127d8762f7adbdd9f712`](https://github.com/YellowBrokeIt/LinkScribe/commit/00567db099c05f2abe1f127d8762f7adbdd9f712), `_enhance_and_save` already retained optional-feature errors in `processing_metadata.warnings` while saving the original transcript. The batch renderer did not display the warnings. The batch status endpoint returned an empty warning list after its in-memory child expired or the process restarted, and the saved editor did not display the persisted metadata.

Consequently, completed transcription and successful delivery of every requested enhancement were not clearly distinguished in batch and saved-record views. The earlier timing correction preserved warnings in batch ZIP reports; the screen and history paths still needed the same explanation.

## Resulting behavior

- Completed batch items retain their warning messages after ordinary job expiry and a new server process. The API reads existing SQLite processing metadata rather than storing another copy in the batch journal.
- Batch detail and recent history include a `with_warnings` count. It counts completed items that have warnings, not individual warning strings. Fatal transcript failures remain in the existing `failed` count.
- Each affected row says **Transcript saved with warnings** and displays its processing notes. A batch can truthfully have successful source transcripts, zero fatal failures, and separately reported unavailable enhancements.
- The saved editor displays `processing_metadata.warnings` when opened, including through batch history. Notes update after saves and highlight generation, and are hidden when a different record has no warnings.
- Warnings are rendered as text. The layout allows long messages to wrap. Original source text remains available. Translation and summary download links still depend on actual saved enhancement results; a failed translation or summary does not gain a successful enhancement download.

Warning polling reads only transcript IDs and processing metadata, using bounded SQLite parameter groups. It does not load full transcript text, rebuild exports, run enhancements, or repeat provider work. Active in-memory notes and durable completed-record notes are deduplicated. The helper closes its SQLite connection explicitly.

## Focused API and persistence verification

[Focused validation](focused-validation.json) and [exact pytest output](focused-tests.txt) record **42 passed in 1.54 seconds** across the new warning tests, existing batch recovery regressions, and related feature checks. Python source parsing, inline JavaScript syntax checking and the scoped diff check also passed.

The new [API regression file](../../tests/test_processing_warnings.py) processes 20 controlled caption fixtures through the actual application routes, batch worker, SQLite library and exporter. One source fails, one successful transcript has a controlled translation failure, and another has a valid interval that cannot be represented in timed exports. The result is 20 completed items, one fatal source failure, 19 saved transcripts and two completed items with warnings.

The tests verify all original source text, absent rejected translation output, retained TXT/JSON exports, warning-bearing batch ZIP reports, and unchanged notes after expiry and a new application lifespan. A separate fresh Python process reads the same SQLite store with acquisition, inference and scheduling forbidden. It recovers the same notes and counts while its in-memory job and batch dictionaries remain empty. Another check forbids transcript loading and export construction during warning polling.

These fixtures are deliberately controlled. They establish persistence and presentation contracts; they do not establish provider access, generated meaning, acoustic accuracy or real translation quality.

## Browser case and observed local limitation

The existing [browser harness](../../tests/smoke_browser.py) now contains `batch_processing_warnings_persist`. It requires visible warnings for two completed caption jobs, separate warning counts, absent unsuccessful enhancement links, unchanged saved text, a warning-free record clearing old notes, and a 320-pixel layout check. It stops its owned application server, starts a different process against the same SQLite database, and checks the saved batch and editor again.

In the full harness, this case runs after all assertions needing the earlier actual-upload Job objects. Subsequent editor checks use durable library IDs. The owned editor fixture is seeded only if absent, so restart does not overwrite its saved state.

Independent review caught a possible false pass while opening a clean record: a hidden warning panel could be inside an editor that had not opened yet. The case now waits for the editor to be visible and its title to match the exact clean record before checking the warning panel. The [correction record](browser-review-correction.json) preserves both helper identities; production code and the already tested API sources were unchanged.

The explicit `--scope processing-warnings --asr stub` mode selects only this case and the JavaScript-error check. It creates no speech fixture and performs no ASR. It does not report the rest of the browser suite as executed.

The local attempt stopped before any browser check: `/usr/bin/chromium` is a wrapper whose `/usr/lib/chromium/chromium` executable is absent. The [original startup report](initial-browser-startup-failure/browser-report.json) and [server log](initial-browser-startup-failure/server.log) are retained. No alternate browser was downloaded, no model was loaded, and no local browser pass is claimed. The normal hosted Chromium workflow must establish the new browser outcome on the published source.

## Evidence scope

The timing, speech-candidate and translation-candidate evidence preceding this change remains unchanged. The source hashes in this bundle identify this new warning implementation. Independent review and the final inventory are recorded in [independent-review.json](independent-review.json) and [manifest.json](manifest.json). The parent owns combined-suite verification and publication; subsequent hosted results require their own exact source and run identities.

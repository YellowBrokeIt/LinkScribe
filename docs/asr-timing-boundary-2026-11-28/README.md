# Physical audio bounds for transcript exports

This checkpoint corrects a demonstrated timestamp overrun and preserves transcripts when an optional subtitle or word-timing representation is unusable. It does not change the speech model, decoder settings, version, or release status. The full-large-v3 candidate remains rejected under its original meaning criteria.

## Original observation and correction

The [unaltered full-large-v3 hosted report](../large-v3-hosted-results-2026-11-28/artifact/recognizer-report.json), produced at commit [`73b75b45bf6715627fac94d087ec4be8b93d353b`](https://github.com/YellowBrokeIt/LinkScribe/commit/73b75b45bf6715627fac94d087ec4be8b93d353b) in [run 46102019808](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46102019808), gives the satellite-phone clip a native interval of **0–7.0 seconds**. Its complete decoded array contains **104,640 samples at 16,000 Hz**, or **6.54 seconds**. The original raw report retains that 0.46-second overrun.

The production recognizer now derives the physical duration from the complete decoded array. A segment must have finite, nonnegative timestamps and a positive interval beginning before that duration. An otherwise valid endpoint beyond the recording is clipped to the recording end. Impossible intervals raise a specific timestamp error. The existing public millisecond rounding is retained where it preserves a valid interval; native precision is retained if rounding would collapse one, and rounding cannot extend the final endpoint past the audio. No new audio crop, acoustic inference, source-specific correction, text change, or decoder setting is introduced.

The exporter previously extended short cues to at least 100 milliseconds. It also rounded endpoints to the nearest millisecond, which could extend an exact fractional-sample duration. Timed exports now quantize inward once: start rounds up to the next whole millisecond and end rounds down. Integer formatting cannot round the endpoint outward again. A 40-millisecond final cue remains 40 milliseconds. For a 104,649-sample recording, the exact duration is 6.5405625 seconds and the latest representable endpoint is **6.540 seconds**.

Some valid native intervals contain no positive whole-millisecond interval. Their text and precise timestamps remain available in the saved record, TXT and JSON. SRT/VTT for that set of segments are omitted with an explanatory `export-notes.txt`; direct requests for unavailable timed formats return HTTP 422. The job and library preserve the warning. Mixed batch archives include saved warnings and newly derived export notes, so older records also explain unavailable subtitles. These cases do not fabricate duration or silently remove transcript text.

## Optional word timing

Valid private word endpoints are bounded consistently. Invalid or zero-duration private word evidence clears the segment's optional word list as a whole, preserving all recognized text and the existing whole-segment speaker warning/fallback. It does not fail the entire transcript or keep only the words that happened to validate.

This matters for actual retained native data. The earlier rejected alignment-only [Tears of Steel report](../asr-official-tail-2026-11-28/alignment-only-results/official_tears_of_steel-report.json) contains seven zero-duration words among 361 raw words; the [Sintel report](../asr-official-tail-2026-11-28/alignment-only-results/vimeo_sintel-report.json) contains two among 256. One native `" Oh,"` has equal start and end at 42.42 seconds. The regression test preserves the entire associated sentence and its established speaker fallback. These observations establish a timing edge case; they do not approve the rejected alignment policy.

## Retained-output replay

The [replay report](retained-output-replay/replay-report.json) binds all eight original complete WAVs and the unchanged hosted native outputs to the corrected application. The [replay helper](../../tests/replay_asr_timing_bounds.py) decodes each original WAV once, verifies its complete PCM identity, and supplies the recorded native segments to the normal application path. **No speech model is loaded and no new recognition is performed.**

The replay verifies unchanged text, segment order and transcribe-request arguments. Among all eight cases, the only public timestamp change is the satellite-phone endpoint from 7.0 to 6.54 seconds. Every case is written through the actual export and SQLite path. The bundle retains 40 actual export files, the source SQLite database, an eight-record backup, and a separate restored database. The restored records match the original records. Every resulting SRT/VTT endpoint is inside the recording's physically representable millisecond bound.

The [independent replay audit](retained-replay-audit.json) rechecks all eight source/report bindings, all 40 export files, exact ZIP membership, physical cue bounds, both databases' logical columns, and the backup payload digest and record count. Database main files were copied byte-for-byte; empty WAL files and ephemeral shared-memory caches are excluded from this archival copy.

The successful replay emitted an existing native-library import warning about an unavailable UCX VFS socket. [Execution evidence](replay-execution.json) preserves it. There was no retry, permissions workaround, model loading, or acoustic inference.

## Historical experiment contract

The old [large-v3 helper](../../tests/qa_large_v3_candidate.py), [plan](../large-v3-screen-2026-11-28/plan.json), [production-policy snapshot](../large-v3-screen-2026-11-28/production-policy.json), hosted report and original experimental judgments remain unchanged. Its normal current-source preflight correctly rejects the changed recognizer; [the rejection is retained](historical-current-policy-rejection.json). The old run does not certify the new production policy.

Historical positive unit validation copies the exact plan-bound files into a temporary source view and reconstructs only the original function and literal constants from the already frozen policy snapshot. It is explicitly a reconstructed function view, not a claim of historical full `app.py` byte identity. A separate negative check requires current-policy drift to be rejected. The [previous unit-test source](historical-large-v3-unit.py) is archived unchanged here.

New report reads specify UTF-8. A narrowly scoped historical-test fixture reproduces the old hosted runner's UTF-8 decoding environment without editing that immutable runner. Scoped LF checkout rules protect the actual report bytes and new evidence-bound helpers across platforms. The recorded Linux `app.py` byte hash is provenance, not a Windows checkout requirement.

## Verification and limits

- The related timing, ASR policy, historical runner, speaker and feature checks passed: **121 tests**.
- The independent final source-bound focused run passed: **48 tests in 1.01 seconds**. [Exact output](focused-tests.txt) and [test metadata](focused-tests.json) are retained.
- The first combined run exposed an older no-speech test fixture that supplied only five audio samples while its mock segments occupied seconds 0–2. The [original fixture](historical-speech-evidence-unit.py), [failure reproduction](first-combined-failure-reproduction.txt), and [correction record](speech-fixture-correction.json) are preserved. Only that synthetic recording's length changed to cover its existing segments; its original quiet samples, native outputs and assertions remain unchanged. The targeted file then passed **17 tests in 0.56 seconds**. An [independent supplemental review](fixture-correction-supplement.json) verifies that the remaining statements and all assertions are unchanged. No production change was made to accommodate the fixture.
- [Independent implementation review](implementation-review.json) found no remaining blocker in the reviewed scope. Its earlier [edge-case review](proposal-edge-case-review.json) preserves the concrete exporter, locale and optional-word concerns resolved by this change.
- [Validation summary](validation-summary.json) records the unchanged historical file identities and the new application identity. [Manifest](manifest.json) inventories this bundle and its source dependencies.

These checks establish bounded timing and preservation behavior from retained output and controlled edge cases. They do not establish new acoustic accuracy, word-time accuracy, speaker quality, Windows execution, or a fresh hosted result for the edited application. Full application regression and subsequent hosted validation belong to the parent checkpoint. Legacy saved records do not acquire a missing original audio duration retroactively; export quantization stays within their stored intervals, while physical-duration enforcement applies at recognition when the complete decoded array is available.

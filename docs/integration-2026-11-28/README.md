# Integrated highlights checkpoint and follow-up fixes

## Published checkpoint

Commit [`f12afd8`](https://github.com/YellowBrokeIt/LinkScribe/commit/f12afd80e99d9673e416d7f243976697a66675a9)
integrates the frozen source-highlights selector and the explicit Vimeo player
URL correction. It remains an unreleased 0.3.0 candidate. The
[machine-readable record](hosted-f12afd8.json) retains exact jobs, source hashes,
checks, failures and artifact identifiers.

| Hosted check | Observed result |
| --- | --- |
| Windows, macOS, Ubuntu and independent Python 3.11/3.13 suites | Each passed 652 tests and 32 subtests. |
| Fresh Linux checkout and actual downloaded candidate source ZIP | Both installations passed their real launcher/endpoint checks. |
| Actual audio upload | PyAV, Whisper Tiny, SQLite and exports passed. |
| Default local Ollama integration | All 12 cases completed; five automatic passes and seven review flags. Meaning is unapproved. |
| Chromium | 31 of 32 checks passed, including actual-upload source highlights, downloads, source navigation, edits and narrow-screen layouts. The new saved-highlights selector failed before generation. |
| Dailymotion, recovery and nonspeech | Full recording, mixed batch, restart, exact silence and actual white-noise checks passed. |
| Original YouTube/Vimeo fixtures | YouTube requested bot sign-in; Vimeo's regular-page client required login. These are new observations, distinct from earlier messages. |
| Additional public fixtures | YouTube full film requested bot sign-in. The explicit Vimeo player returned HTTP401 from the hosted environment. No ASR ran for either. |

Source runs: [platform tests](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586633),
[independent integrations](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586644),
[archive installation](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586619),
[Chromium](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586542),
and [provider checks](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586538).

The assistant inspected the retained desktop highlights, 320px highlights and
320px library-editor screenshots. Text and controls remain within the viewport;
the complete-source notice and source-navigation buttons are readable. That
visual review does not convert the failed check into a pass.

## Browser harness correction

The saved-highlights check searched for a fixture and immediately clicked a
generic **Open / edit** locator while four initial rows were still present.
Playwright correctly refused the ambiguous locator. The correction identifies
the intended owned fixture by its unique title and waits for exactly one row.
It preserves all highlight/edit/regeneration assertions. The backup case now
also requires actual saved highlights, so an earlier failed generation cannot
yield a misleading null-equals-null round-trip pass.

The correction needs a new actual Chromium result for the updated revision.
Rerunning the old unmodified test would not resolve it.

## Editor save race

Code inspection found a separate data-loss race: a save captured an earlier
version, but its completion then replaced the editable transcript even if the
user had typed a newer correction while the request was pending.

[editor-save-race.json](editor-save-race.json) records a paired reproduction
using the actual inline editor handlers from `f12afd8` and the revised candidate.
The [small diagnostic](probe-editor-save-race.cjs) supplies a controlled DOM and
delayed transport, without rewriting the editor logic. The baseline displayed
the older saved text and lost the newer edit. The revised handler preserves the
newer text, keeps highlights disabled while those edits are unsaved, and explains
that another save is needed. This diagnostic is not browser/database evidence.

The revised UI tracks editor sessions and input revisions, snapshots the save
target and payload, prevents duplicate pending saves, and ignores responses for
a closed or different editor. Regeneration and deletion also respect the current
editor session. A new Chromium case sends a real SQLite update, introduces a
newer edit before delivering its response, verifies both versions separately,
then saves the newer edit explicitly and regenerates highlights.

Independent review found two further paths and prompted fixes before the next
checkpoint. Replacing the editor record after highlight generation left input
handlers attached to its former segment objects; the accepted record now
rebuilds those rows. Opening another transcript also checks for typing that
occurred during its pending request, preserving those edits and the current
record instead of replacing them. The browser suite checks generation followed
by a real text edit, and a separate delayed-open case verifies that a newer
correction is subsequently saved to the original record only.

The browser correction and editor changes are pending hosted verification in
this record. Speech accuracy, provider access and generated-text quality gates
remain open; none of these results is a v1.0 approval.

The [follow-up local verification](followup-local.json) records **678 tests and
32 subtests passing**, Python/JavaScript syntax and dependency checks, and exact
source hashes. It includes the aligned-ASR regression checker and its negative
controls. Those controlled checker tests do not stand in for the pending actual
full-recording inference or Chromium run.

## First hosted follow-up: `79189b0`

The [exact-commit first-run record](hosted-79189b0-first-run.json) preserves five
hosted suites each passing **678 tests and 32 subtests**, fresh checkout and
actual ZIP installation, and actual Tiny upload/storage/exports. The ordinary
ZIP requirements installed `curl-cffi` without an extra QA-only dependency.

Chromium passed **33/34 checks**, including highlights after editing, the real
in-flight-save case, and a backup containing nonnull highlights. The pending-open
case captured the title input while the first editor was still hidden and empty.
After the delayed second open, the application retained the correct original
title and displayed the expected preservation message, but the test compared
that title to its prematurely captured empty value. Its later persistence checks
were not reached. The follow-up waits for the original editor and its unique
title before recording the baseline; it removes no acceptance assertion.

The full Dailymotion request now failed acquisition with **“No video formats
found!”**, before any speech recognition. Consequently the new tail checker
failed closed on missing evidence. This does not establish that the aligned
decoder preserved or removed the late dialogue. Exact silence and actual white
noise passed. The additional YouTube source reported unavailable content; Vimeo
again returned HTTP401. All provider failures remain failures. A separately
identified official-source comparison is being investigated, without treating
it as a successful download from the original provider.

## Corrected browser checkpoint: `929cf2d`

The [completed hosted record](hosted-929cf2d.json) confirms **34/34 Chromium
checks passed**. The pending-open test reached its remaining assertions: newer
text was saved to the original record and the other transcript was unchanged.
Both highlights cases, pending-save preservation and the nonnull-highlight backup
round trip passed. Root and independent review of desktop/320px screenshots found
no additional material visual defect. All eight browser source hashes match the
exact checkpoint.

All five platform/Python suites again passed **678 tests and 32 subtests**.
Fresh checkout, actual candidate ZIP installation and actual Tiny upload passed.
The real default Ollama workflow completed all twelve cases with five automatic
passes, seven review flags and zero execution errors. Generated meaning remains
unapproved. This browser-harness/documentation commit did not trigger another
live-provider run; the preceding acquisition failures remain applicable evidence.

## Speech policy rollback after broader review

The [complete official-film comparison](../asr-official-tail-2026-11-28/README.md)
established that four passing late anchors were insufficient: universal word
alignment plus the two-second heuristic omitted the abort and memory-completion
commands. Removing only the heuristic restored those commands, but independent
review of all 102 publisher subtitle cues found new action/name substitutions,
an unresolved short-line corruption and six new punctuation-only segments. Both
alternatives are retained as rejected development evidence.

Production therefore restores the prior conditional word-timestamp policy and
removes the new silence heuristic. Word timestamps remain available when speaker
alignment requests them. Existing whole-recording nonspeech corroboration and
the normal decoder fallback remain unchanged. This rollback does not claim to
repair the baseline's remaining ASR errors or establish overall accuracy.

The experimental tail checker remains byte-for-byte frozen. A
[separate restored-policy checker](../../tests/check_asr_restored_tail_followup.py)
reuses its complete input/model/event/persistence checks and unchanged four
segment-time windows, then requires the current app hash, both requested and
effective ordinary decoder settings, and absent unrequested word alignment.
It never marks the rejected candidate approved. Its
[retained-provider recheck](restored-asr-retained-provider-check.json) passes on
the actual `f12afd8` artifact because the restored application file is exactly
that previously exercised source. This is a historical evidence recheck, **not
a new acquisition or inference run**. The hosted workflow uses this policy-specific
entry point for future actual runs and still fails closed on absent evidence.

The next requirements update also declares `socksio>=1.0,<2`: an earlier actual
model load failed because that dependency was absent under the existing SOCKS
proxy. The successful correction had installed it only in an isolated target.
The standard install should provide it without changing proxies or certificate
verification. The already installed 1.0.0 package initializes both current HTTPX
transports successfully without a network request; fresh package verification
remains tied to the later hosted checkpoint.

## Completed restored-policy checkpoint: `745554b`

The [completed hosted record](hosted-745554b/checkpoint.json) binds all results to
`745554b86bef6f60f85098ec6c9be4c0ad53b3ed`. Every Windows/macOS/Ubuntu and
independent Python 3.11/3.13 suite passed **685 tests and 32 subtests**. The actual
candidate ZIP passed all six installation/startup checks and installed `socksio
1.0.0` from ordinary requirements. Fresh checkout and actual Tiny upload also
passed their pipeline checks.

Chromium again passed **34/34**, including actual speech, source highlights,
pending-save/open preservation, backups and mobile layouts. All eight recorded
source hashes match this revision, and no uncaught JavaScript error occurred.
The full original [browser report](hosted-745554b/browser-browser-report.json)
is retained; controlled link/batch fixtures remain separate from actual network
acquisition.

Default local Ollama completed twelve translation corpus cases: five automatic
passes, seven review flags and no execution errors. The original integration and
translation reports preserve `semantic_quality: unreviewed`. This confirms the
execution path without changing earlier adverse meaning reviews.

All six real provider requests failed before recognition. The original YouTube
trailers reported unavailable content, the regular Vimeo page required login,
Dailymotion returned no video formats, the additional YouTube full film requested
bot sign-in, and the explicit Vimeo player returned HTTP401. The restored-tail
checker therefore failed closed on missing inference evidence; it did not observe
new speech deletion. Exact silence and actual nonzero white-noise rejection
passed. Both raw provider reports and the failed tail check are retained under
the same hosted record. No access restriction was bypassed.

The isolated [M2M100 translation screen](../m2m100-followup-2026-11-28/README.md)
also remains rejected: its measured execution completed, while material role and
transcription/translation meaning errors survived. Its successful setup and small
memory footprint do not close the translation gate.

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

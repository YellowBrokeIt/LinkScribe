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

## Completed script-guard checkpoint: `a4ca88e`

The [exact hosted record](hosted-a4ca88e/checkpoint.json) binds this verification
to `a4ca88ec2820f8c0e1c29f4a7f5d36b8f0a32db3`. All ordinary application workflows
completed successfully. Ubuntu and independent Python 3.11/3.13 configurations
passed **717 tests and 54 subtests**. Windows and macOS each passed **715 tests
and 54 subtests**, skipping two Linux-only owned-process-group controls in the
isolated speech-experiment harness. These skips do not remove application tests.

Chromium passed **34/34** with no JavaScript page errors. All eight recorded
source-file hashes match the tested commit. The original
[browser report](hosted-a4ca88e/browser-browser-report.json) retains actual Tiny
upload, source highlights, edit/save/open behavior, backups and mobile checks.
Fresh checkout, actual Tiny upload and all six checks against the actual generated
source ZIP also passed; the [installation report](hosted-a4ca88e/install-installation.json)
identifies that ZIP and the exercised launcher/health/diagnostic/static/SQLite paths.

The actual default Ollama integration passed its execution checks, and all twelve
corpus cases completed with **five automatic passes, seven review flags and zero
execution errors**. The original [integration report](hosted-a4ca88e/language-integration.json)
and [corpus report](hosted-a4ca88e/language-translation-evaluation.json) retain
`semantic_quality: unreviewed`. Existing adverse meaning reviews remain open.
There was no new provider request at this checkpoint; the six failed acquisitions
at `745554b` remain the most recent live-provider evidence.

The separate Qwen candidate workflow initially failed configuration validation
before any job existed because a job-level environment expression used the
unavailable `runner` context. A [recorded setup-only correction](../qwen3-asr-hosted-env-followup-2026-11-28/README.md)
placed the path in the first shell step and preserved the model, original helper,
all eight full inputs and fixed inference settings. The isolated `7ee0c7f2`
run subsequently completed within its process budget, but independent
[actual-output review](../qwen3-asr-hosted-results-2026-11-28/README.md) found
six major errors and two acceptable results. Neither successful execution nor
the ordinary application tests qualify that recognizer for adoption.


## Physical timing correction: local integration complete

The [timing fix and independent review](../asr-timing-boundary-2026-11-28/README.md)
bind application SHA-256
`5a5732ffcb420d2ca7dde87008168b91d67d8cabfd5f54a13a43436f087c0d4d`.
It clips valid overlong native endpoints to the complete decoded recording,
rejects impossible public timing, and preserves recognized text if optional word
alignment is unusable. Subtitle formatting now quantizes inward without extending
short cues; unrepresentable SRT/VTT leaves TXT/JSON available with persisted,
download and batch warnings.

The eight-case replay decoded original full WAVs and reused retained native
outputs without model loading. Independent review verified unchanged words,
order and decoder arguments, all 40 exports, ZIP membership, two SQLite stores
and the exact eight-record backup restore. Only the observed phone endpoint
changed from 7.0 to 6.54 seconds. This does not improve or regrade the failed
speech candidate's semantic results.

The first full local run found 15 failures in an older synthetic speech-evidence
fixture that supplied five samples but claimed intervals lasting two seconds.
The original fixture and complete isolated reproduction are retained with the
timing evidence. Its correction supplies enough samples while retaining every
original sample, mock interval and speech-policy assertion; independent AST
review confirmed that scope. The subsequent [combined test record](timing-local/combined-tests.json)
and [full output](timing-local/combined-tests.txt) report **753 passed and
54 subtests passed in 8.74 seconds**. The default host Python initially lacked
pytest; the run uses the existing project development environment.

The completed rejected Qwen experiment's automatic workflow is archived as
[documented separately](../qwen3-asr-workflow-retirement-2026-11-28/README.md).
Its immutable source contract still passes in an explicitly reconstructed
historical view. All ordinary hosted application workflows are unchanged.
This local result does not stand in for hosted checks of the later exact commit.


## Completed hosted timing checkpoint `00567db`

The [exact completed record](hosted-00567db/checkpoint.json) binds source commit
`00567db099c05f2abe1f127d8762f7adbdd9f712` and tree
`76baf84793ef4ebcc72fbd87c85c96a5ba48e9c4` to the retained reports and independently
verified artifact ZIP digests. These results do not certify later working changes.

- [Platform tests](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46106004196):
  Ubuntu 753 passed plus 54 subtests; Windows/macOS 749 passed plus 54 subtests,
  with four Linux-only Qwen/large-v3 process-group controls skipped on each.
- [Independent QA](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46106004237):
  Python 3.11/3.13 each 753 plus 54; fresh Linux launcher and actual Tiny upload
  passed. Default Ollama completed all twelve cases with five automatic passes,
  seven review flags and zero execution errors. Meaning remains unreviewed.
- [Chromium](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46106004215):
  all 34 checks passed, including actual audio upload, editor race regressions,
  source highlights, backups and mobile layouts; zero uncaught page errors.
  All eight source identities match this Git commit.
- [Actual candidate archive](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46106004225):
  all six package checks passed from the generated ZIP, covering extraction,
  actual launcher/health, diagnostics, static homepage, SQLite and dependencies.
- [Live providers](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46106004205):
  all six acquisitions failed before ASR. YouTube requested a bot check, regular
  Vimeo required sign-in, the supplied Vimeo player returned HTTP401, and
  Dailymotion returned no video formats. The unchanged no-speech guard rejected
  exact silence before inference and actual nonzero noise after Small inference.
  No successful provider batch or restored late-dialogue check was available.

The [upstream downloader check](hosted-00567db/upstream-downloader-check.json)
found that the installed 2026.11.23 version was the latest published release and
that the newest returned Dailymotion extractor-file change predates it. This
identified no newer release/path fix to apply; it does not establish a universal
cause or justify an access workaround. No additional provider retry was made.

Version stays 0.3.0. Application execution passes do not close the documented
speech, translation, summary, provider or whole-machine resource gates.


## Persisted processing warnings: local integration complete

The [reviewed repair](../processing-warnings-2026-11-28/README.md) restores
processing notes to live/saved batch views and the transcript editor, with a
separate completed-with-warnings count. Fatal failures retain their existing
status. Warning polling reads only stored IDs/metadata in bounded queries.
Controlled 20-item and fresh-process tests preserve all 19 successful transcripts,
one fatal source failure and two completed items with warnings, without
reacquisition or inference.

The [combined local record](warnings-local/combined-tests.json) and
[full output](warnings-local/combined-tests.txt) show **757 passed plus 54 subtests
in 10.56 seconds**, with all five changed source/test identities unchanged during
the run. Independent review found and corrected a browser assertion that could
pass while its editor was still closed; the helper now waits for both visibility
and the exact clean-record title. A local Chromium startup attempt ran zero
checks because the wrapper target executable was absent. That failure remains
recorded; no browser download was attempted. The new real-server-restart case
must pass in hosted Chromium alongside the prior 34 checks.


## Completed warning checkpoint `7a53991`

The [exact completed record](hosted-7a53991/checkpoint.json) binds commit
`7a53991da60c9e052be9a72299218b291b364c8d` and tree
`07ceac544ca6da271cede39d409a0281b9cad5fd` to actual artifacts, source identities
and test log lines. All ordinary hosted workflows passed: Ubuntu/Python3.11/Python3.13
757 plus 54; Windows/macOS 753 plus 54 with four Linux-only harness skips;
fresh Linux checkout, actual ZIP installation and actual Tiny upload. Default
Ollama completed twelve cases with five automatic passes/seven review flags and
zero execution errors; semantic meaning remains unreviewed.

[Independent browser review](../processing-warnings-hosted-2026-11-28/README.md)
verified 35/35 checks, all preceding 34 names in order, actual server PID change,
warning preservation in the downloaded backup, clean-record clearing and mobile
width without overflow. The retained selection includes all non-image artifact
files plus the four relevant screenshots; its manifest explicitly distinguishes
that selection from the complete original reviewer bundle.

One of six individual provider fixtures succeeded: the full 734.15-second
Dailymotion recording passed normal Small recognition, persistence, exports,
cleanup and restart. The other five acquisitions failed. The later mixed batch
failed both acquisitions, including the previously successful Dailymotion URL,
with no ASR event for that repeated item. The [separate frozen diagnosis](../live-source-diagnosis-7a53991-2026-11-28/README.md)
retains the exact error chain and finds no proven batch-specific cause.

The original restored-tail checker remains failed at 27/28. Its world-change
phrase is present raw and saved at 509.18–520.18 seconds; full containment inside
the unchanged 510–529 window fails. The publisher cue is at 518–520 seconds,
so the native interval begins well before that cue. A separate lexical diagnostic
finds all four phrases, without changing or approving the failed timing check.
Measured input/model/decoder/runtime identities match the earlier baseline;
output differences are already native, before application normalization.
This evidence does not establish a production ASR repair or general quality.

## Validated provider metadata: combined local result

The [provider adapter repair](../provider-metadata-reuse-2026-11-28/README.md)
passes its checked resolved result directly to the installed downloader's
processing API. Review found and corrected the API's additional-URL branch;
extra entries and unresolved results are rejected before transfer. The final
104 focused checks include native processing with an owned extractor and no
network access. Existing duration, size, provider transport, output and cleanup
contracts are preserved.

The root combined run passed **777 tests and 54 subtests in 11.04 seconds**.
[run.json](provider-metadata-local/run.json) records the command and unchanged
before/after source hashes, and [pytest.txt](provider-metadata-local/pytest.txt)
retains the complete output. The repaired app hash is
`b0ea2cf313a15697369a61beab15ae7017251476fc25ea7c77bdcbafe527dd47`.
This run makes no live-provider or language/speech-model calls. Hosted checks
are still required for the next published revision. Neither intermittent source
availability nor the historical native timing failure is regraded by this fix.

## Completed provider checkpoint `6de3fad`

The [completed hosted record](hosted-6de3fad/checkpoint.json) binds the exact
published commit `6de3faddf88bb5da8ea35d985b33ad26e55e249f` and tree
`1c8095da5eaecdefd86589194116a7d60b4535a4`. All ordinary workflows passed:
Ubuntu/Python 3.11/Python 3.13 **777 tests plus 54 subtests**, Windows/macOS
**773 plus 54 with four Linux-only harness skips**, fresh checkout, actual
source ZIP installation and actual Tiny upload. Chromium passed all **35**
unchanged cases, with exact checkpoint source hashes, actual restart and no
page exceptions. The unchanged interface was not given a redundant new visual
review; the prior independently inspected screenshots remain separate evidence.

The full 734.1453125-second Dailymotion recording passed the normal Small
pipeline both individually and inside the actual mixed batch. The latter
retained its successful record while the YouTube item failed. Both records,
batch history and exports survived restart. Exact silence and actual white
noise were correctly rejected. Five other individual provider fixtures failed:
three YouTube bot checks, regular Vimeo requiring login and the explicit Vimeo
player returning HTTP 401. Provider availability remains unapproved.

The unchanged single-source tail checker passed **28/28** this time, with the
world-change phrase at 519–521 seconds. The previous `7a53991` failure stays
27/28. No speech settings or timing code changed, so the new pass does not
establish that metadata reuse repaired timing. The two successful current
recognitions also differ in native segmentation (72 versus 61 segments) despite
identical full input PCM. Word-level timing and general speech accuracy remain
unapproved.

Default Ollama again completed all twelve cases, with five automatic passes,
seven review flags and no execution errors. A separate [meaning review](../default-qwen-meaning-review-2026-11-28/README.md)
now records nine major errors and three acceptable cases in the earlier
`7a53991` outputs. Five exact output/source/criterion comparisons to `6de3fad`
establish at least two current major errors and three acceptable unchanged
cases. The other seven newer outputs were not regraded. Completed requests
therefore do not approve translation quality.

## Completed compact-tag experiment and separate summary preparation

The [compact empty-tag translation experiment](../krikri-compact-tag-screen-2026-11-28/README.md)
ran all six original cases once. Its full prompts, thirteen exact restored name
mentions, normal stops, unloads and owned-process cleanup passed the mechanical
contract. Independent meaning review still rejected the candidate: two outputs
were acceptable, three had minor issues and the negation passage had a major
actor/anaphora error. The source's explicitly feminine subject became `he` in
both continuing references. No defaults or production code changed.

The measured generation phase was 139.865458 seconds with 5548.7 MiB peak
sampled RSS under its 6144 MiB owned-process cap. The original raw outputs,
complete samples, failed predecessor and unchanged criteria remain retained.
The [preparation bundle](../krikri-compact-source-name-protection-2026-11-28/README.md)
preserves the first scanner's closing-tag gap and independently reviewed fix.
This is completed development evidence, not fresh-validation or release approval.

The separate [summary proposal](../krikri-summary-feasibility-2026-11-28/README.md)
uses two already-exposed sources, unchanged direct-summary behavior and the
existing Greek-specialist model. Its full source-layout check and
[independent feasibility review](summary-feasibility-review.json) required no
model execution. Native prompt-fit verification, English output review and the
conditional Greek run remain separate future gates. That prospective proposal
does not change any prior summary failure or the current application checkpoint.

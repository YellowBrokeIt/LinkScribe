# Published checkpoint recovery — 28 November 2026

This record reconciles the GitHub state recovered after the user reported that
LinkScribe appeared stuck. The status was checked on **28 November 2026, about
01:27 Europe/Athens (27 November, 23:27 UTC)**. It is a verification record, not
a release approval. The application remains **0.3.0**, and no stable branch
change is implied.

## Published source and activity

- Repository: [YellowBrokeIt/LinkScribe](https://github.com/YellowBrokeIt/LinkScribe).
- Development: [`feature/linkscribe-v03-reliability`](https://github.com/YellowBrokeIt/LinkScribe/tree/feature/linkscribe-v03-reliability), draft [PR #2](https://github.com/YellowBrokeIt/LinkScribe/pull/2).
- Verified published checkpoint: [`dc0985dabaacdbeedd1d55daf0351ea6bda69d84`](https://github.com/YellowBrokeIt/LinkScribe/commit/dc0985dabaacdbeedd1d55daf0351ea6bda69d84), committed 26 November at 21:18:58 UTC / 23:18:58 Athens.
- Stable `master`: [`71812b370eeb49774a465331290442a817eeb49a`](https://github.com/YellowBrokeIt/LinkScribe/commit/71812b370eeb49774a465331290442a817eeb49a), the v0.2 checkpoint from 22 October.
- The [queued-workflow query](https://api.github.com/repos/YellowBrokeIt/LinkScribe/actions/runs?status=queued&per_page=20) and [in-progress query](https://api.github.com/repos/YellowBrokeIt/LinkScribe/actions/runs?status=in_progress&per_page=20) each returned **zero** at this check. This is a timestamped observation, not a promise about future jobs.

The published PR description and release-gate document still described some
checks as pending. Those runs had already finished. The results below close
that status gap; they do not certify revisions made after `dc0985d`.

## Completed hosted checks for `dc0985d`

The run records identify the same full commit above. Logs were read to confirm
the actual test counts and integration outcomes, rather than treating a green
workflow badge as proof of every release requirement.

| Verification | Observed result | Exact run / job |
| --- | --- | --- |
| Ubuntu unit/API suite | 607 passed in 11.32 seconds | [Run 45897284240, job 140174216208](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284240/job/140174216208) |
| Windows unit/API suite | 607 passed in 29.49 seconds | [Run 45897284240, job 140174216590](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284240/job/140174216590) |
| macOS unit/API suite | 607 passed in 46.32 seconds | [Run 45897284240, job 140174216628](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284240/job/140174216628) |
| Independent Python 3.11 | 607 passed in 7.43 seconds | [Run 45897284201, job 140174216709](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/job/140174216709) |
| Independent Python 3.13 | 607 passed in 10.07 seconds | [Run 45897284201, job 140174216250](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/job/140174216250) |
| Fresh Linux checkout and launcher | `start_linux.sh`, health, homepage and library endpoint passed | [Run 45897284201, job 140174216673](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/job/140174216673) |
| Actual generated-speech upload | File → PyAV → Whisper tiny → SQLite → exports passed | [Run 45897284201, job 140174521096](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/job/140174521096) |
| Chromium workflows | 30 checks passed; actual upload ASR; 1440/390/320-pixel layouts; no uncaught JavaScript errors | [Run 45897284272, job 140174216142](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284272/job/140174216142) |
| Actual default Ollama model | 12/12 corpus cases completed; 5 automatic passes, 7 review flags, zero errors; semantic quality explicitly unreviewed | [Run 45897284201, job 140174521089](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/job/140174521089) |
| Candidate artifact generation | Completed successfully | [Run 45897284276](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284276) |
| Actual provider acquisition/ASR | Overall failed because YouTube and Vimeo did not yield usable media; detailed outcomes below | [Run 45897284195, job 140174216100](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284195/job/140174216100) |

The platform test run completed at 21:20:45 UTC, browser QA at 21:21:15 UTC,
provider QA at 21:24:51 UTC, and independent QA at 21:31:45 UTC on 26 November.
The separate [pull-request-triggered test run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897290229)
also completed successfully at 21:20:44 UTC.

Browser checks include consent and empty-input errors, actual upload polling and
exports, saved edits refreshing the visible result, controlled single-link and
mixed-batch workflows, library search/pagination/edit/export, backup restore,
setup diagnostics and origin rejection. The browser's controlled link fixtures
are distinct from the live provider tests. Screenshots remain in the artifact;
this recovery confirms the logged checks without claiming a new visual review
of those images.

The generated-speech upload uses Whisper tiny. It does not establish Small-model
English/Greek accuracy, speaker-label accuracy, or a general real-recording
quality pass. The completed Ollama requests likewise do not establish faithful
translation or summary meaning; the existing semantic failures remain open.

## Latest live provider and non-speech evidence

The downloaded provider artifact contains `provider-report.json`, source/model
fingerprints, actual saved transcripts/exports, event records and server logs.
Its report is complete and marks the overall run failed. The underlying
extractor errors were inspected, not inferred from the application's generic
download-failure message.

| Input | Observed outcome |
| --- | --- |
| YouTube Sintel trailer, `HOfdboHvshg` | Acquisition failed: `This content isn’t available.` |
| YouTube Tears of Steel teaser, `WwHux5QZfC8` | Acquisition failed: `This content isn’t available.` |
| Vimeo Sintel trailer, `11721242` | Acquisition failed: `The web client only works when logged-in.` |
| Dailymotion Tears of Steel, `xbvubxi` | Complete 734.15-second audio processed; SQLite storage, exports and cleanup passed. |
| Dailymotion-success / YouTube-failure batch | Batch outcome, successful transcript downloads and persistence passed; a fresh server process recovered saved results. |
| Exact-zero silence | Rejected as no spoken words, without a saved transcript. |
| Generated nonzero white noise | Actual ASR ran on the complete audio; the unsupported result was rejected, without a saved transcript. |

Earlier YouTube tests encountered bot sign-in requirements and a separate
caption probe returned `IpBlocked`. Those historical observations remain valid
for their runs, but the two current extractor messages do not establish the
same cause. No successful YouTube or Vimeo transcript is claimed. Repeatedly
rerunning identical requests is not evidence that these restrictions have been
resolved.

The complete-film and unseeded non-speech follow-up is therefore no longer
pending at this commit. It adds regression evidence to the
[paired speech/noise comparison](../asr-speech-evidence-2026-11-26/README.md).
It does not certify recognition fidelity, subtitle synchronization or accuracy
on other noise, music or very faint speech.

## Candidate package and retained artifacts

These artifacts were unexpired at the check and have a reported expiry of
26 December 2026. Their original creation proved that files were packaged or
preserved. The additional archive installation check below was performed
during this recovery.

| Artifact | Size | Recorded SHA-256 |
| --- | --- | --- |
| [Candidate source package, 15154885343](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284276/artifacts/15154885343) | 3,725,706 bytes | `5a81c6ab2f05a2111ad9064521b27a99a548a11f7cb1774e424234a68c9b765c` |
| [Browser report/screenshots, 15154925499](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284272/artifacts/15154925499) | 7,964,374 bytes | `db07b2dbcdb35f19b0861f8d5cf48b59ce8a32ca08405788bd25ae835d407f6e` |
| [Language evaluation, 15155071673](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284201/artifacts/15155071673) | 29,065 bytes | `92156a70e1388df385a3f397c840c48a06fe197738b32cade7f832e608c04052` |
| [Provider report/exports, 15154596982](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45897284195/artifacts/15154596982) | 146,195 bytes | `d0e6bd1459b8f3fcb849a7307de583d162436f2a361c55287a1f004194af57e7` |

The source-package, browser and language digests above come from GitHub's
artifact metadata. The provider digest is also present in its upload log.

### Actual downloaded-archive installation

The exact candidate artifact above was downloaded, and its outer SHA-256
matched GitHub's recorded digest. Its manifest identifies `dc0985d` and the
inner source ZIP SHA-256
`b5b9c89d426f520b1ddf818ec5c9c3a47b5a9d78b13df16a488b4b97708301a2`.
The Git ZIP comment also matches the full source commit.

On 28 November at 01:29 Athens, the archive was extracted into an empty
temporary directory and its unchanged `start_linux.sh` created a fresh virtual
environment. Installation, `/health`, `/api/diagnostics`, the packaged homepage,
an empty SQLite library and `pip check` all **passed**. The launcher shut down
cleanly afterward. This used Python 3.12.14 on the assistant's Linux environment,
not the user's computer. No model inference was performed in this check.

The [retained installation report](installation-dc0985d.json) records the actual
source, runtime, checks and timestamps, together with the verifier fingerprint.
The verifier's six focused unit tests also passed, including malformed source
identity, checksum mismatch, traversal, symlink, duplicate and nested-path
conflicts. The candidate-artifact workflow now downloads its own same-run
artifact and repeats this installation check; subsequent hosted results must
still be tied to their own commit. This is a tested source distribution, not a
standalone installer or a v1.0 quality approval.

## Reported later work that has not been recovered here

Recovered conversational context describes later source-highlights work,
frozen-validation checks with coverage/heading limitations, and an
audio → highlights → exports → backup/restart workflow around 4.2 GiB. Those
reports are later than the verified published checkpoint. The inspected
`dc0985d` Git tree does not contain that source-highlights implementation or
its associated acceptance evidence.

This record does not label the reports false, nor does it count them as
completed release gates. Their source revision, actual outputs and measurements
must first be recovered and matched, or the work must be rebuilt and tested.
The existing published resource record remains the
[34.635-second workflow](../full-workflow-2026-11-26/README.md), with 4584.3 MiB
RSS / 4576.3 MiB PSS and failed generated-text quality; that is a different run.

## Next work

1. Observe the new hosted source-archive installation gate on the recovery
   revision. The actual `dc0985d` archive has passed locally as recorded above;
   later artifacts need their own results. Model/workflow fidelity remains a
   separate requirement from installation and startup.
2. Recover the later source-highlights changes and their exact evidence if
   available. Keep that progress unverified until the code and results match;
   otherwise rebuild from the published checkpoint and perform new checks.
3. Preserve the provider failures as observed access limitations. A different
   authorized source or an upstream compatibility fix needs its own actual
   acquisition evidence before provider support is marked verified.
4. Continue evaluating English/Greek fidelity, source-grounded summaries and
   realistic resource limits. Structural successes do not override the
   [open release gates](../V1-RELEASE-GATES.md).

This recovery updates verification and documentation without changing the
application runtime, version, release approval, or stable branch. Every
historical hosted result above remains scoped to `dc0985d`, regardless of the
commit that later carries this record.

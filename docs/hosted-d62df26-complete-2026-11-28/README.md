# Completed hosted application verification

These are the retained results for production source `d62df26c870f175f7454fe0c3900d97891c8bff5`
(tree `209995f34b0618e183400b0f569adb0dd0e4cedb`). The later `f2ebd04` speaker
preparation correction did not change `app.py`, `asr_timing.py` or `enhancements.py`.
The application remains version 0.3.0, with language and broader speech quality
gates open.

## Completed results

| Area | Observed result | Evidence |
| --- | --- | --- |
| Linux and independent Python 3.11/3.13 | 834 tests and 54 subtests passed | `test-counts.json`, complete logs in `job-logs/` |
| Windows and macOS | 828 tests and 54 subtests passed; six Linux process controls skipped | `test-counts.json`, complete logs in `job-logs/` |
| Actual candidate ZIP installation | Fresh virtual environment, launch, health, diagnostics, static UI, SQLite and dependency checks passed | `candidate-install/installation.json` |
| Browser | 35/35 checks; no page exceptions; actual Tiny upload, edit/recovery/restart and narrow layouts exercised | `browser/`, `browser-audit.json` |
| Dailymotion full recording | Actual Small recognition of 734.1453125 seconds; durable save/reload/exports and mixed-success batch passed | `live-sources/`, `live-source-audit.json` |
| Original late-dialogue regression | 28/28 fixed checks, independently replayed against the actual saved record | `replayed-tail-check.json` |
| Other live URLs | Two YouTube attempts required sign-in; two Vimeo attempts were blocked by login or provider access restrictions | `live-sources/`, `provider-followups/` |
| Default translation | Full review of the original twelve exposed cases found nine major errors and three acceptable outputs | `root-language-review.json`, sibling `default-qwen-d62-meaning-review-2026-11-28/` |

Across both live-provider jobs, one of six URLs reached successful transcription.
The inaccessible cases remain failed; no access restriction was bypassed.
Exact silence and actual white-noise rejection passed. The film result does not
establish broad word accuracy or optional word timing accuracy, and browser
fixtures do not substitute for live provider acquisition.

The push and pull-request suites used the same verified source tree. The PR
checkout was synthetic merge `f3fd538679193e36728a3f69dd164251260acb00`, whose
parents and tree were checked independently. Runner-image commit labels are not
application source identities.

## Retention and limitations

`root-copy-inventory.json` binds every copied byte to its original local evidence.
All 45 extracted browser artifact members are retained. The redundant 11.9 MB
browser ZIP is not duplicated here; its exact archive digest, artifact identity
and extracted-member inventory remain in `browser-artifact-manifest.json`.
The smaller install and provider ZIPs are retained with their complete reports.
The original run/job snapshot is explicitly an initial snapshot; completed raw
logs and individual result reports establish the final outcomes above.

The first hosted speaker attempt failed before model execution because one
remote checkpoint filename had been inferred incorrectly. Its source-backed
preparation correction and original failure are preserved separately. The later
actual speaker result and its narrowly corrected offline interpretation are in
`../hosted-speaker-f2ebd04-2026-11-28/`; its original GitHub failure remains intact.

No translation, summary, speech-quality or overall v1.0 approval follows from
these structural checks. No version, model default, acceptance criterion or
provider permission changed in this evidence checkpoint.

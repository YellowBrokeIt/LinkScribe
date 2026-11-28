# Actual fixed-text speaker pipeline at f2ebd04

The actual application completed this controlled two-reader upload, fixed-text
timing, speaker analysis, saved transcript, reload, exports and backup. The
original hosted workflow is **failed** because its final checker expected the
wrong constructor argument. The separate, independently reviewed offline audit
corrects that one assertion and passes the original pipeline and acoustic
criteria. No model was rerun and no original result was rewritten.

## Exact source and execution

- Commit: [f2ebd0433976ed62478b67e98c4515e3d78afaa5](https://github.com/YellowBrokeIt/LinkScribe/commit/f2ebd0433976ed62478b67e98c4515e3d78afaa5).
- Tree: `1852a73d3b8665376242173edac88a0e49700d44`.
- [Original run 46123086352, job 140911610658](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46123086352/job/140911610658): attempt one, conclusion **failure**.
- Hosted artifact 15254526534: 1,916,920 bytes; SHA-256 `1321ed065fb87bcfa8eac3e408e876d2b25a498d3967f6bc187f0a914e36e7ca`.
- [Hosted plan](hosted/published-hosted-plan.json): SHA-256 `30e723794e53facc18bd88675c81d402ae8bce846aca38d5338ff5065459abec`.
- [Immutable commit source audit](hosted/source-commit-audit.json): all 21 source identities match that exact commit.

Preparation successfully fetched the exact pinned SpeechBrain YAML and resolved
its declared remote names to the existing local cache names. The actual mapping
is retained in [speaker-cache-declarations.json](hosted/artifact/speaker-cache-declarations.json),
including remote `label_encoder.txt` to local `label_encoder.ckpt`. The earlier
d62 preparation failure remains in its separate historical bundle; this result
does not erase it.

## Observed pipeline and limited acoustic result

The complete original 34.635-second, 554,160-sample waveform was used throughout.
There was one model initialization, one baseline `transcribe` with
`word_timestamps=False`, and two fixed-text encode/align calls on the original
recognizer windows. All eight source segments retained their recognized text
and received usable optional word evidence. The recognizer was actually
released before the speaker backend ran. The saved result has 19 speaker
groups, including seven groups visibly left unassigned.

The unchanged controlled-fixture score reports two speakers. It assigns 221 of
258 interior samples (0.8566; required at least 0.80), with permutation-matched
purity 1.0000 (required at least 0.95). The other 37 samples remain unassigned.
The four original annotated intervals have 65/65, 50/63, 55/65 and 51/65 assigned
samples. Reference identities are evaluation-only. [Original acoustic score](hosted/original-acoustic-score.json)
and [independent review](offline-contract-audit/independent-review/independent-result-review.json)
retain these exact calculations.

All 111 process-group samples are complete. Sampled group peak was 1,028.8 MiB;
process high-water was 1,159.0 MiB. Worker elapsed time was 11.1442 seconds and
controller elapsed time 11.7187 seconds. Original phase, total-time and 6 GiB
memory caps hold, and owned-process cleanup completed. These are distinct
sampled and process-high-water measurements, not an assertion that sampling
captures every instantaneous group-memory peak.

The independent review passes 185 checks covering complete source and PCM
identities, native tokens and alignment paths, resources, preserved words,
SQLite rows, export payloads and backup. TXT, JSON, SRT, VTT and ZIP downloads
remain available after job eviction; a separate process read the saved SQLite
row. The review distinguishes differing ZIP container timestamps from identical
member payloads and preserves its own temporary SQLite-sidecar observations.

## Why the original checker failed

The production factory omits `cpu_threads`. Pinned faster-whisper 1.2.1 therefore
passes its default zero to CTranslate2 4.9.1. The actual observer records that
constructor argument. Native zero selects the normal environment/default thread
route; it is not an assertion of zero effective threads.

The executed controller sets `OMP_NUM_THREADS=4` and `MKL_NUM_THREADS=4` and
applies affinity `[0,1,2,3]` before successful worker exec. The original CPU
scope is this source-enforced launch constraint. Worker-side affinity readback
and effective native thread count were not recorded, and neither is claimed.
The exact primary-source chain and Git blob identities are retained in the
[closed offline audit](offline-contract-audit/README.md).

The offline correction changes only the wrong constructor comparison `==4` to
`==0`, retaining all other original completed-contract checks and acoustic
thresholds. Its [result](offline-contract-audit/offline-audit.json) reports the
original failed GitHub conclusion separately. The [proposed maintained patch](offline-contract-audit/proposed-maintained-fix.patch)
is **unapplied** at archive creation; any future maintained change needs its own
source-bound plan and review.

## Archive scope and limitations

This archive contains the complete original [artifact ZIP](hosted/artifact.zip)
and all 30 unchanged extracted files, including the four source FLACs, complete
constructed WAV, actual raw report, native-return evidence, 111 resource samples,
SQLite database, backup and exports. No original artifact member is omitted.
[archive-selection.json](archive-selection.json) maps the historical paths to
this archive. Model weights were not part of the original uploaded artifact;
their exact preparation and actual-resolution hashes are retained.

The [closed offline manifest](offline-contract-audit/manifest.json) preserves
the correction code, pre-execution bindings, original failed report, primary
sources, synthetic controls and independent review. The original scratch and
runner paths inside these files are historical provenance, not rewritten paths.
The outer manifest inventories every retained payload independently.

This validates a controlled English read-speech fixture with inserted gaps.
It does not establish Greek or natural-meeting speaker accuracy, overlap
separation, generally accurate word boundaries, or transcript lexical accuracy.
The broader v1 quality gates remain open. Summary and translation were disabled
in this actual run; source/order tests, rather than this recording, support the
separate release-before-text-model boundary.

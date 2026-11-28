# Original three-reader application stage — source-only proposal

**The next bounded check is feasible without a production change.** Use the
exact already exposed 49.38-second three-reader recording through the current
application, with the same model/runtime, recognition, fixed-text timing,
speaker backend, persistence and resource contracts as the successful hosted
two-reader control. This directory proposes that stage for review. It contains
no new executable helper/workflow, test run, download, model call or execution
receipt.

The [stage proposal](stage-proposal.json) freezes the original sources, intervals,
models, criteria and prospective implementation boundaries.
[source-inspection.json](source-inspection.json) binds the actual current source
and retained hosted evidence. [source-recovery.json](source-recovery.json) records
the four available clips and exact recovery identities for the missing pair.

## Current control and the gap this would address

The actual [11e3365 hosted speaker job](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46126494171/job/140922130930)
passed on commit `11e336577c7980f8da9dd817f265472596347a48`. Its recorded result
has two acoustic speakers, 221/258 assigned interior samples (0.8566), and 1.0000
global permutation purity. Its saved output contains 21 groups, including eight
explicit `Unknown speaker` groups. Its controller completed in 17.479 seconds with 166
complete samples, a sampled owned-group RSS peak of 1,138.4 MiB, and clean owned
process termination. All 21 current source hashes match that successful hosted
plan. These are retained observations; no inference was repeated here.

The [original three-reader acoustic result](../speaker-evaluation-2026-11-26/speaker-fresh-holdout-v4.json)
already passed with three speakers, 329/364 assigned interior samples (0.9038)
and purity 1.0000. That observation exercised the acoustic backend. The proposed
stage exercises its original three-reader recording through the **current full
app path**, extending the integrated check beyond the two-reader case.

The earlier constructor-check failure and its source-only correction remain in
their original evidence. No new acoustic threshold adjustment, word correction
or model/default change is supported or proposed.

## Exact fixture

The required final file is `three_speakers_returning.wav`, SHA-256
`8ddce1f24ae57e9f3d5041fda7022c363f2cd31c6272e3d9ba98fa45d04747bf`.
The original construction implies **790,080 samples at 16 kHz**, which must be
checked against the reconstructed exact-hash WAV before model initialization.

| Order | Original clip | Reader | Original reference interval | Current retained bytes |
| --- | --- | --- | --- | --- |
| 1 | `2961-960-0004` | 2961 | 0.500–8.500 s | Exact hash verified |
| 2 | `8455-210777-0028` | 8455 | 9.100–16.835 s | Exact hash verified |
| 3 | `4507-16021-0033` | 4507 | 17.435–22.980 s | Missing |
| 4 | `2961-960-0005` | 2961 | 23.580–31.580 s | Exact hash verified |
| 5 | `4507-16021-0034` | 4507 | 32.180–40.180 s | Missing |
| 6 | `8455-210777-0030` | 8455 | 40.780–48.780 s | Exact hash verified |

Reproduce the existing construction: 8,000 initial zero samples, the original
first at most 128,000 samples of each fully decoded source, and 9,600 zero
samples after every clip including the final one. Use the same PCM16 writer.
This is the original frozen fixture construction; the recognizer receives the
entire resulting WAV, with no new cropping or trimming.

No current decoded-PCM hash is invented for the unavailable complete WAV. The
future preparation must first pass the exact WAV hash, frame count, format and
all six original interval checks, then record its full decoded PCM hash for
comparison with the actual application inputs.

## Safe recovery of the two missing clips

The [original source manifest](../speaker-evaluation-2026-11-26/selected_sources_fresh_holdout.json)
records both files in the public OpenSLR LibriSpeech conversion, revision
`71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`:

- Row **1502**, ID `4507-16021-0033`, SHA-256
  `1a95f7d0613cb1b284ce711f82f46383f9f2e3969d63d356906b7e6ea5a15a62`.
- Row **1503**, ID `4507-16021-0034`, SHA-256
  `82d1c6989ed82652706793e5449d59106eb0cd0fcc9fc2d0b53fae601834d832`.

Use the same recovery mechanism that succeeded for the other four clips in the
current hosted job: one public rows request for `clean/test`, offset 1500,
length 15. Verify the exact row, ID and reader 4507. The fresh returned media URL
must have the exact original unsigned revision path recorded in
`source-recovery.json`; its expiring signature is obtained from that response.
Make one bounded transfer for each source and require the original full SHA-256.
Keep the existing 20 MiB file cap, 240-second stream deadline and 30-second socket
timeout. Do not substitute another utterance, revision, archive member or reader.

The four retained current files are provenance evidence. A fresh hosted runner
can recover all six sources through the three original rows responses at
offsets 500, 1000 and 1500. If any identity, transfer or fixture check fails,
retain the precise source/stage error and stop before model construction.
The missing pair's present availability has **not** been tested here.

The original metadata declares CC BY 4.0 and credits Vassil Panayotov, Guoguo
Chen, Daniel Povey and Sanjeev Khudanpur, with speech derived from LibriVox
audiobooks. Preserve that attribution with the fixture evidence.

## Minimal implementation if approved

Prepare a separate source-bound `tests/qa_three_reader_speaker_integration.py`
variant and a dedicated hosted invocation. Keep the existing two-reader helper,
workflow and all historical plans intact. The narrow controller differences are:

1. A distinct protocol and the exact original three-reader filename/hash, with
   six source records and six reference intervals.
2. Six-clip cardinality in the existing deterministic fixture constructor;
   padding, source cap, decoder, writer and physical/hash checks stay the same.
3. Post-worker scoring with case ID `three_speakers_returning` and expected
   speaker count **3**. Reuse the exact existing `label_at`/`score` functions and
   the original **0.80 coverage / 0.95 global-permutation purity** criteria.
4. New plan, workflow invocation, work and artifact paths. Bind every final
   source hash and review the implementation before a separately approved run.

Reuse the corrected pinned-YAML cache mapping and model checks, current real-app
observer, raw native alignment capture, final recorded resource caps, strict
owned-group accounting and cleanup. Keep one baseline `transcribe` call with
word timestamps off, same-engine fixed-text timing, release before the acoustic
backend, and the existing saved/reloaded/exported/backup checks.

Retain the four-CPU maximum, 6 GiB owned-process cap, 600-second worker total,
180-second initialization/recognition/timing/speaker phase limits, and 90-second
persistence limit. Constructor `cpu_threads=0` remains the current native-auto
request under the source-enforced CPU/OMP limit; the acoustic backend's current
two-thread setting also remains unchanged. Do not claim effective thread counts
were measured merely from constructor arguments.

The proposed focused control cases in `stage-proposal.json` cover source drift,
six-array construction, wrong public-row/hash failures before models, separation
of reference scoring from inference, existing single-recognition/lifetime checks,
final resource limits, and persistence. **None was executed during this task.**

## Acceptance scope

Evaluate the original acoustic criteria only after the owned worker exits.
Neither source-reader identities, reference times, expected count nor reference
text may enter recognition, alignment or acoustic inference. Unknown speech
continues to lower coverage; labels alone cannot establish attribution accuracy.
Review saved labels, unknown groups and text/timing against the raw turns and
original annotations, retaining lexical errors and optional-timing warnings.

A pass would establish one controlled three-reader integration result. It would
not establish Greek or natural-meeting accuracy, overlapping-speech support,
general word timing, long-recording resource use, whole-machine headroom, or
correctness of the baseline recognized words. All earlier failures remain intact.

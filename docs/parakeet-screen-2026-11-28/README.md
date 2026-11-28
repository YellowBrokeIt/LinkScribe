# Parakeet CPU development screen and frontend diagnosis

**The first int8 candidate completed but is rejected for adoption.** Independent
review of all eight original development cases found **four major errors, two
minor issues and two acceptable transcripts**. All mechanical checks passed;
those checks do not approve speech accuracy. A separate frontend-only diagnostic
then found an intentional version difference between the runtime frontend and
the older frontend published with the model. A single controlled recognition
ablation using that published frontend has now completed and is also rejected:
**four major errors, one minor issue and three acceptable transcripts**. It is
not a production change.

This work is an isolated recognizer screen. It does not exercise LinkScribe
provider acquisition, upload, storage, exports, speakers, a full film or a fresh
validation set. Application source, requirements and the production ASR policy
are unchanged. The screen uses the eight already exposed native English/Greek
clips and their original semantic criteria from
[26 November](../asr-2026-11-26/README.md).

## What completed

The original [plan](plan.json), [helper](run_screen.py) and
[pre-output contract review](contract-review.json) were frozen before execution.
Plan SHA-256 is
`3a828ee4eb972a62b7f985ea1566c1cba6bca8bbcdcacc43a2211066c84cec2c`;
helper SHA-256 is
`db64a85c594c15eb5061e9affd10a6ee66f2b28570cdb0548ecef8f72ddae9b0`.
The [raw report](int8-results/recognizer-report.json) has SHA-256
`6c4d06ec6dec4c68d3774f8274c5007b9d7da0ba5ddacb3c3d074b44ff620e1c`.

| Observation | Measured result |
|---|---|
| Execution | 2026-11-28 01:41:04.366831–01:41:14.435021 UTC; exit 0 |
| Inputs | Eight complete recordings, 52.44 s total, original WAV hashes verified |
| Attempts | One model initialization; one recognition per complete clip |
| CPU | Four fixed CPU cores; ONNX 4 intra / 1 inter threads; sequential execution |
| Time | 10.068 s controller total; 4.992 s model initialization; 3.297 s total recognition |
| Slowest clip | 0.691 s |
| Memory | 1,447,682,048-byte sampled process-group peak; 1,447,288,832-byte recorded worker peak |
| Frozen bounds | 2.5 GiB RSS; 90 s startup; 30 s per clip; 300 s total; none reached |
| Input/output binding | All eight full arrays, raw decoder tokens and vocabulary/frame mappings independently verified |
| Semantic review | 4 major errors; 2 minor issues; 2 acceptable |

The [independent all-case review](independent-review/independent-review.json)
has SHA-256
`af40b036a0f36cba482ab984aead8f0e52ea11a9b82e2b78e699c0e3d766238a`.
Its [mechanical audit](independent-review/output-binding-audit.json) preserves
all checks and actual resource measurements. The process completed and no
recognition worker from this first screen remains active.

## Meaning errors retained

| Original case | Review | Material observation |
|---|---|---|
| Greek camping provision, 1528 | Minor | Family/children proposition survives; camping and family wording is damaged. |
| Greek council/name, 1515 | Major | Fifth council and four years survive, but Μαρτελί becomes Μαρτέι. |
| Greek fairness, 1577 | Major | The second negative proposition stops before the word meaning fair. |
| Greek collision, 1598 | Major | Three is omitted, although is corrupted, and collision becomes invitation. The ending still says they were not injured; no clean negation reversal is claimed. |
| Greek beer descriptions, 1590 | Minor | Main names and negated description survive with lexical/spelling damage. |
| English satellite, 1548 | Acceptable | Condition and satellite statement preserved. |
| English UN fund, 1510 | Acceptable | Actor, fund and intended help preserved. |
| English Lakkha/bhajans, 1578 | Major | Both the proper name and named musical term fail the original criteria. |

These outcomes neither justify adoption nor justify a full-film extension of
this exact configuration. Raw hypotheses remain untouched. The comparison to
prior Small uses the completed
[Small VAD-off replay](../asr-2026-11-26/small-vad-off-regression-replay.json),
not the similarly named original report that contains only SOCKS setup errors.
The original Small/Turbo runs used explicit source-language arguments and the
normal application pipeline, so these are development observations rather than
a matched backend performance benchmark.

## Exact candidate and evidence limits

The source model is NVIDIA
[Parakeet-TDT-0.6B-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), with
Greek and English among its declared languages. This screen used Ilya Stupakov's
[ONNX conversion](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/tree/8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce)
at revision `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce`, exact published int8
encoder/decoder files, `onnx-asr==0.12.0`, `onnxruntime==1.32.0` and
`numpy==2.5.5`. All runtime, weight, audio and array identities remain in the
immutable plan and [runtime provenance](runtime-provenance.json).

No VAD, crops, volume adjustments, language hints, prompts, glossary, transcript
guidance or custom corrections were used. The original full WAVs were converted
through the predeclared normal audio decoder, including its signed-16-bit sample
conversion before float32 output. The independent audit verifies every converted
sample and complete array; it does not claim unchanged original float32 WAV
payload bytes. A reviewer initially assumed direct float32 identity, then
corrected that audit assumption while retaining its first checker and note.
The candidate inputs and helper did not change.

The recognizer returns token emission positions at 80 ms granularity. These are
not independently verified word boundaries, word-end times or subtitle cues.
Language labels are expected-language review metadata; this runtime does not
return a detected-language field. Offline/telemetry controls and denied Python
network attempts are recorded, without claiming packet-capture verification.

## Concrete frontend finding and completed diagnostic

The [frontend comparison](frontend-parity/README.md) used the eight same full
arrays without loading speech encoder/decoder weights. All eight comparisons
failed the tolerance fixed from the runtime release's own preprocessing tests.
The normal runtime reports `floor(N/160)` valid frames; the model-supplied older
ONNX frontend reports one more, and shared-frame normalization also differs.
Every NumPy feature hash exactly matches the original recognition screen.
All complete feature pairs and the independent consistency review are retained.

[Primary-source inspection](fidelity-research/README.md) ties this to an
intentional NeMo 2.5 compatibility change in the upstream runtime. It does not
establish that either frontend is the correct training/export contract or that
the difference causes the observed transcript errors. The coordinator authorized
one [same-int8 legacy-frontend ablation](legacy-frontend-ablation/README.md)
with all other inputs, settings, criteria and limits unchanged. It completed once
in 10.567 seconds with all eight structural checks passing, after the language
agent released the model slot. The missing fairness word returned, while the product name Number One changed
to Nummer One and the other material failures remained. The
[independent legacy review](independent-review/legacy-frontend-independent-review.json)
rejects adoption of this configuration as well.
Full-precision Parakeet weights and additional ASR candidates have not been
downloaded by this investigation.

## Audit trail and attribution

The original preparation README is preserved byte-for-byte as
[PREPARATION.md](PREPARATION.md), SHA-256
`6583e87fbc36a9f6f1b0329157e81c0bf5be998090cbfd9da375964a83a0aaeb`.
The historical [pre-execution freeze](pre-execution-freeze.json) names that file
as `README.md`; this current outcome page is its separately written successor.
The original plan, helper, criteria and other pre-execution files remain unchanged.
[manifest.json](manifest.json) binds the completed evidence and records that
historical README path mapping.

Preparation retained the initial unsigned dataset URL's HTTP 403 and its exact
same-recording recovery using fresh public URLs. It also records the audio-only
UCX warning and successful complete-array preparation. Neither failure was
hidden by changing fixtures.

NVIDIA's model and Ilya Stupakov's conversion are attributed under CC BY 4.0;
the runtime is MIT licensed. The source recordings/references are FLEURS by
Alexis Conneau and collaborators, Google Research, 2022, distributed under
CC BY 4.0 at dataset revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`.
Preserve those attributions and applicable licenses when redistributing the
weights, recordings or runtime. Model weights, original audio and virtual
environments remain outside the repository.

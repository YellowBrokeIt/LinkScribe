# Full large-v3 hosted result — failed meaning gate

The one authorized full-large-v3 CPU int8 screen completed all eight original development recordings within its resource limits. Independent review found **4 major errors, 1 minor error and 3 acceptable results** under the unchanged original criteria. Several meanings are clearer than in earlier candidates, but the original meaning gate remains failed. The model/default/release status is unchanged.

## Exact actual run

- Source commit: [`73b75b45bf6715627fac94d087ec4be8b93d353b`](https://github.com/YellowBrokeIt/LinkScribe/commit/73b75b45bf6715627fac94d087ec4be8b93d353b), isolated `qa/large-v3-a4ca88e-native` branch, parent `7ee0c7f2ac319d817ae9861a1d632a56ed62908e`.
- [Run 46102019808](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46102019808), [job 140846358625](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46102019808/job/140846358625): completed successfully. Run created 2026-11-28 03:16:05 UTC; final update 03:19:22 UTC.
- Artifact `15245622385`: 4,097,903 ZIP bytes; independently downloaded SHA256 `a2a0c88be3127dd9020d348c1a80f55cd48633ed32c66048710e61899e5a573b`, equal to GitHub's published digest. All 29 extracted files, totaling 7,344,745 bytes, were independently rehashed.
- Frozen [pre-output plan](../large-v3-screen-2026-11-28/plan.json) SHA256 `b9b779a48cb265e28c060fbf433d40e54058bb86290decc042e620ec363851f2`; helper SHA256 `cd7f933b27fc297fcdd0f1901657306ee90d17211ceae16dd0c4d9d23200c451`.
- Actual raw recognizer report SHA256 `26098ab9a14bc328d7c9aea77e43defadbec57d1055f8190976ecd492fc6485f`.

The model is the full `Systran/faster-whisper-large-v3` revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`, not Turbo. Actual native compute type was `int8_float32` on CPU, with one observed model worker and four requested CPU threads on affinity CPUs 0–3. The original production `_recognize` policy was executed unchanged: automatic language, beam 5, full PCM, VAD off, usual fallback, and conditional word timestamps disabled.

## Independent meaning review

| Case | Original classification | Actual observation |
| --- | --- | --- |
| Greek family camping | Minor | The meaning is preserved; `κατασκηνοτικούς` is a spelling defect. |
| Greek temporary council | Major | `Μαρτελί` becomes `Μαρτεή`. The fifth council and four-year interval survive. |
| Greek fairness | Acceptable | Both negative statements, including unfairness, are preserved. |
| Greek car collision | Major | Concession `Μολονότι` becomes malformed `Μόλον όταν`. Three people, collision and nobody injured are preserved. |
| Greek local beers | Major | `Manta` becomes Latin `Manda`. `Number One` and the descriptive meaning survive. |
| English satellite call | Acceptable | Meaning preserved; a separate native timing overrun is recorded below. |
| English UN warming fund | Acceptable | Meaning preserved. |
| English Lakkha/bhajans | Major | `Lakkha` becomes `Laka`; Singh, leading role and bhajans are preserved. |

The identity and relationship classifications use the previously fixed criteria, including the prior Lakkha/name standard. No negation reversal is alleged. [Every raw hypothesis](raw-case-summary.json), [the unchanged independent review](independent-review/independent-output-review.json), and [its binding audit](independent-review/output-binding-audit.json) remain available. The independent review's SHA256 is `8b53a650404c6b79fef7956879dfb0a7b77fe6fe71744ccd4c8711f01e068db8`; audit SHA256 is `1d812fd2cfd11611d8f685b83f494345323f803e11cd0f1b3b961730cecbb937`.

## Native timestamp overrun, retained without correction

The actual satellite-call recording contains 104,640 samples at 16 kHz, exactly **6.54 seconds**. Its native segment is `[0.0, 7.0]`, ending **0.46 seconds beyond the recording**. The screen deliberately retained that raw end and flagged it. All native intervals were finite and ordered, but that does not establish accurate subtitle or word timing.

No correction has been applied to this evidence. Any later production boundary fix must be evaluated and documented separately; this frozen result cannot certify a changed recognizer. The original helper's source-policy preflight remains bound to the policy that actually generated these outputs.

## Protocol, resources and independent consistency

All eight original WAVs and complete decoded arrays match their predeclared hashes. Each clip had one production recognition call, one full frontend call, and one native decoder call. The complete native iterator was consumed. All raw fallback/segment token sequences were independently checked through the pinned tokenizer, and native timestamp splitting agrees. No sequence reached the native length cap. This is not an exposed-EOS claim.

Actual settings, native/production text, token strings, confidence/repetition data and native segment times are retained. The only native option normalization is `clip_timestamps` from the default string `"0"` to `[0.0]` when the native iterator starts. Seven installed direct wheel hashes agree with the pinned runtime. Inference recorded no Python network attempts.

- One Whisper initialization: **8.517 seconds**.
- Eight recognition calls: **136.213 seconds** total for **52.44 seconds** of full audio; slowest clip **20.095 seconds**, below the 180-second limit.
- Worker total **146.763 seconds**; controller total **147.221 seconds**, below the 1,800-second limit.
- Sampled owned-process-group peak **3,239,559,168 bytes (3,089.48 MiB)**.
- Worker OS high-water **3,247,071,232 bytes (3,096.65 MiB)**, below the 6 GiB bound.
- All **1,345 RSS samples** are retained and independently recompute the reported peak. Sampling is a measured stop policy, not continuous kernel memory containment.
- Exit status 0, no limit stop, and no live owned group members after completion.

The model-file identity check is explicitly a hosted download/hash record; model weights were not downloaded locally or included in the artifact. Raw feature tensors were not uploaded, so their recorded fingerprints cannot be recomputed from retained tensors. Complete input arrays, raw decoder/segment tokens, effective settings and the resource sample series are retained. No fresh validation, full-film, application installation, subtitle accuracy, optional speaker or stable-release approval follows from this eight-clip screen.

## Separate ordinary CI snapshot

[Independent QA run 46102019804](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46102019804) is separate from the recognizer's meaning gate. In the retained 03:24:24 UTC snapshot, Python 3.11 and 3.13 each passed **731 tests plus 54 subtests**; fresh Linux installation and actual upload/Whisper/SQLite/exports also passed. The optional Ollama job was still running at that snapshot. These historical statuses are not claims about a later observation, and they do not change the semantic rejection above.

`artifact/` retains the complete extracted hosted output. Adjacent run/job metadata, job log, ZIP verification, file manifest, compact summaries and unchanged independent reports bind the actual observation. The FLEURS recordings/references remain the original CC BY 4.0 Google/Conneau et al. source under the already frozen dataset revision and URLs. No source, prompt, reference criterion, threshold or output has been changed to fit this result.

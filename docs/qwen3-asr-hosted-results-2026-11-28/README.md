# Qwen3-ASR native hosted result — rejected development candidate

The one authorized CPU FP32 screen completed all eight original exposed clips under the frozen protocol. Independent meaning review found **six major errors and two acceptable results**. This candidate is rejected for adoption; no alignment implementation, production default change, new input, or additional inference follows from this result.

## Exact run and provenance

- Commit: [`7ee0c7f2ac319d817ae9861a1d632a56ed62908e`](https://github.com/YellowBrokeIt/LinkScribe/commit/7ee0c7f2ac319d817ae9861a1d632a56ed62908e), isolated `qa/qwen3-asr-a4ca88e-env` branch.
- Run: [46099257439](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46099257439), job [140837721855](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46099257439/job/140837721855), both completed successfully. Created 2026-11-28 02:40:49 UTC; final run update 02:44:17 UTC.
- Artifact: `15244707388`, `qwen3-asr-native-fp32-7ee0c7f2ac319d817ae9861a1d632a56ed62908e`, 4,148,654 ZIP bytes. The independently downloaded ZIP SHA256 equals GitHub's published digest: `3f5d7635edb1caed673e046e631fee82561f3524c29bbc517b8b0182224ffd1f`.
- Corrected plan: `a46131a56018ad24f70faa76cea1d206407358271ff60fab1dbe1afd6bb72380`; unchanged helper: `f578d2b534506e42f8636d45bd5d43d2fea64902961ad265f62b82b3a5d0fc8f`.
- Native recognizer: `Qwen/Qwen3-ASR-0.6B-hf` revision `7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c`; Torch `2.15.0+cpu`, Transformers `5.13.0`, FP32, four CPU threads, automatic source language, no target language or text guidance.

The original [preparation](../qwen3-asr-screen-2026-11-28/README.md) and [path-only hosted correction](../qwen3-asr-hosted-env-followup-2026-11-28/README.md) remain separate and unchanged. Original run `46098646055` failed workflow expression validation before any job existed: zero jobs, zero artifacts, and no model attempt. That failure is not a recognition-quality result.

## Meaning outcome under the original criteria

| Original case | Independent outcome | Concrete observation |
| --- | --- | --- |
| Greek family camping | Major | Festivals becomes `βασιλεία`; the special-area relationship becomes `δικούς`. |
| Greek temporary council | Major | The fifth council and four years survive, but `Μαρτελί` becomes `Μαρτείου`. |
| Greek fairness | Major | The first negative survives; the second predicate is garbled as `δεν ταινίκιο`, losing the unfairness statement. |
| Greek car collision | Major | Collision becomes invitation and the injury predicate is garbled. Negation tokens survive; this is not claimed as a demonstrated polarity reversal. |
| Greek local beers | Major | `Number One` becomes `Ναμβρούαν` and descriptive predicates change. `Manta` → `Μάντα` is credited as an acceptable transliteration. |
| English satellite call | Acceptable | Meaning preserved. |
| English UN warming fund | Acceptable | Meaning preserved. |
| English Lakkha/bhajans | Major | `Then, like a singer, to delete and singing the passions.` loses the person, leading role and song term. |

[Exact raw hypotheses](raw-case-summary.json) and the [unchanged independent review](independent-review/independent-output-review.json) preserve every case. The graded field is `raw_transcript_without_repetition_repair`; the native parser rewrote none of these eight hypotheses. No repair, glossary, reference hint or changed threshold was applied.

## Completion and measured resources

All eight complete PCM arrays match the originally frozen recordings. Each clip had one recognition attempt, one full frontend call and one bound encoder call. All eight returned the unchanged native input prefix and the complete observed generated sequence, ending at a permitted native EOS with no following tokens. Exactly one model was initialized, offline inference recorded no Python network attempts, and all model-file download records match the pinned byte sizes and SHA256 values.

- Model initialization: 5.404 seconds.
- Recognition sum: 94.016 seconds for 52.44 seconds of complete audio; slowest clip 23.620 seconds, below the 90-second per-clip bound.
- Worker total: 100.404 seconds; controller total: 101.433 seconds.
- Sampled owned-process-group peak: 4,766,765,056 bytes (4,545.94 MiB).
- Worker `ru_maxrss`: 5,269,831,680 bytes (5,025.70 MiB), below the declared 6 GiB bound.
- Exit status 0, no limit stop, and no live owned group members after completion.

The [independent binding audit](independent-review/output-binding-audit.json) reproduces original WAV/full PCM, sequence/token/EOS/parser and retained record consistency checks without running a model. It explicitly distinguishes model-file hashes reported by the hosted worker from locally available weights. Raw feature tensors and the complete RSS sample time series were not uploaded, so they cannot be retrospectively recomputed from this artifact; recorded frontend identities and peak/limit records are retained. The screen is recognizer-only development evidence, with no fresh validation set, application integration, word timestamps, subtitles or speaker approval.

## Retained evidence

`artifact/` is the complete safely extracted hosted artifact, including raw recognizer report, all original WAVs and full decoded arrays, progress/token records, installation records, and resource/cleanup evidence. The ZIP itself is represented by its verified digest and byte count; [artifact-file-manifest.json](artifact-file-manifest.json) binds every extracted file. [hosted-run.json](hosted-run.json) and [hosted-job.log](hosted-job.log) preserve exact final run/job metadata and logs. [runtime-wheel-identities.json](runtime-wheel-identities.json) is a compact derivative of the complete pip report.

The [integration feasibility note](integration-feasibility/integration-risk-note.md) preserves source-only research about native untimed output and a separate Greek CTC aligner. It identifies real timestamp, mixed-script, number, preprocessing, memory and dependency issues. It does not establish an approved integration route, and the recognition rejection means no alignment execution is justified for this candidate.

The original FLEURS recordings/references are attributed to Conneau et al. / Google FLEURS (2022), CC BY 4.0, at the original revision and source URLs retained in input preparation and the frozen fixture inventory. There are no model weights in this bundle. `manifest.json` binds this result bundle after the independent review was copied unchanged.

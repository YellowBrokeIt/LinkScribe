# Source-only PERSON detector screen: raw profile rejected

The single GLiNER screen completed within its execution and resource limits, but it **fails the predeclared exact-name-span gate**. Independent review found five fully correct cases out of six and 12 exact matches among 13 personal-name mentions. The remaining prediction includes a Greek grammatical article with the name. Directly protecting that entire span would leave ordinary source-language prose untranslated.

This was a detector experiment only: six native calls, no translations, no masking, no model retry and no production change. All original raw results remain intact. The two preceding Krikri translation profiles remain rejected.

## Fixed experiment

The [frozen research and plan](../name-span-protection-research-2026-11-28/proposal.md) identify the public Apache-2.0 `urchade/gliner_multi-v2.1` checkpoint at revision `443d26d654e0324125a96bebd8e796c14ff2efe6`. The selected safetensors is 1,155,830,112 bytes, SHA-256 `2100142f31627531497850659dcb3821c99d5e71c08a8e01a98e4b11ef32a199`. The native checkpoint contains 288,949,504 F32 elements. Its tokenizer and official encoder configuration are independently pinned; no second backbone weight or pickle checkpoint was fetched.

The profile used GLiNER 0.2.24 with the existing isolated CPU Torch 2.11.0 and Transformers 4.57.6 runtime, four compute threads, one interop thread and a four-CPU affinity. Only the four declared additional wheels were installed into a new package target. The reused dependency environment remained unchanged. Native prediction settings were `labels=['person']`, threshold 0.5, flat spans, multi-label disabled, batch size one and no inference packing. There was no quantization, fitting or threshold sweep.

The worker's input was the fixed source-only projection of the six original exposed development cases. It contained original source text and segment metadata, with no reference translations, expected names or semantic criteria. Each complete case joined both original segments by LF with a retained offset map. Independent person annotations were frozen before any output and remained outside the worker until the completed review was archived.

The final inference freeze is `7d8717e10fe81fcf3a2d215996b33913f7c7134886af83362354d54268d4c545`. The underlying plan is `1a56796eb75a709c9231354ff17ca7b9f23be9988e3ddbc30ba0492433b2b9d5`.

## Independent source-span result

| Original development case | Required mentions | Returned spans | Exact matches | Decision |
| --- | ---: | ---: | ---: | --- |
| Transcript terminology | 1 | 1 | 1 | Correct |
| People and roles | 6 | 6 | 6 | Correct, including repeated mentions and distinct Greek names |
| Bitcoin amounts | 0 | 0 | 0 | Correct empty result |
| Negation scope | 1 | 1 | 1 | Correct |
| Conditional publication | 4 | 4 | 4 | Correct |
| Uncertain question | 1 | 1 | 0 | Overextended article-plus-name span |

The final raw prediction is `[0,7) "Η Μαρία"`, with score `0.9357870817184448`. The independently annotated name, frozen before output, is `[2,7) "Μαρία"`. The grammatical article and following space are outside that personal name. Nothing has been stripped, relabeled or repaired in the raw output.

The conventional exact-span counts are 12 true positives, one false positive and one false negative. The false positive and false negative describe this same boundary error, not two separate failures. No person was wholly uncovered and no disjoint non-person entity was returned. The high score on the wrong boundary illustrates why confidence and source-substring equality do not certify a suitable name span.

The complete independent decision is [independent-output-review.json](independent-output-review.json), SHA-256 `6c42cc925456fdd3b827ab86d34da01c773f50d125f6da0787ba9a212fc8206b`. The separate [completed protocol audit](independent-completed-output-protocol-audit.json) verifies the native inputs, source bindings and resource evidence; its SHA-256 is `0b7c2399bc4678d6fb1cd4858aa6654bb979b18314e0e8907d808708bfe4ffe3`.

## Actual execution and resource evidence

| Phase | Result | Elapsed | Peak summed RSS | Peak summed PSS |
| --- | --- | ---: | ---: | ---: |
| Exact acquisition and isolated installation | All six objects verified once | 64.955 s | No model loaded | No model loaded |
| Tokenizer/configuration/native-collator preparation | Complete, zero entity-model forwards | 9.580841 s | 659.6 MiB | 653.4 MiB |
| Six native detector calls, including initialization and exit | Complete; protocol and limits passed | 17.557703 s | 2,492.2 MiB | 2,462.9 MiB |

The external detector limits were 6,144 MiB process-tree RSS, 180 seconds for initialization, 60 seconds per complete source case and 600 seconds overall. The complete-case time ceiling is stricter than the authorized ceiling per source segment. Each case received exactly one call. All six native model forwards and all six underlying DeBERTa forwards match the full uncropped preflight arrays, with complete encoded lengths 47, 70, 59, 65, 41 and 63. Every source word is represented; no source was cropped, chunked or normalized.

Native strict loading reported 224 state keys, no missing keys and no unexpected keys. The actual model has 288,949,504 CPU float32 parameters. Both tokenizer vocabulary and checkpoint embedding rows are 250,105. Full checkpoint tensor offsets, lengths and element counts were independently checked.

There are 169 complete inference resource samples, retained in `infer-samples.jsonl`. Sampling and process-tree scope are documented in `infer-resources.json`: summed RSS may double-count shared pages, and sequential scans can miss an instantaneous transient peak. The observed headroom is 3,651.8 MiB under the process cap. This establishes fit for these short standalone detector inputs; it does not establish combined app memory or long-transcript performance. The owned worker and any descendants were confirmed stopped, and the local model slot was released.

The acquisition left 1,821,130,752 bytes free. Immediately before inference, 1,793,011,712 bytes were free, above the 1 GiB reserve. The weight and tokenizer are hardlinked from one content-addressed allocation. No cache was deleted and no shared runtime was overwritten. Payloads remain outside the repository.

## Preserved setup defects and corrections

Independent review found two concrete problems before any entity-model forward. The initial supervisor could report success after a worker exited while an undiscovered child survived in its original process group. A harmless independent probe demonstrated that false success, then killed the child. The initial model hook also expected a per-item list of label maps, although this pinned native input produces the shared mapping `{1: 'person'}`. The native call would have been rejected before reaching its encoder.

Both original scripts, the failed cleanup probe and the original controls are preserved under `initial-protocol-review`. Independent findings are copied unchanged beside them. The corrected observer enumerates the original process group/session after leader exit, retains identified descendants in later samples, sends TERM/KILL independently of leader liveness and rejects a normal leader exit that leaves a live child. Four revised no-model controls pass, including a surviving child that ignores TERM. Their exact helper is `verify_observer_v2.py`.

The corrected native guard requires the exact shared label mapping. Tokenizer-only preparation also exercises the real collator without constructing the entity model. Both actual-forward hooks save observed tensors and metadata before rejecting any mismatch. Seven source-span integrity controls cover source-text substitution, wrong labels, nonfinite scores, overlaps, segment crossing and split graphemes. The first combined control harness used the observer interpreter without `regex`; its completed resource controls and error were retained, and only the span probes were run in the already-declared interpreter that contains the dependency. No model or dependency was changed for that correction.

A code-mode communication reset interrupted polling after the model phase had completed. The completed worker and supervisor files, all six raw outputs, complete samples and cleanup were inspected before proceeding. No phase was restarted and no second prediction was attempted.

## Decision boundary

The raw detector profile remains rejected for direct use in protected translation. A separately frozen, source-only boundary-normalization proposal may investigate the observed article prefix. It must preserve this raw span and score, use generic source grammar rather than fixture names, retain exact source offsets, and pass independent review before any retained-output replay. That investigation is separate evidence and cannot retroactively turn this raw detector result into a pass.

No translation, masking, new validation, summary experiment or production integration follows automatically from this screen. Original-script personal names remain compatible with the existing translation criteria in principle; ordinary prose, complete actor relationships and all other facts still require correct translation and independent review.

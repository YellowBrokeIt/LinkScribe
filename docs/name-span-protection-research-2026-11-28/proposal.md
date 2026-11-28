# Source-derived personal-name protection: feasibility and bounded detector plan

## Decision and scope

There is one plausible next mechanism to test: detect personal-name spans from the actual source with the public `urchade/gliner_multi-v2.1` model, then, in a later separately reviewed experiment, protect those exact spans through translation with reversible identifiers. The immediate proposed experiment is **recognition only** on the six original exposed development sources. It produces spans and scores, not translations or corrected names. No existing model result is regraded.

The model is small enough to justify measuring its CPU load and inference within the 6 GiB process budget. Its Greek personal-name accuracy is unmeasured. The publisher's multilingual claim and the backbone's Greek language evidence do not establish that it will find these names, distinguish names from ordinary words, or preserve meaning after masking. A detector pass would support a subsequent translation experiment only.

Root conditionally authorized this single detector stage after the concrete plan is frozen and independent protocol review has no blocker. The controls are recorded in `detector-screen-plan.json`: one pinned model and profile, no download retries or alternate weights, no cache deletion, at least 1 GiB disk reserve, four CPU threads, a 6,144 MiB externally observed process-tree cap, 180 seconds for initialization, 60 seconds per complete source case, and 600 seconds total. Applying the 60-second ceiling to each whole case is stricter than the authorized ceiling per original source segment. Each case contains two unchanged segments; they are processed together once with a retained offset map. There is no translation, masking, additional corpus, heldout access, or production change in this stage.

## Why this addresses the observed failure

Both frozen Krikri screens were independently judged five acceptable and one major error. The failing case substituted culturally equivalent English names for the actual Greek names. A general instruction to preserve faithful transliterations did not fix that behavior. The original outputs, raw calls, resources and independent reviews remain unchanged in `../krikri-screen-2026-11-28` and `../krikri-name-preservation-2026-11-28`; `prior-evidence-immutability.json` verifies every file in both manifests.

Source protection would remove the spelling decision for detected name occurrences from the translator. An occurrence's output spelling would be the exact source slice selected before translation, not a translation chosen from a supplied answer or a replacement learned from the test fixtures. This can address substitution only when detection and marker handling are correct. It does not repair a wrong actor, pronoun, possession, number, condition or sentence meaning.

The independent criteria note, retained as `independent-criteria-and-design-review.json`, confirms that original-script personal names are compatible with the existing acceptance criteria. Reasonable transliteration is allowed, not required. Ordinary prose still has to be translated, and roles and facts must remain correct. Keeping a genuine Greek name in an English sentence is therefore potentially acceptable; preserving an ordinary Greek phrase because the detector wrongly called it a person is not.

## Exact candidate and primary evidence

| Item | Selected identity or finding |
| --- | --- |
| Entity model | `urchade/gliner_multi-v2.1` at revision `443d26d654e0324125a96bebd8e796c14ff2efe6` |
| Access and declared license | Public, ungated; Apache-2.0 |
| Selected weight | `model.safetensors`, 1,155,830,112 bytes; SHA-256 `2100142f31627531497850659dcb3821c99d5e71c08a8e01a98e4b11ef32a199` |
| Actual model metadata | 288,949,504 F32 parameters; the card's older 209M table entry is not the storage estimate |
| Backbone support | `microsoft/mdeberta-v3-base` at `a0484667b22365f84929a935b5e50a51f71f159d`; declared MIT |
| Tokenizer payload | `spm.model`, 4,305,025 bytes; SHA-256 `13c8d666d62a7bc4ac8f040aab68e942c861f93303156cc28f5c7e885d86d6e3` |
| Native detector limits | 384 source word tokens; maximum entity width 12 words; encoder maximum 512 subtokens including prefix and special tokens |
| Library | GLiNER 0.2.24; audited source commit `4610b5527e4bcdb37358ce80ef7c5cc0d16c1860` |
| Fixed profile | `labels=['person']`, threshold 0.5, flat spans, no multi-label prediction, batch size one, no inference packing, CPU float32, native evaluation mode |

These identities come from the [official model repository](https://huggingface.co/urchade/gliner_multi-v2.1/tree/443d26d654e0324125a96bebd8e796c14ff2efe6), [official model configuration](https://huggingface.co/urchade/gliner_multi-v2.1/blob/443d26d654e0324125a96bebd8e796c14ff2efe6/gliner_config.json), [Microsoft's model card](https://huggingface.co/microsoft/mdeberta-v3-base/tree/a0484667b22365f84929a935b5e50a51f71f159d), and the [pinned GLiNER source](https://github.com/urchade/GLiNER/tree/4610b5527e4bcdb37358ce80ef7c5cc0d16c1860). Exact small API objects, configurations, source files, acquisition URLs and hashes are retained here. Microsoft's card reports Greek and English XNLI results and multilingual CC100 pretraining. That is evidence of language coverage, not a Greek NER benchmark. No adequate Greek name-recognition result was found in the selected model card.

## Reuse of the existing CPU environment

The production requirements and installed app environment contain no trained PERSON recognizer. Tokenizers and SentencePiece do not provide that classification by themselves. The earlier isolated M2M environment already contains Python 3.12.14, CPU Torch 2.11.0, Transformers 4.57.6, Tokenizers 0.22.2, Hugging Face Hub 0.36.2, SentencePiece 0.2.1 and Safetensors 0.8.0. Their versions and distribution metadata hashes are recorded in `runtime-dependencies.json` without importing a model.

The plan reuses that interpreter and its existing packages read-only. Four exact wheels are added to a new owned package target: GLiNER 0.2.24, CPU ONNX Runtime 1.32.0, Protobuf 7.36.2 and FlatBuffers 25.12.19. Their combined compressed size is 28,301,975 bytes. The installed GLiNER package imports ONNX Runtime even though the selected execution path is PyTorch; this is not an ONNX conversion experiment. Protobuf supports the standard tokenizer conversion. The actual wheel tags have been checked against this CPython 3.12 Linux interpreter; hashes, URLs, licenses and requirements are fixed in the plan. No packages will be installed into the app or existing M2M environment.

The official GLiNER loader can initialize the DeBERTa architecture from its configuration and load the complete entity checkpoint without fetching another encoder weight. It also has a convenience downloader that fetches the whole repository, including both safetensors and a second 1.156 GB pickle checkpoint. That helper will not be used. Only the selected safetensors, pinned configuration files and SentencePiece payload are staged in a local model directory.

The proposed local GLiNER configuration changes only the model path and adds the exact pinned encoder configuration. The selected `DebertaV2Config` branch constructs the standard Transformers `DebertaV2Model`; it does not use the library's other remote-code branches. Tokenizer files have no `auto_map`. Local-only/offline operation, the actual encoder/tokenizer classes, absent optional architecture replacements, and strict state loading must be checked. A missing key, unexpected key, incompatible tokenizer conversion or attempted network fallback is a setup failure, not permission to relax loading or download more weights.

### Resource and disk feasibility

The selected weights occupy about 1.08 GiB. Loading may temporarily hold initialized tensors and checkpoint tensors together, plus the Python runtime and activations, so the file size is not a RAM measurement. The 6,144 MiB external stop covers imports, initialization and all detector calls. RSS, PSS, CPU and system-memory observations are retained. Sampling cannot prove there was no unsampled instantaneous peak.

At plan creation, free disk was 3,089,633,280 bytes. The full stage allocation budget is 1,428,570,593 bytes: the model and tokenizer plus 256 MiB for downloaded wheels, unpacked packages, configurations and reports. That projects 1,661,062,687 bytes free, above the required 1,073,741,824-byte reserve. Before starting, at least 2,502,312,417 free bytes are required. Each phase rechecks actual space and stops before breaking the reserve or stage budget. Weights are streamed into one content-addressed file and hardlinked into the local layout, avoiding a second physical copy. No existing cache will be removed.

The detector must exit completely before a later Krikri stage. Krikri's latest isolated screen already reached 5,538.5 MiB RSS, leaving only 605.5 MiB under the same cap. There is no basis for keeping a 1.08 GiB entity model resident beside it. Sequential process isolation is a requirement, and whole-app fit remains unproved.

## Full-source detector protocol

The worker receives `original-six-source-only.json`, SHA-256 `547c4edca0db2801d07d7cf6588655c062fb870a20b455560395eccdc9de3482`. It is a whitelist projection of the original corpus `48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce`. Original segment dictionaries and text are unchanged. Reference translations, semantic criteria, lexical flags and expected-name inventories are excluded. Case IDs and language metadata identify reports; only joined source text and the literal entity label `person` enter the model.

For each case, join all original segment texts with a single LF and retain exact codepoint ranges back to each segment. No stripping, normalization or sentence truncation is allowed. The six complete sources contain 30, 30, 42, 29, 26 and 31 tokens under the library's native regex splitter. This was checked with standard-library text processing only. Actual SentencePiece counts remain unmeasured.

The library can truncate at two different layers: it cuts source words beyond `max_len=384`, and its transformer tokenizer is called with `truncation=True`. The screen therefore independently constructs the entire native `<<ENT>>`, `person`, `<<SEP>>` prefix and source word sequence, encodes it with `truncation=False`, and preserves all IDs, masks and word mappings. It requires at most 384 source words and 512 complete encoded tokens. Before the actual forward operation, the observed native input IDs, attention mask and source-word mask must equal this uncropped preflight and account for every source word. Any mismatch, warning, overflow or missing word stops the case before the forward. No chunking or changed limit is permitted for this initial screen.

Each source receives one native prediction call with the fixed profile. Preserve the raw list and scores first. Then validate exact half-open offsets, source substring equality, finite scores, the `person` label, full grapheme boundaries and nonoverlapping spans. Map each span to its original segment. A span crossing the inserted separator or original segment boundary is a reported failure for this prototype, not an invitation to combine timestamps or adjust its boundaries.

The independent reviewer assesses every actual personal-name mention and every proposed span from source text. Repeated occurrences count separately. Missing people, ordinary prose marked as a name, partial names, and incorrect boundary extensions are failures; there is no threshold search or manual fill-in. Any reference annotations used by the reviewer stay outside the worker input. All six must satisfy full-source, span, coverage and resource checks before a protected-translation experiment is even proposed. This small exposed screen cannot establish general precision or recall.

## Proposed reversible protection, outside the current execution scope

If the detector screen justifies a later experiment, the following is the concrete design to review and freeze before translation.

1. Snapshot the original segments and source hashes. Accept only validated, source-derived PERSON spans with exact segment-local offsets. Do not merge aliases, infer a nominative form, translate names, or add a missed name using a dictionary.
2. Assign a distinct opaque marker to each occurrence, using a fixed ASCII grammar such as `__LSP_<128-bit-random-nonce>_<six-digit-occurrence>__`. Generate and freeze the nonce and mapping before the model request. Reject source text containing the reserved prefix or a possible marker collision before masking. Do not tune the nonce using model outputs.
3. Replace only those exact spans and prove that unmasking the resulting source reconstructs the entire original text byte for byte. Keep the mapping private to deterministic restoration; no list of reference names or translations is supplied to the model.
4. Preserve complete markers at translation fragment boundaries. The existing app fragmenter can fall back to arbitrary character boundaries, so masking followed by that fragmenter unchanged is insufficient. A future isolated implementation must treat markers as indivisible, retain complete-source reconstruction, and account for serialized bytes and full native prompt/output budgets without cropping.
5. Give only a generic instruction that opaque identifiers must be copied exactly. The initial prototype should require each output fragment's marker inventory and relative marker sequence to equal its source fragment's. Reject missing, duplicate, unknown, malformed or migrated markers. This conservative ordering rule can reject a valid translation that legitimately reorders people; record such a rejection, without weakening the rule after viewing results.
6. Restore exact source slices with one nonrecursive parser pass after structural validation. Source names are data, never replacement programs, executable code or markup. This operation must not search for and repair a localized name in generated prose. A corrupted marker rejects the whole translation; no partial result is persisted.
7. Reapply the app's response, script and identity guards against the original unmasked source and preserve every source segment's count, order, timestamp and speaker metadata. Retain raw model content, marker map and restored text separately. Independent semantic review still uses the unchanged original criteria.

Correct marker counts do not establish correct relationships. A model can preserve both name markers and still reverse who acted, negate the wrong proposition or produce a wrong pronoun. Exact marker order reduces one easy substitution mode but does not solve that problem. Extra hallucinated names can also occur outside markers. These remain semantic failures even if the reversible mapping is perfect.

### Inflection, uncertain entities and longer sources

Greek case endings and spelling variants are kept exactly as observed. A genitive or accusative mention may look awkward in an English sentence; guessing a new form would break the source-only contract. Masking can also remove gender and morphology cues that help the translator choose pronouns and agreement. Such errors are not excused by correct names.

Names can also be ordinary nouns, especially when capitalization, punctuation or ASR casing is weak. A detector may protect an ordinary word, miss a real person, include a title or omit part of a compound name. Its confidence is not a certificate that all names were found. The prototype fails closed for structural corruption, but it cannot automatically fail closed for every undetected semantic error. The independent source review is necessary to measure that limitation.

Long transcripts need a separately tested window policy. A plausible later design uses exact source-word windows bounded by both native word and encoded-token limits, with overlap at least the 12-word maximum entity width. Duplicate predictions can be deduplicated only by identical source offsets and text; conflicting overlapping spans and segment-crossing entities require explicit rejection rather than silent selection. Such windows do not guarantee boundary recall. The present six-source screen has no windows and makes no long-transcript claim.

Reserved-marker collision checks and JSON/UTF-8 validation prevent accidental restoration collisions and malformed mappings. They do not prove the translation model will ignore instructions inside transcribed speech. The source remains untrusted data, and no arbitrary action or executable substitution follows from it.

## Required evidence and decision boundary

The recognition stage must retain exact downloads and hashes, installed dependency identities, local-config derivation, offline/class/strict-load evidence, all actual tokenizer and forward inputs, the six raw span lists, exact source and metadata bindings, timing/resource samples, failures and owned-process cleanup. Runner and observer hashes are frozen before inference. Private logs that expose proxy or environment values do not enter the repository.

A failure is retained and the fixed profile stops on execution or resource failure; no fallback model, lowered threshold, changed input or manual name list is introduced. A successful recognition screen means only that this source-derived detector mechanism merits a separately authorized protected-translation trial. It does not establish translation correctness, summary correctness, whole-app memory fit or readiness for v1. Both rejected Krikri bundles and unused validation remain untouched.

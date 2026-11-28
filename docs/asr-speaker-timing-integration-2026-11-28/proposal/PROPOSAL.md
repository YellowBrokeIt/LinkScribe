# Proposed integration: speaker timing after fixed recognition

**Recommendation:** make optional speaker timing a separate, best-effort phase
after one complete baseline recognition pass. Keep the baseline transcript as the
authoritative fallback, and return timing warnings through a separate structured
result. This proposal makes no production change and authorizes no model run.

The reviewed offline local-fallback result now passes the six original broad
segment windows, with only three of six private-word windows available. It has
validated word evidence in 78 of 86 film segments; four short candidates remain
exactly unchanged. The full independent review still identifies large movements
around “Oh,” “Sorry” and “I'm sorry.” These results support a reliability design,
not general acoustic accuracy, word timing, speaker accuracy or ASR approval.
The original global-fallback profile remains rejected and unchanged.

## 1. Concrete current coupling

At source `6de3faddf88bb5da8ea35d985b33ad26e55e249f`, both link and upload paths
pass `word_timestamps=True` into `_recognize` when speakers are requested.
`_recognize` forwards that option to the one `WhisperModel.transcribe` call.
The inspected faster-whisper 1.2.1 `generate_segments` branch then changes the
next recognition seek from the last aligned word when applicable. This can
change later recognized text; the earlier word-timestamp experiments established
that turning this branch on is not a text-preserving timing operation.

The baseline already has the right acceptance checks: one complete 16 kHz
decode, exact duration limit, exact digital-silence rejection, no VAD cropping,
normal temperature fallback, beam five, disabled previous-text conditioning,
physical segment bounds, and full-output no-speech corroboration when required.
These remain in place and finish **before** optional alignment.

## 2. Proposed processing sequence

1. Decode once and keep the same full sample array throughout recognition and
   optional timing. No source change, trimming, resampling a second time or VAD
   compression is introduced.
2. Call `engine.transcribe` exactly once with `word_timestamps=False`. Preserve
   all other existing recognition settings, including normal fallback and
   automatic language selection. Exhaust the generator. Build the current
   bounded public baseline segments exactly as today.
3. Only when speaker timing was requested, retain transient copies of each
   yielded native segment's exact text, token IDs, seek and original interval.
   Keep leading spaces in native text; do not recover tokens by re-encoding the
   stripped public text. Do not add these fields to public segment dictionaries.
4. Complete the current empty-output and all-no-speech checks on the unchanged
   baseline and full audio. A rejected baseline never proceeds to alignment.
5. Release the exhausted recognition generator's references, then run a separate
   `align_fixed_segments` helper on copies, using the same cached model object,
   same complete audio and the already detected language. It has no transcribe,
   generation, language-redetection or model-construction route.
6. Apply the reviewed complete upstream timing postprocessor and iterative
   both-endpoint baseline fallback. Preserve every original source string/token
   and its position. Only the existing transient `_words` field is attached to
   candidate segments. Invalid optional words clear that entire segment's word
   evidence; they never discard recognized text.
7. Return baseline and optional speaker-input candidates separately. Speaker
   analysis consumes the candidate only when it exists. If timing fails, use
   baseline segment copies with empty `_words`, preserving the existing
   whole-segment/unknown-speaker fallback and its visible warnings. If acoustic
   speaker analysis itself fails, save the authoritative baseline, with its
   original segment boundaries and the accumulated warnings.
8. Strip `_words` on every persistence path, including failure paths, as today.
   Save only approved small provenance and warnings. Other enhancements run
   after audio work, under the existing audio-model release policy.

The guarantee is per recognition pass: postprocessing cannot change the text
that this pass produced. Separate recognition runs can still differ under the
existing normal fallback; identical outputs across independent runs are not
promised or used as the only regression check.

## 3. Native window and tokenizer contract

`Segment.seek` is an integer **feature-frame offset**, not a segment's start time
or seconds. The regular generator records `previous_seek` before splitting the
decoded token sequence, and every yielded subsegment from that encoder window
receives that original offset. Do not replace it with `round(segment.start*100)`.

Collect contiguous equal-seek groups in original output order; require strictly
increasing offsets between groups. Windows omitted by recognition's no-speech
logic require no alignment call. Never synthesize their text or fill their gaps.

The full frontend must run on the complete original array, because its dynamic
range normalization uses the whole recording's log-mel maximum. Computing the
frontend separately on cropped windows would change the features. For the first
integration, recompute the full frontend only after the recognition generator
has released its feature matrix. Reuse the same decoded samples. Avoid global
monkey-patching of the cached engine or generator-frame introspection merely to
avoid this additional frontend pass.

Derive each window from the actual engine:

- `content_frames = features.shape[-1] - 1`;
- `num_frames = min(feature_extractor.nb_max_frames, content_frames - seek)`
  for the unchanged full-recording clip policy;
- offset in seconds is `seek * feature_extractor.time_per_frame`;
- slice the full feature matrix at the exact seek and pad using the engine's
  original maximum window length;
- require feature rows to equal `engine.model.n_mels` and use the engine's
  actual sampling rate/hop/stride attributes;
- construct the timing tokenizer from `engine.hf_tokenizer`,
  `engine.model.is_multilingual`, task `transcribe` and `info.language`;
- derive EOT and the start sequence from that tokenizer, preserving original
  text-token IDs and checking exact native text decoding before alignment.

No hard-coded Small model mel dimensions, language IDs or encoder widths enter
the production adapter. A terminal path row at text index N remains a boundary,
not an added word; native zero/degenerate timings can still invalidate optional
word evidence. Preserve the complete original token coverage and punctuation
mapping. Use the actual upstream `get_end` sequential-state update on adjusted
copies, before projection, never the timing method's different return value.
Do not execute any of the recognition seek-update or hallucination-filter logic.

An incomplete token/window map, nonfinite state, encoder mismatch, unsupported
interface, window shorter than the native stride, missing/unknown detected
language, or malformed native result means timing is unavailable. It does not
cause another recognition attempt or a guessed time. If a late window fails,
discard the incomplete timing candidate and return the whole accepted baseline.

## 4. Configured model compatibility

The four currently selectable aliases all use the regular `WhisperModel` and
the same `Segment`/seek interface; the app does not use BatchedInferencePipeline.
The wrapper must not import the batched pipeline's different chunk bookkeeping.

| App alias | Resolved publisher in installed 1.2.1 | Feature rows | Alignment evidence inspected |
|---|---|---:|---|
| tiny | Systran/faster-whisper-tiny | 80 expected; validate actual engine | Published converted config contains six alignment heads; original frontend declares 80 mel rows |
| base | Systran/faster-whisper-base | 80 expected; validate actual engine | Published converted config contains eight alignment heads; original frontend declares 80 mel rows |
| small | Systran/faster-whisper-small | 80 | Exact cached revision `536b0662742c02347bc0e980a01041f333bce120`; ten heads; actual fixed-text diagnostic completed |
| large-v3-turbo | mobiuslabsgmbh/faster-whisper-large-v3-turbo | 128 | Exact retained revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`; six heads and 128-row frontend metadata re-read without loading weights |

The native align operation requires converted-model alignment heads. Missing
heads or an unsupported runtime must fall back visibly. Metadata availability
does not establish measured alignment quality or resource fit for each model.
CPU int8 can resolve to int8_float32; use the already loaded engine's effective
backend rather than creating a second model or forcing another compute type.

The inspected implementation is faster-whisper 1.2.1 / CTranslate2 4.9.1, while
current requirements permit a wider faster-whisper 1.x range. The initial
adapter should explicitly identify that inspected contract and reject a
mismatched or unreviewed timing interface into baseline fallback, preserving
ordinary recognition. Do not silently pin new weights, upgrade packages, or
assert that every future 1.x internal timing implementation is equivalent.

## 5. Return and warning contract

Use an internal `RecognitionResult` dataclass instead of attaching `_seek`,
`_tokens`, model handles or warning sentinels to segment dictionaries:

| Field | Meaning and lifetime |
|---|---|
| `segments` | Authoritative public baseline segments; no raw tokens or timing evidence |
| `language` | Existing recognized/detected language |
| `speaker_segments` | Optional separately copied timing candidate with existing `_words`; ephemeral until speaker assignment |
| `warnings` | Bounded human-readable warnings from optional timing |
| `asr_provenance` | Explicit small JSON-compatible allowlist: engine/model, actual recognition word-timestamp setting, timing method/status and counts |

The private `_recognize` callers and focused test fakes change together to this
one explicit return contract. Caption-only processing can keep its existing
segments/language path with no ASR result. `_enhance_and_save` receives the ASR
result explicitly, initializes warnings from it, and persists only the small
provenance. Neither the result nor its metadata retains samples, full features,
native paths, token arrays, tokenizer/model objects or exception objects.

`asr.word_timestamps` must describe the real recognition call and therefore be
`false` for new records. Add a separate `asr.speaker_timing` object with method
`fixed_text_postpass`, status `complete`, `partial` or `unavailable`, word-timed
segment count, original-timing fallback count and total segment count.
`complete` means the declared mechanical contract completed, not proven acoustic
accuracy. Existing saved records and their historical metadata are not rewritten.

One concrete long-recording constraint is important: `library` limits processing
metadata to 100 list items, 1024 visited nodes and 32 KiB. Copying one diagnostic
warning per segment could make saving an otherwise valid long transcript fail.
Aggregate this adapter's messages by reason and count, with a small fixed maximum,
while keeping details in development evidence rather than saved user records.
Suggested warnings are:

- “Word timing was unavailable in N segment(s); their complete text remains
  available for whole-segment speaker labeling.”
- “Original segment timing was retained for N conflicting segment(s); word-level
  speaker assignment was unavailable there.”
- “Word timing could not be prepared; the original transcript and segment timings
  were retained. Speaker labels may remain unassigned.”

Do not claim that the original boundaries were retained for every invalid-word
segment: a valid adjusted segment can lack usable private words. Counts for
segment-timing fallback and missing word evidence are separate. Existing durable
batch/editor warning rendering can display these messages without a new private
persistence schema or an enhancement-success claim.

## 6. Model and memory lifetime

Use the same `_whisper_model` object for recognition and alignment; do not add
another model cache or initialize an alignment model. Process one window at a
time and release each encoded result/native alignment structure before the next.
Do not keep the diagnostic's full raw paths in ordinary production results.

Full audio, the optional second frontend matrix, raw native segment copies and
engine-local references must leave scope before speaker inference completes and
before `_release_audio_models` runs for translation/summary. That existing
function remains responsible for Whisper/public-speaker/VAD cache clearing and
collection. Transcript-only jobs retain the existing cache reuse policy. The
legacy pyannote lifetime limitation remains separately documented.

For perspective, two hours of 16 kHz float32 mono PCM alone is 460,800,000 bytes.
The complete float32 log-mel matrix is about 230,400,320 bytes at 80 rows or
368,640,512 bytes at 128 rows. These are shape-based calculations, not measured
process peaks; frontend FFT temporaries and model allocations add considerably.
Avoiding simultaneous recognition/postpass feature matrices matters. Long-input
CPU/RAM fit still needs an actual integrated measurement.

Catch ordinary optional timing exceptions after baseline acceptance, clear local
timing references and return baseline plus a warning. Do not retain exception
objects that keep audio through traceback frames. A native process crash or OS
OOM kill cannot be made transcript-preserving merely by `try/except`; durable
pre-enhancement checkpoint/recovery or process isolation would be a separate
requirement if that stronger guarantee is needed. This proposal does not claim
it has solved process-death recovery or whole-machine memory safety.

## 7. Proposed implementation and meaningful checks after approval

Add a focused `asr_timing.py` module containing fixed-text native adaptation,
per-segment projection and the reviewed local conflict resolver. Pass the current
physical-boundary function into it instead of importing `app` circularly. Change
`_recognize` and its two callers to the explicit result contract, and thread the
bounded timing warnings/provenance into `_enhance_and_save`. Do not modify source
acquisition, default models, current silence gates, reference windows or frozen
experiment helpers. No frozen old result certifies these future source changes.

Prospective checks should demonstrate:

- Speakers off and on each make one baseline transcribe call with word timing
  disabled; a stub that changes words when that option is true catches coupling.
- Full array identity/single decode, duration, tiny nonzero speech and existing
  no-speech guards remain unchanged; rejected baseline never invokes the postpass.
- Dynamic 80/128-row, token, seek and incomplete-window behavior; no second model,
  language detection or transcribe call from the postpass.
- A late timing exception/malformed map restores the entire baseline with bounded
  visible warnings, without retaining an incomplete candidate.
- The existing conflict-chain and zero-duration-word controls remain applicable;
  source text/order and immutable baseline copies survive every fallback.
- More than 100 unusable-word segments produce bounded warnings/provenance that
  still save, export and survive restart; raw tokens, audio and `_words` do not
  enter SQLite/JSON/backups.
- Speaker backend failure saves the original baseline; successful speaker groups
  retain the existing text-preservation and uncertainty behavior.
- No result object keeps the model/features alive after audio cache release.

Only after source review and those checks should a separately authorized,
source-bound integrated real-speaker/resource run exercise the changed path.
That run must compare fixed text within its one baseline pass, include optional
failure/fallback evidence, and keep ASR/Greek/noisy/overlapping-speaker accuracy
gates open. No production edit or such run has occurred for this proposal.

## Sources and provenance

The accompanying `source-inspection.json` binds the exact current app/library
functions, installed native sources and retained model metadata inspected here.
Primary external references are:

- [faster-whisper 1.2.1 source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py), inspected from the exact installed file because the web renderer could not fetch that page.
- [Native Whisper align/encode and n_mels API](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html).
- [Tiny converted config](https://huggingface.co/Systran/faster-whisper-tiny/raw/main/config.json) and [Base converted config](https://huggingface.co/Systran/faster-whisper-base/raw/main/config.json).
- [Original Tiny frontend](https://huggingface.co/openai/whisper-tiny/raw/main/preprocessor_config.json) and [Base frontend](https://huggingface.co/openai/whisper-base/raw/main/preprocessor_config.json).
- [Pinned Turbo config](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/blob/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/config.json) and [frontend](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/blob/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/preprocessor_config.json), inspected from retained exact downloaded metadata after the current web lookup failed.

The Tiny/Base current public lookup is capability metadata, not a new immutable
execution pin. No third-party mirror was used to establish the configured Turbo
model's identity, and no model weights were downloaded or initialized.

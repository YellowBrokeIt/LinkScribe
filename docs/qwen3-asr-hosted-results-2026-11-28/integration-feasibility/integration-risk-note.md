# Conditional Qwen integration and Greek CTC alignment feasibility

**Status: source and metadata review only.** The first hosted Qwen workflow was
rejected before creating jobs; the corrected workflow at commit
`7ee0c7f2ac319d817ae9861a1d632a56ed62908e` is now running. No Qwen meaning result or
Greek alignment result is assumed here. No new model weights, model initialization,
alignment, production change, or revision of the frozen screen was performed for
this note.

## The integration boundary

A successful text screen would establish a reason to continue development. It
would not make this recognizer a substitute for the application's promised timed
exports and optional speaker handling. Native Qwen emits a language label and
utterance text. Its separate forced aligner supports 11 languages; Greek is absent
from both the [publisher's native aligner card](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B-hf)
and [native Transformers documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_asr).
The pinned Transformers 5.13.0 processor explicitly rejects Greek when it is passed
to `prepare_forced_aligner_inputs`. Omitting the language argument does not establish
Greek alignment support. The [publisher's streaming route](https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/qwen3_asr.py)
also does not return timestamps.

Current application contracts were inspected in the shared checkout corresponding
to the development checkpoint `a4ca88ec2820f8c0e1c29f4a7f5d36b8f0a32db3`:

| Existing behavior | Consequence for native untimed Qwen output |
| --- | --- |
| `app._recognize` returns `start`, `end`, `text`, and ISO language code | A raw string cannot satisfy this contract without a separately declared untimed representation or actual alignment. Qwen's full language names also need an explicit code mapping. |
| `_exports` always renders SRT/VTT and `_export_key` always exposes them | An untimed result needs capability-aware exports, download menus and ZIP contents. A full-file interval must not be silently treated as a subtitle cue. |
| The editor calls `segment.start.toFixed` and `segment.end.toFixed` | Untimed records need a separate presentation; null or absent times would currently break the editor. |
| Backup validation requires finite numeric segment times | SQLite's JSON column can hold an untimed representation, but restore validation and record capability/version handling must support it explicitly. Merely saving it would create an invalid round trip. |
| Source highlights bind ordered source timestamps; summaries create chapters from source starts | Their present timed forms are unavailable without genuine source times. A future untimed excerpt feature would be separate. |
| Speaker splitting accepts only complete ordered `_words` whose strings reconstruct the parent text | Diarization supplies acoustic speaker turns, not the missing mapping of Qwen's words to those turns. Without trustworthy word times, the existing fallback retains whole segments and can leave mixed voices unknown. |
| ASR provenance and model release currently name/cache faster-whisper | A new backend must report its actual engine/revision and release its own process/model before translation or other heavy inference. |

The smallest honest product capability would be explicitly untimed text with
TXT/JSON, editing, saved recovery and backup support. Timed subtitles, timed
highlights/chapters and speaker splitting would be unavailable for that result.
Text translation can preserve untimed blocks, but its independent semantic gate
still applies. This smaller capability does not fulfill the existing timed v1
requirements. Whole-file or chunk intervals may be retained as processing/search
regions; they are not recognized utterance or word boundaries.

## A concrete separate Greek alignment route

Current [WhisperX alignment source](https://github.com/m-bain/whisperX/blob/8d8e43bf3698dd1df4b011c0f1a8dd1d468ae365/whisperx/alignment.py)
maps `el` to the public Greek Wav2Vec2 model below. This is the maintainer's current
default integration with a third-party language model, not an official Qwen Greek
aligner. The inspected WhisperX source identifies itself as `3.8.7rc1`, so this
particular source pin is not represented as a stable release.

| Identity | Verified metadata |
| --- | --- |
| Model | `jonatasgrosman/wav2vec2-large-xlsr-53-greek` |
| Immutable revision | `489b34fb35fc5876af6193d419772cb9d6d1d531` |
| Access | Public, `private:false`, `gated:false` |
| Terms | Model card declares Apache-2.0; no separate LICENSE file is listed. WhisperX code is BSD-2-Clause. |
| Native class | `Wav2Vec2ForCTC` with `Wav2Vec2Processor`; 16 kHz input |
| Public weight file | `pytorch_model.bin`, 1,262,101,912 bytes, approximately 1.175 GiB of stored bytes |
| Published LFS SHA256 | `65f2b38c59498e261b55da3d81f1156c22531b798055174e62a4343bbc22951f` |
| Weight-format limitation | No safetensors file is listed at this revision. The binary file was not downloaded or loaded. |

The [immutable model card](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-greek/blob/489b34fb35fc5876af6193d419772cb9d6d1d531/README.md)
describes Greek training from Common Voice 6.1 and CSS10. The
[immutable model metadata](https://huggingface.co/api/models/jonatasgrosman/wav2vec2-large-xlsr-53-greek/revision/489b34fb35fc5876af6193d419772cb9d6d1d531?blobs=true)
supplies access and published weight identities. These are availability and format
facts, not measured timestamp accuracy, RAM or runtime.

WhisperX's `load_align_model(language_code="el", device="cpu", model_name=...)`
uses the native Wav2Vec2 classes on its Hugging Face path. A future pinned local
model directory can be passed with `model_cache_only=True`, rather than resolving
a mutable repository name during inference. The separate `align` API accepts
transcript text and source audio intervals; it does not require running Whisper
recognition first. For the existing short complete clips, the known interval
`[0, full_sample_count/16000]` would be an alignment search region for the exact
Qwen hypothesis. Only the aligner's measured, validated output could become final
timed words. A raw source interval is not itself the result.

## Greek spelling, names and numbers remain concrete risks

The model has a 41-entry vocabulary. Its dictionary contains Greek letters with
tonos and diaeresis, no digits, and only one Latin letter, `M`. The independent
metadata review and local text-only coverage analysis are retained beside this
note. They establish representation gaps without claiming an observed alignment
failure:

- In `Number One` and `Manta`, only `m` is represented after case conversion.
  Most of these correct product-name characters cannot receive a matching Greek
  CTC label. Written `3` is also absent.
- The current WhisperX code lowercases model labels and transcript characters.
  Uppercase model `Σ` becomes `σ`, whereas ordinary final `ς` stays `ς` and is
  absent. The already exposed camping and collision reference clips contain this
  case. Plain lowercase conversion therefore does not provide complete ordinary
  Greek coverage.
- Precomposed `ΐ`, decomposed accent sequences and related multi-codepoint forms
  need explicit treatment. NFC/casefold behavior cannot be assumed to preserve
  one input character per alignment label.
- Current source turns unsupported characters into a generic wildcard column
  using the maximum nonblank emission. That score is not evidence that the
  particular missing digit or foreign name was recognized at that position.
- Its default `interpolate_method="nearest"` fills missing word/segment times.
  The inspected utility supports `"ignore"`, but disabling interpolation alone
  does not remove generic wildcard alignment. A successful returned timestamp is
  not automatically trustworthy acoustic evidence.

A proposed adapter would need an explicit alignment-only normalization view with
an original-character/span map, leaving the saved Qwen text unchanged. Orthographic
equivalence such as final sigma must be distinguished from phonetic expansion,
translation or guessed name spelling. Number expansion is context-sensitive in
Greek; blindly replacing `3` with one spoken form is not sufficient. Custom
transliterations of the exposed product names would not establish general support.

Any unsupported, interpolated or fallback span must remain identifiable and retain
its original text. It must not be converted into validated `_words` merely to make
speaker splitting or subtitle export pass. Returning character alignments and
checking full text reconstruction, original order, monotonicity, positive duration,
audio containment and actual dictionary coverage would be necessary evidence.
These checks do not by themselves prove the acoustic timing is accurate. Forced
alignment also cannot establish that an incorrect or hallucinated ASR hypothesis
was truly spoken.

## Runtime and long-audio implications

The model's stored weight bytes are not its peak resident memory. Its 24-layer,
1024-hidden-size encoder has sequence-dependent activation/attention costs, and
WhisperX allocates a trellis over acoustic frames and transcript characters.
The published source performs inference on each supplied segment's audio; passing
an entire long film as one search region does not provide bounded memory or useful
coverage guarantees. Short-clip feasibility cannot approve two-hour input support.

The original Qwen wrapper's chunking is not automatically present in the native
Transformers interface used by this screen. A later long-audio path would need a
separately frozen complete-coverage/chunk-merge plan with explicit handling of
cross-boundary words, repeated/missing text and terminal-token limits. No such
chunking or timing implementation is proposed as complete here.

The current full WhisperX package declares Torch `~=2.8.0` and additional Pyannote,
Torchvision, Torchcodec and Linux Triton dependencies. That conflicts with treating
the Qwen screen's pinned CPU Torch 2.15 runtime as interchangeable, and with the
application's separately tested speaker extras on Torch 2.11. A blanket package
installation into the existing environment is not the minimal integration.
WhisperX's aligner can also fetch NLTK `punkt_tab` at runtime; a reproducible offline
screen would need that small data dependency prepared and pinned explicitly.

The model's preprocessor metadata declares waveform normalization. The inspected
WhisperX Hugging Face alignment branch passes the supplied waveform directly to
the model rather than calling that processor on the waveform. This source-level
preprocessing distinction needs to be declared and evaluated before an adapter
claims to follow a particular model input contract; this review did not measure
its effect or silently substitute another frontend.

For a future authorized measurement, sequential isolated processes offer the
clearest resource boundary: finish and unload Qwen, retain its immutable raw text
and full PCM identities, run only the Greek CTC alignment worker, then exit it
before diarization or text inference. Each stage needs its own measured CPU/RSS
limits. Keeping both models resident is unnecessary, and the existing
`_release_audio_models` does not yet know about either native Qwen or this aligner.

## Conditional next step

First inspect the actual hosted Qwen hypotheses against all original meaning
criteria. If those fail, alignment does not rescue the recognizer. If they pass,
this Greek CTC default is a concrete candidate for a separate small alignment
experiment, using the same full recordings and the untouched Qwen output rather
than a reference transcript. Its treatment of final sigma, accents, digits,
mixed-language names, unsupported spans and original text reconstruction must be
frozen before any run. No download, implementation, promotion or assertion of
complete Greek timing support follows from this metadata review.

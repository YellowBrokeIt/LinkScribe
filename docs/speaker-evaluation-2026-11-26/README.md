# Public CPU speaker prototype — 26 November 2026

The pinned public SpeechBrain ECAPA backend passed controlled real-voice checks
for one, two and three speakers, including a returning speaker using a different
utterance. Silence produced no speaker labels and a 0.55-second utterance was
left unassigned. These results support integration as an optional, approximate
speaker-labeling feature. They do not establish natural-meeting, Greek-speech,
overlap, or word-boundary accuracy.

## Model, runtime and public source audio

The model is [speechbrain/spkrec-ecapa-voxceleb](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb),
public and ungated under Apache-2.0, pinned to revision
`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`. Its embedding checkpoint SHA-256 is
`0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2`.
The backend uses the [Faster Whisper bundled Silero VAD](https://github.com/SYSTRAN/faster-whisper),
PyAV decoding to 16 kHz mono, overlapping acoustic windows, and deterministic
average-link cosine clustering without an expected speaker count.

The isolated Linux QA environment used SpeechBrain 1.1.2, official
`torch==2.11.0+cpu` and `torchaudio==2.11.0+cpu`, Faster Whisper 1.2.1, PyAV 16.1.0,
SciPy 1.18.1, and ONNX Runtime 1.32.0. CUDA was unavailable and no CUDA packages
were installed. The environment occupied about 1.3 GiB and the local model plus
its download cache about 170 MiB. These are observed QA footprints, not minimum
installation requirements for every platform.

All voices come from [LibriSpeech test-clean, OpenSLR 12](https://www.openslr.org/12),
licensed CC BY 4.0. Attribution: Vassil Panayotov, Guoguo Chen, Daniel Povey and
Sanjeev Khudanpur; source readings derive from LibriVox audiobooks. The three
source manifests alongside this document retain individual file hashes, source
identities, durations and acquisition provenance. All nine source hashes in each
cohort were checked to be distinct, including across speakers. No audio or voice
embeddings are stored in this documentation; temporary development embeddings
were removed after investigation.

The first six readers were extracted as complete members of an incomplete
official archive stream; no full-archive checksum is claimed. The final three
readers came from the [OpenSLR dataset's Hugging Face conversion](https://huggingface.co/datasets/openslr/librispeech_asr),
revision `71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`, at predetermined row offsets
500, 1000 and 1500. The source manifest records the exact rows and audio hashes.

## Evaluation discipline and retained failures

The initial distance threshold of 0.36 split one reader into three labels.
The failed [initial report](speaker-initial.json) is retained. A correction to
0.45 passed the first three readers but failed on three new readers; the
[failed validation report](speaker-holdout-v2.json) is also retained. Those six
readers consequently became development material, not an untouched holdout.

Actual development embeddings showed that the model's raw cosine scale varied
substantially across readers. The candidate used distance 0.65 for clustering,
minimum match similarity 0.50, and minimum competing-cluster margin 0.08. Those
are uncalibrated heuristics, not probabilities. A fringe window cannot pull its
cluster center toward itself enough to clear the ambiguity test, and a sampled
cluster rejected for insufficient support cannot be rescued by a weaker nearest
center match. Very similar tail windows do not count as extra support.

The [candidate freeze](candidate-freeze-v4.json) was written before inference on
fresh readers 2961, 8455 and 4507. No source identity, reference interval, expected
count, or scoring result was passed to `diarize_audio`. Source identities were
used only for fixture construction and subsequent scoring. There was no tuning
after the fresh validation outputs.

The final inference module SHA-256 was
`89e497f711c538413c3df79a77421c3ef5272bb63f784df2943ad1c5deccbe47`.
The actual smoke source hash was
`18676e0e99d6a725068593dfb65faed4e0daa2f1964f9a34230f601312052ae3`.
A later smoke-only change rejects duplicated source hashes and oversized fixture
files; existing manifests already satisfied both constraints, so inference was
not repeated for that validation-only change. The second development report
predates the addition of ONNX Runtime to the returned version list; its inference
settings and algorithm are identical to the final candidate.

## Fresh validation results

The clean gates required the discovered count to match, at least 80% of sampled
source-clip interiors to receive a label, and at least 95% consistency under one
global one-to-one mapping of anonymous labels to the known source readers.
Unknown speech lowers coverage. A global mapping checks whether a returning
reader keeps the same label; it does not relabel each utterance independently.

| Controlled recording | Audio length | Discovered speakers | Labeled interior | Label consistency among labeled samples |
| --- | ---: | ---: | ---: | ---: |
| One reader, three different utterances | 25.94 s | 1 | 93.78% | 100% |
| Two readers, each returning | 34.64 s | 2 | 85.66% | 100% |
| Three readers, each returning | 49.38 s | 3 | 90.38% | 100% |

The [full fresh report](speaker-fresh-holdout-v4.json) completed all seven requested
cases in 10.428 seconds with a measured Linux process peak RSS of 861.5 MiB.
Weights were already cached; the time includes model loading and inference but
excludes first download and package installation. Two CPU threads were used for
embedding inference. This is not a whole-app or whole-machine memory measurement:
concurrent Whisper, Ollama, browser, decoder copies, and longer audio add memory.

The [first development rerun](speaker-development-v4.json) and
[second development rerun](speaker-second-development-v4.json) also passed all
five supported checks in each cohort: three clean count/consistency checks,
silence, and short-only abstention. Their process peaks were 877.8 MiB and
869.7 MiB. The short-turn-in-context and overlap recordings were observations,
not quality passes. In the fresh mixed-voice recording, the backend reported one
speaker and left part of the speech unknown despite two actual overlapping
voices. This directly demonstrates why overlap remains unsupported.

## Limits and integration contract

### Actual app integration check

After integration, the fresh two-reader recording passed the actual upload API,
exercised with FastAPI TestClient: default Whisper Small with automatic language detection → public speaker
inference → SQLite → TXT/SRT/VTT/JSON/ZIP workflow. All four ASR segments supplied
validated actual word timestamps. Seventeen resulting text groups retained every
recognized word and exactly two supported speaker labels; uncertain words stayed
`Unknown speaker`. The same controlled interior indicator found 85.66% assigned
coverage and 100% consistency among assigned labels, including both returning
readers. These remain fixture indicators, not an independent timing benchmark.

The [app report](speaker-app-initial.json),
[timeline assessment](speaker-app-label-assessment.json),
[actual JSON](actual-app-transcript.json), and [actual SRT](actual-app-transcript.srt)
retain the evidence. The complete run took 14.407 seconds, with measured Linux
process peak RSS of 1,279.6 MiB for the app, ASR and speaker backend together.
It excludes Ollama and any external process. Translation and summary were disabled
for this run, so it is not the combined all-features memory gate.

The saved transcript remained downloadable after all in-memory jobs were
discarded. Model/settings/warnings were present in the actual JSON and SQLite
record, and a library backup was generated. Separate regressions cover additive
database migration, metadata backup round trips, old v1 backup compatibility,
invalid metadata rejection, and atomic saved-batch title updates on edits.

These are edited English audiobook recordings, with inserted 0.6-second gaps.
Scoring omits 0.75 seconds at each source-clip edge, includes some natural pauses,
and is **not diarization error rate (DER)**. The test does not verify speaker
changes inside continuous speech, exact boundaries, noisy rooms, Greek voices,
very similar voices, or natural multi-party meetings. The upstream
[SpeechBrain AMI recipe](https://github.com/speechbrain/speechbrain/tree/develop/recipes/AMI/Diarization)
has different assumptions; its reported benchmark numbers are not attributed to
this implementation.

`diarize_audio(path, *, config=None, cache_dir=None)` returns anonymous time turns,
explicit unknown results, warnings, and model/settings provenance. Acoustic
window boundaries must not be presented as word timings. The existing Whisper
segment-only workflow needs conservative assignment: a segment containing
material evidence of multiple voices must remain unassigned until actual word
timestamps allow meaningful splitting. Never divide its text proportionally.

Audio duration, window counts, embedding batches and clustering matrices are
bounded. Clustering uses at most 400 reference windows and warns when a temporal
sample is needed. Rare speakers can be missed in long recordings. Two hours of
16 kHz float32 audio alone is about 461 MB; two-hour end-to-end memory was not
measured. Short-window support is correlated acoustic evidence, not independent
confirmation of identity.

## Telemetry correction

An intermediate run was stopped by automatic approval review because the newer
ONNX Runtime dependency attempted unrelated Microsoft telemetry. The interrupted
checkpoint was retained in QA. The backend now sets `ORT_DISABLE_TELEMETRY=1`
before optional runtime imports and calls `disable_telemetry_events()` before
creating the VAD session. App startup must apply the early setting before any
independent Faster Whisper import as well.

Indexed [first-party release notes](https://github.com/microsoft/onnxruntime/releases)
and [privacy documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md)
describe the early opt-out; live retrieval of the privacy file returned 404 during
the investigation. The installed native 1.32.0 binary was independently inspected:
it actually reads this variable using `getenv`, recognizes `1` as true, and takes
the initialization opt-out branch. The [binary evidence](onnx-telemetry-optout-evidence.json)
records its hash and limits. Subsequent complete runs had no repeated rejection.
Syscall tracing was unavailable because the container denies `ptrace`, so this
record does not claim a measured absence of all network traffic.

## Repeating the smoke

Use the optional CPU requirements in a separate environment, acquire the licensed
sources listed in a source manifest, and update its local paths without changing
the source hashes. The actual model call is never stubbed by this command:

```bash
ORT_DISABLE_TELEMETRY=1 python tests/smoke_real_speakers.py \
  --sources /path/to/source-manifest.json \
  --work-dir /path/to/qa/fixtures \
  --cache-dir /path/to/qa/model \
  --output /path/to/qa/speaker-report.json
```

The script fetches no dataset and starts no service. The selected public model
may download on first use. Reports checkpoint before and after cases and retain
errors; an interrupted selection stays incomplete. `--case` selects an exact
fixture ID. Linux RSS units are used by this QA script; portable memory reporting
for macOS/Windows is not claimed.

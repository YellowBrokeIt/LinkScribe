# Complete local workflow — 26 November 2026

The measured Small transcription → public speaker labels → Qwen translation →
Qwen summary → SQLite/export workflow completed within the selected process
memory budget. **It did not pass generated-text quality:** every Greek-target
translation segment was copied in English, and the summary contains a material
fidelity concern. These outcomes are retained together; a resource or structural
pass does not approve the translation, summary, or v1.0 release.

## Actual configuration and source

The run used the actual upload route through FastAPI TestClient and the normal
app worker. Observers delegated model/transport calls without substituting
audio, source text, responses, speaker labels or outputs. The licensed fixture
was `two_speakers_returning.wav`, lasting 34.635 seconds, with SHA-256
`dc977c1cb0af1a30946eeb0c59218039987412462d2e8c5a2d23990b559f087f`.

| Component | Actual selection |
| --- | --- |
| Recognition | Faster Whisper 1.2.1, Small, CPU, automatic language detection, actual word timestamps; production VAD prefilter disabled |
| Speaker labels | Public SpeechBrain ECAPA CPU backend plus its own Silero VAD; existing frozen settings |
| Translation | Ollama `qwen3:4b`, generic JSON adapter, English source → Greek target |
| Summary | The same Qwen model, English source, direct short-source path |
| Ollama | 0.40.12; four inference threads; temperature 0; 8192 context; 2048 output-token limit |
| Model lifetime | Audio caches released before text inference; one unload after the whole translation phase and one after summary; retention opt-out unset |
| QA daemon | One parallel request and one loaded-model limit, configured only for the isolated QA daemon |

The Qwen digest was
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
SpeechBrain model revision was
`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`; its weight hashes and settings are in
the raw report. The supplied Small cache manifest was checked against its actual
files; its repository revision is
`536b0662742c02347bc0e980a01041f333bce120`. That manifest is labeled as supplied
and files verified, not as independent instrumentation of the recognizer's
resolved cache revision.

The code was a frozen working tree when measured. After publication, all nine
source-file fingerprints in the report were checked against
[`a3b8652f9bbef4f065c9b90dd6ac6c3df3434100`](https://github.com/YellowBrokeIt/LinkScribe/commit/a3b8652f9bbef4f065c9b90dd6ac6c3df3434100)
and matched. The application and enhancement hashes were respectively
`dca39c5465709d6cead0fead343dc0b5f2d3eeb170cf5a43264dfc7ec1ed809d` and
`a61f73c8c3dba80405fff25163a1a4c74d02824fcc66c09fa41db8ed891be575`.

[invocation.json](invocation.json) preserves the exact command, explicit
environment, runtime-wrapper hash and host memory. There was no prior Ollama
process, no concurrent unrelated model run, and no new model download. Early
ONNX/Hugging Face telemetry opt-outs and offline Hugging Face mode were set.
No daemon or model runner remained after the wrapper exited.

## Execution, resources and persistence

| Observation | Result |
| --- | --- |
| Complete combined runtime | 59.202 seconds |
| Peak concurrent process RSS | 4584.3 MiB |
| Peak concurrent process PSS | 4576.3 MiB |
| Selected RSS budget | 6144 MiB; passed |
| Memory samples | 266; complete PSS at every sample; no accounting errors |
| Actual language inference | Two translation calls, one summary call |
| Model cleanup controls | Two successful responses with `done_reason: unload` |
| Recognized source | Seven ASR segments; normalized words retained through 21 speaker-labeled groups |
| Speaker labels | Two supported anonymous labels; nine groups remained unknown with visible warnings |
| Saving and exports | SQLite, TXT/SRT/VTT/JSON/ZIP and library backup created; durable JSON matched after in-memory jobs were removed |

The translation calls took 16.972 and 6.513 seconds; the summary call took
19.559 seconds. Both controls are separately identified in the report and are
excluded from inference counts. Their success does not measure how quickly
every native allocation returned to the operating system.

The sampler verified that its supplied PID was the `ollama serve` process
listening on the configured API endpoint. It included that daemon, its model
runner, the app and their descendants, deduplicating PIDs and summing each
sample before taking a peak. The sampler stopped cleanly. RSS can double-count
shared pages; Linux PSS apportions them. Sequential process scans and the
0.2-second interval can miss short transients.

This host had 9967.3 MiB RAM. The 6144 MiB threshold was an engineering process
budget for a smaller target, **not an actual whole-machine test on 7.3 GiB**.
The measurements exclude OS/browser/unrelated process headroom and filesystem
cache outside measured process residency. They do not establish two-hour audio
capacity, natural meeting behavior, or a larger translation model's footprint.
The run exercised the default Qwen path; warm native Marian and legacy pyannote
models were not part of it.

The existing controlled speaker indicator, applied after inference to the
actual word-timed groups, found 85.27% assigned coverage and 100% consistency
among assigned interior samples under one global label mapping. See
[speaker-label-assessment.json](speaker-label-assessment.json). This reused
fixture result is not fresh validation, DER, word-timing accuracy, or general
ASR accuracy. Unknown speech reduces coverage.

## Generated-text failures

The two actual translation prompts explicitly requested Greek. Their raw model
responses instead echoed all 21 English input strings, with no Greek letters.
The schema, count and nonempty-string checks passed, so this source snapshot
saved the output under `el` without a translation warning. The unchanged output
also appears in the real translated exports. Neither the observer nor export
code substituted it. This is a failed translation, even though execution and
the memory gate completed.

The English summary retained the conditional wording in its main paragraph,
but changed “Jack would become Eva's happy husband” into a definite “Jack
becomes…” key point. It also identifies Mr. Neverbend as the captain. The ASR
source lacks clear quotation punctuation and does not safely establish that
relationship; this is an unsupported-interpretation concern, not an independently
listened audio-ground-truth conclusion. The summary received the original
English source, not the failed Greek-target output.

The [separate assistant review](assistant-review.json) records these findings
and exact examples. The automatic reports retain `semantic_quality: unreviewed`.
There is no blinded human review, formal ASR word-error measure or broad model
accuracy claim. This short recording also cannot resolve the separate observed
timeout on long translation inputs.

### Captured-response regression after the actual run

After the failure above, a narrow guard was added for whole-result identity
across a known English/Greek language change. The same 21 source segments,
two captured translation responses and captured unload response were then
replayed through the real adapter and the app's save/export path. **This replay
ran no model, ASR, speaker inference or local service.** It is separate from
the actual-model resource measurement above.

The [replay report](captured-response-replay/report.json) verifies that all
requests matched the actual capture exactly. The adapter rejected the copied
result, and the app saved the original with a neutral “No separate Greek
translation was generated” warning. Original TXT/SRT/VTT bytes remained
identical to those from the actual run. SQLite and library retrieval preserved
the source and warning; translated download routes returned 404, and the
[actual replay ZIP](captured-response-replay/transcript.zip) contains no
translated artifacts. One final unload control was exercised in each replay
phase, with its recorded response returned by the replay transport. This is
not a second real unload measurement. The original actual-run reports were
not modified.

The guard compares the whole assembled result after whitespace normalization,
not individual fragments. Numbers and punctuation without alphabetic text may
legitimately remain identical. Names-only identity receives the same neutral
no-separate-result warning without asserting that the names are wrong. Changed
but inaccurate text remains outside this check. This prevents the observed
silent copy from being offered as a translated artifact; it does not improve
the model's translation, certify language or meaning, or repair the summary.
The report records the guard's different source fingerprint and the
[exact QA script](captured-response-replay/replay-script.py).

## Retained evidence and attribution

- [Complete report](combined-qwen-vad-off.json): actual source/output text,
  model requests/responses, options, runtime identities, source hashes and
  concurrent RSS/PSS peak samples.
- [Nested app report](app-workflow.json): actual recognizer words/timestamps,
  speaker report, job warnings, SQLite record and export hashes.
- [Actual JSON](transcript.json), [SRT](transcript.srt),
  [VTT](transcript.vtt), [TXT](transcript.txt) and [ZIP](transcript.zip).
- [Actual Greek-target JSON](translation_el.json),
  [summary JSON](summary.json) and [summary Markdown](summary.md), copied as
  unchanged member bytes from that ZIP.
- [Library backup](library-backup.zip), [runtime log](run.log), and
  [copy manifest](manifest.json) with hashes of unaltered report/export files.

The audio consists of real LibriSpeech test-clean readings with inserted gaps;
the [fixture provenance](fixture-provenance.json) records construction and
reference intervals. LibriSpeech is licensed CC BY 4.0, attributed to Vassil
Panayotov, Guoguo Chen, Daniel Povey and Sanjeev Khudanpur; readings derive from
LibriVox audiobooks. Source acquisition and individual hashes are retained in
the [speaker evaluation](../speaker-evaluation-2026-11-26/README.md).
Expected identities and counts were used only for post-inference scoring.
No audio, voice embeddings, model weights or credentials are included here.

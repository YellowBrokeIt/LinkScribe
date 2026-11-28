# Full-recording ASR: recovered dialogue and a digital-silence failure

The hosted run at **a3b8652** recovered later film dialogue after the VAD
prefilter was disabled, but **saved invented words from an entirely silent
input**. The overall provider gate failed. This is preserved failure evidence,
not approval of transcription quality or a completed v1.0 gate.

- [Exact source commit](https://github.com/YellowBrokeIt/LinkScribe/commit/a3b8652f9bbef4f065c9b90dd6ac6c3df3434100)
- [Hosted run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45886466964)
- [Actual job and log](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45886466964/job/140138289537)
- [Unchanged complete artifact](original-hosted-artifact.zip)
- [Raw report](raw/provider-report.json), [events](raw/events.jsonl), and [assistant review](assistant-review.json)

The original artifact is 102,986 bytes, GitHub artifact ID `15149328436`,
SHA-256 `6127f905751d7bb3b5d74c49417a97b41b370719161628a980a35a018a9834d4`.
It includes the actual isolated SQLite database, executed harness, logs and
exports; these contain only the licensed/owned QA inputs. Selected JSON and
export files are also expanded here for inspection. They are byte-for-byte
copies, not rewritten summaries. All seven recorded source hashes matched the
published Git object and remained unchanged throughout the run.

## The film reached recognition in full

The actual Dailymotion downloader retrieved the same film bytes as the earlier
Tiny, Small and VAD-diagnostic runs: 11,919,385 bytes, SHA-256
`c8359f5278729091cab5b04d44b19eb4670553769ad2ca0e0097af2e91aef1b0`.
The decoder produced 11,746,325 mono samples at 16 kHz, or **734.1453125 seconds**.
The actual transcribe call requested Small, automatic language, beam size five,
`vad_filter=False` and `condition_on_previous_text=False`, with no prompt or
reference text. The model returned the same full duration before and after
the disabled VAD stage; no VAD or audio-selection events occurred.

| Normal saved result | Segments | Last segment end | Longest segment |
| --- | ---: | ---: | ---: |
| Single link | 97 | 713.96 s | 11.00 s |
| Successful mixed-batch item | 77 | 727.20 s | 29.12 s |

The normal saved outputs now include the world-change/Celia line near 519
seconds and the closing lesson/worse-outcome exchange near 566 seconds.
Those recognizable later lines were absent when the old prefilter discarded
every sample after 423.184 seconds. Unlike the earlier cropped diagnostic,
this evidence comes from the ordinary full-recording application path and its
normal SQLite records and exports.

The correction does **not** establish complete or accurate transcription.
Outputs still contain repeated fragments, ellipsis-only segments and unusual
wording. A late short utterance differs between the two runs: the single-link
result ends with “Let's go,” while the batch result ends with “I'll see you in
a minute.” These credit-tail outputs require direct comparison with the
source audio before a definite hallucination classification. Later timestamps
alone are not evidence of genuine later speech. Counts and wording also vary
between runs, so this is not a claim of bit-reproducible decoding.

The qualitative comparison uses the same published subtitle reference and
scope limitations described in the
[earlier content review](../browser-provider-2026-11-26/assistant-content-review.json).
No formal word-error rate, independent human transcript or subtitle alignment
score is claimed. Raw segment probability scores were not collected in this
baseline; a subsequent observer will retain them without using them to alter
or filter the generated words.

## Exact digital silence produced a false success

The harness generated a 32-second mono 16 kHz signed-16-bit WAV whose **512,000
PCM samples are all zero**. Its WAV SHA-256 was
`61480b2ca09e9d5b7b359b23869ac199fe1bbb5ae6ca1501a6151f73304f3142`.
The recognition-start hash matched that exact owned input, and actual decoder
and model-info observations both reported 32 seconds with VAD disabled.

The app returned `done`, with no warning, and saved these two segments:

| Start | End | Saved text |
| ---: | ---: | --- |
| 0.00 s | 2.06 s | you |
| 30.00 s | 32.00 s | You |

The [unchanged saved record](raw/records/nonspeech-f0ce42c84da34b39905b08136dfb8da5.json)
and original database are retained. Unlike the uncertain film-tail examples,
the zero-sample construction proves there is no acoustic speech source for
these words. The gate correctly failed this result instead of accepting a
nonempty transcript. The observed case elapsed time was 6.076 seconds.

The second owned input was deterministic white noise, also 32 seconds, generated
with the exact recipe and hashes in the report. Its actual Small inference
returned `No spoken words were detected in this recording.` No library record
or transcript exports remained, and the input was cleaned. That case passed
in 92.211 seconds. This is one noise fixture, not a general music/noise
guarantee or a controlled speed benchmark.

## Provider access and preservation remain distinct

Both hosted YouTube fixtures still stopped at a bot sign-in requirement. The
selected Vimeo clip still stopped at the extractor's login fallback. No
credentials, cookie import, proxy rotation, CAPTCHA bypass or disabled TLS
verification was used, and none of these attempts is counted as a provider
pass. The Dailymotion repost remains the actual acquisition success.

The mixed batch completed both items with one successful Dailymotion record
and one visible failed YouTube item. Its [original ZIP](raw/downloads/mixed-batch.zip)
and manifest preserved that distinction. Successful transcript text/times
matched SQLite and TXT/SRT/VTT/JSON exports, original media was cleaned, and
a newly started app process retrieved both successful records and the
completed batch history with identical export bytes. These checks establish
preservation of the actual output, including its errors.

Film attribution: **(CC) Blender Foundation | mango.blender.org**,
[CC BY 3.0 licensing](https://mango.blender.org/about/),
[tested repost](https://www.dailymotion.com/video/xbvubxi).
The silence and noise fixtures are owned generated QA data.

## Following correction, not yet validated by this run

The bounded follow-up decodes once and rejects only empty/exact-zero PCM
before model inference, preserving every nonzero sample without an energy
threshold. It also checks the decoded two-hour sample limit rather than
trusting only container metadata. The same decoded array is then passed to
Whisper, retaining VAD-off behavior. This is a digital-silence and duration
repair; it is not a general hallucination filter.

The follow-up harness distinguishes zero rejection before inference from
actual nonzero-noise inference. It will retain ordinary raw model segment
scores separately and match their text/times to the saved result. Fresh hosted
evidence is required before claiming that follow-up works. This directory
remains the immutable **a3b8652 failed baseline**; the earlier
[VAD diagnostic archive](../browser-provider-2026-11-26/README.md) is unchanged.

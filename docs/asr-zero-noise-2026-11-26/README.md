# Exact-zero rejection passes; nonzero-noise recognition still fails

The actual hosted run at **2760679** verifies the narrow digital-silence
correction: 32 seconds of zero PCM was decoded once and rejected before model
inference, with no transcript record or exports. The same run also exposed a
separate failure: **Small generated and saved garbled text from deterministic
white noise**. The complete provider gate remains failed.

- [Exact source commit](https://github.com/YellowBrokeIt/LinkScribe/commit/2760679cdcd5bf2fdd0f18589e821a89d2bd9b90)
- [Hosted run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45890244230)
- [Actual job and log](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/45890244230/job/140150849770)
- [Complete original artifact](original-hosted-artifact.zip)
- [Raw report](raw/provider-report.json), [events](raw/events.jsonl), and [assistant review](assistant-review.json)

The original artifact is **141,268 bytes**, GitHub ID `15151960577`, SHA-256
`56080e96261cf8903bc4ff78b81426b12d82cf070e6a13ed092ac88c66ff8de2`.
Expanded raw files here are unchanged copies. The complete archive retains the
actual SQLite database, executed harness, logs and exports; only licensed or
owned QA data is present. All seven captured source hashes matched the
published Git object and remained unchanged during processing and restart.

## The zero-input correction was exercised through the actual app

The owned silence WAV is identical to the prior failed fixture: 512,000 zero
signed-16-bit PCM samples, mono 16 kHz, 32 seconds. Its WAV SHA-256 is
`61480b2ca09e9d5b7b359b23869ac199fe1bbb5ae6ca1501a6151f73304f3142`.

| Observed zero-input behavior | Result |
| --- | --- |
| Actual decoded array | 512,000 float32 samples, all zero, exactly 32 seconds |
| Recorded events | Recognition start, one audio decode, recognition failure |
| Model inference, VAD or segment construction | No such event occurred |
| App error | `No spoken words were detected in this recording.` |
| Library/SQLite record | Absent |
| Transcript exports | Absent under the harness's explicit file check |
| Uploaded input | Cleaned |
| Observed case elapsed time | 0.533 seconds |

The downloaded original SQLite database independently contains zero rows for
this job. This evidence validates rejection of exact digital silence before
inference. It does not mean a speech model correctly classified the silence;
no model request was needed. The separate decoded-duration boundary tests do
not constitute a live two-hour recording or peak-decoding-memory test.

## The nonzero-noise case is an actual false success

The second owned WAV contains deterministic white noise, generated with
`random.Random(20261126)` and one `randint(-3276,3276)` per PCM sample. It also
has 512,000 mono samples at 16 kHz. Its bytes match the preceding run's input,
SHA-256 `687acd5e96a280011d4c36699cda0caf02287bf06fc901b5c229ca39bca5b44b`.
The float32 decode contained 511,922 nonzero samples.

The harness observed one full decode and proved that the **identical complete
array**, including its PCM checksum, reached the actual Small transcribe call.
VAD was disabled. No source samples were selected, clipped, normalized by the
harness, or replaced. There was no reference prompt or post-generation repair.

After 74.596 seconds, the app returned `done` with no warning and saved one
0–11 second segment of phonetic-looking corrupted text ending with
“on the right, as on the opposite side.” The
[original record](raw/records/nonspeech-85e935f110c84157811c06ea4ad10404.json)
and original SQLite database retain it; the database contains one row for
this job. The strict no-speech gate failed, as it should. No successful
no-record/export claim applies to this noise case.

The prior noise fixture's pass is preserved in the
[earlier VAD-off archive](../asr-vad-off-2026-11-26/README.md). A single successful
noise run did not establish reliable rejection. Cross-run model-file identity
was not captured by this provider harness, so these are observed configured
paths, not a controlled model-only comparison.

## Raw scores explain the decoder rule, not correctness

The QA observer retained the actual Segment construction without replacing the
model's return tuple, generator, class or objects. It did not use any score to
filter or alter the result. The noise segment had:

| Raw model field | Observed value |
| --- | ---: |
| `no_speech_prob` | 0.9914168715 |
| `avg_logprob` | -0.9114699046 |
| `compression_ratio` | 2.1338582677 |
| Selected fallback `temperature` | 0.8 |

The installed [Faster Whisper 1.2.1 source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
uses a high-enough average log probability to override its no-speech skip.
Here the recorded average exceeded the configured `-1.0` threshold despite
the no-speech value exceeding `0.6`, so that override applied. This explains
the existing acceptance rule. It does **not** establish a safe replacement
threshold or a calibrated measure of word accuracy.

Actual word probabilities are `null` in this ordinary path because word
timestamps were off. The report preserves that absence instead of inventing
word-level certainty. No confidence-based green light is claimed.

## Full film, mixed batch and restart still completed

Both Dailymotion passes used the same 11,919,385-byte licensed film input as
the earlier runs and decoded all **734.1453125 seconds**. Each transcribe call
received the identical full decoded array. The single-link output had 72
segments; the successful batch item had 64. Every observed raw segment's
text/times matched the normal saved result after the app's existing whitespace
and millisecond formatting. SQLite and every downloaded export agreed.

The later world-change/Celia and closing lesson dialogue remains present near
519 and 565–568 seconds. Quality is still unapproved. Suspect credit-tail
utterances differed between passes and used temperature 1.0; the raw text,
times and scores are retained for source-audio review. Later timestamps and
successful exports are not proof of real later speech or synchronized subtitles.

The mixed batch finished two items with one visible failure, retaining the
successful Dailymotion result and its [original batch ZIP](raw/downloads/mixed-batch.zip).
A newly started app process retrieved both successful film records and the
completed batch history with unchanged export bytes. Downloaded media was
cleaned. Both YouTube fixtures still hit a bot sign-in requirement and the
selected Vimeo source still hit an extractor login fallback; none is counted
as an acquisition pass. No credentials or access-bypass measures were used.

Film attribution: **(CC) Blender Foundation | mango.blender.org**,
[CC BY 3.0 licensing](https://mango.blender.org/about/),
[tested repost](https://www.dailymotion.com/video/xbvubxi).
The two non-speech fixtures are owned generated data.

## Runtime and interpretation limits

Both server processes recorded yt-dlp 2026.11.23, curl-cffi 0.17.0, Faster
Whisper 1.2.1, CTranslate2 4.9.1, PyAV 16.1.0 and certifi 2026.11.20 on CPU.
The Small model name and actual options are recorded; its downloaded weights'
digest/revision are not captured here. The film and noise cases within this
run used the same cached engine. These elapsed times are observations, not
controlled performance benchmarks.

This directory is an immutable report of **2760679**. The zero-input bug is
verified fixed for the tested construction; nonzero-noise false success,
general transcription fidelity, subtitle accuracy and external provider access
remain unresolved. No subsequent candidate is validated by this archive.

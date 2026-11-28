# Frozen ASR follow-up: full-film hallucinations and quiet speech

This is a development-candidate record, frozen before hosted validation of the
aligned ASR policy. It does **not** approve v1, a stable release, overall speech
accuracy, subtitle alignment, or all-provider operation. The application remains
version 0.3.0. Later hosted results must be recorded separately against their
actual commit and must not be attributed to these isolated runs.

## Decision and exact candidate

The original Small recognizer saved suspicious dialogue during gaps in the full
Vimeo *Sintel* recording. Disabling temperature fallback made the output much
worse. Replacing Small with Large v3 Turbo alone also left substantial background
hallucinations. Both alternatives are rejected.

The one candidate retained for hosted development validation is the exact
[two-line recognizer patch](aligned-hallucination.patch):

```python
word_timestamps=True,
hallucination_silence_threshold=2.0,
```

It replaces the conditional word-timestamp keyword in `engine.transcribe()`.
The existing full decoded audio, `vad_filter=False`, automatic language
selection, beam size 5, `no_speech_threshold=0.6`,
`condition_on_previous_text=False`, and the upstream temperature fallback
schedule are retained. No text from a subtitle, reference, or expected answer is
passed to the decoder. The separate `word_timestamps` argument to `_recognize`
still controls whether private `_words` are returned to speaker alignment.

The upstream hallucination option depends on word alignment and can skip
candidate anomalies. Passing the complete PCM to the model therefore does not
by itself establish preservation of all real speech. The late-dialogue gate
below remains necessary.

Processing metadata must describe the actual inference settings: word timestamps
are now computed for ordinary transcripts too, and the 2.0-second hallucination
setting should be recorded. Speaker requests remain a separate enhancement
choice. The parent integration owns the application, metadata and unit-test
changes; this folder records the measured isolated candidate.

## Exact input and implementation identity

The experimental source was an isolated archive of
[002d8fc66e5f3666b40477878e064c825ef1c495](https://github.com/YellowBrokeIt/LinkScribe/commit/002d8fc66e5f3666b40477878e064c825ef1c495)
with the separately recorded Vimeo player normalization fix. The recognizer AST
was checked against the later published
[f12afd80e99d9673e416d7f243976697a66675a9](https://github.com/YellowBrokeIt/LinkScribe/commit/f12afd80e99d9673e416d7f243976697a66675a9)
before these ASR changes were integrated. Each experimental report preserves
before/after source hashes, actual model resolution, installed package/source
identity, audio identity, complete raw segment constructions, and actual options.
Neither prior source identity nor local execution establishes later-commit CI.

The licensed full Vimeo recording is
`https://player.vimeo.com/video/19934655`:

| Identity | Recorded value |
|---|---|
| Acquired audio size | 17,669,814 bytes |
| Acquired SHA-256 | `de4bf866b48858c8fe7b9448ecc3d4713dfd74f44c7ca87736bda6c558fc2364` |
| Decoded duration | 888.070375 seconds |
| Complete mono sample count | 14,209,126 at 16 kHz |
| Decoded float32 PCM SHA-256 | `b4c6fe1672bd7448e91e8f48ce14b1161ae95883710f3cb0326e070d4e0b1615` |
| Small revision | `536b0662742c02347bc0e980a01041f333bce120` |
| Small model.bin SHA-256 | `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| Runtime | Faster Whisper 1.2.1, CPU int8 |

The original complete link → actual audio → ASR → SQLite → export → restart
pipeline succeeded locally at 2026-11-27 23:48–23:50 UTC. Its unreviewed content is
preserved in [original-small-evidence.json](original-small-evidence.json), with
the complete original report's SHA-256. The follow-up direct recognizer probes
do not claim to repeat that complete link workflow.

## What the full-film comparison found

The [published English subtitles](https://media.xiph.org/sintel/subtitles/sintel_en.srt)
and [Xiph license notice](https://media.xiph.org/sintel/subtitles/README.txt) are
retained with their hashes. They contain 26 main-dialogue cues and are distributed
under Blender's CC BY 3.0 license. They are an independent reference for selected
dialogue, not exhaustive annotations for interjections, sung words or exact
ASR word boundaries. The composer also publishes the
[end-credit song score](https://www.janmorgenstern.com/sintel/I_Move_On-Sintels_Song.pdf).
The existence of genuine singing matters when interpreting high no-speech scores.

| Arm | Segments | Observed recognition time | Finding |
|---|---:|---:|---|
| Original Small | 81 | Original pipeline, not a matched timing experiment | A 15-line unsupported dialogue burst at 177.84–207.50 s; repeated ellipses at 669.5–691.5 s; incorrect words and coarse boundaries remain. |
| Small, temperature fixed at zero | 129 | 60.922 s | Repetition replaced actual dialogue around 207–233 s; 103 occurrences of the repeated hush token and maximum compression ratio 52.35. Rejected. |
| Small, word alignment plus 2.0 s hallucination setting | 46 | 173.030 s | Removed the unsupported burst, ellipses and repeated pre-song lines; recovered the failure line near 445 s and preserved later dialogue and credit vocals. Candidate only. |
| Large v3 Turbo, original recognizer settings | 80 | 220.343 s | Some words improved, but unrelated generic lines appeared across instrumental gaps. Model-only switch rejected. |

The three follow-up full-film probes used QA seed 20261128. The original provider
run did not use that controlled seed. Timing and segment counts are observations,
not a controlled speed benchmark or accuracy score. The aligned Small candidate
still misrecognizes a character call around 338 s and some sung words, and retains
short utterances that were not exhaustively checked acoustically. No blanket
semantic approval follows from removal of the most conspicuous failures.

[anchor-comparison.json](anchor-comparison.json) retains selected reference cue
groups and nearby actual output. The full reports retain every observed segment,
confidence-related field and temperature, including rejected results. Language
probability is not word accuracy or a calibrated guarantee.

The separate [Silero diagnostic](vad-diagnostic.json) observed no speech interval
in the suspect burst or ellipsis interval. It also observed no speech interval
through genuine credit singing. Accordingly, it was **not** used as a segment
deletion rule. The existing policy against VAD prefiltering remains in place;
earlier hosted evidence already showed that prefiltering removed real late
Dailymotion dialogue.

The implementation reference is the installed, hashed
[Faster Whisper 1.2.1 recognizer](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py).
The candidate changes both word alignment and its dependent hallucination
option; this experiment does not attribute the effect to either change alone.

## Paired quiet-speech and word-evidence regressions

The four [exact-hash FLEURS cases](quiet-fixtures.json) were already used by the
November 26 speech-guard regression: ordinary and −20 dB versions of one English
and one Greek recording. These are regression cases, not new holdout data. The
complete float32 audio was scaled by 0.1 for the quiet variants, without trimming
or normalization; recovered files exactly matched the earlier frozen hashes.

Each of baseline Small, aligned Small and baseline Turbo completed all four
actual upload → ASR → SQLite → export cases. Each run also passed the separate
process SQLite comparison. The seed was 1729 immediately before each recognition
worker. The [paired comparison](quiet-paired-comparison.json) shows that aligned
Small preserved all four baseline Small hypotheses **exactly**. Segment timing
changed and is not represented as identical or independently accurate.

| Case | Baseline Small word errors | Aligned Small word errors | Baseline Turbo word errors |
|---|---:|---:|---:|
| Greek ordinary, 11 reference words | 3 | 3 | 1 |
| Greek −20 dB, 11 reference words | 4 | 4 | 1 |
| English ordinary, 15 reference words | 0 | 0 | 0 |
| English −20 dB, 15 reference words | 2 | 2 | 0 |

These are the original harness's token-level edit counts. The English quiet
Small result uses a contraction, accounting for the two-token edit count; the
Greek results retain spelling errors. This tiny regression set does not support
a general-language accuracy claim.

The four-case runs took 16.305 s / 690,212,864-byte peak RSS for baseline Small,
16.032 s / 690,040,832 bytes for aligned Small, and 58.404 s / 1,779,310,592 bytes
for Turbo. The full-film Turbo process peaked at 2,464,096 KiB (about 2.35 GiB),
with 221.722 s measured subprocess wall time including startup. These are
single-machine process observations with warm model files, not a matched latency
or hardware budget approval. Full-film aligned Small peak RSS was not measured
in the first direct probe.

The separate [speaker-word report](speaker-words-report.json) contains two actual
Small recognitions with `word_timestamps=True`: ordinary English and quiet Greek.
Both produced real `_words`. Passing those words through the existing downstream
alignment preserved the complete recognized text and validated actual word
times. With no acoustic turns supplied, every label remained `Unknown speaker`.
This is **not** new acoustic speaker inference or speaker-accuracy evidence.
Seven existing focused speaker persistence/alignment checks also passed; their
controlled fixtures do not replace a future actual speaker-model regression.

## Preserved local acquisition failures and nonspeech results

All failed attempts remain separate, unchanged reports:

1. [Port 8767 attempt](local-provider-port-mismatch-report.json): the app's normal
   Origin guard rejected API calls with HTTP 403 before provider access or ASR.
   This was a harness configuration error; the guard was not relaxed.
2. [Normal port without transport](local-provider-missing-transport-report.json):
   Dailymotion failed before ASR because its normal extractor required a Firefox
   transport target that was not installed. Both exact digital silence and
   deterministic nonzero white-noise uploads passed their strict no-record,
   no-export and input-cleanup checks.
3. [One corrected transport attempt](local-provider-with-curl-report.json): after
   isolated `curl-cffi==0.17.0` installation, Dailymotion failed before ASR with
   **“No video formats found!”**. Both nonspeech cases passed again. No unchanged
   Dailymotion retry followed this result.

The corrected attempt's acquisition failed after 21.225 s; the complete provider
plus nonspeech process took 58.841 s. The exact error chain, normal options and
raw noise-inference evidence are retained. These local acquisition failures do
not exercise the candidate's full Dailymotion ASR tail.

The missing transport exposed a packaging gap: the hosted workflow had installed
`curl-cffi` separately while the base installation did not. Primary
[PyPI 0.17.0 metadata](https://pypi.org/pypi/curl-cffi/0.17.0/json), retained in
[curl-cffi-0.17.0-metadata.json](curl-cffi-0.17.0-metadata.json), declares Python
≥3.10 and MIT, with ordinary dependencies `cffi>=2.1.1` and
`certifi>=2026.10.19`. Published stable-ABI wheels cover Windows x64/ARM64,
Intel/Apple Silicon macOS, and mainstream glibc/musl Linux architectures. No
32-bit Windows wheel is listed. Published wheel coverage is not proof that every
platform was actually installed in this experiment; dependency/native-library
license notices remain their own notices.

Recommendation: include `curl-cffi>=0.17,<0.18` in the base requirements for the
advertised Dailymotion path and validate it in the real archive installation.
The parent has prepared this packaging correction. The normal extractor selected
its transport; no provider-specific authentication, cookies or header overrides
were introduced. Installing the missing dependency did not turn the subsequent
remote no-formats failure into a provider success.

## Hosted observations and the outstanding tail gate

The already-published f12 checkpoint has environment-specific provider results:

- [Follow-up provider job](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586538/job/140794270324):
  YouTube `R6MlUcmOul8` required bot-verification sign-in; explicit Vimeo
  `19934655` returned HTTP 401 from `player.vimeo.com` with Cloudflare. Both failed
  before ASR. [hosted-provider-context.json](hosted-provider-context.json)
  preserves timestamps, exact errors and original report identity.
- [Original provider job](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46085586538/job/140794270604):
  Dailymotion succeeded with the **old ASR policy**, exact previously retained
  media and PCM, and the same Small model revision/weights. The complete report
  still failed because other providers failed. The baseline context is preserved
  in [dailymotion-hosted-baseline-evidence.json](dailymotion-hosted-baseline-evidence.json).

The new [tail checker](../../tests/check_asr_dailymotion_tail_followup.py) reads
completed normal provider artifacts. It requires the exact retained 734.1453125 s
recording, complete unchanged PCM, actual Small model identity, the current
`app.py` hash, expected candidate settings, raw-to-saved equality, normal
persistence/exports and restart preservation in a distinct process. Actual
request, effective decoder information and segment-creation events are bound to
the same job/process; model resolution must precede the request. It then requires
four specific late phrases in their expected broad time windows, with actual
word timing evidence bound to the same parent text. A 0.5-second parent-bound
tolerance accommodates observed upstream segment/word offsets of 0.36–0.44 s;
the original word strings are concatenated to preserve split contractions. This
localization rule applies to the four anchor intervals, not every transcript
boundary. It does not treat arbitrary nonempty text or late hallucinated credit
text as retained dialogue.

```sh
python tests/check_asr_dailymotion_tail_followup.py \
  qa-real-links/provider-report.json \
  --output qa-real-links/dailymotion-tail-check.json
```

Run the checker even if unrelated providers make the provider harness exit
nonzero. The four anchors concern the world-change exchange around 518 s, the
reply around 534 s, and the lesson/worse-outcome exchange around 561–568 s. Their
bounded lexical variants allow punctuation and ordinary contraction differences;
they are not a transcript rewrite or an exhaustive accuracy metric. Changed
media or model hashes fail the comparison and require review.

The retained f12 baseline passed the explicit `--baseline-review` mode, which
sets `candidate_tail_regression_passed:false`. Twenty-six focused checker tests passed,
including rejection of a missing tail, words moved into an early interval,
missing word evidence, old ASR settings, cropped input, modified saved text,
another source revision and different media. Internally consistent truncation
and early-shift controls fail specifically on the missing late anchors. Further
controls reject injected prefixes, mismatched effective ASR settings, another
job's events, misattached words and a model loaded after inference. These
synthetic checker tests do not claim candidate inference.

The [independent final checker review](checker-independent-review.json) tested
the same frozen checker hash with two positive controls and 24 negative probes;
all produced the expected outcome. The real historical baseline was reviewed in
baseline mode. The candidate-shaped positive control was explicitly synthetic
and exercises checker logic only. No remaining material defect was identified
for this narrow artifact gate; actual candidate inference is still required.

**At this freeze, the aligned candidate's actual hosted Dailymotion tail has not
run.** The next step is to publish the frozen candidate to the draft development
branch for that exact hosted regression. If it loses the retained late dialogue,
reject or revert the ASR policy and preserve the failure. A public original-film
audio source was located through Xiph's licensed directory, but no separate
full-film substitute was run or counted as provider success.

## Evidence and reproduction

The [manifest](manifest.json) hashes every file in this folder and the five new
probe/checker/test scripts. Reports are unchanged copies or explicitly labeled
compact extractions; rejected experiments are preserved. Media/model binaries
are identified by digest rather than duplicated in the repository.

`probe_asr_vimeo_followup.py` accepts an isolated source root, complete audio path,
expected audio SHA-256, output directory and model. `probe_asr_quiet_followup.py`
wraps the existing actual upload-quality harness; [quiet-invocations.json](quiet-invocations.json)
retains its exact commands. `probe_asr_speaker_words_followup.py` exercises real
word production and the existing downstream alignment without an acoustic
speaker-model claim. Recreate the baseline archive and apply only the recorded
patch for a candidate replay. Model, audio and source digests must match before
comparing output. Existing output files are preserved rather than overwritten.

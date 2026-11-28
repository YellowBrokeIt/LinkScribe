# Alignment-only ablation: commands restored, broader regressions remain

**This experiment does not approve universal word alignment as a generally
speech-preserving release policy.** Disabling the 2.0-second hallucination
heuristic restored the two previously omitted commands and retained all four
original tail anchors. The complete-reference review still found material
substitutions and newly emitted ellipsis text. These successes and failures are
retained together, with the original uncorrected output.

The integration decision is to restore the complete prior conditional-word
recognition policy. This evidence records that decision; a later production
change and its own CI must be identified separately. The application remains
version 0.3.0, and no stable release is approved by these experiments.

The experiment was completed once per film on 2026-11-28, after acceptance of
the [frozen plan](../alignment-only-plan.json), SHA-256
`b7c8a2be6c40a5add4b6cf2a738819039ecde5d96f485a0b807af757958d22b1`.
The plan's `not_started` value is its immutable preparation state. The separate
[execution record](execution.json) records the completed attempts. No retry,
threshold tuning, source-specific hint, cropped recording, altered reference,
or relaxed scoring window was used.

## Actual application path and identities

An isolated copy of
[79189b013732fb95c1e685e1639b1b7891899729](https://github.com/YellowBrokeIt/LinkScribe/commit/79189b013732fb95c1e685e1639b1b7891899729)
used the [recorded patch](../alignment-only-proposed.patch): word alignment
remained enabled and `hallucination_silence_threshold` became `None`, including
its processing metadata. Its `app.py` SHA-256 was
`736ff2e1080170701410807c5f0483cb4b09acb68da3e9169ebb376b16399b48`.
All recorded source hashes remained unchanged during each run.

Both actual requests and effective decoder metadata confirm Small, CPU int8,
automatic language selection, beam size 5, full unchanged PCM, VAD disabled,
`no_speech_threshold=0.6`, `condition_on_previous_text=False`, word timestamps
enabled, no hallucination threshold, and the original temperature schedule
`[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]`. Initial prompt, prefix and hotwords were empty.
The same cached model revision
`536b0662742c02347bc0e980a01041f333bce120`, model.bin SHA-256
`3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`,
was resolved before inference. The runs used offline model resolution and
preserved the prior per-film QA seeds.

| Observation | Official *Tears of Steel* | Retained Vimeo *Sintel* |
|---|---:|---:|
| Complete PCM duration | 734.000 s | 888.070375 s |
| Mono float32 samples at 16 kHz | 11,744,000 | 14,209,126 |
| QA seed | 1729 | 20261128 |
| Actual saved segments | 74 | 47 |
| Upload-harness elapsed | 88.614 s | 92.493 s |
| Recognition elapsed | 86.558 s | 92.054 s |
| Complete child-process elapsed | 89.978 s | 93.368 s |
| Process peak RSS | 1,607,110,656 bytes | 1,549,291,520 bytes |
| Sampled process-group peak RSS | 1,608,179,712 bytes | 1,550,254,080 bytes |
| Actual upload, save, SQLite and five exports | Pass | Pass |

The two child processes ran sequentially from **01:08:25 to 01:11:28 UTC**, a
total of 183.356 seconds. Both exited with code 0 and no limit stop. The frozen
240-second recognition, 255-second process, 600-second total and 2.5 GiB sampled
RSS limits were respected. Sampling every 0.25 seconds can miss brief aggregate
peaks. These are single-machine observations with cached weights, not a
controlled performance benchmark. The earlier Sintel aligned/2.0 observation
measured a direct recognizer call, so its elapsed time is not an equivalent
end-to-end comparison.

The [consistency and anchor audit](consistency-anchor-audit.json) independently
reads each retained SQLite database and all exports. Actual raw segment
projections equal the normal saved JSON, report, SQLite rows and exported JSON.
Each export digest and ZIP member also matches. The normal harness evicted its
in-memory job and a separate interpreter verified SQLite. A complete
application/server restart was not exercised by this local upload harness.

## Frozen anchor and omission checks

All six predeclared phrase checks pass using both fully contained raw segments
and real decoder words bound to their parent segment. The original four windows
and patterns were retained exactly. The two command regressions were declared
before this ablation began.

| Reference cue | Frozen window | Actual alignment-only segment | Finding |
|---|---|---|---|
| 70, captain/abort command | 501–513 s | 504.92–508.06 s | Restored |
| 71, world-change line | 510–529 s | 517.86–521.08 s | Retained |
| 72, reply | 528–545 s | 533.86–535.92 s | Retained |
| 73, memory-completion command | 533–544 s | 537.78–539.14 s | Restored with “overwrite” |
| 75, lesson line | 545–574 s | 558.06–563.44 s, including preceding interjection | Retained |
| 76, worse-outcome line | 558–577 s | 565.92–566.70 s | Retained |

The old aligned/2.0 output lacked cues 70 and 73 before storage; the original
baseline retained both, with “override” in cue 73. Their return in this ablation
supports disabling the heuristic for this input. It does not establish
regression-free recognition across the rest of either film.

## Broader quality findings

The [independent full-reference review](independent-full-reference-review.json)
covers all 76 published *Tears of Steel* cues and all 26 published Sintel dialogue
cues, alongside the complete uncorrected hypotheses.
The short Sintel reference is not exhaustive for interjections or sung words.
Reference gaps alone do not establish silence.

Material findings include:

- *Tears of Steel* cue 59 changes the intended verb “crush” to “brush,” while
  both previous arms retained the intended verb. Cue 62 remains corrupted as
  “Who'd that lip?” rather than the baseline's recognized ad-lib phrase.
- Six new ellipsis-only segments occur at 260.30–284.20 seconds in the official
  film. All six remain visible in raw, saved and exported output.
- Sintel cue 16 changes “Get him, Scales!” to “Got him, fearless.” The original
  and aligned/2.0 outputs retained the command/name. Cue 15 again uses “Skills”
  where the aligned/2.0 arm had recognized “Scales.”
- The earlier large unsupported Sintel dialogue burst and its 669.5–691.5 s
  ellipses remain absent. Real quiet dialogue around 207–233 s and 445–465 s is
  still present, with lexical errors preserved.
- Late credit vocals remain represented. The composer publishes a
  [song score](https://www.janmorgenstern.com/sintel/I_Move_On-Sintels_Song.pdf),
  supporting that the film contains real singing. Some newly recognized sung
  text is incomplete or incorrect; the score's existence does not establish an
  exact transcription of this performed recording.

The independent review report has SHA-256
`ef749fe5e7c46538fc1745997ee6208f4868d7cd5c54af6d9c91b014cf2881c3`.
Neither the fixed-anchor success nor the lower segment count grants general semantic,
subtitle, language, or release approval. Previous quiet/noise regressions tested
their own recorded settings; they were not rerun for this configuration.

Word alignment can change decoding as well as timestamps: the installed Faster
Whisper 1.2.1 implementation advances its next decoding position to the last
aligned word in an applicable branch, independently of the hallucination
threshold. The [code observation](upstream-code-observation.json) binds this
explanation to the installed file and primary upstream source. This is a
plausible mechanism for changed subsequent output, rather than proof of the
acoustic cause of every individual error.

## Provider and persistence scope

This is actual full-audio upload evidence using the same retained inputs. It
does not retry or pass the blocked Dailymotion, YouTube or hosted Vimeo requests.
The original exact-provider checker remains unchanged and unexercised after
acquisition failure on 79189b0. The official FLAC was a separately identified,
publisher-listed rendition; the retained Vimeo recording came from the earlier
successful local acquisition. Neither fact changes the later hosted errors.

Each unchanged `*-report.json` retains complete raw observations and the
original absolute artifact paths. The adjacent `*-report-artifacts-*` folders
retain the actual saved transcript, exported files and SQLite database. The
read-only [audit script](../analyze_alignment_only.py) can use these adjacent
archived directories after the original scratch paths disappear. No audio or
model binary is duplicated here. The frozen plan, runner/controller, execution,
source patch, exact reports and manifest provide the audit trail.

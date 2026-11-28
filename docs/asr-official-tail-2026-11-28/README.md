# Official-film comparison: fixed anchors pass, broader speech loss found

**The aligned-word / 2.0-second hallucination policy is not accepted as a general
speech-preserving change.** Its four predeclared late-dialogue anchors passed on
this complete official-film rendition, but an independent exploratory review
found two real reference-covered commands that the baseline retained and the
candidate omitted. Both facts remain recorded. No scoring window, transcript,
reference or frozen provider checker was changed to fit this output.

This is a separate local full-audio upload experiment. The exact Dailymotion
provider gate remains unexercised after its hosted acquisition failed with
“No video formats found!” on
[79189b013732fb95c1e685e1639b1b7891899729](https://github.com/YellowBrokeIt/LinkScribe/commit/79189b013732fb95c1e685e1639b1b7891899729).
The experiment does not establish provider success, overall semantic accuracy,
subtitle accuracy, an application/server restart, or readiness for v1.

## Source and pre-inference freeze

The [official Blender project download page](https://mango.blender.org/download/)
lists Xiph's distribution directory for original images and audio. One ordinary
download of the complete
[stereo FLAC](https://media.xiph.org/tearsofsteel/tearsofsteel-stereo.flac)
succeeded. The retained [license notice](publisher-LICENSE.txt) identifies the
Blender Foundation, *Tears of Steel*, Mango Open Movie Project (2012), and CC BY
3.0. Xiph's [published checksum file](publisher-SHA1SUMS.txt) matches the download.
No further request to the blocked video providers was made.

| Identity | Value |
|---|---|
| Original FLAC | 83,769,154 bytes; 734.000 s; stereo 48 kHz |
| FLAC SHA-256 | `2ec70bfb31b70d4229d8a7c1ea1e759fd3d464c206d0c3a7ff15c7752c0b25ea` |
| Published and verified FLAC SHA1 | `3fe208d47a4d16030d6a2658c1385d6b6ae16491` |
| Complete decoder input | 11,744,000 mono float32 samples at 16 kHz |
| Complete PCM SHA-256 | `ce528ed4ac517abefcbfb90f9aedbb7313d246ad89f03eabb5ba69a104d3ae06` |
| Small revision | `536b0662742c02347bc0e980a01041f333bce120` |
| Small model.bin SHA-256 | `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |

The [plan](plan.json) was frozen at **2026-11-28 00:53:07 UTC**, SHA-256
`42d5aa819b264ee3a1622d8c76956cdfa727b98825c5cb319819036c651a0312`, before
the first inference at 00:53:42 UTC. It pins audio, complete PCM, source code,
Small weights, QA seed 1729, references, four broad timing windows, one attempt
per arm and 240 seconds per inference. Both actual reports record that same
plan hash. There was no cropped-audio substitute or reference prompt.

The [published English SRT](publisher-TOS-en.srt), obtained independently before
inference, contains 76 cues. Its SHA-256 is
`ce9578f6fe098a5821045a38884b229160f9e7ba27890448a92f5be330c6e6fe`.
This reference supports dialogue review; it is not an exhaustive annotation of
every audible interjection or a word-boundary gold standard.

Two preflight bookkeeping corrections remain visible. The initial acquisition
log computed the small checksum text file's size/digest before its buffered
writer closed; the correct closed file is 790 bytes, SHA-256
`d349fa846d03054f602ec677fffe4f8eb7da7ce61e7b5a6e59c04e74964dc9ff`.
The original log is retained. Regex word-boundary escaping was corrected and
checked against each published phrase before inference; the original preflight
plan is retained separately. Neither correction modified audio or an ASR output.

## Paired normal application path

Both arms use isolated copies of the same published 79189b0 tree. The baseline
restores the previous ASR keyword policy and truthful corresponding processing
metadata; its [exact patch](baseline-reversion.patch) is retained. The aligned
arm is the unmodified published recognizer. Both use CPU int8 Small, automatic
language selection, beam size 5, VAD disabled, the unchanged full PCM, original
temperature fallback, and no initial prompt, prefix or hotwords.

The new [runner](../../tests/probe_asr_official_tail_followup.py) wraps the
existing real upload harness. It adds observations and a predeclared QA seed,
without replacing model output or production options. Each arm exercises normal
upload → real recognition → saved JSON → SQLite → TXT/SRT/VTT/JSON/ZIP exports.
The harness evicts in-memory jobs and a separate interpreter verifies SQLite.
This is not a full browser/server-restart claim.

| Observation | Prior-policy baseline | Aligned words + 2.0 s heuristic |
|---|---:|---:|
| Normal harness structural result | Pass | Pass |
| Complete PCM / pinned model / unchanged source verified | Yes | Yes |
| Raw segments = saved JSON = SQLite = exported JSON | Yes | Yes |
| Segments | 86 | 60 |
| Upload-harness elapsed | 64.991 s | 91.627 s |
| Whole child-process elapsed | 65.988 s | 92.613 s |
| Process peak RSS | 1,554,010,112 bytes | 1,539,084,288 bytes |

Both processes exited by 00:56:21 UTC, inside the predeclared bounds. These are
single-machine observations with already-cached model files, not a controlled
performance benchmark. Neither arm was repeated. The subsequent, separately
predeclared alignment-only ablation is recorded below.

## Fixed four-anchor result

The [paired audit](paired-audit.json) verifies source hashes, complete PCM,
actual resolved Small weights, normal decoder settings, raw-to-saved equality,
SQLite and actual word evidence. It applies the frozen patterns and windows.

| Published cue | Frozen window | Aligned raw segment | Result |
|---|---|---|---|
| World-change line, 518–520 s | 510–529 s | 517.28–520.32 s | Phrase and real words retained |
| Reply, 534–536 s | 528–545 s | 534.70–535.96 s | Phrase and real words retained |
| Lesson line, 562–564 s | 545–574 s | 558.40–563.44 s, including preceding interjection | Phrase and real words retained |
| Worse-outcome reply, 566–567 s | 558–577 s | 565.48–566.70 s | Phrase and real words retained |

The baseline contains all four phrases, but its world-change segment spans
508.8–535.2 s. It therefore passes only three strict segment-window checks.
That timing limitation is preserved; the window was not widened. Word-level
evidence was not produced by the baseline policy and was not invented.

## Exploratory broader review: material regression

The [independent review](independent-exploratory-review.json) examined all 76
reference cues and both complete uncorrected hypotheses. It independently
verified raw/report/SQLite/export equality and retains the relevant raw segment
and word neighborhoods. This broader review was exploratory and did not replace
or retroactively expand the four frozen anchor criteria.

| Published reference cue | Baseline evidence | Aligned evidence |
|---|---|---|
| 70: “Captain! We have to abort!”, 506–508 s | Present in raw and saved segment 485.0–508.8 s, with coarse timing | Absent from raw and saved output |
| 73: “Memory overwrite complete!”, 538–539 s | Present at 537.2–539.2 s as “Memory override complete!” | Absent from raw and saved output |
| 62: “Good ad-lib.”, 410–411 s | Recognizable phrase retained | Corrupted to “who dad lip” |

The missing commands are absent before persistence: the normal raw model segment
constructions already lack them. This is not an export or storage deletion.
The four-anchor success does not justify describing this candidate as generally
regression-preserving. Because alignment and the dependent heuristic changed
together, this pair alone does not isolate which change caused each loss.

The subsequent [alignment-only ablation](alignment-only-results/README.md) keeps
word alignment and sets the hallucination heuristic to `None`. After the
[separate plan](ALIGNMENT-ONLY-PLAN.md) was accepted, each unchanged full film
ran once with its prior seed and the same pinned Small weights. Both previously
missing commands returned, and the four original anchors passed again. The
broader review nevertheless found material substitutions and newly emitted
ellipsis text. Those results do not approve universal word alignment as a
generally regression-preserving release policy. The frozen plans, original
outputs and original provider checker remain unchanged; no threshold sweep or
relaxed gate was used.

## Evidence files

`baseline-report.json` and `aligned-report.json` are unchanged actual reports.
`baseline-transcript.*` and `aligned-transcript.*` are unchanged exported files;
the complete small saved/export/SQLite directories are also retained as
`baseline-artifacts/` and `aligned-artifacts/`. Model/audio binaries are identified
by digest and are not duplicated in the repository. `analyze_pair_executed.py`
is the exact first executed audit source whose digest is in the paired audit;
`analyze_pair.py` additionally supports archived relative artifact paths. The
final manifest binds every retained file and the new runner.

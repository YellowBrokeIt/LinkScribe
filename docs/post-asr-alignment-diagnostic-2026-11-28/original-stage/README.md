# Prepared fixed-text timing diagnostic

**No speech model has been initialized or run in this preparation.** Five complete
retained inputs have been decoded and frozen. The executable uses the corrected,
reviewed [postpass proposal](POSTPASS-PROPOSAL.md); actual execution still requires
the final executable review and root's explicit model-slot authorization.

The production application remains at `6de3faddf88bb5da8ea35d985b33ad26e55e249f`.
This directory contains an isolated experiment. It does not change the default
model, recognition options, existing transcripts or any historical gate.

## Fixed scope

The official *Tears of Steel* baseline contains 86 original native segments in
19 original decoder windows. Its full 11,744,000-sample PCM again matches the
historical hash `ce528ed4ac517abefcbfb90f9aedbb7313d246ad89f03eabb5ba69a104d3ae06`.
Four full ordinary/−20 dB English and Greek clips supply four additional windows.
Those short controls retain fixed saved strings and pinned re-encoding, with the
absence of original native token segmentation explicitly recorded.

The [input manifest](input-cases.json) contains fixed source strings, tokens,
window spans and full-array identities. [Preparation](input-preparation.json)
records the decode-only work. Publisher subtitles and the unchanged six phrase
windows are confined to [evaluation-only material](evaluation-only.json), which
the worker does not read.

The original 7a Dailymotion audio is unavailable. The independently acquired
734.000-second official FLAC is a different rendition from that 734.1453125-second
provider input. It cannot regrade 7a. The later 6de ordinary recognizer already
passed the unchanged 28/28 tail gate; this experiment asks a separate question
about timing robustness while text stays fixed.

## Executable behavior

[run_postpass.py](run_postpass.py) calls the complete pinned upstream timing
postprocessor after recognition is already fixed. It retains the native path,
word boundaries before heuristics, full adjusted timing and every projection
warning. Generation, fresh recognition, language redetection and network calls
are forbidden. Exact text/token/window checks precede alignment.

Each attempted encode and align call is written before native invocation, and
returned raw results are written before validation. The controller reuses the
previously reviewed owned-process-group monitor, records 100 ms RSS samples,
and checks final worker high-water/time/completion evidence after exit as well
as live samples. The declared caps remain 2.5 GiB owned RSS, 120 s startup,
240 s per full input and 600 s total, one initialization and one attempt per
input, with at most four available CPU threads.

Requested compute type remains `int8`. As in the prior reviewed CPU harness,
the accepted native effective type is `int8` or `int8_float32`; the actual value
is recorded. A floating-point or GPU fallback cannot silently pass.

The [plan](plan.json) binds executable, input, runtime, model, source and current
physical/export policy identities. The [timing view](production-timing-view.json)
contains exact selected functions from 6de for isolated projection/export
checks. These checks are not a full server, SQLite or acoustic-speaker run.

## Preparation checks

The final [model-free controls](non-model-tests.txt) passed **18 tests** in
1.927 seconds. They include missing/reordered tokens, wrong complete audio/PCM,
incorrect window frames, the required native terminal row, valid zero-duration
token paths, a count of all nine real historical zero-duration words and actual
whole-segment fallback on a retained segment from each of the two recordings,
crossed timing, current physical/subtitle limits, actual upstream `get_end`
state semantics, native compute-type resolution, interrupted-call evidence and
recorded limit/completion failures between samples. The
[source-bound test record](non-model-tests.json) distinguishes this from model
execution. [Validate-only](validate-only.json) also passed, with no frontend,
model construction or inference.

The original raw-only route remains rejected as a repair of the first phrase's
start. [Pinned native source](native-contract/inventory.json) and the
[synthetic contract control](native-contract-check.json) show why: native DTW
begins token zero at frame zero. The complete upstream postprocessor adds timing
estimates; they are now explicit candidate behavior, not hidden in a supposedly
raw-only result.

Preparation history retains the original proposal/state correction, the first
helper/plan/15-pass record, the requested-versus-effective type issue, the final
resource/attempt-accounting review, and the initial wrong-interpreter metadata
lookup. None was a speech-model attempt. No failure is overwritten as a success.

## Commands

The safe preparation check is:

```bash
/workspace/scratch/94360995dd61/linkscribe-dev-venv/bin/python \
  /workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/run_postpass.py \
  --validate-only \
  --plan /workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/plan.json
```

After root explicitly authorizes the reviewed one-shot stage and releases the
shared model slot, its execution command is:

```bash
/workspace/scratch/94360995dd61/linkscribe-dev-venv/bin/python \
  /workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/run_postpass.py \
  --execute \
  --plan /workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/plan.json \
  --output /workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/results
```

The controller rejects an existing output directory. The command has not been
run during preparation. Timing estimates remain unreviewed until actual outputs
exist. Even exact text retention cannot establish that the original recognized
words were spoken; baseline lexical errors and unsupported text remain intact.

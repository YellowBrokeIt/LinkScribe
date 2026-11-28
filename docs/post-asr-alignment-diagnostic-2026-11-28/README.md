# Selected archive: original fixed-text timing stage

**Outcome: the original profile was rejected for full-film timing improvement.**
This directory preserves a selected, hash-verified archive of that experiment;
it is **not the complete original 108-file bundle**.

## Actual result

The one authorized stage completed all five full inputs in 32.457 seconds, with
one Small CPU model initialization, 23 encoder calls and 23 fixed-text alignment
calls. There was no recognition, generation or language-redetection call. Peak
owned-group RSS was 1,120.59 MiB sampled; the worker OS high-water was 1,171.48 MiB.
The model unloaded and the owned process group was empty at completion.

The full-film adjusted intervals had one 0.26-second overlap, between segment
indices 80 and 81 in neighboring original encoder windows. Its predeclared
whole-film fallback restored **all 86 original segment intervals** and cleared
private word evidence. The independently reviewed final output passed **4/6
segment-anchor windows and 0/6 private-word-anchor windows**. Four ordinary and
quiet short clips completed without projection warnings. Every source string,
including the original recognition errors, was preserved.

See [the completed outcome](original-stage/RUN-RESULT.md),
[the raw report](original-stage/results/report.json), and
[the independent timing review](original-stage/independent-result-review/independent-timing-review.json).
The review inspected all 76 publisher cues, the complete 86-segment timeline and
the four short outputs. Mechanical completion does not establish acoustic word
timing accuracy, speaker attribution, application integration or release quality.

## Exact archive selection

The unchanged [original complete manifest](original-complete-manifest.json)
binds the original **108 files / 54,181,965 bytes**. Its SHA256 is
`bb0d69aa010bc536df82ada3e6da2c3ef65eaebcac69b6a892b8d9db8d330633`.

This archive retains **103 of those original files / 5,515,725 bytes** under
`original-stage/`, preserving each selected file byte for byte. It includes:

- All **51 raw result files**, including native alignment paths, before/after
  timing records, exported text/JSON/SRT/VTT, resource samples and the worker log.
- The frozen executable, plans, exact native source excerpts and license files,
  input/token/window identities, synthetic controls and validation results.
- The initial insufficient raw-only proposal, the upstream-state correction and
  preparation failure/review history.
- All **five independent root review and audit files**, plus the earlier protocol
  reviews and unchanged before-execution manifest.

The five omitted files are the complete `.npy` audio arrays, totaling
**48,666,240 bytes**. The
[archive-selection manifest](archive-selection-manifest.json) explicitly lists
all five omitted NPY hashes and sizes, their complete decoded PCM hashes, shapes,
float32 interpretation, 16 kHz rate, sample counts and physical durations. It
also records the original media hashes and sizes; those source media were
rehashed during archive preparation without decoding or running any model.

Original media files and cached model weights were external dependencies of the
original experiment, not members of its 108-file manifest, and are not copied
here. Their recorded identities remain in the selection manifest and frozen
original plan. The selected archive therefore preserves the evidence and
protocol but cannot by itself repeat the model run. Restoring a runnable view
requires the exact omitted arrays or reproduction from hash-matched media with
the pinned decode path, plus the exact separately identified model/runtime.
The historical absolute paths in frozen plans remain unchanged intentionally.

The 734.000-second official FLAC differs from the unavailable exact
734.1453125-second 7a provider input. This experiment cannot regrade that older
provider failure. Any later local-fallback projection is a separate candidate;
it must preserve this original profile, raw outputs and rejection.

No production source or default was changed by this archive operation. No
provider, model, encoder, alignment or recognition call was made while copying it.

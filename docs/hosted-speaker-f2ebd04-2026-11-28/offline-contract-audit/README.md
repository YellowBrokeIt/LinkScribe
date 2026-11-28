# Completed speaker pipeline: qualified offline contract correction

The actual application worker completed successfully at commit
`f2ebd0433976ed62478b67e98c4515e3d78afaa5`. The original hosted controller rejected
the run because it expected the constructor argument `cpu_threads=4`, while the
unchanged application uses faster-whisper's native default `cpu_threads=0`.
The original [GitHub run 46123086352](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46123086352)
remains **failed**, and its report, logs, artifact and original plan remain unchanged.

This separate offline audit changes only that constructor assertion to `==0`.
All other original `completed_contract` statements are reused exactly. It also
checks the complete retained resource series, full-input identity, same-engine
fixed-text timing, recognizer release and recorded durable persistence. No model
is initialized or invoked, and no recognition or hypothesis is repeated.

## Actual result and unchanged acoustic criteria

The 34.635-second original controlled fixture contains the same two returning
readers and four declared source intervals. The complete 554,160-sample waveform
entered recognition, fixed-text timing and speaker analysis. The worker made one
baseline transcription with `word_timestamps=False`, two fixed-text encode/align
calls on the original windows, and one acoustic speaker analysis. All eight
recognized segments retained their text and acquired usable optional word timing;
speaker grouping produced 19 saved groups, seven explicitly unassigned.

The unchanged original score assigns 221 of 258 interior samples (0.8566, required
at least 0.80). All assigned samples agree with the optimal two-reader label
mapping (purity 1.0000, required at least 0.95). The remaining 37 samples stay
unassigned. Per original interval, assigned samples are 65/65, 50/63, 55/65 and
51/65. Reference identities were used only for scoring after the owned worker
exited; they were not passed to the recognizer or speaker backend.

The worker took 11.1442 seconds; controller elapsed time was 11.7187 seconds.
All 111 retained process-group samples are complete. Sampled group peak was
1,078,747,136 bytes (1,028.8 MiB); process high-water was 1,215,311,872 bytes
(1,159.0 MiB). These are different measurements. Both stay below the original
6 GiB limit, all original phase limits hold, and final owned-process cleanup is
complete. Actual weak references establish recognizer release before speaker
analysis. Translation and summary were disabled in this fixture, so this run
does not measure the separate audio-to-text-model lifetime boundary.

## Why constructor zero is correct

The exact primary source files are retained under `thread-source/`, with their
SHA-256 and independently checked Git blob SHA-1 identities in
`thread-source/source-provenance.json`.

- [faster-whisper v1.2.1](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
  defines the constructor default as zero and forwards it to CTranslate2's
  `intra_threads`. Its documentation distinguishes a nonzero override from the
  normal native/default environment path.
- [CTranslate2 v4.9.1 Whisper binding](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/python/cpp/whisper.cc)
  documents `intra_threads=0` as selecting a default value.
- [CTranslate2 v4.9.1 replica pool](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/include/ctranslate2/replica_pool.h)
  applies the configured thread setting when workers are initialized.
- [CTranslate2 v4.9.1 utilities](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/src/utils.cc)
  resolve zero through `OMP_NUM_THREADS`, otherwise using a default of at most
  four hardware threads.

The exact executed controller sets `OMP_NUM_THREADS=4` and `MKL_NUM_THREADS=4`
and applies CPU affinity `[0,1,2,3]` before successful worker exec. This is the
original **source-enforced launch constraint**. The observer records the
constructor argument after `inspect.signature(...).apply_defaults()`, not an
effective native thread measurement. No worker-side affinity readback or
per-thread scheduling series was captured, and this audit does not claim one.

## Retention and reproducibility

`bindings.json` was frozen before this offline execution and pins the original
controller, original acoustic scorer, original hosted plan, original failure,
primary thread sources, complete artifact manifest and actual result. The
unchanged extracted artifact remains in the adjacent
`hosted-f2ebd04-speaker-review/artifact/` directory; its ZIP is artifact
15254526534, 1,916,920 bytes, SHA-256
`1321ed065fb87bcfa8eac3e408e876d2b25a498d3967f6bc187f0a914e36e7ca`.
The audit rehashes all 30 extracted files and the original ZIP before checking
the corrected contract. Exact immutable-commit source checks are retained in
the adjacent `source-commit-audit.json`.

The authorized offline command was:

```sh
python audit_retained_result.py --bindings bindings.json --output offline-audit.json
```

It exited zero. `offline-audit.json` preserves the original failed conclusion
and reports only this separate correction. Three focused tests passed in
0.08 seconds, covering two positive controls and 18 synthetic invalid mutations
for constructor, worker/device/compute, limits, source/model, repeated calls,
incomplete resource accounting and surviving processes. These are checker
controls, not additional acoustic runs.

`proposed-controller.patch` is the exact one-literal correction used by the
offline function reconstruction. `proposed-maintained-fix.patch` additionally
updates the old synthetic constructor fixture and adds five runtime negatives.
Neither patch has been applied to the maintained source. A future maintained
change needs its own source-bound plan; the two prior hosted plans are historical
evidence and must not be rewritten to certify new bytes.

## Scope

This supports the reviewed pipeline and this controlled English fixture only.
Inserted gaps simplify boundaries; read speech is not a natural meeting, Greek
speaker accuracy or overlap evaluation. Forced word timing does not establish
that all recognized words were spoken or that word boundaries are acoustically
precise. All original recognition text, including any lexical errors, remains
unchanged. The broader v1 quality gates remain separate.

## Independent completed-result review

The unchanged independent review is retained under `independent-review/`.
Its 185 checks pass for the original ZIP and all 30 extracted files, exact
immutable sources, complete PCM, native tokens and alignment paths, all resource
samples, source-word preservation, SQLite rows and export/backup payloads. The
review independently reproduces the original acoustic score and accepts the
qualified constructor correction. It preserves two review observations: SQLite
read-only access created temporary sidecars that were moved into reviewer
preparation history; and two ZIP containers have different timestamps while all
member payloads are equal. The actual original artifact inventory is again
exactly 30 files and every original hash is unchanged.

Independent result SHA-256:
`4125be394456498add10fa1d4c7e0affc1a1609861f57a2e36099901f43707b0`.
Constructor-correction review SHA-256:
`5dccbad7c100acf4be9493cff64dd6e64b58114f1495a0901d7225862c4b5093`.

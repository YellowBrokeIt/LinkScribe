# Exact 11e3365 hosted checkpoint

All six workflows completed successfully on `11e336577c7980f8da9dd817f265472596347a48`. This checkpoint corrects the QA constructor expectation while retaining the source-enforced four-CPU launch constraint and the original acoustic criteria. Production app, timing and enhancement files remain identical to d62df26.

## Application checks

Ubuntu and both independent Python suites passed **851 tests and 54 subtests**. Windows/macOS passed **845 tests and 54 subtests**, with six Linux-only process controls skipped. Chromium passed **35/35**, with real speech recognition and no uncaught JavaScript errors. The actual candidate ZIP passed all six fresh installation, launcher, health, diagnostics, UI, database and dependency checks. The source archive has 2,831 members and 86,366,233 uncompressed bytes; unchanged archive bounds remain in place.

The exact raw logs, run/job metadata and installation report are retained. Browser screenshots and the full source ZIP were not redundantly downloaded for this record; that limitation does not change the underlying hosted checks. The outer GitHub source-artifact ZIP and inner install-source ZIP have distinct digests, recorded in their respective receipts.

## Actual two-reader speaker pipeline

The normal Small recognition call used word timestamps off. Same-engine fixed-text alignment ran on the full 554,160-sample PCM and retained all eight source segments with word timing. The actual pinned default constructor has `cpu_threads=0`. Four-CPU launch affinity plus OMP/MKL settings are source-enforced; no separate effective native thread-count measurement is claimed.

Original acoustic criteria passed: **two speakers, 221/258 assigned core samples (85.66%), 100% matched purity**. Thirty-seven core samples remain unassigned. This run saved 21 groups, including 8 Unknown groups. SQLite, exports and backup content were independently checked. The 166-sample resource record completed in 17.479 seconds with 1,193,730,048 bytes peak sampled process-group RSS and clean process shutdown.

The original failed d62/f2 reports remain preserved in their earlier directories. This successful rerun does not rewrite those statuses or claim broader speaker accuracy. Full artifact bytes, audio inputs, raw outputs, persistence and export files are retained here. The independent read/hash/data audit passed 240 checks; see `independent-review/independent-result-review.json`.

## Remaining release blockers

The current default Ollama job completed all twelve translation cases with five automatic passes and seven review flags. It does not establish semantic acceptance. The earlier complete d62 review at identical production code found nine major errors and three acceptable outputs. No new model/default switch is approved. Faithful summaries, wider Greek/English speech meaning, provider access and whole-application modest-machine resource fit remain open. Application version remains 0.3.0.

`checkpoint.json` summarizes exact scope. `manifest.json` binds every payload file below this directory; no signed artifact download URL is retained.

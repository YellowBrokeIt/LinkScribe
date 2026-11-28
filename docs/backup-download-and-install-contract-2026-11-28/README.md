# Stream browser backup downloads and restore installation QA — 2026-11-28

Parent `46215eb9dc929b79c16471c26115811442826e85`, draft PR #2. Version remains 0.3.0.

## Exact-parent CI diagnosis

The preceding pagination checkpoint passed [PR platform tests](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46170187195) and [browser QA](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46170180093), but two installation jobs actually failed. Their downloaded logs identify the same contract drift:

- [Actual ZIP installation, job 141056655374](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46170180038/job/141056655374): `AssertionError: Freshly installed candidate does not have an empty library.`
- [Fresh checkout installer, job 141056584811](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46170180020/job/141056584811): `AssertionError: {'items': [], 'next_cursor': None}`.

The pagination API adds next_cursor, and both checks still compared against the exact old response. Both now require the exact new empty response, including a null cursor. A nonempty library, non-null cursor, or missing field still fails; no installation assertion is dropped. The fresh-database API regression checks that exact contract. New actual checkout and ZIP installation runs are required; this change does not claim they already passed.

The exact parent's independent Python 3.11/3.13 regressions, actual upload and real Ollama execution jobs passed. This does not approve model meaning. [Live sources](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46170180187) still failed overall: logs show Dailymotion and both nonspeech controls passed, two YouTube fixtures and a Vimeo fixture failed, the two additional provider fixtures failed, and the late-dialogue checker failed. Those failures remain open and are not rerun manually or regraded.

## Backup resource improvement

Backup creation already streamed individual database records, but the browser endpoint still held the entire compressed ZIP in a BytesIO and then created another response buffer. Now the existing format/checksum/consistent-read transaction writes to an owned seekable temporary file for browser downloads, retains the existing exact 50 MiB compressed / 100 MiB payload / record-count checks, and returns a 64 KiB-chunk streaming ZIP response. The file is closed on completion, response failure and construction/size failure. The bytes-returning helper remains available, now using the same writer. The existing batch ZIP response reuses the same generic class and preserves its filename and headers. Backup ZIP members and schema are unchanged; no restore validation changes.

## Scoped local evidence (2026-11-28)

Direct clone could not resolve github.com; real dependency installation/whole-app verification remains hosted. The exact replacement writer/compatibility helper, response classes, and endpoint were executed locally with Python, FastAPI/Starlette, HTTPX, real SQLite, ZIP and temporary files. The harness used a minimal matching schema and simplified JSON row decoding (no highlights in fixture). Exact parent pagination query/route used for the fresh-library check. Controls passed: strict fresh empty result, populated and no-match response distinction; actual HTTP ZIP bytes, headers, manifest SHA256, equivalence to bytes helper; exact size limit and 413 cleanup; response send failure closure and 64 KiB maximum chunks.

Synthetic benchmark: 401 rows (400 with 40,000 deterministic high-entropy characters split into two 20,000-character segments, one small Greek row), 24,182,027 compressed bytes, ZIP member contents equivalent. The in-memory bytes helper path used 26,640,453 bytes peak Python allocations, 1.3175 s; the temporary-file writer used 799,748 bytes, 1.3347 s (97.0% lower peak allocations). This is generation-only tracemalloc, not overall RAM, real speech, network download or full restoration performance. There is no speed claim.

FNV-1a of exact replacement sections after trimming whitespace: writer/helper 65a639d4, ZIP response classes a6e4f06b, backup endpoint 6a13a1cd. Five additional maintained full-source regression cases cover fresh API response, backup HTTP/restore with Greek text, exact cap, unexpected write failure, and transport closure/chunks. They require hosted verification; only the scoped local controls above ran here. The usual workflows trigger from the new checkpoint; no extra manual rerun.

All previous release requirements and evidence remain unchanged. Provider access, semantic English/Greek ASR, translation/summary, speaker breadth and whole-machine/long-recording resource requirements remain open.

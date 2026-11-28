# Reduced restore allocations — 2026-11-28

Parent: `eeb20929f300a33ca155f8cd24d80b155ad9ddb3`. The parent's [PR CI run](https://github.com/YellowBrokeIt/LinkScribe/actions/runs/46138900505) completed successfully on Ubuntu, macOS and Windows. This does not establish the new candidate's hosted status.

Restore previously held the compressed archive, full uncompressed payload, decoded JSON records and a second complete list of serialized SQL parameters simultaneously. The candidate releases the payload immediately after JSON parsing, then reuses the decoded list, replacing each validated record with its SQL parameters. Every record is still validated and duplicate IDs are still rejected before opening the database. No changes to archive schema, size limits, validators, existing-ID preservation, transaction boundaries or release gates. JSON decoding still requires a full document in memory; this is not a streaming parser.

Direct Git clone failed DNS resolution in the local runner. The exact restore function was copied from the parent and its old/new FNV-1a fingerprints match the published transformation (b55f5b6c / c8e6269e). A scoped Python 3.13 probe used actual ZIP/checksum/JSON and SQLite WAL operations with equivalent simplified record validation and serialization for synthetic records without highlights. Both functions accepted empty v1/v2 archives, preserved an existing record despite incoming edits, rejected a malformed final record and duplicates (including existing IDs), and accepted a subsequent valid import. The 600-record comparison produced identical SQL rows. Full production validators, API, highlights and platform matrix are not exercised by this probe. Added maintained tests require rejection before even opening SQLite for malformed late records or duplicate IDs, including existing IDs.

Synthetic bilingual archive: 168,745 compressed bytes / 21,807,063 uncompressed bytes. One instrumented sample per implementation:

| Restore | Elapsed with tracemalloc | Peak traced Python allocations |
| --- | ---: | ---: |
| Parent | 0.365 s | 119.08 MiB |
| Candidate | 0.351 s | 83.19 MiB |

These are scoped allocation measurements, not RSS, worst-case memory or real inference. The timing difference is not a reliable speed claim. The remaining parse-time allocation peak still needs work for whole-machine resource acceptance. Hosted verification of the exact new checkpoint remains pending; no language/provider/speaker/long-recording gates have been closed. Version remains 0.3.0.

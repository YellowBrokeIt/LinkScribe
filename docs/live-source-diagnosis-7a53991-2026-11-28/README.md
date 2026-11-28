# Retained live-source diagnosis — 7a53991

**The world-change dialogue was retained. Its native segment failed the original time-containment rule. The repeated Dailymotion batch item failed during provider extraction, before ASR.** Both original failures remain unchanged.

This review concerns commit `7a53991da60c9e052be9a72299218b291b364c8d` and artifact `15248292627`. Before analysis, the original ZIP and all 12 extracted files were copied unchanged. The ZIP SHA256 matches the parent's recorded published digest: `ce6744c736d97f3166a8939d1874c10aedcee5aada5399ab96819932a64450a8`. Every extracted file also matches its ZIP member.

## Dialogue and timing are separate observations

| Observation | Retained evidence |
|---|---|
| Exact phrase | `The world's changed Celia.` is present in native output, the saved record, SQLite, TXT, JSON, SRT and VTT. |
| Native interval | Segment 64 is `509.18–520.1800000000001`; the saved interval is `509.18–520.18` seconds. |
| Frozen rule | The ordinary-policy gate requires the complete segment inside `510–529` seconds. Its start is 0.82 seconds before that lower bound, so the gate fails. |
| Previous same-source output | The f12 baseline placed the same phrase at `518.28–520.28` seconds. |
| Window provenance | The original frozen README describes broad expected windows and the exchange around 518 seconds. This was not an exact acoustic onset/offset measurement. The later retained publisher subtitle cue is `518–520` seconds. |

The unchanged gate has **27 of 28 checks passing**, with `late_dialogue_world_changed` failing. The separate [text-retention diagnostic](text-retention-diagnostic.json) records all four frozen lexical patterns somewhere in the saved transcript and reports their original containment outcomes independently. It does not replace the gate, change its windows, certify word timing, or approve the whole transcript.

All 74 native segments match the saved record after the existing rounding and whitespace handling. All saved logical SQLite columns match, and the four transcript files inside the exported ZIP match their standalone counterparts. The original restart check also passed.

## The differing output is already native

The f12 and current runs have identical acquired-media and complete decoded-PCM hashes, all four Small model file identities, explicit/resolved/effective decoder options, and all eight recorded runtime versions. The model factory and `transcribe` call AST are unchanged. Nevertheless, native differences begin at the first segment: its end is 11 seconds in f12 and 12 seconds now, with different log probability and language probability. The world-change interval also differs before the application saves it.

The physical-duration boundary fix does not move this interior segment. These reports do not identify the cause of the native variation: CPU execution details, wheel binaries, NumPy version and random state are not fully bound. Numerical/backend variation and normal fallback sampling remain possibilities, not established explanations. No source-specific timing shift, threshold change or output repair is supported.

## Repeat acquisition failure

The first Dailymotion acquisition completed at `04:30:36.733473Z`, yielding the same complete 734.1453125-second decoded PCM as f12. The new batch child `15cd97b9651e42bcb9bbdac323170498` then failed at `04:32:23.329442Z`, after 1.47 seconds, with the retained yt-dlp error:

> [dailymotion] xbvubxi: No video formats found!

That child has only `acquisition_start` and `acquisition_failed` events, with no decode or recognition event. Both batch children have durable `error` statuses; the batch finished processing two items with two failures. Its companion YouTube request failed to extract any player response. The mixed-outcome QA assertion expected one success and one failure, so it correctly remains failed.

The same Dailymotion extractor error appears in earlier single-source runs on 745554b and 00567db. The observations therefore do not establish a batch-specific fault, rate limiting, a particular HTTP rejection, or which extraction pass failed.

One separate source-level inefficiency is supported by inspection: the app extracts and validates metadata, then `ydl.download(url)` extracts it again. Reusing the already validated video information can remove that redundant pass and bind the transfer to the checked metadata. This is a plausible generic reliability improvement, **not a demonstrated repair of this provider incident**. It was not implemented or exercised during this diagnosis.

## Evidence

- [diagnosis.json](diagnosis.json): exact comparison, event and source bindings, acquisition distinction and remaining uncertainty.
- [text-retention-diagnostic.json](text-retention-diagnostic.json): independent lexical observations with the frozen failed result retained.
- [independent-review.json](independent-review.json): separate read-only confirmation by `/root/package_verification`.
- [failure-preservation.json](failure-preservation.json): hashes of the original failure files, captured before diagnosis.
- [evidence-manifest.json](evidence-manifest.json): complete frozen inventory, excluding itself.

No provider/model requests, audio listening, output repairs, production/test edits, checker changes or Git mutations were performed. The saved source snapshots are historical evidence and are not claims about later revisions.

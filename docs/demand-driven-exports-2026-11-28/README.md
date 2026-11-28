# Demand-driven transcript downloads — 2026-11-28

Parent: b01535e67894f6cdef028397d6ca23d60a7e1bf3. Its actual PR test run 46130088473 completed
successfully on Ubuntu, Windows and macOS; the Ubuntu job log records
863 passed and 54 subtests. This is parent evidence, not validation of
the new production source.

## Change

Saved job and library downloads previously rendered every export and built a
compressed transcript ZIP even for a single TXT or subtitle request. Batch
downloads also created a per-transcript ZIP that was discarded because only
its flat component files are written to the outer archive.

The shared exporter now renders just the requested file for a single download.
A requested transcript ZIP still renders all the same members, with warnings.
Batch export renders all component files but avoids each discarded inner ZIP.
The existing full-export path for freshly completed jobs is retained. No
changes to subtitle boundaries, exported strings, enhancement availability,
database schema, archive membership or acceptance criteria are intended.

## Actual scoped local verification

Direct git ls-remote failed to resolve github.com in the local container.
The original exporter and timestamp/text rendering helper blocks were
transferred from the immutable parent and verified against connector FNV-1a
fingerprints (over Unicode code units): original 6dbce742, timestamp helpers
5cbc9520, text/subtitle helpers 845e87e9. The candidate block was tested locally
and the transferred candidate checked against e3c7638. The isolated harness
uses the actual Python renderer, compression and timing calculations. It
substitutes only the highlight validity boundary with a fixture already shaped
as an accepted highlight result; this does not test the actual selector or
application API. The added maintained tests exercise those real app paths.

60 original-vs-candidate byte-parity/absence checks passed across normal,
no-enhancement, sub-millisecond source and sub-millisecond translation
fixtures. Full ZIP members (not nondeterministic ZIP timestamps), flat members,
each individual available format and absent formats were compared. A separate
control confirmed a TXT download no longer touches an unrelated malformed
summary. No model/provider requests were made.

Synthetic 2-hour case: 3,600 two-second segments, seeded 180-character text per
segment, speaker labels, same-length translation, summary and saved warnings.
Five uninstrumented elapsed samples per mode (median); a separate tracemalloc
sample per mode. Actual local container results:

| Mode | Median elapsed | Peak traced Python allocations |
| --- | ---: | ---: |
| Previous all-formats + ZIP (even for one TXT) | 253.05 ms | 12.86 MiB |
| Candidate flat batch components | 69.06 ms | 7.29 MiB |
| Candidate single TXT | 0.87 ms | 1.48 MiB |

These are renderer-only synthetic measurements, not whole-process RSS,
real-recording inference, browser or whole-machine resource measurements.
Batch ZIP itself is still constructed in memory. No full-checkout test is
claimed; the new maintained API/ZIP tests require normal CI.

## Remaining gates

Continue exact-head CI and independent language/speaker/resource/provider
verification. Retain the documented grammar-header failure and semantic
failures. Version remains 0.3.0, PR #2 remains draft. No quality or resource
release gate has been weakened.

# Default Small + Auto Greek regression — 26 November 2026

**Both frozen Greek cases passed the actual default-route checks.** The model
and language form fields were omitted; the app selected Small and automatically
detected `el` for both recordings. This closes a narrow default-path coverage
gap after the exact-zero and decoded-duration guards. It is not fresh semantic
validation or a new translation/summary result.

## Fixed source and actual configuration

The two cases were the first Greek entries in the existing exposed FLEURS
development manifest, selected and frozen before this run:

| Case | Duration | Intended coverage |
| --- | ---: | --- |
| `fleurs-el_gr-validation-2-1528` | 6.66 s | Family camping sentence; known spelling/grammar defects |
| `fleurs-el_gr-validation-5-1515` | 6.00 s | Council, fifth/four-year values and the already damaged proper name |

The complete selected manifest SHA-256 is
`d7a54c7ec92d5bdd081a6b8fabe31c693b5d298b9ec0e75688d545a7796a8918`. Audio bytes are unchanged and identified
by their original hashes in [fixtures.json](fixtures.json). The cases had
already informed earlier reviews; they are deliberately described as regression
coverage. Reference text is used only after recognition, never in model prompts.

The measured source is published commit
[`2760679cdcd5bf2fdd0f18589e821a89d2bd9b90`](https://github.com/YellowBrokeIt/LinkScribe/commit/2760679cdcd5bf2fdd0f18589e821a89d2bd9b90).
All four recorded app/library/batch/harness file hashes match that Git object
and stayed unchanged during the run. The app SHA-256 was
`41386cfc78938c8d8a03837e02be7ed4a7a53cbc5525947a73da651304d8c671`.

The existing successful speaker-QA Python 3.12.14 environment was used with
Faster Whisper 1.2.1, CTranslate2 4.9.1 and PyAV 16.1.0, CPU, the verified cached
Small snapshot `536b0662742c02347bc0e980a01041f333bce120`, and no model override.
Hugging Face offline mode and both telemetry opt-outs were set; existing proxy
and TLS settings were inherited unchanged. All Small cache file hashes were
rechecked before launch. No new model download, reference-conditioned decoding,
other inference or response substitution was performed.

[invocation.json](invocation.json) is the unchanged preparation record, marked
not-yet-run when frozen. [execution.json](execution.json) records the subsequent
actual command, source checks, exit code and start/finish times. The original
preparation state is not retroactively rewritten.

## Observed outcome

| Check | Result |
| --- | --- |
| Actual default Small, Auto-detected Greek | 2/2 pass |
| Upload, exact SQLite segments, finite ordered timestamps | 2/2 pass |
| TXT/SRT/VTT/JSON/ZIP and ZIP-member equality | 2/2 pass |
| Uploaded media cleanup, job eviction and persistent retrieval | 2/2 pass |
| Separate-interpreter SQLite retrieval | Passed |
| Measured upload-to-export runtime | 8.712 s for 12.66 s of audio |
| Peak RSS of this QA/app process | 689,950,720 bytes (658.0 MiB) |

The process exited before the next model trial started. Memory excludes other
processes and whole-machine headroom. This is a single short regression run,
not a latency benchmark or a longer-recording capacity test.

Both hypotheses exactly match the preceding explicit-language Small VAD-off
replay. The camping example retains spelling/grammar defects and its earlier
minor-issue classification. The second still changes the proper name Μαρτελί
to Μαρτεή, a major error under the existing review; the fifth council and
four-year interval remain correct. The written-number change to `4` is harmless.
Correct language detection and stable exports do not approve those words.
See [assistant-review.json](assistant-review.json) for the separate comparison.

## Evidence and attribution

The [actual raw report](small-auto-greek-result.json) is an unchanged copy,
SHA-256 `8514a07ce502d4a8c6a072a6f329db2c2c3c8bca55af162a1e776dfec06f8676`. It retains the actual
recognizer source, runtime/model provenance, raw hypotheses, structural results
and export fingerprints. [manifest.json](manifest.json) records every copied
report/export checksum; actual exported files are under `exports/`. No audio,
SQLite database, weights or credentials are included.

FLEURS: *Few-shot Learning Evaluation of Universal Representations of Speech*,
Alexis Conneau and collaborators, Google Research, 2022. The
[google/fleurs dataset](https://huggingface.co/datasets/google/fleurs) revision
is `70bb2e84b976b7e960aa89f1c648e09c59f894dd`, under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Original acquisition,
source references and earlier reviews remain in the
[native speech evidence](../asr-2026-11-26/README.md).

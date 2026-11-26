# Local translation candidates — 26 November 2026

**No new translation default is approved by this evaluation.** Several local
models completed every request while materially changing names, roles, objects
or conditions. LinkScribe preserves the original transcript, but successful
execution and subtitle alignment do not establish faithful translation. The
existing default remains experimental.

This directory retains actual requests, outputs, model identities, source
fingerprints and failed experiments. The examples are internally authored
fictional English/Greek text. Review is by the assistant, not a blinded human
panel or an external translation benchmark. Counts below describe these cases;
they are not estimates of accuracy on general recordings.

## Candidate selection on six existing development cases

Each row uses the same six old development cases, covering transcript terms,
distinct names and roles, localized quantities, negation, publication conditions
and uncertainty. The two native model families use their documented plain-text
protocols; Qwen uses the general structured-JSON adapter. These are comparisons
of practical configured paths, not a controlled model-only benchmark.

| Path | Acceptable | Minor issue | Major error | Decision |
| --- | ---: | ---: | ---: | --- |
| TranslateGemma 4B, native prompt | 3 | 2 | 1 | Distinct Eleni/Elena roles collapse. |
| Hy-MT3 1.8B, explicit native template | 3 | 1 | 2 | Ordinary transcription/receipt concepts change. |
| Qwen3.5 4B, general JSON adapter | 2 | 2 | 2 | Receipt becomes order; Monday becomes Tuesday. |
| Marian TC-big pair, initial native prototypes | 3 | 2 | 1 | Lightweight candidate warranted integration testing; a cross-segment actor error remained. |
| Hy-MT3 7B, explicit native template, greedy | 3 | 2 | 1 | Elena's subtitle-review role becomes Eleni's. |
| Hy-MT3 7B, bounded neighboring-source context prototype | 4 | 1 | 1 | One pronoun improves; the name distinction becomes worse. Not adopted. |
| Hy-MT3 7B, publisher sampling settings with fixed seed | 2 | 2 | 2 | Actor errors remain and wording becomes less stable. Not adopted. |

The first four paths and their exact examples are reviewed in
[assistant-review.json](assistant-review.json). The three larger-model trials
are reviewed separately in [hy-mt3-7b-review.json](hy-mt3-7b-review.json), including
all source/output pairs and actual options.

The historical Qwen3/Gemma3 comparison is retained separately in the
[earlier evaluation](../evaluation-2026-11-26/README.md). A later successful
hosted execution of the default Qwen model does not overturn those semantic
findings merely because no transport or schema error occurred.

## Longer validation exposed additional failures

The twelve-case v2 corpus was frozen before the initial Marian validation.
It contains eight short cases and four longer passages. Once its outputs
informed fixes, subsequent runs became **regression comparisons**, not fresh
validation.

| Actual path on v2 | Acceptable | Minor issue | Major error | Execution failures |
| --- | ---: | ---: | ---: | ---: |
| Initial production Marian | 2 | 4 | 6 | 0 |
| TranslateGemma comparison | 4 | 2 | 6 | 0 |
| Corrected production Marian with sentence/quotation handling | 2 | 4 | 6 | 0 |

All four long passages have material errors in each of these runs. The types
of failure matter more than the equal totals:

- Initial Marian omitted substantial material and produced repeated unrelated
  text on long inputs. End-of-sequence completion did not mean all source
  content had survived.
- Sentence and quotation handling removes those catastrophic coverage and
  repetition failures in the observed regression. It retains all paragraphs,
  quoted content and late return/publication arrangements. Remaining defects
  include an early fabric delivery becoming premature childbirth, reversing
  which measurement came from which instrument, and changing actor references.
- TranslateGemma also preserves more content than initial Marian, but still
  changes return objects, consent wording, actions and plant/transcript terms.

Read the actual outputs in
[initial Marian validation](marian-fresh-validation.json),
[TranslateGemma regression](translategemma-v2-regression.json), and
[corrected Marian production regression](marian-sentences-production-regression.json).
The corrected-path assessment is in
[marian-sentences-production-review.json](marian-sentences-production-review.json).
All twelve cases completed structurally, preserving segment metadata and
the source. Its observed elapsed time was 21.604 seconds; this is a recorded run,
not a controlled performance comparison against another model or machine.

The separate four-case
[v3 corpus](../../tests/fixtures/translation_quality_validation_v3.json) remains
**unexposed to inference** at this checkpoint. No candidate was promoted solely
to produce a passing result on it. Its SHA-256 is
`e6917b37e1bc738086bdb4e7b8248c22f29002964eaa33824beb6ca3a4cc3d14`.

## Changes that were actually integrated

The app routes summary and translation models independently. Failure of one
optional enhancement leaves the original transcript and other completed work
available. Translation validates the complete input before inference, bounds
requests, preserves original segment times and metadata, and rejects empty,
incomplete or over-limit output.

Dedicated adapters send each model its native prompt instead of imposing the
general JSON grammar on a model trained for plain translation. The Hy-MT3 1.8B
import needed an explicit template after the tested runtime produced an
incompatible automatic import. The 7B model uses a different native protocol;
its checked-in Modelfile follows its own pinned first-party tokenizer template
and both documented end tokens. Neither adapter is a quality endorsement.

The experimental Marian path uses pinned original public model archives,
verified hashes, local int8 conversion, bounded token inputs and explicit
completion checks. Sentence/quotation processing preserves every source
character through fragmentation and translates quoted instructions as content.
This engineering repair does not repair the model's remaining word-sense or
actor errors after generation.

No reference translation, case-specific name substitution or expected answer
was inserted into the decoder input or applied to its output.

## Experiments that were not adopted

The Marian source-context/forced-target-prefix trial produced an empty second
translation in the Anna case. Its earlier setup attempt used an unsupported
native API option and failed before inference. Both are disclosed in the
retained [context evidence](marian-context-development.json); no unsupported
option was silently treated as successful execution.

The 7B neighboring-context trial used at most 800 UTF-8 bytes from each adjacent
original fragment, with the publisher's background-information prompt. It
corrected one isolated pronoun but worsened Eleni/Elena. Its
[exact development patch](hy-mt3-context-development.patch) identifies the
isolated changes against the report's source commit. It is not the main app's
translation implementation.

The final 7B sampling trial used temperature 0.7, top-p 0.6, top-k 20 and repeat
penalty 1.05, plus a fixed seed of 0. The app's 8192-token context and 2048-token
output bound remained in place. This tests the publisher's sampling advice
with a reproducibility constraint; it is not a random-seed search. The
[sampling patch](hy-mt3-author-sampling-development.patch) and raw report retain
the exact settings. Actor errors remained, so these settings were not adopted.

## Model identity and resource limits

The 7B candidate is the publisher's public Q4_K_M GGUF from
[tencent/Hy-MT3-7B-GGUF](https://huggingface.co/tencent/Hy-MT3-7B-GGUF), at revision
`aee8478cafe9a14a4f6e074614a5688e1242c0f8`. All 5,145,531,232 downloaded bytes were
hashed and matched the first-party LFS SHA-256:
`e08a5098918c6615e1a84fbe714637237bfdc832e17761bdde4bb65878eb17c9`.
The explicit local alias has model digest
`5cd558f1a3f813d2a75755e3b51daadabec1252e9c4b6fde3b836f58fe85aa61`.

[hy-mt3-7b-runtime.json](hy-mt3-7b-runtime.json) records the base tokenizer
revision, native special tokens, template, actual parameters and verification.
The three trials took 92.180, 120.460 and 95.134 seconds respectively. These
observations do not establish that the complete app, speech models and language
model fit in a 7.3 GiB machine. File size is not peak runtime memory.

Model caches and original weights are not committed here. Reproducible unused
QA caches were removed to make room while keeping the actual outputs and
identities. Public model licensing/setup details are linked from the main
[README](../../README.md); the selected model's license still applies to its
use.

## Reproducing a report

With the selected local model installed and the application dependencies ready:

```bash
LINKSCRIBE_TRANSLATION_MODEL=linkscribe-hy-mt3:7b \
LINKSCRIBE_OLLAMA_THREADS=4 PYTHONPATH=. \
./.venv/bin/python tests/evaluate_translation_quality.py \
  --split development --output /tmp/linkscribe-translation-development.json
```

The 7B alias must first be created from
[models/hy-mt3-7b.Modelfile](../../models/hy-mt3-7b.Modelfile). Use the report's
recorded source revision and model identity for historical reproduction; later
main-branch source changes can alter behavior. The isolated experiments also
require their retained patch. A zero process exit code means the requested
execution/structure checks completed, not that translation meaning was
approved.

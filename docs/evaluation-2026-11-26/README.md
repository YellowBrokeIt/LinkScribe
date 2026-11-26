# Bilingual evaluation and translation reliability — 26 November 2026

The evaluation milestone is complete. A frozen, internally authored corpus now exercises English–Greek terminology, names, amounts, negation, conditions, quoted instructions, and long-passage continuity. The original implementation failed both long cases before returning an accepted translation. Smaller source batches and a constrained response schema fix those processing failures: the final implementation completes all 12 cases with both tested models.

**Semantic translation quality is still not approved.** Assistant review found material meaning errors in 8 of the 12 Qwen cases and 3 of the 12 Gemma cases. These are observations on a small diagnostic corpus, not estimated error rates for arbitrary transcripts. The default model and original translation prompt remain unchanged; the candidate remains experimental.

## Retained changes

- Add the 12-case corpus, production-path evaluator, and regression tests for evidence collection, interruption handling, source preservation, and the limits of lexical indicators.
- Reduce serialized source batches from 2,800 to 1,600 UTF-8 bytes to leave output headroom for Greek. This is empirical headroom, not an exact tokenizer-based guarantee.
- Ask Ollama for a JSON object containing the exact number of translation strings. Existing response validation, truncation rejection, and preservation of the original transcript remain in place.
- Add optional `LINKSCRIBE_OLLAMA_THREADS` configuration. Unset/empty keeps automatic selection; integers 1–32 set the actual request's thread limit. These controlled runs use four threads.
- Preserve evaluation JSON alongside real-model integration output in GitHub Actions, including available evidence from failed runs. Label the interface's translation option experimental.

The final automated suite passed **272 tests, with zero failures, errors, or skips**, on Python 3.12.14. Compilation, dependency consistency, shell syntax, workflow parsing, and whitespace checks also passed. [Automated evidence](automated-tests.json) records the tested source fingerprints. These tests mostly use synthetic inference responses; the reports below separately record actual local inference.

## Final model comparison

Both final runs use identical application/evaluator/corpus fingerprints and matching request bodies after removing only the requested model. Settings are temperature 0, context 8,192, output limit 2,048, and four CPU threads, using Ollama 0.40.12. The comparison uses the original production prompt, the constrained output schema, and 1,600-byte source batches.

| Observed result | Default `qwen3:4b` | Comparison `gemma3:4b` |
| --- | ---: | ---: |
| Completed corpus cases | 12 / 12 | 12 / 12 |
| Processing / structural failures | 0 | 0 |
| Automatic indicator pass | 6 | 9 |
| Automatic review flags | 6 | 3 |
| Assistant review: acceptable | 3 | 5 |
| Assistant review: minor issue | 1 | 4 |
| Assistant review: major error | 8 | 3 |

The semantic classifications are assistant judgments, with independent assistant review and exact examples retained. They are not human approval. Every automatic report deliberately retains `semantic_quality: unreviewed`, regardless of its indicator results. The completed separate review retains `semantic_quality_approved: false`.

Read the [complete source/reference/output comparison](outputs-comparison.md), the [structured assistant review](assistant-review.json), or the raw final reports: [Qwen](qwen3-final.json) and [Gemma](gemma3-comparison.json). Each raw report identifies the exact model digest, runtime, requests, responses, code fingerprints, timestamps, and settings. These were CPU runs in the assistant's environment, not tests on the user's computer or a controlled hardware performance benchmark.

### Meaning errors that automatic success can miss

- Qwen changes “original recording” into `το αρχικό αυτοκινητάκι` (“the original little car”) and transcription/translation into `μετάλλαξη` (“mutation”).
- Qwen changes `5,000 sats` into `5,00.000 sats`. A separate approval condition replaces Giannis with Antonios, despite that case passing its lexical indicators.
- In the long Qwen translation, recorded interviews become registered letters, a Tuesday event becomes Wednesday, and the final yellow box becomes red. The output reaches the end and retains numerical anchors, yet fails meaning.
- Gemma preserves many of the names and conditions that Qwen mishandles, but “The receipt shows…” becomes `Λαμβάνει δεσμευτική τιμολόγηση…` (“receives binding pricing”).
- Gemma's long Greek output uses `δεν τα διατήρησε` (“did not preserve”) for “did not erase,” and `συγκάλυπταν` (“would cover up”) for “would compare.” Its long English output changes “even if the presentation were postponed” into “even though the presentation was postponed,” asserting an event the source did not establish.

Gemma's `12,50€` and `5.000` are valid Greek localization of the input amounts. Its “November 6th” also preserves the day. Literal-number flags on these forms are not proof of wrong values; the semantic review distinguishes them from the actual errors above.

## Why the processing fixes were needed

The initial long English→Greek request generated exactly 2,048 tokens and returned `done_reason: length` after approximately 225 seconds. Its prompt used only 649 tokens: this was an output-budget failure, not exhaustion of the input context. The other long case returned five strings when one source fragment had been requested. Production correctly rejected both instead of saving an apparently successful partial translation.

With the retained fixes, English→Greek uses two balanced source fragments, and Greek→English uses three. The final Qwen English→Greek requests finish normally at 1,490 and 1,454 generated tokens. Both models complete every long-case request normally, preserve the source segment layout and metadata, and return reassembled output. Long-case semantic inspection remains necessary because smaller fragments can lose context across their boundaries.

The long cases informed these engineering changes, so their later runs are **regression verification after observed failures**, rather than untouched quality holdouts.

## Rejected prompt experiments

Two development-only prompt experiments were tested and rejected before the model comparison. No case-specific names, amounts, or expected sentence answers were added to the prompts, and references were never sent to either model.

| Development experiment | Processing result | Assistant assessment / decision |
| --- | --- | --- |
| Original prompt | 6 completed | 2 acceptable, 1 minor issue, 3 major errors; establishes the development baseline. |
| Longer fidelity instructions and a small Greek domain glossary | 6 rejected responses | The model returned objects where strings were required; no accepted translations. Rejected. |
| Same revised prompt plus constrained output schema | 6 completed | 2 acceptable, 4 major errors. Eleni and Elena were merged into one identity; amounts and conditions remained wrong. Rejected. |

Automatic indicator passes rose from three to four in the second experiment even though semantic results worsened. The revised prompt is therefore **not shipped**. The schema was subsequently retained with the original prompt to address the independently observed response-shape failure.

Exact evidence: [original development run](baseline-development.json), [prompt-only run](prompt-only-development.json), [prompt-plus-schema run](schema-prompt-development.json), [initial holdout/long run](baseline-holdout-long.json), and the [rejected experimental patch](rejected-prompt-schema.patch.json). The patch documents the experimental combination; it is not a recommended patch to apply to the final candidate.

## Corpus, provenance, and interpretation

- Twelve unique synthetic cases: six development, four separate short holdouts, and two long passages, balanced six per direction.
- The corpus and references were fixed before these model outputs were inspected. They are internally authored diagnostic fixtures, not a blinded or external benchmark.
- The six saved runs contain 48 case evaluations, including repeated development experiments. They do not represent 48 independent test examples.
- All model text requests go through the production loopback-only Ollama transport. The evaluator starts no services and downloads no models. Only owned synthetic text is used here.
- Evidence checkpoints are atomic before and after each request. `complete` concerns the requested selection; `corpus_complete` requires all 12 cases. Interrupted runs cannot silently become successful evidence.
- The original source is retained on any failed translation. Raw rejected responses remain evidence, not accepted translations.

The published starting point was [`ab36367`](https://github.com/YellowBrokeIt/LinkScribe/commit/ab363679a0e820ac3f127bc565d48d144a05b49b). The evaluator checkpoint is [`6880742`](https://github.com/YellowBrokeIt/LinkScribe/commit/68807427ce2b61898ba607f5a896b04805b78469); its tree is identical to local checkpoint `1b940c4`, recorded in the first reports. The final inference code is [`f10cf00`](https://github.com/YellowBrokeIt/LinkScribe/commit/f10cf000963ee286d2afe10ac859acfb6d4708fe). Source fingerprints bind both final model reports to that code even where a report was recorded before its publication commit was created. Documentation and evidence are added afterward without changing the evaluated implementation.

The raw reports' inference identities are authoritative. A model tag can change over time, so compare its digest as well as its displayed name before interpreting a later rerun as the same model.

## Reproduce

With the selected model installed and a local Ollama daemon running, run from the repository root:

```bash
LINKSCRIBE_OLLAMA_THREADS=4 PYTHONPATH=. .venv/bin/python \
  tests/evaluate_translation_quality.py --output /tmp/qwen3-evaluation.json

LINKSCRIBE_OLLAMA_MODEL=gemma3:4b LINKSCRIBE_OLLAMA_THREADS=4 PYTHONPATH=. \
  .venv/bin/python tests/evaluate_translation_quality.py \
  --output /tmp/gemma3-evaluation.json
```

Use `--split development` or repeat `--case CASE_ID` for a selected run. Keep baseline and candidate output paths separate. Normal exit code zero establishes completed execution and structure only; `--fail-on-review-flags` additionally fails on lexical flags, including legitimate alternative spellings or number formats. Neither exit mode certifies semantic quality.

GitHub Actions repeats the full default-model corpus and retains its run-specific JSON reports for 30 days. Check the Actions runs for the exact PR head before treating hosted results as current; the measurements above are the saved local runs.

## Release decision and next gate

Keep translation experimental and the PR in draft. Gemma is the stronger translation candidate on these observed cases, but its three material meaning failures do not justify automatic default replacement. The shared model setting also controls summaries, which this model-only comparison did not evaluate for Gemma.

The next language milestone is a translation-specific model or configuration that preserves actors, quantities, negation, and conditions on a new frozen validation set, followed by the complete storage/export and summary checks for any changed default. The present corpus remains useful as regression evidence. Full live-provider coverage and gated speaker-model inference remain separate unfinished release gates.

Implementation references: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [the tested Gemma model tag](https://ollama.com/library/gemma3:4b), and [Google's Gemma 3 model card](https://gemma.ai/models/gemma-3/). Model documentation describes capabilities; it does not replace the observed evaluation results.

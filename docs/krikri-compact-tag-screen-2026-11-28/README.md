# Compact empty-tag translation screen: rejected

This is the completed, separately frozen six-case development experiment for
compact opaque source-name markers such as `<x0/>`. All six requests completed
once, and all structural and resource checks passed. Independent meaning review
found **2 acceptable outputs, 3 minor errors and 1 major error**. The candidate
is rejected; this bundle does not authorize broader validation or integration.

The major error survives exact name restoration. In the Greek negation case,
the source explicitly supplies `η Άννα` and continues that subject. The output
restores `Άννα` exactly, then says `he` in both subsequent propositions. The
negation scopes, yesterday/today distinction, possible sale of one book and
undecided status remain correct. This is an actor/anaphora fidelity failure,
not a reversal of polarity. Keeping name spelling intact did not keep every
statement about that person intact.

## Unchanged review criteria and complete results

All six are the original, already-exposed development cases. The corpus remains
SHA256 `48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce`.
The pre-output criterion binding remains
`cd8c9bd75d0e5eaca23d9ac93a728f13d2ccf4490f57af1f1b43d5ed19047ab1`.
Exact source-script personal names were already allowed; ordinary prose,
relationships and facts still require faithful translation. No criterion was
changed after the outputs.

| Original case | Independent judgment | Preserved facts and remaining defect |
| --- | --- | --- |
| Transcript terminology | Acceptable | Saved text versus unsaved original recording, completed 12-minute transcription and translation not yet started all survive. Maria is exact. |
| People and roles | Minor error | All three distinct names, intended and excluded recipients, translator/recorder/subtitle-checker roles survive. `The Νίκος` and `The Ελένη` are unnatural English articles, contrary to the existing case criterion. |
| Amounts | Acceptable | 12.50 euros, 2 items, 5,000 sats versus rejected 500, receipt versus separate transfer, and distinct units survive. `5.000` is valid localization. |
| Negation scope | Major error | Logical scopes, time and uncertainty survive; both continuing references to explicitly feminine Άννα become `he`. |
| Conditional publication | Minor error | Anna/Giannis roles, only-if approval, nonresponse condition, Friday and Monday survive. `η Giannis` has incorrect Greek agreement; the source has no explicit gendered pronoun, and the named roles remain intact. |
| Uncertain question | Minor error | Both alternatives, quoted question, missing answer and insufficient title evidence survive. `Person Μαρία` adds an unnecessary label. |

The full criterion-by-criterion judgments, exact source and output strings,
raw-response hashes and distinctions between minor and material errors are in
`independent-output-review.json`. Its SHA256 is
`ef33bda5ad465866452786d1cbc17a26caecb68c166f4a6c0ca91b1de2f9bfd4`.
The independent protocol audit and its original script are archived unchanged.

## Fixed candidate and actual execution

The model remains the official Krikri Q4_K_M payload, SHA256
`e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f`,
using verified Ollama 0.40.12, its selected native template and existing stops.
Requests keep temperature 0, non-thinking operation, four CPU threads, context
4096, maximum output 2048 and a 240-second request timeout. Initialization,
case and total caps remain 180, 600 and 1800 seconds; the external sampled RSS
limit is 6144 MiB. No new model download or detector inference occurred.

Preparation reused the reviewed source-derived spans and frozen boundary
normalizer. Each mention became a unique request-local empty tag. Exact
same-entry occurrence checks, source/offset/map hashes, strict response JSON,
metadata preservation and the unchanged post-restoration production translation
guard all remained active. Each raw native response was saved before checks.
All **13 name mentions** were restored exactly, with no output repair or retry.

Actual complete prompt counts were **203, 222, 217, 206, 206 and 205**. Native
token vectors matched the frozen complete-message estimates; no source text
was cropped. Generated counts were **60, 66, 68, 56, 62 and 57**, all normal
stops with empty reasoning. Each case acknowledged model unloading and an empty
resident-model list. All six were run because none triggered the operational
first-failure stop; later semantic review is a separate gate.

The generation phase took **139.865458 seconds**, with **1087 complete samples**,
peak summed **RSS 5548.7 MiB / PSS 5539.8 MiB**, no limit breach, and successful
owned worker/daemon/group cleanup. It exited 0. The free disk measurement after
the stage was **1,681,690,624 bytes**. Zero-generation preparation took
21.784206 seconds, 207 samples and peak RSS 5492.1 MiB / PSS 5483.0 MiB.
All samples are retained. These sequential samples may miss transient peaks and
cover only this isolated owned process group, not the whole application or OS.

The execution report's original `semantic_quality: unreviewed` field remains
untouched. `results-summary.json` and the separately archived independent review
record the completed semantic rejection. Mechanical success is not reclassified
as a meaning pass.

## Evidence and limits

The plan is SHA256
`e06f585f49b3a0903aa317eb725775a9f6e9b390c4c826d66c61304fbb8a4d5a`;
the final pre-generation freeze is
`a812e7cbd919b2883b539690041f101d7af99465b625d3bb5e202863f2c8e9cc`.
All 79 frozen input/setup/reviewer bindings were rechecked unchanged after the
run. Seven prior evidence manifests and their bound files were also rechecked.
The failed digest-marker predecessor and compact preparation's initial closing
tag scanner defect remain preserved, with neither rejection regraded.

The detector's missed/oversized-span risk, lexical article-normalizer ambiguity,
inflection, within-entry actor swaps, and request-local marker identity limits
remain. No fresh validation, long passages, summary, whole-app resource check or
production change followed. Any visible-name paired-tag preparation is a
separate candidate and cannot alter this completed result.

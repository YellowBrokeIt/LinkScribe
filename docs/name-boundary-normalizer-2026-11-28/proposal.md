# Source-only Greek article boundary proposal

## Decision and scope

This is a separate, finite development follow-up to the rejected raw GLiNER
screen. The raw screen remains rejected: five of six cases have entirely correct
PERSON spans; twelve of thirteen mentions have exact boundaries. The only
observed error is an ordinary leading article included with a personal name.
There were no wholly missed people or disjoint non-person predictions in that
small screen. Its sources, raw predictions, confidence scores, annotations and
review are immutable.

The candidate proposes a smaller protected span using only the actual source,
the detector's original span and the declared source language. It neither
reruns the detector nor translates, masks or rewrites anything. One replay of
the six existing source/prediction pairs will assess whether this generic rule
corrects that development boundary error without changing the other spans.
Independent review of this plan and the counterexamples precedes the replay.

## Fixed algorithm

The implementation is `boundary_normalizer.py`. It first validates the entire
raw batch: exact native keys, finite original score in the fixed detector's
0.5–1 interval, PERSON label, integer half-open codepoint offsets, exact source
slice, full grapheme boundaries, no overlap, and containment within one original
source segment. Invalid input rejects the whole batch, with no partial output.
Full original segment metadata is retained unchanged.

For declared Greek source only, inspect the first complete whitespace-delimited
token of a multi-token raw span. Compare it, using NFC and casefold **only**, to
the following closed grammatical inventory:

`ο η το του της τον την τη οι τα των τους τις`

These are the distinct Modern Greek definite-article forms, including the
documented τη/την alternative. Both the inventory and candidate token undergo
the same comparison normalization; no accents, punctuation, confusables or name
letters are stripped. The inventory is grammatical and contains no personal
names or fixture-specific replacements. Its primary sources are the official
[Greek school grammar](https://ebooks.edu.gr/ebooks/v/html/8547/2009/Grammatiki_D-EDimotikou_html-apli/index_C5d.html)
and the [Centre for the Greek Language article entry](https://www.greek-language.gr/digitalResources/modern_greek/tools/lexica/glossology_edu/iframe.html?heading=4&id=110).

A proposal moves only the span's start past that one exact token and its
following horizontal whitespace (tab or Unicode space separator). It requires
the remaining source to begin with a letter, remain nonempty, and stay within
the same original segment. Its end stays identical. The proposed text must be
the exact new source slice, and the removed prefix plus the new text must
reconstruct the complete raw span. The removed article and whitespace remain
ordinary **unmasked original source text**. The original raw record and its
confidence score remain available; no new confidence score is invented for
the proposal.

Raw single-token spans stay unchanged. A multi-token raw span may legitimately
produce a **single-token proposed name**. This distinction is fixed before
replay. English and other declared non-Greek sources are unchanged.

The rule refuses to change outer-whitespace spans, starts inside a word or an
apostrophe/hyphen name prefix, line-breaking separators, a punctuation-led
remainder, or consecutive article-like leading tokens. Attached punctuation
prevents an exact first-token match; dotted initials and article substrings are
not article matches. There is no repeated stripping or punctuation repair.
Inflections, initials and internal hyphens/apostrophes in the retained suffix
are left exactly as written. A span crossing two segments is invalid, even if
its text happens to reconstruct across the joining newline.

## What this cannot decide

An exact lexical match cannot prove that a token is grammatical. A genuine
name component can have an article's spelling; an undotted initial can be
indistinguishable from an article. A raw span can also overextend into ordinary
descriptive prose after its article. For those inputs, this same algorithm can
propose the wrong boundary. The predeclared controls include all three types
of counterexample and record the limitation even when mechanical behavior
matches the specification. They do not redefine a wrong name boundary as
acceptable.

Every returned span is therefore a development **proposal requiring independent
source review**, including unchanged spans. The output explicitly says that
automatic name safety is not certified. The candidate does not resolve missed
entities, actor swaps, inflected-name grammar in translation, or references
split between segments. It cannot turn a missing person prediction into a
prediction or determine that all ordinary prose will be translated. A passing
six-case replay would support only this bounded development improvement; it
would not approve unattended protection or translation in the app.

## Frozen inputs, checks and next action

`plan.json` binds the original source-only snapshot, all six complete raw
reports, the immutable raw-screen manifest/review, the unchanged pre-output
annotation digest, this proposal, code and generic controls. The replay worker
receives only source segments, raw entities and the source language. It never
opens annotations, reference answers, translation criteria or a name lexicon.
The independent reviewer alone compares resulting spans with the existing
pre-output annotations after the replay; the raw baseline is not regraded.

`edge-cases.json` declares mechanical outcomes, invalid-input failures and
semantic ambiguity counterexamples. `check_controls.py` runs only these generic
examples. `replay.py` reads the frozen source-only snapshot and the six original
complete raw reports, verifies every bound input, and calls the normalizer once
per case. It writes new per-case proposals and an execution record in this
directory without modifying the old evidence. Source/prediction inputs are
rehashed afterward. It creates no placeholders, substitutions or translations.

Both scripts use the existing isolated Python and its already installed
`regex`; no dependency, model or tokenizer download/load is needed. A fixed
30-second wall limit, 10-second CPU limit, four-CPU affinity and 512 MiB address
space limit bound each offline process. A single replay is permitted after
independent protocol review; a failure is retained, not retried or tuned in
place. No v2/v3 expansion, model inference or production change belongs to this
stage. A separate later decision would be needed for protected translation.

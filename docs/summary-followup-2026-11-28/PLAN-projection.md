# Offline canonical-paragraph projection

This experiment uses **retained actual outputs** and makes no model request. It
asks a narrower question than the repair candidate: can deriving all points from
the unchanged paragraph remove independently generated inconsistencies without
losing important facts that previously appeared only in the points?

The transformation preserves the paragraph and chapters exactly. It splits only
at punctuation boundaries, keeps decimal amounts intact, conservatively protects
initials and common English/Greek abbreviations, and merges adjacent complete
spans until there are at most eight points. Every point must fit the existing
900-character bound; an oversized span is rejected intact, never clipped. The
normalized concatenation of all points must equal the complete paragraph. This
is a small heuristic for punctuated text, not universal sentence analysis.

Mechanical preservation proves that the projection adds no independent version
of a fact. It says nothing about whether the paragraph is correct or complete.
The separate review must compare **the paragraph alone** with every required
fact previously carried by original points. Losing a condition, permission,
actor, assigned action or late correction disqualifies a global replacement.

Use the two fresh production baselines in `development-pair-v1.json`, the two
other short development outputs in the published bounded regression, and the
published eight-point English long result as an explicit negative comparator.
These are exposed development/regression outputs from different recorded
contracts; they are not new held-out evidence or a new live pipeline timing.
No unused frozen validation source is opened.

Meaningful non-model checks cover amounts inside sentences, English titles and
initials, Greek room initials, complete coverage when more than eight sentences
must be merged, and intact rejection of an oversized indivisible span. The
projection is proposed for production only if the separate source review
supports its stated scope; passing reconstruction checks alone is insufficient.

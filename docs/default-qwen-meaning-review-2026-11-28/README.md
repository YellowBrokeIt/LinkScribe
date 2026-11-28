# Actual default-model translation meaning review

The complete, already-published `7a53991` Qwen3:4b translation run contains
**nine major meaning errors and three acceptable cases** under its unchanged
source-specific criteria and fidelity rubric. This independent assistant review
is separate from the original automatic result of five passes and seven review
flags. The raw report remains unchanged.

[The full review](independent-semantic-review.json) retains every source,
actual translation, original criterion judgment, preserved fact and relevant
raw-output identity. The three acceptable cases are negation scope, the uncertain
question, and lending direction. The lending case explicitly allows Peter/Petros
and Sophia/Sofia; those variants are not penalized. Valid decimal/thousands
localization is likewise distinguished from errors.

Failures include corrupted transcription/translation terminology, Eleni shortened
to Ele, a changed approver and lost approval relation, wrong objects/colors,
misrendered quoted content and missing propositions in both long passages. Two
of the five automatic-pass cases have major errors. Exact counts, names appearing
somewhere, valid JSON and normal model completion do not establish fidelity.

The [integrity audit](published-output-integrity-audit.json) verifies the four
published implementation/corpus hashes, all nineteen actual normal-stop calls,
fifteen unloads, complete source-fragment reconstruction and exact assembly of
the raw output into the saved translations. The long omissions occur despite
the complete original source being present in the recorded model requests.
[The audit program](audit_published_report.py) is retained unchanged; it inspects
the published report and does not perform inference.

## Bounded connection to the newer build

The [current-output addendum](current-6de3fad-exact-output-addendum.json) verifies
that five complete translations, their original sources and their criteria are
identical in the completed `6de3fad` hosted run. It independently binds the new
report and its four implementation/corpus hashes. The unchanged people/roles and
conditional-publication cases therefore establish **at least two major errors
in the current run**; the other three compared cases remain acceptable.

Seven newer outputs differ and are explicitly **not regraded** here. The historical
nine-of-twelve count is not applied to the entire newer run. Neither run approves
the default model for v1.0 translation. No model call, source edit, output repair,
new validation exposure or production-default change was made for this review.

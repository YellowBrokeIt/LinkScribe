# Summary action preservation: source-only feasibility decision

**Decision: the reviewed evidence does not support another abstractive summary run or a new production summary mechanism at this point.** One materially different mechanism is technically possible: return complete verbatim source passages for verification, approval and assigned-action statements, instead of rewriting those statements. Its safe component already exists in source highlights. Adding it under a new name would not establish a complete AI summary, and selecting every required action remains the unresolved part.

This is a bounded source/code assessment. No model, native runtime, tokenizer, detector, provider or new validation input was used. The original English and Greek summary cases and criteria remain unchanged. The failed Krikri stages remain rejected; Greek generation remains unrun.

## What the earlier experiments actually establish

| Retained mechanism | Useful result | Remaining failure relevant to actions |
| --- | --- | --- |
| One canonical statement list with exact source IDs, verbatim evidence and literal quantity checks | Prevented independent paragraph/point amount disagreement in that candidate. | A statement invented Beatrice's ownership even though its own exact evidence said Rowan owned the recorder. The assigned return was omitted despite appearing in the cited source. Correct citations did not bind the meaning of generated statements. |
| Source-first revision given the complete original source and an explicitly untrusted draft | Corrected the invented owner. | Removed the room-confirmation assignment and quotation-with-speaker check, and still omitted the recorder return. The specific quotation check was present in the first draft and disappeared during repair. |
| Deterministic paragraph-to-points projection | Preserved its whole input paragraph and eliminated one separate malformed amount. | Discarded information that existed only in the old points, including written approval, named reminder recipients and concrete access/publication checks. A consistent representation can consistently omit required information. |
| Current Krikri schema-only prompt correction | Replaced the copied placeholder with a real factual paragraph while retaining the documented budgets, roles, permission categories and pending state. | The required check of each quotation with its speaker still became generic speaker-permission verification, and no point restored the specific action. Root's independent English review rejects it. |

The exact source and result records are bound in `evidence-bindings.json`: prior candidates and reviews are E1–E6; original and corrected Krikri decisions are E7–E10. These are previously exposed development results, not fresh validation.

The existing direct summary path already receives the complete short source and grounding instructions about actors, assigned actions, permission scope, conditions and plans. Repeating those instructions, asking for another source-first repair, or attaching another exact citation would repeat a failure mode already tested. A lexical check for a name, number or word such as “permission” cannot distinguish the required specific check from a broader substitute.

## The one different mechanism considered

An **extractive action appendix** would return only source passage IDs. The application would render the corresponding complete original passages in source order, with their actual source timestamps. It would not generate action text, actor fields, approval status, headings asserting an obligation, or reconstructed conditions. No quote could be shortened to remove a condition or negation. The independent reviewer would still compare selected passages with the full source.

This differs from the failed citation candidate in an important mechanical respect: the displayed action would be the original passage itself, rather than a new claim accompanied by a correct quotation. It also differs from paragraph projection: the material would come from the source, not an already lossy summary. If the relevant complete passage is selected, the exact action, object, recipient and locally stated condition survive without a paraphrase step.

The remaining problem is selection and context. A model selecting IDs can omit a required action. A keyword selector cannot prove that an action is required rather than completed, rejected, conditional or superseded. A condition or correction may occur in a different passage. Adding generated actor/action slots or a model-produced completeness verdict would introduce another semantic transformation rather than resolve this problem. Always retaining all source passages avoids selection omissions but gives the full transcript, not useful condensation.

## Why this is not a supported next summary fix

`source_highlights.py` (E13) already returns exact whole-segment passages, groups local continuations/corrections, ranks English and Greek action/condition/negation cues, preserves source timestamps and validates exact source binding. It explicitly disclaims complete coverage. The proposed appendix would largely duplicate that existing feature unless a new selector demonstrated a useful coverage improvement under independent criteria.

For the two original summary sources, the existing short-source rule is already decisive at the code level: their four segments contain respectively **926** and **1,587** UTF-8 bytes when joined with newlines, both below the existing **1,800-byte** whole-source threshold. Subject to the existing ordinary input validation, that branch retains each entire short transcript. This is a static inference from the bound source bytes and code; the selector was not executed during this assessment. Reusing those full excerpts to pass the short-summary content checklist would not demonstrate condensation or a better abstractive summary.

There is therefore no useful new summary execution proposal from this investigation. Keep the existing source excerpts available under their current accurate label. Keep generated summaries separate and subject to the unchanged semantic quality gate. This decision is limited to the reviewed local mechanism and evidence; it is not a claim that faithful summarization is impossible or that no future method could work.

## Narrow placeholder bug fix remains available

The sealed schema-prompt stage retains `potential-production-prompt-only.patch` (E11), SHA256 `bb8ad15aabf234a0d256a839e2dfc3191258ecfab7bd7f995a80ad452cddaa40`. It changes only three generic prompt endings: direct/final calls request JSON matching the supplied schema, and excerpt notes name the required string fields without example values. The companion record (E12) binds the existing production source and verifies that context, schema, grounding instructions, point count, chunking, validation and unload logic are untouched.

The observed English paragraph improvement supports treating copied example filler as a distinct prompt defect. It does **not** establish semantic acceptance, approve Krikri, validate the untouched default model or authorize any model/default change. Root can review that already prepared narrow patch as a separate production decision. This assessment neither applies it nor changes any frozen record.

## Resulting scope

- No additional summary candidate, prompt search, source-specific hint, automatic repair or model call is proposed.
- No previously rejected stage is regraded, and no unused validation source is opened.
- The source-only spelling-context translation runtime was reviewed separately; its progress does not change this summary decision.
- All cited prior bytes are hashed in the accompanying record. No production source was modified.

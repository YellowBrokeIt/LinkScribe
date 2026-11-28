# Actual default Qwen translation review: d62df26

**Result: 9 major errors, 3 acceptable cases, 0 minor-only cases; all 12 reviewed.**

This is the completed original v1 corpus, already exposed. No unused validation corpus, new inference or model download was used. Both long passages were read in full.

GitHub run 46121980939, job 140908506262, artifact 15254243683; exact head `d62df26c870f175f7454fe0c3900d97891c8bff5`. Published ZIP SHA256 `5840638f9e0e03f898f38b6702dce44f51425b16bd4ca1ca8061dd084fbd07b4` verified after connector download.

The report records Ollama 0.40.12 with qwen3:4b, model digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. Actual request records retain context8192, output2048, temperature0, four threads and think:false. This review verifies the report and source bindings; the model payload is not in the artifact and was not downloaded for this review.

| Case | Independent meaning |
|---|---|
| dev-en-el-transcript-terminology | major_error |
| dev-el-en-people-and-roles | major_error |
| dev-en-el-bitcoin-amounts | major_error |
| dev-el-en-negation-scope | acceptable |
| dev-en-el-conditional-publication | major_error |
| dev-el-en-uncertain-question | acceptable |
| holdout-en-el-quoted-instructions | major_error |
| holdout-el-en-lending-direction | acceptable |
| holdout-en-el-objects-and-times | major_error |
| holdout-el-en-literal-example | major_error |
| long-en-el-community-archive | major_error |
| long-el-en-library-meeting | major_error |

Automatic counts were five pass and seven review. Conditional publication and quoted instructions both received automatic pass but contain material meaning errors. Explicit Peter/Petros and Sofia/Sophia variants are accepted. Valid number/date localization is not penalized.

The integrity audit verifies all four source hashes against the exact local Git commit, all original case contents/criteria, full input-fragment reconstruction, exact raw-output assembly, timestamps/speakers, strict JSON request schemas,19 normal final responses and15 acknowledged unloads. The long cases have multiple unloads because the unchanged production residency bound allows at most two responses between unloads.

A reviewer-only initial audit mistakenly assumed one unload per original case. Its unmodified source and explanation are retained under `reviewer-preparation/`; the corrected audit checks the actual committed two-response policy. No production code, evidence or semantic criterion changed.

Separate `integration.json` reports its smoke result PASS and is retained raw. Its two simple summaries are not included in the twelve translation classifications and provide no summary-model approval. No standalone process-memory series or native full-request context preflight is inferred from this artifact.

Read `independent-semantic-review.json` for every original source, full actual output, original criterion, judgment, preserved proposition and exact raw-response/output hash. All retrieved artifact bytes remain unchanged.

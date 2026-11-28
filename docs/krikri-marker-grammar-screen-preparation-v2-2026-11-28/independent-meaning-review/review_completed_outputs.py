"""Read/hash completed evidence; no candidate imports, execution or output repair."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = Path("/workspace/scratch/94360995dd61/LinkScribe")
STAGE = ROOT / "docs/krikri-marker-grammar-screen-preparation-v2-2026-11-28"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


# These are the reviewer's complete-meaning judgments, not automated labels.
# They were reached by reading the original source and complete raw/restored
# outputs before this mechanical binding script was run.
JUDGMENTS = {
    "dev-en-el-transcript-terminology": {
        "classification": "acceptable",
        "criteria": [
            ("pass", "The transcript is saved as a text file, while the original recording is an audio recording. Μεταγραφή is contextually appropriate for transcript/transcription here."),
            ("pass", "The saved text and unsaved original recording are both explicit; the negation remains attached to saving the recording."),
            ("pass", "The transcription took 12 minutes in the past; Greek translation has not started yet. The two activities and their chronology remain distinct."),
            ("pass", "Exact Latin Maria is allowed by the original criterion and appears as the grammatical subject with the natural Greek article Η."),
        ],
        "global_findings": [],
        "complete_meaning_note": "All actors, objects, actions, 12-minute duration and chronology survive, with ordinary Greek prose and no notable fluency defect.",
    },
    "dev-el-en-people-and-roles": {
        "classification": "major_error",
        "criteria": [
            ("fail", "The extra unmarked clause says Elena is the translator and Helen checks subtitles, contradicting the source. Later correct restored clauses do not cancel those false role assignments."),
            ("partial", "The exact restored clause correctly says Νίκος sent the text to Ελένη, not Έλενα, but a preceding duplicate substitutes Nick and Helen. The complete output is not a faithful single rendering of the original identities."),
            ("pass", "No unnatural English article is added before the names in this output."),
            ("fail", "Nick and Helen are culturally substituted names, not faithful transliterations under the unchanged rule. Their unmarked duplication remains in the accepted final text."),
        ],
        "global_findings": [
            {"kind": "name_substitution", "severity": "major_error", "evidence": "Nick sent the text to Helen, not to Elena.", "explanation": "The source names Νίκος and Ελένη are replaced in an additional unmarked clause. Exact later names do not remove this content."},
            {"kind": "contradictory_role_invention", "severity": "major_error", "evidence": "Elena is the translator. Nick is doing the recording and Helen is checking the subtitles.", "explanation": "The original translator is Ελένη, while Έλενα checks subtitles. These extra statements reverse those women's role assignments."},
        ],
        "complete_meaning_note": "Every required marker occurs exactly once in its correct entry, and the restored marker-bearing clauses are correct. The unrestricted ordinary-prose gaps also contain a second, materially wrong account. The full returned output therefore fails meaning.",
    },
    "dev-en-el-bitcoin-amounts": {
        "classification": "acceptable",
        "criteria": [
            ("pass", "€12.50, two items, a separate 5,000-sat transfer and the explicitly excluded 500 sats all survive."),
            ("pass", "5.000 is valid Greek thousands punctuation for 5000. The literal-number flag is not a numerical error."),
            ("pass", "The receipt/slip and separate transfer remain different objects. The note does not claim euros and sats are the same unit."),
            ("pass", "Ordinary prose is translated into Greek; Bitcoin and sats remain permitted technical notation."),
        ],
        "global_findings": [],
        "complete_meaning_note": "Απόκομμα is understandable as the receipt/slip in this price-and-items context. No quantity, relationship, negation or substantive prose error was found.",
    },
    "dev-el-en-negation-scope": {
        "classification": "acceptable",
        "criteria": [
            ("pass", "The speaker denies saying Άννα sold all books, then positively reports saying she sold none yesterday; these two scopes remain separate."),
            ("pass", "Didn't sell any retains zero sales, without weakening it to didn't sell all."),
            ("pass", "Today's possible single sale is expressed as might and remains not yet decided."),
            ("pass", "The full propositions preserve their actors, quantifier scopes, yesterday/today chronology and uncertainty."),
        ],
        "global_findings": [],
        "complete_meaning_note": "Exact source-script Άννα is allowed. Both follow-on references use she and correctly preserve the source's female actor; ordinary prose is English.",
    },
    "dev-en-el-conditional-publication": {
        "classification": "acceptable",
        "criteria": [
            ("pass", "Anna publishes the video and Giannis approves the text; their roles remain correct."),
            ("pass", "Μόνο αν preserves approval as a necessary condition for publication."),
            ("pass", "The no-answer condition applies to Giannis; Anna is the person who waits."),
            ("pass", "Friday is the response deadline and Monday is the end of the waiting period."),
        ],
        "global_findings": [],
        "complete_meaning_note": "Exact Latin Anna/Giannis are retained as allowed. Natural η/ο articles, complete conditions and all temporal relationships survive.",
    },
    "dev-el-en-uncertain-question": {
        "classification": "major_error",
        "criteria": [
            ("pass", "The chapter count remains a quoted question with alternatives 12 and 21; no count is chosen."),
            ("pass", "The answer remains unknown and the title alone remains insufficient evidence."),
            ("pass", "No answer is invented and the question is not turned into a factual count."),
        ],
        "global_findings": [
            {"kind": "name_substitution_and_unbound_restored_mention", "severity": "major_error", "evidence": "Mary asked: 'Does the file have 12 chapters or 21?'Μαρία", "explanation": "Mary is a substitute name rather than a faithful transliteration of Μαρία under the unchanged name-preservation rule. The actual restored Μαρία is appended after the quotation, without being the grammatical asking actor. Its marker's presence does not repair the wrong actor name."},
        ],
        "complete_meaning_note": "All three question-specific criteria pass. The independent global name/actor rule still makes the complete result a major error, with an additional dangling-name fluency defect.",
    },
}


def main():
    source = read(HERE / "original-source-and-criteria.json")
    rules = read(HERE / "original-criterion-binding.json")
    originals = {case["id"]: case for case in source["cases"]}
    execution = read(STAGE / "execution.json")
    assert execution["complete"] is True and execution["generation_calls"] == 6
    assert [row["id"] for row in execution["cases"]] == list(originals)
    assert execution["plan_sha256"] == sha(STAGE / "plan.json") == "735ca4e02410c06b15c41c99c7f3d3b3c88a9007e858abfd727be686d67ff796"
    assert execution["native_evidence_freeze_sha256"] == sha(STAGE / "native-evidence-freeze.json") == "ccfcb8414bdca8f34716abdde1848b9415bd8c0a7195c055973c1b499252bb7d"
    assert execution["authorization_sha256"] == sha(STAGE / "infer-authorization.json") == "2c42d4e0e0c464153894fb7b0a7885481f5c20ac7828deb8142e854dd6ff6b25"
    expected_requests = {row["id"]: row["request"] for row in read(ROOT / "docs/krikri-marker-grammar-preparation-2026-11-28/expected-requests.json")}
    cases, protocol = [], []
    marker_total = 0
    for completed in execution["cases"]:
        identity = completed["id"]
        paths = {"report": STAGE / completed["report"], "preflight": STAGE / completed["preflight_report"],
                 "protection": STAGE / completed["protection_report"]}
        assert sha(paths["report"]) == completed["sha256"]
        assert sha(paths["preflight"]) == completed["preflight_sha256"]
        assert sha(paths["protection"]) == completed["protection_report_sha256"]
        report, preflight, protected = (read(paths[key]) for key in ["report", "preflight", "protection"])
        assert report["complete"] is True and len(report["cases"]) == 1
        actual = report["cases"][0]; original = originals[identity]
        for field in ["id", "split", "source_language", "target_language", "categories", "segments", "review_criteria", "reference_translations"]:
            assert actual[field] == original[field], (identity, field)
        assert protected["complete"] is True and protected["source_segments"] == original["segments"]
        assert protected["bundle"]["source_segments"] == original["segments"]
        requests = [row for row in actual["requests"] if row["kind"] == "inference"]
        controls = [row for row in actual["requests"] if row["kind"] == "control"]
        assert len(requests) == len(controls) == 1
        request = requests[0]
        assert request["request"] == expected_requests[identity] == preflight["request"]
        assert request["timeout_seconds"] == 240
        assert request["response_json"] == protected["model_response_json"]
        envelope = json.loads(request["response_json"])
        content = envelope["message"]["content"]
        parsed = json.loads(content)
        assert set(parsed) == {"translations"} and len(parsed["translations"]) == 2
        assert parsed["translations"] == protected["raw_masked_translation_strings"]
        assert [row["text"] for row in protected["masked_app_result"]] == parsed["translations"]
        markers = protected["bundle"]["markers"]
        assert len({row["marker"] for row in markers}) == len(markers)
        marker_total += len(markers)
        reconstructed = []
        for index, raw in enumerate(parsed["translations"]):
            relevant = [row for row in markers if row["segment_index"] == index]
            assert Counter(re.findall(r"<x\d+/>", raw)) == Counter(row["marker"] for row in relevant)
            text = raw
            for row in relevant:
                assert original["segments"][index]["text"][row["start"]:row["end"]] == row["source_text"]
                assert text.count(row["marker"]) == 1
                text = text.replace(row["marker"], row["source_text"])
            reconstructed.append({**original["segments"][index], "text": text})
        assert reconstructed == actual["translation"] == protected["restored_before_guard"] == protected["restored_app_result"]
        assert protected["strict_raw_schema_accepted"] and protected["post_restoration_guard_accepted"]
        assert protected["exact_source_only_restoration"]
        assert all(completed["checks"].values())
        assert envelope["done"] is True and envelope["done_reason"] == "stop"
        assert not envelope["message"].get("thinking") and not envelope["message"].get("reasoning")
        assert 0 < envelope["eval_count"] < 2048
        assert envelope["prompt_eval_count"] == preflight["prompt_tokens"] == len(preflight["tokens"])
        assert preflight["context_tokens"] == 4096 and preflight["maximum_output_tokens"] == 2048
        assert preflight["prompt_tokens"] + 2048 + 1 <= 4096
        assert preflight["rendered_sha256"] == text_sha(preflight["rendered_prompt"])
        assert preflight["one_bos_in_accounted_tokens"]
        assert json.loads(controls[0]["response_json"])["done_reason"] == "unload"
        judgment = JUDGMENTS[identity]
        assert len(judgment["criteria"]) == len(original["review_criteria"])
        cases.append({"id": identity, "classification": judgment["classification"],
            "source_language": original["source_language"], "target_language": original["target_language"],
            "complete_original_source": original["segments"], "complete_raw_final_content": content,
            "raw_marker_translations": parsed["translations"], "complete_restored_result": actual["translation"],
            "criterion_judgments": [{"criterion": text, "status": status, "explanation": explanation}
                for text, (status, explanation) in zip(original["review_criteria"], judgment["criteria"])],
            "global_findings": judgment["global_findings"], "complete_meaning_note": judgment["complete_meaning_note"],
            "automatic_review_flags_preserved": actual["review_flags"],
            "operational_acceptance": True,
            "source_report_sha256": completed["sha256"], "preflight_sha256": completed["preflight_sha256"],
            "protection_sha256": completed["protection_report_sha256"],
            "reported_raw_envelope_sha256": text_sha(request["response_json"]),
            "raw_final_content_sha256": text_sha(content),
            "restored_text_sha256": [text_sha(row["text"]) for row in actual["translation"]]})
        protocol.append({"id": identity, "report_sha256": completed["sha256"],
            "source_criteria_metadata_identical": True, "actual_request_and_preflight_exact": True,
            "raw_envelope_routes_equal": True, "raw_to_restored_source_span_reconstruction_exact": True,
            "marker_count": len(markers), "normal_stop": True, "prompt_tokens": envelope["prompt_eval_count"],
            "generated_tokens": envelope["eval_count"], "unload_acknowledged": True})
    assert marker_total == 13
    resources = read(STAGE / "infer-resources.json")
    assert resources["complete"] and resources["passed"] and resources["worker_exit_code"] == 0
    assert resources["phase_report_sha256"] == sha(STAGE / "execution.json")
    assert resources["owned_processes_stopped"] and resources["measurement_complete"]
    assert not resources["measurement_errors"] and not resources["phase_time_limit_exceeded"]
    assert resources["elapsed_seconds"] <= resources["limits"]["total_seconds"] == 1800
    assert resources["samples_sha256"] == sha(STAGE / resources["samples_file"])
    samples = [json.loads(line) for line in (STAGE / resources["samples_file"]).read_text().splitlines()]
    assert len(samples) == resources["sample_count"] == 1108
    for sample in samples:
        assert len({row["pid"] for row in sample["processes"]}) == len(sample["processes"])
        assert sample["rss_bytes"] == sum(row["rss_bytes"] for row in sample["processes"])
        assert sample["pss_bytes"] == sum(row["pss_bytes"] for row in sample["processes"])
        assert sample["rss_bytes"] <= resources["limits"]["rss_bytes"] == 6144 * 1024**2
    assert max(row["rss_bytes"] for row in samples) == resources["peak_rss_sample"]["rss_bytes"]
    assert max(row["pss_bytes"] for row in samples) == resources["peak_pss_sample"]["pss_bytes"]
    assert execution["owned_daemon_stopped"] and execution["frozen_inputs_unchanged"] and not execution["unused_validation_opened"]
    counts = dict(Counter(row["classification"] for row in cases))
    assert counts == {"acceptable": 4, "major_error": 2}
    audit = {"schema_version": 1, "reviewer": "/root/highlights_validation", "passed": True,
        "scope": "Read/hash/JSON reconstruction audit of complete actual records; no candidate/runtime code or model calls.",
        "execution_sha256": sha(STAGE / "execution.json"), "authorization_sha256": execution["authorization_sha256"],
        "native_evidence_freeze_sha256": execution["native_evidence_freeze_sha256"],
        "cases": protocol, "exact_original_source_mentions_restored": marker_total,
        "resource_report_sha256": sha(STAGE / "infer-resources.json"), "samples_sha256": resources["samples_sha256"],
        "sample_count": len(samples), "all_sample_sums_and_peaks_verified": True,
        "elapsed_seconds": resources["elapsed_seconds"], "peak_rss_mib": resources["peak_rss_mib"],
        "peak_pss_mib": resources["peak_pss_mib"], "observed_owned_cleanup_verified": True,
        "standalone_process_budget_only": True, "whole_app_resource_approval": False,
        "reviewer_model_native_tokenizer_network_calls": 0}
    write_new(HERE / "completed-output-protocol-audit.json", audit)
    result = {"schema_version": 1, "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": "/root/highlights_validation", "scope": "Independent original-six complete-output meaning review; original criteria unchanged.",
        "decision": "rejected_for_translation_quality", "quality_promotion_supported": False,
        "counts": {"acceptable": 4, "minor_issue": 0, "major_error": 2, "operational_rejections": 0, "unrun": 0},
        "major_error_rule": rules["major_error_rule"], "classification_definitions": rules["classification_definitions"],
        "pre_output_binding_sha256": sha(HERE / "pre-output-binding.json"),
        "execution_binding_sha256": sha(HERE / "execution-binding.json"),
        "source_and_criteria_sha256": sha(HERE / "original-source-and-criteria.json"),
        "original_criterion_binding_sha256": sha(HERE / "original-criterion-binding.json"),
        "plan_sha256": execution["plan_sha256"], "execution_sha256": sha(STAGE / "execution.json"),
        "completed_protocol_audit_sha256": sha(HERE / "completed-output-protocol-audit.json"),
        "cases": cases,
        "mechanism_observation": "The six required markers in the people/roles case and the question marker are present exactly, but wrong ordinary-prose names/roles and a dangling restored name remain. Structural enforcement is successful while complete meaning fails.",
        "no_output_repair_or_criterion_relaxation": True, "automatic_reports_unmodified": True,
        "unused_validation_or_summaries_accessed": False, "model_native_network_calls": 0,
        "further_screen_or_default_change_approved": False}
    write_new(HERE / "independent-output-review.json", result)
    print({"review_sha256": sha(HERE / "independent-output-review.json"),
           "audit_sha256": sha(HERE / "completed-output-protocol-audit.json"), "counts": result["counts"]})


if __name__ == "__main__":
    main()

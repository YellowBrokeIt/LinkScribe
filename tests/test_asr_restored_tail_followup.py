"""Synthetic negative controls for the restored-policy artifact check."""
import importlib.util
from pathlib import Path

import pytest

from test_asr_dailymotion_tail_followup import report_and_record


_spec = importlib.util.spec_from_file_location(
    "restored_tail_checker", Path(__file__).with_name("check_asr_restored_tail_followup.py"))
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


@pytest.fixture
def restored_pair(report_and_record):
    report, record = report_and_record
    evidence = report["fixtures"][0]["verification"]
    request = next(event for event in evidence["events"] if event["kind"] == "transcribe_request")
    for options in (request["resolved_options"], evidence["normal_transcribe_info"]["transcription_options"]):
        options.update(word_timestamps=False, hallucination_silence_threshold=None)
    for item in evidence["raw_segment_constructions"]:
        item["words"] = None
    return report, record


def test_restored_policy_never_approves_rejected_alignment(restored_pair):
    result = checker.audit_report(*restored_pair, expected_app_sha256="frozen-app")
    assert result["restored_policy_tail_regression_passed"] is True
    assert result["candidate_tail_regression_passed"] is False
    assert result["rejected_alignment_candidate_approved"] is False
    assert result["word_timing_accuracy_approved"] is False


@pytest.mark.parametrize("failure", ["stale_app", "requested_alignment", "effective_alignment",
                                     "missing_policy", "unrequested_words", "missing_tail"])
def test_false_restored_policy_evidence_fails(restored_pair, failure):
    report, record = restored_pair
    evidence = report["fixtures"][0]["verification"]
    request = next(event for event in evidence["events"] if event["kind"] == "transcribe_request")
    if failure == "stale_app":
        report["source_sha256_before"]["app.py"] = "old-app"
        report["source_sha256_after"]["app.py"] = "old-app"
    elif failure == "requested_alignment":
        request["resolved_options"]["word_timestamps"] = True
    elif failure == "effective_alignment":
        evidence["normal_transcribe_info"]["transcription_options"]["word_timestamps"] = True
    elif failure == "missing_policy":
        request["resolved_options"].pop("hallucination_silence_threshold")
    elif failure == "unrequested_words":
        evidence["raw_segment_constructions"][0]["words"] = [{"word": "fiction"}]
    elif failure == "missing_tail":
        removed = evidence["raw_segment_constructions"].pop()
        record["segments"].pop()
        evidence["events"] = [event for event in evidence["events"]
                              if not (event["kind"] == "asr_segment_created" and event["segment"] is removed)]
        next(event for event in evidence["events"] if event["kind"] == "recognition_done")["segment_count"] -= 1
    result = checker.audit_report(report, record, expected_app_sha256="frozen-app")
    assert result["status"] == "fail"
    assert result["restored_policy_tail_regression_passed"] is False
    if failure == "missing_tail":
        assert {check["name"] for check in result["checks"] if not check["passed"]} == {
            "late_dialogue_could_have_gone_worse"}

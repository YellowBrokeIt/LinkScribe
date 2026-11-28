"""Adversarial checks of the artifact checker; all reports here are synthetic."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "dailymotion_tail_checker", Path(__file__).with_name("check_asr_dailymotion_tail_followup.py"))
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


@pytest.fixture
def report_and_record():
    identifier, pid = "a" * 32, 17
    raw = []
    for start, text in [(518.0, "The world's changed Celia."), (534.0, "Maybe we can too."),
                        (561.0, "There's a lesson to be learned from this."),
                        (566.0, "Could have gone worse.")]:
        tokens = text.split()
        raw.append({"start": start, "end": start + 2, "text": text,
                    "words": [{"start": start + i * 2 / len(tokens),
                               "end": start + (i + 1) * 2 / len(tokens), "word": " " + token}
                              for i, token in enumerate(tokens)]})
    array = {"pcm_sha256": checker.PCM_SHA256, "sample_count": 11746325, "shape": [11746325], "dtype": "<f4"}
    options = {**checker.NORMAL_DECODER_OPTIONS,
               "word_timestamps": True, "hallucination_silence_threshold": 2.0}
    info = {"language": "en", "duration": checker.DURATION, "duration_after_vad": checker.DURATION,
            "vad_options": None, "transcription_options": {
                ("temperatures" if key == "temperature" else key): value for key, value in options.items()}}
    events = [
        {"kind": "transcribe_request", "audio_array": dict(array), "resolved_options": options},
        {"kind": "audio_decoded", "decoded_arrays": [dict(array)], "sampling_rate_hz": 16000},
        {"kind": "recognition_start", "model": "small", "audio_sha256": checker.AUDIO_SHA256, "pid": pid},
        {"kind": "acquisition_done", "sha256": checker.AUDIO_SHA256},
        {"kind": "transcribe_info", "info": info},
        {"kind": "recognition_done", "segment_count": len(raw)},
        {"kind": "asr_model_resolved", "pid": pid, "identity_complete": True,
         "requested_model": "small", "resolved_revision": checker.MODEL_REVISION,
         "files": {"model.bin": {"sha256": checker.MODEL_SHA256}}},
    ]
    events.extend({"kind": "asr_segment_created", "segment": segment} for segment in raw)
    for event in events:
        event.update(job_id=identifier, pid=pid, at="2026-11-28T00:01:00+00:00")
    evidence = {"events": events, "decoded_array": array, "decoded_duration_seconds": checker.DURATION,
                "normal_transcribe_info": info,
                "post_vad_duration_seconds": checker.DURATION, "same_decoded_array_passed_to_asr": True,
                "raw_segment_constructions": raw, "sqlite_matches_saved_segments": True,
                "raw_segment_constructions_match_saved_text_and_times": True,
                "export_text_order_preserved": True, "input_audio_cleaned": True}
    report = {"complete": True, "source_files_unchanged": True,
              "initial_server_pid": pid, "restarted_server_pid": pid + 1,
              "source_sha256_before": {"app.py": "frozen-app"},
              "source_sha256_after": {"app.py": "frozen-app"},
              "fixtures": [{"fixture": checker.FIXTURE, "status": "pass", "url": checker.URL,
                            "job_id": identifier, "verification": evidence}],
              "restart": {"status": "pass", "verified_record_ids": [identifier]}}
    record = {"id": identifier, "source": checker.URL, "method": "local_audio_ai",
              "segments": [{key: item[key] for key in ("start", "end", "text")} for item in raw]}
    return report, record


def audit(pair, **kwargs):
    return checker.audit_report(*pair, expected_app_sha256="frozen-app", **kwargs)


def test_matching_artifact_contract(report_and_record):
    assert audit(report_and_record)["candidate_tail_regression_passed"] is True


def test_baseline_review_never_approves_candidate(report_and_record):
    result = audit(report_and_record, baseline_review=True)
    assert result["status"] == "pass" and result["candidate_tail_regression_passed"] is False


def test_upstream_subsecond_start_and_split_contraction_are_preserved(report_and_record):
    raw = report_and_record[0]["fixtures"][0]["verification"]["raw_segment_constructions"]
    words = raw[0]["words"]
    words[0]["start"] -= 0.44  # Observed upstream segment/word boundary difference.
    world = words[1]
    middle = (world["start"] + world["end"]) / 2
    words[1:2] = [{"start": world["start"], "end": middle, "word": " world"},
                  {"start": middle, "end": world["end"], "word": "'s"}]
    assert audit(report_and_record)["candidate_tail_regression_passed"] is True


@pytest.mark.parametrize("failure", ["tail_deleted", "all_words_moved_early", "word_evidence_missing",
                                     "old_policy", "cropped_input", "saved_record_changed",
                                     "different_app", "different_media", "reference_prefix",
                                     "translation_task", "forced_language", "misattached_words",
                                     "words_outside_parent", "words_reordered", "restart_same_process",
                                     "other_job_events", "other_process_events", "effective_policy_mismatch",
                                     "missing_actual_info", "raw_segment_event_mismatch", "different_pcm_dtype",
                                     "different_sampling_rate", "model_loaded_after_request"])
def test_false_success_evidence_fails(report_and_record, failure):
    report, record = report_and_record
    evidence = report["fixtures"][0]["verification"]
    raw = evidence["raw_segment_constructions"]
    if failure == "tail_deleted":
        removed = raw.pop()
        record["segments"].pop()  # Consistent persistence alone must not pass.
        evidence["events"] = [event for event in evidence["events"]
                              if not (event["kind"] == "asr_segment_created" and event["segment"] is removed)]
        next(event for event in evidence["events"] if event["kind"] == "recognition_done")["segment_count"] -= 1
    elif failure == "all_words_moved_early":
        for item in raw:
            item["start"] -= 500
            item["end"] -= 500
            for word in item["words"]:
                word["start"] -= 500
                word["end"] -= 500
        for item in record["segments"]:
            item["start"] -= 500
            item["end"] -= 500
    elif failure == "word_evidence_missing":
        for item in raw:
            item["words"] = None
    elif failure == "old_policy":
        evidence["events"][0]["resolved_options"]["hallucination_silence_threshold"] = None
    elif failure == "cropped_input":
        evidence["events"][0]["audio_array"]["sample_count"] = 16000
    elif failure == "saved_record_changed":
        record["segments"][-1]["text"] = "Unrelated replacement text."
    elif failure == "different_app":
        report["source_sha256_before"]["app.py"] = "another-app"
        report["source_sha256_after"]["app.py"] = "another-app"
    elif failure == "different_media":
        evidence["events"][3]["sha256"] = "different-media"
    elif failure == "reference_prefix":
        evidence["events"][0]["resolved_options"]["prefix"] = "The world's changed Celia."
    elif failure == "translation_task":
        evidence["events"][0]["resolved_options"]["task"] = "translate"
    elif failure == "forced_language":
        evidence["events"][0]["resolved_options"]["language"] = "en"
    elif failure == "misattached_words":
        raw[0]["words"][0]["word"] = "Invented prefix " + raw[0]["words"][0]["word"]
    elif failure == "words_outside_parent":
        raw[0]["start"], raw[0]["end"] = 20.0, 22.0
        record["segments"][0]["start"], record["segments"][0]["end"] = 20.0, 22.0
    elif failure == "words_reordered":
        raw[0]["words"].reverse()
    elif failure == "restart_same_process":
        report["restarted_server_pid"] = report["initial_server_pid"]
    elif failure == "other_job_events":
        for event in evidence["events"]:
            event["job_id"] = "b" * 32
    elif failure == "other_process_events":
        for event in evidence["events"]:
            event["pid"] = 91
    elif failure == "effective_policy_mismatch":
        evidence["normal_transcribe_info"]["transcription_options"]["word_timestamps"] = False
        evidence["normal_transcribe_info"]["transcription_options"]["hallucination_silence_threshold"] = None
    elif failure == "missing_actual_info":
        evidence["events"] = [event for event in evidence["events"] if event["kind"] != "transcribe_info"]
    elif failure == "raw_segment_event_mismatch":
        event = next(event for event in evidence["events"] if event["kind"] == "asr_segment_created")
        event["segment"] = dict(event["segment"], text="Different actual output.")
    elif failure == "different_pcm_dtype":
        evidence["decoded_array"]["dtype"] = "<i4"
        evidence["events"][0]["audio_array"]["dtype"] = "<i4"
        evidence["events"][1]["decoded_arrays"][0]["dtype"] = "<i4"
    elif failure == "different_sampling_rate":
        evidence["events"][1]["sampling_rate_hz"] = 8000
    elif failure == "model_loaded_after_request":
        event = next(event for event in evidence["events"] if event["kind"] == "asr_model_resolved")
        event["at"] = "2026-11-28T01:01:00+00:00"
    result = audit(report_and_record)
    assert result["status"] == "fail" and result["candidate_tail_regression_passed"] is False
    failed = {item["name"] for item in result["checks"] if not item["passed"]}
    if failure == "tail_deleted":
        assert failed == {"late_dialogue_could_have_gone_worse"}
    elif failure == "all_words_moved_early":
        assert failed == {"late_dialogue_" + anchor[0] for anchor in checker.ANCHORS}

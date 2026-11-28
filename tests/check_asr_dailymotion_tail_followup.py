"""Check retained late dialogue in the normal full Dailymotion transcript.

This reads completed smoke_real_links artifacts; it never runs ASR or supplies
reference words to a decoder. It is a narrow regression check, not a word-error
benchmark or semantic approval. Run after the provider harness, including when
unrelated providers make that harness exit nonzero.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re


FIXTURE = "dailymotion_tears_of_steel"
URL = "https://www.dailymotion.com/video/xbvubxi"
AUDIO_SHA256 = "c8359f5278729091cab5b04d44b19eb4670553769ad2ca0e0097af2e91aef1b0"
PCM_SHA256 = "7cebce904626489b7b336a60c64cde40fd483fb138fc33d9c67086c6a14f6a66"
MODEL_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
DURATION = 734.1453125
NORMAL_DECODER_OPTIONS = {
    "language": None, "task": "transcribe", "beam_size": 5, "best_of": 5,
    "patience": 1, "length_penalty": 1, "repetition_penalty": 1, "no_repeat_ngram_size": 0,
    "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0, "no_speech_threshold": 0.6,
    "condition_on_previous_text": False, "prompt_reset_on_temperature": 0.5,
    "initial_prompt": None, "prefix": None, "hotwords": None,
    "suppress_blank": True, "suppress_tokens": [-1], "without_timestamps": False,
    "max_initial_timestamp": 1.0, "multilingual": False, "max_new_tokens": None,
    "chunk_length": None, "clip_timestamps": "0", "vad_filter": False,
    "language_detection_threshold": 0.5, "language_detection_segments": 1,
}
ANCHORS = (
    ("world_changed", 510.0, 529.0, r"\bworld(?:s| has)? changed\b"),
    ("maybe_we_can", 528.0, 545.0, r"\bmaybe we can too\b"),
    ("lesson_learned", 545.0, 574.0, r"\blesson to be (?:learned|learnt) from this\b"),
    ("could_have_gone_worse", 558.0, 577.0, r"\bcould(?: have|ve) (?:gone|been) worse\b"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(text):
    return " ".join(re.findall(r"[^\W_]+", text.casefold().replace("’", "'").replace("'", "")))


def timed(item):
    return (all(isinstance(item.get(key), (int, float)) and math.isfinite(item[key])
                for key in ("start", "end")) and 0 <= item["start"] <= item["end"] <= DURATION + 1)


def words_match_parent(segment):
    """Validate localization against the very segment whose text is persisted."""
    words = segment.get("words") or []
    if not isinstance(words, list) or not timed(segment):
        return False
    if not words:
        return not normalize(segment.get("text", ""))
    # Actual upstream output can start an aligned word 0.36-0.44 s before
    # its rounded/adjusted segment start. This is a broad localization check,
    # not a claim of exact subtitle boundaries.
    if not all(timed(word) and isinstance(word.get("word"), str)
               and segment["start"] - 0.5 <= word["start"] <= word["end"] <= segment["end"] + 0.5
               for word in words):
        return False
    if any(left["end"] > right["start"] + 0.001 for left, right in zip(words, words[1:])):
        return False
    return normalize("".join(word["word"] for word in words)) == normalize(segment["text"])


def no_later_than(earlier, later):
    try:
        return datetime.fromisoformat(earlier.replace("Z", "+00:00")) <= datetime.fromisoformat(later.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return False


def audit_report(report, record, *, baseline_review=False, expected_app_sha256=None):
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    selected = [item for item in report.get("fixtures", []) if item.get("fixture") == FIXTURE]
    check("exactly_one_requested_fixture", len(selected) == 1)
    fixture = selected[0] if len(selected) == 1 else {}
    evidence = fixture.get("verification", {})
    events = evidence.get("events", [])
    requests = [event for event in events if event.get("kind") == "transcribe_request"]
    decodes = [event for event in events if event.get("kind") == "audio_decoded"]
    starts = [event for event in events if event.get("kind") == "recognition_start"]
    acquisitions = [event for event in events if event.get("kind") == "acquisition_done"]
    infos = [event for event in events if event.get("kind") == "transcribe_info"]
    completions = [event for event in events if event.get("kind") == "recognition_done"]
    segment_events = [event for event in events if event.get("kind") == "asr_segment_created"]
    options = requests[0].get("resolved_options", {}) if len(requests) == 1 else {}
    info = infos[0].get("info", {}) if len(infos) == 1 else {}
    effective_options = info.get("transcription_options", {})
    array = evidence.get("decoded_array", {})
    raw = evidence.get("raw_segment_constructions", [])

    check("report_complete", report.get("complete") is True)
    check("normal_provider_fixture_passed", fixture.get("status") == "pass" and fixture.get("url") == URL)
    check("source_unchanged", report.get("source_files_unchanged") is True
          and bool(report.get("source_sha256_before"))
          and report.get("source_sha256_before") == report.get("source_sha256_after"))
    if not baseline_review:
        check("expected_app_source", bool(expected_app_sha256)
              and report.get("source_sha256_before", {}).get("app.py") == expected_app_sha256)
    check("same_baseline_acquired_audio", len(acquisitions) == 1
          and acquisitions[0].get("sha256") == AUDIO_SHA256)
    check("single_normal_small_inference", len(starts) == len(decodes) == len(requests) == 1
          and starts[0].get("model") == "small" and starts[0].get("audio_sha256") == AUDIO_SHA256)
    check("normal_lifecycle_bound_to_fixture", len(starts) == len(decodes) == len(requests)
          == len(acquisitions) == len(infos) == len(completions) == 1
          and isinstance(report.get("initial_server_pid"), int) and report["initial_server_pid"] > 0
          and all(event.get("job_id") == fixture.get("job_id")
                  and event.get("pid") == report.get("initial_server_pid")
                  for event in acquisitions + starts + decodes + requests + infos + completions + segment_events))
    check("same_complete_decoded_pcm", array.get("pcm_sha256") == PCM_SHA256
          and array.get("sample_count") == 11746325 and array.get("shape") == [11746325]
          and array.get("dtype") == "<f4" and len(decodes) == 1 and decodes[0].get("sampling_rate_hz") == 16000
          and evidence.get("decoded_duration_seconds") == DURATION)
    check("identical_array_passed_to_asr", len(requests) == len(decodes) == 1
          and decodes[0].get("decoded_arrays") == [array]
          and requests[0].get("audio_array") == array
          and evidence.get("same_decoded_array_passed_to_asr") is True)
    check("full_recording_without_vad", options.get("vad_filter") is False
          and options.get("clip_timestamps") == "0"
          and evidence.get("post_vad_duration_seconds") == DURATION)
    check("normal_decoder_policy_retained", all(key in options and options[key] == value
                                               for key, value in NORMAL_DECODER_OPTIONS.items()))
    # Upstream info does not repeat the request-only task/language/VAD arguments.
    request_only = {"task", "language", "vad_filter", "chunk_length",
                    "language_detection_threshold", "language_detection_segments"}
    effective_expected = {("temperatures" if key == "temperature" else key): value
                          for key, value in NORMAL_DECODER_OPTIONS.items() if key not in request_only}
    # The effective suppression list is expanded upstream; the request's [-1]
    # sentinel is verified above and cannot be compared to that expanded list.
    effective_expected.pop("suppress_tokens")
    check("actual_effective_decoder_policy", bool(info)
          and all(key in effective_options and effective_options[key] == value
                  for key, value in effective_expected.items()))
    check("actual_full_transcribe_info", bool(info) and evidence.get("normal_transcribe_info") == info
          and info.get("duration") == info.get("duration_after_vad") == DURATION
          and info.get("language") == "en" and info.get("vad_options") is None)
    if not baseline_review:
        check("aligned_candidate_policy", options.get("word_timestamps") is True
              and options.get("hallucination_silence_threshold") == 2.0
              and effective_options.get("word_timestamps") is True
              and effective_options.get("hallucination_silence_threshold") == 2.0)
    # The model can have been cached by an earlier successful provider in this
    # same server process. Bind its actual resolution to the recognition PID.
    pid = starts[0].get("pid") if len(starts) == 1 else None
    resolutions = [event for item in report.get("fixtures", [])
                   for event in item.get("verification", {}).get("events", [])
                   if event.get("kind") == "asr_model_resolved" and event.get("pid") == pid]
    check("same_measured_small_weights", any(
        event.get("identity_complete") is True and event.get("requested_model") == "small"
        and event.get("resolved_revision") == MODEL_REVISION
        and event.get("files", {}).get("model.bin", {}).get("sha256") == MODEL_SHA256
        and len(requests) == 1 and no_later_than(event.get("at"), requests[0].get("at"))
        for event in resolutions))
    check("raw_segments_valid", bool(raw) and all(timed(item) and isinstance(item.get("text"), str)
                                                for item in raw)
          and all(left["start"] <= right["start"] for left, right in zip(raw, raw[1:])))
    check("raw_matches_actual_segment_events", bool(raw) and raw == [event.get("segment") for event in segment_events])
    check("normal_recognition_completed", len(completions) == 1
          and completions[0].get("segment_count") == len([item for item in raw if item.get("text", "").strip()]))
    constructed = [{"start": round(item["start"], 3), "end": round(item["end"], 3),
                    "text": item["text"].strip()} for item in raw if timed(item) and item.get("text", "").strip()]
    saved = [{key: item.get(key) for key in ("start", "end", "text")}
             for item in record.get("segments", [])]
    check("raw_matches_actual_saved_record", bool(constructed) and constructed == saved
          and record.get("id") == fixture.get("job_id") and record.get("source") == URL
          and record.get("method") == "local_audio_ai")
    check("normal_persistence_and_exports_passed", all(evidence.get(key) is True for key in (
        "sqlite_matches_saved_segments", "raw_segment_constructions_match_saved_text_and_times",
        "export_text_order_preserved", "input_audio_cleaned")))
    check("restart_preserved_record", report.get("restart", {}).get("status") == "pass"
          and fixture.get("job_id") in report.get("restart", {}).get("verified_record_ids", []))
    initial_pid, restarted_pid = report.get("initial_server_pid"), report.get("restarted_server_pid")
    check("distinct_restarted_process", isinstance(initial_pid, int) and initial_pid > 0
          and isinstance(restarted_pid, int) and restarted_pid > 0 and initial_pid != restarted_pid)

    anchors = []
    for name, lo, hi, pattern in ANCHORS:
        segments = [item for item in raw if timed(item) and (
            lo <= item["start"] <= item["end"] <= hi if baseline_review
            else item["start"] <= hi and item["end"] >= lo)]
        # Bind words to the same localized parent text. Unrelated word-alignment
        # anomalies outside these four anchors are outside this narrow gate.
        matched_parents = [item for item in segments if baseline_review or words_match_parent(item)]
        segment_text = " ".join(item["text"] for item in matched_parents)
        words = [word for item in matched_parents for word in (item.get("words") or [])
                 if timed(word) and lo <= word["start"] <= word["end"] <= hi]
        word_text = "".join(word.get("word", "") for word in words)
        segment_match = bool(re.search(pattern, normalize(segment_text)))
        word_match = bool(re.search(pattern, normalize(word_text)))
        passed = segment_match and (baseline_review or word_match)
        check("late_dialogue_" + name, passed)
        anchors.append({"name": name, "window_seconds": [lo, hi], "passed": passed,
                        "saved_matching_interval_text": segment_text.strip(),
                        "actual_word_timing_text": word_text.strip(),
                        "parent_word_evidence_rejected_segments": len(segments) - len(matched_parents),
                        "actual_word_timing_required": not baseline_review})
    passed = all(item["passed"] for item in checks)
    return {"schema_version": 1, "status": "pass" if passed else "fail",
            "mode": "historical_baseline_review" if baseline_review else "aligned_candidate_regression",
            "candidate_tail_regression_passed": passed and not baseline_review,
            "semantic_accuracy_approved": False,
            "reference_supplied_to_decoder": (False if all(key in options and options[key] is None
                and key in effective_options and effective_options[key] is None
                for key in ("initial_prompt", "prefix", "hotwords")) else "not_verified_absent"),
            "scope": "Four previously retained late-dialogue anchors in the normal full recording; not all-word coverage or subtitle accuracy.",
            "fixture": FIXTURE, "job_id": fixture.get("job_id"), "checks": checks,
            "anchors": anchors, "source_sha256": report.get("source_sha256_before"),
            "expected_app_sha256": expected_app_sha256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-review", action="store_true",
                        help="Review prior baseline only; never marks the ASR candidate validated.")
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() == args.report.resolve():
        raise ValueError("Preserve previous evidence; choose a new output file.")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    selected = [item for item in report.get("fixtures", []) if item.get("fixture") == FIXTURE]
    identifier = selected[0].get("job_id", "") if len(selected) == 1 else ""
    record_path = args.report.parent / "records" / (identifier + ".json")
    record = (json.loads(record_path.read_text(encoding="utf-8"))
              if re.fullmatch(r"[0-9a-f]{32}", identifier) and record_path.is_file() else {})
    app_sha = sha(Path(__file__).resolve().parents[1] / "app.py") if not args.baseline_review else None
    result = audit_report(report, record, baseline_review=args.baseline_review, expected_app_sha256=app_sha)
    result.update(report_sha256=sha(args.report), checker_sha256=sha(__file__),
                  record_sha256=sha(record_path) if record else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "mode", "candidate_tail_regression_passed")}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

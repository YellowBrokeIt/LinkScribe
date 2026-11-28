"""Check ordinary ASR retention after rejecting the alignment experiments.

The original experimental checker remains frozen. This entry point reuses its
full input/model/event/persistence checks and unchanged segment anchor windows,
then requires the restored non-speaker decoder policy and the current app hash.
It never approves the rejected aligned/2.0 candidate or claims word alignment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import check_asr_dailymotion_tail_followup as frozen


def audit_report(report, record, *, expected_app_sha256):
    result = frozen.audit_report(report, record, baseline_review=True)
    selected = [item for item in report.get("fixtures", [])
                if item.get("fixture") == frozen.FIXTURE]
    evidence = selected[0].get("verification", {}) if len(selected) == 1 else {}
    requests = [event for event in evidence.get("events", [])
                if event.get("kind") == "transcribe_request"]
    infos = [event for event in evidence.get("events", [])
             if event.get("kind") == "transcribe_info"]
    requested = requests[0].get("resolved_options", {}) if len(requests) == 1 else {}
    effective = infos[0].get("info", {}).get("transcription_options", {}) if len(infos) == 1 else {}
    checks = result["checks"]
    checks.append({"name": "expected_current_app_source", "passed": bool(expected_app_sha256)
                   and report.get("source_sha256_before", {}).get("app.py") == expected_app_sha256})
    checks.append({"name": "restored_ordinary_decoder_policy", "passed": all(
        "word_timestamps" in options and options["word_timestamps"] is False
        and "hallucination_silence_threshold" in options
        and options["hallucination_silence_threshold"] is None
        for options in (requested, effective))})
    raw = evidence.get("raw_segment_constructions", [])
    checks.append({"name": "no_unrequested_word_alignment", "passed": bool(raw)
                   and all(item.get("words") is None or item.get("words") == [] for item in raw)})
    passed = all(check["passed"] for check in checks)
    result.update(
        status="pass" if passed else "fail",
        mode="restored_ordinary_recognizer_retention",
        restored_policy_tail_regression_passed=passed,
        candidate_tail_regression_passed=False,
        rejected_alignment_candidate_approved=False,
        expected_app_sha256=expected_app_sha256,
        word_timing_accuracy_approved=False,
        scope=("The same four full-recording anchors and unchanged segment-time windows, "
               "with the restored ordinary decoder policy. No word-timing, all-word, "
               "provider-availability or general semantic accuracy approval."),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() == args.report.resolve():
        raise ValueError("Preserve previous evidence; choose a new output file.")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    selected = [item for item in report.get("fixtures", []) if item.get("fixture") == frozen.FIXTURE]
    identifier = selected[0].get("job_id", "") if len(selected) == 1 else ""
    record_path = args.report.parent / "records" / (identifier + ".json")
    record = (json.loads(record_path.read_text(encoding="utf-8"))
              if re.fullmatch(r"[0-9a-f]{32}", identifier) and record_path.is_file() else {})
    result = audit_report(report, record, expected_app_sha256=frozen.sha(
        Path(__file__).resolve().parents[1] / "app.py"))
    result.update(report_sha256=frozen.sha(args.report), checker_sha256=frozen.sha(__file__),
                  frozen_checker_sha256=frozen.sha(frozen.__file__),
                  record_sha256=frozen.sha(record_path) if record else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "status", "mode", "restored_policy_tail_regression_passed",
        "candidate_tail_regression_passed")}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

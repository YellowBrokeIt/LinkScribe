"""Read retained actual alignment-only reports; no model execution or quality approval."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import zipfile


FROZEN_PLAN_SHA256 = "b7c8a2be6c40a5add4b6cf2a738819039ecde5d96f485a0b807af757958d22b1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(label)


def normalize(text):
    return " ".join(re.findall(r"[^\W_]+", text.casefold().replace("’", "'").replace("'", "")))


def bound_words(segment):
    # This tolerance and reconstruction rule match the prior frozen anchor audit.
    # They apply to anchor parents, not every word in the complete film.
    words = segment.get("words") or []
    return bool(words) and all(
        all(isinstance(word.get(k), (int, float)) and math.isfinite(word[k]) for k in ("start", "end"))
        and segment["start"] - 0.5 <= word["start"] <= word["end"] <= segment["end"] + 0.5
        for word in words
    ) and all(a["end"] <= b["start"] + 0.001 for a, b in zip(words, words[1:])) and (
        normalize("".join(word["word"] for word in words)) == normalize(segment["text"])
    )


def anchor_result(anchor, raw, hypothesis):
    lo, hi = anchor["window_seconds"]
    overlapping = [s for s in raw if s["end"] >= lo and s["start"] <= hi]
    contained = [s for s in overlapping if lo <= s["start"] <= s["end"] <= hi]
    parents = [s for s in overlapping if bound_words(s)]
    word_text = "".join(w["word"] for s in parents for w in s["words"]
                        if lo <= w["start"] <= w["end"] <= hi)
    segment_text = " ".join(s["text"] for s in contained)
    pattern = anchor.get("normalized_pattern", anchor.get("pattern"))
    return {
        **anchor,
        "phrase_present_in_saved_hypothesis": bool(re.search(pattern, normalize(hypothesis))),
        "strict_segment_window_pass": bool(re.search(pattern, normalize(segment_text))),
        "actual_word_window_pass": bool(re.search(pattern, normalize(word_text))),
        "contained_segment_text": segment_text.strip(),
        "actual_word_window_text": word_text.strip(),
        "overlapping_raw_segments": [{k: s[k] for k in ("start", "end", "text", "words")}
                                     for s in overlapping],
    }


def audit_film(root, film, plan, execution):
    path = root / (film + "-report.json")
    report = json.loads(path.read_text())
    fixture = plan["films"][film]
    protocol = report["alignment_only_protocol"]
    audio = protocol["complete_audio_evidence"]
    events = protocol["events"]
    raw = audio["raw_segment_constructions"]
    require(report["complete"] and report["counts"] == {"pass": 1}, "incomplete structural run")
    require(len(report["cases"]) == 1, "unexpected case count")
    case = report["cases"][0]
    require(case["id"] == film, "case identity")
    require(protocol["film"] == film and protocol["plan_sha256"] == FROZEN_PLAN_SHA256, "frozen plan identity")
    require(protocol["runner_sha256"] == plan["runner_sha256"], "runner identity")
    require(protocol["qa_random_seed"] == fixture["qa_random_seed"], "seed identity")
    require(protocol["provider_gate_exercised"] is False, "provider scope")
    require(protocol["reference_supplied_to_decoder"] is False
            and protocol["production_options_changed_by_wrapper"] is False, "observer scope")
    require(report["source_sha256"]["app.py"] == plan["candidate"]["app_sha256"], "candidate source identity")
    require(report["source_files_unchanged_during_run"] and
            report["source_sha256"] == report["source_sha256_after"], "source changed during inference")
    require(report["manifest_sha256"] == fixture["fixture_manifest_sha256"], "fixture identity")
    require(case["audio_sha256"] == fixture["source_identity"]["media_sha256"], "acquired media identity")
    require(audio["same_decoded_array_passed_to_asr"], "complete audio not retained")
    for key in ("pcm_sha256", "sample_count", "shape", "dtype"):
        require(audio["decoded_array"][key] == fixture["source_identity"][key], "PCM " + key)
    duration = fixture["source_identity"]["decoded_duration_seconds"]
    require(audio["decoded_duration_seconds"] == audio["post_vad_duration_seconds"] == duration,
            "full recording duration")
    require(all(event["job_id"] == case["job_id"] for event in events), "event job identity")
    require(all(a["at"] <= b["at"] for a, b in zip(events, events[1:])), "event chronology")
    singles = {}
    for kind in ("recognition_start", "audio_decoded", "asr_model_resolved", "transcribe_request",
                 "transcribe_info", "recognition_done"):
        matches = [event for event in events if event["kind"] == kind]
        require(len(matches) == 1, "event count: " + kind)
        singles[kind] = matches[0]
    require([e["segment"] for e in events if e["kind"] == "asr_segment_created"] == raw,
            "raw segment/event equality")
    require(singles["recognition_done"]["segment_count"] == len(raw), "raw count")
    require(singles["recognition_start"]["qa_random_seed"] == fixture["qa_random_seed"], "actual seed")
    decoded, request, info = (singles[k] for k in ("audio_decoded", "transcribe_request", "transcribe_info"))
    require(decoded["sampling_rate_hz"] == 16000 and decoded["decoded_arrays"] == [audio["decoded_array"]],
            "actual decode rate/array")
    require(request["audio_array"] == audio["decoded_array"], "actual transcribe array")
    require(info["info"] == audio["normal_transcribe_info"], "actual effective metadata")
    require(info["info"]["duration"] == info["info"]["duration_after_vad"] == duration,
            "actual effective duration")
    require(info["info"]["language"] == case["job_result"]["language"] == "en", "actual language")
    options = request["resolved_options"]
    expected = {"language": None, "task": "transcribe", "beam_size": 5, "vad_filter": False,
                "no_speech_threshold": 0.6, "condition_on_previous_text": False,
                "word_timestamps": True, "hallucination_silence_threshold": None,
                "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], "initial_prompt": None,
                "prefix": None, "hotwords": None, "clip_timestamps": "0",
                "log_prob_threshold": -1.0, "compression_ratio_threshold": 2.4}
    for key, value in expected.items():
        require(options[key] == value, "actual request " + key)
    effective = info["info"]["transcription_options"]
    for key in ("beam_size", "no_speech_threshold", "condition_on_previous_text", "word_timestamps",
                "hallucination_silence_threshold", "initial_prompt", "prefix", "hotwords",
                "log_prob_threshold", "compression_ratio_threshold"):
        require(effective[key] == options[key], "effective policy " + key)
    require(effective["temperatures"] == options["temperature"], "effective fallback policy")
    require(request["explicit_kwargs"] == audio["normal_explicit_transcribe_kwargs"], "explicit options")
    resolved = singles["asr_model_resolved"]
    require(resolved["at"] <= request["at"] and resolved["identity_complete"], "model resolution order")
    require(resolved["resolved_revision"] == plan["model_revision"] and
            resolved["files"]["model.bin"]["sha256"] == plan["model_bin_sha256"], "actual Small weights")
    # Prefer retained evidence next to the report; the original absolute path is only a fallback.
    artifact_dir = root / Path(report["artifacts_directory"]).name
    if not artifact_dir.is_dir():
        artifact_dir = Path(report["artifacts_directory"])
    saved_path = artifact_dir / "jobs" / case["job_id"] / "transcript.json"
    saved = json.loads(saved_path.read_text())
    projection = [{"start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip()}
                  for s in raw if s["text"].strip()]
    require(projection == saved["segments"] == case["segments"], "raw/report/saved equality")
    with sqlite3.connect("file:" + str(artifact_dir / "library.sqlite3") + "?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT id, segments FROM transcripts").fetchall()
    require(len(rows) == 1 and rows[0][0] == case["job_id"] and json.loads(rows[0][1]) == projection,
            "retained SQLite equality")
    require(report["separate_process_sqlite_matches"] is True and all(case["checks"].values()),
            "normal pipeline checks")
    export_dir = artifact_dir / film
    exported = json.loads((export_dir / "transcript.json").read_text())
    require(exported["segments"] == projection, "actual exported JSON equality")
    for ext, identity in case["exports"].items():
        export_path = export_dir / ("transcript." + ext)
        require(sha(export_path) == identity["sha256"] and export_path.stat().st_size == identity["bytes"],
                "actual export identity: " + ext)
    with zipfile.ZipFile(export_dir / "transcript.zip") as archive:
        for ext in ("txt", "srt", "vtt", "json"):
            matches = [name for name in archive.namelist() if name.endswith("." + ext)]
            require(len(matches) == 1 and archive.read(matches[0]) == (export_dir / ("transcript." + ext)).read_bytes(),
                    "actual ZIP member: " + ext)
    arm = next(arm for arm in execution["arms"] if arm["film"] == film)
    require(arm["returncode"] == 0 and arm["stopped_at_limit"] is None, "execution failed or hit limit")
    require(arm["harness_process_peak_rss_bytes"] == report["process_peak_rss_bytes"], "RSS report binding")
    for key in ("observed_process_group_peak_rss_bytes", "harness_process_peak_rss_bytes"):
        require(0 < arm[key] <= plan["process_group_rss_limit_bytes"], "RSS limit")
    elapsed = (datetime.fromisoformat(arm["finished_at"]) - datetime.fromisoformat(arm["started_at"])).total_seconds()
    require(0 < elapsed <= plan["per_process_wall_timeout_seconds"], "process wall limit")
    require(0 < singles["recognition_done"]["elapsed_seconds"] <= plan["per_inference_timeout_seconds"], "recognition limit")
    anchors = [anchor_result(a, raw, case["hypothesis"]) for a in fixture.get("existing_four_anchors", [])]
    omissions = [anchor_result(a, raw, case["hypothesis"]) for a in fixture.get("new_omission_regressions", [])]
    return {
        "report_sha256": sha(path), "job_id": case["job_id"], "saved_transcript_path": str(saved_path),
        "saved_transcript_sha256": sha(saved_path), "app_sha256": report["source_sha256"]["app.py"],
        "full_pcm_model_policy_source_consistency_pass": True,
        "raw_saved_sqlite_exported_segments_equal": True, "normal_pipeline_checks": case["checks"],
        "separate_process_sqlite_matches": True, "application_server_restart_exercised": False,
        "segment_count": len(raw), "upload_harness_elapsed_seconds": report["elapsed_seconds"],
        "recognizer_elapsed_seconds": singles["recognition_done"]["elapsed_seconds"],
        "process_elapsed_seconds": round(elapsed, 3),
        "process_peak_rss_bytes": report["process_peak_rss_bytes"],
        "sampled_process_group_peak_rss_bytes": arm["observed_process_group_peak_rss_bytes"],
        "actual_explicit_options": audio["normal_explicit_transcribe_kwargs"],
        "four_original_anchors": anchors, "two_predeclared_omission_regressions": omissions,
        "risk_window_output": [{"window_seconds": [lo, hi],
             "segments": [s for s in projection if s["end"] >= lo and s["start"] <= hi]}
             for lo, hi in fixture.get("known_risk_windows_seconds", [])],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve existing audits; select a new output file.")
    require(sha(args.plan) == FROZEN_PLAN_SHA256, "accepted plan changed")
    plan = json.loads(args.plan.read_text())
    execution = json.loads((args.root / "execution.json").read_text())
    require(execution["plan_sha256"] == FROZEN_PLAN_SHA256, "execution plan mismatch")
    require([arm["film"] for arm in execution["arms"]] == plan["execution_order"], "one run per film in frozen order")
    total = (datetime.fromisoformat(execution["arms"][-1]["finished_at"]) -
             datetime.fromisoformat(execution["arms"][0]["started_at"])).total_seconds()
    require(0 < total <= plan["total_execution_timeout_seconds"], "total execution limit")
    result = {"reviewed_at": datetime.now(timezone.utc).isoformat(), "analysis_sha256": sha(__file__),
              "plan_sha256": FROZEN_PLAN_SHA256, "execution_sha256": sha(args.root / "execution.json"),
              "provider_gate_exercised": False, "semantic_accuracy_approved": False,
              "subtitle_accuracy_approved": False, "general_speech_preservation_approved": False,
              "scope": "Actual retained full-audio upload results, frozen anchors, and persistence consistency only; full-reference review is separate.",
              "total_process_wall_seconds": round(total, 3), "films": {}}
    for film in plan["execution_order"]:
        result["films"][film] = audit_film(args.root, film, plan, execution)
    official = result["films"]["official_tears_of_steel"]
    for label, key in (("four_original_anchors_preserved", "four_original_anchors"),
                       ("two_predeclared_commands_restored", "two_predeclared_omission_regressions")):
        result[label] = all(a["phrase_present_in_saved_hypothesis"] and a["strict_segment_window_pass"]
                            and a["actual_word_window_pass"] for a in official[key])
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: result[key] for key in ("four_original_anchors_preserved",
          "two_predeclared_commands_restored", "semantic_accuracy_approved", "provider_gate_exercised")}))


if __name__ == "__main__":
    main()

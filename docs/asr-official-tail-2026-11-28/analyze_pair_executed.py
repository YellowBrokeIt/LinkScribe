"""Read-only audit of the two predeclared official-film ASR arms."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(text):
    return " ".join(re.findall(r"[^\W_]+", text.casefold().replace("’", "'").replace("'", "")))


def bound_words(segment):
    words = segment.get("words") or []
    return bool(words) and all(
        all(isinstance(word.get(k), (int, float)) and math.isfinite(word[k]) for k in ("start", "end"))
        and segment["start"] - 0.5 <= word["start"] <= word["end"] <= segment["end"] + 0.5
        for word in words) and all(a["end"] <= b["start"] + 0.001 for a, b in zip(words, words[1:])) \
        and normalize("".join(word["word"] for word in words)) == normalize(segment["text"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve prior evidence; choose a new audit file.")
    plan = json.loads((args.root / "plan.json").read_text())
    result = {"reviewed_at": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(args.root / "plan.json"),
              "analysis_sha256": sha(__file__), "provider_gate_exercised": False,
              "semantic_accuracy_approved": False, "subtitle_accuracy_approved": False,
              "scope": "One complete official-film rendition; four frozen reference anchors and normal persistence/export checks.",
              "arms": {}}
    for arm in ("baseline", "aligned"):
        path = args.root / (arm + "-report.json")
        report = json.loads(path.read_text())
        assert report["complete"] and report["counts"] == {"pass": 1}
        case = report["cases"][0]
        protocol = report["official_tail_protocol"]
        evidence = protocol["complete_audio_evidence"]
        events, raw = protocol["events"], evidence["raw_segment_constructions"]
        assert protocol["plan_sha256"] == result["plan_sha256"]
        assert report["source_sha256"]["app.py"] == plan["arms"][arm]["app_sha256"]
        assert report["source_files_unchanged_during_run"]
        assert evidence["same_decoded_array_passed_to_asr"]
        for key in ("pcm_sha256", "sample_count", "shape", "dtype"):
            assert evidence["decoded_array"][key] == plan["source_identity"][key]
        assert evidence["decoded_duration_seconds"] == evidence["post_vad_duration_seconds"] == 734.0
        requests = [event for event in events if event["kind"] == "transcribe_request"]
        assert len(requests) == 1
        options = requests[0]["resolved_options"]
        assert options["clip_timestamps"] == "0" and options["vad_filter"] is False
        assert all(options[key] is None for key in ("initial_prompt", "prefix", "hotwords", "language"))
        assert options["temperature"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        assert options["word_timestamps"] is (arm == "aligned")
        assert options["hallucination_silence_threshold"] == (2.0 if arm == "aligned" else None)
        resolved = [event for event in events if event["kind"] == "asr_model_resolved"]
        assert len(resolved) == 1 and resolved[0]["identity_complete"]
        assert resolved[0]["resolved_revision"] == plan["model_revision"]
        assert resolved[0]["files"]["model.bin"]["sha256"] == plan["model_bin_sha256"]
        artifact_dir = Path(report["artifacts_directory"])
        saved_path = artifact_dir / "jobs" / case["job_id"] / "transcript.json"
        saved = json.loads(saved_path.read_text())
        constructed = [{"start": round(segment["start"], 3), "end": round(segment["end"], 3),
                        "text": segment["text"].strip()} for segment in raw if segment["text"].strip()]
        assert constructed == [{key: segment[key] for key in ("start", "end", "text")}
                               for segment in saved["segments"]] == case["segments"]
        with sqlite3.connect("file:" + str(artifact_dir / "library.sqlite3") + "?mode=ro", uri=True) as connection:
            stored = connection.execute("SELECT segments FROM transcripts WHERE id=?", (case["job_id"],)).fetchone()
        assert json.loads(stored[0]) == saved["segments"] and report["separate_process_sqlite_matches"]
        anchors = []
        for anchor in plan["independent_reference_anchors"]:
            lo, hi = anchor["window_seconds"]
            contained = [segment for segment in raw if lo <= segment["start"] <= segment["end"] <= hi]
            overlapping = [segment for segment in raw if segment["start"] <= hi and segment["end"] >= lo]
            segment_text = " ".join(segment["text"] for segment in contained)
            parents = [segment for segment in overlapping if bound_words(segment)]
            word_text = "".join(word["word"] for segment in parents for word in segment["words"]
                                if lo <= word["start"] <= word["end"] <= hi)
            pattern = anchor["normalized_pattern"]
            anchors.append({**anchor,
                "phrase_present_in_normal_transcript": bool(re.search(pattern, normalize(case["hypothesis"]))),
                "strict_segment_window_pass": bool(re.search(pattern, normalize(segment_text))),
                "actual_word_window_pass": bool(re.search(pattern, normalize(word_text))) if arm == "aligned" else None,
                "contained_segment_text": segment_text.strip(), "actual_word_window_text": word_text.strip(),
                "overlapping_raw_segments": [{key: segment[key] for key in ("start", "end", "text", "words")}
                                             for segment in overlapping]})
        done = [event for event in events if event["kind"] == "recognition_done"]
        result["arms"][arm] = {"report_sha256": sha(path), "saved_transcript_sha256": sha(saved_path),
            "app_sha256": report["source_sha256"]["app.py"], "source_unchanged": True,
            "identical_complete_pcm_verified": True, "same_pinned_small_weights_verified": True,
            "raw_saved_sqlite_segments_match": True, "separate_process_sqlite_matches": True,
            "normal_export_checks": case["exports"], "segment_count": len(raw),
            "upload_harness_elapsed_seconds": report["elapsed_seconds"],
            "recognizer_elapsed_seconds": done[0]["elapsed_seconds"],
            "process_peak_rss_bytes": report["process_peak_rss_bytes"],
            "actual_explicit_options": evidence["normal_explicit_transcribe_kwargs"], "anchors": anchors}
    candidate = result["arms"]["aligned"]["anchors"]
    result["candidate_four_reference_anchors_preserved"] = all(
        anchor["strict_segment_window_pass"] and anchor["actual_word_window_pass"] for anchor in candidate)
    result["baseline_four_phrases_present"] = all(
        anchor["phrase_present_in_normal_transcript"] for anchor in result["arms"]["baseline"]["anchors"])
    result["baseline_strict_segment_window_count"] = sum(
        anchor["strict_segment_window_pass"] for anchor in result["arms"]["baseline"]["anchors"])
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: result[key] for key in ("candidate_four_reference_anchors_preserved",
        "baseline_four_phrases_present", "baseline_strict_segment_window_count", "provider_gate_exercised")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Explicit CPU speaker evaluation using licensed, locally prepared real voices.

No dataset or package downloads occur here. The optional speaker backend can
fetch its pinned public weights on first use. Source identities are used only
to construct and score controlled fixtures, never passed to diarize_audio.
This is not a meeting diarization benchmark or an overlap quality claim.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diarization import DiarizationConfig, diarize_audio, decode_mono, SAMPLE_RATE


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_wav(path, audio):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def prepare_fixtures(source_path, work_dir):
    if source_path.stat().st_size > 1024 * 1024:
        raise ValueError("Source manifest exceeds 1 MiB.")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    identities = list(source["speakers"])
    if len(identities) != 3 or not source.get("license") or not source.get("attribution"):
        raise ValueError("Provide three licensed speaker identities with attribution.")
    clips = {}
    seen_sources = set()
    for identity in identities:
        entries = source["speakers"][identity]
        if len(entries) < 3:
            raise ValueError("Three distinct source utterances per speaker are required.")
        clips[identity] = []
        for entry in entries[:3]:
            path = Path(entry["path"])
            if path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Source clip exceeds the 20 MiB fixture limit.")
            actual_digest = digest(path)
            if actual_digest != entry["sha256"]:
                raise ValueError(f"Source fingerprint changed: {path.name}")
            if actual_digest in seen_sources:
                raise ValueError("Every source utterance must have a distinct audio hash, including across speakers.")
            seen_sources.add(actual_digest)
            audio = decode_mono(path, 30)
            if len(audio) < 4 * SAMPLE_RATE:
                raise ValueError("Controlled source utterances must last at least four seconds.")
            clips[identity].append(audio[:8 * SAMPLE_RATE])
    work_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []

    def sequence(case_id, specification, kind="clean", gap=0.6):
        audio_parts = [np.zeros(round(0.5 * SAMPLE_RATE), dtype=np.float32)]
        offset = len(audio_parts[0])
        references = []
        for identity, clip_index, short in specification:
            audio = clips[identity][clip_index]
            if short:
                audio = audio[round(1.5 * SAMPLE_RATE):round(2.05 * SAMPLE_RATE)]
            references.append({"start": offset / SAMPLE_RATE,
                               "end": (offset + len(audio)) / SAMPLE_RATE,
                               "speaker": identity, "short": short})
            audio_parts.extend([audio, np.zeros(round(gap * SAMPLE_RATE), dtype=np.float32)])
            offset += len(audio) + len(audio_parts[-1])
        path = work_dir / f"{case_id}.wav"
        joined = np.concatenate(audio_parts)
        write_wav(path, joined)
        fixtures.append({"id": case_id, "kind": kind, "path": str(path.resolve()),
                         "sha256": digest(path), "duration": len(joined) / SAMPLE_RATE,
                         "expected_speakers": len({part[0] for part in specification}),
                         "reference_intervals": references})

    a, b, c = identities
    sequence("one_speaker", [(a, 0, False), (a, 1, False), (a, 2, False)])
    sequence("two_speakers_returning", [(a, 0, False), (b, 0, False),
                                        (a, 1, False), (b, 1, False)])
    sequence("three_speakers_returning", [(a, 0, False), (b, 0, False), (c, 0, False),
                                          (a, 1, False), (c, 1, False), (b, 1, False)])
    sequence("short_only", [(b, 2, True)], "abstention")
    sequence("short_turn_stress", [(a, 1, False), (b, 2, True), (a, 2, False)], "stress")
    silence_path = work_dir / "silence.wav"
    write_wav(silence_path, np.zeros(4 * SAMPLE_RATE, dtype=np.float32))
    fixtures.append({"id": "silence", "kind": "silence", "path": str(silence_path.resolve()),
                     "sha256": digest(silence_path), "duration": 4, "expected_speakers": 0,
                     "reference_intervals": []})
    width = min(len(clips[a][1]), len(clips[b][1]))
    overlap = (clips[a][1][:width] + clips[b][1][:width]) * 0.45
    overlap_path = work_dir / "overlap_stress.wav"
    write_wav(overlap_path, np.concatenate([np.zeros(8000), overlap, np.zeros(8000)]))
    fixtures.append({"id": "overlap_stress", "kind": "stress", "path": str(overlap_path.resolve()),
                     "sha256": digest(overlap_path), "duration": width / SAMPLE_RATE + 1,
                     "expected_speakers": 2, "reference_intervals": [
                         {"start": 0.5, "end": width / SAMPLE_RATE + 0.5,
                          "speakers": [a, b], "overlap": True}]})
    manifest = {"schema_version": 1, "source": source, "source_manifest_sha256": digest(source_path),
                "construction": "Real recorded utterances, capped at eight seconds; 0.6-second inserted gaps. "
                                "Returning speakers use different utterances. No oracle count reaches inference.",
                "limitations": ["Read English speech, not natural meetings or Greek speech.",
                                "Concatenation gaps simplify speaker boundaries.",
                                "Source-clip interiors include natural pauses; metrics are controlled-fixture indicators, not DER.",
                                "Short-turn and overlap stress cases do not establish supported overlap accuracy."],
                "cases": fixtures}
    save(work_dir / "fixtures.json", manifest)
    return manifest


def label_at(turns, moment):
    return next((turn["speaker"] for turn in turns
                 if turn["start"] <= moment < turn["end"]), None)


def score(case, result):
    turns = result["turns"]
    if result["overlapping_speech_supported"] is not False:
        return {"status": "failed", "reason": "Backend incorrectly claims overlap support."}
    if case["kind"] == "silence":
        passed = not turns and result["speaker_count"] == 0
        return {"status": "passed" if passed else "failed", "detected_turns": len(turns)}
    if case["kind"] == "abstention":
        assigned = sum(turn["end"] - turn["start"] for turn in turns if turn["speaker"] is not None)
        return {"status": "passed" if assigned == 0 else "failed", "assigned_seconds": assigned,
                "meaning": "Too little evidence must not establish an identity."}
    if case["id"] == "overlap_stress":
        return {"status": "observed_unsupported_stress", "reported_speakers": result["speaker_count"],
                "meaning": "Mixed audio is outside this backend's supported accuracy; no pass is inferred."}

    references = case["reference_intervals"]
    truth = sorted({item["speaker"] for item in references if not item.get("short")})
    predicted = sorted({item["speaker"] for item in turns if item["speaker"] is not None})
    matrix = np.zeros((len(truth), len(predicted)), dtype=int)
    total = 0
    assigned = 0
    per_interval = []
    for item in references:
        if item.get("short"):
            moments = np.arange(item["start"], item["end"], 0.05)
            per_interval.append({"reference": item, "assigned_fraction":
                                 sum(label_at(turns, value) is not None for value in moments) / len(moments)})
            continue
        moments = np.arange(item["start"] + 0.75, item["end"] - 0.75, 0.1)
        counts = {}
        for moment in moments:
            total += 1
            label = label_at(turns, float(moment))
            counts[str(label)] = counts.get(str(label), 0) + 1
            if label is not None:
                assigned += 1
                matrix[truth.index(item["speaker"]), predicted.index(label)] += 1
        per_interval.append({"reference": item, "core_samples": len(moments), "label_counts": counts})
    from scipy.optimize import linear_sum_assignment
    rows, columns = linear_sum_assignment(-matrix)
    correct = int(matrix[rows, columns].sum())
    coverage = assigned / total if total else 0
    purity = correct / assigned if assigned else 0
    passed = (result["speaker_count"] == case["expected_speakers"] and
              coverage >= 0.80 and purity >= 0.95)
    return {"status": "observed_unsupported_stress" if case["kind"] == "stress" else
                      "passed" if passed else "failed",
            "expected_speakers_for_scoring_only": case["expected_speakers"],
            "reported_speakers": result["speaker_count"], "core_samples": total,
            "assigned_core_fraction": round(coverage, 4),
            "permutation_matched_label_purity": round(purity, 4),
            "correctly_attributed_core_fraction": round(correct / total if total else 0, 4),
            "mapping_for_scoring_only": {predicted[column]: truth[row] for row, column in zip(rows, columns)},
            "per_interval": per_interval}


def main(argv=None):
    # Only the actual Linux CPU run needs POSIX peak-RSS accounting; fixture
    # validation and scoring helpers are also imported by Windows unit tests.
    import resource

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True, help="Licensed source manifest with actual file hashes.")
    parser.add_argument("--work-dir", type=Path, required=True, help="QA-only fixture output directory.")
    parser.add_argument("--cache-dir", type=Path, required=True, help="Pinned public speaker-model cache.")
    parser.add_argument("--output", type=Path, required=True, help="Atomic checkpoint/evidence JSON.")
    parser.add_argument("--case", action="append", default=[], help="Optional exact fixture ID, repeatable.")
    args = parser.parse_args(argv)
    started = time.monotonic()
    report = {"schema_version": 1, "run_id": str(uuid.uuid4()), "complete": False,
              "created_utc": datetime.now(timezone.utc).isoformat(), "results": [],
              "evaluation": "Controlled real-voice CPU smoke, not a meeting benchmark.",
              "acceptance": {"clean_expected_count_matches": True, "minimum_assigned_core_fraction": 0.80,
                             "minimum_permutation_matched_label_purity": 0.95,
                             "short_and_silence_must_not_establish_speaker": True},
              "code_sha256": {name: digest(ROOT / name) for name in
                              ("diarization.py", "tests/smoke_real_speakers.py")},
              "settings": asdict(DiarizationConfig()), "requested_ids": args.case}
    save(args.output, report)
    try:
        manifest = prepare_fixtures(args.sources, args.work_dir)
        available = {case["id"] for case in manifest["cases"]}
        if len(set(args.case)) != len(args.case) or set(args.case) - available:
            raise ValueError("Duplicate or unknown case selection.")
        cases = [case for case in manifest["cases"] if not args.case or case["id"] in args.case]
        report.update({"requested_ids": [case["id"] for case in cases], "requested_count": len(cases),
                       "completed_count": 0, "corpus_complete": False,
                       "fixture_manifest": str((args.work_dir / "fixtures.json").resolve()),
                       "fixture_manifest_sha256": digest(args.work_dir / "fixtures.json")})
        save(args.output, report)
        for case in cases:
            item = {"id": case["id"], "kind": case["kind"], "audio_sha256": case["sha256"]}
            case_started = time.monotonic()
            try:
                # No source identity, expected count, or scoring metadata enters inference.
                result = diarize_audio(case["path"], cache_dir=args.cache_dir)
                item.update({"result": result, "assessment": score(case, result)})
            except Exception as exc:
                item.update({"assessment": {"status": "execution_failed"},
                             "error": {"type": type(exc).__name__, "message": str(exc),
                                       "cause": repr(exc.__cause__) if exc.__cause__ else None}})
            item["wall_seconds"] = round(time.monotonic() - case_started, 3)
            item["peak_process_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
            report["results"].append(item)
            report["completed_count"] = len(report["results"])
            save(args.output, report)
            print(json.dumps({"id": case["id"], "status": item["assessment"]["status"],
                              "seconds": item["wall_seconds"], "peak_rss_mib": item["peak_process_rss_mib"]}), flush=True)
        report["complete"] = True
        report["corpus_complete"] = len(cases) == len(manifest["cases"])
    except KeyboardInterrupt:
        report["error"] = {"type": "KeyboardInterrupt", "message": "Interrupted; completed cases retained."}
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["peak_process_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
        save(args.output, report)
    return 0 if report["complete"] and all(item["assessment"]["status"] in
                                          {"passed", "observed_unsupported_stress"}
                                          for item in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

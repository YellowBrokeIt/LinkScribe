"""One offline replay of fixed source/raw-span pairs; no reference input access."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

from boundary_normalizer import propose_person_boundaries

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(entry):
    path = REPO / entry["path"]
    if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
        raise ValueError("Frozen input mismatch: " + entry["path"])
    return path


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-freeze", required=True)
    args = parser.parse_args()
    started = time.monotonic()
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("30-second replay limit")))
    signal.alarm(30)
    report = {"schema_version": 1, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "complete": False, "completed_cases": [], "detector_calls": 0, "translation_calls": 0,
              "masking_calls": 0, "automatic_semantic_acceptance": False, "annotation_input_read": False}
    exit_code = 1
    try:
        freeze_path = Path(args.execution_freeze).resolve()
        freeze = json.loads(freeze_path.read_bytes())
        if freeze.get("approved_scope") != "one_offline_source_boundary_replay":
            raise ValueError("Execution freeze does not authorize the fixed replay scope.")
        for entry in freeze["files"]:
            checked(entry)
        plan_path = checked(freeze["plan"])
        plan = json.loads(plan_path.read_bytes())
        source_path = checked(plan["source_only_input"])
        sources = json.loads(source_path.read_bytes())["cases"]
        if len(sources) != 6 or len(plan["raw_reports"]) != 6:
            raise ValueError("Expected the unchanged original six source/report pairs.")
        report.update(execution_freeze_sha256=sha(freeze_path), plan_sha256=sha(plan_path),
                      source_only_sha256=sha(source_path), python_executable=sys.executable,
                      affinity=sorted(os.sched_getaffinity(0)), source_criteria_or_annotations_supplied_to_normalizer=False)
        for source, entry in zip(sources, plan["raw_reports"]):
            raw_path = checked(entry)
            raw = json.loads(raw_path.read_bytes())
            text = "\n".join(segment["text"] for segment in source["segments"])
            if (raw.get("complete") is not True or raw["id"] != source["id"] or
                    raw["source"]["source_segments"] != source["segments"] or
                    raw["source"]["source_language"] != source["source_language"] or
                    raw["source"]["source_text"] != text or
                    raw["source"]["source_text_sha256"] != hashlib.sha256(text.encode()).hexdigest()):
                raise ValueError("Raw report does not bind the complete original source.")
            value = propose_person_boundaries(source["segments"], raw["raw_entities"], source["source_language"])
            result = {"complete": True, "id": source["id"], "plan_sha256": sha(plan_path),
                      "execution_freeze_sha256": sha(freeze_path), "raw_report_sha256": entry["sha256"],
                      "source_only_sha256": sha(source_path), "normalizer_calls": 1,
                      "semantic_decision": "awaiting_independent_original_annotation_review", "result": value}
            result_path = HERE / (source["id"] + ".json")
            write(result_path, result)
            report["completed_cases"].append({"id": source["id"], "path": str(result_path.relative_to(REPO)),
                                               "sha256": sha(result_path)})
        for entry in [plan["source_only_input"], *plan["raw_reports"], *freeze["files"]]:
            checked(entry)
        report.update(complete=True, frozen_sources_and_prior_reports_unchanged=True)
        exit_code = 0
    except Exception as error:
        report.update(error={"type": type(error).__name__, "message": str(error)})
    finally:
        report.update(finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                      elapsed_seconds=time.monotonic() - started,
                      process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                      child_processes_created=0, exit_code=exit_code)
        write(HERE / "execution.json", report)
        print(json.dumps({key: report[key] for key in ("complete", "elapsed_seconds", "process_peak_rss_mib", "exit_code")}))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

"""Bounded no-model probes of real stop/cleanup and source-span integrity."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sys

from common import HERE, read_plan, save, sha, utc
from native_worker import validate_entities
from run_phase import monitor


def main():
    plan = read_plan()
    private = Path(plan["runtime"]["owned_root"]) / "private"
    output = HERE / "control-probes.json"
    if output.exists():
        raise ValueError("Refusing to overwrite bounded control evidence.")
    results = []
    for name, code, limit, expected in [
        ("normal", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); time.sleep(.2)",
         {"rss_bytes": 256*1024**2, "initialization_seconds": 2, "case_seconds": 2, "total_seconds": 3}, None),
        ("deadline", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); time.sleep(10)",
         {"rss_bytes": 256*1024**2, "initialization_seconds": 2, "case_seconds": 2, "total_seconds": .3}, "aggregate_time_limit"),
        ("memory", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); x=bytearray(128*1024**2); time.sleep(10)",
         {"rss_bytes": 96*1024**2, "initialization_seconds": 2, "case_seconds": 2, "total_seconds": 3}, "process_tree_memory_limit"),
    ]:
        path = HERE / ("control-" + name + ".json")
        result = monitor([sys.executable, "-c", code], os.environ.copy(), private / ("control-" + name + ".log"),
                         path, HERE / ("control-" + name + "-samples.jsonl"), limit,
                         {"purpose": "No-model control; these reduced caps are not candidate settings."})
        ok = (result.get("stop_reason") == expected and result["owned_processes_stopped"]
              and result["measurement_complete"] and result["passed"] == (expected is None))
        results.append({"control": name, "passed": ok, "observed_stop_reason": result.get("stop_reason"),
                        "report": path.name, "sha256": sha(path)})
    prepared = {"source_text": "Zoë saw Zoë.", "segment_offsets": [{"segment_index": 0, "start": 0, "end": 12}]}
    entities = [{"start": 0, "end": 3, "text": "Zoë", "label": "person", "score": .9},
                {"start": 8, "end": 11, "text": "Zoë", "label": "person", "score": .8}]
    valid = validate_entities(entities, prepared)
    results.append({"control": "distinct_repeated_source_occurrences", "passed": len(valid) == 2 and valid[1]["segment_start"] == 8})
    bad_text = copy.deepcopy(entities); bad_text[0]["text"] = "Zoe"
    bad_label = copy.deepcopy(entities); bad_label[0]["label"] = "organization"
    bad_score = copy.deepcopy(entities); bad_score[0]["score"] = float("nan")
    bad_overlap = [entities[0], entities[0]]
    probes = [("nonexact_source", bad_text, prepared), ("wrong_label", bad_label, prepared),
              ("nonfinite_score", bad_score, prepared), ("overlapping_spans", bad_overlap, prepared),
              ("cross_segment", [{"start": 0,"end": 7,"text": "One\nTwo","label":"person","score":.9}],
               {"source_text":"One\nTwo", "segment_offsets":[{"segment_index":0,"start":0,"end":3},{"segment_index":1,"start":4,"end":7}]}),
              ("partial_grapheme", [{"start":0,"end":3,"text":"Zoe","label":"person","score":.9}],
               {"source_text":"Zoe\u0308", "segment_offsets":[{"segment_index":0,"start":0,"end":4}]})]
    for name, raw, source in probes:
        try:
            validate_entities(raw, source)
        except ValueError:
            rejected = True
        else:
            rejected = False
        results.append({"control": name, "passed": rejected})
    report = {"created_at": utc(), "model_imports": 0, "detector_calls": 0, "translation_calls": 0,
              "review_corpus_used": False, "candidate_threshold_or_limits_modified": False,
              "probe_scope": "Three synthetic resource-control workers and source-span integrity only; not detector accuracy.",
              "passed": all(value["passed"] for value in results), "results": results,
              "runner_sha256": sha(HERE / "run_phase.py"), "worker_sha256": sha(HERE / "native_worker.py")}
    save(output, report)
    print(json.dumps({"passed": report["passed"], "controls": len(results), "report": str(output)}))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

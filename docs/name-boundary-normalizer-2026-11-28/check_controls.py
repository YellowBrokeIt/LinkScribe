"""Exercise only predeclared generic controls; no retained detector input read."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import time

from boundary_normalizer import propose_person_boundaries

HERE = Path(__file__).resolve().parent


def limits():
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("30-second control limit")))
    signal.alarm(30)


def main():
    limits()
    started = time.monotonic()
    raw = (HERE / "edge-cases.json").read_bytes()
    cases = json.loads(raw)["cases"]
    results = []
    for case in cases:
        source = copy.deepcopy(case["segments"])
        spans = copy.deepcopy(case["raw_entities"])
        try:
            value = propose_person_boundaries(source, spans, case["source_language"])
            if case.get("expected_error"):
                raise AssertionError("Invalid input was accepted.")
            assert value["source_segments"] == case["segments"] == source
            assert spans == case["raw_entities"]
            assert value["automatic_name_safety_certified"] is False
            assert value["translation_or_masking_performed"] is False
            assert len(value["proposals"]) == len(case["expected"])
            for proposal, original, expected in zip(value["proposals"], spans, case["expected"]):
                assert proposal["raw"] == original
                assert proposal["raw_score"] == original["score"]
                assert proposal["requires_independent_boundary_review"] is True
                assert proposal["proposed_span"]["end"] == original["end"]
                for key in ("status", "reason"):
                    if key in expected:
                        assert proposal[key] == expected[key], (key, proposal[key], expected[key])
                assert proposal["proposed_span"]["text"] == expected["text"]
                assert proposal["proposed_span"]["start"] == expected["start"]
                removed = proposal["removed_from_protection"]
                assert (removed["text"] if removed else None) == expected.get("removed")
                if removed:
                    assert removed["remains_ordinary_source_text"] is True
                    assert removed["text"] + proposal["proposed_span"]["text"] == original["text"]
            result = {"id": case["id"], "mechanical_contract_passed": True, "output": value}
        except ValueError as error:
            result = {"id": case["id"], "mechanical_contract_passed": bool(case.get("expected_error")),
                      "observed_error": str(error)}
        except Exception as error:
            result = {"id": case["id"], "mechanical_contract_passed": False,
                      "observed_error": type(error).__name__ + ": " + str(error)}
        result["semantic_counterexample"] = case.get("semantic_counterexample")
        result["automatic_semantic_acceptance"] = False
        results.append(result)
    passed = all(item["mechanical_contract_passed"] for item in results)
    report = {"complete": True, "controls_sha256": hashlib.sha256(raw).hexdigest(),
              "passed_mechanical_contract": passed, "automatic_semantic_acceptance": False,
              "counterexample_count": sum(bool(item["semantic_counterexample"]) for item in results),
              "elapsed_seconds": time.monotonic() - started, "case_count": len(results), "results": results,
              "detector_calls": 0, "translation_calls": 0, "retained_output_replays": 0}
    with (HERE / "control-results.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("passed_mechanical_contract", "case_count", "counterexample_count")}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

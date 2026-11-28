"""No-model check of the boundary between intended grammar and frozen guards."""
import sys
from build_preparation import source_only_audit
sys.addaudithook(source_only_audit)

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from profile_oracle import accepted

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "krikri-source-spelling-screen-2026-11-28"
GUARD_SHA = "cb78fafb66c8b7810f860b983a2f0de0570464b98c7a3f843b924d0e43cfbf11"


def main():
    path = PRIOR / "protection.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != GUARD_SHA:
        raise ValueError("Frozen compact guard changed.")
    spec = importlib.util.spec_from_file_location("frozen_compact_grammar_boundary_guard", path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    bundles = json.loads((PRIOR / "protection-inputs.json").read_text())["cases"]
    schemas = json.loads((HERE / "schemas.json").read_text())
    matrix = json.loads((HERE / "native-probe-matrix.json").read_text())["probes"]
    checks = []
    for record, schema in zip(bundles, schemas):
        if record["id"] != schema["id"]:
            raise ValueError("Source order changed.")
        case_probes = {p["kind"]: p for p in matrix if p["case_id"] == record["id"]}
        for kind, expect_restore in [("all-order-0", True), ("normalization-lookalike", False),
                                     ("unconstrained-ordinary-prose", True)]:
            probe = case_probes[kind]
            if not accepted(probe["raw_json"], schema["layout"]):
                raise ValueError("Probe no longer matches the intended raw-body profile.")
            strings = guard.strict_response_strings(probe["raw_json"], 2)
            segments = copy.deepcopy(record["bundle"]["source_segments"])
            for segment, text in zip(segments, strings):
                segment["text"] = text
            try:
                restored, audit = guard.restore_segments(record["bundle"], segments)
                actual, reason = True, None
                if any({k:v for k,v in before.items() if k != "text"} != {k:v for k,v in after.items() if k != "text"}
                       for before, after in zip(record["bundle"]["source_segments"], restored)):
                    raise ValueError("Source metadata changed.")
            except ValueError as error:
                actual, reason = False, str(error)
            checks.append({"id": record["id"] + ":" + kind,
                           "intended_profile_accepts": True,
                           "expected_frozen_guard_accepts": expect_restore,
                           "actual_frozen_guard_accepts": actual, "reason": reason,
                           "passed": actual == expect_restore,
                           "native_or_semantic_acceptance_inferred": False})
    result = {"schema_version": 1, "passed": all(c["passed"] for c in checks),
              "guard_sha256": GUARD_SHA, "checks": checks,
              "normalizer_detector_model_native_tokenizer_converter_calls": 0,
              "frozen_pure_guard_imported_without_detector_or_normalizer_execution": True,
              "meaning_validation_remains_independent": True}
    with (HERE / "guard-boundary-control-results.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "native_calls": 0}))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

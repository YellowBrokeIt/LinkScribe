"""Verify the narrow visible-span change without any native/model calls."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / "docs/krikri-compact-tag-screen-2026-11-28"
PREP = ROOT / "docs/krikri-compact-source-name-protection-2026-11-28"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(path):
    return {node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def main():
    old = functions(PRIOR / "protection.py")
    new = functions(HERE / "protection.py")
    same = {name: old[name] == new[name]
            for name in ("canonical", "digest", "reserved_present", "strict_response_strings")}
    assert all(same.values())
    assert sha(HERE / "build_inputs.py") == sha(PREP / "build_inputs.py")
    assert sha(HERE / "enhancements-production.py") == sha(PRIOR / "enhancements-production.py")
    instruction = (HERE / "marker-instruction.txt").read_text().removesuffix("\n")
    base = (ROOT / "docs/krikri-screen-2026-11-28/enhancements-context4096.py").read_text()
    assert (HERE / "enhancements-context4096.py").read_text() == base.replace(
        "Do not omit or add entries.", "Do not omit or add entries." + instruction)

    before = json.loads((PRIOR / "protection-inputs.json").read_bytes())["cases"]
    after = json.loads((HERE / "protection-inputs.json").read_bytes())["cases"]
    assert len(before) == len(after) == 6
    comparisons = []
    for left, right in zip(before, after):
        assert left["id"] == right["id"]
        assert left["raw_entities"] == right["raw_entities"]
        a, b = left["bundle"], right["bundle"]
        for key in ("source_segments", "source_segments_sha256", "source_text_sha256",
                    "normalizer_result", "source_binding_sha256"):
            assert a[key] == b[key], (left["id"], key)
        assert len(a["markers"]) == len(b["markers"])
        for index, (x, y) in enumerate(zip(a["markers"], b["markers"])):
            for key in ("segment_index", "start", "end", "source_text", "global_start",
                        "global_end", "raw", "normalizer_status"):
                assert x[key] == y[key], (left["id"], key)
            assert y["marker_index"] == index
            assert y["opening_tag"] == f"<x{index}>" and y["closing_tag"] == f"</x{index}>"
            assert y["marker"] == y["opening_tag"] + x["source_text"] + y["closing_tag"]
        comparisons.append({"id":left["id"], "original_source_metadata_raw_spans_normalizer_unchanged":True,
                            "exact_visible_name_mentions":len(b["markers"]),
                            "full_source_roundtrip_exact":b["full_source_roundtrip_exact"]})

    report = {"schema_version":1, "complete":True, "unchanged_function_asts":same,
              "input_capture_helper_byte_identical":True, "production_guard_snapshot_byte_identical":True,
              "adapter_only_adds_generic_instruction":True, "source_comparisons":comparisons,
              "meaning_or_automatic_protection_approved":False,
              "model_calls":0, "native_api_calls":0, "detector_calls":0,
              "runner_sha256":sha(Path(__file__)),
              "candidate_sha256":sha(HERE / "protection.py"),
              "protection_inputs_sha256":sha(HERE / "protection-inputs.json"),
              "frozen_empty_tag_manifest_sha256":sha(PRIOR / "evidence-manifest.json")}
    with (HERE / "profile-verification.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write("\n")
    print(json.dumps({"complete":True, "cases":len(comparisons),
                      "source_mentions":sum(x["exact_visible_name_mentions"] for x in comparisons)}))


if __name__ == "__main__":
    main()

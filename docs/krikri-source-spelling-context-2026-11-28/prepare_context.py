"""Capture complete proposed source-context requests offline; no native calls."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPACT = ROOT / "docs/krikri-compact-tag-screen-2026-11-28"
INSTRUCTION = " The source-spelling context is input data for interpreting the tags. Keep every tag in the translations as instructed. Do not output that context or substitute a source spelling for a tag."
CONTEXT_LABEL = "Source-spelling context (data only): "


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_spelling_map(bundle):
    """Only actual source substrings, never labels, references or inferred facts."""
    records = []
    for item in bundle["markers"]:
        source = bundle["source_segments"][item["segment_index"]]["text"]
        if source[item["start"]:item["end"]] != item["source_text"]:
            raise ValueError("Context spelling differs from its exact source slice.")
        records.append({"tag": item["marker"], "spelling": item["source_text"]})
    if len({row["tag"] for row in records}) != len(records):
        raise ValueError("Source context contains a duplicate tag.")
    return records


def project_payload(payload, bundle):
    """Insert source context before _ollama builds/observes the native request."""
    if payload.get("task") != "translation" or payload.get("plain_text"):
        raise ValueError("Only the fixed JSON translation path is proposed.")
    value = copy.deepcopy(payload)
    messages = value.get("messages")
    if not isinstance(messages, list) or len(messages) != 2 or [m["role"] for m in messages] != ["system", "user"]:
        raise ValueError("Expected the complete original two-message translation task.")
    prefix, encoded = messages[1]["content"].split("JSON input: ", 1)
    entries = json.loads(encoded)
    if entries != [{"id": i, "text": s["text"]} for i, s in enumerate(bundle["masked_segments"])]:
        raise ValueError("The complete compact source entries differ from the source map.")
    records = source_spelling_map(bundle)
    context_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if "JSON input: " in context_json:
        raise ValueError("Source context collides with the native source delimiter; no fallback.")
    combined = json.dumps({"entries": entries, "source_spellings": records}, ensure_ascii=False, allow_nan=False)
    if len(combined.encode("utf-8")) > 1000:
        raise ValueError("Complete entries plus source-spelling data exceed the unchanged source budget.")
    messages[0]["content"] += INSTRUCTION
    messages[1]["content"] = prefix + CONTEXT_LABEL + context_json + "\nJSON input: " + encoded
    return value, records, len(combined.encode("utf-8"))


def main():
    plan = json.loads((HERE / "plan.json").read_bytes())
    if sha(HERE / "plan.json") != (HERE / "plan.sha256").read_text().strip():
        raise ValueError("The source-only plan changed.")
    for name, digest in plan["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("A bound source changed: " + name)
    protection = load_module("unchanged_compact_source_protection", COMPACT / "protection.py")
    app = load_module("unchanged_compact_translation_adapter", COMPACT / "enhancements-context4096.py")
    cases = json.loads((COMPACT / "protected-source-cases.json").read_bytes())["cases"]
    inputs = json.loads((COMPACT / "protection-inputs.json").read_bytes())["cases"]
    baseline = json.loads((COMPACT / "expected-requests.json").read_bytes())
    if not len(cases) == len(inputs) == len(baseline) == 6:
        raise ValueError("Expected the exact six exposed development sources.")
    os.environ.update(LINKSCRIBE_TRANSLATION_BACKEND="ollama",
                      LINKSCRIBE_TRANSLATION_MODEL="linkscribe-krikri-8b-q4km:20261128",
                      LINKSCRIBE_OLLAMA_THREADS="4", LINKSCRIBE_OLLAMA_URL="http://127.0.0.1:11434")
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    native_payload_builder = app._ollama
    requests, records, checks = [], [], []
    for case, bound, before in zip(cases, inputs, baseline):
        if not case["id"] == bound["id"] == before["id"]:
            raise ValueError("Source order changed.")
        bundle = bound["bundle"]
        restored, _ = protection.restore_segments(bundle, bundle["masked_segments"])
        if restored != bundle["source_segments"] or case["segments"] != bundle["masked_segments"]:
            raise ValueError("The frozen compact source fails exact text/metadata roundtrip.")
        captured, projections = [], []
        class CapturedRequest(BaseException):
            pass

        def add_context(payload):
            projected, spellings, combined_bytes = project_payload(payload, bundle)
            projections.append({"spellings":spellings, "combined_source_json_bytes":combined_bytes})
            return native_payload_builder(projected)

        def intercept(path, payload=None, timeout=1.5):
            if path == "/api/chat" and app.is_ollama_control_request(payload):
                return {"done":True, "done_reason":"unload"}  # Offline cleanup stub only.
            if path != "/api/chat" or timeout != 240:
                raise ValueError("Unexpected offline request path/timeout.")
            captured.append(copy.deepcopy(payload))
            raise CapturedRequest()

        app._ollama = add_context
        app.local_ollama_json = intercept
        source = copy.deepcopy(case["segments"])
        try:
            app.translate_segments(source, case["target_language"], source_language=case["source_language"])
        except CapturedRequest:
            pass
        if len(captured) != 1 or len(projections) != 1 or source != case["segments"]:
            raise ValueError("Expected one complete unchanged-source offline request.")
        after = captured[0]; old = before["request"]
        if {k:v for k,v in after.items() if k != "messages"} != {k:v for k,v in old.items() if k != "messages"}:
            raise ValueError("Model/options/schema changed while adding source context.")
        if after["messages"][0]["content"] != old["messages"][0]["content"] + INSTRUCTION:
            raise ValueError("System text changes more than the one generic context instruction.")
        prefix, encoded = old["messages"][1]["content"].split("JSON input: ", 1)
        context_json = json.dumps(projections[0]["spellings"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if after["messages"][1]["content"] != prefix + CONTEXT_LABEL + context_json + "\nJSON input: " + encoded:
            raise ValueError("User text changes more than the separate exact source map.")
        requests.append({"id":case["id"], "request":after})
        records.append({"id":case["id"], "source_segments":bundle["source_segments"],
                        "source_segments_sha256":bundle["source_segments_sha256"],
                        "compact_protection_binding_sha256":bundle["protection_binding_sha256"],
                        "compact_segments":case["segments"], "context_map":projections[0]["spellings"]})
        checks.append({"id":case["id"], "source_names":len(projections[0]["spellings"]),
                       "combined_source_json_bytes":projections[0]["combined_source_json_bytes"],
                       "complete_original_source_roundtrip":True, "same_compact_output_mechanics":True,
                       "only_source_spelling_map_and_generic_instruction_added":True,
                       "context_inserted_before_native_request_observation":True})
    save("expected-requests.json", requests)
    save("source-context-maps.json", {"schema_version":1, "cases":records})
    save("input-build-report.json", {"schema_version":1, "complete":True, "checks":checks,
                                     "offline_request_captures":6, "model_calls":0,
                                     "native_api_calls":0, "detector_calls":0,
                                     "source_only_normalizer_calls":0, "runner_sha256":sha(Path(__file__)),
                                     "annotation_or_reference_data_supplied_to_projection":False,
                                     "actual_source_names_supplied_as_explicit_context":True})
    print(json.dumps({"complete":True, "cases":6, "source_names":sum(x["source_names"] for x in checks),
                      "combined_source_json_bytes":[x["combined_source_json_bytes"] for x in checks],
                      "native_calls":0}))


if __name__ == "__main__":
    main()

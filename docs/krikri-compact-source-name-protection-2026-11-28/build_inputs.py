"""Freeze source-derived protection and exact app requests without model calls."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from protection import INSTRUCTION, build_protection

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BOUNDARY = ROOT / "docs/name-boundary-normalizer-2026-11-28"
BASE = ROOT / "docs/krikri-screen-2026-11-28"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write("\n")


def main():
    manifest_path = BOUNDARY / "evidence-manifest.json"
    if sha(manifest_path) != "e40602570d9f7ab156dcc728167943625e9f5bc334e6491eec65c24ebdffb17a":
        raise ValueError("The independently reviewed source-boundary evidence changed.")
    for entry in json.loads(manifest_path.read_bytes())["files"]:
        path = BOUNDARY / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise ValueError("A frozen source-boundary file changed.")
    source_path = ROOT / "docs/name-span-protection-research-2026-11-28/original-six-source-only.json"
    if sha(source_path) != "547c4edca0db2801d07d7cf6588655c062fb870a20b455560395eccdc9de3482":
        raise ValueError("The original source-only snapshot changed.")
    original = json.loads(source_path.read_bytes())["cases"]
    prior_plan = json.loads((BOUNDARY / "plan.json").read_bytes())
    baseline_requests = json.loads((BASE / "expected-requests.json").read_bytes())
    os.environ.update(LINKSCRIBE_TRANSLATION_BACKEND="ollama", LINKSCRIBE_TRANSLATION_MODEL="linkscribe-krikri-8b-q4km:20261128",
                      LINKSCRIBE_OLLAMA_THREADS="4", LINKSCRIBE_OLLAMA_URL="http://127.0.0.1:11434")
    os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
    spec = importlib.util.spec_from_file_location("offline_request_capture", HERE / "enhancements-context4096.py")
    app = importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    protected_cases, protections, requests, checks = [], [], [], []
    for case, raw_binding, baseline in zip(original, prior_plan["raw_reports"], baseline_requests):
        raw_path = ROOT / raw_binding["path"]
        if sha(raw_path) != raw_binding["sha256"]:
            raise ValueError("An actual detector raw report changed.")
        raw = json.loads(raw_path.read_bytes())
        if raw["id"] != case["id"] or raw["source"]["source_segments"] != case["segments"]:
            raise ValueError("Raw detector source binding differs from the complete source.")
        normalized_path = BOUNDARY / (case["id"] + ".json")
        retained = json.loads(normalized_path.read_bytes())["result"]
        bundle = build_protection(case["segments"], raw["raw_entities"], case["source_language"])
        if bundle["normalizer_result"] != retained:
            raise ValueError("Source-only normalization differs from the independently reviewed actual replay.")
        protected_case = {**copy.deepcopy(case), "segments": copy.deepcopy(bundle["masked_segments"])}
        for segment in protected_case["segments"]:
            if list(app._translation_fragments(segment["text"], app.MAX_JSON_TRANSLATION_INPUT_BYTES)) != [segment["text"]]:
                raise ValueError("A protected short source would be fragmented; this stage cannot proceed.")
        encoded = app._translation_json([s["text"] for s in protected_case["segments"]])
        if len(encoded.encode()) > app.MAX_JSON_TRANSLATION_INPUT_BYTES:
            raise ValueError("The complete protected source exceeds the unchanged single-request byte limit.")
        captured = []
        class CapturedRequest(BaseException):
            pass
        def intercept(path, payload=None, timeout=1.5):
            if path == "/api/chat" and app.is_ollama_control_request(payload):
                return {"done": True, "done_reason": "unload"}  # Offline cleanup stub, no native API call.
            if path != "/api/chat" or timeout != 240:
                raise ValueError("Unexpected offline request capture path.")
            captured.append(copy.deepcopy(payload))
            raise CapturedRequest()
        app.local_ollama_json = intercept
        try:
            app.translate_segments(copy.deepcopy(protected_case["segments"]), case["target_language"],
                                   source_language=case["source_language"])
        except CapturedRequest:
            pass
        if len(captured) != 1 or case["id"] != baseline["id"]:
            raise ValueError("Expected one actual complete app request per fixed source.")
        body = captured[0]
        previous = baseline["request"]
        if ({k:v for k,v in body.items() if k != "messages"} != {k:v for k,v in previous.items() if k != "messages"}
                or body["messages"][0]["content"] != previous["messages"][0]["content"] + INSTRUCTION
                or body["messages"][0]["role"] != "system" or body["messages"][1]["role"] != "user"):
            raise ValueError("The request changes more than the generic instruction and protected source representation.")
        user = body["messages"][1]["content"]
        prefix, json_source = user.split("JSON input: ", 1)
        if prefix != previous["messages"][1]["content"].split("JSON input: ", 1)[0]:
            raise ValueError("Ordinary task/language instructions changed.")
        if json.loads(json_source) != [{"id":i,"text":s["text"]} for i,s in enumerate(protected_case["segments"])]:
            raise ValueError("The native request omits part of the full protected source.")
        protected_cases.append(protected_case)
        protections.append({"id":case["id"],"raw_report_sha256":raw_binding["sha256"],
                            "normalized_replay_sha256":sha(normalized_path),"raw_entities":raw["raw_entities"],"bundle":bundle})
        requests.append({"id":case["id"],"request":body})
        checks.append({"id":case["id"],"markers":len(bundle["markers"]),"masked_source_json_bytes":len(encoded.encode()),
                       "full_source_roundtrip_exact":True,"same_original_segment_metadata":True,
                       "single_uncropped_request":True,"only_instruction_and_reversible_source_representation_changed":True})
    if len(requests) != 6:
        raise ValueError("Expected all six original cases.")
    save("protected-source-cases.json", {"schema_version":1,"cases":protected_cases})
    save("protection-inputs.json", {"schema_version":1,"cases":protections})
    save("expected-requests.json", requests)
    save("input-build-report.json", {"complete":True,"case_count":6,"checks":checks,"model_calls":0,"detector_calls":0,
                                     "native_api_calls":0,"offline_request_captures":6,"source_only_normalizations":6,
                                     "no_reference_or_criteria_supplied_to_algorithm_or_request":True,
                                     "prior_review_bytes_read_for_checksum_only":True,"runner_sha256":sha(Path(__file__)),
                                     "source_only_sha256":sha(source_path),"normalizer_manifest_sha256":sha(manifest_path)})
    print(json.dumps({"cases":6,"model_calls":0,"checks":checks},ensure_ascii=False))


if __name__ == "__main__":
    main()

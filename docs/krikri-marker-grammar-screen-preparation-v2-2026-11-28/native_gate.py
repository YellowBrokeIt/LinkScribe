"""Read-only prerequisites. This file never runs a validator or native model.

Actual reports and their independent review must be separately frozen after the
native continuation finishes. No receipt is synthesized from a local pass flag.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

from context import HERE, ROOT, PRIOR, GRAMMAR, NATIVE, common
from format_projection import require_format_only


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate JSON key in prerequisite evidence: " + key)
            value[key] = item
        return value
    def constant(value):
        raise ValueError("Nonfinite JSON in prerequisite evidence: " + value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def require_http_receipts(native, record, expected_version):
    """Replay the retained calls; only the observed initial refusal lacks bytes.

    This exception is not a generic missing-response allowance. It requires the
    exact first connection-refused version poll and the immediate successful
    readiness response. The documented closed-error sentinel still needs its
    complete HTTP error/raw-response receipt; no candidate error is accepted.
    """
    calls = native.get("http_calls", [])
    first_refusal = {"index": 0, "kind": "version", "path": "/api/version", "port": 11434,
                     "request": None, "timeout_seconds": 10, "complete": False,
                     "error": {"type": "URLError", "message": "<urlopen error [Errno 111] Connection refused>"}}
    sentinel = next((row for row in native.get("grammars", [])
                     if row.get("id") == "unsupported-lookahead-gate-sentinel"), {})
    refused, ready, raw_count = False, False, 0
    for index, call in enumerate(calls):
        if type(call.get("index")) is not int or call["index"] != index:
            raise ValueError("Actual native HTTP call ordering changed.")
        if (call == first_refusal and call.get("complete") is False
                and type(call.get("port")) is int and type(call.get("timeout_seconds")) is int):
            if index != 0 or len(calls) < 2 or calls[1].get("kind") != "version":
                raise ValueError("The initial readiness refusal is not followed immediately by readiness.")
            refused = True
            continue
        if not isinstance(call.get("raw_response"), dict) or not isinstance(call.get("response"), dict):
            raise ValueError("A native call lacks its complete captured HTTP response.")
        if read(record(call["raw_response"])) != call["response"]:
            raise ValueError("Native JSON differs from its captured raw response.")
        raw_count += 1
        successful = (type(call.get("http_status")) is int and 200 <= call["http_status"] < 300
                      and call.get("complete") is True and "error" not in call)
        if call.get("kind") == "version":
            if (ready or index != int(refused) or not successful
                    or call.get("path") != "/api/version" or call.get("port") != 11434
                    or call.get("request") is not None or call.get("timeout_seconds") != 10
                    or call["response"] != {"version": expected_version}):
                raise ValueError("The full successful readiness response does not follow the allowed startup order.")
            ready = True
            continue
        if not ready:
            raise ValueError("A non-readiness call occurred before successful readiness.")
        if not successful:
            closed = (sentinel.get("conversion_error_closed") is True
                      and sentinel.get("response_receipt") == {k: v for k, v in call.items() if k != "error"}
                      and call.get("kind") == "grammar" and call.get("path") == "/completion"
                      and call.get("request") == sentinel.get("request")
                      and call.get("complete") is False and call.get("http_status") in (400, 500)
                      and call.get("error", {}).get("type") == "NativeHTTPError")
            if not closed:
                raise ValueError("A successful or non-readiness call has an incomplete/error receipt.")
    if not ready:
        raise ValueError("No complete successful native readiness response exists.")
    return {"initial_connection_refusals": int(refused), "raw_http_responses": raw_count,
            "successful_version_observed": ready}


def require_native_contract(native, validation, requests, queries, probes):
    """Pure structural checks used both before execution and by no-model controls."""
    if not len(requests) == 6 or len(queries) != 7 or len(probes) != 285:
        raise ValueError("The six-schema/285-probe source inventory changed.")
    if (native.get("complete") is not True or native.get("generation_calls") != 0
            or native.get("all_native_conversion_requests_complete") is not True
            or native.get("owned_daemon_stopped") is not True
            or native.get("unload_response", {}).get("done_reason") != "unload"
            or native.get("resident_after_unload", {}).get("models") != []
            or native.get("unload_error") or native.get("error")):
        raise ValueError("Actual zero-generation native preparation/unload is incomplete.")
    if (validation.get("complete") is not True or validation.get("error")
            or validation.get("candidate_probe_count") != 285
            or validation.get("all_candidate_expectations_match") is not True
            or validation.get("sentinel", {}).get("enforcement_gate_rejects") is not True):
        raise ValueError("Actual candidate grammar validation did not pass all 285 probes and the sentinel.")
    prompts, grammars, outcomes = native.get("prompts", []), native.get("grammars", []), validation.get("probes", [])
    if ([row.get("id") for row in prompts] != [row["id"] for row in requests]
            or [row.get("id") for row in grammars] != [row["id"] for row in queries]
            or [row.get("id") for row in outcomes] != [row["id"] for row in probes]):
        raise ValueError("Actual prompt, grammar or probe order/completeness changed.")
    for prompt, request in zip(prompts, requests):
        tokens = prompt.get("tokens")
        rendered = prompt.get("rendered_prompt")
        if (prompt.get("request") != request["request"]
                or not isinstance(tokens, list) or not tokens or any(type(t) is not int for t in tokens)
                or tokens[0] != 128000 or tokens.count(128000) != 1
                or prompt.get("prompt_tokens") != len(tokens) or len(tokens) + 2048 + 1 > 4096
                or not isinstance(rendered, str) or not rendered
                or prompt.get("rendered_sha256") != hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                or prompt.get("debug_response", {}).get("_debug_info", {}).get("rendered_template") != rendered
                or prompt.get("maximum_output_tokens") != 2048 or prompt.get("context_tokens") != 4096
                or prompt.get("complete_source_segments") != 2):
            raise ValueError("A complete source request/full native prompt-token binding is missing.")
    by_case = {}
    for grammar, query in zip(grammars, queries):
        if grammar.get("request") != query["request"]:
            raise ValueError("An actual native grammar was made from a different query.")
        if query["id"] != "unsupported-lookahead-gate-sentinel":
            if grammar.get("actual_native_grammar_observed") is not True or "grammar" not in grammar:
                raise ValueError("A candidate lacks its actual emitted grammar.")
            by_case[query["id"]] = grammar["grammar"]
    for outcome, probe in zip(outcomes, probes):
        expected = "accepted" if probe["expected_native_acceptance"] else "rejected"
        if (outcome.get("matched") is not True or outcome.get("expected_status") != expected
                or outcome.get("actual_status") != expected or outcome.get("grammar") != by_case[probe["case_id"]]):
            raise ValueError("A native probe failed or was attached to another candidate grammar.")
    for line in native.get("converter_fallback_diagnostics", []):
        if "pattern ^(?=.*<x0/>).*$ is not supported" not in line:
            raise ValueError("A candidate converter diagnostic reports a weakened grammar.")


def require_native_evidence():
    freeze_path = HERE / "native-evidence-freeze.json"
    if common.sha(freeze_path) != (HERE / "native-evidence-freeze.sha256").read_text(encoding="utf-8").strip():
        raise ValueError("Reviewed native evidence freeze changed.")
    freeze = read(freeze_path)
    if (freeze.get("independent_native_contract_approved") is not True
            or freeze.get("native_directory") != str(NATIVE.relative_to(ROOT))):
        raise ValueError("Independent review of this exact actual native continuation is required.")
    bindings = freeze.get("files_sha256", {})

    def bound(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        if path.is_symlink() or bindings.get(key) != common.sha(path):
            raise ValueError("Native review omits or changes an actual prerequisite: " + key)
        return path

    for path in bindings:
        bound(path)
    bound(freeze["independent_review_path"])
    native_plan = read(bound(NATIVE / "plan.json"))
    profile = read(PRIOR / "plan.json")
    if native_plan["model"] != profile["model"] or native_plan["runtime"] != profile["runtime"]:
        raise ValueError("Actual native preparation uses a different model/runtime.")
    for relative, digest in native_plan["source_sha256"].items():
        if common.sha(bound(ROOT / relative)) != digest:
            raise ValueError("Actual native controller source binding changed.")
    reports = {}
    for phase in ("build", "native_prepare", "validate"):
        path = bound(NATIVE / (phase + ".json"))
        report = read(path)
        resource = read(bound(NATIVE / (phase + "-resources.json")))
        samples = bound(NATIVE / resource["samples_file"])
        if (report.get("complete") is not True or resource.get("passed") is not True
                or resource.get("complete") is not True or resource.get("measurement_complete") is not True
                or resource.get("owned_processes_stopped") is not True or resource.get("measurement_errors")
                or resource.get("phase_report_sha256") != common.sha(path)
                or resource.get("samples_sha256") != common.sha(samples)
                or resource.get("plan_sha256") != common.sha(NATIVE / "plan.json")
                or resource.get("phase_time_limit_exceeded") is not False):
            raise ValueError("A prerequisite phase lacks successful measured completion/cleanup: " + phase)
        reports[phase] = report

    def record(item):
        path = bound(item["path"])
        if path.stat().st_size != item["bytes"] or common.sha(path) != item["sha256"]:
            raise ValueError("Raw prerequisite identity changed: " + str(path))
        return path

    def records(value):
        if isinstance(value, dict):
            if {"path", "bytes", "sha256"} <= set(value):
                record(value)
            for item in value.values():
                records(item)
        elif isinstance(value, list):
            for item in value:
                records(item)

    records(reports)
    requests = read(GRAMMAR / "expected-requests.json")
    previous = read(PRIOR / "expected-requests.json")
    for old, new in zip(previous, requests):
        if old["id"] != new["id"]:
            raise ValueError("Original six request order changed.")
        require_format_only(old["request"], new["request"])
    queries = read(GRAMMAR / "proposed-native-grammar-queries.json")["queries"]
    probes = read(GRAMMAR / "native-probe-matrix.json")["probes"]
    native, validation = reports["native_prepare"], reports["validate"]
    require_native_contract(native, validation, requests, queries, probes)
    calls = native["http_calls"]
    render = [row for row in calls if row["kind"] == "render"]
    tokenize = [row for row in calls if row["kind"] == "tokenize"]
    if len(render) != 6 or len(tokenize) != 6:
        raise ValueError("Actual render/tokenization call inventory is incomplete.")
    require_http_receipts(native, record, profile["runtime"]["version"])
    for prompt, rendered, tokenized in zip(native["prompts"], render, tokenize):
        if (rendered["request"] != {**prompt["request"], "_debug_render_only": True}
                or rendered["response"] != prompt["debug_response"]
                or tokenized["request"] != {"content": prompt["rendered_prompt"],
                    "add_special": prompt["tokenize_add_special"], "parse_special": True}
                or tokenized["response"].get("tokens") != prompt["tokens"]):
            raise ValueError("Prompt tokens are not bound to their actual full native calls.")
    for row in native["grammars"]:
        if "grammar" in row:
            grammar = record(row["grammar"]).read_text(encoding="utf-8")
            if calls[row["response_call_index"]]["response"].get("generation_settings/grammar") != grammar:
                raise ValueError("Retained candidate grammar differs from actual native conversion.")
    status_path = ROOT / "docs/krikri-marker-grammar-controller-v2-2026-11-28/status_contract.py"
    spec = importlib.util.spec_from_file_location("grammar_status_readonly", status_path)
    status = importlib.util.module_from_spec(spec); spec.loader.exec_module(status)
    binary = record(reports["build"]["validator"])
    for result, probe in zip(validation["probes"], probes):
        grammar, value = record(result["grammar"]), record(result["input"])
        command = read(record(result["command_receipt"]))
        records(command)
        if (value.read_bytes() != probe["raw_json"].encode("utf-8")
                or command.get("complete") is not True or command.get("error")
                or command["argv"] != [str(binary), str(grammar), str(value)]
                or command.get("timeout_seconds") != 2 or command["elapsed_seconds"] > 2
                or status.classify(command["exit_code"], record(command["raw_streams"]["stdout"]).read_bytes(),
                                   record(command["raw_streams"]["stderr"]).read_bytes()) != result["actual_status"]):
            raise ValueError("A native probe is not bound to its complete actual validator output.")
    return native, freeze

"""Retained-build continuation and model-free grammar validation actions.

Actions are called only by the root-receipted monitored phase worker. Nothing
executes at import. The source capsule is a retained primary-source document,
not a model, tokenizer or downloaded runtime.
"""
import copy
import hashlib
from pathlib import Path
import re
import shlex

from context import (HERE, OWNED, NATIVE_PLAN, GRAMMAR_PREP, read, save, sha, record,
                     event, source_objects, require_storage)
from process_io import run_command
from status_contract import classify


def expected_sources():
    return source_objects(read(HERE / "official-source-capsule.json"), read(NATIVE_PLAN / "source-acquisition.json"))


def verify_materialized_sources():
    expected = expected_sources()
    source = OWNED / "source"
    actual = [p for p in source.rglob("*") if p.is_file()]
    if {str(p.relative_to(source)) for p in actual} != {row["path"] for row in expected}:
        raise ValueError("Materialized source file inventory differs from the exact allowlist.")
    for row in expected:
        path = source / row["path"]
        if path.is_symlink() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise ValueError("Materialized source bytes changed: " + row["path"])
    return expected


def acquire(report, output, plan):
    objects = expected_sources()
    for name in ("source", "bin", "build", "tmp", "probes"):
        (OWNED / name).mkdir()  # Refuse a previous materialization attempt.
    report["source_origin"] = "Exact retained official connector text, verified against pinned Git objects."
    report["new_network_requests"] = 0
    report["files"] = []
    for row in objects:
        require_storage()
        destination = OWNED / "source" / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(row["body"])
        if sha(destination) != row["sha256"] or destination.stat().st_size != row["bytes"]:
            raise ValueError("Saved source identity differs from verified primary bytes.")
        report["files"].append({key: value for key, value in row.items() if key != "body"})
        save(output, report)
    verify_materialized_sources()
    manifest = OWNED / "acquisition-manifest.json"
    if manifest.exists():
        raise ValueError("Acquisition manifest already exists.")
    save(manifest, {"schema_version": 1, "source_capsule_sha256": sha(HERE / "official-source-capsule.json"),
                    "files": report["files"], "total_bytes": sum(row["bytes"] for row in objects),
                    "source_revision": read(NATIVE_PLAN / "source-acquisition.json")["revision"]})
    report["source_manifest"] = record(manifest)
    report["materialized_source_bytes"] = sum(row["bytes"] for row in objects)


def require_record(item):
    path = Path(item["path"])
    if path.is_symlink() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
        raise ValueError("A measured phase artifact changed: " + str(path))
    return path


def verify_loader_output(stdout, metadata):
    allowed = {item["resolved"]: item for item in metadata["files"]}
    observed = []
    for line in stdout.decode("utf-8", errors="strict").splitlines():
        text = line.strip()
        if not text:
            continue
        if re.fullmatch(r"linux-vdso\.so\.\d+\s+\(0x[0-9a-f]+\)", text):
            continue
        match = re.fullmatch(r"(?:\S+\s+=>\s+)?(/\S+)\s+\(0x[0-9a-f]+\)", text)
        if match is None:
            raise ValueError("Loader receipt contains an unresolved or unknown dependency line.")
        path = Path(match.group(1)); resolved = str(path.resolve())
        if resolved not in allowed or sha(path) != allowed[resolved]["sha256"]:
            raise ValueError("Loader resolved an unbound dependency: " + resolved)
        observed.append({"path": str(path), "resolved": resolved, "sha256": sha(path)})
    required = {"libllama.so.0.7.0", "libggml.so.0.27.0", "libggml-base.so.0.27.0"}
    if not required <= {Path(item["resolved"]).name for item in observed}:
        raise ValueError("Loader receipt omits one of the three retained native core libraries.")
    return observed


def dependency_manifest(path, expected_binary):
    text = path.read_text().replace("\\\n", " ")
    target, separator, remainder = text.partition(":")
    if not separator or shlex.split(target) != [str(expected_binary)]:
        raise ValueError("Compiler dependency file has an unexpected target.")
    names = shlex.split(remainder)
    if not names or len(names) != len(set(names)):
        raise ValueError("Compiler dependency list is empty or ambiguous.")
    rows = []
    for name in names:
        value = Path(name).resolve(strict=True)
        allowed = (OWNED / "source", Path("/usr/include"), Path("/usr/lib/gcc"), Path("/usr/libexec/gcc"))
        if not any(value.is_relative_to(root) for root in allowed):
            raise ValueError("Compiler consumed an unexpected source/header: " + str(value))
        rows.append(record(value))
    required = {str((OWNED / "source" / row["path"]).resolve()) for row in expected_sources()
                if row["path"] != "LICENSE"}
    if not required <= {row["path"] for row in rows}:
        raise ValueError("Compiler receipt omits part of the exact pinned include closure.")
    return rows


def validated_cli(binary, grammar_path, input_path, output_base, expected, environment, timeout=2):
    receipt, stdout, stderr = run_command([str(binary), str(grammar_path), str(input_path)], environment,
                                        OWNED, output_base, timeout, 65536)
    status = classify(receipt["exit_code"], stdout, stderr)
    result = {"grammar": record(grammar_path), "input": record(input_path),
              "command_receipt": record(Path(str(output_base) + "-command.json")),
              "actual_status": status, "expected_status": expected, "matched": status == expected}
    return result


def build(report, output, plan):
    """Verify the retained compile, then run only the three previously unrun probes."""
    from continuation_contract import verify_prior_stage, verify_exact_dependencies
    expected = verify_materialized_sources()
    previous = verify_prior_stage()
    old = previous["prior_build_report"]
    dependencies = verify_exact_dependencies()
    required = {str((OWNED / "source" / row["path"]).resolve()) for row in expected
                if row["path"] != "LICENSE"}
    if not required <= {row["path"] for row in dependencies}:
        raise ValueError("The retained dependency receipt omits the pinned source/header closure.")
    command = read(NATIVE_PLAN / "build-command.json")
    environment = command["environment_allowlist"]
    binary = require_record(old["validator"])
    elf = read(require_record(old["elf_receipt"]))
    elf_out = require_record(elf["raw_streams"]["stdout"]).read_bytes()
    text = elf_out.decode("utf-8", errors="strict")
    if ("ELF64" not in text or "Advanced Micro Devices X86-64" not in text
            or str(Path(plan["runtime"]["directory"]) / "lib/ollama") not in text):
        raise ValueError("Retained ELF receipt does not match the required architecture/runtime path.")
    loader = read(require_record(old["loader_receipt"]))
    loader_out = require_record(loader["raw_streams"]["stdout"]).read_bytes()
    resolved = verify_loader_output(loader_out, read(NATIVE_PLAN / "retained-binary-metadata.json"))
    if resolved != old["resolved_libraries"]:
        raise ValueError("Retained native/system library bindings differ.")
    report.update({"mode": "retained_build_verification_then_original_unrun_sanity",
                   "compiler_invocations_this_phase": 0, "acquisition_invocations_this_phase": 0,
                   "prior_failed_build_report": previous["prior_build_report_record"],
                   "prior_failed_build_resources": previous["prior_build_resource_record"],
                   "prior_failed_build_remains_failed": True,
                   "carried_prior_active_seconds": previous["carried_active_seconds"],
                   "previous_build_active_seconds": previous["spent_build_seconds"],
                   "compile_receipt": old["compile_receipt"], "validator": old["validator"],
                   "elf_receipt": old["elf_receipt"], "loader_receipt": old["loader_receipt"],
                   "resolved_libraries": resolved,
                   "compiler_dependency_file": old["compiler_dependency_file"],
                   "actual_compiler_dependencies": dependencies,
                   "exact_outside_root_system_headers": read(HERE / "independent-prior-stage-review/actual-header-dependencies.json")["unexpected_resolved_headers"]})
    save(output, report)
    sanity = read(NATIVE_PLAN / "validator-sanity.json")
    grammar = OWNED / "probes/sanity.gbnf"
    with grammar.open("xb") as stream: stream.write(sanity["grammar"].encode("utf-8"))
    report["sanity"] = []
    for index, case in enumerate(sanity["cases"]):
        input_path = OWNED / "probes" / ("sanity-" + str(index) + ".txt")
        with input_path.open("xb") as stream: stream.write(case["input_utf8"].encode("utf-8"))
        value = validated_cli(binary, grammar, input_path, OWNED / "logs" / ("sanity-" + str(index)),
                              case["expected_status"], environment)
        report["sanity"].append({"id": case["id"], **value}); save(output, report)
        if not value["matched"]:
            raise ValueError("Pinned native validator failed its literal/incomplete-input sanity check.")
    verify_materialized_sources()
    require_record(report["validator"])
    report["native_model_loads"] = 0


def validate(report, output, plan):
    built = read(HERE / "build.json")
    native = read(HERE / "native_prepare.json")
    binary = require_record(built["validator"])
    if (not native.get("owned_daemon_stopped") or native.get("resident_after_unload", {}).get("models") != []
            or native.get("unload_response", {}).get("done_reason") != "unload"):
        raise ValueError("Native preflight did not explicitly unload and stop before validator-only work.")
    frozen_queries = read(GRAMMAR_PREP / "proposed-native-grammar-queries.json")["queries"]
    if [row["id"] for row in native["grammars"]] != [row["id"] for row in frozen_queries]:
        raise ValueError("Actual grammar inventory differs from the seven frozen conversion queries.")
    by_id = {row["id"]: row for row in native["grammars"]}
    report["probes"] = []
    probes = read(GRAMMAR_PREP / "native-probe-matrix.json")["probes"]
    if len(probes) != 285:
        raise ValueError("The full frozen native probe matrix changed.")
    environment = read(NATIVE_PLAN / "build-command.json")["environment_allowlist"]
    for index, probe in enumerate(probes):
        grammar = require_record(by_id[probe["case_id"]]["grammar"])
        value_path = OWNED / "probes" / ("candidate-" + str(index) + ".json")
        with value_path.open("xb") as stream: stream.write(probe["raw_json"].encode("utf-8"))
        expected = "accepted" if probe["expected_native_acceptance"] else "rejected"
        value = validated_cli(binary, grammar, value_path, OWNED / "logs" / ("candidate-" + str(index)),
                              expected, environment)
        report["probes"].append({"id": probe["id"], **value}); save(output, report)
        if not value["matched"]:
            raise ValueError("Actual emitted grammar failed a frozen native acceptance probe: " + probe["id"])
    sentinel = by_id["unsupported-lookahead-gate-sentinel"]
    if sentinel.get("conversion_error_closed") is True:
        report["sentinel"] = {"closed_converter_rejection": True, "enforcement_gate_rejects": True,
                              "response_receipt": sentinel["response_receipt"]}
    else:
        grammar = require_record(sentinel["grammar"])
        value_path = OWNED / "probes/sentinel-missing-marker.json"
        with value_path.open("xb") as stream: stream.write(frozen_queries[-1]["probe_missing_marker"].encode("utf-8"))
        value = validated_cli(binary, grammar, value_path, OWNED / "logs/sentinel-missing-marker",
                              "accepted", environment)
        report["sentinel"] = {**value, "weakened_grammar_accepts_missing_marker": value["matched"],
                              "enforcement_gate_rejects": value["matched"]}
        save(output, report)
        if not value["matched"]:
            raise ValueError("Unsupported sentinel did not follow the pinned fallback/error contract.")
    report["candidate_probe_count"] = len(report["probes"])
    report["all_candidate_expectations_match"] = all(row["matched"] for row in report["probes"])
    report["native_model_loads"] = 0
    report["semantic_acceptance_or_generation_authorization"] = False

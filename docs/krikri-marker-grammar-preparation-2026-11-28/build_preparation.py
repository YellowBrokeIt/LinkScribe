"""Prepare exact six schemas and no-model controls; never convert a grammar."""
from __future__ import annotations

import sys


def source_only_audit(event, args):
    if event.startswith(("socket.", "subprocess.", "os.system", "os.exec", "os.posix_spawn", "ctypes.")):
        raise RuntimeError("No native, process, network or foreign-library operation: " + event)
    if event == "import" and args and str(args[0]).split(".")[0] in {
        "torch", "transformers", "tokenizers", "sentencepiece", "ollama",
        "llama_cpp", "onnxruntime", "gliner", "numpy", "requests", "httpx", "httpx2",
    }:
        raise RuntimeError("No model/runtime/tokenizer import: " + str(args[0]))


sys.addaudithook(source_only_audit)

import copy
import difflib
import hashlib
import itertools
import json
from pathlib import Path
import re

from schema_profile import build_schema, digest, marker_layout, project_request, require_exact_schema
from profile_oracle import accepted, raw_bodies

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / "docs/krikri-source-spelling-screen-2026-11-28"
EXPECTED_PRIOR_MANIFEST = "6e1f3d40163fbe1f2eb589fd5687b9a502174d8b8dd42f68f9b3bbab088c4401"
EXPECTED_CORPUS = "48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce"
EXPECTED_CURRENT = "129d0f8c7dbbd5e621b8017d73c7aff204a40446d8ed59f7df8904c87efb579e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def encode(strings):
    return json.dumps({"translations": strings}, ensure_ascii=False, separators=(",", ":"))


def with_words(layout, prefix="Text ", between=" text ", suffix=" text."):
    return [prefix + between.join(tags) + suffix for tags in layout]


def make_probes(case_id, layout):
    probes = []

    def add(label, content, expect, note="structural probe, not translation evidence"):
        probes.append({"id": case_id + ":" + label, "case_id": case_id,
                       "kind": label, "raw_json": content,
                       "expected_native_acceptance": expect, "note": note})

    base = with_words(layout)
    for index, orders in enumerate(itertools.product(*(list(itertools.permutations(tags)) for tags in layout))):
        add("all-order-" + str(index), encode(with_words(orders)), True)
    add("literal-unicode", encode(with_words(layout, "λόγος café α\u0301 ", " · ", " τέλος.")), True)
    add("json-short-escapes", encode(with_words(layout, 'Text "quote" / \\ ', "\n\t\r\b\f ", " text.")), True)
    add("no-ordinary-prose", encode(["".join(tags) for tags in layout]), True,
        "Known limit: a native structural pass can omit all ordinary meaning; empty entries also fail the unchanged app guard.")
    add("unconstrained-ordinary-prose", encode(with_words(layout, "The amount is 987 and he left. ")), True,
        "Known limit: grammar cannot establish amounts, gender, roles or any source proposition; this is synthetic probe text only.")
    for i, tags in enumerate(layout):
        for tag in tags:
            value = base.copy(); value[i] = value[i].replace(tag, "", 1)
            add("missing-" + tag, encode(value), False)
            value = base.copy(); value[i] += tag
            add("duplicate-" + tag, encode(value), False)
            value = base.copy(); value[i] = value[i].replace(tag, "", 1); value[1-i] += tag
            add("cross-entry-" + tag, encode(value), False)
        value = base.copy(); value[i] += "<x9999/>"
        add("unknown-in-entry-" + str(i), encode(value), False)
        for label, extra in [("opening", "<x9999>"), ("closing", "</x9999>"),
                             ("uppercase", "<X9999/>"), ("spaced-prefix", "< x9999/>"),
                             ("angle-prose", " a < b ")]:
            value = base.copy(); value[i] += extra
            add(label + "-entry-" + str(i), encode(value), False)
    for label, strings in [("too-few-entries", base[:1]), ("too-many-entries", base + ["Text"]),
                           ("zero-entries", []), ("null-entry", [None, base[1]]),
                           ("numeric-entry", [1, base[1]]), ("nested-entry", [[base[0]], base[1]])]:
        add(label, encode(strings), False)
    good = encode(base)
    add("extra-property", good[:-1] + ',"extra":true}', False)
    add("duplicate-property", good[:-1] + ',"translations":' + json.dumps(base, ensure_ascii=False) + '}', False)
    add("wrong-root-type", json.dumps(base, ensure_ascii=False), False)
    add("truncated-json", good[:-1], False)
    add("invalid-escape", good.replace('Text ', 'Text \\q ', 1), False)
    add("raw-control", good.replace('Text ', 'Text \x01 ', 1), False)
    add("unicode-escaped-prose", good.replace('Text ', r'\u03bb ', 1), False,
        "Literal Unicode is permitted; all serialized Unicode escapes are outside this bounded profile.")
    add("unicode-escaped-hidden-tag", good.replace('Text ', r'\u003cx9999/> ', 1), False)
    add("escaped-property-name", good.replace('"translations"', r'"transl\u0061tions"', 1), False)
    if any(layout):
        tag = next(tag for tags in layout for tag in tags)
        add("escaped-required-angle", good.replace(tag, r'\u003c' + tag[1:], 1), False)
        add("escaped-required-slash", good.replace(tag, tag.replace('/', r'\/'), 1), False)
    value = base.copy(); value[0] += "＜ｘ9999/＞"
    add("normalization-lookalike", encode(value), True,
        "Known limit: literal Unicode gap permits this; unchanged NFKC-aware marker guard must reject after decoding.")
    return probes


def regex_profile_accepts(content, schema):
    """Python regex comparison only; never describe this as native evidence."""
    try:
        def pairs(rows):
            result = {}
            for key, value in rows:
                if key in result:
                    raise ValueError("duplicate")
                result[key] = value
            return result
        value = json.loads(content, object_pairs_hook=pairs)
        specs = schema["properties"]["translations"]["items"]
        if (not isinstance(value, dict) or list(value) != ["translations"]
                or not isinstance(value["translations"], list)
                or len(value["translations"]) != len(specs)
                or any(not isinstance(v, str) for v in value["translations"])):
            return False
        bodies = raw_bodies(content)
        return (len(bodies) == len(specs) + 1 and bodies[0] == "translations"
                and all(re.fullmatch(spec["pattern"], body) is not None
                        for spec, body in zip(specs, bodies[1:])))
    except (ValueError, TypeError, UnicodeError):
        return False


def main():
    if sha(PRIOR / "evidence-manifest.json") != EXPECTED_PRIOR_MANIFEST:
        raise ValueError("Prior failed bundle manifest changed.")
    manifest = json.loads((PRIOR / "evidence-manifest.json").read_text())
    for item in manifest["files"]:
        path = PRIOR / item["path"]
        if path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError("Prior failed evidence changed: " + item["path"])
    if sha(PRIOR / "development-cases.json") != EXPECTED_CORPUS:
        raise ValueError("Original criteria/source corpus changed.")
    requests = json.loads((PRIOR / "expected-requests.json").read_text())
    bundles = json.loads((PRIOR / "protection-inputs.json").read_text())["cases"]
    contexts = json.loads((PRIOR / "source-context-maps.json").read_text())["cases"]
    prepared = json.loads((PRIOR / "prepare.json").read_text())
    if not len(requests) == len(bundles) == len(contexts) == len(prepared["prompts"]) == 6:
        raise ValueError("Expected exactly the prior six exposed complete sources.")
    new_requests, schemas, reports, probes = [], [], [], []
    for prior, record, context, prompt in zip(requests, bundles, contexts, prepared["prompts"]):
        if not prior["id"] == record["id"] == context["id"] == prompt["id"]:
            raise ValueError("Prior source/request/native-vector order differs.")
        before = copy.deepcopy(prior["request"])
        result, layout = project_request(before, record["bundle"], context)
        if before != prior["request"] or {k: v for k, v in result.items() if k != "format"} != {
                k: v for k, v in before.items() if k != "format"}:
            raise ValueError("A field other than format changed.")
        if prompt["request"] != before:
            raise ValueError("Reused prompt vector is not from the exact unchanged prior messages.")
        schema = result["format"]
        text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        report = {"id": prior["id"], "layout": layout,
                  "tag_counts": list(map(len, layout)),
                  "branches_per_entry": [len(list(itertools.permutations(tags))) for tags in layout],
                  "schema_bytes": len(text.encode()), "schema_sha256": digest(schema),
                  "old_request_sha256": digest(before), "new_request_sha256": digest(result),
                  "complete_source_binding_sha256": record["bundle"]["protection_binding_sha256"],
                  "only_format_changed": True, "messages_byte_content_unchanged": True,
                  "retained_prior_native_prompt_tokens": prompt["prompt_tokens"],
                  "retained_prior_rendered_sha256": prompt["rendered_sha256"],
                  "retained_prior_tokens_sha256": digest(prompt["tokens"]),
                  "context4096_minus_prior_prompt_minus_output2048_minus_terminal1": 4096 - prompt["prompt_tokens"] - 2048 - 1,
                  "actual_new_native_render_or_tokenization": False,
                  "schema_not_rendered_into_model_messages": True}
        new_requests.append({"id": prior["id"], "request": result})
        schemas.append({"id": prior["id"], "layout": layout, "schema": schema})
        reports.append(report)
        probes.extend(make_probes(prior["id"], layout))
    # These checks prove only the pure source-level intended profile. They are
    # deliberately retained alongside a pending native acceptance field.
    by_id = {row["id"]: row for row in schemas}
    results = []
    for probe in probes:
        entry = by_id[probe["case_id"]]
        oracle = accepted(probe["raw_json"], entry["layout"])
        regex_result = regex_profile_accepts(probe["raw_json"], entry["schema"])
        results.append({"id": probe["id"], "expected": probe["expected_native_acceptance"],
                        "source_scanner_accepts": oracle, "python_regex_accepts": regex_result,
                        "native_accepts": None, "native_executed": False,
                        "passed_source_control": oracle == regex_result == probe["expected_native_acceptance"]})
    construction = []

    def rejects(label, operation):
        try:
            operation()
        except ValueError as error:
            construction.append({"id": label, "rejected": True, "reason": str(error)})
        else:
            construction.append({"id": label, "rejected": False})

    rejects("more-than-three-markers", lambda: build_schema([["<x0/>", "<x1/>", "<x2/>", "<x3/>"], []]))
    rejects("cross-entry-duplicate-marker", lambda: build_schema([["<x0/>"], ["<x0/>"]]))
    rejects("noncanonical-marker", lambda: build_schema([["<x01/>"], []]))
    rejects("one-entry-layout", lambda: build_schema([["<x0/>"]]))
    layout = schemas[0]["layout"]
    for label, mutate in [
        ("unsupported-lookahead", lambda v: v["properties"]["translations"]["items"][0].update(pattern=r"^(?=.*<x0/>).*$")),
        ("missing-anchor", lambda v: v["properties"]["translations"]["items"][0].update(pattern=".*")),
        ("generic-string-fallback", lambda v: v["properties"]["translations"]["items"][0].pop("pattern")),
        ("ignored-min-length", lambda v: v["properties"]["translations"]["items"][0].update(minLength=1)),
        ("modern-prefix-items", lambda v: v["properties"]["translations"].update(prefixItems=v["properties"]["translations"].pop("items"), items=False)),
        ("extra-schema-key", lambda v: v.update(unevaluatedProperties=False)),
        ("changed-arity", lambda v: v["properties"]["translations"]["items"].pop()),
    ]:
        value = build_schema(layout); mutate(value)
        rejects(label, lambda v=value: require_exact_schema(v, layout))
    bound = copy.deepcopy(bundles[0]["bundle"])
    bound["source_segments"][0]["speaker"] = "Changed speaker"
    rejects("source-metadata-drift", lambda: marker_layout(bound, contexts[0]))
    changed_context = copy.deepcopy(contexts[0]); changed_context["context_map"][0]["spelling"] += "x"
    rejects("source-spelling-drift", lambda: marker_layout(bundles[0]["bundle"], changed_context))
    changed_request = copy.deepcopy(requests[0]["request"])
    changed_request["messages"][1]["content"] = changed_request["messages"][1]["content"].replace("12 minutes", "13 minutes")
    rejects("ordinary-source-drift", lambda: project_request(changed_request, bundles[0]["bundle"], contexts[0]))
    passed = all(row["passed_source_control"] for row in results) and all(row["rejected"] for row in construction)
    save("expected-requests.json", new_requests)
    save("schemas.json", schemas)
    save("input-and-budget-report.json", {"schema_version": 1, "cases": reports,
         "new_tokenizer_native_model_converter_calls": 0,
         "prior_native_counts_are_not_new_schema_conversion_evidence": True})
    save("native-probe-matrix.json", {"schema_version": 1, "probes": probes,
         "native_or_converter_execution": False, "independent_native_acceptance_required": True})
    save("source-control-results.json", {"schema_version": 1, "passed": passed,
         "raw_json_probes": results, "construction_rejections": construction,
         "new_tokenizer_native_model_converter_calls": 0,
         "network_process_and_model_imports_blocked": True,
         "python_checks_are_not_native_enforcement_evidence": True})
    # Bind the existing compact guard, raw source maps and independent criteria,
    # rather than importing production or creating an adapter with new behavior.
    names = ["evidence-manifest.json", "development-cases.json", "expected-requests.json",
             "source-context-maps.json", "protection-inputs.json", "protected-source-cases.json",
             "enhancements-context4096.py", "enhancements-production.py", "protection.py",
             "source_context.py", "prepare.json", "independent-criterion-binding.json",
             "independent-output-meaning-review.json", "resource_monitor.py", "infer_native.py",
             "prepare_native.py", "context.py", "run_native.py", "execution_gate.py"]
    save("historical-source-bindings.json", {"schema_version": 1,
         "files": [{"path": str((PRIOR / name).relative_to(ROOT)), "bytes": (PRIOR / name).stat().st_size,
                    "sha256": sha(PRIOR / name)} for name in names],
         "algorithm_inputs": ["exact prior request", "retained protection bundle", "retained source-spelling map"],
         "criteria_bound_as_review_data_not_supplied_to_schema_builder": True,
         "prior_full_manifest_verified": True})
    current = ROOT / "enhancements.py"
    if sha(current) != EXPECTED_CURRENT:
        raise ValueError("Current source observation differs from root's declared summary-only checkpoint.")
    patch = "".join(difflib.unified_diff((PRIOR / "enhancements-production.py").read_text().splitlines(True),
                                      current.read_text().splitlines(True),
                                      fromfile="historical-production", tofile="current-production-observation"))
    with (HERE / "current-summary-only.patch").open("x", encoding="utf-8") as stream:
        stream.write(patch)
    save("current-source-observation.json", {"schema_version": 1,
         "current_observed_sha256": sha(current),
         "historical_production_sha256": sha(PRIOR / "enhancements-production.py"),
         "planned_translation_adapter_sha256": sha(PRIOR / "enhancements-context4096.py"),
         "current_file_is_not_an_execution_dependency": True,
         "execution_uses_historical_translation_snapshot_unchanged": True,
         "reason": "Root applied three summary-example removals after the prior experiment was sealed. This proposal preserves the exact historical translation path; no summary is executed.",
         "recorded_diff_sha256": sha(HERE / "current-summary-only.patch")})
    print(json.dumps({"source_controls_passed": passed, "raw_json_probes": len(probes),
                      "construction_controls": len(construction), "native_converter_calls": 0,
                      "schemas": len(schemas), "schema_bytes": [r["schema_bytes"] for r in reports],
                      "retained_prior_native_prompt_tokens": [r["retained_prior_native_prompt_tokens"] for r in reports]}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

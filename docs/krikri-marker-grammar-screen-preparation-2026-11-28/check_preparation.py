"""Source-only controls. Synthetic reports here are never execution evidence."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from context import HERE, ROOT, PRIOR, GRAMMAR, read_plan
from execution_gate import verify_receipt
from format_projection import require_format_only, grammar_payloads
from native_gate import require_native_contract
from source_context import source_context_payloads


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class PreparationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = read(PRIOR / "expected-requests.json")
        cls.requests = read(GRAMMAR / "expected-requests.json")
        cls.queries = read(GRAMMAR / "proposed-native-grammar-queries.json")["queries"]
        cls.probes = read(GRAMMAR / "native-probe-matrix.json")["probes"]

    def synthetic(self):
        # This is a logic-only control, deliberately not saved in the real native
        # directory or claimed as tokenizer/converter/validator execution.
        prompts = []
        for row in self.requests:
            rendered = "synthetic control only"
            prompts.append({"id": row["id"], "request": copy.deepcopy(row["request"]),
                "tokens": [128000, 123], "prompt_tokens": 2, "rendered_prompt": rendered,
                "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                "debug_response": {"_debug_info": {"rendered_template": rendered}},
                "maximum_output_tokens": 2048, "context_tokens": 4096, "complete_source_segments": 2})
        grammars = [{"id": q["id"], "request": copy.deepcopy(q["request"]),
                     "actual_native_grammar_observed": True,
                     "grammar": {"path": "synthetic/" + q["id"], "bytes": 1, "sha256": "synthetic"}}
                    for q in self.queries]
        mapping = {row["id"]: row["grammar"] for row in grammars}
        native = {"complete": True, "generation_calls": 0, "all_native_conversion_requests_complete": True,
                  "owned_daemon_stopped": True, "unload_response": {"done_reason": "unload"},
                  "resident_after_unload": {"models": []}, "prompts": prompts, "grammars": grammars}
        outcomes = [{"id": p["id"], "grammar": mapping[p["case_id"]], "matched": True,
                     "expected_status": "accepted" if p["expected_native_acceptance"] else "rejected",
                     "actual_status": "accepted" if p["expected_native_acceptance"] else "rejected"}
                    for p in self.probes]
        validation = {"complete": True, "candidate_probe_count": 285,
                      "all_candidate_expectations_match": True, "probes": outcomes,
                      "sentinel": {"enforcement_gate_rejects": True}}
        return native, validation

    def check(self, native, validation):
        return require_native_contract(native, validation, self.requests, self.queries, self.probes)

    def test_exact_plan_and_unchanged_original_corpus_settings(self):
        plan = read_plan()
        previous = read(PRIOR / "plan.json")
        for key in ("model", "runtime", "python_runtime", "native_setup", "limits", "evaluation"):
            self.assertEqual(plan[key], previous[key])
        self.assertEqual([x["id"] for x in self.requests], plan["evaluation"]["case_ids"])
        self.assertEqual(hashlib.sha256((PRIOR / "development-cases.json").read_bytes()).hexdigest(),
                         plan["evaluation"]["corpus_sha256"])

    def test_all_six_requests_change_only_format(self):
        self.assertEqual(len(self.previous), 6)
        for old, new, query in zip(self.previous, self.requests, self.queries):
            self.assertEqual(old["id"], new["id"])
            require_format_only(old["request"], new["request"])
            self.assertEqual(new["request"]["format"], query["request"]["json_schema"])

    def test_message_or_option_change_rejected(self):
        for key in ("messages", "options", "model"):
            modified = copy.deepcopy(self.requests[0]["request"])
            modified[key] = "changed"
            with self.assertRaises(ValueError):
                require_format_only(self.previous[0]["request"], modified)

    def test_projection_changes_only_schema_and_restores_builder(self):
        for old, new in zip(self.previous, self.requests):
            seen, record = [], {}
            module = SimpleNamespace(_ollama=lambda payload: seen.append(copy.deepcopy(payload)))
            builder = module._ollama
            payload = {"task": "translation", "messages": old["request"]["messages"],
                       "response_schema": old["request"]["format"]}
            snapshot = copy.deepcopy(payload)
            with grammar_payloads(module, old["request"], new["request"], record, lambda: None):
                module._ollama(payload)
            self.assertEqual(payload, snapshot)
            self.assertEqual(seen, [{**payload, "response_schema": new["request"]["format"]}])
            self.assertIs(module._ollama, builder)
            self.assertTrue(record["grammar_payload_builder_restored"])

    def test_wrong_payload_and_second_call_fail_before_transport(self):
        old, new = self.previous[0]["request"], self.requests[0]["request"]
        seen, record = [], {}
        module = SimpleNamespace(_ollama=lambda payload: seen.append(payload))
        builder = module._ollama
        with self.assertRaises(ValueError):
            with grammar_payloads(module, old, new, record, lambda: None):
                module._ollama({"task": "translation", "messages": [], "response_schema": old["format"]})
        self.assertFalse(seen)
        self.assertIs(module._ollama, builder)
        with self.assertRaises(ValueError):
            with grammar_payloads(module, old, new, {}, lambda: None):
                payload = {"task": "translation", "messages": old["messages"], "response_schema": old["format"]}
                module._ollama(payload)
                module._ollama(payload)
        self.assertEqual(len(seen), 1)
        self.assertIs(module._ollama, builder)

    def test_composed_source_context_and_schema_preserve_all_six_payloads(self):
        compact = read(ROOT / "docs/krikri-compact-tag-screen-2026-11-28/expected-requests.json")
        protections = read(PRIOR / "protection-inputs.json")["cases"]
        maps = read(PRIOR / "source-context-maps.json")["cases"]
        for original, old, new, protection, mapping in zip(compact, self.previous, self.requests, protections, maps):
            seen, record = [], {}
            module = SimpleNamespace(_ollama=lambda payload: seen.append(copy.deepcopy(payload)))
            builder = module._ollama
            payload = {"task": "translation", "messages": original["request"]["messages"],
                       "response_schema": original["request"]["format"]}
            before = copy.deepcopy(payload)
            with grammar_payloads(module, old["request"], new["request"], record, lambda: None), \
                 source_context_payloads(module, protection["bundle"], mapping, record, lambda: None):
                module._ollama(payload)
            self.assertEqual(payload, before)
            self.assertEqual(seen, [{"task": "translation", "messages": new["request"]["messages"],
                                     "response_schema": new["request"]["format"]}])
            self.assertIs(module._ollama, builder)
            self.assertTrue(record["native_payload_builder_restored"])
            self.assertTrue(record["grammar_payload_builder_restored"])

    def test_synthetic_contract_control_only(self):
        self.check(*self.synthetic())

    def test_incomplete_or_wrong_grammar_inventory_rejected(self):
        for mutation in ("missing", "wrong_query", "unobserved"):
            native, validation = self.synthetic()
            if mutation == "missing":
                native["grammars"].pop(2)
            elif mutation == "wrong_query":
                native["grammars"][0]["request"]["n_predict"] = 1
            else:
                native["grammars"][0]["actual_native_grammar_observed"] = False
            with self.assertRaises(ValueError):
                self.check(native, validation)

    def test_missing_failed_or_misbound_probe_rejected(self):
        for mutation in ("missing", "failed", "wrong_grammar"):
            native, validation = self.synthetic()
            if mutation == "missing":
                validation["probes"].pop()
            elif mutation == "failed":
                validation["probes"][20]["actual_status"] = "error"
            else:
                validation["probes"][20]["grammar"] = native["grammars"][3]["grammar"]
            with self.assertRaises(ValueError):
                self.check(native, validation)

    def test_partial_or_changed_prompt_binding_rejected(self):
        for mutation in ("missing", "request", "tokens", "budget", "render"):
            native, validation = self.synthetic()
            if mutation == "missing": native["prompts"].pop()
            if mutation == "request": native["prompts"][0]["request"]["messages"] = []
            if mutation == "tokens": native["prompts"][0]["tokens"].pop()
            if mutation == "budget":
                native["prompts"][0]["tokens"] = [128000] + [12] * 2047
                native["prompts"][0]["prompt_tokens"] = 2048
            if mutation == "render": native["prompts"][0]["rendered_prompt"] += " altered"
            with self.assertRaises(ValueError):
                self.check(native, validation)

    def test_no_prior_generation_or_resident_model_allowed(self):
        for key, value in (("generation_calls", 1), ("owned_daemon_stopped", False),
                           ("unload_response", {}), ("resident_after_unload", {"models": ["live"]})):
            native, validation = self.synthetic(); native[key] = value
            with self.assertRaises(ValueError): self.check(native, validation)

    def test_sentinel_or_candidate_fallback_rejected(self):
        native, validation = self.synthetic()
        validation["sentinel"]["enforcement_gate_rejects"] = False
        with self.assertRaises(ValueError): self.check(native, validation)
        native, validation = self.synthetic()
        native["converter_fallback_diagnostics"] = ["candidate pattern is not supported; accepting any string"]
        with self.assertRaises(ValueError): self.check(native, validation)

    def test_separate_exact_root_authority_required(self):
        receipt = {"phase": "infer", "plan_sha256": "plan", "independent_review_sha256": "review",
                   "native_evidence_freeze_sha256": "native", "root_authorized": True,
                   "generation_authorized": True, "local_model_slot_reserved": True,
                   "runner_author_self_approval": False}
        verify_receipt(receipt, "plan", "review", "native")
        for key in receipt:
            changed = dict(receipt); changed.pop(key)
            with self.assertRaises(ValueError): verify_receipt(changed, "plan", "review", "native")

    def test_corrected_monitor_is_reused_exactly(self):
        original = ROOT / "docs/krikri-marker-grammar-controller-v2-2026-11-28/resource_monitor.py"
        self.assertEqual((HERE / "resource_monitor.py").read_bytes(), original.read_bytes())
        self.assertIn(b'final_elapsed > limits["total_seconds"]', original.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)

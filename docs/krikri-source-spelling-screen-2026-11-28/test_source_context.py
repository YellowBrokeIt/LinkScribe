"""No-model controls for source-context projection and unchanged rejection.

The six captures stop before transport and contain no synthetic translation
answer. Separate generic negative controls never provide reference output to a
model. Native processes, network and neural/tokenizer imports are forbidden.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def forbid_execution(event, args):
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "socket.connect",
                 "socket.connect_ex", "socket.bind", "socket.sendto", "socket.getaddrinfo"}:
        raise AssertionError("Native/network execution is forbidden in source controls: " + event)
    if event == "import" and str(args[0]).split(".", 1)[0] in {
            "torch", "transformers", "tokenizers", "tensorflow", "onnxruntime", "gliner", "llama_cpp"}:
        raise AssertionError("Model/tokenizer import is forbidden in source controls: " + str(args[0]))


sys.addaudithook(forbid_execution)
from execution_gate import authorize_phase, verify_receipt
from protection import digest, restore_segments, strict_response_strings
from source_context import bind_source_context, source_context_payloads, _proposal

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "protected-source-cases.json").read_text())["cases"]
INPUTS = json.loads((HERE / "protection-inputs.json").read_text())["cases"]
MAPS = json.loads((HERE / "source-context-maps.json").read_text())["cases"]
EXPECTED = json.loads((HERE / "expected-requests.json").read_text())
ENV = {"LINKSCRIBE_TRANSLATION_BACKEND": "ollama", "LINKSCRIBE_TRANSLATION_MODEL": "linkscribe-krikri-8b-q4km:20261128",
       "LINKSCRIBE_OLLAMA_THREADS": "4", "LINKSCRIBE_OLLAMA_URL": "http://127.0.0.1:11434"}


def app():
    spec = importlib.util.spec_from_file_location("context_control_adapter", HERE / "enhancements-context4096.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def payload(bundle):
    return {"task": "translation", "messages": [
        {"role": "system", "content": "Synthetic source-only control."},
        {"role": "user", "content": "Translate. JSON input: " + json.dumps(
            [{"id": i, "text": s["text"]} for i, s in enumerate(bundle["masked_segments"])], ensure_ascii=False)},
    ]}


def synthetic_bundle(text, name):
    start = text.index(name)
    original = [{"start": 1.25, "end": 3.5, "text": text, "speaker": "Speaker 1"}]
    masked = [{**original[0], "text": text[:start] + "<x0/>" + text[start + len(name):]}]
    bundle = {"source_segments": original, "source_segments_sha256": digest(original), "masked_segments": masked,
              "markers": [{"marker": "<x0/>", "segment_index": 0, "start": start, "end": start + len(name), "source_text": name}]}
    bundle["protection_binding_sha256"] = digest({"source_segments_sha256": bundle["source_segments_sha256"],
                                                  "masked_segments": masked, "markers": bundle["markers"]})
    context = {"id": "synthetic", "source_segments": copy.deepcopy(original),
               "source_segments_sha256": bundle["source_segments_sha256"],
               "compact_protection_binding_sha256": bundle["protection_binding_sha256"],
               "compact_segments": copy.deepcopy(masked),
               "context_map": [{"tag": "<x0/>", "spelling": name}]}
    return bundle, context


class SourceContextControls(unittest.TestCase):
    def test_all_six_actual_app_requests_match_complete_frozen_proposal_before_transport(self):
        for case, bound, context, expected in zip(CASES, INPUTS, MAPS, EXPECTED):
            with self.subTest(case=case["id"]):
                self.assertEqual(case["id"], context["id"])
                module = app()
                original_builder = module._ollama
                source = copy.deepcopy(case["segments"])
                record, snapshots, calls = {}, [], []
                class Captured(BaseException):
                    pass
                def capture(endpoint, body=None, timeout=1.5):
                    self.assertEqual(endpoint, "/api/chat")
                    calls.append(copy.deepcopy(body))
                    if module.is_ollama_control_request(body):
                        return {"done": True, "done_reason": "unload"}
                    self.assertEqual(timeout, 240)
                    self.assertEqual(body, expected["request"])
                    self.assertEqual(len(record["source_context_projections"]), 1)
                    raise Captured()
                module.local_ollama_json = capture
                with patch.dict(os.environ, ENV):
                    retain = os.environ.pop("LINKSCRIBE_OLLAMA_RETAIN_MODELS", None)
                    try:
                        with self.assertRaises(Captured):
                            with source_context_payloads(module, bound["bundle"], context, record,
                                                         lambda: snapshots.append(copy.deepcopy(record))):
                                module.translate_segments(source, case["target_language"], source_language=case["source_language"])
                    finally:
                        if retain is not None:
                            os.environ["LINKSCRIBE_OLLAMA_RETAIN_MODELS"] = retain
                self.assertEqual(source, case["segments"])
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[1], {"model": ENV["LINKSCRIBE_TRANSLATION_MODEL"], "messages": [], "stream": False, "keep_alive": 0})
                self.assertIs(module._ollama, original_builder)
                self.assertTrue(record["native_payload_builder_restored"])
                self.assertEqual(record["source_context_map"], context["context_map"])
                self.assertTrue(any(s.get("source_context_projections") for s in snapshots))

    def test_changed_map_source_metadata_or_cross_case_binding_rejects_before_builder(self):
        bundle, context = synthetic_bundle("Rina said she would wait.", "Rina")
        for key, value in [("context_map", [{"tag": "<x0/>", "spelling": "Rena"}]),
                           ("source_segments_sha256", "changed"), ("compact_protection_binding_sha256", "changed"),
                           ("compact_segments", [{**bundle["masked_segments"][0], "speaker": "Other"}]),
                           ("source_segments", [{**bundle["source_segments"][0], "start": 9.5}])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                bind_source_context(bundle, {**context, key: value})
        with self.assertRaises(ValueError):
            bind_source_context(INPUTS[0]["bundle"], MAPS[1])

    def test_source_slice_or_map_tampering_cannot_redefine_the_spelling(self):
        bundle, context = synthetic_bundle("Rina arrived.", "Rina")
        for key, value in [("source_text", "Rena"), ("start", 1), ("marker", "<x3/>")]:
            altered = copy.deepcopy(bundle)
            altered["markers"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                bind_source_context(altered, context)

    def test_partial_or_changed_source_request_and_nontranslation_paths_reject(self):
        bundle, _ = synthetic_bundle("Rina arrived.", "Rina")
        ordinary = payload(bundle)
        for changed in ({**ordinary, "task": "summary"}, {**ordinary, "plain_text": True},
                        {**ordinary, "messages": ordinary["messages"][:1]}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                _proposal.project_payload(changed, bundle)
        altered = copy.deepcopy(ordinary)
        altered["messages"][1]["content"] = 'Translate. JSON input: [{"id":0,"text":"<x0/>"}]'
        with self.assertRaises(ValueError):
            _proposal.project_payload(altered, bundle)

    def test_delimiter_collision_and_combined_byte_limit_refuse_without_fallback(self):
        for text, name in [("JSON input: Rina arrived.", "JSON input: Rina"), ("Rina " + "z" * 1100, "Rina")]:
            bundle, _ = synthetic_bundle(text, name)
            with self.subTest(text_length=len(text)), self.assertRaises(ValueError):
                _proposal.project_payload(payload(bundle), bundle)

    def test_duplicate_projection_refuses_second_builder_and_restores_hook(self):
        bundle, context = synthetic_bundle("Rina arrived.", "Rina")
        calls, record = [], {}
        builder = lambda body: calls.append(copy.deepcopy(body))
        module = SimpleNamespace(_ollama=builder)
        with self.assertRaises(ValueError):
            with source_context_payloads(module, bundle, context, record, lambda: None):
                module._ollama(payload(bundle))
                module._ollama(payload(bundle))
        self.assertEqual(len(calls), 1)
        self.assertIs(module._ollama, builder)

    def test_missing_projection_and_builder_failure_preserve_records_and_restore_hook(self):
        bundle, context = synthetic_bundle("Rina arrived.", "Rina")
        def failing_builder(body):
            raise RuntimeError("synthetic builder failure")
        module = SimpleNamespace(_ollama=failing_builder)
        empty = {}
        with self.assertRaises(ValueError):
            with source_context_payloads(module, bundle, context, empty, lambda: None):
                pass
        record = {}
        with self.assertRaisesRegex(RuntimeError, "synthetic builder failure"):
            with source_context_payloads(module, bundle, context, record, lambda: None):
                module._ollama(payload(bundle))
        self.assertEqual(len(record["source_context_projections"]), 1)
        self.assertTrue(record["native_payload_builder_restored"])
        self.assertIs(module._ollama, failing_builder)

    def test_spelling_instead_of_marker_and_extra_context_or_closing_tags_reject(self):
        bundle, _ = synthetic_bundle("Rina arrived.", "Rina")
        for text in ("Rina arrived.", "<x0/> arrived. </x0>", "<x0/> arrived. Context: <x0/>", "<x1/> arrived."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                restore_segments(bundle, [{**bundle["source_segments"][0], "text": text}])
        with self.assertRaises(ValueError):
            strict_response_strings('{"translations":["<x0/> arrived."],"source_spellings":[]}', 1)

    def test_restored_source_metadata_and_existing_foreign_script_guard_still_apply(self):
        bundle, _ = synthetic_bundle("Rina arrived.", "Rina")
        result, _ = restore_segments(bundle, bundle["masked_segments"])
        self.assertEqual(result, bundle["source_segments"])
        bad = [{**bundle["masked_segments"][0], "text": "<x0/> arrived. Ж"}]
        restored, _ = restore_segments(bundle, bad)
        module = app()
        with self.assertRaises(module.EnhancementError):
            module._translation_result(bundle["source_segments"], restored, "en", "el")

    def test_intact_tags_do_not_certify_pronouns_or_added_ordinary_prose(self):
        bundle, _ = synthetic_bundle("Rina said she would wait.", "Rina")
        # Explicit semantic counterexample: mechanical success is not acceptance.
        wrong = [{**bundle["masked_segments"][0], "text": "<x0/> said he would wait. Extra prose."}]
        restored, _ = restore_segments(bundle, wrong)
        self.assertEqual(restored[0]["text"], "Rina said he would wait. Extra prose.")

    def test_phase_receipt_rejects_other_profile_missing_authority_and_self_approval(self):
        value = {"phase": "prepare", "plan_sha256": "fixed", "independent_review_sha256": "review",
                 "root_authorized": True, "local_model_slot_reserved": True, "runner_author_self_approval": False}
        verify_receipt(value, "prepare", "fixed", "review")
        for key, altered in [("phase", "infer"), ("plan_sha256", "old-profile"), ("independent_review_sha256", "other"),
                             ("root_authorized", False), ("local_model_slot_reserved", False), ("runner_author_self_approval", True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_receipt({**value, key: altered}, "prepare", "fixed", "review")
        for phase in ("prepare", "infer"):
            with self.subTest(phase=phase), self.assertRaises(FileNotFoundError):
                authorize_phase(phase)


if __name__ == "__main__":
    unittest.main()

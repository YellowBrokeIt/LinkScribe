"""Model-free controls for phase sequencing and actual application observation."""
import copy
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

import infer_native
import native_session
from protocol import (CASE_IDS, RSS_BYTES, SUMMARY_CHECKS, final_phase_checks,
                      remaining_seconds, verify_authorization, verify_english_acceptance)
from request_contract import capture_case, forbidden_network, load_adapter

HERE = Path(__file__).resolve().parent


class SummaryContractControls(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((HERE/'source-cases.json').read_text(encoding='utf-8'))
        self.requests = json.loads((HERE/'expected-requests.json').read_text(encoding='utf-8'))
        self.resources = {'passed': True, 'complete': True, 'worker_exit_code': 0,
                          'owned_processes_stopped': True, 'elapsed_seconds': 20,
                          'measurement_complete': True, 'measurement_errors': [],
                          'peak_rss_sample': {'rss_bytes': 2000},
                          'events': [{'event': 'initialized', 'observed_elapsed_seconds': 1}],
                          'plan_sha256': 'fixed-plan'}
        self.report = {'id': CASE_IDS[0], 'complete': True, 'structural_pass': True,
                       'checks': dict.fromkeys(SUMMARY_CHECKS, True),
                       'owned_daemon_stopped': True, 'frozen_inputs_unchanged': True,
                       'generation_calls': 1, 'native_create_calls': 0, 'model_downloads': 0,
                       'resident_after_unload': {'models': []}, 'plan_sha256': 'fixed-plan'}
        self.bindings = dict.fromkeys(('plan_sha256', 'english_report_sha256', 'english_resources_sha256',
                                      'original_review_criteria_sha256', 'source_cases_sha256'), 'exact-hash')
        self.decision = {**self.bindings, 'case_id': CASE_IDS[0], 'review_complete': True,
                         'independent_of_runner_author': True, 'major_error_count': 0,
                         'original_criteria_satisfied': True, 'paragraph_points_and_chapter_reviewed': True,
                         'approved_to_run_greek': True}
        self.network = [patch.object(socket.socket, 'connect', forbidden_network),
                        patch.object(socket.socket, 'connect_ex', forbidden_network),
                        patch.object(socket, 'create_connection', forbidden_network)]
        for guard in self.network:
            guard.start()
            self.addCleanup(guard.stop)

    def test_both_real_summary_requests_reproduce_frozen_full_source_with_no_transport(self):
        self.assertEqual([capture_case(case) for case in self.cases], self.requests)
        self.assertEqual([r['timestamped_excerpt_bytes'] for r in self.requests], [957, 1618])
        for case, request in zip(self.cases, self.requests):
            self.assertEqual(request['request']['messages'][1]['content'],
                             '\n'.join(f"[{s['start']:.1f}s] {s['text']}" for s in case['segments']))
            self.assertEqual(request['request']['options'],
                             {'temperature': 0, 'num_ctx': 4096, 'num_predict': 2048, 'num_thread': 4})
            self.assertIs(request['request']['think'], False)

    def test_external_exact_authorization_and_exclusive_slot_required(self):
        auth = {'phase': 'english', 'plan_sha256': 'plan', 'independent_review_sha256': 'review',
                'root_authorized': True, 'local_model_slot_reserved': True, 'runner_author_self_approval': False}
        verify_authorization(auth, 'english', 'plan', 'review')
        for key, value in [('phase', 'greek'), ('plan_sha256', 'changed'), ('independent_review_sha256', 'changed'),
                           ('root_authorized', False), ('local_model_slot_reserved', False),
                           ('runner_author_self_approval', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_authorization({**auth, key: value}, 'english', 'plan', 'review')

    def test_english_semantic_review_is_exact_and_cannot_be_empty_or_self_approved(self):
        verify_english_acceptance(self.decision, self.report, self.resources, self.bindings)
        for key, value in [('major_error_count', 1), ('major_error_count', False),
                           ('english_report_sha256', 'changed'), ('english_resources_sha256', 'changed'),
                           ('independent_of_runner_author', False), ('paragraph_points_and_chapter_reviewed', False),
                           ('original_criteria_satisfied', False), ('approved_to_run_greek', False)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                verify_english_acceptance({**self.decision, key: value}, self.report, self.resources, self.bindings)
        for checks in ({}, {**self.report['checks'], 'output_below_cap': False}):
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                verify_english_acceptance(self.decision, {**self.report, 'checks': checks}, self.resources, self.bindings)

    def test_phase_budget_accumulates_without_reset_and_rejects_prior_failures(self):
        self.assertEqual(remaining_seconds([self.resources, {**self.resources, 'elapsed_seconds': 100}]), 780)
        for change in ({'elapsed_seconds': 900}, {'elapsed_seconds': float('nan')}, {'passed': False},
                       {'owned_processes_stopped': False}, {'measurement_complete': False},
                       {'peak_rss_sample': {'rss_bytes': RSS_BYTES + 1}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                remaining_seconds([{**self.resources, **change}])

    def test_final_completion_gate_rejects_recorded_limits_or_missing_results(self):
        self.assertEqual(final_phase_checks('english', self.resources, self.report, 900), [])
        for resource_change, report_change in [({'elapsed_seconds': 901}, {}),
                ({'events': [{'event': 'initialized', 'observed_elapsed_seconds': 180.001}]}, {}),
                ({'owned_processes_stopped': False}, {}), ({}, {'checks': {}}),
                ({}, {'generation_calls': 2}), ({}, {'model_downloads': 1}),
                ({}, {'resident_after_unload': {'models': ['still-loaded']}}),
                ({}, {'complete': False}), ({}, {'plan_sha256': 'other-plan'})]:
            with self.subTest(resource_change=resource_change, report_change=report_change):
                self.assertTrue(final_phase_checks('english', {**self.resources, **resource_change},
                                                   {**self.report, **report_change}, 900))

    def run_observed_synthetic_response(self, content, *, unload_ok=True):
        module = load_adapter()
        envelope = {'done': True, 'done_reason': 'stop', 'message': {'role': 'assistant', 'content': content},
                    'eval_count': 40, 'prompt_eval_count': 500}
        calls = []
        def fake_transport(endpoint, payload=None, timeout=1.5):
            calls.append(copy.deepcopy(payload))
            if module.is_ollama_control_request(payload):
                return {'done': True, 'done_reason': 'unload' if unload_ok else 'stop'}
            return copy.deepcopy(envelope)
        module.local_ollama_json = fake_transport
        report = {'generation_calls': 0}
        checkpoints = []
        with patch.object(infer_native, 'load_adapter', return_value=module), \
                patch.object(infer_native.common, 'api', return_value={'models': []}):
            try:
                infer_native.summarize_one(self.cases[0], self.requests[0], {'prompt_tokens': 500}, report,
                                          lambda: checkpoints.append(copy.deepcopy(report)))
            except ValueError as error:
                report['synthetic_expected_rejection'] = str(error)
        return report, calls, checkpoints

    def test_actual_app_trimming_and_chapter_limit_preserve_raw_response(self):
        raw = {'summary': '  Synthetic test paragraph.  ', 'key_points': ['  Synthetic point.  '],
               'chapter_title': '  ' + 'x'*130 + '  '}
        report, calls, checkpoints = self.run_observed_synthetic_response(json.dumps(raw))
        self.assertTrue(report['structural_pass'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['raw_summary_object'], raw)
        self.assertEqual(report['application_result']['summary'], 'Synthetic test paragraph.')
        self.assertEqual(report['application_result']['chapters'], [{'start': 0.5, 'title': 'x'*120}])
        self.assertTrue(any(p['requests'][0].get('raw_evidence_available') and p['application_result'] is None
                            for p in checkpoints))

    def test_invalid_inner_json_is_retained_and_never_repaired(self):
        invalid = '{"summary":"first","summary":"second","key_points":["x"],"chapter_title":"x"}'
        report, calls, _ = self.run_observed_synthetic_response(invalid)
        self.assertFalse(report['structural_pass'])
        self.assertIsNone(report['application_result'])
        self.assertEqual(json.loads(report['requests'][0]['response_json'])['message']['content'], invalid)
        self.assertEqual(len(calls), 2)

    def test_failed_unload_rejects_a_returned_summary_without_discarding_it(self):
        content = json.dumps({'summary': 'Synthetic notes.', 'key_points': ['Synthetic point.'], 'chapter_title': 'Test'})
        report, calls, _ = self.run_observed_synthetic_response(content, unload_ok=False)
        self.assertFalse(report['structural_pass'])
        self.assertIsNotNone(report['application_result'])
        self.assertFalse(report['checks']['one_exact_unload_acknowledged'])
        self.assertEqual(len(calls), 2)

    def test_rejected_native_render_is_checkpointed_before_preflight_validation(self):
        unexpected = {'_debug_info': {'rendered_template': 'An unexpected native wrapper.'}, 'eval_count': 0}
        report, checkpoints = {}, []
        with patch.object(native_session.common, 'api', return_value=unexpected), self.assertRaises(ValueError):
            native_session.observed_preflight(self.requests[0]['request'], self.cases[0], None, {}, {},
                                              report, lambda: checkpoints.append(copy.deepcopy(report)))
        trace = report['preflight_attempts'][0]
        self.assertFalse(trace['complete'])
        self.assertEqual(json.loads(trace['calls'][0]['response_json']), unexpected)
        self.assertTrue(any(p['preflight_attempts'][0]['calls']
                            and p['preflight_attempts'][0]['calls'][0]['response_json'] is not None
                            and 'error' not in p['preflight_attempts'][0] for p in checkpoints))


if __name__ == '__main__':
    unittest.main()

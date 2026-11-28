"""Preparation-only controls: no WhisperModel construction or real align call."""
import ast
import copy
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import run_postpass as qa
from check_native_contract import validate_native_path


class PostpassContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tokenizers import Tokenizer
        cls.plan = json.loads((qa.ROOT / 'plan.json').read_text(encoding='utf-8'))
        cls.cases = json.loads((qa.ROOT / 'input-cases.json').read_text(encoding='utf-8'))['cases']
        cls.tokenizer = Tokenizer.from_file(str(Path(cls.plan['model']['path']) / 'tokenizer.json'))
        cls.view = qa.timing_view()

    def test_frozen_preflight_without_model(self):
        _, cases = qa.validate_plan(qa.ROOT / 'plan.json')
        self.assertEqual(len(cases), 5)
        self.assertEqual(sum(len(case['windows']) for case in cases), 23)

    def test_all_original_token_and_window_maps(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                qa.validate_case_contract(case, self.tokenizer)

    def test_native_terminal_is_boundary_not_generated_token(self):
        result = validate_native_path([[0, 0], [0, 1], [1, 2], [2, 3]], [0.5, 0.6], 2, 8)
        self.assertEqual(result['boundary_frames'], [0, 2, 3])
        with self.assertRaises(ValueError):
            validate_native_path([[0, 0], [1, 2]], [0.5, 0.6], 2, 8)
        with self.assertRaises(ValueError):
            validate_native_path([[0, 0], [1, 2], [2, 3]], [0.5, 0.6, 0.7], 2, 8)

    def test_legitimate_native_zero_span_is_not_rejected_as_path(self):
        result = validate_native_path([[0, 0], [1, 0], [2, 1], [2, 2]], [0.5, 0.6], 2, 6)
        self.assertEqual(result['zero_duration_token_spans'], 1)

    def test_wrong_source_frame_token_and_segment_controls(self):
        changes = [
            lambda c: c['raw_segments'][0]['tokens'].pop(1),
            lambda c: c['windows'][0]['text_tokens'].reverse(),
            lambda c: c['windows'][0].update(num_frames=c['windows'][0]['num_frames'] - 1),
            lambda c: c['windows'][0].update(seek=1),
            lambda c: c['raw_segments'].reverse(),
            lambda c: c['array'].update(dtype='<i4'),
        ]
        for index, mutate in enumerate(changes):
            with self.subTest(mutation=index):
                case = copy.deepcopy(self.cases[0])
                mutate(case)
                with self.assertRaises(ValueError):
                    qa.validate_case_contract(case, self.tokenizer)

    def test_consistently_rebound_wrong_audio_and_pcm_still_reject(self):
        for field, wrong in [('media_sha256', '0' * 64), ('pcm_sha256', '0' * 64)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                data = {'reference_material_included': False, 'cases': copy.deepcopy(self.cases)}
                if field == 'media_sha256':
                    data['cases'][0][field] = wrong
                else:
                    data['cases'][0]['array'][field] = wrong
                root = Path(directory)
                inputs = root / 'inputs.json'
                inputs.write_text(json.dumps(data), encoding='utf-8')
                plan = copy.deepcopy(self.plan)
                plan['input_cases_path'] = str(inputs)
                plan['pinned_files'].append({'path': str(inputs), 'sha256': qa.sha(inputs)})
                path = root / 'plan.json'
                path.write_text(json.dumps(plan), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Source media changed|Full decoded array changed'):
                    qa.validate_plan(path)

    def test_merged_word_spanning_original_boundary_marks_both_unusable(self):
        window = {'text_tokens': [1, 2], 'segment_token_spans': [
            {'segment_index': 0, 'start': 0, 'end': 1}, {'segment_index': 1, 'start': 1, 'end': 2}]}
        self.assertEqual(qa.segment_mapping([{'word': 'ab', 'tokens': [1, 2]}], window), {0: False, 1: False})
        with self.assertRaisesRegex(ValueError, 'lost/reordered'):
            qa.segment_mapping([{'word': 'a', 'tokens': [1]}], window)

    def simple_case(self):
        return {'array': {'duration_seconds': 1.0005625},
                'baseline_segments': [{'start': 0, 'end': 1.0005625, 'text': 'Hello world'}],
                'raw_segments': [{'text': ' Hello world', 'tokens': [1, 2]}],
                'windows': [{'seek': 0, 'num_frames': 100, 'segment_indices': [0]}]}

    def test_zero_word_preserves_whole_text_and_segment(self):
        case = self.simple_case()
        candidate = [{'text': ' Hello world', 'tokens': [1, 2], 'start': 0.2, 'end': 1.0,
                      'words': [{'word': ' Hello', 'start': 0.2, 'end': 0.2}, {'word': ' world', 'start': 0.2, 'end': 1.0}]}]
        _, output, record = qa.project(case, candidate, {0: True}, self.view)
        self.assertEqual(output[0]['text'], 'Hello world')
        self.assertEqual(output[0]['_words'], [])
        self.assertEqual(output[0]['start'], 0.2)
        self.assertTrue(record['warnings'])

    def test_real_historical_zero_words_preserve_valid_segments(self):
        repo = Path('/workspace/scratch/94360995dd61/LinkScribe/docs/asr-official-tail-2026-11-28/alignment-only-results')
        sources = [
            ('official_tears_of_steel-report.json', 'abf6ad93ec75a2a3c95138e3e8c2d9181e2daf52b01edc7a9c8eb5b57a384f17', 734.0, 7),
            ('vimeo_sintel-report.json', '9427702a555170bc52d4c563ad1ff64f7d18d1701e06032ce9581b324e456a97', 888.070375, 2),
        ]
        for name, expected_sha, duration, expected_count in sources:
            with self.subTest(source=name):
                path = repo / name
                self.assertEqual(qa.sha(path), expected_sha)
                data = json.loads(path.read_text(encoding='utf-8'))
                events = []
                def walk(item):
                    if isinstance(item, dict):
                        if item.get('kind') == 'asr_segment_created':
                            events.append(item['segment'])
                        else:
                            for value in item.values(): walk(value)
                    elif isinstance(item, list):
                        for value in item: walk(value)
                walk(data)
                self.assertEqual(sum(word['start'] == word['end'] for segment in events for word in segment.get('words') or []), expected_count)
                chosen = next(segment for segment in events if any(word['start'] == word['end'] for word in segment.get('words') or [])
                              and ''.join(word['word'] for word in segment['words']).strip() == segment['text'].strip())
                case = {'array': {'duration_seconds': duration},
                        'raw_segments': [chosen],
                        'baseline_segments': [{'start': chosen['start'], 'end': chosen['end'], 'text': chosen['text'].strip()}],
                        'windows': [{'seek': chosen['seek'], 'num_frames': min(3000, int(duration * 100) - chosen['seek']), 'segment_indices': [0]}]}
                _, output, record = qa.project(case, [copy.deepcopy(chosen)], {0: True}, self.view)
                self.assertEqual(output[0]['text'], chosen['text'].strip())
                self.assertEqual(output[0]['_words'], [])
                self.assertEqual(record['fallback_segment_indices'], [])

    def test_crossed_candidate_reverts_full_timing_without_sorting_text(self):
        case = {'array': {'duration_seconds': 2},
                'raw_segments': [{'text': ' First', 'tokens': [1]}, {'text': ' Second', 'tokens': [2]}],
                'baseline_segments': [{'start': 0, 'end': 0.5, 'text': 'First'}, {'start': 0.5, 'end': 1.5, 'text': 'Second'}],
                'windows': [{'seek': 0, 'num_frames': 200, 'segment_indices': [0, 1]}]}
        adjusted = [{'text': ' First', 'tokens': [1], 'start': 0.6, 'end': 1,
                     'words': [{'word': ' First', 'start': 0.6, 'end': 1}]},
                    {'text': ' Second', 'tokens': [2], 'start': 0.8, 'end': 1.3,
                     'words': [{'word': ' Second', 'start': 0.8, 'end': 1.3}]}]
        baseline, output, record = qa.project(case, adjusted, {0: True, 1: True}, self.view)
        self.assertFalse(record['global_candidate_ordered'])
        self.assertEqual([{k: v for k, v in segment.items() if k != '_words'} for segment in output], baseline)

    def test_invalid_segment_retains_baseline_with_warning(self):
        for start, end in [(float('nan'), 1), (0.8, 0.2), (-1, 0.5), (2, 3)]:
            with self.subTest(start=start, end=end):
                case = self.simple_case()
                candidate = [{'text': ' Hello world', 'tokens': [1, 2], 'start': start, 'end': end,
                              'words': [{'word': ' Hello world', 'start': start, 'end': end}]}]
                baseline, output, record = qa.project(case, candidate, {0: True}, self.view)
                self.assertEqual({k: v for k, v in output[0].items() if k != '_words'}, baseline[0])
                self.assertEqual(record['fallback_segment_indices'], [0])

    def test_current_physical_cap_and_inward_subtitle_policy(self):
        bound = self.view['_bounded_asr_interval']
        start, end = bound(6.5, 7, 104649 / 16000)
        self.assertEqual(end, 6.5405625)
        self.assertEqual(self.view['_subtitle_interval_ms']({'start': start, 'end': end}), (6500, 6540))

    def test_unrepresentable_cue_preserves_text_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            notes = qa.exports(path, 'candidate', [{'start': 0.0002, 'end': 0.0008, 'text': 'Retained words'}], self.view)
            self.assertEqual(len(notes), 2)
            self.assertTrue((path / 'candidate.txt').is_file() and (path / 'candidate.json').is_file())
            self.assertFalse((path / 'candidate.srt').exists() or (path / 'candidate.vtt').exists())

    def test_unmodified_upstream_get_end_state_differs_from_method_return(self):
        import numpy as np
        source_path = next(Path(entry['path']) for entry in self.plan['pinned_files'] if entry['path'].endswith('faster_whisper/transcribe.py'))
        source = source_path.read_text(encoding='utf-8')
        snippets = [ast.get_source_segment(source, n) for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef) and n.name in ('add_word_timestamps', 'merge_punctuations')]
        get_end_source = (qa.ROOT / 'native-contract/upstream-get-end-source.txt').read_text(encoding='utf-8')
        scope = {'np': np, 'itertools': itertools}
        exec('from __future__ import annotations\n' + '\n\n'.join(snippets) + '\n' + get_end_source, scope)
        alignment = [{'word': ' A', 'tokens': [1], 'start': 0, 'end': 0.5, 'probability': 0.9},
                     {'word': ' B', 'tokens': [2], 'start': 0.5, 'end': 1, 'probability': 0.9},
                     {'word': ' C', 'tokens': [3], 'start': 2, 'end': 5, 'probability': 0.9}]
        fake = SimpleNamespace(find_alignment=lambda *args: [copy.deepcopy(alignment)], frames_per_second=100)
        group = [{'seek': 0, 'start': 0, 'end': 2.2, 'text': ' A B C', 'tokens': [1, 2, 3]}]
        returned = scope['add_word_timestamps'](fake, [group], SimpleNamespace(eot=100), None, 3000, '', '', 0)
        self.assertEqual(returned, 2.2)
        self.assertEqual(scope['get_end'](group), 2.5)
        self.assertEqual(group[0]['text'], ' A B C')
        self.assertEqual(group[0]['tokens'], [1, 2, 3])

    def test_raw_nonfinite_failure_can_be_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.json'
            qa.write_json(path, {'native_probability': float('nan')})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['native_probability'], {'nonfinite_float': 'nan'})

    def test_native_cpu_int8_resolution_and_wrong_backend_rejection(self):
        for compute_type in ('int8', 'int8_float32'):
            native = SimpleNamespace(device='cpu', compute_type=compute_type, num_workers=1, is_multilingual=True, n_mels=80)
            qa.validate_native_settings(native, self.plan)
        for device, compute_type in [('cpu', 'float32'), ('cpu', 'float16'), ('cuda', 'int8_float32')]:
            with self.subTest(device=device, compute_type=compute_type):
                native = SimpleNamespace(device=device, compute_type=compute_type, num_workers=1, is_multilingual=True, n_mels=80)
                with self.assertRaises(ValueError):
                    qa.validate_native_settings(native, self.plan)

    def test_final_recorded_limits_and_completion_reject_between_sample_failures(self):
        execution = {'plan_sha256': 'test-plan', 'started_monotonic': 100, 'elapsed_seconds': 10,
                     'sampled_group_peak_rss_bytes': 1000, 'worker_returncode': 0, 'limit_stop': None,
                     'controller_error': None, 'cleanup': {'leader_exited': True, 'live_group_members_after_cleanup': []}}
        report = {'plan_sha256': 'test-plan', 'complete': True, 'all_inputs_completed': True,
                  'model_initialized': True, 'model_unloaded': True, 'recognition_performed': False,
                  'process_peak_rss_bytes': 1000, 'startup_completed_monotonic': 101,
                  'native_calls': {'encode': 23, 'align': 23, 'generate': 0, 'detect_language': 0},
                  'case_results': [{'id': name, 'status': 'complete', 'source_text_unchanged': True,
                                    'original_segment_order_unchanged': True, 'elapsed_seconds': 1,
                                    'process_peak_rss_bytes_so_far': 1000} for name in self.plan['case_order']]}
        self.assertEqual(qa.assess_completed_run(self.plan, execution, report), [])
        mutations = [
            lambda e, r: r.update(process_peak_rss_bytes=self.plan['limits']['rss_bytes'] + 1),
            lambda e, r: r['case_results'][0].update(elapsed_seconds=self.plan['limits']['per_input_seconds'] + 0.001),
            lambda e, r: r.update(startup_completed_monotonic=220.001),
            lambda e, r: e.update(elapsed_seconds=600.001),
            lambda e, r: r.update(all_inputs_completed=False),
            lambda e, r: r.update(model_unloaded=False),
            lambda e, r: r['case_results'].pop(),
            lambda e, r: r['native_calls'].update(align=24),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                trial_e, trial_r = copy.deepcopy(execution), copy.deepcopy(report)
                mutate(trial_e, trial_r)
                self.assertTrue(qa.assess_completed_run(self.plan, trial_e, trial_r))

    def test_native_attempt_is_checkpointed_before_a_failing_call(self):
        import numpy as np
        saved = []
        class FailingNative:
            def encode(self, features, **kwargs):
                if not saved or not saved[-1].get('encode_attempt_recorded'):
                    raise AssertionError('Encode attempt was not durable before call')
                raise TimeoutError('Synthetic encoder interruption; no model used')
            def align(self, *args, **kwargs):
                if not saved or not saved[-1].get('align_attempt_recorded'):
                    raise AssertionError('Align attempt was not durable before call')
                raise TimeoutError('Synthetic alignment interruption; no model used')
        guard = qa.NativeGuard(FailingNative())
        array = np.zeros((1, 2, 2), dtype=np.float32)
        guard.window = {'text_tokens': [1], 'num_frames': 4}
        guard.start_sequence = [99]
        guard.record = {'batched_feature_sha256': qa.array_identity(array)['sha256'],
                        'encoded_features': qa.array_identity(array)}
        guard.checkpoint = lambda: saved.append(copy.deepcopy(guard.record))
        with self.assertRaises(TimeoutError):
            guard.encode(array)
        with self.assertRaises(TimeoutError):
            guard.align(array, [99], [[1]], 4)
        self.assertTrue(saved[-1]['align_attempt_recorded'])
        self.assertEqual(saved[-1]['actual_align_request']['text_tokens'], [[1]])


if __name__ == '__main__':
    unittest.main()

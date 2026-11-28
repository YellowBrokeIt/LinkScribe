"""Synthetic controls only; retained actual results are not projected here."""
import ast
import copy
from pathlib import Path
import unittest

import replay_projection as candidate

ORIGINAL = Path('/workspace/scratch/94360995dd61/post-asr-alignment-diagnostic-2026-11-28/run_postpass.py')


def make_segments(intervals):
    return [{'start': start, 'end': end, 'text': f'Source {index}',
             'source_id': index, 'metadata': {'language': 'en', 'tokens': [index]},
             '_words': [{'word': f'Source {index}', 'start': start, 'end': end,
                         'probability': 0.75}]}
            for index, (start, end) in enumerate(intervals)]


def times(segments):
    return [(segment['start'], segment['end']) for segment in segments]


class LocalProjectionTests(unittest.TestCase):
    def test_no_conflict_is_exactly_preserved(self):
        baseline = make_segments([(0, 1), (1, 2), (2, 3)])
        proposed = make_segments([(0.1, 0.9), (1.1, 1.8), (2.1, 2.9)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 3)
        self.assertEqual(result, proposed)
        self.assertIsNot(result, proposed)
        self.assertEqual(metadata['rounds'], [])
        self.assertEqual(metadata['reverted_segment_indices'], [])

    def test_one_conflict_restores_only_its_endpoints(self):
        baseline = make_segments([(0, 1), (1, 2), (2, 3), (3, 4)])
        proposed = make_segments([(0.1, 0.9), (1.2, 2.3), (2.2, 2.9), (3.1, 3.9)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 4)
        self.assertEqual(times(result), [(0.1, 0.9), (1, 2), (2, 3), (3.1, 3.9)])
        self.assertEqual(metadata['reverted_segment_indices'], [1, 2])
        self.assertEqual(result[1]['_words'], [])
        self.assertEqual(result[2]['_words'], [])
        self.assertEqual(result[0]['_words'], proposed[0]['_words'])
        self.assertEqual(result[3]['_words'], proposed[3]['_words'])

    def test_restoration_propagates_to_a_new_neighbor(self):
        baseline = make_segments([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
        proposed = make_segments([(0.1, 0.9), (1.1, 1.9), (2.2, 3.4), (3.3, 3.6), (3.8, 4.8)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 5)
        self.assertEqual(times(result), [(0.1, 0.9), (1.1, 1.9), (2, 3), (3, 4), (4, 5)])
        self.assertEqual([item['newly_reverted_segment_indices'] for item in metadata['rounds']], [[2, 3], [4]])

    def test_chain_can_converge_to_the_complete_baseline(self):
        baseline = make_segments([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
        proposed = make_segments([(0.2, 1.2), (1.3, 2.4), (2.3, 2.7), (2.8, 3.6), (3.7, 4.9)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 5)
        self.assertEqual(times(result), times(baseline))
        self.assertEqual([item['newly_reverted_segment_indices'] for item in metadata['rounds']], [[1, 2], [0, 3], [4]])
        self.assertTrue(all(segment['_words'] == [] for segment in result))
        self.assertLessEqual(len(metadata['rounds']), len(baseline))

    def test_disjoint_conflicts_leave_intervening_candidate_unchanged(self):
        baseline = make_segments([(i, i + 1) for i in range(7)])
        proposed = make_segments([(0.1, 1.2), (1.1, 1.9), (2.1, 2.9), (3.1, 3.9),
                                  (4.1, 5.2), (5.1, 5.9), (6.1, 6.9)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 7)
        self.assertEqual(metadata['reverted_segment_indices'], [0, 1, 4, 5])
        for index in [2, 3, 6]:
            self.assertEqual(result[index], proposed[index])

    def test_equal_endpoints_and_existing_float_tolerance_are_unchanged(self):
        baseline = make_segments([(0, 1), (1, 2)])
        for start in [1, 1 - 5e-10]:
            with self.subTest(start=start):
                proposed = make_segments([(0, 1), (start, 2)])
                result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 2)
                self.assertEqual(result, proposed)
                self.assertEqual(metadata['rounds'], [])

    def test_exact_fractional_bounds_are_preserved_without_rounding(self):
        duration = 104649 / 16000
        baseline = make_segments([(0, 6.54), (6.54, duration)])
        proposed = make_segments([(0.1, 6.5403), (6.5402, duration)])
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, duration)
        self.assertEqual(times(result), times(baseline))
        self.assertEqual(result[-1]['end'], duration)
        self.assertEqual(metadata['reverted_segment_indices'], [0, 1])

    def test_metadata_tokens_text_and_inputs_are_not_mutated(self):
        baseline = make_segments([(0, 1), (1, 2)])
        proposed = make_segments([(0.1, 1.2), (1.1, 1.9)])
        proposed[0]['metadata']['extra'] = {'speaker': 'A', 'provenance': 'fixed'}
        before = copy.deepcopy((baseline, proposed))
        result, metadata = candidate.resolve_interval_conflicts(proposed, baseline, 2)
        self.assertEqual((baseline, proposed), before)
        for old, new in zip(proposed, result):
            self.assertEqual({k: v for k, v in old.items() if k not in ['start', 'end', '_words']},
                             {k: v for k, v in new.items() if k not in ['start', 'end', '_words']})
        result[0]['metadata']['extra']['speaker'] = 'B'
        self.assertEqual(proposed[0]['metadata']['extra']['speaker'], 'A')

    def test_invalid_baseline_order_fails_without_inventing_a_repair(self):
        baseline = make_segments([(0, 1.2), (1.1, 2)])
        before = copy.deepcopy(baseline)
        with self.assertRaisesRegex(ValueError, 'Original baseline overlaps'):
            candidate.resolve_interval_conflicts(baseline, baseline, 2)
        self.assertEqual(baseline, before)

    def test_invalid_candidate_intervals_are_not_clamped(self):
        baseline = make_segments([(0, 1)])
        for start, end in [(-0.1, 0.9), (0, 1.1), (0.5, 0.5), (0.8, 0.2),
                           (float('nan'), 1), (0, float('inf')), (False, 1)]:
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, 'Candidate interval'):
                candidate.resolve_interval_conflicts(make_segments([(start, end)]), baseline, 1)

    def test_invalid_physical_duration_and_baseline_fail(self):
        baseline = make_segments([(0, 1)])
        for duration in [0, -1, float('nan'), float('inf'), True]:
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'physical duration'):
                candidate.resolve_interval_conflicts(baseline, baseline, duration)
        with self.assertRaisesRegex(ValueError, 'Baseline interval'):
            candidate.resolve_interval_conflicts(baseline, make_segments([(0, 1.1)]), 1)

    def test_missing_changed_or_reordered_source_is_rejected(self):
        baseline = make_segments([(0, 1), (1, 2)])
        for proposed in [baseline[:1], list(reversed(baseline)), [{**baseline[0], 'text': 'changed'}, baseline[1]]]:
            with self.subTest(proposed=proposed), self.assertRaises(ValueError):
                candidate.resolve_interval_conflicts(proposed, baseline, 2)
        missing = [{'start': 0, 'end': 1}]
        with self.assertRaisesRegex(ValueError, 'source text'):
            candidate.resolve_interval_conflicts(missing, missing, 1)

    def test_original_per_segment_projection_prefix_is_exact(self):
        old_tree = ast.parse(ORIGINAL.read_text(encoding='utf-8'))
        new_tree = ast.parse(Path(candidate.__file__).read_text(encoding='utf-8'))
        old = next(node for node in old_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'project')
        new = next(node for node in new_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build_candidates')
        boundary = next(index for index, node in enumerate(old.body)
                        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ordered' for target in node.targets))
        self.assertEqual(ast.dump(ast.Module(body=old.body[1:boundary], type_ignores=[])),
                         ast.dump(ast.Module(body=new.body[1:-1], type_ignores=[])))

    def test_invalid_optional_words_preserve_source_and_existing_fallback(self):
        frozen = candidate.load_frozen_helper(ORIGINAL)
        view = frozen.timing_view()
        case = {'array': {'duration_seconds': 1}, 'baseline_segments': [{'start': 0, 'end': 1, 'text': 'word'}],
                'raw_segments': [{'text': ' word', 'tokens': [1]}],
                'windows': [{'seek': 0, 'num_frames': 100, 'segment_indices': [0]}]}
        adjusted = [{'text': ' word', 'tokens': [1], 'start': 0.1, 'end': 0.9,
                     'words': [{'word': ' word', 'start': 0.5, 'end': 0.5}]}]
        _, output, metadata = candidate.project(case, adjusted, {0: True}, view)
        self.assertEqual(output, [{'start': 0.1, 'end': 0.9, 'text': 'word', '_words': []}])
        self.assertTrue(any('whole-segment speaker fallback' in warning for warning in metadata['warnings']))


if __name__ == '__main__':
    unittest.main(verbosity=2)

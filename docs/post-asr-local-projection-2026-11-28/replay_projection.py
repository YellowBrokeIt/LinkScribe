"""Experimental offline projection only. No model, frontend or recognition calls."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from numbers import Real
from pathlib import Path
import sys
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def valid_interval(segment, duration):
    values = (segment.get('start'), segment.get('end'))
    return all(isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) for value in values) and 0 <= values[0] < values[1] <= duration


def conflicts(segments):
    return [{'left_index': index, 'right_index': index + 1,
             'left_end': left['end'], 'right_start': right['start'],
             'overlap_seconds': left['end'] - right['start']}
            for index, (left, right) in enumerate(zip(segments, segments[1:]))
            if right['start'] < left['end'] - 1e-9]


def resolve_interval_conflicts(candidates, baseline, duration):
    """Restore conflicting endpoints to baseline; never manufacture a timestamp.

    Both endpoints are restored together. Repeated detection catches conflicts
    introduced with adjacent candidates by that restoration. The fallback set
    grows monotonically, so an ordered baseline guarantees finite convergence.
    """
    require(isinstance(duration, Real) and not isinstance(duration, bool)
            and math.isfinite(duration) and duration > 0, 'Invalid physical duration')
    require(len(candidates) == len(baseline) > 0, 'Incomplete segment list')
    require(all(isinstance(segment.get('text'), str) and segment['text'].strip()
                for segment in baseline), 'Missing original source text')
    require(all(valid_interval(segment, duration) for segment in baseline), 'Baseline interval is not physically valid')
    require(not conflicts(baseline), 'Original baseline overlaps; no ordered fallback is available without inventing times')
    require(all(valid_interval(segment, duration) for segment in candidates), 'Candidate interval is not physically valid')
    require([segment.get('text') for segment in candidates] == [segment.get('text') for segment in baseline], 'Fixed source text or order changed')
    output = copy.deepcopy(candidates)
    reverted = set()
    rounds = []
    for round_index in range(len(output) + 1):
        found = conflicts(output)
        if not found:
            return output, {'rounds': rounds, 'reverted_segment_indices': sorted(reverted),
                            'final_ordered': True, 'baseline_was_ordered': True}
        incident = {item[key] for item in found for key in ('left_index', 'right_index')}
        newly_reverted = incident - reverted
        require(newly_reverted, 'Conflicting baseline intervals cannot be repaired by this policy')
        rounds.append({'round': round_index + 1, 'conflicts': found,
                       'incident_segment_indices': sorted(incident),
                       'newly_reverted_segment_indices': sorted(newly_reverted)})
        for index in incident:
            output[index]['start'] = baseline[index]['start']
            output[index]['end'] = baseline[index]['end']
            output[index]['_words'] = []
        reverted.update(incident)
    raise ValueError('Fallback did not converge within the finite segment bound')


def build_candidates(case, adjusted, mapping, view):
    """Exact historical per-segment projection, before its global fallback."""
    duration = case['array']['duration_seconds']
    baseline, output, warnings, fallback = [], [], [], []
    bound = view['_bounded_asr_interval']
    for original in case['baseline_segments']:
        start, end = bound(original['start'], original['end'], duration)
        baseline.append({**original, 'start': start, 'end': end})
    window_by_index = {i: window for window in case['windows'] for i in window['segment_indices']}
    for index, (original, candidate) in enumerate(zip(baseline, adjusted)):
        raw = case['raw_segments'][index]
        require(candidate['text'] == raw['text'] and candidate['tokens'] == raw['tokens'], 'Fixed source mutated')
        item = dict(original)
        words = candidate.get('words') or []
        word_text_matches = ''.join(word['word'] for word in words).strip() == original['text']
        try:
            require(mapping.get(index) and word_text_matches, 'Incomplete word-to-segment mapping')
            start, end = bound(candidate['start'], candidate['end'], duration)
            window = window_by_index[index]
            lower = window['seek'] / 100
            upper = min(duration, (window['seek'] + window['num_frames']) / 100)
            require(start >= lower - 1e-9 and end <= upper + 1e-9, 'Adjusted timing leaves original encoder window')
            item.update(start=start, end=end)
        except (ValueError, view['ReadableError']) as exc:
            warnings.append(f"Segment {index + 1}: alignment timing unavailable; original text and timing retained ({exc}).")
            fallback.append(index)
            words = []
        private, valid = [], bool(words)
        previous_end = item['start'] - 0.05
        for word in words:
            try:
                start, end = bound(word['start'], word['end'], duration)
                require(isinstance(word['word'], str) and word['word'].strip()
                        and start >= previous_end - 0.001
                        and start >= item['start'] - 0.05 and end <= item['end'] + 0.05,
                        'Invalid optional word interval')
                private.append({'word': word['word'], 'start': start, 'end': end})
                previous_end = end
            except (ValueError, TypeError, KeyError, view['ReadableError']):
                valid = False
                break
        item['_words'] = private if valid else []
        if not valid:
            warnings.append(f"Segment {index + 1}: word timing was incomplete or inconsistent; all source text retained for whole-segment speaker fallback.")
        output.append(item)
    require(len(output) == len(baseline), 'Incomplete output projection')
    return baseline, output, warnings, fallback


def project(case, adjusted, mapping, view):
    baseline, candidates, warnings, existing_fallback = build_candidates(case, adjusted, mapping, view)
    output, resolution = resolve_interval_conflicts(candidates, baseline, case['array']['duration_seconds'])
    if resolution['reverted_segment_indices']:
        warnings.append('Conflicting intervals kept their original segment timings and no private word timings; unaffected segments retained their validated timing estimates.')
    fallback = sorted(set(existing_fallback) | set(resolution['reverted_segment_indices']))
    require([segment['text'] for segment in output] == [segment['text'] for segment in baseline], 'Fixed text changed')
    return baseline, output, {'warnings': warnings, 'fallback_segment_indices': fallback,
                              'local_conflict_resolution': resolution, 'final_candidate_ordered': True}


def load_frozen_helper(path):
    path = Path(path)
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location('frozen_original_postpass', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def validate_plan(path):
    plan = read_json(path)
    require(plan['candidate'] == 'incident_segment_baseline_fallback_v1', 'Wrong projection candidate')
    require(plan['model_frontend_recognition_or_alignment_calls_allowed'] is False, 'This is offline projection only')
    for item in plan['pinned_files']:
        source = Path(item['path'])
        require(source.stat().st_size == item['bytes'] and sha256(source) == item['sha256'], 'Frozen source changed: ' + str(source))
    original = read_json(plan['input_cases_path'])
    report = read_json(plan['original_report_path'])
    require([case['id'] for case in original['cases']] == plan['case_order'], 'Changed original case order')
    require([case['id'] for case in report['case_results']] == plan['case_order'], 'Changed retained-result order')
    require(report['all_inputs_completed'] and report['recognition_performed'] is False, 'Incomplete original fixed-text stage')
    require(report['native_calls'] == {'encode': 23, 'align': 23, 'generate': 0, 'detect_language': 0}, 'Wrong original call provenance')
    manifest = read_json(plan['raw_results_manifest_path'])
    for item in manifest['files']:
        source = Path(plan['original_experiment_root']) / item['path']
        require(source.stat().st_size == item['bytes'] and sha256(source) == item['sha256'], 'Original raw output changed: ' + str(source))
    for case, result in zip(original['cases'], report['case_results']):
        require(result['status'] == 'complete' and result['source_text_unchanged'] and result['original_segment_order_unchanged'], 'Incomplete fixed source result')
        require(result['full_input']['sha256'] == case['array']['pcm_sha256']
                and result['full_input']['shape'] == case['array']['shape']
                and result['full_input']['sample_count'] == case['array']['sample_count']
                and result['full_input']['dtype'] == '<f4', 'Retained result has the wrong complete source')
        require([window['window'] for window in result['windows']] == case['windows'], 'Retained token/window mapping changed')
    return plan, original['cases'], report


def replay(plan_path, output):
    started = time.monotonic()
    plan, cases, original_report = validate_plan(plan_path)
    output = Path(output)
    require(not output.exists(), 'Output directory already exists; no repeat or overwrite is allowed')
    output.mkdir(parents=True)
    frozen = load_frozen_helper(plan['original_helper_path'])
    view = frozen.timing_view()
    report = {'schema_version': 1, 'candidate': plan['candidate'], 'plan_sha256': sha256(plan_path),
              'original_report_sha256': sha256(plan['original_report_path']),
              'new_model_frontend_recognition_alignment_or_network_calls': 0,
              'evaluation_reference_read': False, 'case_results': [], 'complete': False,
              'timing_accuracy': 'unreviewed; no production integration'}
    try:
        for case, retained in zip(cases, original_report['case_results']):
            adjusted = [None] * len(case['raw_segments'])
            mapping = {}
            for record in retained['windows']:
                window = record['window']
                segments = record['upstream_adjusted_segments']
                require(len(segments) == len(window['segment_indices']), 'Missing retained adjusted segment')
                for index, segment in zip(window['segment_indices'], segments):
                    require(adjusted[index] is None, 'Duplicate retained segment')
                    adjusted[index] = copy.deepcopy(segment)
                mapping.update(frozen.segment_mapping(record['native_words_after_merge'], window))
            require(all(segment is not None for segment in adjusted), 'Incomplete retained original segment coverage')
            baseline, candidate, projection = project(case, adjusted, mapping, view)
            directory = output / case['id']
            directory.mkdir()
            baseline_notes = frozen.exports(directory, 'baseline', baseline, view)
            candidate_notes = frozen.exports(directory, 'candidate', candidate, view)
            result = {'id': case['id'], 'status': 'complete', 'full_input': retained['full_input'],
                      'token_scope': retained['token_scope'],
                      'source_text_unchanged': [s['text'] for s in candidate] == [s['text'] for s in baseline],
                      'original_segment_order_unchanged': True, 'baseline_segments': baseline,
                      'candidate_segments': candidate, 'projection': projection,
                      'baseline_export_notes': baseline_notes, 'candidate_export_notes': candidate_notes}
            report['case_results'].append(result)
            write_json(directory / 'projection.json', result)
            write_json(output / 'report.json', report)
        report['complete'] = True
        return_code = 0
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        return_code = 1
    report['elapsed_seconds'] = time.monotonic() - started
    write_json(output / 'report.json', report)
    return return_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--validate-only', action='store_true')
    mode.add_argument('--replay', action='store_true')
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.validate_only:
        plan, cases, report = validate_plan(args.plan)
        print(json.dumps({'valid': True, 'cases': len(cases), 'actual_projection_performed': False,
                          'new_model_frontend_recognition_alignment_or_network_calls': 0}))
        return 0
    parser.error('--output is required for replay') if args.output is None else None
    return replay(args.plan, args.output)


if __name__ == '__main__':
    raise SystemExit(main())

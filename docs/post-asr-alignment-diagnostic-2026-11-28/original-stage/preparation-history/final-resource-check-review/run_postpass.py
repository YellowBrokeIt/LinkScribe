"""Isolated fixed-text timing diagnostic. Execution requires explicit CLI mode.

Preparation/validation never construct a speech model. This module does not
modify production, recognize new words, or read publisher evaluation material.
"""
from __future__ import annotations
import argparse
import ast
import copy
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from numbers import Real
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
from typing import Any

from check_native_contract import validate_native_path

ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    def safe(item):
        if isinstance(item, float) and not math.isfinite(item):
            return {'nonfinite_float': repr(item)}
        if isinstance(item, dict):
            return {key: safe(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [safe(child) for child in item]
        return item
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(safe(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def array_identity(array):
    import numpy as np
    return {'shape': list(array.shape), 'dtype': array.dtype.str, 'sample_count': int(array.size),
            'sha256': hashlib.sha256(array.tobytes()).hexdigest(), 'finite': bool(np.isfinite(array).all())}


def timing_view():
    data = json.loads((ROOT / 'production-timing-view.json').read_text(encoding='utf-8'))
    scope = {'Any': Any, 'Real': Real, 'math': math, 'Decimal': Decimal,
             'ROUND_CEILING': ROUND_CEILING, 'ROUND_FLOOR': ROUND_FLOOR}
    exec(compile('\n\n'.join(data['functions'].values()), '<frozen-6de-timing-view>', 'exec'), scope)
    return scope


def validate_case_contract(case, tokenizer):
    raw, saved = case['raw_segments'], case['baseline_segments']
    require(len(raw) == len(saved) > 0, 'Incomplete original segment list')
    require(case['array']['dtype'] == '<f4' and case['array']['sample_rate_hz'] == 16000, 'Wrong full PCM interpretation')
    n = case['array']['sample_count']
    require(case['array']['shape'] == [n] and n > 0 and case['array']['duration_seconds'] == n / 16000, 'Wrong full PCM extent')
    eot = tokenizer.token_to_id('<|endoftext|>')
    require(case['eot'] == eot, 'Wrong tokenizer end token')
    seen = []
    for index, (segment, public) in enumerate(zip(raw, saved)):
        require(segment['text'].strip() == public['text'], 'Source text changed')
        require(all(type(token) is int and token >= 0 for token in segment['tokens']), 'Invalid source token')
        text_ids = [token for token in segment['tokens'] if token < eot]
        require(text_ids and tokenizer.decode(text_ids, skip_special_tokens=False) == segment['text'], 'Original token decode changed')
    expected_seeks = list(dict.fromkeys(segment['seek'] for segment in raw))
    require([window['seek'] for window in case['windows']] == expected_seeks, 'Window order or seek changed')
    for window in case['windows']:
        seek = window['seek']
        indices = [i for i, segment in enumerate(raw) if segment['seek'] == seek]
        require(type(seek) is int and seek >= 0 and window['segment_indices'] == indices, 'Wrong segment/window map')
        require(window['num_frames'] == min(3000, n // 160 - seek) and window['num_frames'] >= 2, 'Wrong nonpadding frames')
        flat, spans = [], []
        for index in indices:
            ids = [token for token in raw[index]['tokens'] if token < eot]
            spans.append({'segment_index': index, 'start': len(flat), 'end': len(flat) + len(ids)})
            flat.extend(ids)
        require(window['text_tokens'] == flat and window['segment_token_spans'] == spans, 'Missing/reordered token or segment span')
        seen.extend(indices)
    require(seen == list(range(len(raw))), 'Incomplete global segment coverage')


def validate_plan(plan_path):
    import numpy as np
    from tokenizers import Tokenizer
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    require(plan['candidate'] == 'fixed_text_complete_upstream_postpass_v2', 'Wrong candidate')
    for entry in plan['pinned_files']:
        require(sha(entry['path']) == entry['sha256'], 'Pinned source changed: ' + entry['path'])
    for name, version in plan['runtime_packages'].items():
        require(importlib.metadata.version(name) == version, 'Runtime version changed: ' + name)
    for name, entry in plan['model']['files'].items():
        require(sha(Path(plan['model']['path']) / name) == entry['sha256'], 'Model file changed: ' + name)
    tokenizer = Tokenizer.from_file(str(Path(plan['model']['path']) / 'tokenizer.json'))
    data = json.loads(Path(plan['input_cases_path']).read_text(encoding='utf-8'))
    require(data['reference_material_included'] is False, 'Evaluation material must stay outside worker inputs')
    cases = data['cases']
    require([case['id'] for case in cases] == plan['case_order'], 'Changed or incomplete five-input selection')
    for case in cases:
        validate_case_contract(case, tokenizer)
        require(sha(case['media_path']) == case['media_sha256'], 'Source media changed')
        require(sha(case['array']['path']) == case['array']['npy_sha256'], 'Full PCM file changed')
        audio = np.load(case['array']['path'], allow_pickle=False)
        identity = array_identity(audio)
        require(identity['shape'] == case['array']['shape'] and identity['dtype'] == '<f4'
                and identity['sha256'] == case['array']['pcm_sha256'] and identity['finite'], 'Full decoded array changed')
        del audio
    return plan, cases


def segment_mapping(merged_alignment, window):
    """All native tokens remain exact; word spans may make a boundary unusable."""
    words = [word for word in merged_alignment if word['word']]
    flat = [token for word in words for token in word['tokens']]
    require(flat == window['text_tokens'], 'Upstream timing lost/reordered a recognized token')
    boundaries, offset = {0}, 0
    for word in words:
        offset += len(word['tokens'])
        boundaries.add(offset)
    return {span['segment_index']: span['start'] in boundaries and span['end'] in boundaries
            for span in window['segment_token_spans']}


def project(case, adjusted, mapping, view):
    """Keep fixed strings; optional bad evidence falls back without guessed times."""
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
    ordered = all(right['start'] >= left['end'] - 1e-9 for left, right in zip(output, output[1:]))
    if not ordered:
        output = [{**segment, '_words': []} for segment in baseline]
        fallback = list(range(len(baseline)))
        warnings.append('Adjusted intervals crossed or were unordered; complete baseline timing retained without shifting source text.')
    require([segment['text'] for segment in output] == [segment['text'] for segment in baseline], 'Source text changed in projection')
    return baseline, output, {'warnings': warnings, 'fallback_segment_indices': fallback, 'global_candidate_ordered': ordered}


def exports(directory, name, segments, view):
    public = [{key: value for key, value in segment.items() if key != '_words'} for segment in segments]
    write_json(directory / (name + '.json'), public)
    (directory / (name + '.txt')).write_text('\n'.join(segment['text'] for segment in public) + '\n', encoding='utf-8')
    notes = []
    for fmt in ('srt', 'vtt'):
        try:
            (directory / (name + '.' + fmt)).write_text(view['_render_subtitles'](public, fmt), encoding='utf-8')
        except view['SubtitleTimingError'] as exc:
            notes.append(str(exc))
    return notes


def load_monitor(plan):
    spec = importlib.util.spec_from_file_location('frozen_owned_group_monitor', plan['monitor_path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forbidden(*args, **kwargs):
    raise RuntimeError('Recognition, generation, language redetection and network calls are forbidden in this fixed-text diagnostic')


def validate_native_settings(native, plan):
    require(native.device == 'cpu' and native.compute_type in plan['expected_effective_compute_types']
            and native.num_workers == 1 and native.is_multilingual and native.n_mels == 80,
            'Unexpected native device/compute/worker setting')


class NativeGuard:
    def __init__(self, native):
        self.native = native
        self.window = None
        self.start_sequence = None
        self.record = None
        self.calls = {'encode': 0, 'align': 0, 'generate': 0, 'detect_language': 0}

    def __getattr__(self, name):
        if name in ('generate', 'detect_language'):
            def reject(*args, **kwargs):
                self.calls[name] += 1
                return forbidden()
            return reject
        return getattr(self.native, name)

    def encode(self, features, *args, **kwargs):
        import numpy as np
        require(self.window is not None, 'Encoding without a declared window')
        identity = array_identity(np.asarray(features))
        require(identity['sha256'] == self.record['batched_feature_sha256'], 'Encoded input window changed')
        self.calls['encode'] += 1
        result = self.native.encode(features, *args, **kwargs)
        self.record['encoded_features'] = array_identity(np.asarray(result))
        return result

    def align(self, encoded, start_sequence, text_tokens, num_frames, *, median_filter_width=7):
        import numpy as np
        require(start_sequence == self.start_sequence and text_tokens == [self.window['text_tokens']]
                and num_frames == self.window['num_frames'] and median_filter_width == 7, 'Native alignment request changed')
        require(array_identity(np.asarray(encoded))['sha256'] == self.record['encoded_features']['sha256'], 'Wrong encoder output')
        self.record['actual_align_request'] = {'start_sequence': start_sequence, 'text_tokens': text_tokens,
                                               'num_frames': num_frames, 'median_filter_width': median_filter_width}
        self.calls['align'] += 1
        result = self.native.align(encoded, start_sequence, text_tokens, num_frames, median_filter_width=median_filter_width)
        require(len(result) == 1, 'Wrong native result batch')
        raw = {'alignments': [list(pair) for pair in result[0].alignments], 'text_token_probs': list(result[0].text_token_probs)}
        self.record['raw_native_result'] = raw
        self.record['native_path_contract'] = validate_native_path(raw['alignments'], raw['text_token_probs'], len(self.window['text_tokens']), num_frames)
        return result


def worker(plan_path, output):
    plan, cases = validate_plan(plan_path)
    output = Path(output)
    progress = lambda **data: write_json(output / 'progress.json', data)
    progress(phase='startup', model_initialized=False)
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.create_connection = forbidden
    import numpy as np
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from faster_whisper import WhisperModel
    from faster_whisper.tokenizer import Tokenizer
    from faster_whisper.audio import pad_or_trim
    from faster_whisper.utils import get_end
    threads = min(plan['max_cpu_threads'], len(os.sched_getaffinity(0)))
    started = time.monotonic()
    engine = WhisperModel(plan['model']['path'], device='cpu', compute_type='int8', cpu_threads=threads,
                          num_workers=1, local_files_only=True)
    progress(phase='startup', model_initialized=True)
    write_json(output / 'model-initialization.json', {'model_initialized': True, 'model_path': plan['model']['path'],
               'model_revision': plan['model']['revision'], 'cpu_threads': threads, 'workers': 1,
               'device': engine.model.device, 'requested_compute_type': 'int8', 'compute_type': engine.model.compute_type})
    guard = NativeGuard(engine.model)
    engine.model = guard
    engine.transcribe = forbidden
    engine.generate_segments = forbidden
    validate_native_settings(guard.native, plan)
    require(engine.frames_per_second == 100 and engine.tokens_per_second == 50
            and engine.feature_extractor.nb_max_frames == 3000
            and engine.feature_extractor.n_fft == 400 and engine.feature_extractor.hop_length == 160,
            'Changed native feature/time coordinates')
    original_find = engine.find_alignment
    captured = {}
    def captured_find(*args, **kwargs):
        words = original_find(*args, **kwargs)
        captured['before'] = copy.deepcopy(words)
        captured['live'] = words
        return words
    engine.find_alignment = captured_find
    report = {'schema_version': 1, 'plan_sha256': sha(plan_path), 'model_initialized': True, 'recognition_performed': False,
              'candidate': plan['candidate'], 'model_initialization_seconds': time.monotonic() - started,
              'cpu_threads': threads, 'workers': 1, 'device': engine.model.device,
              'requested_compute_type': 'int8', 'compute_type': engine.model.compute_type,
              'case_results': [], 'timing_accuracy': 'unreviewed', 'semantic_quality': 'baseline source errors preserved'}
    view = timing_view()
    try:
        for case_index, case in enumerate(cases):
            case_start = time.monotonic()
            progress(phase='case', case=case['id'], case_index=case_index, case_started_monotonic=case_start, model_initialized=True)
            directory = output / case['id']
            directory.mkdir()
            result = {'id': case['id'], 'status': 'running', 'token_scope': case['token_scope'], 'windows': [], 'source_text_unchanged': False}
            report['case_results'].append(result)
            try:
                audio = np.load(case['array']['path'], allow_pickle=False)
                result['full_input'] = array_identity(audio)
                require(result['full_input']['sha256'] == case['array']['pcm_sha256'], 'Full input changed before frontend')
                features = engine.feature_extractor(audio)
                result['full_features'] = array_identity(features)
                require(features.shape == (80, len(audio) // 160 + 1) and result['full_features']['finite'], 'Wrong full-recording frontend extent')
                tokenizer = Tokenizer(engine.hf_tokenizer, True, task='transcribe', language=case['language'])
                require(tokenizer.sot_sequence == case['start_sequence'] and tokenizer.eot == case['eot'], 'Tokenizer state changed')
                guard.start_sequence = tokenizer.sot_sequence
                adjusted, mapping, state = copy.deepcopy(case['raw_segments']), {}, 0.0
                for window_number, window in enumerate(case['windows']):
                    rec = {'window': window, 'sequential_state_before': state}
                    result['windows'].append(rec)
                    guard.window, guard.record = window, rec
                    fragment = features[:, window['seek']:window['seek'] + window['num_frames']]
                    require(fragment.shape == (80, window['num_frames']), 'Truncated original window')
                    padded = pad_or_trim(fragment)
                    rec['padded_features'] = array_identity(padded)
                    rec['batched_feature_sha256'] = array_identity(np.expand_dims(padded, 0))['sha256']
                    encoded = engine.encode(padded)
                    group = [adjusted[index] for index in window['segment_indices']]
                    returned = engine.add_word_timestamps([group], tokenizer, encoded, window['num_frames'],
                                                         plan['prepend_punctuations'], plan['append_punctuations'], state)
                    rec['native_words_before_upstream_adjustments'] = captured['before'][0]
                    rec['native_words_after_merge'] = copy.deepcopy(captured['live'][0])
                    rec['upstream_adjusted_segments'] = copy.deepcopy(group)
                    rec['method_return_not_used_for_state'] = returned
                    next_state = get_end(group)
                    if next_state is not None:
                        require(math.isfinite(next_state) and 0 <= next_state <= case['array']['duration_seconds'],
                                'Nonfinite or physically impossible upstream timing state')
                        state = next_state
                    rec['sequential_state_after_get_end'] = state
                    mapping.update(segment_mapping(captured['live'][0], window))
                    require(all(adjusted[i]['text'] == case['raw_segments'][i]['text'] and adjusted[i]['tokens'] == case['raw_segments'][i]['tokens']
                                for i in window['segment_indices']), 'Upstream timing mutated source text/tokens')
                    write_json(directory / 'raw-alignment.json', result)
                    del encoded, fragment, padded
                baseline, candidate, projection = project(case, adjusted, mapping, view)
                result.update(status='complete', source_text_unchanged=True, original_segment_order_unchanged=True,
                              baseline_segments=baseline, candidate_segments=candidate, projection=projection)
                result['baseline_export_notes'] = exports(directory, 'baseline', baseline, view)
                result['candidate_export_notes'] = exports(directory, 'candidate', candidate, view)
                del audio, features
            except Exception as exc:
                result.update(status='failed', error_type=type(exc).__name__, error=str(exc), original_complete_segments=case['baseline_segments'])
                write_json(directory / 'retained-original.json', case['baseline_segments'])
            result['elapsed_seconds'] = time.monotonic() - case_start
            result['process_peak_rss_bytes_so_far'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            write_json(directory / 'raw-alignment.json', result)
            write_json(output / 'report.json', report)
            gc.collect()
        report['native_calls'] = guard.calls
        report['complete'] = len(report['case_results']) == len(cases)
        report['all_inputs_completed'] = all(item['status'] == 'complete' for item in report['case_results'])
        require(guard.calls['generate'] == guard.calls['detect_language'] == 0, 'Forbidden recognition executed')
        if report['all_inputs_completed']:
            expected = sum(len(case['windows']) for case in cases)
            require(guard.calls['encode'] == guard.calls['align'] == expected, 'Wrong encode/alignment attempt count')
    finally:
        guard.native.unload_model()
        report['model_unloaded'] = not guard.native.model_is_loaded
        report['process_peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        report['elapsed_after_model_start_seconds'] = time.monotonic() - started
        write_json(output / 'report.json', report)
        progress(phase='complete', model_initialized=True, model_unloaded=report['model_unloaded'])
    return 0 if report.get('all_inputs_completed') and report['model_unloaded'] else 1


def execute(plan_path, output):
    plan, _ = validate_plan(plan_path)
    output = Path(output)
    require(not output.exists(), 'Output directory already exists; no accidental repeat/overwrite')
    output.mkdir(parents=True)
    monitor = load_monitor(plan)
    env = dict(os.environ)
    threads = str(min(plan['max_cpu_threads'], len(os.sched_getaffinity(0))))
    env.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', ORT_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false',
               OMP_NUM_THREADS=threads, OPENBLAS_NUM_THREADS=threads, MKL_NUM_THREADS=threads, PYTHONHASHSEED='0')
    start = time.monotonic()
    limit_stop = None
    controller_error = None
    peak = 0
    with (output / 'worker.log').open('w', encoding='utf-8') as log, (output / 'resource-samples.jsonl').open('w', encoding='utf-8') as samples:
        process = subprocess.Popen([sys.executable, str(Path(__file__)), '--worker', '--plan', str(plan_path), '--output', str(output)],
                                   stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        try:
            while process.poll() is None:
                elapsed = time.monotonic() - start
                rss = monitor.group_rss(process.pid)
                peak = max(peak, rss)
                state_path = output / 'progress.json'
                state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'phase': 'startup'}
                samples.write(json.dumps({'elapsed_seconds': elapsed, 'group_rss_bytes': rss, 'phase': state.get('phase'), 'case': state.get('case')}) + '\n')
                samples.flush()
                if rss > plan['limits']['rss_bytes']:
                    limit_stop = 'owned_process_rss'
                elif elapsed > plan['limits']['total_seconds']:
                    limit_stop = 'total_wall_time'
                elif state.get('phase') == 'startup' and elapsed > plan['limits']['startup_seconds']:
                    limit_stop = 'startup_wall_time'
                elif state.get('phase') == 'case' and time.monotonic() - state['case_started_monotonic'] > plan['limits']['per_input_seconds']:
                    limit_stop = 'input_wall_time'
                if limit_stop:
                    break
                time.sleep(0.1)
        except BaseException as exc:
            controller_error = {'type': type(exc).__name__, 'message': str(exc)}
        finally:
            cleanup = monitor.terminate_owned(process)
            process.wait(timeout=10)
    result = {'schema_version': 1, 'plan_sha256': sha(plan_path), 'elapsed_seconds': time.monotonic() - start,
              'sampled_group_peak_rss_bytes': peak, 'sampling_interval_seconds': 0.1,
              'sampling_limit': 'Short peaks can occur between samples.', 'limit_stop': limit_stop,
              'worker_returncode': process.returncode, 'cleanup': cleanup, 'controller_error': controller_error}
    write_json(output / 'execution.json', result)
    return 0 if process.returncode == 0 and not limit_stop and not controller_error and not cleanup['live_group_members_after_cleanup'] else 1


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--validate-only', action='store_true')
    modes.add_argument('--execute', action='store_true')
    modes.add_argument('--worker', action='store_true')
    parser.add_argument('--plan', type=Path, default=ROOT / 'plan.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.validate_only:
        _, cases = validate_plan(args.plan)
        print(json.dumps({'valid': True, 'cases': len(cases), 'model_initialized': False, 'frontend_executed': False, 'inference_performed': False}))
        return 0
    require(args.output is not None, 'Explicit output path required')
    return execute(args.plan, args.output) if args.execute else worker(args.plan, args.output)


if __name__ == '__main__':
    raise SystemExit(main())

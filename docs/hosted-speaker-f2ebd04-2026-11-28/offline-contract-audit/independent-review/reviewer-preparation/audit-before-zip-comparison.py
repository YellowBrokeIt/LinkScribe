"""Audit retained completed outputs; no application/model code is imported."""
import array
import ast
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import wave
import zipfile

BASE = Path('/workspace/scratch/94360995dd61')
REPO = BASE / 'LinkScribe'
SOURCE = BASE / 'hosted-f2ebd04-speaker-review'
ARTIFACT = SOURCE / 'artifact'
OUT = Path(__file__).resolve().parent
HEAD = 'f2ebd0433976ed62478b67e98c4515e3d78afaa5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def committed(path):
    return subprocess.check_output(['git', 'show', HEAD + ':' + path], cwd=REPO)


def text(items):
    return ' '.join(' '.join(item['text'].split()) for item in items)


checks = []


def check(name, result):
    checks.append({'name': name, 'passed': bool(result)})
    if not result:
        raise AssertionError(name)


manifest = read(SOURCE / 'artifact-manifest.json')
metadata = read(SOURCE / 'artifacts-metadata.json')['artifacts'][0]
plan = read(SOURCE / 'published-hosted-plan.json')
preparation = read(ARTIFACT / 'preparation.json')
execution = read(ARTIFACT / 'execution.json')
report = read(ARTIFACT / 'speaker-app-report.json')
check('original_workflow_failure_retained', execution['passed'] is False and execution['final_failure'] == {'type': 'ValueError', 'message': 'Unexpected native model runtime'})
check('exact_head_and_run', execution['github_sha'] == metadata['workflow_run']['head_sha'] == HEAD and metadata['workflow_run']['id'] == 46123086352)
check('published_zip_digest_and_size', metadata['id'] == 15254526534 and metadata['size_in_bytes'] == (SOURCE / 'artifact.zip').stat().st_size and metadata['digest'] == 'sha256:' + sha(SOURCE / 'artifact.zip'))
for item in manifest['files']:
    path = ARTIFACT / item['path']
    check('retained/' + item['path'], path.stat().st_size == item['bytes'] and sha(path) == item['sha256'])
check('complete_artifact_inventory', sorted(item['path'] for item in manifest['files']) == sorted(str(path.relative_to(ARTIFACT)) for path in ARTIFACT.rglob('*') if path.is_file()))
check('exact_followup_plan', sha(SOURCE / 'published-hosted-plan.json') == execution['plan_sha256'] == '30e723794e53facc18bd88675c81d402ae8bce846aca38d5338ff5065459abec')
check('plan_matches_actual_commit', committed('docs/asr-speaker-hosted-followup-2026-11-28/hosted-plan.json') == (SOURCE / 'published-hosted-plan.json').read_bytes())
for item in plan['source_files']:
    check('commit/' + item['path'], hashlib.sha256(committed(item['path'])).hexdigest() == item['sha256'])
for path, digest in report['source_sha256'].items():
    check('worker_source/' + path, hashlib.sha256(committed(path)).hexdigest() == digest)
check('runtime_and_preparation_complete', preparation['complete'] is True and preparation['model_constructed'] is False and preparation['runtime_packages'] == plan['runtime_packages'])
for family, model in plan['models'].items():
    for name, expected in model['files'].items():
        got = preparation['models'][family][name]
        check('transfer/' + family + '/' + name, got['sha256'] == expected['sha256'] and 0 < got['bytes'] <= expected['maximum_bytes'])
yaml = ARTIFACT / 'speaker-hyperparams.yaml'
check('actual_pinned_yaml_retained', sha(yaml) == plan['models']['speaker']['files']['hyperparams.yaml']['sha256'])
declarations = read(ARTIFACT / 'speaker-cache-declarations.json')
label = declarations['declarations']['label_encoder']
check('actual_label_remote_local_mapping', label['source_filename'] == 'label_encoder.txt' and label['seeded_filename'] == 'label_encoder.ckpt' and '<pretrained_path>/label_encoder.txt' in yaml.read_text())
label_transfer = preparation['models']['speaker']['label_encoder.ckpt']
check('actual_label_payload_identity', label_transfer['source_filename'] == 'label_encoder.txt' and label_transfer['local_filename'] == 'label_encoder.ckpt' and label_transfer['sha256'] == 'e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9')

wave_path = ARTIFACT / 'inputs' / plan['fixture']['filename']
with wave.open(str(wave_path), 'rb') as stream:
    sample_count = stream.getnframes()
    check('full_original_wav', stream.getnchannels() == 1 and stream.getsampwidth() == 2 and stream.getframerate() == 16000 and sample_count == 554160 and sha(wave_path) == plan['fixture']['sha256'] == report['audio']['sha256'])
    values = array.array('h', stream.readframes(sample_count))
if sys.byteorder != 'little':
    values.byteswap()
pcm_sha = hashlib.sha256(b''.join(struct.pack('<f', value / 32768.0) for value in values)).hexdigest()
duration = sample_count / 16000
expected_wave = {'shape': [sample_count], 'dtype': 'float32', 'sample_count': sample_count, 'sha256': pcm_sha}
recognition = report['actual_transcribe_calls'][0]
timing = report['fixed_text_timing_calls'][0]
check('one_full_recognition_and_optional_timing', len(report['actual_transcribe_calls']) == len(report['fixed_text_timing_calls']) == len(report['actual_recognizer_calls']) == 1)
check('same_full_pcm_for_asr_timing_and_speaker_decode', recognition['waveform'] == timing['waveform'] == report['speaker_decode_calls'][0]['waveform'] == expected_wave and pcm_sha == preparation['fixture']['decoded_pcm_sha256'])
expected_options = {'language': None, 'beam_size': 5, 'vad_filter': False, 'no_speech_threshold': 0.6, 'condition_on_previous_text': False, 'word_timestamps': False}
check('unchanged_recognition_request', recognition['options'] == expected_options)
effective = recognition['effective_options']
check('unchanged_effective_policy_no_hints', effective['word_timestamps'] is False and effective['beam_size'] == 5 and effective['condition_on_previous_text'] is False and effective['no_speech_threshold'] == 0.6 and effective['hallucination_silence_threshold'] is None and effective['clip_timestamps'] == '0' and effective['initial_prompt'] is None and effective['prefix'] is None and effective['hotwords'] is None)
check('generator_completed_before_timing', recognition['generator_exhausted'] is True and timing['completed'] is True)
check('exact_raw_segment_transfer', timing['raw_segments'] == [item for item in recognition['raw_segments'] if item['text'].strip()])
check('exact_baseline_and_timing_transfer', timing['baseline_segments'] == report['actual_recognizer_calls'][0]['segments'] and timing['segments'] == report['actual_speaker_calls'][0]['input_segments'])
init = report['model_initializations'][0]
check('one_same_native_engine', len(report['model_initializations']) == 1 and init['completed'] and init['engine_identity'] == recognition['engine_identity'] == timing['engine_identity'])
check('source_faithful_constructor_default_zero', init['model'] == 'small' and init['cpu_threads'] == 0 and init['num_workers'] == 1 and init['requested_device'] == init['actual_device'] == 'cpu' and init['requested_compute_type'] == 'int8' and init['actual_compute_type'] in {'int8', 'int8_float32'} and init['feature_rows'] == 80)
resolution = report['model_resolutions'][0]
check('actual_exact_small_model_files', len(report['model_resolutions']) == 1 and resolution['revision_directory'] == plan['models']['recognizer']['revision'] and resolution['files'] == {name: {'bytes': row['bytes'], 'sha256': row['sha256']} for name, row in plan['models']['recognizer']['files'].items()})

groups = []
for segment in timing['raw_segments']:
    if not groups or groups[-1]['seek'] != segment['seek']:
        groups.append({'seek': segment['seek'], 'tokens': []})
    groups[-1]['tokens'].extend(token for token in segment['tokens'] if token < 50257)
check('exact_original_two_seek_windows', [group['seek'] for group in groups] == [0, 2660] and len(report['timing_encode_calls']) == len(report['native_align_calls']) == len(groups) == 2)
native_summaries = []
for group, encoded, aligned in zip(groups, report['timing_encode_calls'], report['native_align_calls']):
    frames = min(3000, sample_count // 160 - group['seek'])
    check('native_tokens_and_frames/' + str(group['seek']), aligned['text_tokens'] == [group['tokens']] and aligned['num_frames'] == frames and aligned['start_sequence'] == [50258, 50259, 50359] and aligned['options'] == {'median_filter_width': 7})
    check('native_return_before_validation/' + str(group['seek']), aligned['completed'] and aligned['native_returned'] and aligned['contract_validated'] and encoded['feature_shape'] == [80, 3000] and len(encoded['feature_sha256']) == 64)
    result = aligned['native_results'][0]
    path, probabilities = result['alignments'], result['text_token_probs']
    check('full_monotone_native_path/' + str(group['seek']), len(aligned['native_results']) == 1 and path[0] == [0, 0] and path[-1] == [len(group['tokens']), frames // 2 - 1] and all(len(point) == 2 and all(type(value) is int for value in point) and 0 <= point[0] <= len(group['tokens']) and 0 <= point[1] < frames // 2 for point in path) and all((b[0] - a[0], b[1] - a[1]) in {(0, 1), (1, 0), (1, 1)} for a, b in zip(path, path[1:])))
    check('native_token_probability_binding/' + str(group['seek']), len(probabilities) == len(group['tokens']) and all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities))
    native_summaries.append({'seek': group['seek'], 'text_tokens': len(group['tokens']), 'num_frames': frames, 'path_points': len(path), 'terminal': path[-1], 'feature_sha256': encoded['feature_sha256']})


def bounded_ordered(items):
    return all(math.isfinite(item['start']) and math.isfinite(item['end']) and 0 <= item['start'] < item['end'] <= duration for item in items) and all(a['end'] <= b['start'] for a, b in zip(items, items[1:]))


check('all_eight_timing_segments_keep_text_and_bounds', len(timing['segments']) == 8 and [item['text'] for item in timing['segments']] == [item['text'] for item in timing['baseline_segments']] and bounded_ordered(timing['segments']))
for number, segment in enumerate(timing['segments']):
    words = segment['_words']
    check('real_word_evidence/' + str(number), bool(words) and bounded_ordered(words) and ' '.join(''.join(word['word'] for word in words).split()) == ' '.join(segment['text'].split()) and words[0]['start'] >= segment['start'] - 0.05 and words[-1]['end'] <= segment['end'] + 0.05)
check('timing_completed_without_fallback_warning', timing['warnings'] == [] and timing['provenance'] == {'method': 'fixed_text_postpass', 'status': 'complete', 'segment_count': 8, 'word_timed_segments': 8, 'original_timing_segments': 0})
release = report['audio_model_release_calls'][0]
check('recognizer_released_before_speakers', len(report['audio_model_release_calls']) == 1 and release['options'] == {'recognizer_only': True} and release['before']['recognizer'] == 1 and release['after']['recognizer'] == 0 and release['recognizer_references_released'] and report['actual_speaker_calls'][0]['recognizer_released_before_call'])
acoustic = report['acoustic_analysis_calls'][0]['result']
check('actual_acoustic_source_and_model', len(report['acoustic_analysis_calls']) == 1 and report['acoustic_analysis_calls'][0]['completed'] and report['acoustic_analysis_calls'][0]['source_sha256'] == report['audio']['sha256'] and acoustic['model']['revision'] == plan['models']['speaker']['revision'] and acoustic['model']['sha256'] == {name: row['sha256'] for name, row in plan['models']['speaker']['files'].items()} and acoustic['audio_seconds'] == duration)
check('acoustic_turns_physically_bounded', bounded_ordered(acoustic['turns']) and acoustic['overlapping_speech_supported'] is False)

record = report['record']
segments = record['segments']
check('saved_text_labels_and_timing_preserved', len(segments) == 19 and bounded_ordered(segments) and text(segments) == text(timing['baseline_segments']) and all('_words' not in item for item in segments))
check('speaker_result_matches_saved_record', report['actual_speaker_calls'][0]['result']['segments'] == segments)
warnings = record['processing_metadata']['warnings']
check('warnings_preserved_and_limited', len(warnings) == 4 and warnings == report['job']['warnings'] == report['actual_speaker_calls'][0]['result']['warnings'] == record['processing_metadata']['speakers']['warnings'])
check('no_text_enhancement_requested', report['upload_form'] == {'consent': 'true', 'speakers': 'true', 'target_language': 'none', 'summary': 'false'} and record['translations'] == {} and record['summary'] is None and record['highlights'] is None)
run_dir = next(ARTIFACT.glob('speaker-app-report-artifacts-*'))
with sqlite3.connect('file:' + str(run_dir / 'library.sqlite3') + '?mode=ro&immutable=1', uri=True) as db:
    db.row_factory = sqlite3.Row
    stored = dict(db.execute('SELECT * FROM transcripts WHERE id=?', (record['id'],)).fetchone())
for key in ['segments', 'translations', 'summary', 'highlights', 'processing_metadata']:
    stored[key] = json.loads(stored[key]) if stored[key] is not None else None
check('independent_sqlite_reload', stored == record == report['separate_process_sqlite']['record'])
export = read(run_dir / 'transcript.json')
check('json_export_preserves_saved_fields', all(export[key] == record[key] for key in export))
check('txt_export_preserves_each_group', (run_dir / 'transcript.txt').read_text().splitlines() == [item['speaker'] + ': ' + item['text'] for item in segments])
for format_name, expected in report['exports'].items():
    check('export_hash/' + format_name, sha(run_dir / ('transcript.' + format_name)) == expected['sha256'])
    check('job_export/' + format_name, (run_dir / ('transcript.' + format_name)).read_bytes() == (run_dir / 'jobs' / record['id'] / ('transcript.' + format_name)).read_bytes())


def milliseconds(value):
    hours, minutes, seconds, millis = re.split('[:,.]', value)
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)


for format_name in ['srt', 'vtt']:
    content = (run_dir / ('transcript.' + format_name)).read_text()
    pairs = re.findall(r'(\d+:\d{2}:\d{2}[,.]\d{3}) --> (\d+:\d{2}:\d{2}[,.]\d{3})', content)
    check('subtitle_count/' + format_name, len(pairs) == len(segments))
    for number, ((start, end), segment) in enumerate(zip(pairs, segments)):
        a, b = milliseconds(start), milliseconds(end)
        check('inward_physical_subtitle/' + format_name + '/' + str(number), 0 <= a < b <= sample_count // 16 and a >= int((Decimal(str(segment['start'])) * 1000).to_integral_value(rounding=ROUND_CEILING)) and b <= int((Decimal(str(segment['end'])) * 1000).to_integral_value(rounding=ROUND_FLOOR)))
with zipfile.ZipFile(run_dir / 'transcript.zip') as archive:
    check('zip_contains_exact_exports', sorted(archive.namelist()) == ['transcript.json', 'transcript.srt', 'transcript.txt', 'transcript.vtt'] and all(archive.read(name) == (run_dir / name).read_bytes() for name in archive.namelist()))
with zipfile.ZipFile(run_dir / 'library-backup.zip') as archive:
    backup = json.loads(archive.read('transcripts.json'))
    metadata = json.loads(archive.read('manifest.json'))
    check('backup_preserves_exact_record_and_notes', backup['version'] == 2 and backup['records'] == [record] and metadata['sha256'] == hashlib.sha256(archive.read('transcripts.json')).hexdigest())

sample_path = ARTIFACT / 'resource-samples.jsonl'
samples = [json.loads(line) for line in sample_path.read_text().splitlines()]
check('all_111_samples_bound', len(samples) == execution['sample_count'] == 111 and sha(sample_path) == execution['resource_samples_sha256'])
check('sample_time_order', all(math.isfinite(item['elapsed_seconds']) and 0 <= item['elapsed_seconds'] <= execution['elapsed_seconds'] for item in samples) and all(a['elapsed_seconds'] < b['elapsed_seconds'] for a, b in zip(samples, samples[1:])))
check('every_owned_sample_complete', all(item['complete'] is True and item['read_errors'] == [] and item['rss_bytes'] == sum(member['rss_bytes'] for member in item['members']) and all(isinstance(member['rss_bytes'], int) and member['rss_bytes'] >= 0 for member in item['members']) for item in samples))
peak = max(item['rss_bytes'] for item in samples)
check('sampled_and_os_high_water_within_limit', peak == execution['sampled_group_peak_rss_bytes'] <= plan['rss_limit_bytes'] and 0 < report['peak_process_rss_bytes'] <= plan['rss_limit_bytes'])
check('recorded_total_and_phase_limits', 0 < report['elapsed_seconds'] <= execution['elapsed_seconds'] <= plan['total_worker_seconds'] and all(0 <= item['elapsed_seconds'] <= plan['phase_seconds'].get(item['name'], plan['total_worker_seconds']) for item in report['phases']))
check('complete_successful_worker_and_cleanup', report['complete'] is True and execution['returncode'] == 0 and execution['stop_reason'] is None and execution['all_resource_samples_complete'] and execution['cleanup']['leader_exited'] and execution['cleanup']['live_group_members_after_cleanup'] == [] and execution['cleanup']['strict_final_sample'] == {'rss_bytes': 0, 'members': [], 'read_errors': [], 'complete': True})
check('recorded_four_cpu_launch_set', execution['cpu_affinity'] == [0, 1, 2, 3] and len(execution['cpu_affinity']) == plan['maximum_cpus'] == 4)
controller = committed('tests/qa_speaker_integration.py').decode()
check('source_enforces_launch_affinity_and_omp', 'preexec_fn=lambda: os.sched_setaffinity(0, cpus)' in controller and 'OMP_NUM_THREADS=str(len(cpus)), MKL_NUM_THREADS=str(len(cpus))' in controller)
check('original_gate_rejection_is_constructor_mismatch', 'report["model_initializations"][0]["cpu_threads"] == 4' in controller and init['cpu_threads'] == 0)
app_tree = ast.parse(committed('app.py').decode())
factory = next(node for node in app_tree.body if isinstance(node, ast.FunctionDef) and node.name == '_whisper_model')
constructor = next(node for node in ast.walk(factory) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'WhisperModel')
check('production_does_not_override_cpu_threads', all(keyword.arg != 'cpu_threads' for keyword in constructor.keywords))
primary = SOURCE / 'thread-source'
for item in read(primary / 'source-provenance.json'):
    content = (primary / item['retained_file']).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    check('pinned_thread_source/' + item['path'], len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'] and blob == item['git_blob_sha1'])
check('source_zero_means_omp_or_default', 'cpu_threads: int = 0' in (primary / 'faster-whisper-1.2.1-transcribe.py').read_text() and 'intra_threads=cpu_threads' in (primary / 'faster-whisper-1.2.1-transcribe.py').read_text() and 'if (num_threads == 0)\n      num_threads = read_int_from_env("OMP_NUM_THREADS", get_default_num_threads());' in (primary / 'ct2-utils.cc').read_text())

result = {
    'scope': 'Independent retained artifact, source, complete PCM, raw alignment, resource and persistence audit. No model/application/native inference executed and no original artifact or gate changed.',
    'head_sha': HEAD, 'run_id': 46123086352, 'job_id': 140911610658, 'artifact_id': 15254526534,
    'checks': checks, 'errors': [], 'original_hosted_gate_result': 'failed; preserved',
    'original_failure': execution['final_failure'], 'source_faithful_constructor_argument': init['cpu_threads'],
    'native_runtime': init, 'inference_side_affinity_readback_available': False,
    'affinity_evidence_scope': 'Recorded four-CPU set passed through successful Popen preexec sched_setaffinity; source sets OMP/MKL to4. This is launch enforcement/source evidence, not an independent in-worker readback or a measurement of effective native thread count.',
    'full_pcm_sha256': pcm_sha, 'duration_seconds': duration, 'native_alignment_summary': native_summaries,
    'saved_groups': len(segments), 'unassigned_saved_groups': sum(item['speaker'] == 'Unknown speaker' for item in segments),
    'word_timed_segments': 8, 'timing_fallback_warnings': timing['warnings'],
    'resources': {'complete_samples': len(samples), 'sampled_group_peak_rss_bytes': peak, 'worker_os_peak_rss_bytes': report['peak_process_rss_bytes'], 'worker_elapsed_seconds': report['elapsed_seconds'], 'controller_elapsed_seconds': execution['elapsed_seconds'], 'phase_seconds': report['phases'], 'owned_group_cleanup_complete': True},
    'identities': {name: identity(ARTIFACT / name) for name in ['speaker-app-report.json', 'execution.json', 'preparation.json', 'resource-samples.jsonl', 'speaker-hyperparams.yaml', 'speaker-cache-declarations.json']},
    'acoustic_scoring': identity(OUT / 'original-acoustic-score.json'),
    'limits': ['The full recorded feature matrices are not in the artifact; native feature hashes and full-input/token-bound adapter execution are verified without recomputing features.', 'No word-level human timestamp reference or audio listening review is claimed.', 'No text enhancement was requested, so this run observes recognizer release before speakers, not a live ASR/speaker-to-Ollama transition.', 'The raw acoustic score concerns one previously exposed concatenated English reading fixture; it is not meeting, Greek, overlap or broader ASR accuracy evidence.'],
}
destination = OUT / 'retained-result-audit.json'
destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'path': str(destination), 'sha256': sha(destination), 'checks': len(checks), 'errors': []}))

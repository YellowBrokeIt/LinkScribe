"""Audit retained completed outputs; no application/model code is imported."""
import array
import ast
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import sys
import wave
import zipfile

BASE = Path('/workspace/scratch/94360995dd61')
REPO = BASE / 'LinkScribe'
SOURCE = BASE / 'hosted-11e3365-root'
ARTIFACT = SOURCE / 'speaker'
OUT = Path(__file__).resolve().parent
HEAD = '11e336577c7980f8da9dd817f265472596347a48'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def observed_source(path):
    # Read current bytes only; compare with the actual plan/report hashes below.
    # HEAD provenance comes from retained GitHub metadata, not a new Git command.
    return (REPO / path).read_bytes()


def text(items):
    return ' '.join(' '.join(item['text'].split()) for item in items)


checks = []


def check(name, result):
    checks.append({'name': name, 'passed': bool(result)})
    if not result:
        raise AssertionError(name)


manifest = read(SOURCE / 'speaker-artifact-manifest.json')
speaker_artifact_metadata = next(row for row in read(SOURCE / 'speaker-artifacts-metadata.json')['artifacts'] if row['id'] == 15254889987)
PLAN_PATH = REPO / 'docs/asr-speaker-constructor-followup-2026-11-28/hosted-plan.json'
plan = read(PLAN_PATH)
preparation = read(ARTIFACT / 'preparation.json')
execution = read(ARTIFACT / 'execution.json')
report = read(ARTIFACT / 'speaker-app-report.json')
check('current_hosted_success', execution['passed'] is True and execution['pipeline_contract_pass'] is True and execution['controlled_fixture_acoustic_pass'] is True)
check('exact_head_and_run', execution['github_sha'] == speaker_artifact_metadata['workflow_run']['head_sha'] == HEAD and speaker_artifact_metadata['workflow_run']['id'] == 46126494171)
check('published_zip_digest_and_size', speaker_artifact_metadata['id'] == 15254889987 and speaker_artifact_metadata['size_in_bytes'] == (SOURCE / 'speaker-artifact.zip').stat().st_size and speaker_artifact_metadata['digest'] == 'sha256:' + sha(SOURCE / 'speaker-artifact.zip'))
for item in manifest['files']:
    path = ARTIFACT / item['path']
    check('retained/' + item['path'], path.stat().st_size == item['bytes'] and sha(path) == item['sha256'])
check('complete_artifact_inventory', sorted(item['path'] for item in manifest['files']) == sorted(str(path.relative_to(ARTIFACT)) for path in ARTIFACT.rglob('*') if path.is_file()))
check('exact_followup_plan', sha(PLAN_PATH) == execution['plan_sha256'] == '3a613e540873888ffeb0007b4817d1dfabd8d8470033f8b935bb7e991ce4ecca')
check('actual_preflight_and_plan_head', read(ARTIFACT / 'preflight.json')['github_sha'] == HEAD and read(ARTIFACT / 'preflight.json')['plan_sha256'] == sha(PLAN_PATH))
for item in plan['source_files']:
    check('observed_source_matches_actual_plan/' + item['path'], hashlib.sha256(observed_source(item['path'])).hexdigest() == item['sha256'])
for path, digest in report['source_sha256'].items():
    check('worker_source/' + path, hashlib.sha256(observed_source(path)).hexdigest() == digest)
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
check('saved_text_labels_and_timing_preserved', len(segments) == 21 and bounded_ordered(segments) and text(segments) == text(timing['baseline_segments']) and all('_words' not in item for item in segments))
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
    if format_name != 'zip':
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
with zipfile.ZipFile(run_dir / 'transcript.zip') as exported_zip, zipfile.ZipFile(run_dir / 'jobs' / record['id'] / 'transcript.zip') as job_zip:
    check('job_and_download_zip_payloads_identical', sorted(exported_zip.namelist()) == sorted(job_zip.namelist()) and all(exported_zip.read(name) == job_zip.read(name) for name in exported_zip.namelist()))
with zipfile.ZipFile(run_dir / 'library-backup.zip') as archive:
    backup = json.loads(archive.read('transcripts.json'))
    metadata = json.loads(archive.read('manifest.json'))
    check('backup_preserves_exact_record_and_notes', backup['version'] == 2 and backup['records'] == [record] and metadata['sha256'] == hashlib.sha256(archive.read('transcripts.json')).hexdigest())

sample_path = ARTIFACT / 'resource-samples.jsonl'
samples = [json.loads(line) for line in sample_path.read_text().splitlines()]
check('all_166_samples_bound', len(samples) == execution['sample_count'] == 166 and sha(sample_path) == execution['resource_samples_sha256'])
check('sample_time_order', all(math.isfinite(item['elapsed_seconds']) and 0 <= item['elapsed_seconds'] <= execution['elapsed_seconds'] for item in samples) and all(a['elapsed_seconds'] < b['elapsed_seconds'] for a, b in zip(samples, samples[1:])))
check('every_owned_sample_complete', all(item['complete'] is True and item['read_errors'] == [] and item['rss_bytes'] == sum(member['rss_bytes'] for member in item['members']) and all(isinstance(member['rss_bytes'], int) and member['rss_bytes'] >= 0 for member in item['members']) for item in samples))
peak = max(item['rss_bytes'] for item in samples)
check('sampled_and_os_high_water_within_limit', peak == execution['sampled_group_peak_rss_bytes'] <= plan['rss_limit_bytes'] and 0 < report['peak_process_rss_bytes'] <= plan['rss_limit_bytes'])
check('recorded_total_and_phase_limits', 0 < report['elapsed_seconds'] <= execution['elapsed_seconds'] <= plan['total_worker_seconds'] and all(0 <= item['elapsed_seconds'] <= plan['phase_seconds'].get(item['name'], plan['total_worker_seconds']) for item in report['phases']))
check('complete_successful_worker_and_cleanup', report['complete'] is True and execution['returncode'] == 0 and execution['stop_reason'] is None and execution['all_resource_samples_complete'] and execution['cleanup']['leader_exited'] and execution['cleanup']['live_group_members_after_cleanup'] == [] and execution['cleanup']['strict_final_sample'] == {'rss_bytes': 0, 'members': [], 'read_errors': [], 'complete': True})
check('recorded_four_cpu_launch_set', execution['cpu_affinity'] == [0, 1, 2, 3] and len(execution['cpu_affinity']) == plan['maximum_cpus'] == 4)
controller = observed_source('tests/qa_speaker_integration.py').decode()
check('source_enforces_launch_affinity_and_omp', 'preexec_fn=lambda: os.sched_setaffinity(0, cpus)' in controller and 'OMP_NUM_THREADS=str(len(cpus)), MKL_NUM_THREADS=str(len(cpus))' in controller)
check('maintained_gate_matches_actual_constructor_default', 'report["model_initializations"][0]["cpu_threads"] == 0' in controller and init['cpu_threads'] == 0)
app_tree = ast.parse(observed_source('app.py').decode())
factory = next(node for node in app_tree.body if isinstance(node, ast.FunctionDef) and node.name == '_whisper_model')
constructor = next(node for node in ast.walk(factory) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'WhisperModel')
check('production_does_not_override_cpu_threads', all(keyword.arg != 'cpu_threads' for keyword in constructor.keywords))
primary = BASE / 'hosted-f2ebd04-speaker-review/thread-source'
for item in read(primary / 'source-provenance.json'):
    content = (primary / item['retained_file']).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    check('pinned_thread_source/' + item['path'], len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'] and blob == item['git_blob_sha1'])
check('source_zero_means_omp_or_default', 'cpu_threads: int = 0' in (primary / 'faster-whisper-1.2.1-transcribe.py').read_text() and 'intra_threads=cpu_threads' in (primary / 'faster-whisper-1.2.1-transcribe.py').read_text() and 'if (num_threads == 0)\n      num_threads = read_int_from_env("OMP_NUM_THREADS", get_default_num_threads());' in (primary / 'ct2-utils.cc').read_text())

# Independently score the unchanged reference cores using stdlib arithmetic,
# without importing the application or its NumPy/SciPy scoring helper.
truth = sorted({row['speaker'] for row in plan['fixture']['reference_intervals']})
predicted = sorted({row['speaker'] for row in acoustic['turns'] if row['speaker'] is not None})
matrix = {(actual, label): 0 for actual in truth for label in predicted}
intervals = []
total = assigned = 0
for reference in plan['fixture']['reference_intervals']:
    first = Decimal(str(reference['start'])) + Decimal('0.75')
    last = Decimal(str(reference['end'])) - Decimal('0.75')
    count = int(((last - first) / Decimal('0.1')).to_integral_value(rounding=ROUND_CEILING))
    counts = {}
    for number in range(count):
        moment = float(first + Decimal('0.1') * number)
        label = next((turn['speaker'] for turn in acoustic['turns']
                      if turn['start'] <= moment < turn['end']), None)
        total += 1
        counts[str(label)] = counts.get(str(label), 0) + 1
        if label is not None:
            assigned += 1
            matrix[(reference['speaker'], label)] += 1
    intervals.append({'reference': reference, 'core_samples': count, 'label_counts': counts})
best = max(itertools.permutations(predicted), key=lambda labels: sum(matrix[(t, p)] for t, p in zip(truth, labels)))
correct = sum(matrix[(t, p)] for t, p in zip(truth, best))
score = {'status': 'passed' if len(predicted) == 2 and assigned / total >= 0.8 and correct / assigned >= 0.95 else 'failed',
         'expected_speakers_for_scoring_only': 2, 'reported_speakers': acoustic['speaker_count'],
         'core_samples': total, 'assigned_core_fraction': round(assigned / total, 4),
         'permutation_matched_label_purity': round(correct / assigned, 4),
         'correctly_attributed_core_fraction': round(correct / total, 4),
         'mapping_for_scoring_only': {p: t for t, p in zip(truth, best)}, 'per_interval': intervals}
check('independent_original_acoustic_score_exact', score == execution['controlled_fixture_acoustic_assessment'])
check('original_thresholds_unchanged', plan['controlled_fixture_criteria']['minimum_assigned_core_fraction'] == 0.8
      and plan['controlled_fixture_criteria']['minimum_permutation_matched_label_purity'] == 0.95)
(OUT / 'independent-acoustic-score.json').write_text(json.dumps(score, indent=2) + '\n')

speaker_job = read(SOURCE / 'speaker-jobs-metadata.json')['jobs'][0]
check('actual_speaker_job_head_and_success', speaker_job['id'] == 140922130930
      and speaker_job['run_id'] == 46126494171 and speaker_job['head_sha'] == HEAD
      and speaker_job['status'] == 'completed' and speaker_job['conclusion'] == 'success')
with zipfile.ZipFile(SOURCE / 'speaker-artifact.zip') as outer:
    check('speaker_zip_complete_inventory_and_payloads', sorted(outer.namelist()) == sorted(row['path'] for row in manifest['files'])
          and all(outer.read(row['path']) == (ARTIFACT / row['path']).read_bytes() for row in manifest['files']))

# The install evidence artifact is local; the actual source archive remains a
# separately identified hosted artifact and is deliberately not downloaded.
install_dir = SOURCE / 'install'
install = read(install_dir / 'installation.json')
install_manifest = read(SOURCE / 'install-artifact-manifest.json')
artifact_metadata = read(SOURCE / 'candidate-artifacts-metadata.json')['artifacts']
install_metadata = next(row for row in artifact_metadata if row['id'] == 15255569442)
source_metadata = next(row for row in artifact_metadata if row['id'] == 15254769950)
check('install_artifact_github_digest', install_metadata['digest'] == 'sha256:' + sha(SOURCE / 'install-artifact.zip')
      and install_metadata['size_in_bytes'] == (SOURCE / 'install-artifact.zip').stat().st_size
      and install_manifest['zip_sha256'] == sha(SOURCE / 'install-artifact.zip'))
check('all_artifact_metadata_same_exact_source', all(row['workflow_run']['head_sha'] == HEAD for row in
      (speaker_artifact_metadata, install_metadata, source_metadata)) and source_metadata['workflow_run']['id'] == 46126494141
      and install_metadata['workflow_run']['id'] == 46126494141)
for row in install_manifest['files']:
    path = install_dir / row['path']
    check('install_retained/' + row['path'], path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
with zipfile.ZipFile(SOURCE / 'install-artifact.zip') as outer:
    check('install_zip_exact_payloads', sorted(outer.namelist()) == sorted(row['path'] for row in install_manifest['files'])
          and all(outer.read(row['path']) == (install_dir / row['path']).read_bytes() for row in install_manifest['files']))
expected_install_checks = ['archive provenance and safe extraction', 'actual start_linux.sh, fresh venv and /health',
                           'setup diagnostics', 'packaged static homepage', 'fresh SQLite library',
                           'installed dependency consistency']
check('six_actual_install_checks_passed', install['status'] == 'passed' and install['checks'] == expected_install_checks
      and 'error' not in install and install['source']['commit'] == HEAD
      and install['source']['repository'] == 'YellowBrokeIt/LinkScribe')
check('source_archive_receipt_scope', install['source']['artifact'] == 'LinkScribe-candidate-source.zip'
      and install['source']['sha256'] == '466443904cfff8cd68c90ffa72338810a4dd7b3315393727a688d5af6b29d4f1'
      and install['source']['members'] == 2831 and install['source']['uncompressed_bytes'] == 86366233)
check('source_outer_artifact_distinct_identity', source_metadata['digest'] ==
      'sha256:96e433fb4936364108be7823be173680be70e580fe3c8088cde5bd011f8ff4de'
      and source_metadata['size_in_bytes'] == 41996185
      and source_metadata['digest'] != 'sha256:' + install['source']['sha256'])
launcher_log = (install_dir / 'launcher.log').read_text()
check('standard_requirements_installed_curl_cffi',
      'Collecting curl-cffi<0.18,>=0.17 (from -r requirements.txt (line 8))' in launcher_log
      and 'curl-cffi-0.17.0' in launcher_log and 'Successfully installed ' in launcher_log)
for endpoint in ('/health', '/api/diagnostics', '/', '/api/library'):
    check('actual_installed_endpoint/' + endpoint, '"GET ' + endpoint + ' HTTP/1.1" 200 OK' in launcher_log)
check('dependency_check_and_graceful_shutdown_logged', 'No broken requirements found.' in launcher_log
      and 'Application shutdown complete.' in launcher_log and 'Finished server process [2285]' in launcher_log)
check('installed_health_identity', install['health']['status'] == 'ok' and install['health']['service'] == 'LinkScribe'
      and install['runtime']['python'] == '3.11.18')
install_helper = observed_source('tests/smoke_candidate_install.py').decode()
check('observed_install_verifier_keeps_provenance_and_bounds', all(fragment in install_helper for fragment in
      ('MAX_ARCHIVE_MEMBERS = 5000', 'MAX_ARCHIVE_BYTES = 100 * 1024 * 1024',
       'MAX_EXTRACTED_BYTES = 300 * 1024 * 1024', '"LinkScribe/app.py", "LinkScribe/asr_timing.py"',
       'bundle.comment != expected_commit.encode("ascii")', 'probe.bind(("127.0.0.1", 8765))',
       'subprocess.Popen(["bash", "start_linux.sh"]', 'saved != {"items": []}')))

# Recheck all original file identities after immutable SQLite and ZIP reading.
for row in manifest['files']:
    check('unchanged_after_review/' + row['path'], sha(ARTIFACT / row['path']) == row['sha256'])
check('no_sqlite_sidecars_created', not (run_dir / 'library.sqlite3-wal').exists()
      and not (run_dir / 'library.sqlite3-shm').exists())

result = {
    'schema_version': 1,
    'scope': 'Independent read/hash/AST/stdlib-data audit only; no app/model/native/provider execution, download or Git operation.',
    'head_sha': HEAD, 'checks_passed': len(checks), 'checks': checks, 'errors': [],
    'speaker': {
        'run_id': 46126494171, 'job_id': 140922130930, 'artifact_id': 15254889987,
        'artifact_zip': identity(SOURCE / 'speaker-artifact.zip'), 'plan': identity(PLAN_PATH),
        'report': identity(ARTIFACT / 'speaker-app-report.json'), 'execution': identity(ARTIFACT / 'execution.json'),
        'actual_native_runtime': init, 'full_pcm_sha256': pcm_sha, 'sample_count': sample_count,
        'duration_seconds': duration, 'native_alignment_summary': native_summaries,
        'word_timed_segments': 8, 'saved_groups': len(segments),
        'unassigned_saved_groups': sum(row['speaker'] == 'Unknown speaker' for row in segments),
        'timing_fallback_warnings': timing['warnings'], 'speaker_warnings': warnings,
        'acoustic_score': score, 'assigned_core_samples': assigned, 'unassigned_core_samples': total-assigned,
        'resources': {'samples': len(samples), 'sampled_group_peak_rss_bytes': peak,
                      'worker_os_peak_rss_bytes': report['peak_process_rss_bytes'],
                      'worker_elapsed_seconds': report['elapsed_seconds'],
                      'controller_elapsed_seconds': execution['elapsed_seconds'],
                      'owned_group_cleanup_complete': True},
        'persistence': 'Exact saved record independently reloaded with immutable read-only SQLite and compared with report, JSON, TXT, timed exports, transcript ZIP payloads and schema-v2 backup.',
    },
    'install': {
        'run_id': 46126494141, 'artifact_id': 15255569442,
        'evidence_zip': identity(SOURCE / 'install-artifact.zip'),
        'report': identity(install_dir / 'installation.json'), 'launcher_log': identity(install_dir / 'launcher.log'),
        'checks': install['checks'], 'runtime': install['runtime'], 'source_receipt': install['source'],
        'source_outer_artifact': source_metadata,
        'source_archive_locally_downloaded_or_rehashed': False,
        'scope': 'Bound hosted install receipt plus independently hash-verified evidence ZIP/log and retained GitHub metadata. Actual source ZIP safe extraction/provenance is verified by the hosted checker, not repeated locally.',
    },
    'limitations': [
        'Source commit identity is bound by retained GitHub artifact/job metadata and embedded head/plan hashes. Current source bytes match every actual plan/report source hash; no new Git command was used.',
        'Constructor cpu_threads0 is the unchanged app default. Four-CPU launch affinity and OMP/MKL4 are source-enforced and recorded; effective native threads and inference-side affinity were not independently measured.',
        '166 summed-RSS samples can miss transient peaks. The separate worker OS high-water is also checked. This excludes unrelated machine processes.',
        'Native feature matrices are not retained. Full PCM, feature identities, native tokens/windows/frames and raw monotone paths are bound without recomputing model features.',
        'The unchanged score applies only to the already-exposed constructed English reading fixture. It does not approve Greek, meetings, overlap, general ASR quality or precise word-timing accuracy.',
        'All recognized text is preserved; this does not establish that recognition itself is correct. No new audio-listening or complete ASR-reference review was performed.',
        'Translation and summary were disabled. The run observes recognizer release before speakers, not a live audio-to-text-AI transition.',
        'Source artifact outer ZIP and inner candidate ZIP are distinct. Neither source container was downloaded/rehashed in this review; their reported identities are kept separate.',
        'The install verifies fresh Linux Python3.11 startup/dependencies/endpoints, not a standalone installer, Windows/macOS installation or model inference.',
    ],
}
(OUT / 'retained-artifact-audit.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'checks_passed':len(checks),'audit_sha256':sha(OUT/'retained-artifact-audit.json'),
                  'acoustic_score_sha256':sha(OUT/'independent-acoustic-score.json'),
                  'speaker_groups':len(segments),'assigned_core_samples':assigned,'core_samples':total}))

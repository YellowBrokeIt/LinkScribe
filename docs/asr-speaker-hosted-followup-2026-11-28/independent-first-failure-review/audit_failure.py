"""Read only retained hosted artifacts and immutable local Git objects."""
from pathlib import Path
import array
import hashlib
import json
import struct
import subprocess
import sys
import wave

BASE = Path('/workspace/scratch/94360995dd61')
REPO = BASE / 'LinkScribe'
SOURCE = BASE / 'hosted-d62df26-speaker-review'
ARTIFACT = SOURCE / 'artifact'
OUT = Path(__file__).resolve().parent
HEAD = 'd62df26c870f175f7454fe0c3900d97891c8bff5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def committed(path):
    return subprocess.check_output(['git', 'show', HEAD + ':' + path], cwd=REPO)


checks = []


def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})
    if not value:
        raise AssertionError(name)


plan_bytes = committed('docs/asr-speaker-timing-integration-2026-11-28/hosted-plan.json')
helper_bytes = committed('tests/qa_speaker_integration.py')
plan = json.loads(plan_bytes)
prep = read(ARTIFACT / 'preparation.json')
metadata = read(SOURCE / 'artifacts-metadata.json')['artifacts'][0]
manifest = read(SOURCE / 'artifact-manifest.json')
check('exact_run_and_head', metadata['workflow_run']['id'] == 46121980993 and metadata['workflow_run']['head_sha'] == HEAD)
check('published_zip_digest_and_size', metadata['digest'] == 'sha256:' + digest(SOURCE / 'artifact.zip') and metadata['size_in_bytes'] == (SOURCE / 'artifact.zip').stat().st_size)
check('exact_committed_plan', hashlib.sha256(plan_bytes).hexdigest() == 'ab8540dfd58584f5de43ae5019d7c4812a1a2b4762759fc390702e5ecb321faa')
check('exact_committed_helper', hashlib.sha256(helper_bytes).hexdigest() == '1d86a5dd2aedfda9a34eb40c3b5dcb23edbc39e4f53397169b5f5136ddb21aa2')
for item in manifest['files']:
    path = ARTIFACT / item['path']
    check('artifact/' + item['path'], path.stat().st_size == item['bytes'] and digest(path) == item['sha256'])
check('complete_artifact_inventory', sorted(row['path'] for row in manifest['files']) == sorted(str(path.relative_to(ARTIFACT)) for path in ARTIFACT.rglob('*') if path.is_file()))
check('runtime_all_16_pins', len(prep['runtime_packages']) == 16 and prep['runtime_packages'] == plan['runtime_packages'])
check('original_source_receipts', len(prep['sources']) == 4 and all(got['id'] == expected['id'] and got['sha256'] == expected['sha256'] for got, expected in zip(prep['sources'], plan['fixture']['sources'])))
wave_path = ARTIFACT / 'inputs' / plan['fixture']['filename']
with wave.open(str(wave_path), 'rb') as stream:
    raw = stream.readframes(stream.getnframes())
    wave_config = {'channels': stream.getnchannels(), 'sample_width': stream.getsampwidth(), 'sample_rate': stream.getframerate(), 'sample_count': stream.getnframes()}
check('complete_original_wav', digest(wave_path) == plan['fixture']['sha256'] and wave_config == {'channels': 1, 'sample_width': 2, 'sample_rate': 16000, 'sample_count': 554160})
values = array.array('h', raw)
if sys.byteorder != 'little':
    values.byteswap()
pcm = b''.join(struct.pack('<f', value / 32768.0) for value in values)
pcm_sha = hashlib.sha256(pcm).hexdigest()
check('complete_pcm_matches_report', pcm_sha == prep['fixture']['decoded_pcm_sha256'])
check('no_worker_artifacts', not any(path.name in {'execution.json', 'report.json', 'worker-attempt.json', 'worker.log', 'recognizer-report.json'} for path in ARTIFACT.rglob('*')))
check('reported_pre_model_failure', prep['complete'] is False and prep['model_constructed'] is False and prep['failure'] == {'type': 'HTTPError', 'message': 'HTTP Error 404: Not Found'})
expected_done = {'recognizer': list(plan['models']['recognizer']['files']), 'speaker': ['classifier.ckpt', 'hyperparams.yaml', 'mean_var_norm_emb.ckpt']}
for family, names in expected_done.items():
    check(family + '_completed_names', list(prep['models'][family]) == names)
    for name in names:
        check(family + '/' + name + '_reported_hash', prep['models'][family][name]['sha256'] == plan['models'][family]['files'][name]['sha256'])
step = next(item for item in read(SOURCE / 'final-jobs.json')['jobs'][0]['steps'] if item['name'] == 'Run the one bounded offline application pipeline')
check('inference_step_skipped', step['conclusion'] == 'skipped')
pretrainer = REPO / 'docs/asr-speaker-timing-integration-2026-11-28/independent-review/speechbrain-v1.1.2-parameter_transfer.py'
check('retained_pinned_pretrainer', digest(pretrainer) == '9ef59c7141e6aad15d11dd184957054e758baf3537bc71ffe3079753715d4f65')
report = {
    'scope': 'Read-only independent retained-artifact/source audit; no metadata fetch, provider/model/native execution, or code mutation.',
    'head_sha': HEAD, 'run_id': 46121980993, 'job_id': 140908265951, 'artifact_id': metadata['id'],
    'artifact_zip': identity(SOURCE / 'artifact.zip'), 'checks': checks, 'errors': [],
    'full_wav': wave_config, 'full_pcm_sha256': pcm_sha,
    'identities': {name: identity(SOURCE / name) for name in ['artifact/preparation.json', 'artifact/prepare-failure.json', 'artifact/preflight.json', 'final-run.json', 'final-jobs.json', 'artifacts-metadata.json', 'artifact-manifest.json']},
    'source_contract': identity(pretrainer),
}
destination = OUT / 'failure-artifact-audit.json'
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'path': str(destination), 'sha256': digest(destination), 'checks': len(checks), 'errors': [], 'full_pcm_sha256': pcm_sha}))

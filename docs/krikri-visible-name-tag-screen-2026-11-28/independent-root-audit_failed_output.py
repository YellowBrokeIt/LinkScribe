"""Independent failed-case audit; use the declared existing venv, no models."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent/'LinkScribe'
STAGE = ROOT/'docs/krikri-visible-name-tag-screen-2026-11-28'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())

freeze = read(STAGE/'inference-freeze.json')
assert sha(STAGE/'inference-freeze.json') == 'd08480222ac83a11cc6aa1cb181a67bb000ff3ef2c5967755327658765c1d069'
for path, expected in freeze['files_sha256'].items(): assert sha(ROOT/path) == expected, path
execution, resources = read(STAGE/'execution.json'), read(STAGE/'infer-resources.json')
assert execution['generation_calls'] == len(execution['cases']) == 1 and execution['complete'] is False
case_info = execution['cases'][0]
for path_key, hash_key in [('report','sha256'),('preflight_report','preflight_sha256'),('protection_report','protection_report_sha256')]:
    assert sha(STAGE/case_info[path_key]) == case_info[hash_key]
case = read(STAGE/case_info['report'])['cases'][0]
protection = read(STAGE/case_info['protection_report'])
requests, setup = read(STAGE/'expected-requests.json'), read(STAGE/'prepare.json')
calls = [r for r in case['requests'] if r['kind']=='inference']
controls = [r for r in case['requests'] if r['kind']=='control']
assert len(calls) == len(controls) == 1
assert calls[0]['request'] == requests[0]['request'] and calls[0]['timeout_seconds'] == 240
preflight = read(STAGE/case_info['preflight_report'])
for key in ('rendered_prompt','tokens','prompt_tokens','request'): assert preflight[key] == setup['prompts'][0][key]
raw = json.loads(calls[0]['response_json'])
strings = json.loads(raw['message']['content'])['translations']
assert raw['done'] is True and raw['done_reason'] == 'stop' and raw['prompt_eval_count'] == 231
assert raw['eval_count'] == 65 and not raw['message'].get('thinking')
assert protection['model_response_json'] == calls[0]['response_json']
assert protection['raw_masked_translation_strings'] == strings
assert case['translation'] is None and protection['complete'] is False
assert protection['exact_source_only_restoration'] is False and protection['post_restoration_guard_accepted'] is False
actual_name = re.search(r'<x0>(.*?)</x0>', strings[0]).group(1)
assert actual_name == 'Mαρία' and ord(actual_name[0]) == 0x4d
spec = importlib.util.spec_from_file_location('frozen_exact_pair_guard', STAGE/'protection.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.restore_segments(protection['bundle'], protection['masked_app_result'])
except ValueError as error:
    reproduced_error = str(error)
else:
    raise AssertionError('Changed inner name was accepted')
assert reproduced_error == protection['error']['message']
unload = json.loads(controls[0]['response_json'])
assert unload['done'] is True and unload['done_reason'] == 'unload'
assert case_info['checks']['resident_models_empty'] is True and execution['owned_daemon_stopped'] is True
assert resources['worker_exit_code'] == 1 and resources['passed'] is False and resources['complete'] is False
assert resources['measurement_complete'] is True and not resources['measurement_errors']
assert resources['owned_processes_stopped'] is True
assert resources['phase_report_sha256'] == sha(STAGE/'execution.json')
assert resources['samples_sha256'] == sha(STAGE/'infer-samples.jsonl')
samples = [json.loads(line) for line in (STAGE/'infer-samples.jsonl').read_text().splitlines()]
assert len(samples) == resources['sample_count'] == 303
for sample in samples:
    assert len({p['pid'] for p in sample['processes']}) == len(sample['processes'])
    assert sum(p['rss_bytes'] for p in sample['processes']) == sample['rss_bytes']
    assert sum(p['pss_bytes'] for p in sample['processes']) == sample['pss_bytes']
assert max(samples,key=lambda s:s['rss_bytes']) == resources['peak_rss_sample']
assert max(samples,key=lambda s:s['pss_bytes']) == resources['peak_pss_sample']
assert all(a['elapsed_seconds'] <= b['elapsed_seconds'] for a,b in zip(samples,samples[1:]))
assert resources['peak_rss_sample']['rss_bytes'] < resources['limits']['rss_bytes']
assert resources['elapsed_seconds'] < resources['limits']['total_seconds']
record = {
    'schema_version':1, 'reviewed_at':datetime.now(timezone.utc).isoformat(),
    'decision':'Reject at the first operational failure; no accepted/restored translation and five cases unrun.',
    'independent_of_candidate_author':True, 'auditor_sha256':sha(__file__),
    'source_criteria_before_output_sha256':sha(HERE/'source-and-criteria-before-output.json'),
    'inference_freeze_sha256':sha(STAGE/'inference-freeze.json'),
    'frozen_bindings_verified':len(freeze['files_sha256']),
    'execution_sha256':sha(STAGE/'execution.json'), 'case_report_sha256':sha(STAGE/case_info['report']),
    'protection_report_sha256':sha(STAGE/case_info['protection_report']),
    'resource_report_sha256':sha(STAGE/'infer-resources.json'),
    'sample_stream_sha256':sha(STAGE/'infer-samples.jsonl'),
    'actual_generations':1, 'unrun_cases':5, 'accepted_translations':0,
    'expected_exact_span':'<x0>Maria</x0>', 'actual_span':'<x0>'+actual_name+'</x0>',
    'actual_name_codepoints':[f'U+{ord(c):04X}' for c in actual_name],
    'guard_rejection_reproduced':reproduced_error, 'changed_inner_name_repaired':False,
    'raw_translation_strings':strings,
    'raw_meaning_observations':{
        'text_and_recording':'Preserved: transcript saved as a text file; original recording not saved.',
        'process_and_chronology':'Preserved: transcription took 12 minutes; Greek translation has not started.',
        'name':'Mixed-script Mαρία differs from source Maria. The exact-copy protocol fails; surviving ordinary facts do not make this rejected response an accepted translation.',
        'other_five_cases':'Unrun; no quality judgment.'},
    'runtime':{'normal_stop':True,'prompt_tokens':231,'output_tokens':65,'reasoning_empty':True,
               'raw_retained_before_guard':True,'elapsed_seconds':resources['elapsed_seconds'],
               'samples':len(samples),'peak_rss_bytes':resources['peak_rss_sample']['rss_bytes'],
               'peak_pss_bytes':resources['peak_pss_sample']['pss_bytes'],'worker_exit_code':1,
               'unload_and_owned_cleanup_passed':True,'measurement_complete':True,'resource_limit_triggered':False},
    'unchanged_prior_failures_and_criteria':True, 'production_or_fresh_validation_approved':False,
    'reviewer_native_or_model_calls':0,
    'initial_audit_interpreter_issue_sha256':sha(HERE/'initial-audit-environment-error.json')}
output = HERE/'independent-failed-output-review.json'
with output.open('x',encoding='utf-8') as stream:
    json.dump(record,stream,ensure_ascii=False,indent=2)
    stream.write('\n')
print(json.dumps({'path':str(output),'sha256':sha(output),'bindings':len(freeze['files_sha256']),
                  'samples':len(samples),'decision':record['decision']}))

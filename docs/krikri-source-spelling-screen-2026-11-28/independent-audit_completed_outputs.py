"""Root's offline audit of the two retained native outputs; no model execution."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

authorization = read(HERE / 'infer-authorization.json')
assert sha(HERE / 'infer-authorization.json') == 'a3824c316e396f429be6c093dcd8cbda0e090543deb83fade35f7d21ca190ade'
for path, digest in authorization['files_sha256'].items():
    assert sha(ROOT / path) == digest, path
assert len(authorization['files_sha256']) == 133
execution = read(HERE / 'execution.json')
resources = read(HERE / 'infer-resources.json')
sources = read(HERE / 'development-cases.json')['cases']
expected = read(HERE / 'expected-requests.json')
setup = read(HERE / 'prepare.json')
assert execution['generation_calls'] == len(execution['cases']) == 2
assert execution['complete'] is False and execution['frozen_inputs_unchanged'] is True
assert execution['authorization_sha256'] == sha(HERE / 'infer-authorization.json')
assert execution['inference_freeze_sha256'] == sha(HERE / 'inference-freeze.json')
spec = importlib.util.spec_from_file_location('root_frozen_exact_marker_guard', HERE / 'protection.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
observations = []
for index, item in enumerate(execution['cases']):
    assert item['id'] == sources[index]['id'] == expected[index]['id']
    for path_key, hash_key in [('report', 'sha256'), ('preflight_report', 'preflight_sha256'),
                              ('protection_report', 'protection_report_sha256')]:
        assert sha(HERE / item[path_key]) == item[hash_key]
    case = read(HERE / item['report'])['cases'][0]
    protection = read(HERE / item['protection_report'])
    preflight = read(HERE / item['preflight_report'])
    calls = [r for r in case['requests'] if r['kind'] == 'inference']
    controls = [r for r in case['requests'] if r['kind'] == 'control']
    assert len(calls) == len(controls) == case['request_count'] == case['control_request_count'] == 1
    assert calls[0]['request'] == expected[index]['request'] and calls[0]['timeout_seconds'] == 240
    for key in ('rendered_prompt', 'tokens', 'prompt_tokens', 'request'):
        assert preflight[key] == setup['prompts'][index][key], (item['id'], key)
    assert preflight['rendered_sha256'] == hashlib.sha256(preflight['rendered_prompt'].encode()).hexdigest()
    assert len(preflight['tokens']) == preflight['prompt_tokens']
    assert preflight['tokens'][0] == 128000 and preflight['tokens'].count(128000) == 1
    assert preflight['prompt_tokens'] + 2048 + 1 <= 4096
    request = calls[0]['request']
    assert request['options'] == {'temperature': 0, 'num_ctx': 4096, 'num_predict': 2048, 'num_thread': 4}
    assert request['think'] is False
    assert protection['source_segments'] == sources[index]['segments']
    assert protection['bundle']['source_segments'] == sources[index]['segments']
    mapping = [{'tag': marker['marker'], 'spelling': marker['source_text']}
               for marker in protection['bundle']['markers']]
    assert mapping == protection['source_context_map']
    assert len(protection['source_context_projections']) == 1
    projection = protection['source_context_projections'][0]
    assert projection['source_spellings'] == mapping
    assert projection['projected_app_payload']['messages'] == request['messages']
    assert projection['projected_app_payload']['response_schema'] == request['format']
    assert projection['combined_source_json_bytes'] <= 1000
    assert projection['inserted_before_native_request_builder_and_observer'] is True
    assert protection['native_payload_builder_restored'] is True
    raw = json.loads(calls[0]['response_json'])
    assert raw['done'] is True and raw['done_reason'] == 'stop'
    assert raw['prompt_eval_count'] == preflight['prompt_tokens'] == [261, 350][index]
    assert raw['eval_count'] == [59, 47][index] and not raw['message'].get('thinking')
    assert protection['model_response_json'] == calls[0]['response_json']
    strings = guard.strict_response_strings(raw['message']['content'], len(sources[index]['segments']))
    assert protection['raw_masked_translation_strings'] == strings
    assert [s['text'] for s in protection['masked_app_result']] == strings
    if index == 0:
        restored, report = guard.restore_segments(protection['bundle'], protection['masked_app_result'])
        assert restored == case['translation']
        assert protection['complete'] is True and protection['exact_source_only_restoration'] is True
        assert protection['post_restoration_guard_accepted'] is True
        assert item['automatic_status'] == 'pass'
        rejection = None
    else:
        try:
            guard.restore_segments(protection['bundle'], protection['masked_app_result'])
        except ValueError as error:
            rejection = str(error)
        else:
            raise AssertionError('Case 2 unexpectedly passed the exact marker guard')
        assert rejection == protection['error']['message']
        assert case['translation'] is None and protection['complete'] is False
        assert protection['exact_source_only_restoration'] is False
        assert protection['post_restoration_guard_accepted'] is False
        assert item['automatic_status'] == 'error'
        assert all(marker['marker'] not in ''.join(strings) for marker in protection['bundle']['markers'])
    unload = json.loads(controls[0]['response_json'])
    assert unload['done'] is True and unload['done_reason'] == 'unload'
    assert item['checks']['resident_models_empty'] is True
    observations.append({'id': item['id'], 'source_segments': sources[index]['segments'],
                         'raw_translation_strings': strings, 'accepted_translation': case['translation'],
                         'guard_rejection_reproduced': rejection,
                         'prompt_tokens': raw['prompt_eval_count'], 'output_tokens': raw['eval_count'],
                         'report_sha256': item['sha256'], 'protection_sha256': item['protection_report_sha256']})

unrun = [source['id'] for source in sources[2:]]
for case_id in unrun:
    for suffix in ('.json', '-protection.json', '-preflight.json'):
        assert not (HERE / (case_id + suffix)).exists()
assert execution['owned_daemon_stopped'] is True
assert resources['worker_exit_code'] == 1 and resources['passed'] is False and resources['complete'] is False
assert resources['measurement_complete'] is True and not resources['measurement_errors']
assert resources['owned_processes_stopped'] is True and not resources.get('stop_reason')
assert resources['phase_report_sha256'] == sha(HERE / 'execution.json')
assert resources['samples_sha256'] == sha(HERE / 'infer-samples.jsonl')
samples = [json.loads(line) for line in (HERE / 'infer-samples.jsonl').read_text().splitlines()]
assert len(samples) == resources['sample_count'] == 429
for sample in samples:
    assert len({process['pid'] for process in sample['processes']}) == len(sample['processes'])
    for key in ('rss_bytes', 'pss_bytes'):
        assert sum(process[key] for process in sample['processes']) == sample[key]
assert all(left['elapsed_seconds'] <= right['elapsed_seconds'] for left, right in zip(samples, samples[1:]))
assert max(samples, key=lambda sample: sample['rss_bytes']) == resources['peak_rss_sample']
assert max(samples, key=lambda sample: sample['pss_bytes']) == resources['peak_pss_sample']
assert resources['peak_rss_sample']['rss_bytes'] < resources['limits']['rss_bytes']
assert resources['elapsed_seconds'] < resources['limits']['total_seconds']
assert resources['disk_reserve_retained'] is True and resources['frozen_inputs_unchanged'] is True
record = {
    'schema_version': 1, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'reviewer': '/root', 'independent_of_candidate_author': True,
    'auditor_sha256': sha(__file__),
    'source_and_criteria_before_output_sha256': sha(HERE / 'independent-root-source-criteria-before-output.json'),
    'inference_authorization_sha256': sha(HERE / 'infer-authorization.json'),
    'frozen_bindings_verified': len(authorization['files_sha256']),
    'execution_sha256': sha(HERE / 'execution.json'),
    'resource_report_sha256': sha(HERE / 'infer-resources.json'),
    'sample_stream_sha256': sha(HERE / 'infer-samples.jsonl'),
    'case_observations': observations, 'cases_unrun': unrun,
    'actual_generations': 2, 'accepted_translations': 1,
    'raw_response_and_complete_request_preserved': True,
    'all_429_sample_sums_order_and_peaks_verified': True,
    'runtime': {'elapsed_seconds': resources['elapsed_seconds'], 'sample_count': len(samples),
                'peak_rss_bytes': resources['peak_rss_sample']['rss_bytes'],
                'peak_pss_bytes': resources['peak_pss_sample']['pss_bytes'],
                'worker_exit_code': 1, 'supervisor_passed': False,
                'measurement_complete': True, 'resource_limit_triggered': False,
                'both_unloads_resident_empty_and_owned_cleanup_passed': True},
    'reviewer_native_model_tokenizer_calls': 0,
    'reviewer_repair_or_retry_performed': False,
    'mechanical_decision': 'Reject at case 2; the completed first case is reviewed separately for meaning. Four cases remain unrun.',
    'semantic_approval_claimed_by_this_mechanical_audit': False,
}
output = HERE / 'independent-completed-output-audit.json'
with output.open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'path': str(output), 'sha256': sha(output), 'bindings': 133, 'samples': 429,
                  'actual_generations': 2, 'accepted_translations': 1, 'unrun': 4}))

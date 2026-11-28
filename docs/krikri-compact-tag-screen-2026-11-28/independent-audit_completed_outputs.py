"""Audit retained JSON and bytes only. Never import or run application/model code."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE = Path(__file__).resolve().parent
STAGE = ROOT / 'docs/krikri-compact-tag-screen-2026-11-28'
ORIGINAL = HERE.parent / 'krikri-source-name-protection-independent-review-2026-11-28/source-and-criteria-before-output.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def check(test, label):
    if not test:
        raise AssertionError(label)

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        check(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result

def loads(text):
    return json.loads(text, object_pairs_hook=unique_object)

def read(path):
    return loads(path.read_text(encoding='utf-8'))

def no_reserved_namespace(text):
    folded = unicodedata.normalize('NFKC', text).casefold()
    folded = ''.join(c for c in folded if unicodedata.category(c) != 'Cf')
    return re.search(r'<\s*/?\s*x', folded) is None

check(sha(ORIGINAL) == '48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce', 'unchanged original review sources')
check(sha(STAGE/'development-cases.json') == sha(ORIGINAL), 'identical experiment corpus')
freeze = read(STAGE/'inference-freeze.json')
check(sha(STAGE/'inference-freeze.json') == 'a812e7cbd919b2883b539690041f101d7af99465b625d3bb5e202863f2c8e9cc', 'exact inference freeze')
for rel, expected in freeze['files_sha256'].items():
    check(sha(ROOT/rel) == expected, 'immutable source/setup binding: ' + rel)
check(len(freeze['files_sha256']) == 79, '79 reviewed inference bindings')
sources = read(ORIGINAL)['cases']
requests = read(STAGE/'expected-requests.json')
prepared = read(STAGE/'prepare.json')['prompts']
source_protection = read(STAGE/'protection-inputs.json')['cases']
execution = read(STAGE/'execution.json')
check(sha(STAGE/'execution.json') == '247a669873a2d9f261886a60febfea7373f0f8803f1770af0ea9b63cc0885ec3', 'completed execution identity')
check(execution['generation_calls'] == len(execution['cases']) == len(sources) == 6 and execution['complete'], 'six completed cases once')
check(execution['inference_freeze_sha256'] == sha(STAGE/'inference-freeze.json'), 'execution frozen inputs')
check(execution['owned_daemon_stopped'] and execution['frozen_inputs_unchanged'] and not execution['unused_validation_opened'], 'recorded cleanup and scope')
pattern = re.compile(r'<x(?:0|[1-9][0-9]{0,3})/>')
rows = []
for i, entry in enumerate(execution['cases']):
    source = sources[i]
    case_id = source['id']
    check(entry['id'] == requests[i]['id'] == source_protection[i]['id'] == case_id, 'original fixed case order')
    for pathkey, hashkey in [('report', 'sha256'), ('preflight_report', 'preflight_sha256'), ('protection_report', 'protection_report_sha256')]:
        check(sha(STAGE/entry[pathkey]) == entry[hashkey], case_id + ': ' + pathkey + ' hash')
    report = read(STAGE/entry['report'])
    case = report['cases'][0]
    protected = read(STAGE/entry['protection_report'])
    preflight = read(STAGE/entry['preflight_report'])
    check(report['complete'] and report['completed_cases'] == report['requested_cases'] == len(report['cases']) == 1, 'completed one-case report')
    for key, value in source.items():
        check(case[key] == value, case_id + ': original source/criterion field ' + key)
    check(protected['source_segments'] == source['segments'], 'original complete source retained')
    check(protected['bundle'] == source_protection[i]['bundle'], 'frozen source-derived map unchanged')
    for key in ['request', 'rendered_prompt', 'tokens', 'prompt_tokens', 'layout', 'tokenize_add_special']:
        check(preflight[key] == prepared[i][key], 'fresh complete native preflight ' + key)
    check(text_sha(preflight['rendered_prompt']) == preflight['rendered_sha256'], 'rendered prompt identity')
    check(preflight['tokens'].count(128000) == 1 and len(preflight['tokens']) == preflight['prompt_tokens'], 'one BOS and full token count')
    check(preflight['context_tokens'] == 4096 and preflight['maximum_output_tokens'] == 2048, 'unchanged native capacity')
    check(len(preflight['tokens']) + 2048 + 1 <= 4096, 'full output plus terminal reserve')
    calls = [r for r in case['requests'] if r['kind'] == 'inference']
    controls = [r for r in case['requests'] if r['kind'] == 'control']
    check(len(case['requests']) == 2 and len(calls) == len(controls) == 1, 'one generation and one unload only')
    check(calls[0]['request'] == requests[i]['request'] == preflight['request'] and calls[0]['timeout_seconds'] == 240, 'exact actual request and timeout')
    check(calls[0]['elapsed_seconds'] < 240 and entry['elapsed_seconds'] < 600, 'request and case caps')
    raw = loads(calls[0]['response_json'])
    final = raw['message']['content']
    check(raw == loads(protected['model_response_json']), 'independent raw-observer copies equal')
    check(raw['model'] == 'linkscribe-krikri-8b-q4km:20261128', 'expected native model')
    check(raw['done'] is True and raw['done_reason'] == 'stop' and not raw['message'].get('thinking'), 'normal final stop/no reasoning')
    check(raw['prompt_eval_count'] == preflight['prompt_tokens'] and 0 < raw['eval_count'] < 2048, 'actual native prompt and complete output')
    check(loads(controls[0]['response_json'])['done_reason'] == 'unload' and controls[0]['request']['keep_alive'] == 0, 'acknowledged unload')
    check(all(entry['checks'].values()) and all(case['structural_checks'].values()), 'recorded execution/metadata checks')
    parsed = loads(final)
    check(set(parsed) == {'translations'} and len(parsed['translations']) == len(source['segments']), 'strict final schema and all entries')
    strings = parsed['translations']
    check(all(isinstance(t, str) and t.strip() for t in strings), 'nonempty translated entries')
    check(strings == protected['raw_masked_translation_strings'] and protected['strict_raw_schema_accepted'], 'exact raw string evidence')
    check([s['text'] for s in protected['masked_app_result']] == [s.strip() for s in strings], 'only baseline whitespace strip before restoration')
    markers = protected['bundle']['markers']
    check(len({m['marker'] for m in markers}) == len(markers), 'unique request-local occurrence IDs')
    expected = copy.deepcopy(source['segments'])
    for j, original in enumerate(source['segments']):
        scoped = [m for m in markers if m['segment_index'] == j]
        masked = original['text']
        for m in reversed(scoped):
            check(original['text'][m['start']:m['end']] == m['source_text'], 'exact original name slice')
            masked = masked[:m['start']] + m['marker'] + masked[m['end']:]
        check(masked == protected['bundle']['masked_segments'][j]['text'], 'ordinary source and exact name masking')
        check(sorted(pattern.findall(strings[j])) == sorted(m['marker'] for m in scoped), 'exact same-segment once-only marker multiset')
        without = strings[j]
        restored = strings[j]
        for m in scoped:
            check(sum(t.count(m['marker']) for t in strings) == 1, 'one exact occurrence across full request')
            without = without.replace(m['marker'], '')
            restored = restored.replace(m['marker'], m['source_text'])
        check(no_reserved_namespace(without), 'no malformed/residual opening or closing marker prefix')
        expected[j]['text'] = restored.strip()
    check(expected == case['translation'] == protected['restored_before_guard'] == protected['restored_app_result'], 'exact source-only restoration and untouched accepted prose/metadata')
    check(protected['complete'] and protected['exact_source_only_restoration'] and protected['post_restoration_guard_accepted'], 'complete accepted restoration stage')
    rows.append({
        'id': case_id,
        'report_sha256': entry['sha256'],
        'preflight_sha256': entry['preflight_sha256'],
        'protection_sha256': entry['protection_report_sha256'],
        'raw_response_json_utf8_sha256': text_sha(calls[0]['response_json']),
        'raw_final_content_utf8_sha256': text_sha(final),
        'raw_translation_string_utf8_sha256': [text_sha(s) for s in strings],
        'restored_translation_string_utf8_sha256': [text_sha(s['text']) for s in case['translation']],
        'actual_prompt_tokens': raw['prompt_eval_count'],
        'output_tokens': raw['eval_count'],
        'exact_restored_name_mentions': len(markers),
        'same_segment_once_only': True,
        'one_normal_generation_and_acknowledged_unload': True,
        'post_restoration_guard_accepted': True,
    })
check(sum(r['exact_restored_name_mentions'] for r in rows) == 13, 'all 13 protected source names restored exactly')

resources = read(STAGE/'infer-resources.json')
check(sha(STAGE/'infer-resources.json') == '2a8c07e507c116a1fad5eb55b8009bae1c5a87b858104ab31603aa211cdb067f', 'final external resource report')
samples_path = STAGE/resources['samples_file']
check(sha(samples_path) == resources['samples_sha256'], 'retained complete resource samples')
samples = [loads(s) for s in samples_path.read_text(encoding='utf-8').splitlines()]
check(len(samples) == resources['sample_count'] == 1087, '1087 complete samples')
for s in samples:
    check(len({p['pid'] for p in s['processes']}) == len(s['processes']), 'deduplicated sampled processes')
    for field in ['rss_bytes', 'pss_bytes']:
        check(sum(p[field] for p in s['processes']) == s[field], 'exact process ' + field + ' sum')
check(all(a['elapsed_seconds'] <= b['elapsed_seconds'] for a, b in zip(samples, samples[1:])), 'ordered sample times')
for field in ['rss', 'pss']:
    peak = max(samples, key=lambda x: x[field + '_bytes'])
    check(peak == resources['peak_' + field + '_sample'], 'peak ' + field + ' equals full series')
    check(round(peak[field + '_bytes']/1048576, 1) == resources['peak_' + field + '_mib'], 'reported rounded peak ' + field)
check(resources['measurement_complete'] and not resources['measurement_errors'] and resources['owned_processes_stopped'], 'complete resource measurement and recorded cleanup')
check(not resources.get('stop_reason') and resources['worker_exit_code'] == 0 and resources['passed'] and resources['complete'], 'successful operational exit')
check(resources['phase_report_sha256'] == sha(STAGE/'execution.json'), 'resource report binds completed worker report')
check(resources['limits'] == {'rss_bytes': 6442450944, 'total_seconds': 1800, 'initialization_seconds': 180, 'case_seconds': 600}, 'unchanged resource caps')
check(resources['cpu_affinity'] == [0, 1, 2, 3], 'four allowed CPUs')
check(resources['peak_rss_sample']['rss_bytes'] < 6442450944 and resources['elapsed_seconds'] < 1800 and resources['disk_reserve_retained'], 'resource and storage bounds')
events = resources['events']
check([e['id'] for e in events if e['event'] == 'case_start'] == [s['id'] for s in sources], 'all six starts once in original order')
check([e['id'] for e in events if e['event'] == 'case_complete'] == [s['id'] for s in sources], 'all six completions once in original order')
check(events[0]['observed_elapsed_seconds'] < 180, 'first native-ready call within initialization cap')
out = {
    'schema_version': 1,
    'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'audit_complete': True,
    'audit_passed': True,
    'meaning_approval_not_implied': True,
    'inference_freeze_sha256': sha(STAGE/'inference-freeze.json'),
    'frozen_files_verified': len(freeze['files_sha256']),
    'original_corpus_sha256': sha(ORIGINAL),
    'execution_sha256': sha(STAGE/'execution.json'),
    'resource_report_sha256': sha(STAGE/'infer-resources.json'),
    'sample_file_sha256': sha(samples_path),
    'native_cases_observed': rows,
    'not_run': [],
    'resources': {
        'elapsed_seconds': resources['elapsed_seconds'],
        'sample_count': len(samples),
        'peak_rss_bytes': resources['peak_rss_sample']['rss_bytes'],
        'peak_pss_bytes': resources['peak_pss_sample']['pss_bytes'],
        'peak_rss_mib': resources['peak_rss_mib'],
        'peak_pss_mib': resources['peak_pss_mib'],
        'rss_margin_mib': round((6442450944 - resources['peak_rss_sample']['rss_bytes'])/1048576, 3),
        'worker_exit_code': 0,
        'recorded_all_owned_processes_stopped': True,
        'resource_limit_hit': False,
        'whole_app_resource_approval': False,
        'measurement_limit': resources['sampling_limit'],
    },
    'scope_limit': 'Reads retained bytes, native outputs and measurement series only; does not independently rerun models or reconstruct current process state.',
    'reviewer_model_or_translation_calls': 0,
    'audit_script_sha256': sha(Path(__file__)),
}
target = HERE/'completed-output-protocol-audit.json'
with target.open('x', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'audit_passed': True, 'path': str(target), 'sha256': sha(target), 'cases': len(rows), 'exact_source_name_mentions': 13, 'sample_count': len(samples)}))

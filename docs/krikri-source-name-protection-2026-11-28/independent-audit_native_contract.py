"""Read-only independent integrity audit. No model imports or execution."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE = Path(__file__).resolve().parent
STAGE = ROOT / 'docs/krikri-source-name-protection-2026-11-28'
BASE = ROOT / 'docs/krikri-screen-2026-11-28'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def check(value, label):
    if not value:
        raise AssertionError(label)

plan = read(STAGE / 'plan.json')
check(sha(STAGE / 'plan.json') == 'd8b4c2e29998cd650be1f2d5bf232d47c6a8b478f831102f71bed0e2b3581bf4', 'plan')
check(len(plan['source_sha256']) == 59, '59 frozen files')
for rel, expected in plan['source_sha256'].items():
    check(sha(ROOT / rel) == expected, 'frozen source ' + rel)
freeze = read(STAGE / 'native-setup-freeze.json')
check(sha(STAGE / 'native-setup-freeze.json') == 'f8b5a6f5094598ca733ea62d5ebc4a61019896d647b6a45d7cb5721582e68ed9', 'setup freeze')
for rel, expected in freeze['files_sha256'].items():
    check(sha(ROOT / rel) == expected, 'native setup ' + rel)

# The literal adapter delta is confined to the new generic instruction.
before = (BASE / 'enhancements-context4096.py').read_text()
after = (STAGE / 'enhancements-context4096.py').read_text()
instruction = (STAGE / 'marker-instruction.txt').read_text().rstrip('\n')
check(instruction.startswith(' Tokens beginning with __LSNP_'), 'generic instruction')
needle = 'Do not omit or add entries.'
check(before.count(needle) == 1 and before.replace(needle, needle + instruction) == after, 'only adapter delta')

original_path = HERE / 'source-and-criteria-before-output.json'
check(sha(original_path) == '48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce', 'criteria corpus')
originals = read(original_path)['cases']
check(read(STAGE / 'development-cases.json') == read(original_path), 'exact original six')
protected = read(STAGE / 'protected-source-cases.json')['cases']
maps = read(STAGE / 'protection-inputs.json')['cases']
requests = read(STAGE / 'expected-requests.json')
baseline_requests = read(BASE / 'expected-requests.json')
annotations_path = HERE.parent / 'name-span-independent-review-2026-11-28/source-person-annotations-before-output.json'
check(sha(annotations_path) == '9a26e6f9eec232ae65f539a7d049c44d8a58cfd966d07c02005d5b933cacdae6', 'unchanged detector annotation')
annotations = read(annotations_path)['cases']
prepared = read(STAGE / 'prepare.json')
baseline_setup = read(BASE / 'prepare.json')
check(prepared['complete'] and prepared['generation_calls'] == prepared['native_create_calls'] == prepared['model_downloads'] == 0, 'zero generation')
check(prepared['cache'] == baseline_setup['cache'] and prepared['header'] == baseline_setup['header'], 'native package/header unchanged')
check(prepared['show']['template'] == baseline_setup['show']['template'] and not prepared['show'].get('system'), 'native template/no persona')
check(prepared['current_parameter_mapping'] == plan['native_setup']['import_parameters'] == prepared['baseline_parameter_mapping'], 'native parameter mapping')
check(prepared['owned_daemon_stopped'] and prepared['unload_response']['done_reason'] == 'unload' and prepared['resident_after_unload'] == {'models': []}, 'native unload and cleanup')
check(len(originals) == len(protected) == len(maps) == len(requests) == len(prepared['prompts']) == len(annotations) == 6, 'exact six cases')
rows = []
for source, masked_case, mapped, request, old_request, prompt, annotation in zip(originals, protected, maps, requests, baseline_requests, prepared['prompts'], annotations):
    case_id = source['id']
    check(all(v['id'] == case_id for v in [masked_case, mapped, request, old_request, prompt, annotation]), 'case identity/order')
    bundle = mapped['bundle']
    check(bundle['source_segments'] == source['segments'], 'complete source')
    check(bundle['masked_segments'] == masked_case['segments'], 'masked source')
    check(digest(source['segments']) == bundle['source_segments_sha256'], 'source metadata digest')
    joined = '\n'.join(s['text'] for s in source['segments'])
    check(hashlib.sha256(joined.encode()).hexdigest() == bundle['source_text_sha256'], 'joined source digest')
    check(joined == annotation['joined_source'], 'annotation source')
    expected_mentions = [{'segment_index': m['segment_index'], 'start': m['segment_start'], 'end': m['segment_end'], 'source_text': m['text'], 'global_start': m['joined_start'], 'global_end': m['joined_end']} for m in annotation['expected_exact_mentions']]
    actual_mentions = [{k: m[k] for k in expected_mentions[0]} for m in bundle['markers']] if expected_mentions else []
    check(actual_mentions == expected_mentions and len(bundle['markers']) == len(expected_mentions), 'exact already-reviewed person boundaries')
    normalized = read(ROOT / 'docs/name-boundary-normalizer-2026-11-28' / (case_id + '.json'))
    check(bundle['normalizer_result'] == normalized['result'], 'actual prior normalizer replay unchanged')
    check(sha(ROOT / 'docs/name-boundary-normalizer-2026-11-28' / (case_id + '.json')) == mapped['normalized_replay_sha256'], 'normalizer replay hash')
    raw_path = ROOT / 'docs/name-span-detector-screen-2026-11-28' / (case_id + '.json')
    check(sha(raw_path) == mapped['raw_report_sha256'] and read(raw_path)['raw_entities'] == mapped['raw_entities'], 'actual raw detector evidence')
    nonce = digest({'source': joined, 'spans': [{'start': m['global_start'], 'end': m['global_end']} for m in bundle['markers']]})[:16]
    reconstructed = copy.deepcopy(bundle['masked_segments'])
    for occurrence, marker in enumerate(bundle['markers']):
        check(marker['marker'] == f"__LSNP_{nonce}_{marker['segment_index']:04d}_{occurrence:04d}__", 'only source-derived marker')
        segment = source['segments'][marker['segment_index']]
        check(segment['text'][marker['start']:marker['end']] == marker['source_text'] == joined[marker['global_start']:marker['global_end']], 'exact source slice')
        check(reconstructed[marker['segment_index']]['text'].count(marker['marker']) == 1, 'one same-segment source marker')
        reconstructed[marker['segment_index']]['text'] = reconstructed[marker['segment_index']]['text'].replace(marker['marker'], marker['source_text'])
    check(reconstructed == source['segments'], 'full text and metadata roundtrip')
    check(bundle['protection_binding_sha256'] == digest({'source_segments_sha256':bundle['source_segments_sha256'], 'masked_segments':bundle['masked_segments'], 'markers':bundle['markers']}), 'protection digest')
    body, old_body = request['request'], old_request['request']
    check({k:v for k,v in body.items() if k != 'messages'} == {k:v for k,v in old_body.items() if k != 'messages'}, 'native settings/schema unchanged')
    check(body['messages'][0]['content'] == old_body['messages'][0]['content'] + instruction, 'only generic system addition')
    check([m['role'] for m in body['messages']] == ['system','user'], 'two-message format')
    user = body['messages'][1]['content']
    prefix, values = user.split('JSON input: ', 1)
    check(prefix == old_body['messages'][1]['content'].split('JSON input: ',1)[0], 'target task unchanged')
    check(json.loads(values) == [{'id':i,'text':s['text']} for i,s in enumerate(masked_case['segments'])], 'full masked request')
    check(prompt['request'] == body and prompt['debug_response'].get('eval_count',0) == 0 and not prompt['debug_response'].get('message',{}).get('content'), 'actual answer-free render')
    system = body['messages'][0]['content']
    rendered = '<|start_header_id|>system<|end_header_id|>\n\nCutting Knowledge Date: December 2023\nToday Date: 28 Nov 2026\n\n' + system + '<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n' + user + '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n'
    check(prompt['rendered_prompt'] == rendered and prompt['rendered_sha256'] == hashlib.sha256(rendered.encode()).hexdigest(), 'exact native formatting/messages')
    tokens = prompt['tokens']
    check(len(tokens) == prompt['prompt_tokens'] and tokens[0] == 128000 and tokens.count(128000) == 1 and prompt['tokenize_add_special'] is True, 'one native BOS and token count')
    check(len(tokens) + 2048 + 1 <= 4096 and prompt['unused_capacity_after_maximum_output'] == 4096-len(tokens)-2048, 'all output capacity reserved')
    command = prompt['runner']['command']
    check(command[command.index('-c')+1] == '4096' and command[command.index('-t')+1] == '4' and command[command.index('-np')+1] == '1', 'actual runner profile')
    check('--offline' in command and plan['model']['sha256'] in command[command.index('--model')+1], 'actual declared model/offline')
    check(prompt['runner']['executable_sha256'] == plan['runtime']['files_sha256']['lib/ollama/llama-server'], 'runner binary identity')
    rows.append({'id':case_id,'source_segments':len(source['segments']),'exact_source_mentions':len(bundle['markers']),'full_source_metadata_roundtrip':True,'native_prompt_tokens':len(tokens),'unused_context_after_full_output':4096-len(tokens)-2048})

controls = read(STAGE / 'protection-control-results.json')
check(controls['complete'] and len(controls['results']) == controls['controls'] == 24 and all(r['mechanical_passed'] for r in controls['results']), '24 recorded controls')
check(controls['results'][-1]['id'] == 'within-segment-role-order-not-certified' and controls['results'][-1]['semantic_limit'], 'role reversal limitation retained')
old_ast = ast.parse((ROOT / 'docs/name-span-detector-screen-2026-11-28/run_phase.py').read_text())
new_ast = ast.parse((STAGE / 'resource_monitor.py').read_text().replace('GEMMA_EVENT ', 'PERSON_EVENT '))
old_functions = {n.name:ast.dump(n,include_attributes=False) for n in old_ast.body if isinstance(n,ast.FunctionDef)}
new_functions = {n.name:ast.dump(n,include_attributes=False) for n in new_ast.body if isinstance(n,ast.FunctionDef)}
for name in ['alive_owned','owned_group','stop_owned','monitor']:
    check(old_functions[name] == new_functions[name], 'reviewed observer function unchanged ' + name)
resources = read(STAGE / 'prepare-resources.json')
samples_path = STAGE / 'prepare-samples.jsonl'
check(sha(samples_path) == resources['samples_sha256'], 'full sample series hash')
samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
check(len(samples) == resources['sample_count'] == 220, '220 actual samples')
check(resources['passed'] and resources['complete'] and resources['measurement_complete'] and not resources['measurement_errors'] and resources['owned_processes_stopped'] and resources['worker_exit_code'] == 0, 'measured completion')
check(resources['phase_report_sha256'] == sha(STAGE/'prepare.json'), 'resource-to-phase binding')
check(resources['limits'] == {'rss_bytes':6442450944,'total_seconds':600,'initialization_seconds':180,'case_seconds':600}, 'fixed preparation limits')
for sample in samples:
    check(len({p['pid'] for p in sample['processes']}) == len(sample['processes']), 'resource deduplication')
    check(sum(p['rss_bytes'] for p in sample['processes']) == sample['rss_bytes'], 'RSS sum')
    check(sum(p['pss_bytes'] for p in sample['processes']) == sample['pss_bytes'], 'PSS sum')
check(all(a['elapsed_seconds'] <= b['elapsed_seconds'] for a,b in zip(samples,samples[1:])), 'ordered sample clock')
check(max(samples,key=lambda s:s['rss_bytes']) == resources['peak_rss_sample'], 'actual RSS peak sample')
check(max(samples,key=lambda s:s['pss_bytes']) == resources['peak_pss_sample'], 'actual PSS peak sample')
check(max(s['rss_bytes'] for s in samples) <= 6442450944 and resources['elapsed_seconds'] < 180 and len(resources['cpu_affinity']) == 4, 'actual resource bounds')
check(resources['free_disk_after_bytes'] >= 1024**3 and resources['disk_reserve_retained'], 'disk reserve')

report = {'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),'complete':True,'passed':True,'plan_sha256':sha(STAGE/'plan.json'),'native_setup_freeze_sha256':sha(STAGE/'native-setup-freeze.json'),'frozen_source_files_verified':59,'native_freeze_files_verified':len(freeze['files_sha256']),'unchanged_source_and_criteria_sha256':sha(original_path),'unchanged_person_annotation_sha256':sha(annotations_path),'cases':rows,'exact_source_mentions':sum(r['exact_source_mentions'] for r in rows),'generic_controls_recorded_pass':24,'observer_core_ast_unchanged_except_event_prefix':True,'preparation':{'generation_calls':0,'model_downloads':0,'native_create_calls':0,'elapsed_seconds':resources['elapsed_seconds'],'full_sample_count':len(samples),'peak_rss_bytes':resources['peak_rss_sample']['rss_bytes'],'peak_pss_bytes':resources['peak_pss_sample']['pss_bytes'],'owned_processes_stopped':True},'no_model_import_or_execution_by_reviewer':True,'audit_script_sha256':sha(Path(__file__))}
out = HERE / 'native-contract-audit.json'
with out.open('x',encoding='utf-8') as stream:
    json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps({'passed':True,'report':str(out),'sha256':sha(out),'cases':rows},ensure_ascii=False))

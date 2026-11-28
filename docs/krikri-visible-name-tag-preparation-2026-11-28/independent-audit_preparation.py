"""Read retained preparation bytes and test only the changed pure restoration guard."""
import ast
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
STAGE = ROOT/'docs/krikri-visible-name-tag-preparation-2026-11-28'
PRIOR = ROOT/'docs/krikri-compact-tag-screen-2026-11-28'
BASE = ROOT/'docs/krikri-screen-2026-11-28'
HERE = Path(__file__).resolve().parent
def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def check(value, label):
    if not value: raise AssertionError(label)

check(sha(STAGE/'plan.json') == 'dcab0f9ef25ad365c915a44f287a3bdc607ef5856027215ed81b9325bcff893d', 'frozen plan')
check(sha(STAGE/'preparation-freeze.json') == 'a75d624fa3b29ae2fe4522fa3e32b2c93932a721fecbde7236d50f6547b73b77', 'completed preparation identity')
plan, freeze = read(STAGE/'plan.json'), read(STAGE/'preparation-freeze.json')
for mapping in [plan['source_sha256'], freeze['files_sha256']]:
    for relative, expected in mapping.items(): check(sha(ROOT/relative) == expected, 'frozen ' + relative)
check(sha(STAGE/'development-cases.json') == '48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce', 'original six source/criteria')
check(sha(STAGE/'independent-criterion-binding.json') == 'cd8c9bd75d0e5eaca23d9ac93a728f13d2ccf4490f57af1f1b43d5ed19047ab1', 'unchanged original meaning binding')
oldtree, newtree = [ast.parse((p/'protection.py').read_text(encoding='utf-8')) for p in [PRIOR, STAGE]]
for name in ['canonical', 'digest', 'reserved_present', 'strict_response_strings']:
    nodes = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name) for tree in [oldtree, newtree]]
    check(ast.dump(nodes[0], include_attributes=False) == ast.dump(nodes[1], include_attributes=False), 'unchanged ' + name)
instruction = (STAGE/'marker-instruction.txt').read_text(encoding='utf-8').removesuffix('\n')
baseline = (BASE/'enhancements-context4096.py').read_text(encoding='utf-8')
check(baseline.replace('Do not omit or add entries.', 'Do not omit or add entries.' + instruction) == (STAGE/'enhancements-context4096.py').read_text(encoding='utf-8'), 'only generic instruction added to baseline adapter')
sources = read(STAGE/'development-cases.json')['cases']
maps, oldmaps = [read(p/'protection-inputs.json')['cases'] for p in [STAGE, PRIOR]]
requests, oldrequests = [read(p/'expected-requests.json') for p in [STAGE, BASE]]
estimates, oldprompts = read(STAGE/'token-estimates.json'), read(PRIOR/'prepare.json')['prompts']
check(len(sources) == len(maps) == len(oldmaps) == len(requests) == len(estimates['cases']) == 6, 'complete six cases')
rows = []
for source, mapped, old, request, previous, estimate, oldprompt in zip(sources, maps, oldmaps, requests, oldrequests, estimates['cases'], oldprompts):
    check(all(r['id'] == source['id'] for r in [mapped, old, request, previous, estimate, oldprompt]), 'original order')
    bundle = mapped['bundle']
    check(bundle['source_segments'] == source['segments'] == old['bundle']['source_segments'], 'original complete source')
    for key in ['normalizer_result', 'source_segments_sha256', 'source_text_sha256', 'source_binding_sha256']:
        check(bundle[key] == old['bundle'][key], 'unchanged source and normalizer ' + key)
    check(mapped['raw_entities'] == old['raw_entities'], 'same actual detector spans')
    check(bundle['source_segments_sha256'] == digest(source['segments']), 'source metadata hash')
    check(bundle['protection_binding_sha256'] == digest({'source_segments_sha256': bundle['source_segments_sha256'], 'masked_segments': bundle['masked_segments'], 'markers': bundle['markers']}), 'external map hash')
    reconstructed = copy.deepcopy(bundle['masked_segments'])
    for index, (marker, before) in enumerate(zip(bundle['markers'], old['bundle']['markers'])):
        for key in ['segment_index', 'start', 'end', 'source_text', 'global_start', 'global_end', 'raw', 'normalizer_status']:
            check(marker[key] == before[key], 'same reviewed mention ' + key)
        exact = source['segments'][marker['segment_index']]['text'][marker['start']:marker['end']]
        check(exact == marker['source_text'] and marker['marker_index'] == index, 'exact name and occurrence identity')
        check(marker['marker'] == f'<x{index}>' + exact + f'</x{index}>', 'visible exact source pair')
        segment = reconstructed[marker['segment_index']]
        check(segment['text'].count(marker['marker']) == 1, 'one original source occurrence')
        segment['text'] = segment['text'].replace(marker['marker'], exact)
    check(len(bundle['markers']) == len(old['bundle']['markers']) and reconstructed == source['segments'], 'all source characters/metadata round-trip')
    body, oldbody = request['request'], previous['request']
    check({k:v for k,v in body.items() if k != 'messages'} == {k:v for k,v in oldbody.items() if k != 'messages'}, 'unchanged request settings/schema')
    check(body['messages'][0]['content'] == oldbody['messages'][0]['content'] + instruction, 'generic system instruction only')
    prefix, data = body['messages'][1]['content'].split('JSON input: ', 1)
    check(prefix == oldbody['messages'][1]['content'].split('JSON input: ', 1)[0], 'unchanged target/task instruction')
    check(json.loads(data) == [{'id':i, 'text':s['text']} for i,s in enumerate(bundle['masked_segments'])], 'complete visible-source actual request')
    encoded = json.dumps(json.loads(data), ensure_ascii=False, separators=(',', ':'))
    check(len(encoded.encode('utf-8')) <= 1000, 'unchanged full-source JSON capacity')
    rendered = oldprompt['rendered_prompt']
    for a, b in zip(oldprompt['request']['messages'], body['messages']):
        check(rendered.count(a['content']) == 1, 'complete retained native message')
        rendered = rendered.replace(a['content'], b['content'], 1)
    check(rendered == estimate['estimated_rendered_prompt'], 'estimated native wrapper retains full messages')
    tokens = estimate['estimated_tokens']
    check(len(tokens) == estimate['estimated_prompt_tokens'] and tokens[0] == 128000 and tokens.count(128000) == 1, 'estimated BOS and token count')
    check(len(tokens) + 2048 + 1 <= 4096, 'full output plus end reserve')
    rows.append({'id':source['id'], 'source_mentions':len(bundle['markers']), 'full_source_roundtrip_exact':True, 'estimated_prompt_tokens':len(tokens), 'actual_new_native_accounting_observed':False})
check(sum(r['source_mentions'] for r in rows) == 13, 'same 13 source mentions')
controls = read(STAGE/'protection-control-results.json')
check(controls['controls'] == len(controls['results']) == 47 and all(r['mechanical_passed'] for r in controls['results']), '47 retained controls')
check(sum(bool(r.get('semantic_limit')) for r in controls['results']) == 4, 'four acknowledged semantic limitations')
check(len(estimates['prior_vectors_equal']) == 6 and all(r['entire_vector_equal'] for r in estimates['prior_vectors_equal']), 'recorded six full prior-native vector comparisons')

# Only the changed pure restoration functions are compiled. No builder,
# normalizer, tokenizer, model, app or native endpoint is imported or run.
names = {'canonical', 'digest', 'reserved_present', 'restore_segments'}
nodes = [n for n in newtree.body if isinstance(n, ast.FunctionDef) and n.name in names]
scope = {'copy':copy, 'Counter':Counter, 'hashlib':hashlib, 'json':json, 're':re, 'unicodedata':unicodedata,
         'PATTERN':re.compile(r'<x(?P<index>0|[1-9][0-9]{0,3})>(?P<source_text>.*?)</x(?P=index)>', re.DOTALL)}
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<reviewed-pure-restoration>', 'exec'), scope)
bundle = maps[0]['bundle']
valid, audit = scope['restore_segments'](bundle, copy.deepcopy(bundle['masked_segments']))
check(valid == sources[0]['segments'] and all(r['wrapper_only_removal'] and not r['changed_inner_text_repaired'] for r in audit), 'only wrappers stripped')
probe_results = []
for label, mutate in [
    ('changed_inner_name_must_reject', lambda text: text.replace('<x0>Maria</x0>', '<x0>Mara</x0>')),
    ('valid_pair_plus_residual_closing_must_reject', lambda text: text + ' </x0>'),
    ('nested_same_index_must_reject', lambda text: text.replace('<x0>Maria</x0>', '<x0><x0>Maria</x0></x0>')),
]:
    response = copy.deepcopy(bundle['masked_segments'])
    response[0]['text'] = mutate(response[0]['text'])
    try:
        scope['restore_segments'](bundle, response)
    except ValueError as error:
        probe_results.append({'id':label, 'rejected':True, 'error':str(error)})
    else:
        raise AssertionError(label)
result = {'schema_version':1, 'reviewed_at':datetime.now(timezone.utc).isoformat(), 'audit_passed':True,
          'plan_sha256':sha(STAGE/'plan.json'), 'preparation_freeze_sha256':sha(STAGE/'preparation-freeze.json'),
          'source_bindings_verified':len(plan['source_sha256']), 'completed_bindings_verified':len(freeze['files_sha256']),
          'candidate_sha256':sha(STAGE/'protection.py'), 'cases':rows, 'retained_controls':47,
          'pure_restoration_probes':probe_results, 'original_criteria_unchanged':True,
          'reviewer_model_tokenizer_native_provider_or_detector_calls':0,
          'scope':'Preparation integrity and changed pure-guard checks only. Token estimates are retained reported values; reviewer did not rerun the tokenizer or native runtime.',
          'audit_script_sha256':sha(Path(__file__))}
target = HERE/'preparation-audit.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'path':str(target), 'sha256':sha(target), 'audit_passed':True}))

"""Read/hash/AST-only review; never imports or executes candidate modules."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'docs/krikri-marker-grammar-screen-preparation-2026-11-28'
NEW = ROOT / 'docs/krikri-marker-grammar-screen-preparation-v2-2026-11-28'
PRIOR = ROOT / 'docs/krikri-source-spelling-screen-2026-11-28'
GRAMMAR = ROOT / 'docs/krikri-marker-grammar-preparation-2026-11-28'
NATIVE = ROOT / 'docs/krikri-marker-grammar-build-continuation-2026-11-28'
ACTUAL_REVIEW = Path('/workspace/scratch/94360995dd61/grammar-native-prepare-independent-review-2026-11-28/independent-native-validation-review.json')
checks = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check(label, okay):
    checks.append({'check': label, 'passed': bool(okay)})
    if not okay:
        raise AssertionError(label)


def item(path):
    path = Path(path)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def function(path, name):
    return next(node for node in ast.parse(Path(path).read_text(encoding='utf-8')).body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name)


def dump(value):
    return ast.dump(value, include_attributes=False)


for path, expected in [
    (OLD / 'plan.json', '514369ee0bbe9550907e0d9e8f0fef94976462da41348b5ca83d24e70cdf6a75'),
    (OLD / 'manifest.json', '78ca0cdbab68879d1b637a1de6d9c6adac497fab12273082256779e77ade28f8'),
    (NEW / 'plan.json', '735ca4e02410c06b15c41c99c7f3d3b3c88a9007e858abfd727be686d67ff796'),
    (NEW / 'manifest.json', 'ca026d2c798f6c140fefca18e64f11cae10781252392789e37b40f7c905114d5'),
    (NEW / 'native_gate.py', '8ecb84b8735ffaaa7e005bc0d3a4b29c855522a3082b5de8c5b577f4868e292d'),
    (NEW / 'infer_native.py', '2ad2b37438c29f05f2178a8cb3f0d5d8d8a3bc7e862c879356a2acf37b21db38'),
    (NEW / 'resource_monitor.py', 'fac821f2f0c7a70d3b835981b5bc19dade8ed2991c802aef36dbc10be3d5d99b'),
    (NATIVE / 'native_prepare.json', '92c674e206ac013d90e6efd1f1570152f1d07682e138915047aba6146640ad2c'),
    (ACTUAL_REVIEW, '7b6b977c0f01eadf652e36eb39973f52ca2bd109055da116ad5b42f3c1f8675a'),
]:
    check('fixed identity: ' + str(path), sha(path) == expected)

counts = {}
for directory in (OLD, NEW):
    plan = read(directory / 'plan.json')
    manifest = read(directory / 'manifest.json')
    check('plan sidecar: ' + directory.name,
          sha(directory / 'plan.json') == (directory / 'plan.sha256').read_text().strip())
    check('manifest sidecar: ' + directory.name,
          sha(directory / 'manifest.json') == (directory / 'manifest.sha256').read_text().strip())
    for relative, expected in plan['source_sha256'].items():
        path = ROOT / relative
        check('source: ' + str(path), not path.is_symlink() and sha(path) == expected)
    for row in manifest['files']:
        path = directory / row['path']
        check('manifest member: ' + str(path), not path.is_symlink()
              and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
    counts[directory.name] = {'source_bindings': len(plan['source_sha256']),
                              'manifest_members': len(manifest['files'])}

old_plan, plan, prior_plan = (read(path / 'plan.json') for path in (OLD, NEW, PRIOR))
for key in ('model', 'runtime', 'python_runtime', 'native_setup', 'limits', 'evaluation'):
    check('unchanged original profile: ' + key, plan[key] == old_plan[key] == prior_plan[key])
for name in ('execution_gate.py', 'format_projection.py', 'infer_native.py', 'run_native.py', 'resource_monitor.py'):
    check('unchanged execution file: ' + name, (OLD / name).read_bytes() == (NEW / name).read_bytes())
check('exact prior reviewed monitor', (NEW / 'resource_monitor.py').read_bytes() ==
      (ROOT / 'docs/krikri-marker-grammar-controller-v2-2026-11-28/resource_monitor.py').read_bytes())
check('context changes private path only',
      (OLD / 'context.py').read_text().replace('runtime/marker-grammar-screen")',
                                             'runtime/marker-grammar-screen-v2")') ==
      (NEW / 'context.py').read_text())
for name in ('read', 'require_native_contract'):
    check('unchanged native function AST: ' + name,
          dump(function(OLD / 'native_gate.py', name)) == dump(function(NEW / 'native_gate.py', name)))
check('original fourteen control AST unchanged',
      dump(function(OLD / 'check_preparation.py', 'PreparationControls')) ==
      dump(function(NEW / 'check_preparation.py', 'PreparationControls')))

old_evidence = function(OLD / 'native_gate.py', 'require_native_evidence')
new_evidence = function(NEW / 'native_gate.py', 'require_native_evidence')
old_index = next(i for i, node in enumerate(old_evidence.body)
                 if isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                 and node.target.id == 'call' and isinstance(node.iter, ast.Name) and node.iter.id == 'calls')
replacement = new_evidence.body[old_index]
check('only receipt loop replacement shape', isinstance(replacement, ast.Expr)
      and isinstance(replacement.value, ast.Call) and isinstance(replacement.value.func, ast.Name)
      and replacement.value.func.id == 'require_http_receipts')
old_evidence.body[old_index] = replacement
check('rest of actual prerequisite gate AST unchanged', dump(old_evidence) == dump(new_evidence))

requests = read(GRAMMAR / 'expected-requests.json')
previous = read(PRIOR / 'expected-requests.json')
native = read(NATIVE / 'native_prepare.json')
queries = read(GRAMMAR / 'proposed-native-grammar-queries.json')['queries']
cases = read(PRIOR / 'development-cases.json')['cases']
protections = read(PRIOR / 'protection-inputs.json')['cases']
check('six ordered original requests', len(requests) == len(previous) == len(cases) == 6
      and [x['id'] for x in requests] == plan['evaluation']['case_ids'] == [x['id'] for x in cases])
for old, new, prompt, query in zip(previous, requests, native['prompts'], queries):
    case_id = new['id']
    check(case_id + ' exact only-format change', old['id'] == case_id
          and old['request']['format'] != new['request']['format']
          and {k:v for k,v in old['request'].items() if k != 'format'} ==
              {k:v for k,v in new['request'].items() if k != 'format'})
    check(case_id + ' actual complete native source/schema binding',
          prompt['id'] == case_id == query['id'] and prompt['request'] == new['request']
          and new['request']['format'] == query['request']['json_schema'])
    check(case_id + ' full native prompt fits unchanged output allowance',
          len(prompt['tokens']) == prompt['prompt_tokens']
          and len(prompt['tokens']) + 2048 + 1 <= 4096
          and prompt['tokens'][0] == 128000 and prompt['tokens'].count(128000) == 1)

gate = function(NEW / 'native_gate.py', 'require_http_receipts')
refusal = next(node.value for node in gate.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'first_refusal' for target in node.targets))
exact_refusal = ast.literal_eval(refusal)
calls = native['http_calls']
check('actual initial no-response refusal equals exact permitted literal', calls[0] == exact_refusal)
check('actual immediate successful pinned-version receipt', calls[1]['kind'] == 'version'
      and calls[1]['response'] == {'version': plan['runtime']['version']})
for index, call in enumerate(calls[1:], 1):
    record = call['raw_response']
    path = Path(record['path'])
    check('retained raw successful response ' + str(index), call['index'] == index
          and call['complete'] is True and call['http_status'] == 200 and 'error' not in call
          and path.stat().st_size == record['bytes'] and sha(path) == record['sha256']
          and read(path) == call['response'])
check('actual 24 attempts and 23 full raw responses', len(calls) == 24)

controls = read(NEW / 'source-only-controls.json')
control_names = [n.name for n in ast.walk(ast.parse((NEW / 'check_preparation.py').read_text()))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
check('reported 21 controls match source method inventory', len(control_names) == 21
      and controls['test_count'] == 21 and controls['exit_code'] == 0)
check('control log bound', sha(NEW / 'source-only-controls.txt') == controls['log_sha256'])
check('control result bound to current plan', controls['plan_sha256'] == sha(NEW / 'plan.json'))
for row in controls['syntax']:
    check('control source identity: ' + row['path'], sha(ROOT / row['path']) == row['sha256'])

result = {
    'schema_version': 1,
    'created_at': datetime.now(timezone.utc).isoformat(),
    'scope': 'Independent read/hash/AST-only audit; no candidate import, control rerun, network, native, compiler, tokenizer, validator or model execution.',
    'source_counts': counts,
    'checked_files': [item(NEW / name) for name in ('plan.json','manifest.json','context.py','native_gate.py',
                      'format_projection.py','execution_gate.py','infer_native.py','run_native.py','resource_monitor.py')],
    'prior_actual_native_review': item(ACTUAL_REVIEW),
    'original_corpus': item(PRIOR / 'development-cases.json'),
    'actual_native_prompt_counts': [x['prompt_tokens'] for x in native['prompts']],
    'retained_readiness_shape': {'first_refusals': 1, 'raw_successes': 23, 'attempts': 24},
    'owner_control_evidence': item(NEW / 'source-only-controls.json'),
    'controls_reviewed_not_reexecuted': control_names,
    'receipts_at_audit_time': {name: (NEW/name).exists() for name in
        ('infer-authorization.json','infer-claim.json','execution.json','native-evidence-freeze.json')},
    'checks_passed': len(checks), 'checks': checks, 'errors': [],
}
(OUT / 'source-contract-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks_passed':len(checks),'audit_sha256':sha(OUT/'source-contract-audit.json'),
                  'source_counts':counts,'candidate_execution_performed':False}))

"""Read-only source/data audit; never imports or executes candidate code."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE = Path(__file__).resolve().parent
STAGE = ROOT / 'docs/krikri-marker-grammar-controller-2026-11-28'
NATIVE = ROOT / 'docs/krikri-marker-grammar-native-plan-2026-11-28'
PREP = ROOT / 'docs/krikri-marker-grammar-preparation-2026-11-28'
PRIOR = ROOT / 'docs/krikri-source-spelling-screen-2026-11-28'
checks = []

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def check(name, value, detail=None):
    checks.append({'id': name, 'passed': bool(value), 'detail': detail})

def bindings(path, root, key='source_sha256'):
    data = read(path)
    for relative, expected in data[key].items():
        target = root / relative
        check(str(path.relative_to(ROOT)) + ':' + relative,
              target.is_file() and not target.is_symlink() and digest(target) == expected)
    return data

plan = bindings(STAGE / 'plan.json', ROOT)
check('controller-plan-sha-sidecar', digest(STAGE / 'plan.json') == (STAGE / 'plan.sha256').read_text().strip())
native = bindings(NATIVE / 'plan.json', ROOT)
check('native-plan-identity', digest(NATIVE / 'plan.json') == plan['native_plan_sha256'])
check('grammar-preparation-plan-identity', digest(PREP / 'plan.json') == plan['grammar_preparation_plan_sha256'])

manifest = read(STAGE / 'evidence-manifest.json')
for entry in manifest['files']:
    target = STAGE / entry['path']
    check('controller-manifest:' + entry['path'], target.is_file() and not target.is_symlink()
          and target.stat().st_size == entry['bytes'] and digest(target) == entry['sha256'])

inventory = read(NATIVE / 'source-acquisition.json')
capsule = read(STAGE / 'official-source-capsule.json')
check('official-repository-revision', all(capsule[key] == inventory[key] for key in ('repository', 'revision')))
check('official-ordered-allowlist', [x['path'] for x in capsule['files']] == [x['path'] for x in inventory['files']])
total = 0
for actual, expected in zip(capsule['files'], inventory['files']):
    body = actual['content'].encode('utf-8')
    blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    check('official-object:' + actual['path'], len(body) == actual['bytes'] == expected['bytes']
          and blob == actual['git_blob_sha1'] == expected['git_blob_sha1'])
    total += len(body)
check('official-source-count-total', len(capsule['files']) == inventory['file_count'] == 11
      and total == inventory['total_bytes'] == 289300)

metadata = read(NATIVE / 'retained-binary-metadata.json')
for item in metadata['files'] + plan['extra_tool_bindings']:
    p = Path(item['path'])
    check('retained-tool-library:' + item['path'], str(p.resolve()) == item['resolved']
          and p.stat().st_size == item['bytes'] and digest(p) == item['sha256'])

requests = read(PREP / 'expected-requests.json')
old_requests = read(PRIOR / 'expected-requests.json')
cases = read(PRIOR / 'protected-source-cases.json')['cases']
queries = read(PREP / 'proposed-native-grammar-queries.json')['queries']
probes = read(PREP / 'native-probe-matrix.json')['probes']
check('complete-six-request-order', len(requests) == len(old_requests) == len(cases) == 6
      and [x['id'] for x in requests] == [x['id'] for x in old_requests] == [x['id'] for x in cases])
for current, old, case, query in zip(requests, old_requests, cases, queries):
    body = current['request']
    check('format-only-request-change:' + current['id'],
          {k: v for k, v in body.items() if k != 'format'} == {k: v for k, v in old['request'].items() if k != 'format'})
    source = json.loads(body['messages'][1]['content'].split('JSON input: ', 1)[1])
    check('complete-masked-source:' + current['id'],
          source == [{'id': i, 'text': row['text']} for i, row in enumerate(case['segments'])])
    check('actual-query-schema-binding:' + current['id'], current['id'] == query['id']
          and query['request']['json_schema'] == body['format'])
check('ordered-seven-zero-output-queries', len(queries) == 7 and all(
    q['request']['prompt'] == [[]] and type(q['request']['n_predict']) is int and q['request']['n_predict'] == 0
    and q['request']['response_fields'] == ['generation_settings/grammar'] for q in queries))
check('unchanged-285-native-probes', len(probes) == 285 and
      {x['case_id'] for x in probes} == {x['id'] for x in cases} and
      all(type(x['expected_native_acceptance']) is bool for x in probes))
check('separate-unsupported-sentinel', queries[-1]['id'] == 'unsupported-lookahead-gate-sentinel'
      and queries[-1]['request']['json_schema'] not in [x['request']['format'] for x in requests])

asts = {}
for path in sorted(STAGE.glob('*.py')):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    asts[path.name] = tree
    check('static-parse:' + path.name, True)
for name in ('context.py', 'execution_gate.py', 'phase_worker.py', 'process_io.py', 'phase_actions.py', 'status_contract.py'):
    check('foundation-snapshot-identical:' + name, (STAGE / name).read_bytes() ==
          (STAGE / 'review-snapshots/acquire-build-v1' / name).read_bytes())
check('strict-status-parser-identical', (STAGE / 'status_contract.py').read_bytes() == (NATIVE / 'status_contract.py').read_bytes())

controls = read(STAGE / 'source-control-results.json')
check('recorded-controls-pass-without-rerun', len(controls['checks']) == 57 and controls['passed'] is True
      and all(x['passed'] for x in controls['checks']))
check('recorded-controls-no-native-authority', controls['compiler_native_library_converter_tokenizer_model_calls'] == 0
      and controls['network_calls'] == 0 and controls['actual_root_receipts_created'] == 0
      and controls['native_probe_matrix_not_executed'] is True)
resource_count = 0
for c in controls['checks']:
    if 'resource_report' not in c:
        continue
    item = c['resource_report']; path = Path(item['path']); report = read(path)
    check('retained-resource-report:' + c['id'], path.stat().st_size == item['bytes'] and digest(path) == item['sha256'])
    samples_path = path.parent / report['samples_file']
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    check('retained-resource-samples:' + c['id'], digest(samples_path) == report['samples_sha256']
          and len(samples) == report['sample_count'] and report['measurement_complete'] is True
          and report['owned_processes_stopped'] is True and not report['measurement_errors'])
    check('retained-resource-sums:' + c['id'], all(s['rss_bytes'] == sum(p['rss_bytes'] for p in s['processes'])
          and s['pss_bytes'] == sum(p['pss_bytes'] for p in s['processes']) for s in samples))
    check('retained-resource-stop:' + c['id'], report.get('stop_reason') == c['observed_stop_reason'])
    resource_count += 1
check('five-harmless-process-controls', resource_count == 5)

out = {'schema_version': 1, 'scope': 'Independent static source/hash/AST and retained-data audit only; candidate modules/entrypoints/controls were not imported or executed.',
       'plan_sha256': digest(STAGE / 'plan.json'), 'manifest_sha256': digest(STAGE / 'evidence-manifest.json'),
       'source_bindings': len(plan['source_sha256']), 'native_plan_source_bindings': len(native['source_sha256']),
       'manifest_files': len(manifest['files']), 'official_source_objects': len(capsule['files']),
       'retained_tools_libraries': len(metadata['files']) + len(plan['extra_tool_bindings']),
       'owned_build_root_exists_at_audit': Path(plan['owned_runtime_root']).exists(),
       'root_phase_receipts_present_at_audit': [p for p in plan['phases'] if (STAGE / (p + '-authorization.json')).exists()],
       'checks': checks, 'passed': all(c['passed'] for c in checks),
       'compiler_native_library_converter_tokenizer_model_network_calls': 0,
       'control_reexecutions': 0}
(HERE / 'source-contract-audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': out['passed'], 'checks': len(checks), 'errors': [c for c in checks if not c['passed']],
                  'audit_sha256': digest(HERE / 'source-contract-audit.json')}, ensure_ascii=False))

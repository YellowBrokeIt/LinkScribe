"""Read-only source audit. No candidate import, tokenizer or native execution."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
OUT = Path(__file__).resolve().parent
STAGE = ROOT / 'docs/krikri-source-spelling-screen-2026-11-28'
COMPACT = ROOT / 'docs/krikri-compact-tag-screen-2026-11-28'
PROPOSAL = ROOT / 'docs/krikri-source-spelling-context-2026-11-28'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_bindings(bindings):
    failures = [name for name, expected in bindings.items() if sha(ROOT / name) != expected]
    return {'count': len(bindings), 'mismatches': failures, 'passed': not failures}


plan = load(STAGE / 'plan.json')
freeze = load(STAGE / 'preparation-freeze.json')
reuse = load(STAGE / 'reuse-verification.json')
checks = {}
checks['plan_exact'] = sha(STAGE / 'plan.json') == 'cd20d9168446cbe0ece0cc2795b5bb501fd0f182c3a4697b129c9c3227728392'
checks['preparation_freeze_exact'] = sha(STAGE / 'preparation-freeze.json') == '7492e898c79f8ec340da91b956e4b33ae8763d73188acdcaf900e3acb138e8f3'
source_bindings = check_bindings(plan['source_sha256'])
freeze_bindings = check_bindings(freeze['files_sha256'])
checks['source_bindings'] = source_bindings['passed'] and source_bindings['count'] == 116
checks['freeze_bindings'] = freeze_bindings['passed'] and freeze_bindings['count'] == 32
compact_files = {}
for name, expected in reuse['byte_identical_compact_files'].items():
    compact_files[name] = sha(STAGE / name) == sha(COMPACT / name) == expected
checks['all_compact_reuse'] = all(compact_files.values())
proposal_files = {}
for name, expected in reuse['byte_identical_reviewed_proposal_files'].items():
    proposal_files[name] = sha(STAGE / name) == sha(PROPOSAL / name) == expected
checks['all_proposal_reuse'] = all(proposal_files.values())
runtime_diff = ''.join(''.join(difflib.unified_diff(
    (COMPACT / name).read_text().splitlines(keepends=True),
    (STAGE / name).read_text().splitlines(keepends=True),
    fromfile='compact/' + name, tofile='source-spelling/' + name))
    for name in ['infer_native.py', 'prepare_native.py', 'run_native.py'])
checks['actual_runtime_diff_equals_retained_patch'] = runtime_diff == (STAGE / 'runtime-deltas.patch').read_text()
path_diff = ''.join(difflib.unified_diff(
    (COMPACT / 'context.py').read_text().splitlines(keepends=True),
    (STAGE / 'context.py').read_text().splitlines(keepends=True),
    fromfile='compact/context.py', tofile='source-spelling/context.py'))
checks['actual_path_diff_equals_retained_patch'] = path_diff == (STAGE / 'runtime-path-only.patch').read_text()
for path in [STAGE / name for name in ['source_context.py', 'execution_gate.py', 'prepare_native.py', 'infer_native.py', 'run_native.py']]:
    ast.parse(path.read_text())
checks['changed_runtime_syntax'] = True
maps = load(STAGE / 'source-context-maps.json')['cases']
bundles = load(STAGE / 'protection-inputs.json')['cases']
sources = load(STAGE / 'development-cases.json')['cases']
requests = load(STAGE / 'expected-requests.json')
checks['six_complete_case_order'] = len(maps) == len(bundles) == len(sources) == len(requests) == 6 and [v['id'] for v in maps] == [v['id'] for v in bundles] == [v['id'] for v in sources] == [v['id'] for v in requests]
mention_checks = []
for source, item, mapping in zip(sources, bundles, maps):
    bundle = item['bundle']
    expected = []
    for mention in bundle['markers']:
        text = source['segments'][mention['segment_index']]['text']
        expected.append({'tag': mention['marker'], 'spelling': text[mention['start']:mention['end']]})
        mention_checks.append(text[mention['start']:mention['end']] == mention['source_text'])
    mention_checks.append(mapping['context_map'] == expected and mapping['source_segments'] == source['segments'] == bundle['source_segments'])
checks['all_thirteen_exact_source_occurrences'] = sum(len(v['bundle']['markers']) for v in bundles) == 13 and all(mention_checks)
checks['proposal_projector_unchanged'] = sha(PROPOSAL / 'prepare_context.py') == reuse['projection_function_reused_without_edit']['sha256']
checks['native_preflight_unchanged'] = sha(ROOT / reuse['native_preflight_reused_unchanged']['path']) == reuse['native_preflight_reused_unchanged']['sha256']
checks['criterion_binding_unchanged'] = sha(STAGE / 'independent-criterion-binding.json') == 'cd8c9bd75d0e5eaca23d9ac93a728f13d2ccf4490f57af1f1b43d5ed19047ab1'
record = {
    'schema_version': 1,
    'created_at': datetime.now(timezone.utc).isoformat(),
    'scope': 'Independent source/reuse/request-binding audit only; actual native preparation belongs to root review.',
    'plan_sha256': sha(STAGE / 'plan.json'),
    'preparation_freeze_sha256': sha(STAGE / 'preparation-freeze.json'),
    'source_bindings': source_bindings,
    'preparation_bindings': freeze_bindings,
    'compact_file_identity_checks': compact_files,
    'proposal_file_identity_checks': proposal_files,
    'checks': checks,
    'passed': all(checks.values()),
    'new_model_native_tokenizer_detector_network_calls': 0,
    'candidate_source_imports_by_this_audit': 0,
    'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [STAGE / n for n in ['source_context.py', 'execution_gate.py', 'infer_native.py', 'prepare_native.py', 'run_native.py', 'test_source_context.py', 'no-model-controls.json', 'runtime-deltas.patch', 'runtime-path-only.patch', 'source-context-maps.json', 'expected-requests.json']]},
}
with (OUT / 'source-contract-audit.json').open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'passed': record['passed'], 'checks': checks, 'audit_sha256': sha(OUT / 'source-contract-audit.json')}, indent=2))
raise SystemExit(not record['passed'])

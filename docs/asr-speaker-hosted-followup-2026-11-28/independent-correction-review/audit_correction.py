"""Read-only binding and source-delta audit; no candidate code is executed."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess

BASE = Path('/workspace/scratch/94360995dd61')
REPO = BASE / 'LinkScribe'
OUT = Path(__file__).resolve().parent
HEAD = 'd62df26c870f175f7454fe0c3900d97891c8bff5'
OLD_PLAN = 'docs/asr-speaker-timing-integration-2026-11-28/hosted-plan.json'
NEW_PLAN = 'docs/asr-speaker-hosted-followup-2026-11-28/hosted-plan.json'
EXPECTED = {
    NEW_PLAN: '30e723794e53facc18bd88675c81d402ae8bce846aca38d5338ff5065459abec',
    'tests/qa_speaker_integration.py': '9473330e6f56b58d3ae673103129f737da17e50b86cb33f79e1bcfdd66162560',
    '.github/workflows/speaker-integration-qa.yml': '46bd5db12008244930c11f794c7e32aab6997f09ba5f732bd61d1d8031bb2bd5',
    'tests/test_speaker_hosted_qa.py': '2cc7d67a6a0e15b12d37fff3f111412efd9156ac18e324803b4c8b148601d449',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())}


def committed(path):
    return subprocess.check_output(['git', 'show', HEAD + ':' + path], cwd=REPO)


checks = []


def check(name, result):
    checks.append({'name': name, 'passed': bool(result)})
    if not result:
        raise AssertionError(name)


old_bytes = committed(OLD_PLAN)
old = json.loads(old_bytes)
new = json.loads((REPO / NEW_PLAN).read_text(encoding='utf-8'))
check('parent_plan_preserved', (REPO / OLD_PLAN).read_bytes() == old_bytes)
for path, expected in EXPECTED.items():
    check('frozen/' + path, digest((REPO / path).read_bytes()) == expected)
for binding in new['source_files']:
    check('source/' + binding['path'], digest((REPO / binding['path']).read_bytes()) == binding['sha256'])
policy = ['protocol', 'attempts', 'maximum_cpus', 'rss_limit_bytes', 'total_worker_seconds',
          'phase_seconds', 'worker_environment', 'fixture', 'models', 'recognition_contract',
          'controlled_fixture_criteria', 'runtime_packages', 'measurement_contract', 'limitations']
for name in policy:
    check('unchanged/' + name, old[name] == new[name])
before = {item['path']: item for item in old['source_files']}
after = {item['path']: item for item in new['source_files']}
changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
check('exact_changed_execution_sources', changed == ['.github/workflows/speaker-integration-qa.yml', 'tests/qa_speaker_integration.py'])
old_workflow = committed('.github/workflows/speaker-integration-qa.yml').decode()
new_workflow = (REPO / '.github/workflows/speaker-integration-qa.yml').read_text(encoding='utf-8')
check('workflow_only_plan_reference_changed', new_workflow == old_workflow.replace(OLD_PLAN, NEW_PLAN))
old_helper = ast.parse(committed('tests/qa_speaker_integration.py').decode())
new_helper = ast.parse((REPO / 'tests/qa_speaker_integration.py').read_text(encoding='utf-8'))


def functions(tree):
    return {node.name: ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


original, candidate = functions(old_helper), functions(new_helper)
changed_functions = sorted(name for name in original.keys() | candidate.keys() if original.get(name) != candidate.get(name))
check('only_preparation_functions_changed', changed_functions == ['prepare', 'prepare_model_files', 'speaker_cache_declarations'])
remaining_old = [node for node in old_helper.body if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
remaining_new = [node for node in new_helper.body if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
remaining_new = [node for node in remaining_new if not (isinstance(node, ast.Import) and len(node.names) == 1 and node.names[0].name == 'urllib.error')]
for node in remaining_new:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and child.value == NEW_PLAN:
            child.value = OLD_PLAN
check('remaining_module_only_http_error_import_and_default_plan', ast.dump(ast.Module(body=remaining_old, type_ignores=[]), include_attributes=False) == ast.dump(ast.Module(body=remaining_new, type_ignores=[]), include_attributes=False))
archive = REPO / 'docs/asr-speaker-hosted-followup-2026-11-28/published-before-correction'
for archived, live in [('controller.py', 'tests/qa_speaker_integration.py'), ('controls.py', 'tests/test_speaker_hosted_qa.py'), ('workflow.yml', '.github/workflows/speaker-integration-qa.yml'), ('hosted-plan.json', OLD_PLAN)]:
    check('preserved_original/' + archived, (archive / archived).read_bytes() == committed(live))
owner_controls = BASE / 'asr-speaker-hosted-mapping-controls.txt'
check('owner_control_log_copied_unchanged', owner_controls.read_bytes() == (REPO / 'docs/asr-speaker-hosted-followup-2026-11-28/mapping-controls.txt').read_bytes())
check('owner_30_model_free_controls_reported_pass', '30 passed in 0.48s' in owner_controls.read_text(encoding='utf-8'))
report = {
    'scope': 'Independent read-only correction audit. Reads local files, ASTs and immutable Git objects only; does not import/execute candidate code or perform downloads/model/native operations.',
    'checks': checks, 'errors': [], 'source_binding_count': len(new['source_files']),
    'unchanged_other_source_count': len(before) - len(changed),
    'changed_execution_sources': changed, 'changed_functions': changed_functions,
    'unchanged_helper_function_count': sum(original.get(name) == candidate.get(name) for name in original.keys() & candidate.keys()),
    'unchanged_policy_blocks': policy,
    'identities': {path: identity(REPO / path) for path in EXPECTED},
    'owner_control_result': identity(owner_controls),
    'test_scope': 'Owner result independently bound and source inspected; no duplicate test execution in this review.',
}
destination = OUT / 'correction-binding-audit.json'
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'path': str(destination), 'sha256': digest(destination.read_bytes()), 'checks': len(checks), 'errors': []}))

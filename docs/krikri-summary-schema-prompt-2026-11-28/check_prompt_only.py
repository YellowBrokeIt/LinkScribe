"""Source-only proof of the one prompt correction; no native or app call."""
import ast
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREVIOUS = ROOT/'docs/krikri-summary-screen-2026-11-28'
OLD_MANIFEST = 'be5bbd6ad8ac62fced8eb072c2fd8c4847db7e74e38b80fb9c396e9ac5a6847a'
REPLACEMENTS = {
    'JSON only: {"summary":"concise factual summary","key_points":["point"],"chapter_title":"short topical title"}.':
        'Return only JSON matching the supplied schema.',
    'JSON only: {"notes":"concise factual notes","chapter_title":"short topical title"}.':
        'Return only JSON with the string fields `notes` and `chapter_title`.',
    'JSON only: {"summary":"concise factual summary","key_points":["point"]}.':
        'Return only JSON matching the supplied schema.',
}
REUSED_FILES = [
    'source-cases.json', 'review-criteria.json', 'enhancements-production.py',
    'protocol.py', 'native_preflight.py', 'native_session.py', 'prepare_native.py',
    'infer_native.py', 'resource_monitor.py', 'run_native.py', 'request_contract.py',
    'test_protocol.py', 'native-preflight-layout-only.patch',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    assert sha(PREVIOUS/'evidence-manifest.json') == OLD_MANIFEST
    previous = json.loads((PREVIOUS/'evidence-manifest.json').read_text(encoding='utf-8'))
    for item in previous['files']:
        source = PREVIOUS/item['path']
        assert source.stat().st_size == item['bytes'] and sha(source) == item['sha256']
    old = ast.parse((PREVIOUS/'enhancements-context4096.py').read_text(encoding='utf-8'))
    expected = copy.deepcopy(old)
    counts = dict.fromkeys(REPLACEMENTS, 0)
    for node in ast.walk(expected):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for before, after in REPLACEMENTS.items():
                counts[before] += node.value.count(before)
                node.value = node.value.replace(before, after)
    assert all(count == 1 for count in counts.values())
    actual = ast.parse((HERE/'enhancements-context4096.py').read_text(encoding='utf-8'))
    assert ast.dump(actual) == ast.dump(expected), 'Unexpected non-prompt application change'
    assert all((HERE/name).read_bytes() == (PREVIOUS/name).read_bytes() for name in REUSED_FILES)
    old_context = (PREVIOUS/'context.py').read_text(encoding='utf-8')
    assert old_context.replace('/linkscribe-krikri-runtime/summary-screen',
                               '/linkscribe-krikri-runtime/summary-schema-prompt') == (HERE/'context.py').read_text(encoding='utf-8')
    old_requests = json.loads((PREVIOUS/'expected-requests.json').read_text(encoding='utf-8'))
    new_requests = json.loads((HERE/'expected-requests.json').read_text(encoding='utf-8'))
    assert len(old_requests) == len(new_requests) == 2
    direct_before = next(iter(REPLACEMENTS))
    cases = []
    for original, candidate in zip(old_requests, new_requests):
        expected_request = copy.deepcopy(original)
        old_system = original['request']['messages'][0]['content']
        assert old_system.count(direct_before) == 1
        expected_request['request']['messages'][0]['content'] = old_system.replace(direct_before, REPLACEMENTS[direct_before])
        assert candidate == expected_request, 'Source/schema/settings/control or unrelated prompt changed'
        cases.append({'id': candidate['id'], 'only_changed_path': 'request.messages[0].content',
                      'old_system_sha256': hashlib.sha256(old_system.encode('utf-8')).hexdigest(),
                      'new_system_sha256': hashlib.sha256(candidate['request']['messages'][0]['content'].encode('utf-8')).hexdigest(),
                      'complete_user_source_unchanged': True, 'schema_options_model_control_unchanged': True,
                      'timestamped_excerpt_bytes': candidate['timestamped_excerpt_bytes']})
    return {
        'schema_version': 1, 'passed': True, 'original_rejected_manifest_sha256': OLD_MANIFEST,
        'original_manifest_files_verified': len(previous['files']),
        'candidate_adapter_sha256': sha(HERE/'enhancements-context4096.py'),
        'entire_adapter_ast_matches_only_three_example_value_replacements': True,
        'long_note_reduction_prompt_unchanged': True,
        'all_schema_grounding_language_chunking_validation_unload_logic_unchanged': True,
        'reused_files': {name: sha(HERE/name) for name in REUSED_FILES},
        'context_only_change': 'New private log directory; phase/review/budget behavior unchanged.',
        'request_capture_sha256': sha(HERE/'expected-requests.json'), 'cases': cases,
        'new_native_model_tokenizer_detector_or_network_calls': 0,
        'original_english_rejection_or_greek_unrun_status_changed': False,
        'scope': 'Source-only comparison. No evidence yet that removing example values repairs either material English error.',
    }


if __name__ == '__main__':
    output = HERE/'prompt-only-verification.json'
    if output.exists():
        raise ValueError('Refusing to overwrite a frozen source-only check.')
    result = verify()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'cases': len(result['cases']), 'native_calls': 0,
                      'sha256': sha(output)}))

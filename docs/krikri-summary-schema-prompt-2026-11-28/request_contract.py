"""Capture real app summary requests with a blocked transport and no model calls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
MODEL = 'linkscribe-krikri-8b-q4km:20261128'


def load_adapter():
    spec = importlib.util.spec_from_file_location('isolated_summary_adapter', HERE/'enhancements-context4096.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapturedRequest(BaseException):
    """Stop before any native transport or synthetic summary result exists."""


def forbidden_network(*args, **kwargs):
    raise AssertionError('Network/native calls are forbidden during request capture.')


def capture_case(case):
    module = load_adapter()
    records = []
    source = copy.deepcopy(case['segments'])
    chunks = module._summary_source_chunks(source)
    if len(chunks) != 1:
        raise ValueError('The fixed source no longer uses the direct summary path.')
    excerpt = module._summary_excerpt(chunks[0])
    expected_excerpt = '\n'.join(f"[{s['start']:.1f}s] {s['text']}" for s in source)
    if excerpt != expected_excerpt:
        raise ValueError('The direct summary excerpt omitted or changed original source text.')

    def capture(endpoint, payload=None, timeout=1.5):
        if endpoint != '/api/chat':
            raise AssertionError('Unexpected app endpoint during capture.')
        control = module.is_ollama_control_request(payload)
        records.append({'kind': 'control' if control else 'inference',
                        'request': copy.deepcopy(payload), 'timeout_seconds': timeout})
        if control:
            return {'done': True, 'done_reason': 'unload'}
        raise CapturedRequest()

    module.local_ollama_json = capture
    env = {'LINKSCRIBE_OLLAMA_MODEL': MODEL, 'LINKSCRIBE_OLLAMA_THREADS': '4',
           'LINKSCRIBE_OLLAMA_URL': 'http://127.0.0.1:11434'}
    with patch.dict(os.environ, env), patch.object(socket.socket, 'connect', forbidden_network), \
            patch.object(socket.socket, 'connect_ex', forbidden_network), \
            patch.object(socket, 'create_connection', forbidden_network):
        old_retain = os.environ.pop('LINKSCRIBE_OLLAMA_RETAIN_MODELS', None)
        try:
            try:
                module.summarize_segments(source, source_language=case['source_language'])
            except CapturedRequest:
                pass
            else:
                raise AssertionError('The capture did not stop before native transport.')
        finally:
            if old_retain is not None:
                os.environ['LINKSCRIBE_OLLAMA_RETAIN_MODELS'] = old_retain
    calls = [r for r in records if r['kind'] == 'inference']
    controls = [r for r in records if r['kind'] == 'control']
    if len(calls) != 1 or len(controls) != 1 or source != case['segments']:
        raise AssertionError('The single-call/source/cleanup capture contract changed.')
    if calls[0]['request']['messages'][1]['content'] != expected_excerpt or calls[0]['timeout_seconds'] != 240:
        raise AssertionError('The real app request changed the source excerpt or transport limit.')
    return {'id': case['id'], 'request': calls[0]['request'], 'timeout_seconds': 240,
            'source_segments': len(source), 'source_unchanged': True,
            'timestamped_excerpt_bytes': len(excerpt.encode('utf-8')),
            'timestamped_excerpt_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest(),
            'capture_only': True, 'native_calls': 0, 'model_loads': 0,
            'captured_cleanup_request': controls[0]}


def main():
    output = HERE/'expected-requests.json'
    if output.exists():
        raise ValueError('Refusing to overwrite frozen request capture.')
    cases = json.loads((HERE/'source-cases.json').read_text(encoding='utf-8'))
    records = [capture_case(case) for case in cases]
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'requests': len(records), 'native_calls': 0, 'model_loads': 0,
                      'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()

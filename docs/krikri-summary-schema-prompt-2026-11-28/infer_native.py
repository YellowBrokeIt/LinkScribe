"""One independently gated direct application summary; never queue the next case."""
import argparse
import copy
import json
import os
import signal
import time
from unittest.mock import patch

from context import HERE, ROOT, common, read_json, read_plan, authorize, utc
from native_session import native_session, observed_preflight
from protocol import CASE_IDS, SUMMARY_CHECKS, native_response_checks, raw_summary_matches_schema
from request_contract import load_adapter


def summarize_one(case, request, preflight, report, checkpoint):
    """Observe the existing transport; do not replace parsing or summary behavior."""
    module = load_adapter()
    original_transport = module.local_ollama_json
    source = copy.deepcopy(case['segments'])
    report['source_segments'] = copy.deepcopy(source)
    report['requests'] = []
    report['application_result'] = None
    report['raw_summary_object'] = None
    report['checks'] = dict.fromkeys(sorted(SUMMARY_CHECKS), False)
    started = time.monotonic()

    def observed_transport(endpoint, payload=None, timeout=1.5):
        control = module.is_ollama_control_request(payload)
        entry = {'kind': 'control' if control else 'inference', 'endpoint': endpoint,
                 'request': copy.deepcopy(payload), 'timeout_seconds': timeout,
                 'response_json': None, 'raw_evidence_available': False}
        report['requests'].append(entry)
        checkpoint()
        if endpoint != '/api/chat':
            raise ValueError('Unexpected application endpoint during the fixed summary phase.')
        if control:
            controls = [r for r in report['requests'] if r['kind'] == 'control']
            expected = request['captured_cleanup_request']
            if len(controls) != 1 or payload != expected['request'] or timeout != expected['timeout_seconds']:
                raise ValueError('Unexpected summary unload request or attempt count.')
        else:
            if (report['generation_calls'] != 0 or payload != request['request']
                    or timeout != request['timeout_seconds'] or timeout != 240):
                raise ValueError('Actual summary request differs from the frozen single full-source request.')
            report['generation_calls'] += 1
            entry['native_attempt_checkpointed'] = True
            checkpoint()
        call_started = time.monotonic()
        try:
            response = original_transport(endpoint, payload, timeout=timeout)
            # Preserve the entire returned envelope and exact content string before
            # the app parses/validates the model's JSON. No repair is performed.
            entry['response_json'] = json.dumps(response, ensure_ascii=True, allow_nan=True)
            entry['raw_evidence_available'] = True
            entry['raw_scope'] = 'Complete parsed native envelope, serialized before application content validation; not HTTP wire bytes.'
            checkpoint()
            return response
        except BaseException as error:
            entry['error'] = {'type': type(error).__name__, 'message': str(error)}
            if isinstance(error, json.JSONDecodeError):
                entry['unparsed_response_text'] = error.doc
                entry['raw_evidence_available'] = True
            raise
        finally:
            entry['elapsed_seconds'] = time.monotonic() - call_started
            checkpoint()

    module.local_ollama_json = observed_transport
    env = {'LINKSCRIBE_OLLAMA_MODEL': request['request']['model'], 'LINKSCRIBE_OLLAMA_THREADS': '4',
           'LINKSCRIBE_OLLAMA_URL': 'http://127.0.0.1:11434'}
    with patch.dict(os.environ, env):
        retain = os.environ.pop('LINKSCRIBE_OLLAMA_RETAIN_MODELS', None)
        try:
            report['application_result'] = module.summarize_segments(source, source_language=case['source_language'])
        except BaseException as error:
            report['application_error'] = {'type': type(error).__name__, 'message': str(error)}
        finally:
            module.local_ollama_json = original_transport
            if retain is not None:
                os.environ['LINKSCRIBE_OLLAMA_RETAIN_MODELS'] = retain
            checkpoint()

    calls = [r for r in report['requests'] if r['kind'] == 'inference']
    controls = [r for r in report['requests'] if r['kind'] == 'control']
    checks = report['checks']
    checks['one_exact_declared_request'] = len(calls) == 1 and calls[0]['request'] == request['request']
    checks['request_timeout_240s'] = len(calls) == 1 and calls[0]['timeout_seconds'] == 240
    checks['original_source_unchanged'] = source == case['segments']
    response = json.loads(calls[0]['response_json']) if len(calls) == 1 and calls[0]['response_json'] else {}
    checks.update(native_response_checks(response, preflight['prompt_tokens']))
    try:
        raw = module._strict_model_json(response.get('message', {}).get('content', ''))
        report['raw_summary_object'] = raw
        checks['strict_raw_summary_schema'] = raw_summary_matches_schema(raw)
        if checks['strict_raw_summary_schema']:
            expected_projection = {
                'summary': raw['summary'].strip(), 'key_points': [p.strip() for p in raw['key_points']],
                'chapters': [{'start': case['segments'][0]['start'],
                              'title': module._summary_title(raw, case['source_language'])}],
            }
            report['application_projection_scope'] = 'Unchanged app edge trimming and existing chapter-title limit/fallback; raw title remains separately retained.'
            checks['application_projection_exact'] = report['application_result'] == expected_projection
    except (ValueError, TypeError, KeyError, module.EnhancementError) as error:
        report['raw_schema_error'] = {'type': type(error).__name__, 'message': str(error)}
    checks['application_result_accepted'] = report['application_result'] is not None and 'application_error' not in report
    chapters = (report['application_result'] or {}).get('chapters', [])
    checks['authentic_single_chapter_start'] = (len(chapters) == 1
                                               and chapters[0]['start'] == case['segments'][0]['start'])
    if len(controls) == 1 and controls[0]['response_json']:
        control_response = json.loads(controls[0]['response_json'])
        checks['one_exact_unload_acknowledged'] = (
            controls[0]['request'] == request['captured_cleanup_request']['request']
            and control_response.get('done') is True and control_response.get('done_reason') == 'unload')
    report['resident_after_unload'] = common.api('/api/ps')
    checks['resident_models_empty'] = report['resident_after_unload'].get('models') == []
    report['case_elapsed_seconds'] = time.monotonic() - started
    checks['case_below_600s'] = report['case_elapsed_seconds'] <= 600
    report['structural_pass'] = set(checks) == SUMMARY_CHECKS and all(value is True for value in checks.values())
    checkpoint()
    if not report['structural_pass']:
        raise ValueError('The fixed summary failed its execution/schema/native/source/cleanup contract; no retry or next case is allowed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('english', 'greek'), required=True)
    phase = parser.parse_args().phase
    plan = read_plan()
    authorize(phase)
    output = HERE/(phase + '.json')
    if output.exists():
        raise ValueError('Refusing to repeat or overwrite a summary case.')
    index = 0 if phase == 'english' else 1
    case = read_json(HERE/'source-cases.json')[index]
    request = read_json(HERE/'expected-requests.json')[index]
    prepared = read_json(HERE/'prepare.json')
    if case['id'] != CASE_IDS[index] or request['id'] != case['id'] or prepared['prompts'][index]['id'] != case['id']:
        raise ValueError('The original case/request/preflight order changed.')
    started = time.monotonic()
    report = {'schema_version': 1, 'phase': phase, 'id': case['id'], 'started_at': utc(),
              'complete': False, 'structural_pass': False, 'generation_calls': 0,
              'native_create_calls': 0, 'model_downloads': 0,
              'plan_sha256': common.sha(HERE/'plan.json'),
              'authorization_sha256': common.sha(HERE/(phase + '-authorization.json')),
              'native_setup_freeze_sha256': common.sha(HERE/'native-setup-freeze.json'),
              'semantic_quality': 'unreviewed', 'next_case_automatically_queued': False}
    checkpoint = lambda: common.save(output, report)
    checkpoint()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('External supervisor stopped inference.')))
    try:
        with native_session(plan, phase, report, checkpoint) as process:
            if report['cache'] != prepared['cache']:
                raise ValueError('Actual imported package differs from the reviewed summary setup.')
            preflight = observed_preflight(request['request'], case, process, plan, report['header'], report, checkpoint)
            report['preflight'] = preflight
            checkpoint()
            for key in ('request', 'rendered_prompt', 'tokens', 'prompt_tokens', 'layout', 'tokenize_add_special'):
                if preflight[key] != prepared['prompts'][index][key]:
                    raise ValueError('The actual full native prompt differs from reviewed preparation: ' + key)
            common.event('initialized', phase=phase, prompt_tokens=preflight['prompt_tokens'])
            common.event('case_start', id=case['id'], prompt_tokens=preflight['prompt_tokens'])
            summarize_one(case, request, preflight, report, checkpoint)
            report['complete'] = True
            common.event('case_complete', id=case['id'], structural_pass=True, semantic_quality='unreviewed')
    except BaseException as error:
        report['complete'] = False
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        common.event('case_failed', id=case['id'], error=report['error'])
    finally:
        report['finished_at'] = utc()
        report['elapsed_seconds'] = time.monotonic() - started
        report['frozen_inputs_unchanged'] = all(common.sha(ROOT/p) == h for p, h in plan['source_sha256'].items())
        report['complete'] &= report['frozen_inputs_unchanged'] and report.get('owned_daemon_stopped', False)
        checkpoint()
    common.event('phase_complete', phase=phase, complete=report['complete'], error=report.get('error'))
    return int(not report['complete'])


if __name__ == '__main__':
    raise SystemExit(main())

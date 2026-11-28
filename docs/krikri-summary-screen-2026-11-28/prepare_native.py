"""Explicitly authorized zero-generation preparation of both full summary requests."""
import signal
import time

from context import HERE, ROOT, common, read_json, read_plan, authorize, utc
from native_session import native_session, observed_preflight
from protocol import CASE_IDS


def main():
    plan = read_plan()
    authorize('prepare')
    output = HERE / 'prepare.json'
    if output.exists():
        raise ValueError('Refusing to repeat or overwrite native summary preparation.')
    started = time.monotonic()
    report = {'schema_version': 1, 'phase': 'prepare', 'started_at': utc(), 'complete': False,
              'generation_calls': 0, 'native_create_calls': 0, 'model_downloads': 0, 'prompts': [],
              'plan_sha256': common.sha(HERE/'plan.json'),
              'authorization_sha256': common.sha(HERE/'prepare-authorization.json')}
    checkpoint = lambda: common.save(output, report)
    checkpoint()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('External supervisor stopped preparation.')))
    try:
        cases = read_json(HERE/'source-cases.json')
        expected = read_json(HERE/'expected-requests.json')
        if [c['id'] for c in cases] != list(CASE_IDS) or [r['id'] for r in expected] != list(CASE_IDS):
            raise ValueError('Complete original two-case request order changed.')
        with native_session(plan, 'prepare', report, checkpoint) as process:
            for case, request in zip(cases, expected):
                value = observed_preflight(request['request'], case, process, plan, report['header'], report, checkpoint)
                report['prompts'].append(value)
                checkpoint()
                if len(report['prompts']) == 1:
                    common.event('initialized', phase='prepare', generation_calls=0)
                    common.event('case_start', id='summary-render-only', generation_calls=0)
            report['unload_response'] = common.api('/api/chat', {
                'model': plan['model']['local_name'], 'messages': [], 'keep_alive': 0, 'stream': False})
            report['resident_after_unload'] = common.api('/api/ps')
            if (report['unload_response'].get('done') is not True
                    or report['unload_response'].get('done_reason') != 'unload'
                    or report['resident_after_unload'].get('models') != []):
                raise ValueError('Render-only summary preparation did not unload cleanly.')
            report['complete'] = True
            common.event('case_complete', id='summary-render-only', generation_calls=0,
                         prompt_token_counts=[p['prompt_tokens'] for p in report['prompts']])
    except BaseException as error:
        report['complete'] = False
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        report['finished_at'] = utc()
        report['elapsed_seconds'] = time.monotonic() - started
        report['frozen_inputs_unchanged'] = all(common.sha(ROOT/p) == h for p, h in plan['source_sha256'].items())
        report['complete'] &= report['frozen_inputs_unchanged'] and report.get('owned_daemon_stopped', False)
        checkpoint()
    common.event('phase_complete', phase='prepare', complete=report['complete'], error=report.get('error'))
    return int(not report['complete'])


if __name__ == '__main__':
    raise SystemExit(main())

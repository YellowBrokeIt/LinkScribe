"""Owned, existing-model-only native session; no action occurs on import."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from context import BASE, PRIVATE, common, cache_identity, read_json, stop_daemon, storage_reserve
from native_preflight import native_preflight


def observed_preflight(body, case, process, plan, header, report, checkpoint):
    """Retain every actual render/token response before preflight may reject it."""
    trace = {'id': case['id'], 'complete': False, 'calls': []}
    report.setdefault('preflight_attempts', []).append(trace)
    checkpoint()
    original_api = common.api
    def observe(path, payload=None, timeout=10, port=11434):
        call = {'path': path, 'payload': payload, 'timeout_seconds': timeout, 'port': port,
                'response_json': None}
        trace['calls'].append(call)
        checkpoint()
        started = time.monotonic()
        try:
            response = original_api(path, payload, timeout=timeout, port=port)
            call['response_json'] = json.dumps(response, ensure_ascii=True, allow_nan=True)
            checkpoint()
            return response
        except BaseException as error:
            call['error'] = {'type': type(error).__name__, 'message': str(error)}
            if isinstance(error, json.JSONDecodeError):
                call['unparsed_response_text'] = error.doc
            raise
        finally:
            call['elapsed_seconds'] = time.monotonic() - started
            checkpoint()
    common.api = observe
    try:
        result = native_preflight(body, case, process, plan, header)
        trace['complete'] = True
        checkpoint()
        return result
    except BaseException as error:
        trace['error'] = {'type': type(error).__name__, 'message': str(error)}
        checkpoint()
        raise
    finally:
        common.api = original_api


def parameter_mapping(display):
    """Compare unordered displayed keys, retaining exact ordered stop strings."""
    expected_keys = {'num_ctx', 'temperature', 'top_p', 'stop'}
    result = {'stop': []}
    for line in display.splitlines():
        if not line.strip():
            continue
        key, text = line.split(maxsplit=1)
        if key not in expected_keys:
            raise ValueError('Unexpected displayed native parameter: ' + key)
        value = json.loads(text)
        if key == 'stop':
            if not isinstance(value, str):
                raise ValueError('Native stop value is not a string.')
            result['stop'].append(value)
        else:
            if key in result or type(value) not in (int, float) or (key == 'num_ctx' and type(value) is not int):
                raise ValueError('Duplicate or invalid numeric native parameter: ' + key)
            result[key] = value
    if set(result) != expected_keys or not result['stop']:
        raise ValueError('A required native parameter is missing.')
    return result


@contextmanager
def native_session(plan, phase, report, checkpoint):
    """Keep the daemon inside the externally monitored worker process group."""
    process = None
    report['owned_daemon_stopped'] = False
    runtime = Path(plan['storage']['owned_runtime_directory'])
    try:
        report['free_disk_before_bytes'] = storage_reserve()
        common.verify_blob(runtime, plan)
        prepared = read_json(BASE / 'prepare.json')
        report['header'] = prepared['header']
        report['cache'] = cache_identity(runtime, plan)
        if report['cache'] != prepared['cache']:
            raise ValueError('The exact baseline native package changed.')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 11434))
        PRIVATE.mkdir(parents=True, exist_ok=True)
        fd = os.open(PRIVATE / (phase + '-daemon-private.log'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as log:
            process = subprocess.Popen(
                [str(Path(plan['runtime']['directory']) / 'bin/ollama'), 'serve'],
                env=common.daemon_environment(runtime), stdout=log, stderr=subprocess.STDOUT,
                start_new_session=False)
            report['owned_daemon_pid'] = process.pid
            checkpoint()
            report['runtime'] = common.ready(process)
            if report['runtime'].get('version') != plan['runtime']['version']:
                raise ValueError('The actual native runtime version changed.')
            report['show'] = common.api('/api/show', {'model': plan['model']['local_name']})
            report['native_parameter_mapping'] = parameter_mapping(report['show']['parameters'])
            if (report['show']['template'] != prepared['show']['template']
                    or report['show'].get('system', '')
                    or report['native_parameter_mapping'] != plan['native_setup']['import_parameters']):
                raise ValueError('The native template, parameters, stops or absent persona changed.')
            checkpoint()
            yield process
    finally:
        if process is not None:
            try:
                report['owned_daemon_stopped'] = stop_daemon(process) and process.poll() is not None
                report['owned_daemon_exit_code'] = process.returncode
            except BaseException as error:
                report['daemon_cleanup_error'] = {'type': type(error).__name__, 'message': str(error)}
                report['owned_daemon_stopped'] = False
        checkpoint()

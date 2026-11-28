"""Isolated summary-stage paths and exact existing native-runtime bindings."""
from datetime import datetime, timezone
import json
import importlib.metadata
from pathlib import Path
import platform
import shutil
import sys

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'docs/krikri-screen-2026-11-28'
sys.path.insert(0, str(BASE))
import staging as baseline
from native_verify import cache_identity
from protocol import verify_authorization, verify_english_acceptance, remaining_seconds

common = baseline.common
PRIVATE = Path('/workspace/scratch/94360995dd61/linkscribe-krikri-runtime/summary-schema-prompt')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_plan():
    baseline.read_plan()
    path = HERE / 'plan.json'
    if common.sha(path) != (HERE / 'plan.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('The preparation plan changed.')
    plan = read_json(path)
    for rel, expected in plan['source_sha256'].items():
        if common.sha(ROOT / rel) != expected:
            raise ValueError('Frozen summary source changed: ' + rel)
    if plan['model'] != read_json(BASE/'plan.json')['model']:
        raise ValueError('The frozen native model changed.')
    if (Path(sys.executable).absolute() != Path(plan['python_runtime']['executable']).absolute()
            or platform.python_version() != plan['python_runtime']['version']
            or importlib.metadata.version('psutil') != plan['python_runtime']['psutil']):
        raise ValueError('The declared existing Python/observer runtime changed.')
    return plan


def verify_bound_files(value):
    for relative, expected in value['files_sha256'].items():
        if common.sha(ROOT / relative) != expected:
            raise ValueError('An execution-gate file changed: ' + relative)


def authorize(phase):
    """All authorization artifacts must be supplied by root after independent review."""
    path = HERE / (phase + '-authorization.json')
    value = read_json(path)
    if common.sha(path) != (HERE/(phase + '-authorization.sha256')).read_text(encoding='utf-8').strip():
        raise ValueError('Phase authorization identity changed.')
    review = ROOT / value['independent_review_path']
    verify_authorization(value, phase, common.sha(HERE/'plan.json'), common.sha(review))
    verify_bound_files(value)
    if phase in ('english', 'greek'):
        freeze_path = HERE/'native-setup-freeze.json'
        if common.sha(freeze_path) != (HERE/'native-setup-freeze.sha256').read_text(encoding='utf-8').strip():
            raise ValueError('Native setup freeze changed.')
        freeze = read_json(freeze_path)
        if (freeze.get('plan_sha256') != common.sha(HERE/'plan.json')
                or freeze.get('independent_native_review_approved') is not True
                or freeze.get('generation_calls') != 0
                or value.get('native_setup_freeze_sha256') != common.sha(freeze_path)):
            raise ValueError('The independently reviewed zero-generation native setup is missing.')
        if (not isinstance(freeze.get('independent_native_review_path'), str)
                or common.sha(ROOT/freeze['independent_native_review_path']) != freeze.get('independent_native_review_sha256')):
            raise ValueError('The exact independent native review must be bound in the setup freeze.')
        verify_bound_files(freeze)
        if (freeze['files_sha256'].get(str((HERE/'prepare.json').relative_to(ROOT))) != common.sha(HERE/'prepare.json')
                or freeze['files_sha256'].get(str((HERE/'prepare-resources.json').relative_to(ROOT))) != common.sha(HERE/'prepare-resources.json')
                or freeze['files_sha256'].get(str((HERE/'prepare-samples.jsonl').relative_to(ROOT))) != common.sha(HERE/'prepare-samples.jsonl')):
            raise ValueError('The native setup freeze must bind its actual report, resources and full samples.')
    if phase == 'greek':
        decision_path = ROOT/value['english_semantic_decision_path']
        if common.sha(decision_path) != value['english_semantic_decision_sha256']:
            raise ValueError('The independent English decision changed.')
        decision = read_json(decision_path)
        bindings = {
            'plan_sha256': common.sha(HERE/'plan.json'),
            'english_report_sha256': common.sha(HERE/'english.json'),
            'english_resources_sha256': common.sha(HERE/'english-resources.json'),
            'original_review_criteria_sha256': common.sha(HERE/'review-criteria.json'),
            'source_cases_sha256': common.sha(HERE/'source-cases.json'),
        }
        verify_english_acceptance(decision, read_json(HERE/'english.json'),
                                  read_json(HERE/'english-resources.json'), bindings)
    return value


def remaining_budget(phase):
    prior_names = [] if phase == 'prepare' else ['prepare'] if phase == 'english' else ['prepare', 'english']
    reports = []
    for name in prior_names:
        value = read_json(HERE/(name + '-resources.json'))
        if (value.get('plan_sha256') != common.sha(HERE/'plan.json')
                or value.get('phase_report_sha256') != common.sha(HERE/(name + '.json'))
                or value.get('samples_sha256') != common.sha(HERE/(name + '-samples.jsonl'))):
            raise ValueError('A preceding measured phase is not bound to its exact result/samples.')
        reports.append(value)
    return remaining_seconds(reports)


def storage_reserve():
    available = shutil.disk_usage(HERE).free
    if available < 1024 ** 3:
        raise ValueError('The required 1 GiB free disk reserve is unavailable.')
    return available


def stop_daemon(process):
    """Stop this actual daemon/descendants; the outer monitor owns the full group."""
    try:
        parent = psutil.Process(process.pid)
        owned = [parent, *parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        owned = []
    for item in reversed(owned):
        try:
            item.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=3)
    for item in alive:
        try:
            item.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=3)
    process.wait(timeout=3)
    return not [p for p in alive if p.is_running() and p.status() != psutil.STATUS_ZOMBIE]


def utc():
    return datetime.now(timezone.utc).isoformat()

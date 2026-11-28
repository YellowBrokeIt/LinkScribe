"""Measure one explicitly authorized phase; no next phase is launched automatically."""
import argparse
import os
import shutil
import sys

from context import HERE, ROOT, PRIVATE, common, read_json, read_plan, authorize, remaining_budget, storage_reserve
from protocol import PHASES, RSS_BYTES, final_phase_checks
from resource_monitor import monitor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    args = parser.parse_args()
    plan = read_plan()
    authorize(args.phase)
    remaining = remaining_budget(args.phase)
    free_before = storage_reserve()
    output = HERE/(args.phase + '-resources.json')
    samples = HERE/(args.phase + '-samples.jsonl')
    phase_output = HERE/(args.phase + '.json')
    if phase_output.exists():
        raise ValueError('Refusing to repeat a completed or interrupted worker phase.')
    worker = HERE/('prepare_native.py' if args.phase == 'prepare' else 'infer_native.py')
    command = [sys.executable, str(worker)]
    if args.phase != 'prepare':
        command.extend(['--phase', args.phase])
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    limits = {'rss_bytes': RSS_BYTES, 'total_seconds': remaining,
              'initialization_seconds': 180, 'case_seconds': 600}
    report = monitor(command, environment, PRIVATE/(args.phase + '-worker-private.log'),
                     output, samples, limits,
                     {'phase': args.phase, 'plan_sha256': common.sha(HERE/'plan.json'),
                      'worker_sha256': common.sha(worker),
                      'observer_sha256': common.sha(HERE/'resource_monitor.py'),
                      'free_disk_before_bytes': free_before,
                      'shared_total_model_stage_seconds': 900, 'remaining_stage_seconds_at_start': remaining,
                      'whole_app_resource_approval': False})
    report['phase_report_sha256'] = common.sha(phase_output) if phase_output.exists() else None
    try:
        phase_report = read_json(phase_output)
    except (OSError, ValueError):
        phase_report = None
    report['final_contract_errors'] = final_phase_checks(args.phase, report, phase_report, remaining)
    report['frozen_inputs_unchanged'] = all(common.sha(ROOT/p) == h for p, h in plan['source_sha256'].items())
    report['free_disk_after_bytes'] = shutil.disk_usage(HERE).free
    report['disk_reserve_retained'] = report['free_disk_after_bytes'] >= 1024**3
    report['passed'] &= (not report['final_contract_errors'] and report['frozen_inputs_unchanged']
                         and report['disk_reserve_retained'])
    common.save(output, report)
    print({'phase': args.phase, 'passed': report['passed'], 'elapsed_seconds': report['elapsed_seconds'],
           'peak_rss_mib': report['peak_rss_mib'], 'samples': report['sample_count']}, flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())

"""Static hashes/AST and retained-output audit of the final-time correction."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
OLD = ROOT / 'docs/krikri-marker-grammar-controller-2026-11-28'
NEW = ROOT / 'docs/krikri-marker-grammar-controller-v2-2026-11-28'
HERE = Path(__file__).resolve().parent
checks = []
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))
def check(name, passed, detail=None):
    checks.append({'id': name, 'passed': bool(passed), 'detail': detail})

plan = read(NEW / 'plan.json')
old_plan = read(OLD / 'plan.json')
check('new-plan-sidecar', sha(NEW/'plan.json') == (NEW/'plan.sha256').read_text().strip())
for relative, expected in plan['source_sha256'].items():
    path = ROOT / relative
    check('v2-source:' + relative, path.is_file() and not path.is_symlink() and sha(path) == expected)
for directory, label in [(OLD,'preserved-v1'),(NEW,'v2')]:
    for row in read(directory/'evidence-manifest.json')['files']:
        path = directory/row['path']
        check(label+'-manifest:' + row['path'], path.is_file() and not path.is_symlink()
              and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
revision = read(NEW/'revision-record.json')
for name, expected in revision['unchanged_controller_files'].items():
    check('only-monitor-runtime-change:' + name, sha(NEW/name) == expected == sha(OLD/name))
excluded = {'source_sha256','controller_model_free_controls','status','revision'}
check('all-original-phase-identity-budget-fields-unchanged',
      {k:v for k,v in plan.items() if k not in excluded} == {k:v for k,v in old_plan.items() if k not in excluded})
check('previous-review-unchanged', sha(NEW/'independent-v1-review/independent-source-review.json') ==
      'a8bc4707a19078a9ce6655e32023cdb4822a857c22637e251ad2a9451e6002c9')

old_text=(OLD/'resource_monitor.py').read_text();new_text=(NEW/'resource_monitor.py').read_text()
expected=old_text.replace('        report["elapsed_seconds"] = round(time.monotonic() - started, 6)\n        report["finished_at"] = utc()\n','',1)
insert='''        final_elapsed = time.monotonic() - started
        report["elapsed_seconds"] = round(final_elapsed, 6)
        report["finished_at"] = utc()
        report["phase_time_limit_exceeded"] = final_elapsed > limits["total_seconds"]
        if report["phase_time_limit_exceeded"]:
            report["complete"] = False
            report.setdefault("stop_reason", "aggregate_time_limit")
'''
expected=expected.replace('        report["passed"] = (report["complete"] and report["measurement_complete"]',
                          insert+'        report["passed"] = (report["complete"] and report["measurement_complete"]',1)
check('exact-narrow-monitor-delta', expected == new_text)
for name in ['resource_monitor.py','controls/test_finalization.py']:
    ast.parse((NEW/name).read_text(),filename=str(NEW/name));check('static-parse:'+name,True)
check('elapsed-measured-after-final-storage-before-pass',
      new_text.index('report["storage_after_cleanup"] = policy_check()') < new_text.index('final_elapsed = time.monotonic() - started') <
      new_text.index('report["passed"] = (report["complete"] and report["measurement_complete"]'))
controls=read(NEW/'source-control-results.json')
check('retained-57-controls-pass-without-reviewer-rerun', len(controls['checks']) == 57 and controls['passed'] and all(x['passed'] for x in controls['checks']))
paired=read(NEW/'late-finalization-control/result.json')
check('retained-paired-regression-pass', paired['passed'] and paired['v1_false_pass_preserved'] and paired['v2_rejects_same_late_finalization'])
for label,expected_pass in [('v1',True),('v2',False)]:
    row=next(x for x in paired['results'] if x['revision']==label)
    resource_path=NEW/'late-finalization-control'/row['resource_report']['path']
    resource=read(resource_path)
    check('paired-receipt:'+label, sha(resource_path)==row['resource_report']['sha256'] and
          row['actual_passed'] is expected_pass and resource['passed'] is expected_pass and
          resource['elapsed_seconds'] > resource['limits']['total_seconds'] == 1.0 and
          resource['monitor_sha256']==sha((OLD if label=='v1' else NEW)/'resource_monitor.py') and
          resource['worker_exit_code']==0 and resource['owned_processes_stopped'] is True and
          row['cleanup_calls'][0]['cleanup_complete_before_delay'] is True)
    if label=='v2':
        check('final-overrun-now-incomplete', resource['complete'] is False and resource['phase_time_limit_exceeded'] is True
              and resource['stop_reason']=='aggregate_time_limit')
final=read(NEW/'final-source-verification.json')
check('seven-retained-process-control-records',len(final['all_seven_harmless_observer_runs'])==7)
for row in final['all_seven_harmless_observer_runs']:
    path=NEW/row['path']; resource=read(path); sample_path=path.parent/resource['samples_file']
    samples=[json.loads(line) for line in sample_path.read_text().splitlines()]
    check('retained-report-and-sample-hashes:'+row['path'],sha(path)==row['sha256'] and sha(sample_path)==row['samples_sha256']==resource['samples_sha256'])
    check('retained-cleanup-and-complete-accounting:'+row['path'], resource['owned_processes_stopped'] is True and
          resource['measurement_complete'] is True and not resource['measurement_errors'] and len(samples)==resource['sample_count']==row['sample_count'] and
          all(s['rss_bytes']==sum(p['rss_bytes'] for p in s['processes']) and s['pss_bytes']==sum(p['pss_bytes'] for p in s['processes']) for s in samples))
    check('retained-recorded-peaks:'+row['path'], max(s['rss_bytes'] for s in samples)==resource['peak_rss_sample']['rss_bytes'] and
          max(s['pss_bytes'] for s in samples)==resource['peak_pss_sample']['pss_bytes'])
    check('retained-expected-outcome:'+row['path'], resource['passed']==row['passed_phase'] and resource.get('stop_reason')==row['stop_reason'])

out={'schema_version':1,'scope':'Static source/hash/AST plus existing harmless-control outputs; no candidate import/execution or control rerun.',
     'plan_sha256':sha(NEW/'plan.json'),'manifest_sha256':sha(NEW/'evidence-manifest.json'),
     'source_bindings':len(plan['source_sha256']),'v2_manifest_files':len(read(NEW/'evidence-manifest.json')['files']),
     'preserved_v1_manifest_files':len(read(OLD/'evidence-manifest.json')['files']),
     'monitor_sha256':sha(NEW/'resource_monitor.py'),'checks':checks,'passed':all(x['passed'] for x in checks),
     'owned_build_root_exists_at_audit':Path(plan['owned_runtime_root']).exists(),
     'phase_receipts_present_at_audit':[p for p in plan['phases'] if (NEW/(p+'-authorization.json')).exists()],
     'compiler_native_library_converter_tokenizer_model_network_calls':0,'control_reexecutions':0}
(HERE/'source-followup-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
                  'audit_sha256':sha(HERE/'source-followup-audit.json')},ensure_ascii=False))

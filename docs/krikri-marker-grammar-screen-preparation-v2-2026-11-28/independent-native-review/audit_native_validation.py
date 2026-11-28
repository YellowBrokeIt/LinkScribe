"""Read and independently classify all retained grammar probe receipts."""
import hashlib,json,re
from collections import Counter
from pathlib import Path

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
STAGE=ROOT/'docs/krikri-marker-grammar-build-continuation-2026-11-28'
PREP=ROOT/'docs/krikri-marker-grammar-preparation-2026-11-28'
NATIVE=ROOT/'docs/krikri-marker-grammar-native-plan-2026-11-28'
HERE=Path(__file__).resolve().parent
checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check(n,v):checks.append({'id':n,'passed':bool(v)})
def rec(p):
    p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def verify(row,n):
    p=Path(row['path']);check(n,p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']);return p

plan=read(STAGE/'plan.json');report=read(STAGE/'validate.json');resources=read(STAGE/'validate-resources.json');auth=read(STAGE/'validate-authorization.json');claim=read(STAGE/'validate-claim.json')
for label,bindings in [('plan',plan['source_sha256']),('authorization',auth['files_sha256'])]:
    for name,digest in bindings.items():check(label+':'+name,sha(ROOT/name)==digest)
check('exact-root-validation-receipt',sha(STAGE/'validate-authorization.json')==(STAGE/'validate-authorization.sha256').read_text().strip() and auth['root_authorized'] is True and auth['runner_author_self_approval'] is False and auth['generation_authorized'] is False and auth['phase']=='validate' and auth['independent_review_sha256']==sha(ROOT/auth['independent_review_path']))
check('report-resource-claim-source-binding',report['plan_sha256']==resources['plan_sha256']==auth['plan_sha256']==claim['plan_sha256']==sha(STAGE/'plan.json') and
      report['authorization_sha256']==resources['authorization_sha256']==claim['authorization_sha256']==sha(STAGE/'validate-authorization.json') and
      report['claim_sha256']==resources['claim_sha256']==sha(STAGE/'validate-claim.json') and resources['phase_report_sha256']==sha(STAGE/'validate.json') and
      resources['worker_sha256']==sha(STAGE/'phase_worker.py') and resources['observer_sha256']==sha(STAGE/'resource_monitor.py'))
for phase,row in auth['completed_phase_bindings'].items():check('successful-exact-predecessor:'+phase,sha(STAGE/(phase+'.json'))==row['report_sha256'] and sha(STAGE/(phase+'-resources.json'))==row['resources_sha256'] and read(STAGE/(phase+'-resources.json'))['passed'] is True)
native=read(STAGE/'native_prepare.json');native_resources=read(STAGE/'native_prepare-resources.json');built=read(STAGE/'build.json')
check('native-unloaded-before-validator-only-phase',native['owned_daemon_stopped'] is True and native['unload_response']['done_reason']=='unload' and native['resident_after_unload']=={'models':[]} and native_resources['owned_processes_stopped'] is True and native_resources['finished_at']<resources['started_at'])
check('actual-success-without-generation',report['complete'] is True and resources['complete'] is True and resources['passed'] is True and resources['worker_exit_code']==0 and report['generation_calls']==report['network_model_downloads']==report['native_model_loads']==0 and report['semantic_acceptance_or_generation_authorization'] is False)
binary=verify(built['validator'],'same-sanity-checked-binary')
environment=read(NATIVE/'build-command.json')['environment_allowlist'];expected=read(PREP/'native-probe-matrix.json')['probes'];queries=read(PREP/'proposed-native-grammar-queries.json')['queries']
grammars={x['id']:x['grammar'] for x in native['grammars']};observations=[]
check('complete-original-285-probe-order',len(report['probes'])==len(expected)==report['candidate_probe_count']==285 and [x['id'] for x in report['probes']]==[x['id'] for x in expected])

def audit_probe(actual,grammar_id,raw_input,expected_status,label):
    grammar=verify(actual['grammar'],label+':grammar');inp=verify(actual['input'],label+':input');receipt_path=verify(actual['command_receipt'],label+':command');command=read(receipt_path)
    check(label+':same-emitted-grammar',actual['grammar']==grammars[grammar_id])
    check(label+':exact-frozen-input',inp.read_bytes()==raw_input.encode('utf-8'))
    check(label+':exact-validator-command',command['argv']==[str(binary),str(grammar),str(inp)] and command['environment']==environment and command['cwd']==plan['owned_runtime_root'] and command['timeout_seconds']==2 and command['capture_limit_bytes_per_stream']==65536)
    out=verify(command['raw_streams']['stdout'],label+':stdout').read_bytes();err=verify(command['raw_streams']['stderr'],label+':stderr').read_bytes()
    check(label+':bounded-normal-exit',command['complete'] is True and command['exit_code']==0 and command['elapsed_seconds']<=2 and len(out)<=65536 and not err)
    # This is an independent interpretation of the retained CLI text, without
    # importing the candidate status parser or running the validator.
    if out==b'Input string is valid according to the grammar.\n':status='accepted'
    else:
        lines=out.splitlines()
        status='rejected' if len(lines)>=5 and lines[0]==b'Input string is invalid according to the grammar.' and lines[1].startswith(b'Error: ') and lines[2]==b'' and lines[3]==b'Input string:' else 'unrecognized'
    check(label+':raw-status-matches-frozen-expectation',status==expected_status==actual['actual_status']==actual['expected_status'] and actual['matched'] is True)
    value={'id':label,'case_id':grammar_id,'expected_status':expected_status,'actual_raw_status':status,
           'grammar_sha256':actual['grammar']['sha256'],'input_sha256':actual['input']['sha256'],
           'receipt_sha256':actual['command_receipt']['sha256'],'stdout_sha256':hashlib.sha256(out).hexdigest(),
           'stderr_bytes':len(err),'exit_code':command['exit_code'],'elapsed_seconds':command['elapsed_seconds']}
    return value

for i,(actual,probe) in enumerate(zip(report['probes'],expected)):
    observations.append(audit_probe(actual,probe['case_id'],probe['raw_json'],'accepted' if probe['expected_native_acceptance'] else 'rejected',probe['id']))
sentinel=report['sentinel'];q=queries[-1]
sentinel_observation=audit_probe(sentinel,q['id'],q['probe_missing_marker'],'accepted','unsupported-lookahead-gate-sentinel')
check('weak-sentinel-caught-and-excluded-from-candidates',sentinel['weakened_grammar_accepts_missing_marker'] is True and sentinel['enforcement_gate_rejects'] is True and
      q['id']=='unsupported-lookahead-gate-sentinel' and q['id'] not in {x['case_id'] for x in expected} and '<x0/>' not in q['probe_missing_marker'])
counts=Counter(x['actual_raw_status'] for x in observations)
check('285-complete-expected-outcomes',dict(counts)=={'accepted':74,'rejected':211} and report['all_candidate_expectations_match'] is True)
samples_path=STAGE/resources['samples_file'];samples=[json.loads(x) for x in samples_path.read_text().splitlines()]
check('actual-resource-sample-hash-count',sha(samples_path)==resources['samples_sha256'] and len(samples)==resources['sample_count']==292)
check('complete-resource-sums',resources['measurement_complete'] is True and not resources['measurement_errors'] and all(len({p['pid'] for p in x['processes']})==len(x['processes']) and x['rss_bytes']==sum(p['rss_bytes'] for p in x['processes']) and x['pss_bytes']==sum(p['pss_bytes'] for p in x['processes']) for x in samples))
check('sample-chronology-and-peaks',all(a['elapsed_seconds']<=b['elapsed_seconds'] for a,b in zip(samples,samples[1:])) and max(x['rss_bytes'] for x in samples)==resources['peak_rss_sample']['rss_bytes'] and max(x['pss_bytes'] for x in samples)==resources['peak_pss_sample']['pss_bytes'])
check('resource-limits-and-cleanup',resources['owned_processes_stopped'] is True and resources['phase_time_limit_exceeded'] is False and resources['elapsed_seconds']<=resources['limits']['total_seconds']==60 and resources['limits']['case_seconds']==2 and resources['peak_rss_sample']['rss_bytes']<=resources['limits']['rss_bytes']==256*1024**2 and len(resources['cpu_affinity'])==4 and all(x['storage']['violation'] is None for x in samples) and resources['storage_after_cleanup']['violation'] is None and resources['storage_final']['violation'] is None and resources['frozen_inputs_unchanged'] is True)
check('all286-actual-cli-start-finish-events',[x['id'] for x in resources['events'] if x['event']=='case_start']==['candidate-'+str(i) for i in range(285)]+['sentinel-missing-marker'] and [x['id'] for x in resources['events'] if x['event']=='case_complete']==['candidate-'+str(i) for i in range(285)]+['sentinel-missing-marker'])
check('aggregate-time-includes-failed-build-and-every-completed-phase',resources['completed_predecessor_active_seconds']==native_resources['active_aggregate_seconds'] and resources['active_aggregate_seconds']==native_resources['active_aggregate_seconds']+resources['elapsed_seconds'] and resources['active_aggregate_seconds']<=900)
out={'schema_version':1,'scope':'Read-only independent classification of all285 retained native candidate probe outputs plus the separate sentinel; no validator/controller/model execution.',
     'report':rec(STAGE/'validate.json'),'resources':rec(STAGE/'validate-resources.json'),'authorization':rec(STAGE/'validate-authorization.json'),
     'samples':rec(samples_path),'source_bindings':len(plan['source_sha256']),'authorization_bindings':len(auth['files_sha256']),
     'outcome_counts':dict(counts),'probe_observations':observations,'sentinel_observation':sentinel_observation,
     'checks':checks,'passed':all(x['passed'] for x in checks),'reviewer_native_calls':0,'semantic_approval':False}
(HERE/'actual-native-validation-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
                  'audit_sha256':sha(HERE/'actual-native-validation-audit.json')}))

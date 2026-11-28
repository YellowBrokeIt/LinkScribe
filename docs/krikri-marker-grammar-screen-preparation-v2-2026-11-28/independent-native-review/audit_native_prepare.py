"""Read-only actual native prompt/grammar/raw-resource audit; no native calls."""
import hashlib,json,re
from collections import Counter
from pathlib import Path

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
STAGE=ROOT/'docs/krikri-marker-grammar-build-continuation-2026-11-28'
PREP=ROOT/'docs/krikri-marker-grammar-preparation-2026-11-28'
PRIOR=ROOT/'docs/krikri-source-spelling-screen-2026-11-28'
HERE=Path(__file__).resolve().parent
checks=[]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as s:
        while b:=s.read(1024*1024):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check(n,v):checks.append({'id':n,'passed':bool(v)})
def rec(p):
    p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def verify(item,n):
    p=Path(item['path']);check(n,p.is_file() and not p.is_symlink() and p.stat().st_size==item['bytes'] and sha(p)==item['sha256']);return p

plan=read(STAGE/'plan.json');r=read(STAGE/'native_prepare.json');res=read(STAGE/'native_prepare-resources.json');auth=read(STAGE/'native_prepare-authorization.json');claim=read(STAGE/'native_prepare-claim.json')
for label,bindings in [('plan',plan['source_sha256']),('authorization',auth['files_sha256'])]:
    for path,digest in bindings.items():check(label+':'+path,sha(ROOT/path)==digest)
check('root-receipt-and-reserved-slot',sha(STAGE/'native_prepare-authorization.json')==(STAGE/'native_prepare-authorization.sha256').read_text().strip() and
      auth['root_authorized'] is True and auth['runner_author_self_approval'] is False and auth['generation_authorized'] is False and auth['local_model_slot_reserved'] is True and
      auth['independent_review_sha256']==sha(ROOT/auth['independent_review_path']))
check('actual-receipt-claim-source-binding',r['plan_sha256']==res['plan_sha256']==auth['plan_sha256']==claim['plan_sha256']==sha(STAGE/'plan.json') and
      r['authorization_sha256']==res['authorization_sha256']==claim['authorization_sha256']==sha(STAGE/'native_prepare-authorization.json') and
      r['claim_sha256']==res['claim_sha256']==sha(STAGE/'native_prepare-claim.json') and res['phase_report_sha256']==sha(STAGE/'native_prepare.json') and
      res['worker_sha256']==sha(STAGE/'phase_worker.py') and res['observer_sha256']==sha(STAGE/'resource_monitor.py'))
for phase,row in auth['completed_phase_bindings'].items():check('successful-predecessor:'+phase,sha(STAGE/(phase+'.json'))==row['report_sha256'] and sha(STAGE/(phase+'-resources.json'))==row['resources_sha256'] and read(STAGE/(phase+'-resources.json'))['passed'] is True)
check('complete-phase-no-generated-translations',r['complete'] is True and res['complete'] is True and res['passed'] is True and res['worker_exit_code']==0 and r['generation_calls']==r['model_create_import_calls']==r['model_downloads']==r['network_model_downloads']==0)

old=read(PRIOR/'prepare.json');oldplan=read(PRIOR/'plan.json')
check('actual-cache-header-template-preserved',r['cache']==old['cache'] and r['header']==old['header'] and r['show']['template']==old['show']['template'] and not r['show'].get('system'))
params={'stop':[]}
for line in r['show']['parameters'].splitlines():
    if line.strip():
        k,v=line.split(maxsplit=1);v=json.loads(v)
        if k=='stop':params[k].append(v)
        else:params[k]=v
check('actual-native-parameters',params==oldplan['native_setup']['import_parameters'])
check('actual-native-version',r['runtime_version']=={'version':plan['runtime']['version']})
runner=r['bound_runner'];command=runner['command'];owned={x['pid']:x['created'] for x in res['owned_process_identities']}
check('bound-owned-runner-and-thread-context',runner['pid'] in owned and owned[runner['pid']]==runner['created'] and r['daemon_pid'] in owned and
      command[command.index('-c')+1]=='4096' and command[command.index('-t')+1]=='4' and command[command.index('-np')+1]=='1' and
      command[command.index('--host')+1]=='127.0.0.1' and int(command[command.index('--port')+1])==runner['port'] and '--offline' in command and
      not any(x in command for x in ['--mmproj','--spec-draft-model','--spec-type']))
check('actual-runner-binary-and-model-path',sha(runner['executable'])==runner['executable_sha256']==plan['runtime']['files_sha256']['lib/ollama/llama-server'] and
      command[command.index('--model')+1]==str(Path(oldplan['storage']['owned_runtime_directory'])/'models/blobs'/('sha256-'+plan['model']['sha256'])))
for name,digest in plan['runtime']['files_sha256'].items():check('actual-native-binary:'+name,sha(Path(plan['runtime']['directory'])/name)==digest)

calls=r['http_calls'];counts=Counter(x['kind'] for x in calls)
check('exact-call-inventory',dict(counts)==r['request_counts']=={'version':2,'show':1,'render':6,'tokenize':6,'grammar':7,'unload':1,'residents':1} and [x['index'] for x in calls]==list(range(24)))
check('one-retained-startup-readiness-refusal',calls[0]['kind']=='version' and calls[0]['complete'] is False and calls[0]['error']['type']=='URLError' and 'Connection refused' in calls[0]['error']['message'] and 'raw_response' not in calls[0] and all(x['complete'] is True for x in calls[1:]))
for call in calls[1:]:
    raw=verify(call['raw_response'],'raw-http:'+str(call['index'])).read_bytes()
    check('raw-http-json:'+str(call['index']),json.loads(raw)==call['response'] and call['http_status']==200 and len(raw)<=2*1024**2)

requests=read(PREP/'expected-requests.json');queries=read(PREP/'proposed-native-grammar-queries.json')['queries'];cases=read(PRIOR/'protected-source-cases.json')['cases']
renders=[x for x in calls if x['kind']=='render'];tokenizations=[x for x in calls if x['kind']=='tokenize'];grammar_calls=[x for x in calls if x['kind']=='grammar']
prompt_rows=[]
for i,(actual,expected,case,render,tok,previous) in enumerate(zip(r['prompts'],requests,cases,renders,tokenizations,old['prompts'])):
    cid=case['id'];body=expected['request'];text=actual['rendered_prompt'];tokens=actual['tokens'];source=json.loads(body['messages'][1]['content'].split('JSON input: ',1)[1])
    check('complete-prompt-request:'+cid,actual['id']==expected['id']==cid and actual['request']==body and render['request']=={**body,'_debug_render_only':True} and actual['debug_response']==render['response'] and not render['response'].get('message',{}).get('content'))
    check('full-source-and-spelling-message:'+cid,source==[{'id':j,'text':x['text']} for j,x in enumerate(case['segments'])] and actual['rendered_prompt']==previous['rendered_prompt'] and actual['rendered_sha256']==hashlib.sha256(text.encode()).hexdigest())
    check('actual-full-native-vector:'+cid,tok['request']=={'content':text,'add_special':actual['tokenize_add_special'],'parse_special':True} and tok['response']['tokens']==tokens==previous['tokens'] and tok['port']==runner['port'] and all(type(x) is int for x in tokens))
    check('one-bos-complete-budget:'+cid,tokens[0]==128000 and tokens.count(128000)==1 and actual['prompt_tokens']==len(tokens) and len(tokens)+2048+1<=4096 and actual['maximum_output_tokens']==2048 and actual['context_tokens']==4096 and actual['complete_source_segments']==len(case['segments']))
    prompt_rows.append({'id':cid,'tokens':len(tokens),'render_sha256':actual['rendered_sha256'],'token_vector_sha256':hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest()})
check('all-six-prompts-accounted',len(r['prompts'])==len(renders)==len(tokenizations)==len(requests)==6)
grammars=[]
for row,query,call in zip(r['grammars'],queries,grammar_calls):
    grammar=verify(row['grammar'],'actual-grammar:'+row['id']);content=grammar.read_text()
    check('exact-zero-output-query:'+row['id'],row['id']==query['id'] and row['request']==query['request']==call['request'] and row['response_call_index']==call['index'] and row['port']==call['port']==runner['port'] and call['request']['prompt']==[[]] and type(call['request']['n_predict']) is int and call['request']['n_predict']==0)
    check('raw-grammar-response-binding:'+row['id'],set(call['response'])=={'generation_settings/grammar'} and call['response']['generation_settings/grammar']==content and 0<len(content.encode())<=1024**2 and '\0' not in content and re.search(r'(?m)^root\s*::=',content))
    grammars.append({'id':row['id'],**row['grammar']})
check('all-seven-queries-accounted',len(r['grammars'])==len(grammar_calls)==len(queries)==7)
log_path=verify(r['private_daemon_log'],'private-native-log');log=log_path.read_text();log_lines=log.splitlines()
prompt_metrics=re.findall(r'slot print_timing: id\s+0 \| task\s+(\d+) \| prompt eval time =\s+([0-9.]+) ms /\s+(\d+) tokens',log)
generation_metrics=re.findall(r'slot print_timing: id\s+0 \| task\s+(\d+) \|\s+eval time =\s+([0-9.]+) ms /\s+(\d+) tokens',log)
check('actual-log-seven-zero-prompt-and-evaluation-counters',len(prompt_metrics)==len(generation_metrics)==7 and [x[0] for x in prompt_metrics]==[x[0] for x in generation_metrics] and all(float(x[1])==0 and int(x[2])==0 for x in prompt_metrics+generation_metrics))
fallback=[line for line in log_lines if 'accepting any string' in line]
check('only-declared-sentinel-fallback-warning',fallback==r['converter_fallback_diagnostics'] and len(fallback)==1 and 'pattern ^(?=.*<x0/>).*$ is not supported (unsupported group syntax)' in fallback[0])
check('explicit-unload-empty-resident-and-cleanup',r['unload_response']==calls[-2]['response'] and r['unload_response']['done_reason']=='unload' and r['resident_after_unload']==calls[-1]['response']=={'models':[]} and r['owned_daemon_stopped'] is True and r['native_api_builder_restored'] is True and res['owned_processes_stopped'] is True)

samples_path=STAGE/res['samples_file'];samples=[json.loads(x) for x in samples_path.read_text().splitlines()]
check('resource-sample-hash-count',sha(samples_path)==res['samples_sha256'] and len(samples)==res['sample_count']==294)
check('resource-complete-accounting',res['measurement_complete'] is True and not res['measurement_errors'] and all(len({p['pid'] for p in x['processes']})==len(x['processes']) and x['rss_bytes']==sum(p['rss_bytes'] for p in x['processes']) and x['pss_bytes']==sum(p['pss_bytes'] for p in x['processes']) for x in samples))
check('resource-chronology-peaks',all(a['elapsed_seconds']<=b['elapsed_seconds'] for a,b in zip(samples,samples[1:])) and max(x['rss_bytes'] for x in samples)==res['peak_rss_sample']['rss_bytes'] and max(x['pss_bytes'] for x in samples)==res['peak_pss_sample']['pss_bytes'])
check('resource-time-memory-disk-limits',res['phase_time_limit_exceeded'] is False and res['elapsed_seconds']<=res['limits']['total_seconds']==600 and res['peak_rss_sample']['rss_bytes']<=res['limits']['rss_bytes']==6144*1024**2 and len(res['cpu_affinity'])==4 and all(x['storage']['violation'] is None for x in samples) and res['storage_after_cleanup']['violation'] is None and res['storage_final']['violation'] is None and res['frozen_inputs_unchanged'] is True)
initialized=next(x for x in res['events'] if x['event']=='initialized')
check('initialization-time-bound',initialized['observed_elapsed_seconds']<=res['limits']['initialization_seconds']==180)
check('prior-active-time-carried',res['completed_predecessor_active_seconds']==read(STAGE/'build-resources.json')['active_aggregate_seconds'] and res['active_aggregate_seconds']==res['completed_predecessor_active_seconds']+res['elapsed_seconds'] and res['active_aggregate_seconds']<=900)
out={'schema_version':1,'scope':'Independent read-only actual native preparation audit; no model weights rehashed, no candidate/native/compiler/tokenizer/network calls by reviewer.',
     'report':rec(STAGE/'native_prepare.json'),'resources':rec(STAGE/'native_prepare-resources.json'),'authorization':rec(STAGE/'native_prepare-authorization.json'),
     'sample_file':rec(samples_path),'source_bindings':len(plan['source_sha256']),'authorization_bindings':len(auth['files_sha256']),
     'prompt_bindings':prompt_rows,'actual_grammars':grammars,'backend_zero_token_log_evidence':{'log':rec(log_path),'prompt_metrics':prompt_metrics,'generation_metrics':generation_metrics},
     'checks':checks,'passed':all(x['passed'] for x in checks),'actual_grammar_acceptance_not_yet_reviewed':True,'reviewer_native_calls':0}
(HERE/'actual-native-prepare-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
                  'audit_sha256':sha(HERE/'actual-native-prepare-audit.json')}))

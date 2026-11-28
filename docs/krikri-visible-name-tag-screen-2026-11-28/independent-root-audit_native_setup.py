"""Read-only review of exact visible-name runtime preparation; never imports models."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE=Path(__file__).resolve().parent
STAGE=ROOT/'docs/krikri-visible-name-tag-screen-2026-11-28'
PREP=ROOT/'docs/krikri-visible-name-tag-preparation-2026-11-28'
PRIOR=ROOT/'docs/krikri-compact-tag-screen-2026-11-28'
BASE=ROOT/'docs/krikri-screen-2026-11-28'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def check(v,label):
    if not v:raise AssertionError(label)

check(sha(STAGE/'plan.json')=='8878b61813184629abb2ffb4814d250fe85f05e8f2a94be09065c5854e32ac74','runtime plan')
check(sha(STAGE/'native-setup-freeze.json')=='6898861ce1ded9d8233fb123a50b65e39d0340934e63ae5a5d0624d8f6d2128d','native freeze')
plan=read(STAGE/'plan.json');freeze=read(STAGE/'native-setup-freeze.json')
check(len(plan['source_sha256'])==82,'82 plan bindings')
for rel,expected in plan['source_sha256'].items():check(sha(ROOT/rel)==expected,'source '+rel)
for rel,expected in freeze['files_sha256'].items():check(sha(ROOT/rel)==expected,'native freeze '+rel)
for name in ['prepare_native.py','infer_native.py','resource_monitor.py','run_native.py']:
    check((STAGE/name).read_bytes()==(PRIOR/name).read_bytes(),'reviewed runtime unchanged '+name)
check((STAGE/'context.py').read_text()==(PRIOR/'context.py').read_text().replace('linkscribe-krikri-runtime/compact-tag-screen','linkscribe-krikri-runtime/visible-name-tag-screen'),'only private log directory adapted')
for name in ['protection.py','enhancements-context4096.py','expected-requests.json','protection-inputs.json','protected-source-cases.json','development-cases.json']:
    check((STAGE/name).read_bytes()==(PREP/name).read_bytes(),'reviewed visible-name profile copied exactly '+name)
check(sha(STAGE/'development-cases.json')=='48ad72a365a55ec9aff24ef78f6f310d16221d5964e5d6c8e156df6ad9d701ce','unchanged original six')
check(sha(PREP/'evidence-manifest.json')==plan['prepared_visible_profile']['manifest_sha256'],'immutable visible-name preparation')
setup=read(STAGE/'prepare.json');baseline=read(BASE/'prepare.json')
check(setup['complete'] and setup['generation_calls']==setup['native_create_calls']==setup['model_downloads']==0,'complete zero generation')
check(setup['cache']==baseline['cache'] and setup['header']==baseline['header'],'selected native package/header unchanged')
check(setup['current_parameter_mapping']==setup['baseline_parameter_mapping']==plan['native_setup']['import_parameters'],'native context/ordered stops/profile')
check(setup['show']['template']==baseline['show']['template'] and not setup['show'].get('system'),'same native template/no persona')
check(setup['owned_daemon_stopped'] and setup['unload_response']['done'] is True and setup['unload_response']['done_reason']=='unload' and setup['resident_after_unload']=={'models':[]},'native unload/resident cleanup')
requests=read(STAGE/'expected-requests.json');masked=read(STAGE/'protected-source-cases.json')['cases'];estimates=read(PREP/'token-estimates.json')['cases']
check(len(setup['prompts'])==len(requests)==len(masked)==len(estimates)==6,'six complete requests')
rows=[]
for prompt,request,case,estimate in zip(setup['prompts'],requests,masked,estimates):
    check(prompt['id']==request['id']==case['id']==estimate['id'],'source order')
    check(prompt['request']==request['request'],'actual native request exact')
    body=prompt['request'];source_rows=json.loads(body['messages'][1]['content'].split('JSON input: ',1)[1])
    check(source_rows==[{'id':i,'text':s['text']} for i,s in enumerate(case['segments'])],'complete masked source entries')
    check(prompt['rendered_prompt']==estimate['estimated_rendered_prompt'] and prompt['tokens']==estimate['estimated_tokens'],'actual complete native render/vector equals prior estimate')
    check(hashlib.sha256(prompt['rendered_prompt'].encode()).hexdigest()==prompt['rendered_sha256'],'rendered hash')
    check(prompt['debug_response'].get('eval_count',0)==0 and not prompt['debug_response'].get('message',{}).get('content'),'answer-free native render')
    tokens=prompt['tokens'];check(len(tokens)==prompt['prompt_tokens'] and tokens[0]==128000 and tokens.count(128000)==1 and prompt['tokenize_add_special'] is True,'one observed native BOS/count')
    check(len(tokens)+2048+1<=4096,'complete output reserve')
    command=prompt['runner']['command']
    check(command[command.index('-c')+1]=='4096' and command[command.index('-t')+1]=='4' and command[command.index('-np')+1]=='1','actual fixed runner profile')
    check('--offline' in command and plan['model']['sha256'] in command[command.index('--model')+1],'actual exact model path/offline')
    check(prompt['runner']['executable_sha256']==plan['runtime']['files_sha256']['lib/ollama/llama-server'],'actual runner binary')
    rows.append({'id':prompt['id'],'actual_prompt_tokens':len(tokens),'complete_native_tokens_equal_previous_estimate':True,'one_bos':True,'remaining_after2048_and_end':4096-len(tokens)-2048-1})
resources=read(STAGE/'prepare-resources.json');sample_path=STAGE/'prepare-samples.jsonl'
check(sha(sample_path)==resources['samples_sha256'],'sample hash')
samples=[json.loads(s) for s in sample_path.read_text().splitlines()]
check(len(samples)==resources['sample_count']==212,'212 actual samples')
for sample in samples:
    check(len({r['pid'] for r in sample['processes']})==len(sample['processes']),'unique processes')
    check(sum(p['rss_bytes'] for p in sample['processes'])==sample['rss_bytes'],'complete RSS sum')
    check(sum(p['pss_bytes'] for p in sample['processes'])==sample['pss_bytes'],'complete PSS sum')
check(all(a['elapsed_seconds']<=b['elapsed_seconds'] for a,b in zip(samples,samples[1:])),'sample order')
check(max(samples,key=lambda r:r['rss_bytes'])==resources['peak_rss_sample'] and max(samples,key=lambda r:r['pss_bytes'])==resources['peak_pss_sample'],'recorded actual peak samples')
check(resources['phase_report_sha256']==sha(STAGE/'prepare.json'),'phase binding')
check(resources['passed'] and resources['complete'] and resources['measurement_complete'] and not resources['measurement_errors'] and resources['worker_exit_code']==0 and resources['owned_processes_stopped'],'actual complete clean preparation')
check(resources['limits']=={'rss_bytes':6442450944,'total_seconds':600,'initialization_seconds':180,'case_seconds':600},'unchanged setup limits')
check(resources['peak_rss_sample']['rss_bytes']<6442450944 and resources['elapsed_seconds']<180 and len(resources['cpu_affinity'])==4,'observed resource limits')
check(resources['disk_reserve_retained'] and resources['free_disk_after_bytes']>=1024**3,'disk reserve')
report={'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),'audit_passed':True,'plan_sha256':sha(STAGE/'plan.json'),'native_setup_freeze_sha256':sha(STAGE/'native-setup-freeze.json'),'plan_files_verified':82,'native_freeze_files_verified':len(freeze['files_sha256']),'reviewed_runtime_reused_byte_exact_except_private_path':True,'reviewed_corrected_profile_maps_requests_copied_byte_exact':True,'cases':rows,'preparation':{'model_generation_calls':0,'native_create_calls':0,'model_downloads':0,'elapsed_seconds':resources['elapsed_seconds'],'samples':len(samples),'peak_rss_bytes':resources['peak_rss_sample']['rss_bytes'],'peak_pss_bytes':resources['peak_pss_sample']['pss_bytes'],'worker_exit_code':0,'owned_processes_stopped':True,'free_disk_after_bytes':resources['free_disk_after_bytes']},'reviewer_model_tokenizer_native_provider_or_network_calls':0,'audit_script_sha256':sha(Path(__file__))}
p=HERE/'native-setup-audit.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'path':str(p),'sha256':sha(p),'audit_passed':True}))

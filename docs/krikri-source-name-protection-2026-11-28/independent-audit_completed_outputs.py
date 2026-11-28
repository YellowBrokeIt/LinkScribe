"""Inspect retained completed data only; no application or model execution."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE = Path(__file__).resolve().parent
STAGE = ROOT/'docs/krikri-source-name-protection-2026-11-28'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())
def text_sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()
def check(test, label):
    if not test: raise AssertionError(label)

freeze=read(STAGE/'inference-freeze.json')
check(sha(STAGE/'inference-freeze.json')=='43fd6abd4ae20c30d205048269c92cfb45457ade8cb10b1df2ed7b163d696416','frozen inference')
for rel, expected in freeze['files_sha256'].items(): check(sha(ROOT/rel)==expected,'frozen '+rel)
sources=read(HERE/'source-and-criteria-before-output.json')['cases']
requests=read(STAGE/'expected-requests.json')
prepared=read(STAGE/'prepare.json')['prompts']
execution=read(STAGE/'execution.json')
check(execution['generation_calls']==len(execution['cases'])==2 and not execution['complete'],'correct early stop')
check(execution['owned_daemon_stopped'] and execution['frozen_inputs_unchanged'],'worker cleanup')
rows=[]
pattern=re.compile(r'__LSNP_[0-9a-f]{16}_[0-9]{4}_[0-9]{4}__')
for i, entry in enumerate(execution['cases']):
    source=sources[i]; case_id=source['id']
    check(entry['id']==case_id,'original case order')
    for pathkey, hashkey in [('report','sha256'),('preflight_report','preflight_sha256'),('protection_report','protection_report_sha256')]:
        check(sha(STAGE/entry[pathkey])==entry[hashkey],pathkey+' binding')
    report=read(STAGE/entry['report']); result=report['cases'][0]
    protected=read(STAGE/entry['protection_report'])
    preflight=read(STAGE/entry['preflight_report'])
    check(report['complete'] and report['completed_cases']==report['requested_cases']==len(report['cases'])==1,'case evaluation completed')
    check(result['segments']==source['segments'] and protected['source_segments']==source['segments'],'complete original source')
    for key in ['request','rendered_prompt','tokens','prompt_tokens','layout','tokenize_add_special']:
        check(preflight[key]==prepared[i][key],'fresh native preflight '+key)
    calls=[r for r in result['requests'] if r['kind']=='inference']
    controls=[r for r in result['requests'] if r['kind']=='control']
    check(len(calls)==1 and calls[0]['request']==requests[i]['request'] and calls[0]['timeout_seconds']==240,'one exact frozen request')
    raw=json.loads(calls[0]['response_json']); final=raw['message']['content']
    check(raw==json.loads(protected['model_response_json']),'two raw evidence routes agree')
    check(raw['done'] is True and raw['done_reason']=='stop' and not raw['message'].get('thinking'),'normal final stop/no reasoning')
    check(raw['prompt_eval_count']==preflight['prompt_tokens'] and 0<raw['eval_count']<2048,'actual prompt/output counts')
    check(len(controls)==1 and json.loads(controls[0]['response_json'])['done_reason']=='unload','one acknowledged unload')
    check(entry['checks']['resident_models_empty'],'empty native resident list')
    strings=json.loads(final)['translations']
    check(strings==protected['raw_masked_translation_strings'] and protected['strict_raw_schema_accepted'],'retained native strict schema')
    check([s['text'] for s in protected['masked_app_result']]==[s.strip() for s in strings],'only baseline trim before marker gate')
    markers=protected['bundle']['markers']
    exact_counts=[sum(t.count(m['marker']) for t in strings) for m in markers]
    restored=result.get('translation')
    if i==0:
        check(exact_counts==[1] and protected['complete'] and protected['post_restoration_guard_accepted'],'first exact marker acceptance')
        expected=copy.deepcopy(source['segments'])
        for j,text in enumerate(strings):
            for m in markers:
                if m['segment_index']==j: text=text.replace(m['marker'],m['source_text'])
            expected[j]['text']=text.strip()
        check(expected==restored==protected['restored_before_guard']==protected['restored_app_result'],'exact accepted source-only restoration')
        check(all(entry['checks'].values()),'first declared checks')
        altered=[]
    else:
        check(exact_counts==[0]*6 and all(not pattern.search(t) for t in strings),'six expected markers absent')
        check(not protected['complete'] and not protected['exact_source_only_restoration'] and not protected['post_restoration_guard_accepted'],'rejection before restoration')
        check(restored is None and 'restored_app_result' not in protected and 'restored_before_guard' not in protected,'no restored or accepted result')
        check(result['error']==protected['error'] and result['error']['type']=='ValueError','same retained rejection')
        check({k for k,v in entry['checks'].items() if not v}=={'structure_execution_and_guard_accepted','marker_restoration_and_post_guard_accepted'},'only marker/acceptance checks fail')
        altered=[]
        for m in markers:
            matches=re.findall(r'\b[Pp]erson '+re.escape(m['marker'][len('__LSNP_'):-1]),strings[m['segment_index']])
            check(len(matches)==1,'one observed renamed marker suffix in same entry')
            altered.append({'original_exact_marker':m['marker'],'source_name':m['source_text'],'segment_index':m['segment_index'],'observed_corrupt_text':matches[0]})
    rows.append({'id':case_id,'report_sha256':entry['sha256'],'preflight_sha256':entry['preflight_sha256'],'protection_sha256':entry['protection_report_sha256'],'raw_response_json_utf8_sha256':text_sha(calls[0]['response_json']),'raw_final_content_utf8_sha256':text_sha(final),'raw_translation_string_utf8_sha256':[text_sha(s) for s in strings],'restored_translation_string_utf8_sha256':[text_sha(s['text']) for s in restored] if restored is not None else None,'actual_prompt_tokens':raw['prompt_eval_count'],'output_tokens':raw['eval_count'],'exact_expected_marker_counts':exact_counts,'observed_corrupt_markers':altered,'one_normal_generation_and_acknowledged_unload':True,'post_restoration_accepted':bool(protected['post_restoration_guard_accepted'])})
not_run=[]
for source in sources[2:]:
    for suffix in ['.json','-protection.json','-preflight.json']:
        check(not (STAGE/(source['id']+suffix)).exists(),'unrun case artifact absent')
    not_run.append(source['id'])
resources=read(STAGE/'infer-resources.json')
samples_path=STAGE/'infer-samples.jsonl'
check(sha(samples_path)==resources['samples_sha256'],'complete sample file binding')
samples=[json.loads(s) for s in samples_path.read_text().splitlines()]
check(len(samples)==resources['sample_count']==507,'507 samples')
for s in samples:
    check(len({p['pid'] for p in s['processes']})==len(s['processes']),'unique sampled processes')
    check(sum(p['rss_bytes'] for p in s['processes'])==s['rss_bytes'] and sum(p['pss_bytes'] for p in s['processes'])==s['pss_bytes'],'exact resource sums')
check(all(a['elapsed_seconds']<=b['elapsed_seconds'] for a,b in zip(samples,samples[1:])),'sample ordering')
check(max(samples,key=lambda x:x['rss_bytes'])==resources['peak_rss_sample'] and max(samples,key=lambda x:x['pss_bytes'])==resources['peak_pss_sample'],'recorded resource peaks')
check(resources['measurement_complete'] and not resources['measurement_errors'] and resources['owned_processes_stopped'],'complete measurement/cleanup')
check(not resources.get('stop_reason') and resources['worker_exit_code']==1 and not resources['passed'] and not resources['complete'],'honest failed stage outcome')
check(resources['phase_report_sha256']==sha(STAGE/'execution.json'),'execution binding')
check(resources['limits']=={'rss_bytes':6442450944,'total_seconds':1800,'initialization_seconds':180,'case_seconds':600},'unchanged limits')
check(resources['peak_rss_sample']['rss_bytes']<6442450944 and resources['elapsed_seconds']<180 and resources['disk_reserve_retained'],'no resource threshold hit')
out={'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),'audit_complete':True,'audit_passed':True,'candidate_stage_accepted':False,'inference_freeze_sha256':sha(STAGE/'inference-freeze.json'),'frozen_files_verified':len(freeze['files_sha256']),'execution_sha256':sha(STAGE/'execution.json'),'resource_report_sha256':sha(STAGE/'infer-resources.json'),'sample_file_sha256':sha(samples_path),'native_cases_observed':rows,'not_run':not_run,'stop_reason':'First exact-marker corruption; unchanged guard rejected and remaining four cases were not attempted.','resources':{'elapsed_seconds':resources['elapsed_seconds'],'sample_count':len(samples),'peak_rss_bytes':resources['peak_rss_sample']['rss_bytes'],'peak_pss_bytes':resources['peak_pss_sample']['pss_bytes'],'worker_exit_code':1,'owned_processes_stopped':True,'resource_limit_hit':False},'reviewer_model_or_translation_calls':0,'audit_script_sha256':sha(Path(__file__))}
target=HERE/'completed-output-protocol-audit.json'
with target.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'audit_passed':True,'candidate_stage_accepted':False,'path':str(target),'sha256':sha(target)}))

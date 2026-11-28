"""Bind a retrospective semantic review to retained native outputs only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE=Path(__file__).resolve().parent
REPORT=HERE/'artifact/translation-evaluation.json'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def text_sha(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def read(p): return json.loads(p.read_bytes())
def check(v,label):
    if not v: raise AssertionError(label)

check(sha(REPORT)=='0ccc6c2017beece99b3a91b68f2533d1a91cd15ed4374a972a94ff1c4c5d40b9','published report')
report=read(REPORT)
commit=report['source']['git_commit']
check(commit=='d62df26c870f175f7454fe0c3900d97891c8bff5' and report['source']['git_dirty'] is False,'recorded clean source')
source_bytes={}
for relative,expected in report['source']['sha256'].items():
    value=subprocess.run(['git','show',commit+':'+relative],cwd=ROOT,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
    check(hashlib.sha256(value).hexdigest()==expected,'committed source '+relative)
    source_bytes[relative]=value
corpus=json.loads(source_bytes['tests/fixtures/translation_quality_cases.json'])
check(corpus['corpus_version']==report['corpus_version']=='2026-11-26-v1','original corpus version')
check(report['complete'] and report['corpus_complete'] and report['completed_cases']==report['requested_cases']==len(report['cases'])==12,'complete12')
check(report['runtime']['configured_model']=='qwen3:4b' and report['runtime']['ollama_version']=='0.40.12','runtime identity')
check(report['runtime']['model']['digest']=='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7','exact model digest')
rows=[]
for original,case in zip(corpus['cases'],report['cases']):
    check(all(case[k]==v for k,v in original.items()),'all original source/criteria '+case['id'])
    check(all(case['structural_checks'].values()),'recorded structure')
    check(len(case['translation'])==len(case['segments']),'saved segment count')
    calls=[r for r in case['requests'] if r['kind']=='inference']
    controls=[r for r in case['requests'] if r['kind']=='control']
    check(len(calls)==case['request_count'] and len(controls)==case['control_request_count'],'request counts')
    input_rows=[]; output_parts=[]; bindings=[]
    for call in calls:
        request=call['request']
        check(request['model']=='qwen3:4b' and request['options']=={'temperature':0,'num_ctx':8192,'num_predict':2048,'num_thread':4},'native request profile')
        check(request['think'] is False and request['stream'] is False and call['timeout_seconds']==240,'native request limits')
        chunks=json.loads(request['messages'][1]['content'].split('JSON input: ',1)[1])
        response=json.loads(call['response_json'])
        content=response['message']['content']; strings=json.loads(content)['translations']
        check(response['model']=='qwen3:4b','returned model identity')
        check(set(json.loads(content))=={'translations'},'strict result object')
        schema={'type':'object','properties':{'translations':{'type':'array','items':{'type':'string'},'minItems':len(chunks),'maxItems':len(chunks)}},'required':['translations'],'additionalProperties':False}
        check(request['format']==schema,'actual exact response schema')
        check(call['raw_evidence_available'] is True,'raw evidence present')
        check(response['done'] is True and response['done_reason']=='stop' and not response['message'].get('thinking'),'normal final response')
        check(0<response['eval_count']<2048 and response['prompt_eval_count']>0,'bounded final token counts')
        check(len(chunks)==len(strings),'native entry count')
        input_rows.extend(chunks);output_parts.extend(strings)
        bindings.append({'request_json_canonical_sha256':text_sha(json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'))),'response_json_utf8_sha256':text_sha(call['response_json']),'final_content_utf8_sha256':text_sha(content),'input_fragment_utf8_sha256':[text_sha(c['text']) for c in chunks],'raw_translation_string_utf8_sha256':[text_sha(s) for s in strings],'prompt_eval_count':response['prompt_eval_count'],'eval_count':response['eval_count'],'normal_stop':True})
    if len(case['segments'])==1:
        check(all(r['id']==0 for r in input_rows),'long single-original-segment IDs')
        check(''.join(r['text'] for r in input_rows)==case['segments'][0]['text'],'long full source reconstruction')
        check(' '.join(s.strip() for s in output_parts)==case['translation'][0]['text'],'long raw output assembly')
    else:
        check(len(calls)==1 and input_rows==[{'id':i,'text':s['text']} for i,s in enumerate(case['segments'])],'complete short source')
        check([s.strip() for s in output_parts]==[s['text'] for s in case['translation']],'short raw output preservation')
    check(all({k:v for k,v in a.items() if k!='text'}=={k:v for k,v in b.items() if k!='text'} for a,b in zip(case['segments'],case['translation'])),'original segment metadata')
    check(len(controls)==1,'one explicit unload per case')
    for control in controls:
        check(control['request']=={'model':'qwen3:4b','messages':[],'stream':False,'keep_alive':0} and control['timeout_seconds']==5,'exact unload request')
        response=json.loads(control['response_json'])
        check(response['done'] is True and response['done_reason']=='unload','acknowledged control unload')
    rows.append({'id':case['id'],'automatic_status':case['automatic_status'],'source_and_criteria_match_original_commit':True,'complete_source_reconstruction':True,'raw_output_reconstructs_saved_translation':True,'source_segment_utf8_sha256':[text_sha(s['text']) for s in case['segments']],'translated_segment_utf8_sha256':[text_sha(s['text']) for s in case['translation']],'inference_calls':len(calls),'unload_calls':len(controls),'native_call_bindings':bindings})
out={'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),'audit_complete':True,'audit_passed':True,'published_report_path':str(REPORT),'published_report_sha256':sha(REPORT),'published_report_bytes':REPORT.stat().st_size,'report_run_id':report['run_id'],'corpus_version':report['corpus_version'],'source_identity':report['source'],'source_hashes_independently_verified_from_recorded_commit':True,'runtime_identity':report['runtime'],'cases':rows,'inference_calls':sum(r['inference_calls'] for r in rows),'unload_calls':sum(r['unload_calls'] for r in rows),'interpretation':'Integrity and recorded native execution audit only. Semantic judgments are a separate retrospective independent review. The12 cases were previously exposed; no fresh validation is claimed. No actual native render-only context accounting or full-app resource result is inferred from this report.','audit_model_provider_or_network_calls':0,'audit_script_sha256':sha(Path(__file__))}
p=HERE/'published-output-integrity-audit.json'
with p.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'path':str(p),'sha256':sha(p),'inference_calls':out['inference_calls'],'unloads':out['unload_calls'],'audit_passed':True}))

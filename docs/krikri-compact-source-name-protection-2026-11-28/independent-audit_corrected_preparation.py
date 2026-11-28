"""Read-only compact-profile audit plus the exact corrected pure-guard probe."""
import ast
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
HERE=Path(__file__).resolve().parent
STAGE=ROOT/'docs/krikri-compact-source-name-protection-2026-11-28'
PRIOR=ROOT/'docs/krikri-source-name-protection-2026-11-28'
BASE=ROOT/'docs/krikri-screen-2026-11-28'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def check(v,label):
    if not v:raise AssertionError(label)

check(sha(STAGE/'plan.json')=='f4f6affa0fb1f5c0e67343c790e376b51363c3905f6d4dc8950afa4bc8a39847','corrected plan')
plan=read(STAGE/'plan.json')
for rel,expected in plan['source_sha256'].items():check(sha(ROOT/rel)==expected,'bound '+rel)
archive=read(STAGE/'initial-protocol-review/manifest.json')
for row in archive['files']:
    p=STAGE/'initial-protocol-review'/row['path']
    check(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'preserved initial '+row['path'])
check(sha(STAGE/'initial-protocol-review/independent-counterexample/initial-residual-closing-tag-probe.json')==sha(HERE/'initial-residual-closing-tag-probe.json'),'original independent probe retained')
before=(STAGE/'initial-protocol-review/protection.py').read_text()
after=(STAGE/'protection.py').read_text()
replacement='''    # Reserve both opening and closing forms, even if a model inserts spacing.
    # This is rejection-only comparison; no source or output is rewritten.
    return bool(re.search(r"<\\s*/?\\s*x", folded))'''
check(before.replace('    return "<x" in folded',replacement)==after,'only scanner code change')
oldtree=ast.parse((PRIOR/'protection.py').read_text());newtree=ast.parse(after)
names={'canonical','digest','strict_response_strings','restore_segments'}
for name in names:
    a=next(n for n in oldtree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    b=next(n for n in newtree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    check(ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),'unchanged strict function '+name)
instruction=(STAGE/'marker-instruction.txt').read_text().rstrip('\n')
base_adapter=(BASE/'enhancements-context4096.py').read_text()
check(base_adapter.replace('Do not omit or add entries.','Do not omit or add entries.'+instruction)==(STAGE/'enhancements-context4096.py').read_text(),'only generic instruction')
for name in ['marker-instruction.txt','enhancements-context4096.py','protection-inputs.json','protected-source-cases.json','expected-requests.json','token-estimates.json','development-cases.json']:
    check((STAGE/name).read_bytes()==(STAGE/'initial-protocol-review'/name).read_bytes(),'unchanged setup '+name)
controls=read(STAGE/'protection-control-results-v2.json')
check(controls['controls']==len(controls['results'])==29 and all(c['mechanical_passed'] for c in controls['results']),'all29 retained controls')
source=read(STAGE/'development-cases.json')['cases'];maps=read(STAGE/'protection-inputs.json')['cases'];oldmaps=read(PRIOR/'protection-inputs.json')['cases'];requests=read(STAGE/'expected-requests.json');oldrequests=read(BASE/'expected-requests.json');estimated=read(STAGE/'token-estimates.json');native_old=read(PRIOR/'prepare.json')['prompts']
check(len(source)==len(maps)==len(requests)==len(estimated['cases'])==6,'six cases')
rows=[]
for case,row,old,request,oldrequest,estimate,oldprompt in zip(source,maps,oldmaps,requests,oldrequests,estimated['cases'],native_old):
    check(all(v['id']==case['id'] for v in [row,old,request,oldrequest,estimate,oldprompt]),'case order')
    bundle=row['bundle'];joined='\n'.join(s['text'] for s in case['segments'])
    check(bundle['source_segments']==case['segments']==old['bundle']['source_segments'],'full original source')
    check(bundle['normalizer_result']==old['bundle']['normalizer_result'] and row['raw_entities']==old['raw_entities'],'same reviewed actual source mentions')
    check(bundle['source_segments_sha256']==digest(case['segments']),'external original metadata hash')
    check(bundle['source_binding_sha256']==digest({'source':joined,'spans':[{'start':m['global_start'],'end':m['global_end']} for m in bundle['markers']]}),'external source/offset digest')
    check(bundle['protection_binding_sha256']==digest({'source_segments_sha256':bundle['source_segments_sha256'],'masked_segments':bundle['masked_segments'],'markers':bundle['markers']}),'external map digest')
    reconstructed=copy.deepcopy(bundle['masked_segments'])
    for occurrence,m in enumerate(bundle['markers']):
        check(m['marker']==f'<x{occurrence}/>' and m['source_text']==case['segments'][m['segment_index']]['text'][m['start']:m['end']],'exact mention tag/slice')
        check({k:v for k,v in m.items() if k!='marker'}=={k:v for k,v in old['bundle']['markers'][occurrence].items() if k!='marker'},'unchanged mention metadata')
        check(reconstructed[m['segment_index']]['text'].count(m['marker'])==1,'one request-local mention')
        reconstructed[m['segment_index']]['text']=reconstructed[m['segment_index']]['text'].replace(m['marker'],m['source_text'])
    check(reconstructed==case['segments'],'exact source roundtrip')
    body=request['request'];oldbody=oldrequest['request']
    check({k:v for k,v in body.items() if k!='messages'}=={k:v for k,v in oldbody.items() if k!='messages'},'same schema/profile')
    check(body['messages'][0]['content']==oldbody['messages'][0]['content']+instruction,'generic instruction only')
    prefix,jsoninput=body['messages'][1]['content'].split('JSON input: ',1)
    check(prefix==oldbody['messages'][1]['content'].split('JSON input: ',1)[0],'same task language')
    check(json.loads(jsoninput)==[{'id':i,'text':s['text']} for i,s in enumerate(bundle['masked_segments'])],'complete unfragmented request')
    rendered=oldprompt['rendered_prompt']
    for a,b in zip(oldprompt['request']['messages'],body['messages']):rendered=rendered.replace(a['content'],b['content'],1)
    check(rendered==estimate['estimated_rendered_prompt'],'estimated full native wrapper')
    tokens=estimate['estimated_tokens']
    check(len(tokens)==estimate['estimated_prompt_tokens'] and tokens[0]==128000 and tokens.count(128000)==1,'estimated one-BOS count')
    check(len(tokens)+2048+1<=4096,'estimated full output reserve')
    rows.append({'id':case['id'],'exact_source_mentions':len(bundle['markers']),'source_roundtrip_exact':True,'estimated_prompt_tokens':len(tokens),'actual_new_native_count_observed':False})
check(sum(r['exact_source_mentions'] for r in rows)==13,'13 prior-reviewed mentions')
check(all(r['entire_vector_equal'] for r in estimated['prior_vectors_equal']) and len(estimated['prior_vectors_equal'])==6,'recorded full old-native vector checks')
check(all(len(r['tokens'])==3 and all(t<128000 for t in r['tokens']) for r in estimated['tag_tokenizations']),'actual estimated tags are ordinary tokens')

# Rerun only the exact meaningful pure-guard counterexample after its fix.
selected=ast.Module(body=[n for n in newtree.body if isinstance(n,ast.FunctionDef) and n.name in {'canonical','digest','reserved_present','restore_segments'}],type_ignores=[])
scope={'json':json,'hashlib':hashlib,'unicodedata':unicodedata,'copy':copy,'Counter':Counter,'re':re,'PATTERN':re.compile(r'<x(?:0|[1-9][0-9]{0,3})/>')}
exec(compile(selected,str(STAGE/'protection.py'),'exec'),scope)
original=[{'start':0.0,'end':2.0,'text':'Dana arrived.'}];masked=[{'start':0.0,'end':2.0,'text':'<x0/> arrived.'}];markers=[{'marker':'<x0/>','segment_index':0,'start':0,'end':4,'source_text':'Dana'}]
bundle={'source_segments':original,'source_segments_sha256':digest(original),'masked_segments':masked,'markers':markers};bundle['protection_binding_sha256']=digest({'source_segments_sha256':bundle['source_segments_sha256'],'masked_segments':masked,'markers':markers})
error=None
try:scope['restore_segments'](bundle,[{'start':0.0,'end':2.0,'text':'Η <x0/> έφτασε. </x0>'}])
except ValueError as exc:error=str(exc)
check(error=='Translated text contains a malformed or unrecognized marker prefix.','exact prior guard bypass now rejected')
check(scope['reserved_present']('</x0>') and scope['reserved_present']('< / x0 >') and scope['reserved_present']('< x0 />'),'source/spacing namespace rejection')
report={'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),'audit_passed':True,'plan_sha256':sha(STAGE/'plan.json'),'frozen_files_verified':len(plan['source_sha256']),'initial_archive_sha256':sha(STAGE/'initial-protocol-review/manifest.json'),'initial_archive_files_verified':len(archive['files']),'exact_prior_probe_now_rejected':True,'rejection_error':error,'revised_controls':29,'source_mentions':13,'cases':rows,'scope':'No-model preparation review only; actual new native rendering/counts and inference unobserved. The only reviewer execution was standard-library integrity checking and the exact corrected pure-guard regression.','model_tokenizer_native_or_provider_calls_by_reviewer':0,'audit_script_sha256':sha(Path(__file__))}
p=HERE/'corrected-preparation-audit.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'path':str(p),'sha256':sha(p),'audit_passed':True}))

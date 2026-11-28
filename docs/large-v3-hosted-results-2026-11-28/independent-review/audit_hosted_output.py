#!/usr/bin/env python3
"""Read-only standard-library audit of the hosted large-v3 artifact."""
import ast,hashlib,json,math,struct,statistics,types,zipfile
from datetime import datetime,timezone
from pathlib import Path
R=Path('/workspace/scratch/94360995dd61/LinkScribe');D=R/'docs/large-v3-screen-2026-11-28';O=Path(__file__).resolve().parent;H=Path('/workspace/scratch/94360995dd61/large-v3-hosted-73b75b45-2026-11-28');A=H/'artifact'
def sha(data):return hashlib.sha256(data).hexdigest()
def fsha(p):return sha(p.read_bytes())
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def canonical(value):return sha(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
def record(p):return {'bytes':p.stat().st_size,'sha256':fsha(p)}
def npy(path):
 raw=path.read_bytes();assert raw[:6]==b'\x93NUMPY';version=tuple(raw[6:8]);assert version in ((1,0),(2,0));width=2 if version==(1,0) else 4;start=8+width+int.from_bytes(raw[8:8+width],'little');header=ast.literal_eval(raw[8+width:start].decode('latin1').strip());data=raw[start:];assert header['descr']=='<f4' and header['fortran_order'] is False and len(header['shape'])==1 and len(data)==header['shape'][0]*4 and all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',data));return header,data
values=list(range(33,127))+list(range(161,173))+list(range(174,256));chars=values.copy();n=0
for value in range(256):
 if value not in values:values.append(value);chars.append(256+n);n+=1
reverse={chr(c):b for b,c in zip(values,chars)}
def decode(pieces):return bytes(reverse[c] for c in ''.join(pieces)).decode('utf-8')
plan=load(D/'plan.json');r=load(A/'recognizer-report.json');e=load(A/'execution.json');inp=load(A/'input-preparation.json');download=load(A/'model-download.json');pre=load(A/'preflight.json');bound=load(O/'contract-review.json');criteria=load(O/'source-and-criteria-before-output.json')
assert fsha(D/'plan.json')==r['plan_sha256']==e['plan_sha256']==pre['plan_sha256']=='b9b779a48cb265e28c060fbf433d40e54058bb86290decc042e620ec363851f2'
assert r['helper_sha256']==pre['helper_sha256']=='cd7f933b27fc297fcdd0f1901657306ee90d17211ceae16dd0c4d9d23200c451'
assert r['commit']==pre['github_sha']=='73b75b45bf6715627fac94d087ec4be8b93d353b'
assert fsha(O/'source-and-criteria-before-output.json')==bound['criteria']['sha256']=='e57ce6808f6315656c6e8c67a39b3a00d3454b5ce8ad32a3f899d16be830c7d9'
for item in plan['source_files']:assert record(R/item['path'])=={'bytes':item['bytes'],'sha256':item['sha256']}
assert fsha(A/'recognizer-report.json')=='26098ab9a14bc328d7c9aea77e43defadbec57d1055f8190976ecd492fc6485f'
assert fsha(A/'execution.json')=='ee987abd4b98c62a579537a995c6fbb19401c42e977119567a7c3ce48750966e'
zip_path=H/'large-v3-native-73b75b45.zip';zrec=record(zip_path);verified=load(H/'artifact-download-verification.json');manifest=load(H/'artifact-file-manifest.json')
assert zrec=={'bytes':4097903,'sha256':'a2a0c88be3127dd9020d348c1a80f55cd48633ed32c66048710e61899e5a573b'} and verified['published_digest_matches'] and manifest['artifact_zip_sha256']==zrec['sha256']
assert verified['commit']==r['commit'] and (verified['run_id'],verified['job_id'],verified['artifact_id'])==(46102019808,140846358625,15245622385)
for row in manifest['files']:assert record(A/row['path'])=={'bytes':row['bytes'],'sha256':row['sha256']}
with zipfile.ZipFile(zip_path) as z:
 for name in z.namelist():
  if name.endswith('/'):continue
  assert z.read(name)==(A/name).read_bytes()
assert r['complete'] and r['structural_pass'] and r['model_initialized'] and r['model_initializations']==1 and r['pinned_sources_and_model_files_unchanged'] and r['recorded_limits_pass']
assert r['runtime_versions']==plan['runtime_versions'] and r['source_language_argument'] is None and r['references_supplied_to_decoder'] is False and r['app_integration'] is False and r['fresh_validation'] is False and r['python_network_attempts']==[]
assert r['cpu_affinity']==e['cpu_affinity']==[0,1,2,3] and r['model_constructor_arguments']=={'device':'cpu','compute_type':'int8','cpu_threads':4,'num_workers':1,'local_files_only':True}
assert r['actual_model']=={'device':'cpu','compute_type':'int8_float32','cpu_threads_requested':4,'num_workers_requested':1,'num_workers_observed':1,'multilingual':True,'max_length':448,'n_mels':128,'loaded':True}
assert inp['complete'] and download['complete'] and download['model_initialized'] is False and inp['speech_model_initialized'] is False
model_files=load(D/'model-files.json');pinned={x['filename']:x for x in model_files['files']};assert download['model_id']==plan['model_id'] and download['revision']==plan['model_revision'] and set(pinned)=={x['filename'] for x in download['files']}
for row in download['files']:
 item=pinned[row['filename']];assert row['attempt']==1 and row['status']=='verified' and row['bytes']==item['bytes'] and row['sha256']==item['sha256'] and row['url_without_query']==item['immutable_url']
assert (A/'pip-check.txt').read_text().strip()=='No broken requirements found.'
install=load(A/'runtime-install.json');dist={x['metadata']['name'].lower().replace('_','-'):x for x in install['install']};pins=load(D/'runtime-pin-review.json')
for wheel in pins['official_cp312_linux_wheels']:
 row=dist[wheel['name'].lower().replace('_','-')];assert row['metadata']['version']==wheel['version'] and row['download_info']['url']==wheel['url'] and row['download_info']['archive_info']['hashes']['sha256']==wheel['sha256']
tokenizer_path=Path('/workspace/scratch/94360995dd61/large-v3-model-metadata-2026-11-28/tokenizer.json');assert fsha(tokenizer_path)==pinned['tokenizer.json']['sha256'];tokenizer=load(tokenizer_path);vocab={v:k for k,v in tokenizer['model']['vocab'].items()}
for token in tokenizer['added_tokens']:vocab[token['id']]=token['content']
ids={v:k for k,v in vocab.items()};eot=ids['<|endoftext|>'];assert eot==r['native_eot_token_id']==50257 and tokenizer['decoder']['type']=='ByteLevel'
installed=Path('/workspace/scratch/94360995dd61/linkscribe-dev-venv/lib/python3.12/site-packages')
for name,item in r['native_runtime_source_files'].items():assert fsha(installed/(name.replace('.','/')+'.py'))==item['sha256']
native_path=installed/'faster_whisper/transcribe.py';tree=ast.parse(native_path.read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='WhisperModel');split_node=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_split_segments_by_timestamps');future=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0);module=ast.fix_missing_locations(ast.Module(body=[future,split_node],type_ignores=[]));ns={};exec(compile(module,str(native_path),'exec'),ns);split=ns['_split_segments_by_timestamps'];fake_self=types.SimpleNamespace(time_precision=.02,input_stride=2);fake_tokenizer=types.SimpleNamespace(timestamp_begin=ids['<|0.00|>'])
policy=load(D/'production-policy.json');assert r['observed_production_policy']['function_ast_sha256']==policy['function_ast_sha256'] and r['observed_production_policy']['constants']==policy['constants'] and r['observed_production_policy']['function_source_lf']==policy['function_source_lf']
ordered=[x['id'] for x in plan['cases']];assert ordered==[x['id'] for x in inp['cases']]==[x['id'] for x in r['cases']]==[x['id'] for x in criteria['cases']]
audit=[]
for expected,prep,c in zip(plan['cases'],inp['cases'],r['cases']):
 cid=c['id'];wave=A/'inputs'/f'{cid}.wav';array=A/'inputs'/f'{cid}.npy';header,pcm=npy(array)
 assert c['attempt']==prep['attempt']==1 and c['sample_count']==prep['sample_count']==expected['sample_count']==header['shape'][0]
 assert fsha(wave)==prep['original_audio_sha256']==prep['download']['sha256']==expected['audio_sha256'] and wave.stat().st_size==prep['download']['bytes'] and fsha(array)==prep['array_sha256']
 assert sha(pcm)==prep['pcm_sha256']==expected['pcm_sha256']==c['pcm_sha256']==c['transcribe_input_pcm_sha256'] and prep['dtype']=='<f4' and prep['sample_rate_hz']==16000 and prep['full_untrimmed_recording']
 assert c['transcribe_calls']==1 and len(c['frontend_calls'])==1 and c['native_segment_iterator_exhausted'] and c['production_outcome']=='success' and c['structural_status']=='pass' and all(v is True for v in c['checks'].values())
 fe=c['frontend_calls'][0];assert fe['sample_count']==expected['sample_count'] and fe['pcm_sha256']==sha(pcm) and fe['feature_shape']==[128,expected['sample_count']//160+1] and fe['feature_dtype']=='<f4' and fe['arguments']=={'chunk_length':None}
 assert c['actual_transcribe_request']==plan['production_transcribe_request'] and c['effective_transcribe_arguments']['language'] is None and c['effective_transcribe_arguments']['task']=='transcribe'
 opt=c['transcribe_info']['transcription_options'];after=c['transcribe_info_after_exhaustion']['transcription_options'];assert after=={**opt,'clip_timestamps':[0.0]}
 for key,val in {'beam_size':5,'best_of':5,'patience':1,'condition_on_previous_text':False,'word_timestamps':False,'initial_prompt':None,'prefix':None,'hotwords':None,'without_timestamps':False,'hallucination_silence_threshold':None,'clip_timestamps':'0','temperatures':[0.0,0.2,0.4,0.6,0.8,1.0],'no_speech_threshold':.6,'compression_ratio_threshold':2.4,'log_prob_threshold':-1.0,'max_new_tokens':None}.items():assert opt[key]==val
 duration=expected['sample_count']/16000;assert c['transcribe_info']['duration']==c['transcribe_info']['duration_after_vad']==duration and c['transcribe_info']['vad_options'] is None
 language='el' if cid.startswith('fleurs-el_') else 'en';assert c['detected_language']==c['transcribe_info']['language']==language
 assert len(c['decoder_calls'])==1;call=c['decoder_calls'][0];assert call['prompt_ids']==[[ids['<|startoftranscript|>'],ids[f'<|{language}|>'],ids['<|transcribe|>']]]
 args=call['effective_generate_arguments'];assert args['beam_size']==5 and args['patience']==1 and args['max_length']==448 and args['return_scores'] and args['return_no_speech_prob'] and args['suppress_tokens']==opt['suppress_tokens'] and args['suppress_blank'] is True
 assert len(call['results'])==1;result=call['results'][0];assert len(result['sequences_ids'])==1
 for seq,pieces,text,length in zip(result['sequences_ids'],result['token_strings'],result['text_without_special_tokens'],result['sequence_plus_prompt_lengths']):
  assert pieces==[vocab[t] for t in seq] and decode([vocab[t] for t in seq if t<eot])==text and length==len(seq)+len(call['prompt_ids'][0])<448
 assert math.isfinite(result['no_speech_prob']) and all(math.isfinite(x) for x in result['scores'])
 split_segments,seek,single=split(fake_self,fake_tokenizer,result['sequences_ids'][0],0.0,expected['sample_count']//160,duration,0)
 assert len(split_segments)==len(c['raw_segments'])
 previous_start=previous_end=-1
 for raw,derived,prod in zip(c['raw_segments'],split_segments,c['production_segments']):
  assert raw['tokens']==derived['tokens'] and raw['token_strings']==[vocab[t] for t in raw['tokens']]
  assert raw['text']==raw['text_redecoded_from_tokens']==decode([vocab[t] for t in raw['tokens'] if t<eot]) and raw['words'] is None
  assert math.isclose(raw['start'],derived['start'],abs_tol=1e-9) and math.isclose(raw['end'],derived['end'],abs_tol=1e-9)
  assert math.isfinite(raw['start']) and math.isfinite(raw['end']) and 0<=raw['start']<raw['end'] and raw['start']>=previous_start and raw['end']>=previous_end
  previous_start,previous_end=raw['start'],raw['end'];assert prod=={'start':round(raw['start'],3),'end':round(raw['end'],3),'text':raw['text'].strip()}
 assert c['raw_transcript']==''.join(x['text'] for x in c['raw_segments']) and c['production_transcript']==' '.join(x['text'] for x in c['production_segments'])
 overruns=[{'segment_index':i,'end_seconds':s['end'],'audio_seconds':duration,'overrun_seconds':round(s['end']-duration,9)} for i,s in enumerate(c['raw_segments']) if s['end']>duration+.02]
 assert [x['segment_index'] for x in overruns]==c['native_times_exceeding_audio_duration']
 assert c['elapsed_seconds']<=plan['per_case_seconds'] and c['recorded_process_peak_rss_bytes']<=r['recorded_process_peak_rss_bytes']<=plan['rss_limit_bytes']
 audit.append({'id':cid,'sample_count':expected['sample_count'],'duration_seconds':duration,'wav_sha256':fsha(wave),'array_sha256':fsha(array),'pcm_sha256':sha(pcm),'raw_transcript_utf8_sha256':sha(c['raw_transcript'].encode()),'raw_segments_canonical_json_sha256':canonical(c['raw_segments']),'decoder_calls_canonical_json_sha256':canonical(c['decoder_calls']),'production_segments_canonical_json_sha256':canonical(c['production_segments']),'case_canonical_json_sha256':canonical(c),'full_input_and_token_decode_checks_pass':True,'native_segment_time_derivation_matches':True,'native_segment_overruns':overruns,'decoder_calls':1,'sequence_plus_prompt_lengths':result['sequence_plus_prompt_lengths'],'elapsed_seconds':c['elapsed_seconds']})
samples_path=A/'resource-samples.jsonl';samples=[json.loads(line) for line in samples_path.read_text().splitlines()];assert len(samples)==e['sample_count']==1345 and fsha(samples_path)==e['resource_samples_sha256']
assert all(isinstance(x['rss_bytes'],int) and x['rss_bytes']>=0 and math.isfinite(x['elapsed_seconds']) for x in samples) and all(a['elapsed_seconds']<b['elapsed_seconds'] for a,b in zip(samples,samples[1:]))
assert max(x['rss_bytes'] for x in samples)==e['sampled_group_peak_rss_bytes']<plan['rss_limit_bytes']
assert e['returncode']==0 and e['stop_reason'] is None and e['owned_worker_exited'] and e['cleanup']['leader_exited'] and e['cleanup']['live_group_members_after_cleanup']==[]
assert r['initialization_seconds']<=plan['startup_seconds'] and r['elapsed_seconds']<=plan['total_worker_seconds'] and e['elapsed_seconds']<=plan['total_worker_seconds']
intervals=[b['elapsed_seconds']-a['elapsed_seconds'] for a,b in zip(samples,samples[1:])]
report={'schema_version':1,'audited_at':datetime.now(timezone.utc).isoformat(),'reviewer':'independent package_verification agent','all_declared_mechanical_checks_pass':True,'semantic_quality_approved':False,'method':'Standard-library read-only audit. Verified pinned tokenizer vocabulary and ByteLevel token-to-text decode; executed only the already-pinned pure timestamp split function on recorded token arrays, without model/library imports or acoustic inference.','hosted_identity':{k:verified[k] for k in ('commit','run_id','job_id','artifact_id')},'zip':zrec,'original_criteria_sha256':fsha(O/'source-and-criteria-before-output.json'),'contract_review_sha256':fsha(O/'contract-review.json'),'artifact_files':{row['path']:{'bytes':row['bytes'],'sha256':row['sha256']} for row in manifest['files']},'all_zip_entries_equal_extracted_files':True,'all_manifest_files_rehashed':True,'model_download_record_matches_frozen_inventory':True,'model_weights_not_downloaded_or_rehashed_by_reviewer':True,'actual_direct_wheel_hashes_match_published_pins':True,'tokenizer_small_file_sha256':fsha(tokenizer_path),'native_pure_timestamp_source_sha256':fsha(native_path),'production_policy_ast_matches':True,'observed_native_option_normalization':'The only before/after option difference is native parsing of clip_timestamps from string0 to [0.0], matching the frozen generate_segments code and retaining the full source interval.','cases':audit,'resources':{'sample_count':len(samples),'sampled_group_peak_rss_bytes':e['sampled_group_peak_rss_bytes'],'sampled_group_peak_rss_mib':e['sampled_group_peak_rss_bytes']/1024**2,'worker_os_highwater_rss_bytes':r['recorded_process_peak_rss_bytes'],'worker_os_highwater_rss_mib':r['recorded_process_peak_rss_bytes']/1024**2,'rss_limit_bytes':plan['rss_limit_bytes'],'controller_seconds':e['elapsed_seconds'],'worker_seconds':r['elapsed_seconds'],'initialization_seconds':r['initialization_seconds'],'case_sum_seconds':sum(c['elapsed_seconds'] for c in r['cases']),'maximum_case_seconds':max(c['elapsed_seconds'] for c in r['cases']),'sample_interval_seconds_declared':.1,'sample_gap_seconds_observed':{'min':min(intervals),'median':statistics.median(intervals),'max':max(intervals)},'cleanup':e['cleanup'],'stop_reason':None},'scope_limits':['All eight original development recordings were already exposed; this is not fresh validation.','Input arrays and recorded frontend binding are exact; feature tensors are represented by actual-worker shape/hash observations and were not archived or recomputed independently.','Model binary was verified by the frozen hosted worker and bound download report; the reviewer did not download or rehash the large payload.','Raw native sequence/token/text and timestamp splitting consistency does not prove acoustic correctness or proper word alignment.','One satellite segment ends at7.00s for6.54s audio; the0.46s overrun is retained rather than replaced.','The declared completion check is full native iterator exhaustion and sequences below cap, not exposed terminal-EOS proof.','RSS series and OS worker highwater pass their declared bounds, but sampling is not continuous kernel enforcement or full-app/whole-machine approval.','No audio listening, model inference, retry, threshold change, production edit or Git mutation was performed.']}
p=O/'output-binding-audit.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'path':str(p),'sha256':fsha(p),'cases':len(audit),'mechanical_checks_pass':True,'resource_samples':len(samples)},indent=2))
if __name__=='__main__':pass

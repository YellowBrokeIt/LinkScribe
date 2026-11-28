"""Read-only mechanical provenance/output audit. No ML imports or inference."""
from pathlib import Path
import ast, datetime, hashlib, json, math, re, struct, zipfile
ROOT=Path('/workspace/scratch/94360995dd61')
DOC=ROOT/'LinkScribe/docs/parakeet-screen-2026-11-28/legacy-frontend-ablation'
OUT=ROOT/'parakeet-independent-review-2026-11-28'
RUN=ROOT/'parakeet-legacy-frontend-ablation-2026-11-28/results'
def digest(data): return hashlib.sha256(data).hexdigest()
def file_sha(path): return digest(Path(path).read_bytes())
def canonical_sha(value): return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
plan=json.loads((DOC/'plan.json').read_text())
report=json.loads((RUN/'recognizer-report.json').read_text())
execution=json.loads((RUN/'execution.json').read_text())
assert file_sha(DOC/'plan.json')=='f9b47352771a31ee354640e2e534d58cf01685cea9cfda642a7ef93e1ba6a44c'
assert file_sha(DOC/'run_screen.py')=='411bcc94bc3776f3a727be480b8b5bf569b289c7e543697f778f158caabe7a72'
assert report['plan_sha256']==execution['plan_sha256']==file_sha(DOC/'plan.json')
assert report['helper_sha256']==file_sha(DOC/'run_screen.py')
for item in plan['pinned_files']:
 path=Path(item['path']); assert path.stat().st_size==item['bytes']; assert file_sha(path)==item['sha256']
assert report['complete'] and execution['returncode']==0 and execution['stopped_at_limit'] is None
assert len(report['cases'])==8 and {x['id'] for x in report['cases']}=={x['id'] for x in plan['case_inputs']}
assert report['cpu_affinity']==plan['cpu_affinity']
assert all(s['providers']==['CPUExecutionProvider'] and s['intra_op_num_threads']==4 and s['inter_op_num_threads']==1 and s['execution_mode']=='ExecutionMode.ORT_SEQUENTIAL' for s in report['onnx_sessions'])
assert report['python_network_attempts']==[] and report['onnxruntime_disable_telemetry_events_called']
assert report['source_language_argument'] is None and report['target_language_argument'] is None and report['reference_supplied_to_decoder'] is False
assert report['pinned_files_unchanged_after_run']
assert report['actual_tokenizer']=={'vocabulary_entries':8193,'blank_id':8192,'emission_frame_seconds':0.08}
assert report['max_tokens_per_step']==10 and report['actual_frontend']=='PublishedLegacyNemoFrontend'
vocab={int(i):t.replace('\u2581',' ') for t,i in (line.split(' ') for line in (Path(plan['model_directory'])/'vocab.txt').read_text().splitlines())}
assert len(vocab)==8193 and vocab[8192]=='<blk>'
frame_scale=0.08
inputs={x['id']:x for x in plan['case_inputs']}
rows=[]
for case in report['cases']:
 source=inputs[case['id']]
 wav=Path(source['original_audio_path']).read_bytes()
 assert digest(wav)==source['original_audio_sha256']
 assert wav[:4]==b'RIFF' and wav[8:12]==b'WAVE' and struct.unpack('<I',wav[4:8])[0]+8==len(wav)
 chunks={}; pos=12
 while pos<len(wav):
  kind=wav[pos:pos+4]; size=struct.unpack('<I',wav[pos+4:pos+8])[0]; assert kind not in chunks
  chunks[kind]=wav[pos+8:pos+8+size]; assert len(chunks[kind])==size; pos+=8+size+(size%2)
 assert pos==len(wav)
 fmt=struct.unpack('<HHIIHH',chunks[b'fmt '][:16]); assert fmt==(3,1,16000,64000,4,32)
 pcm=chunks[b'data']; assert len(pcm)==4*source['sample_count']
 npy=Path(source['array_path']).read_bytes(); assert digest(npy)==source['array_sha256'] and npy[:6]==b'\x93NUMPY'
 major=npy[6]; size_n=2 if major==1 else 4; header_n=int.from_bytes(npy[8:8+size_n],'little')
 header=ast.literal_eval(npy[8+size_n:8+size_n+header_n].decode('latin1'))
 assert header=={'descr':'<f4','fortran_order':False,'shape':(source['sample_count'],)}
 prepared_pcm=npy[8+size_n+header_n:]
 original_values=struct.unpack('<'+str(source['sample_count'])+'f',pcm)
 decoded_pcm=struct.pack('<'+str(source['sample_count'])+'f',*(min(32767,max(-32768,round(v*32768)))/32768 for v in original_values))
 assert prepared_pcm==decoded_pcm
 source_pcm_sha=digest(pcm)
 pcm=prepared_pcm
 assert digest(pcm)==source['pcm_sha256']==case['pcm_sha256']==case['frontend_input_pcm_sha256']
 assert case['sample_count']==source['sample_count'] and case['frontend_calls']==1 and case['attempt']==1
 assert case['source_language_argument'] is None and case['target_language_argument'] is None and not case['vad_used'] and not case['audio_trimmed']
 assert len(case['decode_calls'])==1
 raw=case['raw_result']; dec=case['decode_calls'][0]
 assert dec['output']==raw
 assert all(isinstance(i,int) and 0<=i<8192 for i in dec['token_ids'])
 tokens=[vocab[i] for i in dec['token_ids']]
 assert tokens==raw['tokens']
 reconstructed=re.sub(r'\A\s|\s\B|(\s)\b',lambda m:' ' if m.group(1) else '', ''.join(tokens))
 assert reconstructed==raw['text']
 assert [frame_scale*i for i in dec['emission_frame_indices']]==raw['timestamps']
 assert dec['token_logprobs']==raw['logprobs']
 assert len(tokens)==len(raw['timestamps'])==len(raw['logprobs'])
 assert all(math.isfinite(x) for x in raw['timestamps']+raw['logprobs'])
 assert all(0<=x<=source['duration_seconds']+0.08 for x in raw['timestamps'])
 assert all(a<=b for a,b in zip(raw['timestamps'],raw['timestamps'][1:]))
 assert all(case['checks'].values()) and case['structural_status']=='pass'
 assert case['elapsed_seconds']<plan['per_case_wall_seconds']
 assert case['process_peak_rss_bytes']<plan['rss_limit_bytes']
 rows.append({'id':case['id'],'wav_sha256':digest(wav),'prepared_array_sha256':digest(npy),'full_pcm_sha256':digest(pcm),'sample_count':source['sample_count'],'duration_seconds':source['duration_seconds'],'source_wav_pcm_sha256':source_pcm_sha,'source_wav_float32_equals_prepared_float32':False,'complete_wav_matches_declared_decode_conversion':True,'full_array_equals_logged_frontend_input':True,'raw_result_sha256':canonical_sha(raw),'raw_decode_call_sha256':canonical_sha(dec),'text_utf8_sha256':digest(raw['text'].encode()),'tokens_match_frozen_vocabulary':True,'text_matches_native_decode':True,'timestamps_equal_native_emission_frames_times_0_08':True,'logprobs_equal_native_capture':True,'token_count':len(tokens),'last_token_seconds':raw['timestamps'][-1],'elapsed_seconds':case['elapsed_seconds'],'all_declared_structural_checks':True})

assert file_sha(RUN/'recognizer-report.json')=='5cebad8176f649a43a17ced5efc6114d8fb27a9ffe6ac63a3e374903ff574f0e'
assert file_sha(RUN/'execution.json')=='439c6bac5d90100b975f7e03462661bcb8afaedc4e1d7f2ce5c054766322086f'
assert report['normal_numpy_frontend_constructed_but_not_called']
assert file_sha(plan['original_plan_path'])==report['original_plan_sha256']==plan['original_plan_sha256']
assert file_sha(plan['original_int8_report_path'])==report['original_int8_report_sha256']==plan['original_int8_report_sha256']
assert file_sha(plan['semantic_criteria_path'])==plan['semantic_criteria_sha256']
legacy_session=[s for s in report['onnx_sessions'] if s.get('path')==plan['legacy_frontend_path']]
assert len(legacy_session)==1 and legacy_session[0]['sha256']==plan['legacy_frontend_sha256']
assert file_sha(plan['legacy_frontend_path'])==plan['legacy_frontend_sha256']
def npy_data(blob):
 assert blob[:6]==b'\x93NUMPY'
 size_n=2 if blob[6]==1 else 4
 header_n=int.from_bytes(blob[8:8+size_n],'little')
 header=ast.literal_eval(blob[8+size_n:8+size_n+header_n].decode('latin1'))
 return header,blob[8+size_n+header_n:]
feature_pairs={p['id']:p for p in plan['published_frontend_features']}
for c,row in zip(report['cases'],rows,strict=True):
 pair=feature_pairs[c['id']]; assert file_sha(pair['path'])==pair['sha256']==c['published_frontend_binding']['retained_pair_sha256']
 with zipfile.ZipFile(pair['path']) as z:
  head,data=npy_data(z.read('onnx_features.npy'));lenhead,lendata=npy_data(z.read('onnx_lengths.npy'))
 assert head['descr']=='<f4' and not head['fortran_order']
 assert list(head['shape'])==c['features']['shape'] and len(data)==math.prod(head['shape'])*4
 assert digest(data)==c['features']['sha256']
 assert lenhead['descr']=='<i8' and lenhead['shape']==(1,) and list(struct.unpack('<q',lendata))==c['features']['lengths']
 binding=c['published_frontend_binding']; assert all(binding[k] for k in ['equal_shape','equal_lengths','release_tolerance_pass','features_sha256_exact'])
 row['legacy_frontend_features_sha256']=digest(data)
 row['retained_onnx_pair_sha256']=pair['sha256']
 row['features_exactly_match_retained_published_frontend']=True
 row['feature_lengths']=c['features']['lengths']
 row['feature_shape']=c['features']['shape']

start=datetime.datetime.fromisoformat(execution['started_at']); initialized=datetime.datetime.fromisoformat(report['model_initialized_at'])
startup_init=(initialized-start).total_seconds()
assert startup_init<plan['initialization_wall_seconds'] and execution['elapsed_seconds']<plan['total_wall_seconds']
assert report['process_peak_rss_bytes']<plan['rss_limit_bytes'] and execution['sampled_process_group_peak_rss_bytes']<plan['rss_limit_bytes']
audit={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Read-only standard-library audit; no model initialization, recognition, audio listening or output correction. Canonical object hashes use sorted-key compact UTF-8 JSON; text hashes use exact UTF-8 bytes.','plan_sha256':file_sha(DOC/'plan.json'),'helper_sha256':file_sha(DOC/'run_screen.py'),'report_sha256':file_sha(RUN/'recognizer-report.json'),'execution_sha256':file_sha(RUN/'execution.json'),'review_input_snapshot_sha256':file_sha(OUT/'review-inputs-before-output.json'),'all_pinned_files_match':True,'legacy_frontend_exactly_bound_to_retained_onnx_pairs':True,'original_plan_sha256':plan['original_plan_sha256'],'original_int8_report_sha256':plan['original_int8_report_sha256'],'pre_output_contract_review_sha256':file_sha(OUT/'legacy-frontend-contract-review.json'),'all_eight_complete_once':True,'all_cpu_sessions_match':True,'raw_input_and_output_binding_pass':True,'source_target_reference_arguments_absent':True,'recorded_python_network_attempts':0,'declared_resource_limits_pass':True,'resources':{'source_audio_seconds':sum(x['duration_seconds'] for x in plan['case_inputs']),'controller_elapsed_seconds':execution['elapsed_seconds'],'worker_elapsed_seconds':report['elapsed_seconds'],'startup_and_initialization_seconds_from_controller':startup_init,'model_initialization_seconds_recorded':report['initialization_elapsed_seconds'],'recognition_sum_seconds':sum(x['elapsed_seconds'] for x in report['cases']),'slowest_case_seconds':max(x['elapsed_seconds'] for x in report['cases']),'worker_recorded_peak_rss_bytes':report['process_peak_rss_bytes'],'process_group_sampled_peak_rss_bytes':execution['sampled_process_group_peak_rss_bytes'],'rss_limit_bytes':plan['rss_limit_bytes'],'controller_exit_code':execution['returncode'],'stopped_at_limit':execution['stopped_at_limit']},'cases':rows,'limitations':['Capture binding establishes unchanged runtime output, not semantic correctness. The older supplied frontend is not independently established as the correct training frontend; this is a sensitivity diagnostic.','The original float32 WAV is converted through the predeclared normal signed-16-bit audio-decoder path; every full prepared array matches that conversion exactly. It is not byte-identical to the original float32 sample payload.','Token emission timestamps are not independently annotated word starts or word ends; timing accuracy is not approved.','No app upload/storage/export/restart route was exercised by this recognizer-only experiment.','Owned-worker RSS measurements do not establish total machine usage or an unsampled group peak.','No independent packet capture or human audio listening was performed.']}
(OUT/'legacy-output-binding-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'audit_sha256':file_sha(OUT/'legacy-output-binding-audit.json'),'cases':len(rows),'resources':audit['resources']},indent=2))

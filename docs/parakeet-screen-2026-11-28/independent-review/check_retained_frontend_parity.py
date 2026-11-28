"""Inspect saved feature arrays only; never import or run either frontend."""
from pathlib import Path
import datetime,hashlib,json,math
import numpy as np
ROOT=Path('/workspace/scratch/94360995dd61')
D=ROOT/'LinkScribe/docs/parakeet-screen-2026-11-28/frontend-parity'
R=ROOT/'parakeet-frontend-parity-2026-11-28/results'
OUT=ROOT/'parakeet-independent-review-2026-11-28'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bufsha(a):return hashlib.sha256(a.tobytes()).hexdigest()
p=json.loads((D/'plan.json').read_text());r=json.loads((R/'report.json').read_text());e=json.loads((R/'execution.json').read_text())
assert sha(D/'plan.json')=='52a9ca579d96d8cb8d496925ce0917e0028135d04c212884aaa08667954b32c1'
assert sha(D/'run_frontend_parity.py')==p['helper_sha256']=='d0e323ac001b23fe909f6100a25aa386af3bd46e6f8baf7ad7e8dcb63f901b93'
assert r['plan_sha256']==e['plan_sha256']==sha(D/'plan.json')
assert r['complete'] and not r['speech_model_initialized'] and not r['speech_recognition_performed']
assert e['returncode']==0 and e['stopped_at_limit'] is None
assert len(r['frontend_sessions'])==1 and r['frontend_sessions'][0]['path']==p['supplied_onnx_frontend']
assert r['frontend_sessions'][0]['sha256']==sha(p['supplied_onnx_frontend'])
assert r['frontend_sessions'][0]['providers']==['CPUExecutionProvider']
prior_path=Path(p['original_report']);prior=json.loads(prior_path.read_text());prior={c['id']:c for c in prior['cases']}
assert sha(prior_path)=='6c4d06ec6dec4c68d3774f8274c5007b9d7da0ba5ddacb3c3d074b44ff620e1c'
inputs={c['id']:c for c in p['cases']};rows=[]
for c in r['cases']:
 path=R/c['complete_feature_pair_file'];assert sha(path)==c['complete_feature_pair_sha256']
 with np.load(path,allow_pickle=False) as z:
  assert set(z.files)=={'numpy_features','onnx_features','numpy_lengths','onnx_lengths'}
  a=z['numpy_features'];b=z['onnx_features'];al=z['numpy_lengths'];bl=z['onnx_lengths']
  assert a.dtype.str==b.dtype.str=='<f4' and al.dtype.str==bl.dtype.str=='<i8'
  assert list(a.shape)==list(b.shape)==c['numpy_shape']==c['onnx_shape']
  assert al.tolist()==c['numpy_lengths'] and bl.tolist()==c['onnx_lengths']
  assert bufsha(a)==c['numpy_features_sha256']==prior[c['id']]['features']['sha256']
  assert bufsha(b)==c['onnx_features_sha256']
  assert int(al[0])==c['sample_count']//160 and int(bl[0])==int(al[0])+1==a.shape[-1]
  assert np.isfinite(a).all() and np.isfinite(b).all()
  delta=np.abs(a-b);allowed=p['tolerance']['atol']+p['tolerance']['rtol']*np.abs(b);fail=delta>allowed
  assert int(fail.sum())==c['violating_values']
  d64=a.astype(np.float64)-b.astype(np.float64)
  assert float(np.abs(d64).max())==c['max_absolute_difference']
  assert math.isclose(float(np.abs(d64).mean()),c['mean_absolute_difference'],rel_tol=1e-12)
  assert fail.sum(axis=(0,1)).tolist()==c['violations_per_frame']
  assert c['release_tolerance_pass'] is False and c['equal_lengths'] is False
  wave=np.load(inputs[c['id']]['array_path'],allow_pickle=False)
  assert sha(inputs[c['id']]['array_path'])==inputs[c['id']]['array_sha256']
  assert wave.size==c['sample_count'] and bufsha(wave)==c['pcm_sha256']==prior[c['id']]['pcm_sha256']
  shared=int(al[0]);shared_fail=int(fail[:,:,:shared].sum());assert shared_fail>0
  rows.append({'id':c['id'],'retained_pair_sha256':sha(path),'sample_count':c['sample_count'],'features_shape':list(a.shape),'numpy_valid_frames':int(al[0]),'supplied_onnx_valid_frames':int(bl[0]),'numpy_features_equal_original_screen':True,'same_prepared_pcm_as_original_screen':True,'values_outside_frozen_tolerance':int(fail.sum()),'shared_valid_values_outside_frozen_tolerance':shared_fail,'total_values':a.size,'maximum_absolute_difference':c['max_absolute_difference'],'numpy_last_frame_all_zero':bool(np.all(a[:,:,-1]==0)),'supplied_onnx_last_frame_all_zero':bool(np.all(b[:,:,-1]==0)),'parity_pass':False})
assert len(rows)==8 and r['all_eight_pass'] is False and r['all_eight_match_original_numpy_features'] is True
assert r['worker_peak_rss_bytes']<p['limits']['rss_bytes'] and e['worker_peak_sampled_rss_bytes']<p['limits']['rss_bytes']
assert e['elapsed_seconds']<p['limits']['total_seconds'] and r['initialization_seconds']<p['limits']['startup_seconds']
assert all(c['elapsed_seconds']<p['limits']['per_case_seconds'] for c in r['cases'])
review={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'independent package_verification agent','scope':'Read-only consistency audit of retained feature pairs, recorded outputs and helper source. Only NumPy file reading/arithmetic; neither frontend nor speech model was imported or executed by reviewer.','plan_sha256':sha(D/'plan.json'),'helper_sha256':sha(D/'run_frontend_parity.py'),'report_sha256':sha(R/'report.json'),'execution_sha256':sha(R/'execution.json'),'original_int8_screen_report_sha256':sha(prior_path),'checker_sha256':sha(Path(__file__)),'frozen_tolerance':p['tolerance'],'same_shape_and_lengths_required':p['same_shape_and_length_required'],'all_eight_pairs_consistent_with_report':True,'parity_counts':{'pass':0,'fail':8},'all_numpy_features_exactly_match_original_screen':True,'all_pairs_have_differences_within_shared_valid_frames':True,'no_new_speech_recognition_recorded':True,'all_recorded_resource_limits_pass':True,'findings':['All eight saved pairs have the same tensor shapes but differ by one reported valid frame: NumPy floor(N/160), supplied ONNX floor(N/160)+1.','Every final NumPy frame is zero-masked; the supplied ONNX final frame is nonzero. Differences also exceed the frozen tolerance within shared valid frames, so the result is not explained solely by adding/removing a trailing output element.','The NumPy feature bytes in every pair exactly equal the features captured in the rejected original int8 screen; that original screen used its declared frontend.','The one recorded ONNX session is the permitted supplied frontend, with CPU provider and one thread. No speech encoder/decoder sessions are permitted by the inspected constructor guard.','Exit 0 means the diagnostic completed; report parity is explicitly false for every case. It does not mark a successful equivalence gate.'],'limits':['The supplied older ONNX frontend is not established here as the training/export ground truth.','The runtime release tests use their current bundled frontend; their tolerance is a diagnostic threshold here, not proof that the supplied model-package frontend should be equivalent.','This audit does not establish that changing frontend would repair any transcript, nor isolate quantization as a cause.','No threshold, candidate frontend, precision, model, criteria or transcript was changed.'],'decision':'Confirmed concrete frontend mismatch between the pinned implementations. Keep both raw representations and failed comparisons. Do not silently substitute the supplied ONNX or interpret this as corrected ASR quality. Training/export provenance would be needed to identify a justified replacement.','cases':rows}
(OUT/'frontend-parity-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'review_sha256':sha(OUT/'frontend-parity-review.json'),'cases':len(rows),'parity_failures':8,'shared_valid_violations_total':sum(c['shared_valid_values_outside_frozen_tolerance'] for c in rows),'max_difference_range':[min(c['maximum_absolute_difference'] for c in rows),max(c['maximum_absolute_difference'] for c in rows)]},indent=2))

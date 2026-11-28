"""Static source and retained-data audit; no candidate import or execution."""
import ast
import hashlib
import json
from pathlib import Path
import os
import shlex

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
NEW=ROOT/'docs/krikri-marker-grammar-build-continuation-2026-11-28'
OLD=ROOT/'docs/krikri-marker-grammar-controller-v2-2026-11-28'
NATIVE=ROOT/'docs/krikri-marker-grammar-native-plan-2026-11-28'
HERE=Path(__file__).resolve().parent
checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check(name,value,detail=None):checks.append({'id':name,'passed':bool(value),'detail':detail})
def verify_record(row,label):
    p=Path(row['path']);check(label,p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'])

plan=read(NEW/'plan.json');old_plan=read(OLD/'plan.json')
check('plan-sidecar',sha(NEW/'plan.json')==(NEW/'plan.sha256').read_text().strip())
for relative,expected in plan['source_sha256'].items():
    path=ROOT/relative;check('frozen-binding:'+relative,path.is_file() and not path.is_symlink() and sha(path)==expected)
manifest=read(NEW/'evidence-manifest.json')
for row in manifest['files']:
    path=NEW/row['path'];check('manifest:'+row['path'],path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'])
for name in ['resource_monitor.py','process_io.py','native_actions.py','native_contract.py','status_contract.py','official-source-capsule.json']:
    check('unchanged-runtime:'+name,(NEW/name).read_bytes()==(OLD/name).read_bytes())
for key in ['native_plan_path','native_plan_sha256','grammar_preparation_plan_sha256','runtime','model','python_runtime',
            'extra_tool_bindings','native_inherited_home','home_policy','owned_runtime_root','phase_budgets',
            'aggregate_active_seconds','disk','phase_receipts','worker_parent_identity','zero_output_contract']:
    check('unchanged-contract-field:'+key,plan[key]==old_plan[key])
check('only-three-continuation-phases',plan['phases']==['build','native_prepare','validate'])
check('prior-review-exact',sha(NEW/'independent-prior-stage-review/independent-stage-review.json')==
      '0d32d5e31f9aef6d1df84c9477f1c2bcc6d22013e4efd24ade9744559888a991')
profile=read(NEW/'independent-prior-stage-review/actual-header-dependencies.json')
check('prior-independent-dependency-evidence-exact',sha(NEW/'independent-prior-stage-review/actual-header-dependencies.json')==
      '5ab49d6690aff96a06251586ad6b5c4797e2ca18922460913e60f69f8d982857')
inputs=read(NEW/'continuation-inputs.json')
check('continuation-input-identity',sha(NEW/'continuation-inputs.json')==plan['continuation']['inputs_sha256'])
for row in inputs['retained_files']:verify_record(row,'retained-input:'+row['path'])
old_build=read(OLD/'build.json');old_resources=read(OLD/'build-resources.json');acquire_resources=read(OLD/'acquire-resources.json')
check('old-build-remains-failed',old_build['complete'] is False and old_resources['passed'] is False and
      old_build['error']==inputs['expected_prior_build_error'] and 'sanity' not in old_build)
check('exact-current-binary-and-depfile',inputs['validator']==old_build['validator'] and inputs['depfile']==old_build['compiler_dependency_file'])
check('exact-original-time-carried',plan['continuation']['spent_build_seconds']==inputs['spent_build_seconds']==old_resources['elapsed_seconds']==1.062938 and
      plan['continuation']['carried_active_seconds']==inputs['carried_active_seconds']==old_resources['elapsed_seconds']+acquire_resources['elapsed_seconds'] and
      plan['continuation']['remaining_original_build_seconds']==120-old_resources['elapsed_seconds']==118.937062)
verify_record(profile['depfile'],'complete-depfile-record')
target,separator,remainder=Path(profile['depfile']['path']).read_text().replace('\\\n',' ').partition(':')
names=shlex.split(remainder)
check('complete-exact-273-dependency-order',separator==':' and len(names)==len(set(names))==profile['dependency_count']==273
      and names==[x['compiler_path'] for x in profile['all_dependencies']] and shlex.split(target)==[inputs['validator']['path']])
for row in profile['all_dependencies']:verify_record(row,'consumed-header:'+row['path'])
exceptions=profile['unexpected_resolved_headers']
check('exact-five-resolved-exceptions',{x['path'] for x in exceptions}=={'/usr/lib/linux/uapi/x86/asm/'+n for n in
      ['errno.h','types.h','bitsperlong.h','posix_types.h','posix_types_64.h']})
for row in exceptions:
    alias=row['system_include_alias'];p=Path(alias['path'])
    check('exact-system-alias:'+row['path'],p.is_symlink() and p.is_relative_to('/usr/include') and os.readlink(p)==alias['link_text'] and str(p.resolve())==alias['resolved']==row['path'])

trees={}
for path in sorted(NEW.glob('*.py')):
    trees[path.name]=ast.parse(path.read_text(),filename=str(path));check('static-parse:'+path.name,True)
def fn(path,name):
    node=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name==name)
    return ast.dump(node,include_attributes=False)
for name in ['validate','validated_cli','verify_loader_output','require_record','expected_sources','verify_materialized_sources']:
    check('unchanged-phase-function:'+name,fn(NEW/'phase_actions.py',name)==fn(OLD/'phase_actions.py',name))
for name in ['verify_receipt','verify_controller_parent']:
    check('unchanged-root-gate-function:'+name,fn(NEW/'execution_gate.py',name)==fn(OLD/'execution_gate.py',name))
new_text=(NEW/'phase_actions.py').read_text();old_text=(OLD/'phase_actions.py').read_text()
tail='    sanity = read(NATIVE_PLAN / "validator-sanity.json")'
check('original-sanity-execution-tail-unchanged',new_text.split(tail,1)[1].split('\ndef validate(',1)[0]==old_text.split(tail,1)[1].split('\ndef validate(',1)[0])
build=next(x for x in trees['phase_actions.py'].body if isinstance(x,ast.FunctionDef) and x.name=='build')
calls=[x for x in ast.walk(build) if isinstance(x,ast.Call)]
check('no-direct-compile-acquire-subprocess-in-build',not any(isinstance(x.func,ast.Name) and x.func.id in ['run_command','acquire'] for x in calls)
      and not any(isinstance(x.func,ast.Attribute) and x.func.attr in ['Popen','run','system'] for x in calls))
check('sanity-cli-is-only-dispatched-native-action',sum(isinstance(x.func,ast.Name) and x.func.id=='validated_cli' for x in calls)==1)
controls=read(NEW/'source-control-results.json')
check('46-retained-controls-pass',len(controls['checks'])==46 and controls['passed'] is True and all(x['passed'] for x in controls['checks']))
check('controls-no-native-or-authority',controls['subprocess_compiler_validator_native_tokenizer_model_network_calls']==0 and
      controls['actual_phase_receipts_created']==0 and controls['prior_build_regraded'] is False)
for row in controls['checks']:
    if row['id'].startswith('actual-entrypoint-missing-root-receipt-'):check('retained-receipt-refusal:'+row['id'],row['passed'])

out={'schema_version':1,'scope':'Independent static source/hash/AST and retained-data review only; no candidate code or control execution.',
     'plan_sha256':sha(NEW/'plan.json'),'manifest_sha256':sha(NEW/'evidence-manifest.json'),'source_bindings':len(plan['source_sha256']),
     'manifest_files':len(manifest['files']),'checks':checks,'passed':all(x['passed'] for x in checks),
     'actual_phase_receipts_present':[x for x in plan['phases'] if (NEW/(x+'-authorization.json')).exists()],
     'reviewer_subprocess_compiler_validator_native_tokenizer_model_network_calls':0}
(HERE/'source-contract-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
                  'audit_sha256':sha(HERE/'source-contract-audit.json')}))

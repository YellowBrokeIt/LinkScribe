"""Read retained phase receipts and source/header bytes; run no native tools."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct

ROOT=Path('/workspace/scratch/94360995dd61/LinkScribe')
STAGE=ROOT/'docs/krikri-marker-grammar-controller-v2-2026-11-28'
NATIVE=ROOT/'docs/krikri-marker-grammar-native-plan-2026-11-28'
OWNED=Path('/workspace/scratch/94360995dd61/linkscribe-grammar-validator-runtime')
HERE=Path(__file__).resolve().parent
checks=[]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as s:
        while b:=s.read(1024*1024):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check(n,v,detail=None):checks.append({'id':n,'passed':bool(v),'detail':detail})
def record(p):
    p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def verify_record(item,label):
    p=Path(item['path']);check(label,p.is_file() and not p.is_symlink() and p.stat().st_size==item['bytes'] and sha(p)==item['sha256']);return p

plan=read(STAGE/'plan.json')
for rel,expected in plan['source_sha256'].items():check('source:'+rel,sha(ROOT/rel)==expected)
phase_reports={}
for phase,expected_success in [('acquire',True),('build',False)]:
    p=STAGE/(phase+'.json');rp=STAGE/(phase+'-resources.json');ap=STAGE/(phase+'-authorization.json');cp=STAGE/(phase+'-claim.json')
    report=read(p);resource=read(rp);authorization=read(ap);claim=read(cp)
    for rel,expected in authorization['files_sha256'].items():check(phase+'-authorization-file:'+rel,sha(ROOT/rel)==expected)
    check(phase+'-receipt-sidecar',sha(ap)==(STAGE/(phase+'-authorization.sha256')).read_text().strip())
    check(phase+'-authorization-scope',authorization['phase']==phase and authorization['root_authorized'] is True and
          authorization['runner_author_self_approval'] is False and authorization['generation_authorized'] is False and
          authorization['plan_sha256']==sha(STAGE/'plan.json') and authorization['independent_review_sha256']==sha(ROOT/authorization['independent_review_path']))
    check(phase+'-runtime-bindings',report['plan_sha256']==resource['plan_sha256']==claim['plan_sha256']==sha(STAGE/'plan.json') and
          report['authorization_sha256']==resource['authorization_sha256']==claim['authorization_sha256']==sha(ap) and
          report['claim_sha256']==resource['claim_sha256']==sha(cp) and resource['phase_report_sha256']==sha(p) and
          resource['worker_sha256']==sha(STAGE/'phase_worker.py') and resource['observer_sha256']==sha(STAGE/'resource_monitor.py'))
    check(phase+'-observed-success-or-preserved-failure',report['complete'] is expected_success and resource['complete'] is expected_success and
          resource['passed'] is expected_success and resource['worker_exit_code']==(0 if expected_success else 1))
    check(phase+'-no-native-generation',report['generation_calls']==0 and report['network_model_downloads']==0 and resource['generation_authorized'] is False)
    samples_path=STAGE/resource['samples_file'];samples=[json.loads(x) for x in samples_path.read_text().splitlines()]
    check(phase+'-sample-hash-count',sha(samples_path)==resource['samples_sha256'] and len(samples)==resource['sample_count'])
    check(phase+'-sample-chronology',all(a['elapsed_seconds']<=b['elapsed_seconds'] for a,b in zip(samples,samples[1:])))
    check(phase+'-memory-accounting',all(len({q['pid'] for q in x['processes']})==len(x['processes']) and
          x['rss_bytes']==sum(q['rss_bytes'] for q in x['processes']) and x['pss_bytes']==sum(q['pss_bytes'] for q in x['processes']) for x in samples))
    check(phase+'-peaks',max(x['rss_bytes'] for x in samples)==resource['peak_rss_sample']['rss_bytes'] and
          max(x['pss_bytes'] for x in samples)==resource['peak_pss_sample']['pss_bytes'])
    check(phase+'-limits-cleanup',resource['measurement_complete'] is True and not resource['measurement_errors'] and
          resource['owned_processes_stopped'] is True and resource['phase_time_limit_exceeded'] is False and
          resource['elapsed_seconds']<=resource['limits']['total_seconds'] and resource['peak_rss_sample']['rss_bytes']<=resource['limits']['rss_bytes'] and
          len(resource['cpu_affinity'])==4 and resource['frozen_inputs_unchanged'] is True and
          all(x['storage']['violation'] is None for x in samples) and resource['storage_after_cleanup']['violation'] is None and resource['storage_final']['violation'] is None)
    for predecessor,expected in authorization['completed_phase_bindings'].items():
        check(phase+'-predecessor:'+predecessor,sha(STAGE/(predecessor+'.json'))==expected['report_sha256'] and
              sha(STAGE/(predecessor+'-resources.json'))==expected['resources_sha256'])
    phase_reports[phase]={'report':record(p),'resources':record(rp),'authorization':record(ap),'claim':record(cp),
                         'samples':record(samples_path),'sample_count':len(samples),'elapsed_seconds':resource['elapsed_seconds'],
                         'peak_rss_bytes':resource['peak_rss_sample']['rss_bytes'],'peak_pss_bytes':resource['peak_pss_sample']['pss_bytes'],
                         'owned_processes_stopped':resource['owned_processes_stopped'],'passed':resource['passed']}

acquire=read(STAGE/'acquire.json');build=read(STAGE/'build.json')
capsule=read(STAGE/'official-source-capsule.json');inventory=read(NATIVE/'source-acquisition.json')
check('source-exact-ordered-inventory',[x['path'] for x in acquire['files']]==[x['path'] for x in capsule['files']]==[x['path'] for x in inventory['files']])
for actual,original in zip(acquire['files'],capsule['files']):
    path=OWNED/'source'/actual['path'];body=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
    check('saved-source:'+actual['path'],body==original['content'].encode('utf-8') and len(body)==actual['bytes']==original['bytes'] and
          sha(path)==actual['sha256'] and blob==actual['git_blob_sha1']==original['git_blob_sha1'])
check('source-complete-count-bytes',len(acquire['files'])==11 and sum(x['bytes'] for x in acquire['files'])==acquire['materialized_source_bytes']==289300)
check('source-no-extra-files',{str(p.relative_to(OWNED/'source')) for p in (OWNED/'source').rglob('*') if p.is_file()}=={x['path'] for x in acquire['files']})
manifest_path=verify_record(acquire['source_manifest'],'acquisition-manifest-record')
check('acquisition-manifest-content',read(manifest_path)['files']==acquire['files'] and read(manifest_path)['source_capsule_sha256']==sha(STAGE/'official-source-capsule.json'))

command=read(NATIVE/'build-command.json')
receipts={}
for field,key in [('compile_receipt','argv'),('elf_receipt','post_link_elf_read_argv'),('loader_receipt','post_link_loader_list_argv')]:
    p=verify_record(build[field],field);r=read(p);receipts[field]=r
    check(field+'-exact-command',r['argv']==command[key] and r['environment']==command['environment_allowlist'] and r['cwd']==command['cwd'])
    check(field+'-actual-completion',r['complete'] is True and r['exit_code']==0 and not r.get('error'))
    for stream,item in r['raw_streams'].items():verify_record(item,field+'-raw-'+stream)
check('compile-no-diagnostics',all(x['bytes']==0 for x in receipts['compile_receipt']['raw_streams'].values()))
binary=verify_record(build['validator'],'compiled-binary-record');binary_bytes=binary.read_bytes()
check('actual-binary-elf64-x86_64',binary_bytes[:4]==b'\x7fELF' and binary_bytes[4:6]==b'\x02\x01' and struct.unpack_from('<H',binary_bytes,18)[0]==62)
elf_text=Path(receipts['elf_receipt']['raw_streams']['stdout']['path']).read_text()
check('retained-elf-rpath-architecture','ELF64' in elf_text and 'Advanced Micro Devices X86-64' in elf_text and
      str(Path(plan['runtime']['directory'])/'lib/ollama') in elf_text)
metadata=read(NATIVE/'retained-binary-metadata.json');allowed={x['resolved']:x for x in metadata['files']}
loader_text=Path(receipts['loader_receipt']['raw_streams']['stdout']['path']).read_text();loader=[]
for line in loader_text.splitlines():
    line=line.strip()
    if re.fullmatch(r'linux-vdso\.so\.\d+\s+\(0x[0-9a-f]+\)',line):continue
    m=re.fullmatch(r'(?:\S+\s+=>\s+)?(/\S+)\s+\(0x[0-9a-f]+\)',line)
    check('loader-line:'+line,m is not None)
    if m:
        p=Path(m[1]);resolved=str(p.resolve());check('actual-bound-library:'+resolved,resolved in allowed and sha(p)==allowed[resolved]['sha256'])
        loader.append({'path':str(p),'resolved':resolved,'sha256':sha(p)})
check('loader-report-exact',loader==build['resolved_libraries'])

depfile=verify_record(build['compiler_dependency_file'],'actual-dependency-file')
target,sep,remainder=depfile.read_text().replace('\\\n',' ').partition(':');names=shlex.split(remainder)
check('actual-dependency-target-and-uniqueness',sep==':' and shlex.split(target)==[str(binary)] and len(names)==len(set(names))==273)
allowed_roots=(OWNED/'source',Path('/usr/include'),Path('/usr/lib/gcc'),Path('/usr/libexec/gcc'))
dependencies=[];unexpected=[]
for name in names:
    path=Path(name);resolved=path.resolve(strict=True);item={**record(resolved),'compiler_path':name,'allowed_by_original_gate':any(resolved.is_relative_to(x) for x in allowed_roots)}
    dependencies.append(item)
    if not item['allowed_by_original_gate']:
        alias=Path('/usr/include/x86_64-linux-gnu/asm')/resolved.name
        item['system_include_alias']={'path':str(alias),'is_symlink':alias.is_symlink(),'link_text':os.readlink(alias) if alias.is_symlink() else None,'resolved':str(alias.resolve())}
        unexpected.append(item)
        check('uapi-alias:'+resolved.name,alias.is_symlink() and os.readlink(alias)=='../../../lib/linux/uapi/x86/asm/'+resolved.name and alias.resolve()==resolved)
check('exact-five-outside-allowlist',set(x['path'] for x in unexpected)=={'/usr/lib/linux/uapi/x86/asm/'+n for n in ['errno.h','types.h','bitsperlong.h','posix_types.h','posix_types_64.h']})
check('complete-pinned-source-header-closure',{str((OWNED/'source'/x['path']).resolve()) for x in acquire['files'] if x['path']!='LICENSE'}<={x['path'] for x in dependencies})
check('unchanged-failed-build-preserved',build['error']=={'type':'ValueError','message':'Compiler consumed an unexpected source/header: /usr/lib/linux/uapi/x86/asm/errno.h'} and 'sanity' not in build and
      not (OWNED/'probes/sanity.gbnf').exists() and not (STAGE/'native_prepare.json').exists() and not (STAGE/'validate.json').exists())

dep_report={'schema_version':1,'scope':'Read-only inspection of the one actual compiler dependency receipt and existing filesystem header aliases; no compiler rerun.',
            'depfile':record(depfile),'dependency_count':len(dependencies),'unexpected_resolved_headers':unexpected,'all_dependencies':dependencies}
(HERE/'actual-header-dependencies.json').write_text(json.dumps(dep_report,ensure_ascii=False,indent=2)+'\n')
out={'schema_version':1,'scope':'Independent actual acquisition and failed-build receipt/source/data audit; no native process/tool/library/compiler/model execution by reviewer.',
     'plan_sha256':sha(STAGE/'plan.json'),'phase_reports':phase_reports,'checks':checks,'passed':all(x['passed'] for x in checks),
     'actual_build_gate_passed':False,'compiled_binary':record(binary),'dependency_audit_sha256':sha(HERE/'actual-header-dependencies.json'),
     'native_sanity_calls_observed':0,'model_loads_observed':0,'no_retry_or_mutation':True}
(HERE/'retained-stage-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'audit_passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
                  'audit_sha256':sha(HERE/'retained-stage-audit.json'),'dependency_sha256':sha(HERE/'actual-header-dependencies.json')}))

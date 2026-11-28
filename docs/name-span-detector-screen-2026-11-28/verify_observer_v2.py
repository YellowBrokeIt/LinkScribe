"""Repeat essential no-model stops and reproduce a leader-exits orphan safely."""
import ast
import json
import os
from pathlib import Path
import sys

from common import HERE, read_plan, save, sha, utc
from run_phase import monitor

plan = read_plan()
private = Path(plan["runtime"]["owned_root"]) / "private"
output = HERE / "revised-control-probes.json"
if output.exists():
    raise ValueError("Refusing to overwrite revised observer controls.")
orphan_code = (
    "import subprocess,sys,time; "
    "subprocess.Popen([sys.executable,'-c',"
    "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(15)'],"
    "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(.08)"
)
records = []
for name, code, limits, expected in [
    ("normal", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); time.sleep(.2)",
     {"rss_bytes":256*1024**2,"initialization_seconds":2,"case_seconds":2,"total_seconds":3},None),
    ("deadline", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); time.sleep(10)",
     {"rss_bytes":256*1024**2,"initialization_seconds":2,"case_seconds":2,"total_seconds":.3},"aggregate_time_limit"),
    ("memory", "import time; print('PERSON_EVENT {\"event\":\"initialized\"}',flush=True); x=bytearray(128*1024**2); time.sleep(10)",
     {"rss_bytes":96*1024**2,"initialization_seconds":2,"case_seconds":2,"total_seconds":3},"process_tree_memory_limit"),
    ("orphan", orphan_code,
     {"rss_bytes":256*1024**2,"initialization_seconds":2,"case_seconds":2,"total_seconds":10},"owned_child_survived_worker_exit"),
]:
    path=HERE/("control-v2-"+name+".json")
    result=monitor([sys.executable,"-c",code],os.environ.copy(),private/("control-v2-"+name+".log"),path,
                   HERE/("control-v2-"+name+"-samples.jsonl"),limits,
                   {"purpose":"No-model control; synthetic caps do not change detector settings."})
    passed=(result.get("stop_reason")==expected and result["owned_processes_stopped"]
            and result["measurement_complete"] and result["passed"]==(expected is None))
    if name=="orphan":
        passed &= bool(result.get("survivors_at_leader_exit")) and len(result["owned_process_identities"])>=2
    records.append({"control":name,"passed":passed,"report":path.name,"sha256":sha(path),
                    "observed_stop_reason":result.get("stop_reason"),"cleanup_complete":result["owned_processes_stopped"]})

def function_text(path,name):
    text=path.read_text()
    node=next(item for item in ast.parse(text).body if isinstance(item,ast.FunctionDef) and item.name==name)
    return ast.get_source_segment(text,node)

span_unchanged=(function_text(HERE/'native_worker.py','validate_entities')
                ==function_text(HERE/'initial-protocol-review/native_worker.py','validate_entities'))
span_result=json.loads((HERE/'span-control-probes.json').read_text())
report={"created_at":utc(),"passed":all(item['passed'] for item in records) and span_unchanged and span_result['passed'],
        "model_imports":0,"detector_calls":0,"translation_calls":0,"results":records,
        "span_validator_unchanged_from_seven_passing_controls":span_unchanged,
        "span_controls_sha256":sha(HERE/'span-control-probes.json'),
        "observer_sha256":sha(HERE/'run_phase.py'),"worker_sha256":sha(HERE/'native_worker.py')}
save(output,report)
print(json.dumps({"passed":report['passed'],"observer_controls":len(records),"unchanged_span_controls":7,
                  "observer_sha256":report['observer_sha256'],"worker_sha256":report['worker_sha256']}))
raise SystemExit(int(not report['passed']))

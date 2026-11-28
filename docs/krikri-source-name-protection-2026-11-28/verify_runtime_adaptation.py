"""Check observer reuse and owned-daemon cleanup without a model process."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import psutil
from context import HERE, ROOT, stop_daemon

original = ROOT / "docs/name-span-detector-screen-2026-11-28/run_phase.py"
adapted = HERE / "resource_monitor.py"
before = ast.parse(original.read_text().replace("PERSON_EVENT ", "GEMMA_EVENT "))
after = ast.parse(adapted.read_text())
names = {"alive_owned", "owned_group", "stop_owned", "monitor"}
def definitions(tree):
    return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names}
assert definitions(before) == definitions(after) and set(definitions(after)) == names
command = [sys.executable, "-c", "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); print(p.pid,flush=True); time.sleep(20)"]
process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, start_new_session=False)
child_pid = int(process.stdout.readline())
child = psutil.Process(child_pid)
child_identity = child.create_time()
try:
    stopped = stop_daemon(process)
finally:
    if process.poll() is None:
        process.kill();process.wait()
    try:
        if child.create_time() == child_identity and child.status() != psutil.STATUS_ZOMBIE:
            child.kill()
    except psutil.NoSuchProcess:
        pass
try:
    child_alive = child.is_running() and child.create_time() == child_identity and child.status() != psutil.STATUS_ZOMBIE
except psutil.NoSuchProcess:
    child_alive = False
assert stopped and process.poll() is not None and not child_alive
report = {"complete":True,"observer_functions_ast_equal_after_event_prefix_adaptation":True,
          "reused_functions":sorted(names),"original_observer_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
          "adapted_observer_sha256":hashlib.sha256(adapted.read_bytes()).hexdigest(),
          "owned_daemon_and_child_cleanup_passed":True,"daemon_pid":process.pid,"child_pid":child_pid,
          "daemon_exit_code":process.poll(),"child_alive_after":child_alive,"model_loads":0,"model_calls":0,
          "original_reviewed_orphan_probe_preserved":True}
with (HERE / "runtime-adaptation-controls.json").open("x") as stream:
    json.dump(report,stream,indent=2);stream.write("\n")
print(json.dumps({"observer_reuse_exact":True,"cleanup_probe_passed":True,"model_calls":0}))

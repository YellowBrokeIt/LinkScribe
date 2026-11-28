from pathlib import Path
from datetime import datetime, timezone
import json, resource, subprocess, sys, time
report_path=Path(sys.argv[1])
if report_path.exists(): raise RuntimeError('Preserve the existing measurement report.')
command=sys.argv[2:]
start=datetime.now(timezone.utc).isoformat(); tick=time.monotonic()
try:
 result=subprocess.run(command,timeout=900)
 code=result.returncode; status='completed'
except subprocess.TimeoutExpired:
 code=124;status='timeout'
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
report={'scope':'Linux process-resource observation; one isolated probe child, no other child workloads. Not a controlled speed benchmark.','command':command,'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-tick,'execution_status':status,'returncode':code,'peak_rss_kib':usage.ru_maxrss,'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
raise SystemExit(code)

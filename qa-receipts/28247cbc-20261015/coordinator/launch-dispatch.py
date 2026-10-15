import json, os, subprocess, time
from pathlib import Path
r=Path('/workspace/casepath-startup-gate-28247cbc-20261015'); repo=Path('/workspace/casepath-release-ae0-inventory')
e=json.loads((r/'inventory/prepare.json').read_text())['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(r/'harness/dispatch.py')]
record={'candidate':'28247cbc87785b366fa542bb0aa0bd5f37e6c2e3','command':cmd,'cwd':str(repo),'env':e,'started_epoch':time.time(),'launcher_pid':os.getpid()}
with (r/'dispatch-wrapper.log').open('x') as log:
 p=subprocess.Popen(cmd,cwd=repo,env=e,stdout=log,stderr=subprocess.STDOUT)
 record['dispatch_pid']=p.pid;(r/'coordinator/dispatch-command.json').write_text(json.dumps(record,indent=2)+'\n')
 statuscmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(r/'harness/status.py')]
 while True:
  status=subprocess.run(statuscmd,cwd=repo,env=e,capture_output=True,text=True)
  if status.returncode: print(status.stderr,flush=True)
  try: code=p.wait(timeout=20);break
  except subprocess.TimeoutExpired: pass
 subprocess.run(statuscmd,cwd=repo,env=e,capture_output=True,text=True)
 record.update(exit_code=code,finished_epoch=time.time());(r/'coordinator/dispatch-command.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({'dispatch_pid':p.pid,'exit_code':code,'finished_epoch':record['finished_epoch']}),flush=True)
 raise SystemExit(code)

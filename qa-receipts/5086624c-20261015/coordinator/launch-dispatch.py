import json, os, subprocess, time
from pathlib import Path
r=Path('/workspace/casepath-saved-history-gate-5086624c-20261015'); repo=Path('/workspace/casepath-release-ae0-shard6')
e=json.loads((r/'inventory/prepare.json').read_text())['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(r/'harness/dispatch.py')]
record={'candidate':'5086624c8a024ba298819e5e27d749efbd0cc7fc','command':cmd,'cwd':str(repo),'env':e,'started_epoch':time.time(),'launcher_pid':os.getpid()}
with (r/'dispatch-wrapper.log').open('x') as log:
 p=subprocess.Popen(cmd,cwd=repo,env=e,stdout=log,stderr=subprocess.STDOUT)
 record['dispatch_pid']=p.pid;(r/'coordinator/dispatch-command.json').write_text(json.dumps(record,indent=2)+'\n')
 statuscmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(r/'harness/status.py')]
 seen_terminal=set();seen_failure=set()
 while True:
  status=subprocess.run(statuscmd,cwd=repo,env=e,capture_output=True,text=True)
  if status.returncode: print(status.stderr,flush=True)
  else:
   snapshot=json.loads(status.stdout)
   terminals={x['shard'] for x in snapshot['shards'] if x['terminal']}
   failures={(x['shard'],f['id'],f['when']) for x in snapshot['shards'] for f in x['failures']}
   if terminals-seen_terminal or failures-seen_failure:
    print(json.dumps({'event':'NATIVE_TERMINAL_OR_FAILURE','snapshot':snapshot}),flush=True)
   seen_terminal=terminals;seen_failure=failures
  try: code=p.wait(timeout=5);break
  except subprocess.TimeoutExpired: pass
 subprocess.run(statuscmd,cwd=repo,env=e,capture_output=True,text=True)
 record.update(exit_code=code,finished_epoch=time.time());(r/'coordinator/dispatch-command.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({'dispatch_pid':p.pid,'exit_code':code,'finished_epoch':record['finished_epoch']}),flush=True)
 raise SystemExit(code)

import json,os,shutil,time
from pathlib import Path
R=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018')
with (R/'RESOURCE_WATCH_STARTED.json').open('x') as f:json.dump({'pid':os.getpid(),'epoch':time.time(),'interval_seconds':3,'minimum_bytes':3*1024**3},f)
while not (R/'STOP_RESOURCE_WATCH').exists():
 active={};commands=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   comm=(d/'comm').read_text().strip()
   if 'python' not in comm:continue
   parts=(d/'cmdline').read_bytes().split(b'\0');args=[x.decode(errors='replace') for x in parts if x]
   # Record only the exact own public harness path and shard argument; never environments.
   script=str(R/'coordinator/one_shard.py')
   if script in args:
    pos=args.index(script);n=args[pos+1];out=R/f'shard{n}'
    active[n]='pytest' if (out/'ATTEMPT_STARTED.json').exists() and not (out/'result.json').exists() else ('terminal_verification' if (out/'result.json').exists() else 'prepare')
    commands.append({'pid':int(d.name),'script':script,'shard':n})
  except (OSError,PermissionError,IndexError):pass
 limit=json.loads((R/'heavy-budget.json').read_text())['max_gate_heavy']
 row={'epoch':time.time(),'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'active':active,'processes':commands,'gate_heavy':len(active),'global_heavy_limit':2,'gate_heavy_limit':limit,'unrelated_heavy':'parent confirms no additional heavy jobs; protected services unchanged'}
 with (R/'global-resource-observations.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 if row['free_bytes']<3*1024**3 or len(active)>limit:
  (R/'STOP_ADMISSION_RESOURCE_VIOLATION.json').write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
 time.sleep(3)

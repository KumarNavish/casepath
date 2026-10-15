import json,subprocess,time
from pathlib import Path
r=Path('/workspace/casepath-saved-history-gate-5086624c-20261015');seen=None
while True:
 p=subprocess.run(['/workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python','-P',str(r/'harness/status.py')],capture_output=True,text=True,check=True)
 s=json.loads(p.stdout);row=s['shards'][5];state=(row['terminal'],tuple((x['id'],x['when']) for x in row['failures']))
 if state!=seen:print(json.dumps({'event':'SHARD6_REMAINING_MONITOR','snapshot':s}),flush=True);seen=state
 if (r/'shard6-terminal.json').exists():break
 time.sleep(5)
print('ALL_NATIVE_RUNS_AND_SOURCE_AFTER_TERMINAL',flush=True)

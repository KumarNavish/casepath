import json,shutil,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
deadline=time.time()+45
while True:
 summaries=[];terminal=[]
 for n in range(1,7):
  out=R/f'shard{n}';p=out/'reports.jsonl';rows=[]
  if p.exists():
   for line in p.read_text().splitlines():
    try:rows.append(json.loads(line))
    except json.JSONDecodeError:continue
  failures=[x for x in rows if x['outcome']=='failed']
  if failures:print(json.dumps({'FIRST_FAILURE':failures,'shard':n}),flush=True);raise SystemExit(1)
  summary={'shard':n,'passed':sum(x['when']=='call' and x['outcome']=='passed' for x in rows),'skipped':sum(x['outcome']=='skipped' for x in rows),'phases':len(rows),'terminal':(out/'result.json').exists()}
  if summary['terminal']:
   result=json.loads((out/'result.json').read_text());summary.update(exit_code=result['exit_code'],duration_seconds=result['duration_seconds'])
   mark=R/f'coordinator/monitor-shard{n}-terminal.json'
   if not mark.exists():mark.write_text(json.dumps(summary,indent=2)+'\n');terminal.append(summary)
  summaries.append(summary)
 if terminal or time.time()>=deadline:
  print(json.dumps({'epoch':time.time(),'new_terminal':terminal,'free_bytes':shutil.disk_usage('/workspace').free,'shards':summaries}),flush=True);break
 time.sleep(5)

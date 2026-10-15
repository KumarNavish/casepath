import json, shutil, time
from pathlib import Path
R=Path('/workspace/casepath-transport-gate-0a213e47-20261015')
rows=[]
for n in range(1,7):
    p=R/f'shard{n}'
    rs=[]
    if (p/'reports.jsonl').exists():
        for line in (p/'reports.jsonl').read_text().splitlines():
            try: rs.append(json.loads(line))
            except json.JSONDecodeError: pass  # an in-flight final write, never terminal reconciliation
    row={'shard':n,'phases':len(rs),'call_count':sum(x['when']=='call' for x in rs),'failures':[{'id':x['id'],'when':x['when'],'failure':x['failure']} for x in rs if x['outcome']=='failed'],'skipped_count':sum(x['outcome']=='skipped' for x in rs),'terminal':(p/'result.json').exists()}
    if row['terminal']: row['result']=json.loads((p/'result.json').read_text())['exit_code']
    if rs: row['last_report_epoch']=rs[-1]['utc_epoch']
    rows.append(row)
status={'epoch':time.time(),'shards':rows,'free_bytes':shutil.disk_usage('/workspace').free}
with (R/'resource-observations.jsonl').open('a') as f: f.write(json.dumps(status)+'\n')
print(json.dumps(status),flush=True)

from pathlib import Path
import os,json,time,subprocess,shutil
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
with (R/'FINALIZATION_WAITER_STARTED.json').open('x') as f:json.dump({'pid':os.getpid(),'epoch':time.time(),'scope':'Observe original serial driver; no product execution or retry'},f)
while True:
 p=R/'serial-driver-events.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
 if rows and rows[-1]['kind']=='DRIVER_STOP_NO_RETRY':raise RuntimeError('Original driver stopped; no automatic retry')
 if rows and rows[-1]['kind']=='all_six_terminal_and_pushed':break
 time.sleep(3)
for n in range(1,7):
 assert json.loads((R/f'shard{n}/result.json').read_text())['exit_code']==0
 assert json.loads((R/f'completed-shard{n}-runtime-retirement.json').read_text())['pushed_receipts_commit']
(R/'STOP_RESOURCE_WATCH').touch(exist_ok=False)
pid=json.loads((R/'RESOURCE_WATCH_STARTED.json').read_text())['pid']
for _ in range(10):
 p=Path('/proc')/str(pid)/'stat';state=p.read_text().split()[2] if p.exists() else None
 if state is None or state=='Z':break
 time.sleep(1)
assert state is None or state=='Z'
(R/'observers-stopped.json').write_text(json.dumps({'epoch':time.time(),'resource_watch_pid':pid,'resource_watch_state':state,'resource_watch_stopped':True,'all_original_prepares_and_tests_complete':True,'resource_and_scheduler_logs_stable':True,'optional_environment_sampler_not_started':True,'final_workspace_free_bytes':shutil.disk_usage('/workspace').free},indent=2)+'\n')
env=dict(os.environ);env.update(HOME='/workspace/rsh0',TMPDIR='/workspace/rst0',TMP='/workspace/rst0',TEMP='/workspace/rst0',PYTHONDONTWRITEBYTECODE='1')
with (R/'coordinator/finalization-wrapper.log').open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/'coordinator/finalize_receipts.py')],cwd='/workspace',env=env,stdout=f,stderr=subprocess.STDOUT)
(R/'FINALIZATION_TERMINAL.json').write_text(json.dumps({'pid':os.getpid(),'exit_code':p.returncode,'epoch':time.time(),'no_product_execution_by_finalization':True},indent=2)+'\n');assert p.returncode==0

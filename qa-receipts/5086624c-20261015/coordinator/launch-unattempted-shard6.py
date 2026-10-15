import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-saved-history-gate-5086624c-20261015');repo=Path('/workspace/casepath-release-ae0-shard6');out=R/'shard6';env=json.loads((out/'prepare.json').read_text())['env'];SHA='5086624c8a024ba298819e5e27d749efbd0cc7fc'
assert not (out/'ATTEMPT_STARTED.json').exists();events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];assert len([x for x in events if x['type']=='blocked_before_attempt' and x['shard']==6])==1 and not any(x['type']=='start' and x['shard']==6 for x in events);assert shutil.disk_usage('/workspace').free>=3*1024**3
active=[n for n in [4,5] if not (R/f'shard{n}'/'result.json').exists()]+[6];assert len(active)<=3
start={'type':'start','shard':6,'active':active,'free_bytes':shutil.disk_usage('/workspace').free,'tmp':env['TMPDIR'],'home':env['HOME'],'epoch':time.time(),'initial_attempt_after_explicit_resource_recovery':True,'previous_test_execution_or_retry':False}
with (R/'scheduler-events.jsonl').open('a') as f:f.write(json.dumps(start)+'\n')
record={'candidate':SHA,'pid':os.getpid(),'started_epoch':time.time(),'initial_test_execution':True,'prior_block_was_before_ATTEMPT_and_before_test_execution':True,'retry':False,'env':env,'cwd':str(repo)}
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run','6'];record['command']=cmd
with (out/'wrapper.log').open('x') as f:
 p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);record['wrapper_pid']=p.pid;(R/'coordinator/initial-shard6-after-resource-recovery.json').write_text(json.dumps(record,indent=2)+'\n');code=p.wait()
verify=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),'shard6','after']
with (out/'verify-after.log').open('x') as f:proof=subprocess.run(verify,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
row={'shard':6,'exit_code':code,'source_after_exit_code':proof.returncode,'result_path':str(out/'result.json'),'attempt_count':1};active=[n for n in [4,5] if not (R/f'shard{n}'/'result.json').exists()]
with (R/'scheduler-events.jsonl').open('a') as f:f.write(json.dumps({'type':'finish',**row,'active':active,'free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time(),'initial_attempt_after_explicit_resource_recovery':True})+'\n')
record.update(exit_code=code,source_after_exit_code=proof.returncode,finished_epoch=time.time());(R/'coordinator/initial-shard6-after-resource-recovery.json').write_text(json.dumps(record,indent=2)+'\n');(R/'shard6-terminal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
raise SystemExit(code or proof.returncode)

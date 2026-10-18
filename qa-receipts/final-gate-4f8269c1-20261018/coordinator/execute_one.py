from pathlib import Path
import json,os,subprocess,sys,time,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');n=sys.argv[1];assert n in [str(i) for i in range(1,7)]
SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf';p=R/f'shard{n}';repo=Path(json.loads((R/'clone-map.json').read_text())['repos'][n]);prep=json.loads((p/'prepare.json').read_text());env=prep['env']
assert prep['exit_code']==0 and (p/'runtime-before.json').is_file() and not (p/'ATTEMPT_STARTED.json').exists()
assert shutil.disk_usage('/workspace').free>=3*1024**3+2*1024**3
memmax=int(Path('/sys/fs/cgroup/memory.max').read_text());mem=int(Path('/sys/fs/cgroup/memory.current').read_text());assert memmax-mem>2*1024**3
m=json.loads((R/'shard-map.json').read_text());assert m['candidate']==SHA and len(m['shards'][n])>0
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',n]
with (p/'TEST_ADMITTED.json').open('x') as f:json.dump({'candidate':SHA,'epoch':time.time(),'free_disk_bytes':shutil.disk_usage('/workspace').free,'floor_bytes':3*1024**3,'memory_limit_bytes':memmax,'memory_current_bytes':mem,'command':cmd,'once_only':True},f,indent=2)
with (p/'wrapper.log').open('x') as f:
 proc=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 (p/'TEST_PROCESS.json').write_text(json.dumps({'pid':proc.pid,'wrapper_pid':os.getpid(),'candidate':SHA,'epoch':time.time()},indent=2)+'\n')
 while True:
  row={'epoch':time.time(),'free_disk_bytes':shutil.disk_usage('/workspace').free,'memory_current_bytes':int(Path('/sys/fs/cgroup/memory.current').read_text()),'pid':proc.pid,'running':proc.poll() is None}
  with (p/'resource-observations.jsonl').open('a') as obs:obs.write(json.dumps(row)+'\n')
  if not row['running']:break
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:pass
 code=proc.returncode
with (p/'verify-after-wrapper.log').open('x') as f:
 verified=subprocess.run(['/usr/bin/python3',str(R/'coordinator/verify.py'),n,'after'],cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
record={'candidate':SHA,'shard':n,'pytest_wrapper_exit':code,'source_runtime_after_exit':verified.returncode,'epoch':time.time(),'attempt_count':1}
(p/'worker-terminal.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
raise SystemExit(0 if code==verified.returncode==0 else 1)

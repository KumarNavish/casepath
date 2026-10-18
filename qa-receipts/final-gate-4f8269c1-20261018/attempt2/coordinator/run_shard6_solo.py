from pathlib import Path
import json,os,time,subprocess,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018/attempt2');out=R/'shard6';out.mkdir(exist_ok=True)
assert not (out/'SOLO_ADMISSION.json').exists()
for n in ['3','4']:
 terminal=json.loads((R/f'shard{n}/worker-terminal.json').read_text());assert terminal['source_runtime_after_exit']==0
# Observe exact pytest interpreter invocations without exposing arguments/environment values.
pids=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  if p.stat().st_uid!=os.getuid():continue
  a=(p/'cmdline').read_bytes().split(b'\0')
 except (FileNotFoundError,ProcessLookupError,PermissionError):continue
 if any(a[i:i+2]==[b'-m',b'pytest'] for i in range(len(a)-1)):pids.append(int(p.name))
assert not pids,('Other pytest remains active',pids)
def usage():return int([x.split()[1] for x in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines() if x.startswith('usage_usec ')][0])
a=usage();start=time.monotonic();time.sleep(1.5);seconds=time.monotonic()-start;used=(usage()-a)/1e6/seconds
assert used<0.5,('Host not idle enough for sole-heavy run',used)
assert shutil.disk_usage('/workspace').free>3*1024**3+2*1024**3
record={'candidate':'4f8269c1781c4097f79790f39dd0312a2f9f32bf','epoch':time.time(),'prior_attempt2_shards3_4_terminal':True,'other_pytest_pids':pids,'cpu_sample_seconds':seconds,'used_vcpu_before_start':used,'quota_vcpu':4,'free_disk_bytes':shutil.disk_usage('/workspace').free,'diagnostic_not_repeated':True,'Mac_explicitly_authorized_once':True}
with (out/'SOLO_ADMISSION.json').open('x') as f:json.dump(record,f,indent=2)
for script,args in [('harness/prepare_clones.py',['shard6']),('coordinator/verify.py',['6','before']),('coordinator/execute_one.py',['6'])]:
 with (out/(Path(script).stem+'-wrapper.log')).open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/script),*args],stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:print(json.dumps({'stage':script,'exit':p.returncode}),flush=True);raise SystemExit(p.returncode)
print(json.dumps({'shard':6,'attempt':2,'sole_heavy':True,'exit':0}),flush=True)

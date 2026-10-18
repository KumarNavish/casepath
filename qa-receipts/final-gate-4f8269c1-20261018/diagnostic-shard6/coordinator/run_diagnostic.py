from pathlib import Path
import json,time,sys,subprocess,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018/diagnostic-shard6');O=R/'shard6'
def usage():return int([x.split()[1] for x in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines() if x.startswith('usage_usec ')][0])
a=usage();start=time.monotonic();time.sleep(1.5);elapsed=time.monotonic()-start;b=usage();vcpu=(b-a)/1e6/elapsed
mem=int(Path('/sys/fs/cgroup/memory.current').read_text());free=shutil.disk_usage('/workspace').free
record={'epoch':time.time(),'cpu_sample_seconds':elapsed,'used_vcpu':vcpu,'quota_vcpu':4,'spare_vcpu_sampled':4-vcpu,'memory_current_bytes':mem,'memory_limit_bytes':34359738368,'free_disk_bytes':free,'other_heavy_work':'Only authorized attempt2 shards3/4; all original six terminal.','diagnostic_not_gate_admission':True}
with (R/'resource-admission.json').open('x') as f:json.dump(record,f,indent=2)
assert vcpu<3 and free>3*1024**3+500*1024**2 and mem<30*1024**3,record
for script,args in [('harness/prepare_clones.py',['shard6']),('coordinator/verify.py',['6','before']),('coordinator/execute_one.py',['6'])]:
 with (O/(Path(script).stem+'-wrapper.log')).open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/script),*args],stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:print(json.dumps({'stage':script,'exit':p.returncode}),flush=True);raise SystemExit(p.returncode)
print(json.dumps({'diagnostic_exit':0,'gate_admission':False,'resource':record}),flush=True)

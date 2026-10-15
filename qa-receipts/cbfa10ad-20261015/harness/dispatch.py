import concurrent.futures, hashlib, json, os, shutil, subprocess, threading, time
from pathlib import Path

R=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015')
SHA='cbfa10adaee2dd777b2aea3fc888c5ee4fa3f236'
MIN=3*1024**3
lock=threading.Lock(); active=set()
def save(path,obj): path.write_text(json.dumps(obj,indent=2)+'\n')
def event(row):
    row['epoch']=time.time()
    with (R/'scheduler-events.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
def run(n):
    name='shard'+str(n); out=R/name; repo=Path('/workspace/casepath-release-ae0-'+name)
    env=json.loads((out/'prepare.json').read_text())['env']
    with lock:
        assert not (out/'ATTEMPT_STARTED.json').exists(),name+' already attempted'
        free=shutil.disk_usage('/workspace').free
        if free<MIN:
            event({'type':'blocked_before_attempt','shard':n,'free_bytes':free,'required_free_bytes':MIN})
            return {'shard':n,'blocked':'resource headroom','free_bytes':free}
        active.add(n); assert len(active)<=3
        event({'type':'start','shard':n,'active':sorted(active),'free_bytes':free,'tmp':env['TMPDIR'],'home':env['HOME']})
    cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',str(n)]
    with (out/'wrapper.log').open('x') as f:
        result=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
    # No test retry: after-source verification runs after every terminal attempt.
    verify=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),name,'after']
    with (out/'verify-after.log').open('x') as f: proof=subprocess.run(verify,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
    row={'shard':n,'exit_code':result.returncode,'source_after_exit_code':proof.returncode,'result_path':str(out/'result.json'),'attempt_count':1}
    with lock:
        active.remove(n)
        event({'type':'finish',**row,'active':sorted(active),'free_bytes':shutil.disk_usage('/workspace').free})
    return row

proof=json.loads((R/'proof-disjoint-union-before.json').read_text())
assert proof['candidate']==SHA and proof['no_overlap_or_gaps'] and proof['whole_file_partition']
assert json.loads((R/'EXECUTION_AUTHORIZATION.json').read_text())['signal']=='FINAL_GATE_AUTHORIZED'
with (R/'FULL_GATE_PROCESS_STARTED.json').open('x') as f:
    json.dump({'candidate':SHA,'pid':os.getpid(),'epoch':time.time(),'max_active_heavy':3,'no_automatic_retry':True,'proof_sha256':hashlib.sha256((R/'proof-disjoint-union-before.json').read_bytes()).hexdigest()},f,indent=2)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(run,n) for n in range(1,7)]
    rows=[f.result() for f in concurrent.futures.as_completed(futures)]
save(R/'all-shard-terminal.json',{'candidate':SHA,'epoch':time.time(),'results':sorted(rows,key=lambda x:x['shard']),'all_executed':all('exit_code' in x for x in rows),'all_green':all(x.get('exit_code')==0 and x.get('source_after_exit_code')==0 for x in rows)})
print(json.dumps({'all_terminal':rows}),flush=True)

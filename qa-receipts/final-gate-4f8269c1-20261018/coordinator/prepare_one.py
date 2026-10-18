import json,os,subprocess,sys,time,shutil
from pathlib import Path
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf'
n=sys.argv[1];assert n in [str(i) for i in range(1,7)]
out=R/f'shard{n}';out.mkdir(exist_ok=True);repo=Path(json.loads((R/'clone-map.json').read_text())['repos'][n]);control='/workspace/casepath-final-gate-4f8269c1-control-20261018'
assert shutil.disk_usage('/workspace').free>=3*1024**3+500*1024**2
with (out/'CLONE_STARTED.json').open('x') as f:json.dump({'candidate':SHA,'repo':str(repo),'epoch':time.time(),'free_bytes':shutil.disk_usage('/workspace').free},f)
with (out/'clone.log').open('x') as f:
 subprocess.run(['git','clone','--no-hardlinks','--no-checkout',control,str(repo)],stdout=f,stderr=subprocess.STDOUT,check=True)
subprocess.run(['git','-C',str(repo),'remote','set-url','origin','https://github.com/KumarNavish/casepath.git'],check=True)
with (out/'fetch.log').open('x') as f:
 subprocess.run(['git','-C',str(repo),'fetch','--depth=1','origin','codex/casepath-causal-experience-integration-20261009'],stdout=f,stderr=subprocess.STDOUT,check=True)
assert subprocess.check_output(['git','-C',str(repo),'rev-parse','FETCH_HEAD'],text=True).strip()==SHA
subprocess.run(['git','-C',str(repo),'switch','-c',f'codex/final-gate-4f8269c1-shard{n}-20261018',SHA],check=True,stdout=subprocess.DEVNULL)
for script,args in [('harness/prepare_clones.py',[f'shard{n}']),('coordinator/verify.py',[n,'before'])]:
 with (out/(Path(script).stem+'-wrapper.log')).open('x') as f:
  result=subprocess.run(['/usr/bin/python3',str(R/script),*args],stdout=f,stderr=subprocess.STDOUT)
 assert result.returncode==0,(script,result.returncode)
print(json.dumps({'shard':n,'prepared':True,'before_proofs':True,'free_bytes':shutil.disk_usage('/workspace').free}),flush=True)

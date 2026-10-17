from pathlib import Path
import json,os,shutil,subprocess,time
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
repo=Path(json.loads((R/'clone-map.json').read_text())['repos']['1']);out=R/'inventory';out.mkdir(exist_ok=True)
prep=json.loads((R/'shard1/prepare.json').read_text());assert prep['exit_code']==0 and prep['after_status']==''
env=dict(prep['env']);env.update(HOME='/workspace/k65h0',TMPDIR='/workspace/k65t0',TMP='/workspace/k65t0',TEMP='/workspace/k65t0',PYTHONPYCACHEPREFIX=str(out/'pycache'))
for p in [Path(env['HOME']),Path(env['TMPDIR']),out/'pycache']:p.mkdir(exist_ok=True)
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'collect'];start=time.time()
with (out/'collection-wrapper.log').open('x') as stream:result=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
(out/'collection-wrapper-command.json').write_text(json.dumps({'command':cmd,'cwd':str(repo),'env':env,'exit_code':result.returncode,'started_epoch':start,'finished_epoch':time.time()},indent=2)+'\n')
assert result.returncode==0
for source,target in [(repo/'casepath-api/artifacts/artifact-manifest.json',R/'artifact-manifest.json')]:shutil.copy2(source,target)
cmd=['/usr/bin/python3',str(R/'coordinator/inventory.py')]
with (out/'mapping.log').open('x') as stream:result=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
assert result.returncode==0
print((R/'proof-disjoint-union-before.json').read_text(),flush=True)

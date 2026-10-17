import hashlib,json,os,subprocess,sys,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
n=sys.argv[1];phase=sys.argv[2];out=R/f'shard{n}';repo=Path(json.loads((R/'clone-map.json').read_text())['repos'][n])
prep=json.loads((out/'prepare.json').read_text());assert prep['exit_code']==0
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),f'shard{n}',phase]
env=prep['env'];record={'shard':n,'phase':phase,'command':cmd,'cwd':str(repo),'env':env,'started_epoch':time.time()}
with (out/f'verify-{phase}.log').open('x') as stream:result=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode,finished_epoch=time.time());(out/f'verify-{phase}-command.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'shard':n,'phase':phase,'exit_code':result.returncode}))
raise SystemExit(result.returncode)

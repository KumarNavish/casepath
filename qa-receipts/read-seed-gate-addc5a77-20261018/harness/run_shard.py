import json, os, subprocess, sys, time, hashlib
from pathlib import Path
ROOT=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59'
mode=sys.argv[1]
if mode!='collect':
    approval=json.loads((ROOT/'EXECUTION_AUTHORIZATION.json').read_text())
    if approval.get('signal')!='FINAL_GATE_AUTHORIZED' or approval.get('candidate')!=SHA: raise SystemExit('Authorization mismatch')
clones=json.loads((ROOT/'clone-map.json').read_text())['repos']
repo=Path(clones['1' if mode=='collect' else sys.argv[2]])
out=ROOT/'inventory' if mode=='collect' else ROOT/('shard'+sys.argv[2])
for directory in ['home','tmp','pycache','artifact-registry','uv-cache']: (out/directory).mkdir(parents=True,exist_ok=True)
Path('/workspace/rst'+('0' if mode=='collect' else sys.argv[2])).mkdir(exist_ok=True)
Path('/workspace/rsh'+('0' if mode=='collect' else sys.argv[2])).mkdir(exist_ok=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
if head!=SHA or status: raise SystemExit('Frozen checkout identity or cleanliness mismatch: '+head+' '+status)
manifest=json.loads((repo/'casepath/source-manifest.json').read_bytes())
for row in manifest['files']:
    path=repo/row['path']; raw=path.read_bytes()
    if path.is_symlink() or len(raw)!=row['size_bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']: raise SystemExit('Sealed file mismatch: '+row['path'])
temp='/workspace/rst'+('0' if mode=='collect' else sys.argv[2])
home='/workspace/rsh'+('0' if mode=='collect' else sys.argv[2])
env={'HOME':home,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','NODE_PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules','PYTHONHASHSEED':'0','PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPYCACHEPREFIX':str(out/'pycache'),'PYTHONPATH':str(ROOT/'harness')+os.pathsep+str(repo/'casepath-api'),'SOURCE_DATE_EPOCH':'1786406400','TMPDIR':temp,'TMP':temp,'TEMP':temp,'TZ':'UTC','CASEPATH_MODEL_MODE':'deterministic_reference','CASEPATH_SOURCE_COMMIT':SHA,'CASEPATH_DB_PATH':str(out/'casepath.db'),'CASEPATH_ARTIFACT_REGISTRY_PATH':str(out/'artifact-registry'),'CASEPATH_UV':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/uv','CASEPATH_ENV_LOCK_HELD':'','CASEPATH_ENV_READY':'','UV_CACHE_DIR':str(out/'uv-cache'),'UV_LINK_MODE':'copy','CASEPATH_QA_REPOSITORY':str(repo),'CASEPATH_QA_ARTIFACTS':str(out)}
assert 'CASEPATH_READ_SEED_PATH' not in env and not (repo/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists(), 'Real/optional seed must be absent in Cloud gate'
python=repo/'.runtime/casepath-dev-v2/venv/bin/python'
cmd=[str(python),'-P','-m','pytest','-q','-p','no:cacheprovider','-p','casepath_shard_observer']
if mode=='collect': cmd+=['--collect-only','casepath-api/tests','casepath/tools/test_build_deployment_identity.py','casepath/tools/test_casepath_release.py']
else:
    ids=json.loads((ROOT/'shard-map.json').read_text())['shards'][sys.argv[2]]
    (out/'pytest-arguments.txt').write_text('\n'.join(ids)+'\n')
    cmd+=['-o','tmp_path_retention_policy=failed','--junitxml='+str(out/'junit.xml'),'--durations=0','--basetemp='+str(out/'pytest-tmp'),'@'+str(out/'pytest-arguments.txt')]
record={'candidate':SHA,'cwd':str(repo),'command':cmd,'env':env,'started_epoch':time.time(),'manifest_sha256':hashlib.sha256((repo/'casepath/source-manifest.json').read_bytes()).hexdigest()}
if True:
    with (out/'ATTEMPT_STARTED.json').open('x') as latch: latch.write(json.dumps({'candidate':SHA,'started_epoch':record['started_epoch'],'command':cmd,'retry_allowed':False},indent=2))
(out/'command.json').write_text(json.dumps(record,indent=2))
with (out/('collection.log' if mode=='collect' else 'pytest.log')).open('w') as stream:
    completed=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
record['exit_code']=completed.returncode; record['finished_epoch']=time.time(); record['duration_seconds']=record['finished_epoch']-record['started_epoch']
record['after_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
record['after_status']=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
(out/'result.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'exit_code':completed.returncode,'duration':record['duration_seconds'],'head':record['after_head'],'status':record['after_status']}))
raise SystemExit(completed.returncode)

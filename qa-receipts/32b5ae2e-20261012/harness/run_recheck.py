import json, os, subprocess, sys, time, hashlib
from pathlib import Path
ROOT=Path('/tmp/casepath-release-32b-20261012')
SHA='32b5ae2eb4eb84885c875b89c0de091f98a30897'
mode=sys.argv[1]
if mode not in {'isolate','serial'}: raise SystemExit('Expected isolate or serial')
repo=Path('/workspace/casepath-release-ae0-shard4')
out=ROOT/('isolated-failed-node' if mode=='isolate' else 'shard4-serial')
if (out/'command.json').exists(): raise SystemExit('Refusing to overwrite an existing attempt')
for directory in ['home','tmp','pycache','artifact-registry','uv-cache']: (out/directory).mkdir(parents=True,exist_ok=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
if head!=SHA or status: raise SystemExit('Frozen checkout identity or cleanliness mismatch: '+head+' '+status)
manifest=json.loads((repo/'casepath/source-manifest.json').read_bytes())
for row in manifest['files']:
    path=repo/row['path']; raw=path.read_bytes()
    if path.is_symlink() or len(raw)!=row['size_bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']: raise SystemExit('Sealed file mismatch: '+row['path'])
env={'HOME':str(out/'home'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','NODE_PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules','PYTHONHASHSEED':'0','PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPYCACHEPREFIX':str(out/'pycache'),'PYTHONPATH':str(ROOT/'harness')+os.pathsep+str(repo/'casepath-api'),'SOURCE_DATE_EPOCH':'1786406400','TMPDIR':str(out/'tmp'),'TZ':'UTC','CASEPATH_MODEL_MODE':'deterministic_reference','CASEPATH_SOURCE_COMMIT':SHA,'CASEPATH_DB_PATH':str(out/'casepath.db'),'CASEPATH_ARTIFACT_REGISTRY_PATH':str(out/'artifact-registry'),'CASEPATH_UV':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/uv','CASEPATH_ENV_LOCK_HELD':'','CASEPATH_ENV_READY':'','UV_CACHE_DIR':str(out/'uv-cache'),'UV_LINK_MODE':'copy','CASEPATH_QA_REPOSITORY':str(repo),'CASEPATH_QA_ARTIFACTS':str(out)}
python=repo/'.runtime/casepath-dev-v2/venv/bin/python'
cmd=[str(python),'-P','-m','pytest','-q','-p','no:cacheprovider','-p','casepath_shard_observer']
if True:
    ids=['casepath-api/tests/test_autonomous_adversarial_v1.py::test_submit_reassesses_arrival_after_outcome_before_knowledge_publication'] if mode=='isolate' else json.loads((ROOT/'shard-map.json').read_text())['shards']['4']
    (out/'pytest-arguments.txt').write_text('\n'.join(ids)+'\n')
    cmd+=['--junitxml='+str(out/'junit.xml'),'--durations=0','--basetemp='+str(out/'pytest-tmp'),'@'+str(out/'pytest-arguments.txt')]
record={'candidate':SHA,'cwd':str(repo),'command':cmd,'env':env,'started_epoch':time.time(),'attempt':mode,'original_failure_preserved':True,'manifest_sha256':hashlib.sha256((repo/'casepath/source-manifest.json').read_bytes()).hexdigest()}
(out/'command.json').write_text(json.dumps(record,indent=2))
with (out/'pytest.log').open('w') as stream:
    completed=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
record['exit_code']=completed.returncode; record['finished_epoch']=time.time(); record['duration_seconds']=record['finished_epoch']-record['started_epoch']
record['after_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
record['after_status']=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
(out/'result.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'exit_code':completed.returncode,'duration':record['duration_seconds'],'head':record['after_head'],'status':record['after_status']}))
raise SystemExit(completed.returncode)

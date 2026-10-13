import concurrent.futures, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

ROOT=Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
SHA='3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
MANIFEST='ead2ad3ddd10000737985f7db5d704b5e7366da72b54e371624f1a0709ac5c39'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]

def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()

def prepare(name):
    repo=Path('/workspace/casepath-release-ae0-'+name)
    out=ROOT/name
    n='0' if name=='inventory' else name[5:]
    for item in ['pycache','uv-cache']:
        (out/item).mkdir(exist_ok=True)
    env={'HOME':'/workspace/g3ah'+n,'TMPDIR':'/workspace/g3at'+n,'TMP':'/workspace/g3at'+n,'TEMP':'/workspace/g3at'+n,
         'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
         'PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
         'NODE_PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules',
         'PYTHONHASHSEED':'0','PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPYCACHEPREFIX':str(out/'pycache'),'SOURCE_DATE_EPOCH':'1786406400',
         'CASEPATH_MODEL_MODE':'deterministic_reference','CASEPATH_SOURCE_COMMIT':SHA,
         'CASEPATH_UV':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/uv',
         'UV_CACHE_DIR':str(ROOT/'uv-cache'),'UV_LINK_MODE':'copy',
         'UV_PYTHON_INSTALL_DIR':'/workspace/.local/share/uv/python'}
    transport_names=['HTTP_PROXY','HTTPS_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE']
    process_env=dict(env)
    process_env.update({key:os.environ[key] for key in transport_names if key in os.environ})
    assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain')
    assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink()
    assert hashlib.sha256((repo/'casepath/source-manifest.json').read_bytes()).hexdigest()==MANIFEST
    command=['./bin/casepath','prepare']
    record={'candidate':SHA,'cwd':str(repo),'command':command,'env':env,'started_epoch':time.time(),
            'before_head':SHA,'before_status':'','manifest_sha256':MANIFEST,
            'canonical_fetched_head':git(repo,'rev-parse','FETCH_HEAD'),
            'canonical_fetch_source':'/workspace/casepath-operations-coordinator-20261013',
            'original_origin_fetch_failure_log':str(out/'fetch.log'),
            'inherited_transport_variable_names':[key for key in transport_names if key in process_env],
            'internal_launcher_env_contract':'Exact source preserved: stdlib env-i probes omit temp aliases; locked/product env-i uses controlled runtime TMPDIR only.'}
    with (out/'PREPARE_STARTED.json').open('x') as stream:
        json.dump(record,stream,indent=2)
    with (out/'prepare.log').open('w') as stream:
        result=subprocess.run(command,cwd=repo,env=process_env,stdout=stream,stderr=subprocess.STDOUT)
    record.update(exit_code=result.returncode,finished_epoch=time.time(),after_head=git(repo,'rev-parse','HEAD'),after_status=git(repo,'status','--porcelain'))
    record['duration_seconds']=record['finished_epoch']-record['started_epoch']
    (out/'prepare.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({'name':name,'exit_code':result.returncode,'duration_seconds':record['duration_seconds'],'status':record['after_status']}),flush=True)
    return record

before=shutil.disk_usage('/workspace').free
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
    results=list(pool.map(prepare,NAMES))
after=shutil.disk_usage('/workspace').free
summary={'candidate':SHA,'before_free_bytes':before,'after_free_bytes':after,'minimum_headroom_bytes':3*1024**3,
         'adequate_headroom':after>=3*1024**3,'prepared':[r['cwd'] for r in results if r['exit_code']==0],
         'tests_launched':False,'results':[{k:r[k] for k in ['cwd','exit_code','after_head','after_status','duration_seconds']} for r in results]}
(ROOT/'prepare-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary),flush=True)
raise SystemExit(0 if all(r['exit_code']==0 and r['after_head']==SHA and not r['after_status'] for r in results) else 1)

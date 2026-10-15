import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path('/workspace/casepath-startup-gate-28247cbc-20261015')
SHA='28247cbc87785b366fa542bb0aa0bd5f37e6c2e3'
MANIFEST='62bb41a293c3ad95fab19225d4c8d2af4c92937f285726bd2000e4f8bce640a2'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]

def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()

def prepare(name):
    repo=Path('/workspace/casepath-release-ae0-'+name)
    out=ROOT/name
    n='0' if name=='inventory' else name[5:]
    for item in ['pycache','uv-cache']:
        (out/item).mkdir(exist_ok=True)
    env={'HOME':'/workspace/nh'+n,'TMPDIR':'/workspace/nt'+n,'TMP':'/workspace/nt'+n,'TEMP':'/workspace/nt'+n,
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
            'canonical_fetch_source':'/workspace/casepath-recorded-opening-prototype-20261015',
            'canonical_local_fetch_log':str(out/'fetch.log'),
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

if __name__=='__main__':
    assert len(sys.argv)>1
    for name in sys.argv[1:]:
        assert name in NAMES
        result=prepare(name)
        assert result['exit_code']==0 and result['after_head']==SHA and not result['after_status']

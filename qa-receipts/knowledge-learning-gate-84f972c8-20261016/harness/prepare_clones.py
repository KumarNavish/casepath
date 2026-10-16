import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9'
MANIFEST='83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382'
NAMES=[f'shard{i}' for i in range(1,7)]

def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()

def prepare(name):
    repo=Path('/workspace/casepath-release-ae0-'+name)
    out=ROOT/name
    n='0' if name=='inventory' else name[5:]
    for item in ['pycache','uv-cache']:
        (out/item).mkdir(exist_ok=True)
    env={'HOME':'/workspace/kh'+n,'TMPDIR':'/workspace/kt'+n,'TMP':'/workspace/kt'+n,'TEMP':'/workspace/kt'+n,
         'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
         'PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
         'NODE_PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules',
         'PYTHONHASHSEED':'0','PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPYCACHEPREFIX':str(out/'pycache'),'SOURCE_DATE_EPOCH':'1786406400',
         'CASEPATH_MODEL_MODE':'deterministic_reference','CASEPATH_SOURCE_COMMIT':SHA,
         'CASEPATH_UV':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/uv',
         'UV_CACHE_DIR':str(out/'uv-cache'),'UV_LINK_MODE':'copy',
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
            'canonical_fetch_source':'https://github.com/KumarNavish/casepath',
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

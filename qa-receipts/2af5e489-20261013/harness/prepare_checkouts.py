import sys,hashlib,json,os,pathlib,socket,subprocess,time
ROOT=pathlib.Path('/tmp/casepath-release-2af5-20261013')
SHA='2af5e4897284b0b1eab7a82a4e98273ae481b77b'
URL='https://github.com/KumarNavish/casepath.git'
BRANCH='codex/casepath-causal-experience-integration-20261009'
repos=[('inventory',pathlib.Path('/workspace/casepath-release-ae0-inventory'))]+[(f'shard{i}',pathlib.Path(f'/workspace/casepath-release-ae0-shard{i}')) for i in range(1,7)]
def prepare(pair):
 name,repo=pair; out=ROOT/name; out.mkdir(parents=True,exist_ok=True)
 def git(*a): return subprocess.check_output(['git',*a],cwd=repo,text=True).strip()
 record={'repo':str(repo),'old_head':git('rev-parse','HEAD'),'before_status':git('status','--porcelain'),'canonical_url':URL,'branch':BRANCH,'started_epoch':time.time(),'host':socket.gethostname()}
 if record['before_status']: raise RuntimeError('Existing changes '+str(repo))
 with (out/'fetch.log').open('w') as log:
  subprocess.run(['git','-c','credential.helper=!gh auth git-credential','fetch',URL,BRANCH],cwd=repo,stdout=log,stderr=subprocess.STDOUT,check=True)
  record['canonical_fetched_head']=git('rev-parse','FETCH_HEAD')
  if record['canonical_fetched_head']!=SHA: raise RuntimeError('Canonical changed')
  subprocess.run(['git','checkout','--detach',SHA],cwd=repo,stdout=log,stderr=subprocess.STDOUT,check=True)
 for d in ['home','tmp','uv-cache','pycache','artifact-registry']:(out/d).mkdir(exist_ok=True)
 env={'HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC','PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','NODE_PATH':'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules','CASEPATH_UV':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/uv','UV_CACHE_DIR':str(out/'uv-cache'),'UV_LINK_MODE':'copy','PYTHONHASHSEED':'0','SOURCE_DATE_EPOCH':'1786406400','CASEPATH_MODEL_MODE':'deterministic_reference','CASEPATH_SOURCE_COMMIT':SHA}
 record['command']=['./bin/casepath','prepare']; record['env']=dict(env)
 transport_names=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','UV_NATIVE_TLS']
 record['inherited_transport_variable_names']=[k for k in transport_names if k in os.environ]
 env.update({k:os.environ[k] for k in record['inherited_transport_variable_names']})
 with (out/'prepare.log').open('w') as log:r=subprocess.run(record['command'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
 record.update(exit_code=r.returncode,finished_epoch=time.time(),after_head=git('rev-parse','HEAD'),after_status=git('status','--porcelain'),api_tree=git('rev-parse',SHA+':casepath-api'))
 record['duration_seconds']=record['finished_epoch']-record['started_epoch']
 (out/'prepare.json').write_text(json.dumps(record,indent=2))
 print(json.dumps({'name':name,'exit_code':r.returncode,'seconds':record['duration_seconds'],'head':record['after_head'],'status':record['after_status']}),flush=True)
 if r.returncode or record['after_status'] or record['after_head']!=SHA:raise RuntimeError('Preparation failed '+name)
 return record
selected=set(sys.argv[1:])
records=json.loads((ROOT/'preparation-summary.json').read_text()) if (ROOT/'preparation-summary.json').exists() else []
for pair in repos:
 if selected and pair[0] not in selected: continue
 record=prepare(pair)
 records=[r for r in records if r['repo']!=record['repo']]+[record]
 (ROOT/'preparation-summary.json').write_text(json.dumps(records,indent=2))

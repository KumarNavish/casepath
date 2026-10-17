from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
SHA='65a796a5dfb21f4cdbe0a3d1a4925b931710b30c';MAN='6fec138ef5f8eacff8cc4fc19f0084f61b81fde81c2a37c300708c24b5eb2a2c'
assert json.loads((R/'HEADROOM.json').read_text())['runtime_floor_bytes']==3*1024**3
assert shutil.disk_usage('/workspace').free>=3*1024**3+300*1024**2
for name in ['k65h0','k65t0']:Path('/workspace',name).mkdir(exist_ok=True)
base_env={'HOME':'/workspace/k65h0','TMPDIR':'/workspace/k65t0','TMP':'/workspace/k65t0','TEMP':'/workspace/k65t0','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'}
transport=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS']
env=dict(base_env);env.update({k:os.environ[k] for k in transport if k in os.environ})
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,env=env,text=True).strip()
rows=[]
for n,path in json.loads((R/'clone-map.json').read_text())['repos'].items():
 repo=Path(path);out=R/f'shard{n}';out.mkdir(exist_ok=False)
 assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink() and not (repo/'.git/objects/info/alternates').exists()
 assert not git(repo,'status','--porcelain')
 refs=git(repo,'for-each-ref','--format=%(refname) %(objectname)').splitlines();prior=git(repo,'rev-parse','HEAD');branch=git(repo,'branch','--show-current')
 cmd=['git','fetch','origin','codex/casepath-causal-experience-integration-20261009'];start=time.time()
 with (out/'fetch.log').open('x') as stream:p=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
 fetch={'command':cmd,'cwd':str(repo),'env':base_env,'inherited_transport_names':[k for k in transport if k in env],'started_epoch':start,'finished_epoch':time.time(),'exit_code':p.returncode}
 (out/'fetch-command.json').write_text(json.dumps(fetch,indent=2)+'\n');assert p.returncode==0
 assert git(repo,'rev-parse','FETCH_HEAD')==SHA
 git(repo,'switch','--detach',SHA)
 assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain')
 assert hashlib.sha256((repo/'casepath/source-manifest.json').read_bytes()).hexdigest()==MAN
 # Branch refs remain untouched; remote refs may advance only through the canonical fetch.
 after=dict(line.split(' ',1) for line in git(repo,'for-each-ref','--format=%(refname) %(objectname)').splitlines())
 for line in refs:
  ref,value=line.split(' ',1)
  if ref.startswith('refs/heads/'):assert after[ref]==value
 record={'logical_shard':n,'repo':str(repo),'head':SHA,'status':'','prior_head':prior,'prior_branch':branch,'prior_refs_preserved':refs,'normal_clone':True,'no_alternates':True,'manifest_sha256':MAN,'canonical_fetched_head':SHA,'canonical_fetch_log':str(out/'fetch.log')}
 (out/'checkout.json').write_text(json.dumps(record,indent=2)+'\n');rows.append(record)
 for prefix in ['k65h','k65t']:Path('/workspace',prefix+n).mkdir(exist_ok=True)
(R/'canonical-fetch.json').write_text(json.dumps({'candidate':SHA,'manifest_sha256':MAN,'file_count':1712,'clones':rows},indent=2)+'\n')
print(json.dumps({'candidate':SHA,'normal_clones':6,'free_bytes':shutil.disk_usage('/workspace').free}),flush=True)

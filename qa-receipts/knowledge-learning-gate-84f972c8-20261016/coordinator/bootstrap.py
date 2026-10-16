import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
P=Path('/workspace/casepath-transport-gate-evidence-git-20261015/qa-receipts/b8616d4c-20261016')
OLDROOT='/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016'
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9'
OLD='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
MAN='83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382'
OM='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
URL='https://github.com/KumarNavish/casepath.git'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
assert os.uname().nodename=='656813ef2295'
assert git(P.parents[1],'rev-parse','HEAD')=='474c63348f40355c555886faaf5fb1d612aecc9a'
provenance=[]
for source in sorted((P/'harness').glob('*.py')):
 text=source.read_text().replace(OLDROOT,str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/bh','/workspace/kh').replace('/workspace/bt','/workspace/kt')
 target=R/'harness'/source.name;target.write_text(text)
 provenance.append({'source':str(source),'prior_sha256':digest(source),'adapted_sha256':digest(target),'changes':'Exact candidate/manifest/evidence root and isolated short HOME/TMP aliases only'})
save(R/'harness-provenance.json',provenance)
for file in ['mac-ids.txt','known-skips.json']:shutil.copy2(P/file,R/file)
assert digest(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
save(R/'PREPARATION_AUTHORIZATION.json',{'candidate':SHA,'signal':'NORMAL_PREPARE_FRESH_COLLECTION','source_files':1709,'manifest_sha256':MAN,'user_authorized':True,'epoch':time.time()})
save(R/'EXECUTION_AUTHORIZATION.json',{'candidate':SHA,'signal':'FINAL_GATE_AUTHORIZED','user_authorized':True,'max_heavy_entire_host':3,'resource_floor_bytes':3*1024**3,'retry_allowed':False,'new_skips_allowed':False,'epoch':time.time()})
canonical=[]
for n in range(1,7):
 repo=Path(f'/workspace/casepath-release-ae0-shard{n}');out=R/f'shard{n}';out.mkdir()
 assert not git(repo,'status','--porcelain') and (repo/'.git').is_dir() and not (repo/'.git').is_symlink()
 prior=git(repo,'rev-parse','HEAD');refs=git(repo,'for-each-ref','--format=%(refname) %(objectname)').splitlines()
 branch=git(repo,'branch','--show-current')
 # Preserve every prior branch/ref; no integration branch is moved.
 if branch:
  remote=subprocess.check_output(['git','ls-remote',URL,'refs/heads/'+branch],cwd=repo,text=True).split()
  if remote:assert remote[0]==prior,(n,branch,prior,remote)
 git(repo,'remote','set-url','origin',URL)
 with (out/'fetch.log').open('x') as f:subprocess.run(['git','fetch','origin','codex/casepath-causal-experience-integration-20261009'],cwd=repo,stdout=f,stderr=subprocess.STDOUT,check=True)
 assert git(repo,'rev-parse','FETCH_HEAD')==SHA
 git(repo,'switch','--detach',SHA)
 assert not git(repo,'status','--porcelain') and digest(repo/'casepath/source-manifest.json')==MAN
 row={'shard':n,'repo':str(repo),'head':SHA,'status':'','prior_head':prior,'prior_branch':branch,'prior_refs_preserved':refs,'normal_clone':True,'canonical_url':URL,'manifest_sha256':MAN}
 save(out/'checkout.json',row);canonical.append(row)
 for prefix in ['kh','kt']:Path(f'/workspace/{prefix}{n}').mkdir(exist_ok=True)
save(R/'canonical-fetch.json',{'candidate':SHA,'manifest_sha256':MAN,'files':1709,'clones':canonical})
# Compare the candidate bytes against the separately pushed contributor commits.
repo=Path('/workspace/casepath-release-ae0-shard1');proof=[]
for n,commit,scope in [(6,'6064e7ad1519cfc6d272254e78e4b522a144088b','casepath-api'),(5,'82afc52156b160135047db65daf4418ac1c8352c','casepath/assets')]:
 owner=Path(f'/workspace/casepath-release-ae0-shard{n}')
 paths=subprocess.check_output(['git','diff','--name-only',OLD,commit,'--',scope],cwd=owner,text=True).splitlines()
 for file in paths:
  prior=subprocess.check_output(['git','show',commit+':'+file],cwd=owner);current=(repo/file).read_bytes();assert prior==current,file
  proof.append({'path':file,'owner_commit':commit,'sha256':hashlib.sha256(current).hexdigest(),'byte_equal':True})
save(R/'contributor-source-equality.json',proof)
save(R/'resource-before.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'launch_floor_bytes':3*1024**3,'max_heavy':3,'epoch':time.time()})
print(json.dumps({'candidate':SHA,'normal_clones':6,'contributor_paths_verified':len(proof),'free_bytes':shutil.disk_usage('/workspace').free}),flush=True)

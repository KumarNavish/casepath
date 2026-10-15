import hashlib,json,os,shutil,stat,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
P=Path('/workspace/casepath-saved-history-gate-5086624c-20261015')
G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
SHA='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
OLD='5086624c8a024ba298819e5e27d749efbd0cc7fc'
MAN='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
OM='39f03a9ebb1287c5e03f57a444ea97bb079dc44e84cff90a86805c19fba35c3f'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
assert os.uname().nodename=='656813ef2295'
assert git(G,'rev-parse','--verify','HEAD^{commit}')=='629ba83da9e835b4c5064c05898b4924a7210043'
url=git(G,'remote','get-url','origin')
remote=subprocess.check_output(['git','ls-remote',url,'refs/heads/qa-receipts/5086624c-20261015'],cwd=G,text=True).split()[0]
assert remote==git(G,'rev-parse','HEAD')
raw=json.loads((P/'raw-bundle.json').read_text());assert digest(Path(raw['archive']))==raw['archive_sha256']
assert digest(G/'qa-receipts/5086624c-20261015/raw-evidence.tar.gz')==raw['archive_sha256']
save(R/'PREPARATION_AUTHORIZATION.json',{'candidate':SHA,'signal':'NORMAL_PREPARE_FRESH_COLLECTION','source_files':1709,'manifest_sha256':MAN,'root_explicit':True,'epoch':time.time()})
save(R/'EXECUTION_AUTHORIZATION.json',{'candidate':SHA,'signal':'FINAL_GATE_AUTHORIZED','root_explicit_GO':True,'max_heavy_entire_host':3,'resource_floor_bytes':3*1024**3,'retry_allowed':False,'new_skips_allowed':False,'serial_scheduling_approved':True,'epoch':time.time()})
before=shutil.disk_usage('/workspace').free;records=[]
for n in range(2,7):
 repo=Path('/workspace/casepath-release-ae0-shard'+str(n)); oldout=P/f'shard{n}'
 assert git(repo,'rev-parse','HEAD')==OLD and not git(repo,'status','--porcelain')
 for rel in ['result.json','source-before/capsule-verification.json','source-after/capsule-verification.json','source-before/CAPSULE_RECEIPT.json','source-after/CAPSULE_RECEIPT.json','prepare.json','junit.xml','reports.jsonl']:
  assert digest(oldout/rel)==digest(G/'qa-receipts/5086624c-20261015'/f'shard{n}'/rel),rel
 result=json.loads((oldout/'result.json').read_text());assert result['exit_code']==0 and result['candidate']==OLD
 proof=json.loads((oldout/'source-after/capsule-verification.json').read_text());assert proof['head']==OLD and proof['manifest_sha256']==OM and proof['source_artifact_static_bindings_verified'] and proof['status']==''
 capsule=repo/'.runtime/casepath-dev-v2/source-capsules'/OM;receipt=capsule/'CAPSULE_RECEIPT.json'
 assert digest(receipt)==proof['capsule_receipt_file_sha256']
 manifest=json.loads((repo/'casepath/source-manifest.json').read_text());assert digest(repo/'casepath/source-manifest.json')==OM
 for row in manifest['files']:
  for root in [repo,capsule]:
   p=root/row['path'];assert not p.is_symlink() and p.stat().st_size==row['size_bytes'] and digest(p)==row['sha256'],str(p)
 venv=repo/'.runtime/casepath-dev-v2/venv';out=R/'retirement-receipts'/f'old-shard{n}';out.mkdir()
 shutil.copy2(receipt,out/'CAPSULE_RECEIPT.json')
 shutil.copy2(venv/'pyvenv.cfg',out/'pyvenv.cfg')
 env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']}
 for k,v in {'HOME':f'/workspace/bh{n}','TMPDIR':f'/workspace/bt{n}','TMP':f'/workspace/bt{n}','TEMP':f'/workspace/bt{n}'}.items():
  Path(v).mkdir(exist_ok=True);env[k]=v
 cmd=[str(venv/'bin/python'),'-P','-c','import importlib.metadata,json,sys; print(json.dumps({"version":sys.version,"packages":sorted((x.metadata["Name"],x.version) for x in importlib.metadata.distributions())},sort_keys=True))']
 packages=subprocess.check_output(cmd,cwd=repo,env=env,text=True);(out/'python-packages.json').write_text(packages)
 for rel in ['source-after/capsule-verification.json','result.json','prepare.json']:shutil.copy2(oldout/rel,out/Path(rel).name)
 record={'shard':n,'prior_candidate':OLD,'prior_manifest_sha256':OM,'capsule_receipt_sha256':digest(receipt),'source_proof_sha256':digest(oldout/'source-after/capsule-verification.json'),'durable_evidence_commit':remote,'prior_raw_archive_sha256':raw['archive_sha256'],'paths':[str(capsule),str(venv)],'source_files_current_and_capsule_verified':1709,'runtime_package_receipt':str(out/'python-packages.json'),'test_exit_code':0}
 records.append(record)
archive=R/'retirement-receipts'/'old-completed-runtimes-proofs.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted((R/'retirement-receipts').glob('old-shard*')):tar.add(p,arcname=p.name)
with tarfile.open(archive,'r:gz') as tar:
 for member in tar.getmembers():
  if member.isfile():assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==digest(R/'retirement-receipts'/member.name)
save(R/'old-runtime-retirement-before.json',{'candidate':SHA,'before_free_bytes':before,'archive':str(archive),'archive_sha256':digest(archive),'records':records,'source_Git_raw_receipts_unique_failed_fixtures_journals_preserved':True})
for record in records:
 for s in record['paths']:
  p=Path(s);repo=p.parents[3] if p.name==OM else p.parents[2]
  assert '/.runtime/casepath-dev-v2/' in s and (p.name==OM or p.name=='venv') and not p.is_symlink()
  # Immutable source capsules become writable only to retire a proven reproducible copy.
  for root,dirs,files in os.walk(p):os.chmod(root,0o700)
  shutil.rmtree(p)
save(R/'old-runtime-retirement.json',{'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'records':records,'archive_sha256':digest(archive),'preserved':'All checkout source, Git refs and objects, original raw receipts, unique/failed fixtures, journals, runtime home/tmp/boots'})
provenance=[]
for name in ['prepare_clones.py','verify_prepared_capsules.py','run_shard.py','casepath_shard_observer.py','status.py','finalize.py','bundle.py']:
 source=P/'harness'/name;rawtext=source.read_text();changed=rawtext.replace(str(P),str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/qt','/workspace/bt').replace('/workspace/qh','/workspace/bh')
 if name=='run_shard.py':changed=changed.replace("Path('/workspace/casepath-release-ae0-shard6') if mode=='collect'", "Path('/workspace/casepath-release-ae0-shard1') if mode=='collect'")
 target=R/'harness'/name;target.write_text(changed);provenance.append({'file':name,'prior':str(source),'prior_sha256':digest(source),'adapted_sha256':digest(target),'changes':'Candidate, manifest, evidence root, short scoped HOME/TMP aliases; collection uses physical shard1'})
save(R/'harness-provenance.json',provenance)
for filename in ['mac-ids.txt','known-skips.json'] :shutil.copy2(P/filename,R/filename)
canonical=[]
for n in range(1,7):
 repo=Path('/workspace/casepath-release-ae0-shard'+str(n));out=R/f'shard{n}';out.mkdir();assert not git(repo,'status','--porcelain')
 prior=git(repo,'rev-parse','HEAD');refs=git(repo,'for-each-ref','--format=%(refname) %(objectname)','refs/heads').splitlines()
 git(repo,'branch',f'codex/b861-preserved-prior-shard{n}-20261016',prior)
 with (out/'fetch.log').open('x') as f:subprocess.run(['git','fetch',url,'codex/casepath-causal-experience-integration-20261009'],cwd=repo,stdout=f,stderr=subprocess.STDOUT,check=True)
 assert git(repo,'rev-parse','--verify','FETCH_HEAD^{commit}')==SHA
 branch=f'codex/b861-fullgate-shard{n}-20261016';git(repo,'switch','-c',branch,SHA)
 assert not git(repo,'status','--porcelain') and digest(repo/'casepath/source-manifest.json')==MAN
 row={'shard':n,'repo':str(repo),'branch':branch,'head':SHA,'status':'','prior_head':prior,'prior_refs_preserved':refs,'normal_clone':(repo/'.git').is_dir(),'canonical_fetch_host':'github.com','manifest_sha256':MAN}
 save(out/'checkout.json',row);canonical.append(row)
(R/'inventory').mkdir()
for n in range(7):
 for p in [Path(f'/workspace/bh{n}'),Path(f'/workspace/bt{n}')]:p.mkdir(exist_ok=True)
save(R/'canonical-fetch.json',{'candidate':SHA,'manifest_sha256':MAN,'files':1709,'clones':canonical})
save(R/'resource-before.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'launch_floor_bytes':3*1024**3,'max_heavy':3,'active_gate_test_processes':0,'epoch':time.time()})
print(json.dumps({'prepared_source_clones':6,'candidate':SHA,'tests_started':False,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'retired_only_prior_proven_ignored_runtime_paths':10}),flush=True)

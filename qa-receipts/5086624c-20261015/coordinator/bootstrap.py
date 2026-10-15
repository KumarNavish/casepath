import hashlib,json,os,shutil,socket,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-saved-history-gate-5086624c-20261015');P=Path('/workspace/casepath-startup-gate-28247cbc-20261015');BASE=Path('/workspace/casepath-transport-gate-0a213e47-20261015');S=Path('/workspace/casepath-entry-wiring-review-20261015')
SHA='5086624c8a024ba298819e5e27d749efbd0cc7fc';MAN='39f03a9ebb1287c5e03f57a444ea97bb079dc44e84cff90a86805c19fba35c3f';OLD='28247cbc87785b366fa542bb0aa0bd5f37e6c2e3';OLDMAN='62bb41a293c3ad95fab19225d4c8d2af4c92937f285726bd2000e4f8bce640a2';NAMES=[f'shard{i}' for i in range(1,7)]
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
assert socket.gethostname()=='656813ef2295' and git(S,'rev-parse','HEAD')==SHA
assert not R.exists();R.mkdir(mode=0o700)
for name in ['harness','coordinator','retirement-receipts','review','inventory']+NAMES:(R/name).mkdir(mode=0o700)
for n in range(7):
 for prefix in ['qh','qt']:
  p=Path('/workspace/'+prefix+str(n));assert not p.exists();p.mkdir(mode=0o700)
for prefix in ['qh','qt']:
 p=Path('/workspace/'+prefix+'h');assert not p.exists();p.mkdir(mode=0o700)
save(R/'resource-before.json',{'epoch':time.time(),'host':socket.gethostname(),'workspace_free':shutil.disk_usage('/workspace').free,'tmp_free':shutil.disk_usage('/tmp').free,'environment_names':sorted(os.environ),'protected_server':subprocess.check_output(['ps','-p','595190','-o','pid,ppid,comm'],text=True)})
# Old actual before/after/native receipts are already exported and remotely pushed at26548cdd.
archive=Path('/workspace/casepath-startup-gate-28247cbc-20261015-raw-evidence.tar.gz');oldraw=json.loads((P/'raw-bundle.json').read_text());assert digest(archive)==oldraw['archive_sha256']
retired=[];beforefree=shutil.disk_usage('/workspace').free
for name in ['inventory','shard4','shard5','shard6']:
 repo=Path('/workspace/casepath-release-ae0-'+name);proofpath=P/name/'source-after/capsule-verification.json';proof=json.loads(proofpath.read_text());before=json.loads((P/name/'source-before/capsule-verification.json').read_text());assert proof['capsule_receipt']==before['capsule_receipt'] and proof['source_artifact_static_bindings_verified']
 cap=repo/'.runtime/casepath-dev-v2/source-capsules'/OLDMAN;receipt=cap/'CAPSULE_RECEIPT.json';assert digest(receipt)==proof['capsule_receipt_file_sha256']
 kept=R/'retirement-receipts'/(name+'-'+OLDMAN+'-CAPSULE_RECEIPT.json');shutil.copyfile(receipt,kept)
 targets=[cap]+([repo/'.runtime/casepath-dev-v2/venv'] if name=='inventory' else [])
 for target in targets:
  assert target.is_dir() and not target.is_symlink();size=sum(p.stat().st_size for p in target.rglob('*') if p.is_file() and not p.is_symlink())
  for p in target.rglob('*'):
   if p.is_dir() and not p.is_symlink():p.chmod(0o700)
  target.chmod(0o700);shutil.rmtree(target);retired.append({'path':str(target),'bytes':size,'proof':str(proofpath),'proof_sha256':digest(proofpath),'retained_receipt':str(kept),'receipt_sha256':proof['capsule_receipt_file_sha256'],'durable_evidence_commit':'26548cdd4e2bc237a742de985bbec3e821d8d5a3','raw_archive':str(archive),'raw_archive_sha256':oldraw['archive_sha256']})
save(R/'replacement-proven-retirement.json',{'before_free_bytes':beforefree,'after_free_bytes':shutil.disk_usage('/workspace').free,'paths':retired,'preserved':'Old28247 raw proof/source/Git, failed shard4 fixture, runtime home/tmp/boots/journals; existing shard4/5/6 venvs reused by normal prepare'})
provenance=[]
for name in ['prepare_clones.py','run_shard.py','verify_prepared_capsules.py','casepath_shard_observer.py','status.py','dispatch.py']:
 source=P/'harness'/name;target=R/'harness'/name;s=source.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OLDMAN,MAN).replace('/workspace/nh','/workspace/qh').replace('/workspace/nt','/workspace/qt').replace('1708','1709').replace('1709,25,38','1709,25,39').replace('1709, 25, 38','1709, 25, 39').replace('== 38','== 39').replace('/workspace/casepath-recorded-opening-prototype-20261015',str(S));target.write_text(s);provenance.append({'path':target.relative_to(R).as_posix(),'prior_path':str(source),'prior_sha256':digest(source),'adapted_sha256':digest(target)})
p=R/'harness/prepare_clones.py';s=p.read_text().replace("NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]","NAMES=[f'shard{i}' for i in range(1,7)]").replace("'UV_CACHE_DIR':str(ROOT/'uv-cache')","'UV_CACHE_DIR':'/workspace/.cache/uv'");p.write_text(s)
p=R/'harness/run_shard.py';s=p.read_text().replace("Path('/workspace/casepath-release-ae0-inventory') if mode=='collect'","Path('/workspace/casepath-release-ae0-shard6') if mode=='collect'");p.write_text(s)
for name in ['known-skips.json','mac-ids.txt']:shutil.copyfile(BASE/name,R/name)
for name in NAMES:
 repo=Path('/workspace/casepath-release-ae0-'+name);assert (repo/'.git').is_dir() and git(repo,'rev-parse','HEAD')==OLD and not git(repo,'status','--porcelain')
 commands=[['git','fetch',str(S),SHA],['git','checkout','--detach',SHA]]
 with (R/name/'fetch.log').open('x') as f:
  for cmd in commands:subprocess.run(cmd,cwd=repo,check=True,stdout=f,stderr=subprocess.STDOUT)
 assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain') and digest(repo/'casepath/source-manifest.json')==MAN
 save(R/name/'checkout.json',{'candidate':SHA,'cwd':str(repo),'commands':commands,'status':'','normal_clone':True,'manifest_sha256':MAN})
repo=Path('/workspace/casepath-release-ae0-shard6')
for source,target in [('casepath/source-manifest.json','source-manifest.json'),('casepath-api/artifacts/artifact-manifest.json','artifact-manifest.json')]:shutil.copyfile(repo/source,R/target)
for ext in ['md','json']:
 p=Path('/workspace/casepath-cold-start-review-20261015/saved-history-root-review-5086624.'+ext);shutil.copyfile(p,R/'review'/p.name)
save(R/'EXECUTION_AUTHORIZATION.json',{'signal':'PREPARATION_AND_COLLECTION_ONLY_HOLD_TEST_LAUNCH','candidate':SHA,'manifest_sha256':MAN,'prepared_physical_clones':6,'collection_physical_clone':'shard6','max_heavy_active':3,'no_test_run_authorized':True,'source':'Root explicitly authorized prepare+freshcollect only; actualpytestRUN requires separate browserGO'})
save(R/'canonical-fetch.json',{'candidate':SHA,'manifest_sha256':MAN,'local_canonical_source':str(S),'canonical_working_head_preserved':git(S,'rev-parse','HEAD'),'isolated_normal_clones':6,'collection_reuses':'shard6'})
for row in provenance:row['adapted_sha256']=digest(R/row['path'])
save(R/'harness-provenance.json',provenance);shutil.copyfile('/workspace/saved-50866-gate-init.py',R/'coordinator/bootstrap.py')
print(json.dumps({'root':str(R),'prepared_physical_clones':6,'collection_reuses':'shard6','checked_out_exact':SHA,'free_bytes_before_prepares':shutil.disk_usage('/workspace').free,'test_run':'HOLD','prepare_dependency_cache':'/workspace/.cache/uv'}),flush=True)

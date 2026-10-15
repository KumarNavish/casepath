import ast,hashlib,json,os,shutil,socket,stat,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-startup-gate-28247cbc-20261015');P=Path('/workspace/casepath-transport-gate-0a213e47-20261015');C=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015');S=Path('/workspace/casepath-recorded-opening-prototype-20261015')
SHA='28247cbc87785b366fa542bb0aa0bd5f37e6c2e3';MAN='62bb41a293c3ad95fab19225d4c8d2af4c92937f285726bd2000e4f8bce640a2';OLD='0a213e471d70dbc63df2e0fcb3a62049ec5183aa';OLDMAN='8261e891c9403d486bdb60d1abe485ae56a6b6e556bb9b3125a3702d76e72331';CBFA='cbfa10adaee2dd777b2aea3fc888c5ee4fa3f236'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
assert socket.gethostname()=='656813ef2295';assert not R.exists();R.mkdir(mode=0o700)
for name in ['harness','coordinator','retirement-receipts']+NAMES:(R/name).mkdir(mode=0o700)
for n in range(7):
 for prefix in ['nh','nt']:
  p=Path('/workspace/'+prefix+str(n));assert not p.exists();p.mkdir(mode=0o700)
save(R/'resource-before.json',{'epoch':time.time(),'host':socket.gethostname(),'workspace_free':shutil.disk_usage('/workspace').free,'tmp_free':shutil.disk_usage('/tmp').free,'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'environment_names':sorted(os.environ),'protected_server':subprocess.check_output(['ps','-p','595190','-o','pid,ppid,comm'],text=True)})
# Index retained raw proofs; preserve source and all gate evidence intact.
proofindex={}
for root in Path('/workspace').iterdir():
 if root.is_dir() and 'gate' in root.name:
  for p in root.glob('*/source-*/capsule-verification.json'):
   try:x=json.loads(p.read_text())
   except (OSError,ValueError):continue
   if x.get('manifest_sha256') and x.get('capsule_receipt_file_sha256'):proofindex.setdefault(x['manifest_sha256'],[]).append((p,x))
retired=[];free_before=shutil.disk_usage('/workspace').free
for name in NAMES:
 repo=Path('/workspace/casepath-release-ae0-'+name);assert (repo/'.git').is_dir() and git(repo,'rev-parse','HEAD')==CBFA and not git(repo,'status','--porcelain')
 for cap in sorted((repo/'.runtime/casepath-dev-v2/source-capsules').iterdir()):
  assert cap.is_dir() and not cap.is_symlink() and len(cap.name)==64
  rr=(cap/'CAPSULE_RECEIPT.json').read_bytes();receipt=json.loads(rr);semantic=dict(receipt);assert semantic.pop('receipt_sha256')==digest(canonical(semantic))
  matches=[(p,x) for p,x in proofindex.get(cap.name,[]) if x['capsule_receipt_file_sha256']==digest(rr)]
  assert matches,(name,cap.name,'no prior verified proof')
  matches.sort(key=lambda t:(('source-after' not in str(t[0])),('/'+name+'/' not in str(t[0])),str(t[0])))
  proofpath,proof=matches[0]
  source_raw=(cap/'casepath/source-manifest.json').read_bytes();assert digest(source_raw)==cap.name==receipt['source_manifest_file_sha256'];source=json.loads(source_raw)
  assert subprocess.check_output(['git','show',proof['head']+':casepath/source-manifest.json'],cwd=repo)==source_raw
  assert len(source['files'])==source['file_count']==receipt['source_file_count'] and receipt['source_roster_sha256']==digest(canonical(source['files']))
  for row in source['files']:
   p=cap/row['path'];raw=p.read_bytes();assert not p.is_symlink() and len(raw)==row['size_bytes'] and digest(raw)==row['sha256']
  ar=(cap/'casepath-api/artifacts/artifact-manifest.json').read_bytes();assert digest(ar)==receipt['artifact_manifest_file_sha256'];artifact=json.loads(ar);assert len(artifact['files'])==receipt['artifact_file_count']
  for row in artifact['files']:
   p=cap/'casepath-api/artifacts'/row['path'];raw=p.read_bytes();assert not p.is_symlink() and len(raw)==row['size_bytes'] and digest(raw)==row['sha256']
  static=[]
  for p in sorted((cap/'casepath-public').rglob('*')):
   assert not p.is_symlink()
   if p.is_file():
    raw=p.read_bytes();rel=p.relative_to(cap/'casepath-public').as_posix();static.append({'path':rel,'sha256':digest(raw),'size_bytes':len(raw),'executable':bool(p.stat().st_mode&stat.S_IXUSR)})
    if p.name!='deployment.json':assert raw==(cap/'casepath'/rel).read_bytes()
  assert len(static)==receipt['static_file_count'] and digest(canonical(static))==receipt['static_inventory_sha256']
  target=R/'retirement-receipts'/(name+'-'+cap.name);target.mkdir();(target/'CAPSULE_RECEIPT.json').write_bytes(rr);(target/'source-manifest.json').write_bytes(source_raw)
  retired.append({'path':str(cap),'canonical_commit':proof['head'],'prior_raw_proof':str(proofpath),'prior_proof_sha256':digest(proofpath.read_bytes()),'receipt_sha256':digest(rr),'retained_receipt':str(target/'CAPSULE_RECEIPT.json'),'canonical_git_manifest_equal':True,'full_source_artifact_static_hashes_verified':True})
  for p in cap.rglob('*'):
   if p.is_dir():p.chmod(0o700)
  cap.chmod(0o700);shutil.rmtree(cap)
save(R/'replacement-proven-retirement.json',{'before_free_bytes':free_before,'after_free_bytes':shutil.disk_usage('/workspace').free,'paths':retired,'retained':'Git/source, every prior raw gate receipt, venvs, failed/interrupted pytest fixtures, journals; only verified obsolete canonical source capsule runtime bytes removed'})
# Reuse immutable observer and established full-gate harness with exact identity/count/path adaptations.
provenance=[]
for p in [*P.joinpath('harness').glob('*.py'),P/'coordinator/coordinator-reconcile.py']:
 target=R/p.relative_to(P);s=p.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OLDMAN,MAN).replace('/workspace/oh','/workspace/nh').replace('/workspace/ot','/workspace/nt').replace('1706','1708').replace('1708,25,37','1708,25,38').replace('1708, 25, 37','1708, 25, 38').replace("== 37","== 38").replace("/workspace/casepath-stream-transport-20261015",str(S))
 target.write_text(s);provenance.append({'path':target.relative_to(R).as_posix(),'prior_path':str(p),'prior_sha256':digest(p.read_bytes()),'adapted_sha256':digest(target.read_bytes())})
# Separate preparation workers execute only their named clones, sequentially per worker.
p=R/'harness/prepare_clones.py';s=p.read_text().replace('import concurrent.futures, hashlib, json, os, shutil, subprocess, time','import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, time')
a=s.index("before=shutil.disk_usage('/workspace').free")
s=s[:a]+"if __name__=='__main__':\n    assert len(sys.argv)>1\n    for name in sys.argv[1:]:\n        assert name in NAMES\n        result=prepare(name)\n        assert result['exit_code']==0 and result['after_head']==SHA and not result['after_status']\n"
p.write_text(s)
# Current Mac attestation remains pending unless a current exact-candidate receipt is supplied.
p=R/'harness/finalize.py';s=p.read_text().replace("'mac_owner_attested_passed':127","'mac_owner_attested_passed':reconciled['mac_attested_passed']");p.write_text(s)
for name in ['known-skips.json','mac-ids.txt']:shutil.copyfile(P/name,R/name)
assert git(S,'rev-parse','origin/codex/casepath-causal-experience-integration-20261009')==SHA
for name in NAMES:
 repo=Path('/workspace/casepath-release-ae0-'+name);commands=[['git','fetch',str(S),SHA],['git','checkout','--detach',SHA]]
 with (R/name/'fetch.log').open('x') as f:
  for cmd in commands:subprocess.run(cmd,cwd=repo,check=True,stdout=f,stderr=subprocess.STDOUT)
 assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain')
 assert digest((repo/'casepath/source-manifest.json').read_bytes())==MAN
 save(R/name/'checkout.json',{'candidate':SHA,'commands':commands,'cwd':str(repo),'status':'','normal_clone':True,'manifest_sha256':MAN,'source':str(S)})
repo=Path('/workspace/casepath-release-ae0-inventory')
for source,target in [('casepath/source-manifest.json','source-manifest.json'),('casepath-api/artifacts/artifact-manifest.json','artifact-manifest.json')]:shutil.copyfile(repo/source,R/target)
save(R/'canonical-fetch.json',{'candidate':SHA,'manifest_sha256':MAN,'local_canonical_source':str(S),'canonical_remote_integration_ref':git(S,'rev-parse','origin/codex/casepath-causal-experience-integration-20261009'),'canonical_working_head_preserved':git(S,'rev-parse','HEAD'),'isolated_clean_clones':7})
save(R/'EXECUTION_AUTHORIZATION.json',{'signal':'PREPARATION_AND_COLLECTION_ONLY_HOLD_TEST_LAUNCH','candidate':SHA,'manifest_sha256':MAN,'max_heavy_active':3,'no_automatic_retries':True,'mac_attestation':'PENDING','source':'Root relayed new full-gate authorization; actual tests held until root review clearance'})
for row in provenance:row['adapted_sha256']=digest((R/row['path']).read_bytes())
save(R/'harness-provenance.json',provenance)
shutil.copyfile('/workspace/startup-28247-gate-init.py',R/'coordinator/bootstrap.py')
for p in [*R.joinpath('harness').glob('*.py'),R/'coordinator/coordinator-reconcile.py']:ast.parse(p.read_text())
print(json.dumps({'root':str(R),'exact_candidate':SHA,'retired_verified_capsules':len(retired),'free_bytes':shutil.disk_usage('/workspace').free,'test_launch':'HOLD'}),flush=True)

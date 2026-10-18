import hashlib,json,os,pathlib,shutil,subprocess,time
P=pathlib.Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018');R=pathlib.Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');G=pathlib.Path('/workspace/casepath-transport-gate-evidence-git-20261015')
SHA='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd';MAN='98bd51f82f96e146314496cd41255781634d19c407ced1a37221927b91a6b32e';OLD='a89b97bb8eecdd8e98771c99ca879d4e253f7881';OM='416eea6c4831046fca1bab76ec7072bc116cdc2912a169b094341d3a2ee68b0a'
assert os.uname().nodename=='656813ef2295' and not (R/'EXECUTION_AUTHORIZATION.json').exists()
R.mkdir(mode=0o700,exist_ok=True);(R/'coordinator').mkdir(exist_ok=True);(R/'harness').mkdir(exist_ok=True)
def save(f,x): (R/f).write_text(json.dumps(x,indent=2)+'\n')
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert git(G,'rev-parse','HEAD')=='cc395aa627e2063965780c7fb63a0e3a41982ad5' and digest(G/'.git/index')=='0022046a23b158d171f6a239bd7b0f21c23ec4372594997f0b4f7cd7d2ba3153'
protected=pathlib.Path('/workspace/casepath-reference-85a-qa');assert git(protected,'rev-parse','HEAD')=='5fe9a95757c6feaefde02ca239d14df9ec6684ed' and not git(protected,'status','--porcelain')
save('protected-checkouts-before.json',{'source':{'path':str(protected),'head':git(protected,'rev-parse','HEAD'),'status':''},'evidence':{'path':str(G),'head':git(G,'rev-parse','HEAD'),'index_sha256':digest(G/'.git/index')},'focused_evidence_ref':git(G,'ls-remote','origin','refs/heads/qa-receipts/touch-targets-20261018').split()[0],'epoch':time.time()})
files=['casepath_shard_observer.py','prepare_clones.py','run_shard.py','runtime_inventory.py','verify_prepared_capsules.py']
co=['inventory.py','one_shard.py','verify.py','reconcile.py','summarize.py','resource_watch.py','retire_pushed_runtime.py','retire_pushed_cache.py','stage_one.py','export_receipts.py','scan_export.py','bundle.py','finish_audit.py','qualify_final.py','verify_pushed_bundle.py']
provenance=[]
for folder,names in [('harness',files),('coordinator',co)]:
 for name in names:
  src=P/folder/name;raw=src.read_text();new=raw.replace(str(P),str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/a9h','/workspace/tt4h').replace('/workspace/a9t','/workspace/tt4t').replace('qa-receipts/mobile-context-gate-a89b97bb-20261018','qa-receipts/touch-target-gate-4bf9b439-20261018')
  if name=='stage_one.py':new=new.replace('range(3, 7)','range(1, 7)')
  if name=='retire_pushed_cache.py':new=new.replace('range(3, 7)','range(1, 7)')
  if name=='inventory.py':new=new.replace("'prior_candidate':'4a03578bcaecd0cc4948d36747d96ce68e905244'","'prior_candidate':'"+OLD+"'").replace("'global_max_heavy':3","'global_max_heavy':2")
  if name=='resource_watch.py':new=new.replace("'global_heavy_limit':3","'global_heavy_limit':2")
  if name=='summarize.py':new=new.replace('assert max_active<=3','assert max_active<=2').replace("'global_max_heavy':3","'global_max_heavy':2")
  if name=='export_receipts.py':
   new=new.replace("ref+':'+ref","commit+':'+ref")
  (R/folder/name).write_text(new)
  provenance.append({'source':str(src),'source_sha256':digest(src),'target':str(R/folder/name),'target_sha256':digest(R/folder/name)})
save('harness-provenance.json',{'basis':'Reuse immutable prior pinned harness with candidate/root/owned paths, two-heavy limit, current prior inventory and explicit commit push substitutions only','files':provenance})
for f in ['known-skips.json','mac-ids.txt','timing-regression-ids.json','secret-scan-exact-allowlist.json']:
 shutil.copy2(P/f,R/f)
for a,b in [('collected-ids.txt','prior-collected-ids.txt'),('shard-map.json','prior-shard-map.json'),('per-file-durations.json','prior-per-file-durations.json')]:shutil.copy2(P/a,R/'coordinator'/b)
shutil.copy2(P/'coordinator/original2613-collected-ids.txt',R/'coordinator/original2613-collected-ids.txt')
repos=json.loads((P/'clone-map.json').read_text())['repos'];repos['4']='/workspace/casepath-release-ae0-shard2'
save('clone-map.json',{'candidate':SHA,'repos':repos,'source':'Reuse clean independent normal clones, canonical fetch before frozen checkout; protected implementation/failed source excluded','protected_implementation':str(protected),'protected_failed_clone2':'/workspace/casepath-release-ae0-shard5','created_epoch':time.time()})
for n in ['0']+list(repos):
 for prefix in ['tt4h','tt4t']:pathlib.Path('/workspace/'+prefix+n).mkdir(mode=0o700)
for n in repos:(R/('shard'+n)).mkdir(mode=0o700)
(R/'inventory').mkdir(mode=0o700)
save('EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'manifest_sha256':MAN,'source_file_count':1714,'authorization':'Parent explicit exact frozen complete six-Cloud-shard gate once; no retries/new skips/deselection; no product/seal/index changes; raw evidence pushes and reproducible owned runtime retirement only after durable checksummed proof authorized','epoch':time.time()})
save('heavy-budget.json',{'max_gate_heavy':2,'global_max_heavy':2,'min_workspace_free_bytes':3*1024**3,'basis':'At most two heavy processes globally; serial prepare; admission floor3GiB; choose one if disk requires'})
save('initial-resource.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'epoch':time.time()})
save('prior-evidence-preservation.json',{'prior_root':str(P),'prior_raw_archive_sha256':digest(P/'raw-evidence.tar.gz'),'prior_sumfile_sha256':digest(P/'SHA256SUMS'),'prior_remote_commit':'a49b8f2ca9fd55f0dc13a5cb04dc58f2cdaac338','source_and_raw_retained':True})
records=[]
for n,path in repos.items():
 p=pathlib.Path(path);assert (p/'.git').is_dir() and not (p/'.git').is_symlink() and not git(p,'status','--porcelain')
 owned=[]
 for q in pathlib.Path('/proc').iterdir():
  if not q.name.isdigit():continue
  try:
   cwd=os.readlink(q/'cwd')
   if cwd==path or cwd.startswith(path+'/'):
    comm=(q/'comm').read_text().strip()
    if comm not in ['git']:owned.append({'pid':int(q.name),'comm':comm,'cwd':cwd})
  except OSError:pass
 assert not owned,owned
 before=git(p,'rev-parse','HEAD')
 cmd=['git','fetch','origin','codex/casepath-causal-experience-integration-20261009']
 with (R/f'shard{n}/fetch.log').open('x') as f:r=subprocess.run(cmd,cwd=p,stdout=f,stderr=subprocess.STDOUT)
 assert r.returncode==0 and git(p,'rev-parse','FETCH_HEAD')==SHA
 subprocess.run(['git','checkout','--detach',SHA],cwd=p,check=True,capture_output=True)
 assert git(p,'rev-parse','HEAD')==SHA and not git(p,'status','--porcelain') and digest(p/'casepath/source-manifest.json')==MAN
 source=json.loads((p/'casepath/source-manifest.json').read_text());assert len(source['files'])==source['file_count']==1714
 records.append({'shard':n,'repo':path,'before_head':before,'before_status':'','owned_processes_before':owned,'canonical_fetch_command':cmd,'fetch_head':SHA,'head':SHA,'status':'','manifest_sha256':MAN})
save('canonical-fetch.json',records)
p=pathlib.Path(repos['1']);shutil.copy2(p/'casepath/source-manifest.json',R/'source-manifest.json')
diff=subprocess.check_output(['git','diff','--name-status',OLD,SHA],cwd=p,text=True);save('candidate-diff-vs-a89.json',{'base':OLD,'candidate':SHA,'name_status':diff.splitlines(),'review_scope':'Three authored paths plus asset pins/index and seal; no source edits by gate'})
for f in ['AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md']:
 save('coordinator/instruction-'+pathlib.Path(f).stem+'.json',{'candidate':SHA,'file':f,'sha256':digest(p/f),'read':True})
print(json.dumps({'root':str(R),'candidate':SHA,'clones':len(repos),'diff':diff.splitlines(),'free_bytes':shutil.disk_usage('/workspace').free}))

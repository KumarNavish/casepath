import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-roles-final-gate-c925a026-20261018')
P=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
SHA='c925a0267971edb52fea5f2bd9653a2495b7ac15'
MAN='1d4da0d965b790395b2d45979f04cc5e8f391b8a8accbeee7a6b1253d472c758'
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
repos=json.loads((P/'clone-map.json').read_text())['repos']
save(R/'clone-map.json',{'candidate':SHA,'repos':repos,'source':'Same six completed prior-gate owned normal clones; frontend1/2/3 excluded','created_epoch':time.time()})
save(R/'EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'source':'Parent delegated user GO full six Cloud shards + unchanged Mac127; frozen source; no paid/provider/hosting/deploy','no_retries':True,'floor_bytes':3*1024**3,'global_max_heavy':3,'gate_max_heavy':2})
save(R/'heavy-budget.json',{'max_gate_heavy':2,'global_max_heavy':3,'source':'Disk-safe staggered preparation and execution'})
provenance=[]
for directory,names in [('harness',['casepath_shard_observer.py','prepare_clones.py','run_shard.py','verify_prepared_capsules.py']),('coordinator',['verify.py','reconcile.py'])]:
 for name in names:
  src=P/directory/name;target=R/directory/name
  txt=src.read_text().replace(str(P),str(R)).replace('65a796a5dfb21f4cdbe0a3d1a4925b931710b30c',SHA).replace('6fec138ef5f8eacff8cc4fc19f0084f61b81fde81c2a37c300708c24b5eb2a2c',MAN).replace('/workspace/k65h','/workspace/c9h').replace('/workspace/k65t','/workspace/c9t').replace('1712','1714')
  target.write_text(txt);provenance.append({'source':str(src),'source_sha256':digest(src),'target':str(target),'target_sha256':digest(target)})
for src,target in [(P/'mac-ids.txt',R/'mac-ids.txt'),(P/'known-skips.json',R/'known-skips.json'),(P/'collected-ids.txt',R/'coordinator/prior-collected-ids.txt'),(P/'per-file-durations.json',R/'coordinator/prior-per-file-durations.json'),(P/'shard-map.json',R/'coordinator/prior-shard-map.json'),(Path('/workspace/atomic-proof-20261017/export/renamed-test-ids.json'),R/'renamed-test-ids.json')]:
 shutil.copy2(src,target);provenance.append({'source':str(src),'target':str(target),'sha256':digest(target),'byte_equal':src.read_bytes()==target.read_bytes()})
save(R/'harness-provenance.json',provenance)
save(R/'mac-owner-attestation.json',{'candidate':SHA,'ids':127,'owner':'Mac coordination owner','status':'pending actual native Mac execution/results','raw_receipts_inspected_in_cloud':False,'mac_fallback_forbidden':True})
save(R/'migration-process-audit.json',{'candidate':SHA,'cloud_proc1_maps':'not bypassed; unsupported audit tests remain assigned unchanged to Mac127','Mac_raw_inspected_in_Cloud':False})
processes=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  cwd=str((d/'cwd').resolve(strict=True));cmd=(d/'comm').read_text().strip()
  # Do not inspect environments, credential files, maps, or raw command arguments.
  if any(cwd==repo or cwd.startswith(repo+'/') for repo in repos.values()):processes.append({'pid':int(d.name),'cwd':cwd,'comm':cmd})
 except (OSError,PermissionError):pass
save(R/'checkout-process-preflight.json',{'epoch':time.time(),'processes_in_selected_clones':processes,'method':'/proc PID cwd and comm only; no maps/env; protected ports excluded','parent_confirmed_no_other_writers':True})
assert not processes,processes
prior_agg=json.loads((P/'aggregate.json').read_text());assert prior_agg['cloud_failed']==0 and prior_agg['all_six_first_only_attempts']
records=[]
for n,rep in repos.items():
 repo=Path(rep);out=R/f'shard{n}';out.mkdir(exist_ok=True)
 assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink()
 oldhead=git(repo,'rev-parse','HEAD');status=git(repo,'status','--porcelain');assert not status
 manifest=repo/'casepath/source-manifest.json';old=json.loads(manifest.read_text());rows=[]
 for row in old['files']:
  f=repo/row['path'];assert not f.is_symlink()
  actual=digest(f)
  if actual!=row['sha256'] or f.stat().st_size!=row['size_bytes']:
   assert subprocess.check_output(['git','show','HEAD:'+row['path']],cwd=repo)==f.read_bytes()
  rows.append({**row,'manifest_declared_sha256':row['sha256'],'sha256':actual,'size_bytes':f.stat().st_size})
 record={'shard':n,'repo':rep,'before_head':oldhead,'before_status':status,'before_manifest_sha256':digest(manifest),'before_sealed_files':len(rows),'normal_git_authority':True,'prior_gate_aggregate_sha256':digest(P/'aggregate.json'),'prior_raw_archive_sha256':digest(P/'raw-evidence.tar.gz'),'old_source_roster':rows,'parent_confirmed_completed_owned_clone':True,'no_active_processes_in_clone':True}
 save(out/'checkout-retirement-before.json',record)
 with (out/'fetch.log').open('x') as stream:
  c=subprocess.run(['git','fetch','origin',SHA],cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
 assert c.returncode==0 and git(repo,'rev-parse','FETCH_HEAD')==SHA
 assert subprocess.run(['git','merge-base','--is-ancestor',oldhead,SHA],cwd=repo).returncode==0
 record['old_head_reachable_in_canonical_fetched_candidate']=True
 record['canonical_fetch_source']=git(repo,'remote','get-url','origin');record['canonical_fetched_head']=SHA
 subprocess.run(['git','checkout','--detach',SHA],cwd=repo,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain') and digest(manifest)==MAN
 record.update(after_head=SHA,after_status='',after_manifest_sha256=MAN,source_retained_in_canonical_git_history=True,completed_epoch=time.time())
 save(out/'checkout-retirement.json',record);records.append({k:v for k,v in record.items() if k!='old_source_roster'})
save(R/'canonical-fetch.json',records)
shutil.copy2(Path(repos['1'])/'casepath/source-manifest.json',R/'source-manifest.json')
print(json.dumps({'candidate':SHA,'reused_clean_owned_normal_clones':len(records),'free_bytes':shutil.disk_usage('/workspace').free}),flush=True)

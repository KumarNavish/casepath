from pathlib import Path
import ast,json,os,hashlib,shutil,subprocess,time
P=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');OLD='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';SHA='16c10bc21c1b2b3b6602cb028028adf28e20823b';OM='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8';MAN='e7fbfd43062c19ed04468966aee9a2c61dcb1064b8baaa449cd4a2fe841e0442'
def save(n,v):(R/n).write_text(json.dumps(v,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
assert os.uname().nodename=='656813ef2295' and shutil.disk_usage('/workspace').free>=3*1024**3
(R/'harness').mkdir(exist_ok=True);prov=[]
for folder in ['harness','coordinator']:
 for p in sorted((P/folder).glob('*.py')):
  if p.name in ['initialize_gate.py','process_observer.py'] or p.name.startswith('read-seed-addc-'):continue
  s=p.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/rsh','/workspace/ilh').replace('/workspace/rst','/workspace/ilt').replace('qa-receipts/read-seed-gate-addc5a77-20261018','qa-receipts/idle-read-gate-16c10bc2-20261018').replace('1718','1719').replace('exactaddc','exact16c')
  if p.name in ['inventory.py','reconcile.py']:s=s.replace('len(prior)==2777','len(prior)==2833').replace("'baseline_inventory':2777","'baseline_inventory':2833").replace("'all2777_baseline_ids_included_unchanged':True","'all2833_baseline_ids_included_unchanged':True,'all2777_baseline_ids_included_unchanged':True").replace("'all2777_baseline_ids_retained_unchanged':True","'all2833_baseline_ids_retained_unchanged':True,'all2777_baseline_ids_retained_unchanged':True")
  if p.name=='inventory.py':s=s.replace("'prior_candidate':'8f230fd4ad455a15a7a53803ae7b857a4db2aaff'","'prior_candidate':'"+OLD+"'").replace('baseline2777 exact IDs retained','baseline2833 exact IDs retained')
  if p.name=='summarize.py':s=s.replace('baseline_inventory=2777','baseline_inventory=2833').replace('approved_runtime_retirement_permission_failures=1','approved_runtime_retirement_permission_failures=0, initial_workspace_admission_failures=1').replace("'all2777_baseline_ids_included_unchanged':True","'all2833_baseline_ids_included_unchanged':True,'all2777_baseline_ids_included_unchanged':True")
  if p.name=='qualify_final.py':s=s.replace('baseline_inventory=2777','baseline_inventory=2833, all2833_prior_addc_ids_retained_unchanged=True').replace("focused_read_seed_evidence_commit='81919a0beceab6672f72daf1e823120e9046e2cc'","focused_idle_read_evidence_commit='98c4b3042ee29678507dac09076a1bf8a8a99eb6'").replace('focused_read_seed_source_bindings=10','focused_idle_read_source_bindings=2')
  if p.name=='finish_audit.py':
   s=s[:s.index("branch_proof=json.loads")]+'''branch_proof=json.loads((R/'approved-retirement-proof.json').read_text());row=branch_proof['source_branch']
actual=subprocess.check_output(['git','rev-parse',row['branch']],cwd=row['path'],text=True).strip();assert actual==row['head']
remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+row['branch']],cwd=G,text=True).split()[0];assert remote==row['remote']
(R/'focused-source-branches-after.json').write_text(json.dumps({'branch':row['branch'],'local':actual,'remote':remote,'focused_evidence_commit':'98c4b3042ee29678507dac09076a1bf8a8a99eb6','no_source_branch_rewritten':True,'epoch':time.time()},indent=2)+'\\n')
'''
  if p.name=='bundle.py':s=s.replace('all2777 unchanged baseline IDs plus56 actual new seed/export IDs','all2833 unchanged addc baseline IDs plus9 actual new idle-read IDs')
  ast.parse(s);t=R/folder/p.name;t.write_text(s);prov.append({'source':str(p),'source_sha256':digest(p),'target':str(t),'target_sha256':digest(t)})
save('harness-provenance.json',{'basis':'Proven addc full gate harness, new16c/root/1719/short env paths; baseline2833 and9 new IDs reconciled dynamically; no product edits','files':prov})
for n in ['known-skips.json','mac-ids.txt','timing-regression-ids.json','secret-scan-exact-allowlist.json']:shutil.copy2(P/n,R/n)
for a,b in [('collected-ids.txt','prior-collected-ids.txt'),('shard-map.json','prior-shard-map.json'),('per-file-durations.json','prior-per-file-durations.json')]:shutil.copy2(P/a,R/'coordinator'/b)
for n in ['original2613-collected-ids.txt','b861-collected-ids.txt','a89-collected-ids.txt','4bf-collected-ids.txt']:shutil.copy2(P/'coordinator'/n,R/'coordinator'/n)
shutil.copy2(P/'coordinator/prior-collected-ids.txt',R/'coordinator/legacy2777-collected-ids.txt')
repos=json.loads((P/'clone-map.json').read_text())['repos'];save('clone-map.json',{'candidate':SHA,'repos':repos,'source':'Same six isolated normal clones;023a9d13 source branch local+remote preserved','protected_writer':'/workspace/casepath-operations-review-20261013','protected_touch_writer':'/workspace/casepath-reference-85a-qa','protected_failed_clone':'/workspace/casepath-release-ae0-shard5','created_epoch':time.time()})
for n in ['0']+list(repos):
 for prefix in ['ilh','ilt']:Path('/workspace/'+prefix+n).mkdir(mode=0o700,exist_ok=True)
for n in repos:(R/('shard'+n)).mkdir(mode=0o700,exist_ok=True)
(R/'inventory').mkdir(mode=0o700,exist_ok=True)
save('EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'manifest_sha256':MAN,'source_file_count':1719,'authorization':'Parent explicitly authorizes frozen16c six Cloud shards exactly once plus unchangedMac127 owner validation. No retries/new skips/deselection/source edits/real seed/private data/models/services/production/deploy. Retain all2833baseline IDs and all new IDs.','epoch':time.time()})
save('heavy-budget.json',{'max_gate_heavy':2,'global_max_heavy':2,'actual_serial_schedule_heavy_cap':1,'min_workspace_free_bytes':3*1024**3,'basis':'Strict3GiB floor+unchanged500MiB normalprepare reservation; one heavy given disk and cgroup budget'})
save('initial-resource.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'memory_current':Path('/sys/fs/cgroup/memory.current').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'epoch':time.time()})
save('prior-evidence-preservation.json',{'prior_root':str(P),'prior_raw_archive_sha256':digest(P/'raw-evidence.tar.gz'),'prior_sumfile_sha256':digest(P/'SHA256SUMS'),'prior_remote_commit':'6953f0eb9c325fdef906d01321a9d198432fd0c4','source_and_raw_retained':True})
save('process-sampler-qualification.json',{'optional_sampling_retried':False,'actual_child_environment_samples':0,'prior_observed_error':'EACCES13','configured_environment_isolation_verified_by_exact_command_result_receipts':True,'no_observed_child_path_coverage_claimed':True})
protected=json.loads((P/'protected-checkouts-before.json').read_text());protected['prior_gate_ref']='6953f0eb9c325fdef906d01321a9d198432fd0c4';protected['epoch']=time.time();save('protected-checkouts-before.json',protected)
records=[]
for n,path in repos.items():
 p=Path(path);assert (p/'.git').is_dir() and not (p/'.git').is_symlink() and not git(p,'status','--porcelain');before=git(p,'rev-parse','HEAD');branch=git(p,'branch','--show-current');owned=[]
 for q in Path('/proc').iterdir():
  if not q.name.isdigit():continue
  try:
   args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
   if any(a.startswith(path+'/.runtime/') or a==path+'/bin/casepath' for a in args):owned.append({'pid':q.name})
  except OSError:pass
 assert not owned,owned;cmd=['git','fetch','origin','codex/casepath-causal-experience-integration-20261009']
 with (R/f'shard{n}/fetch.log').open('x') as f:x=subprocess.run(cmd,cwd=p,stdout=f,stderr=subprocess.STDOUT)
 assert x.returncode==0 and git(p,'rev-parse','FETCH_HEAD')==SHA
 subprocess.run(['git','checkout','--detach',SHA],cwd=p,check=True,capture_output=True)
 assert git(p,'rev-parse','HEAD')==SHA and not git(p,'status','--porcelain') and digest(p/'casepath/source-manifest.json')==MAN
 m=json.loads((p/'casepath/source-manifest.json').read_bytes());assert m['file_count']==len(m['files'])==1719
 for row in m['files']:assert digest(p/row['path'])==row['sha256']
 assert not (p/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists()
 records.append({'shard':n,'repo':path,'before_head':before,'before_branch_preserved':branch,'before_status':'','owned_processes_before':owned,'canonical_fetch_command':cmd,'fetch_head':SHA,'head':SHA,'status':'','manifest_sha256':MAN,'sealed_files_verified':1719,'optional_package_seed_absent':True})
save('canonical-fetch.json',records);p=Path(repos['1']);shutil.copy2(p/'casepath/source-manifest.json',R/'source-manifest.json');diff=git(p,'diff','--name-status',OLD,SHA).splitlines();assert len(diff)==3
save('candidate-diff-vs-addc.json',{'base':OLD,'candidate':SHA,'name_status':diff,'expected_scope':'Reviewed hosted_sql_v1.py+new idle transport tests+seal only','focused_evidence_commit':'98c4b3042ee29678507dac09076a1bf8a8a99eb6'})
for n in ['AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md']:
 assert (p/n).read_bytes()==(Path('/workspace/casepath-reference-85a-qa')/n).read_bytes();save('coordinator/instruction-'+Path(n).stem+'.json',{'file':n,'sha256':digest(p/n),'read_and_unchanged':True})
save('optional-seed-isolation.json',{'candidate':SHA,'parent_CASEPATH_READ_SEED_PATH_present':'CASEPATH_READ_SEED_PATH' in os.environ,'inherited_to_children':False,'package_seed_absent_in_all_six':True,'real_seed_or_private_data_allowed':False});assert 'CASEPATH_READ_SEED_PATH' not in os.environ
for n in ['pinned-shared-tool-identities.json','migration-process-audit.json','qualification-limits.json']:
 d=json.loads((P/n).read_text());d.update(candidate=SHA,prior_receipt=str(P/n),current_Mac_owner_attestation_pending=True)
 if n=='pinned-shared-tool-identities.json':
  for row in d['tools']:assert digest(Path(row['path']))==row['sha256']
 save(n,d)
shutil.copy2('/workspace/idle16-init.py',R/'coordinator/initialize_gate.py');print(json.dumps({'initialized_clones':6,'candidate':SHA,'source_file_count':1719,'free_bytes':shutil.disk_usage('/workspace').free,'normalprepare_not_started':True}))

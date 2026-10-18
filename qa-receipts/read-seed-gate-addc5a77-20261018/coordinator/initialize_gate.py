from pathlib import Path
import ast,os,json,hashlib,subprocess,shutil,time
P=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
OLD='8f230fd4ad455a15a7a53803ae7b857a4db2aaff';SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';OM='b7af849b48589e598bcb5385d7dd4ad63bc9a868e634f62ff0be96910ec453e3';MAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8'
def save(n,v):(R/n).write_text(json.dumps(v,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
assert os.uname().nodename=='656813ef2295' and (R/'approved-retirement-result.json').exists();assert shutil.disk_usage('/workspace').free>=3*1024**3+500*1024**2
(R/'harness').mkdir(exist_ok=True);provenance=[]
for folder in ['harness','coordinator']:
 for p in sorted((P/folder).glob('*.py')):
  if p.name in ['initialize_gate.py','process_observer.py']:continue
  s=p.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/owh','/workspace/rsh').replace('/workspace/owt','/workspace/rst').replace('qa-receipts/outcome-wait-gate-8f230fd4-20261018','qa-receipts/read-seed-gate-addc5a77-20261018').replace('1714','1718').replace('exact4bf','exactaddc').replace('exact8f','exactaddc')
  if p.name in ['prepare_clones.py','run_shard.py']:
   insert="assert 'CASEPATH_READ_SEED_PATH' not in env and not (repo/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists(), 'Real/optional seed must be absent in Cloud gate'\n"
   if p.name=='prepare_clones.py':s=s.replace("    transport_names=",'    '+insert+'    transport_names=')
   else:s=s.replace("python=repo/",insert+"python=repo/")
  ast.parse(s);t=R/folder/p.name;t.write_text(s);provenance.append({'source':str(p),'source_sha256':digest(p),'target':str(t),'target_sha256':digest(t)})
save('harness-provenance.json',{'basis':'Reuse proven8f harness; new frozen candidate/root/manifest1718/short child paths; explicit optional seed absent; fresh inventory genuine delta reconciled','files':provenance})
for name in ['known-skips.json','mac-ids.txt','timing-regression-ids.json','secret-scan-exact-allowlist.json']:shutil.copy2(P/name,R/name)
for a,b in [('collected-ids.txt','prior-collected-ids.txt'),('shard-map.json','prior-shard-map.json'),('per-file-durations.json','prior-per-file-durations.json')]:shutil.copy2(P/a,R/'coordinator'/b)
for name in ['original2613-collected-ids.txt','b861-collected-ids.txt','a89-collected-ids.txt']:shutil.copy2(P/'coordinator'/name,R/'coordinator'/name)
shutil.copy2('/workspace/casepath-touch-target-gate-4bf9b439-20261018/collected-ids.txt',R/'coordinator/4bf-collected-ids.txt')
repos=json.loads((P/'clone-map.json').read_text())['repos'];save('clone-map.json',{'candidate':SHA,'repos':repos,'source':'Same six normal physical clones after clean/no-active-process check; focused af786/8b920 branchrefs durably preserved','protected_writer':'/workspace/casepath-operations-review-20261013','protected_touch_writer':'/workspace/casepath-reference-85a-qa','protected_failed_clone':'/workspace/casepath-release-ae0-shard5','created_epoch':time.time()})
for n in ['0']+list(repos):
 for prefix in ['rsh','rst']:Path('/workspace/'+prefix+n).mkdir(mode=0o700,exist_ok=True)
for n in repos:(R/('shard'+n)).mkdir(mode=0o700,exist_ok=True)
(R/'inventory').mkdir(mode=0o700,exist_ok=True)
save('EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'manifest_sha256':MAN,'source_file_count':1718,'authorization':'Parent explicit full addc once six shards; retain all2777 baseline IDs and all genuinely new seed/export IDs; no retries/new skips/deselection/source changes/real seed/provider calls/deployment. Normal prepare, separate controlled child HOME/TMP/DB/artifacts.','epoch':time.time()})
save('heavy-budget.json',{'max_gate_heavy':2,'global_max_heavy':2,'actual_serial_schedule_heavy_cap':1,'min_workspace_free_bytes':3*1024**3,'basis':'Disk and cgroup memory bounded; one heavy safely admitted'})
save('initial-resource.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'memory_current':int(Path('/sys/fs/cgroup/memory.current').read_text()),'memory_max':int(Path('/sys/fs/cgroup/memory.max').read_text()),'epoch':time.time()})
save('prior-evidence-preservation.json',{'prior_root':str(P),'prior_raw_archive_sha256':digest(P/'raw-evidence.tar.gz'),'prior_sumfile_sha256':digest(P/'SHA256SUMS'),'prior_remote_commit':'9d7e4f0bfd2e1dca18e11ba79282ddb0272a5f28','prior_a89_root':'/workspace/casepath-mobile-context-gate-a89b97bb-20261018','prior_a89_archive_sha256':digest(Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018/raw-evidence.tar.gz')),'source_and_raw_retained':True})
save('process-sampler-qualification.json',{'optional_sampling_retried':False,'actual_child_environment_samples':0,'prior_observed_error':'EACCES13','configured_environment_isolation_verified_by_exact_command_result_receipts':True,'no_observed_child_path_coverage_claimed':True})
protected=json.loads((P/'protected-checkouts-before.json').read_text());protected['prior_gate_ref']='9d7e4f0bfd2e1dca18e11ba79282ddb0272a5f28';protected['epoch']=time.time();save('protected-checkouts-before.json',protected)
records=[]
for n,path in repos.items():
 p=Path(path);assert (p/'.git').is_dir() and not (p/'.git').is_symlink() and not git(p,'status','--porcelain');before=git(p,'rev-parse','HEAD');branch=git(p,'branch','--show-current');owned=[]
 for q in Path('/proc').iterdir():
  if not q.name.isdigit():continue
  try:
   cwd=os.readlink(q/'cwd')
   if cwd==path or cwd.startswith(path+'/'):owned.append({'pid':q.name,'cwd':cwd})
  except OSError:pass
 assert not owned;cmd=['git','fetch','origin','codex/casepath-causal-experience-integration-20261009']
 with (R/f'shard{n}/fetch.log').open('x') as f:x=subprocess.run(cmd,cwd=p,stdout=f,stderr=subprocess.STDOUT)
 assert x.returncode==0 and git(p,'rev-parse','FETCH_HEAD')==SHA
 subprocess.run(['git','checkout','--detach',SHA],cwd=p,check=True,capture_output=True)
 assert git(p,'rev-parse','HEAD')==SHA and not git(p,'status','--porcelain') and digest(p/'casepath/source-manifest.json')==MAN
 m=json.loads((p/'casepath/source-manifest.json').read_bytes());assert m['file_count']==len(m['files'])==1718
 for row in m['files']:assert digest(p/row['path'])==row['sha256']
 assert not (p/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists()
 records.append({'shard':n,'repo':path,'before_head':before,'before_branch_preserved':branch,'before_status':'','owned_processes_before':owned,'canonical_fetch_command':cmd,'fetch_head':SHA,'head':SHA,'status':'','manifest_sha256':MAN,'sealed_files_verified':1718,'optional_package_seed_absent':True})
save('canonical-fetch.json',records);p=Path(repos['1']);shutil.copy2(p/'casepath/source-manifest.json',R/'source-manifest.json');diff=git(p,'diff','--name-status',OLD,SHA).splitlines();assert len(diff)==11
save('candidate-diff-vs-8f.json',{'base':OLD,'candidate':SHA,'name_status':diff,'expected_scope':'Reviewed backend5/tools5 plus seal only','focused_evidence_commit':'81919a0beceab6672f72daf1e823120e9046e2cc'})
for f in ['AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md']:
 assert (p/f).read_bytes()==(Path('/workspace/casepath-reference-85a-qa')/f).read_bytes();save('coordinator/instruction-'+Path(f).stem+'.json',{'candidate':SHA,'file':f,'sha256':digest(p/f),'read_and_unchanged':True})
save('optional-seed-isolation.json',{'candidate':SHA,'parent_CASEPATH_READ_SEED_PATH_present':'CASEPATH_READ_SEED_PATH' in os.environ,'inherited_to_children':False,'package_seed_absent_in_all_six':True,'real_seed_or_private_data_allowed':False,'synthetic_test_fixtures_only':True});assert 'CASEPATH_READ_SEED_PATH' not in os.environ
save('mac-owner-attestation.json',{'candidate':SHA,'manifest_sha256':MAN,'source_file_count':1718,'assigned_ids':127,'passed':127,'skipped':0,'failed':0,'exit_code':0,'once_only':True,'wrapper_duration_seconds':114.4089,'pytest_duration_seconds':105.75,'all_sealed_files_verified_before_after':True,'source_clean_before_after':True,'raw_retained_on_Mac':True,'raw_inspected_in_cloud':False,'basis':'Current exact addc Mac owner attestation conveyed by integration parent; not prior candidate result'})
shutil.copy2('/workspace/read-seed-addc-init.py',R/'coordinator/initialize_gate.py');print(json.dumps({'candidate':SHA,'root':str(R),'clones':6,'source_file_count':1718,'free_bytes':shutil.disk_usage('/workspace').free}))

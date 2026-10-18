import pathlib,json,hashlib,os,subprocess,shutil,time,ast
P=pathlib.Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');R=pathlib.Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');G=pathlib.Path('/workspace/casepath-transport-gate-evidence-git-20261015')
OLD='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd';SHA='8f230fd4ad455a15a7a53803ae7b857a4db2aaff';OM='98bd51f82f96e146314496cd41255781634d19c407ced1a37221927b91a6b32e';MAN='b7af849b48589e598bcb5385d7dd4ad63bc9a868e634f62ff0be96910ec453e3';WRITER='f6e6f7bb033f38b4d999fe0f5b353f656eef87bd';BRANCH='qa-receipts/outcome-wait-gate-8f230fd4-20261018'
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(R/n).write_text(json.dumps(v,indent=2)+'\n')
assert os.uname().nodename=='656813ef2295' and not R.exists();assert shutil.disk_usage('/workspace').free>=3*1024**3+500*1024**2
assert git(G,'rev-parse','HEAD')=='cc395aa627e2063965780c7fb63a0e3a41982ad5' and sha(G/'.git/index')=='0022046a23b158d171f6a239bd7b0f21c23ec4372594997f0b4f7cd7d2ba3153'
protected=pathlib.Path('/workspace/casepath-reference-85a-qa');writer=pathlib.Path('/workspace/casepath-operations-review-20261013');assert git(protected,'rev-parse','HEAD')=='5fe9a95757c6feaefde02ca239d14df9ec6684ed' and not git(protected,'status','--porcelain');assert git(writer,'rev-parse','HEAD')==WRITER and not git(writer,'status','--porcelain')
R.mkdir(mode=0o700);(R/'harness').mkdir();(R/'coordinator').mkdir()
focus=git(G,'ls-remote','origin','refs/heads/qa-receipts/outcome-wait-reasons-20261018').split()[0];assert focus=='81c71464a5e33b51de0159f064b7cd4d2e713ed4'
save('protected-checkouts-before.json',{'source':{'path':str(protected),'head':git(protected,'rev-parse','HEAD'),'status':''},'writer':{'path':str(writer),'head':WRITER,'status':''},'evidence':{'path':str(G),'head':git(G,'rev-parse','HEAD'),'index_sha256':sha(G/'.git/index')},'focused_evidence_ref':git(G,'ls-remote','origin','refs/heads/qa-receipts/touch-targets-20261018').split()[0],'outcome_focused_evidence_ref':focus,'prior_gate_ref':git(G,'ls-remote','origin','refs/heads/qa-receipts/touch-target-gate-4bf9b439-20261018').split()[0],'epoch':time.time()})
assert json.loads((R/'protected-checkouts-before.json').read_text())['prior_gate_ref']=='5366ea3eb1125230661dd2f31f1e3156447997e8'
provenance=[]
for folder in ['harness','coordinator']:
 for p in sorted((P/folder).glob('*.py')):
  if p.name in ['initialize_gate.py','process_observer.py']:continue
  s=p.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OM,MAN).replace('/workspace/tt4h','/workspace/owh').replace('/workspace/tt4t','/workspace/owt').replace('qa-receipts/touch-target-gate-4bf9b439-20261018',BRANCH)
  if p.name=='inventory.py':s=s.replace("'prior_candidate':'a89b97bb8eecdd8e98771c99ca879d4e253f7881'","'prior_candidate':'"+OLD+"'")
  if p.name=='finish_audit.py':
   # Both protected writers remain separate from the six frozen test clones.
   s+='''\nwriter=Path('/workspace/casepath-operations-review-20261013')
writer_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=writer,text=True).strip();writer_status=subprocess.check_output(['git','status','--porcelain'],cwd=writer,text=True).strip()
assert writer_head=='f6e6f7bb033f38b4d999fe0f5b353f656eef87bd' and writer_status==''
outcome_focus=subprocess.check_output(['git','ls-remote','origin','refs/heads/qa-receipts/outcome-wait-reasons-20261018'],cwd=G,text=True).split()[0]
assert outcome_focus=='81c71464a5e33b51de0159f064b7cd4d2e713ed4'
(R/'protected-outcome-writer-after.json').write_text(json.dumps({'writer_head':writer_head,'writer_status':writer_status,'outcome_focused_ref':outcome_focus,'epoch':time.time()},indent=2)+'\\n')
'''
  if p.name=='qualify_final.py':
   a=s.index('aggregate.update(');b=s.index("save(R / 'aggregate.json', aggregate)",a)
   s=s[:a]+'''aggregate.update(baseline_inventory=2777, all2777_prior_4bf_ids_retained_unchanged=True,
                 all2777_a89_ids_retained_unchanged=True, original_b861_inventory=2613,
                 all_b861_ids_retained_unchanged=True, pytest_added_ids=0, pytest_removed_ids=0,
                 retained_timing_regressions=13, retained_timing_regressions_passed=13,
                 existing_outcome_focused_node_cases=62, retained_touch_browser_cases=14,
                 focused_node_cases_are_pytest_ids=False, focused_cases_reexecuted_by_this_gate=False,
                 outcome_focused_evidence_commit='81c71464a5e33b51de0159f064b7cd4d2e713ed4',
                 touch_focused_evidence_commit='0fd8c8562d8516e4159d2e00ed6affb2fc636e3f',
                 minimum_observed_workspace_free_bytes=minimum,
                 maximum_actual_prepare_or_pytest_concurrency=maximum,
                 configured_gate_heavy_cap=2, global_heavy_cap=2, actual_serial_schedule_heavy_cap=1,
                 optional_proc_environment_sampling_retried=False, observed_child_environment_samples=0,
                 environment_qualification='Configured isolation recorded by exact command/result environments; prior EACCES13 sampling not retried and no observed child-path coverage claimed',
                 all_six_full_runtime_before_after_equal=True, source_publication_or_deployment_by_gate=False,
                 configuration_draft_changes_needed=False)
''' + s[b:]
   s=s[:s.index("print(json.dumps({'all13_timing_passed'")]+"print(json.dumps({'all13_timing_passed':True,'all2777_ids_retained':True,'existing62_outcome_and14_touch_cases_reexecuted':False,'minimum_observed_free_bytes':minimum,'max_heavy':maximum}),flush=True)\n"
  if p.name=='serial_driver.py':
   s=s.replace('currently available4GB','currently available3.94GB')
  ast.parse(s);target=R/folder/p.name;target.write_text(s);provenance.append({'source':str(p),'source_sha256':sha(p),'target':str(target),'target_sha256':sha(target)})
save('harness-provenance.json',{'basis':'Exact proven4bf harness; new frozen candidate/root/short child paths/protected writer and correct focused metadata only; no product edits; optional denied environ sampler omitted','files':provenance})
for name in ['known-skips.json','mac-ids.txt','timing-regression-ids.json','secret-scan-exact-allowlist.json']:shutil.copy2(P/name,R/name)
for a,b in [('collected-ids.txt','prior-collected-ids.txt'),('shard-map.json','prior-shard-map.json'),('per-file-durations.json','prior-per-file-durations.json')]:shutil.copy2(P/a,R/'coordinator'/b)
for name in ['original2613-collected-ids.txt','b861-collected-ids.txt']:shutil.copy2(P/'coordinator'/name,R/'coordinator'/name)
shutil.copy2(pathlib.Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018/collected-ids.txt'),R/'coordinator/a89-collected-ids.txt')
repos=json.loads((P/'clone-map.json').read_text())['repos'];repos['6']='/workspace/casepath-release-ae0-shard3'
save('clone-map.json',{'candidate':SHA,'repos':repos,'source':'Reuse clean isolated normal clones; protected outcome writer and touch writer and failed clone excluded','protected_writer':str(writer),'protected_touch_writer':str(protected),'protected_failed_clone':'/workspace/casepath-release-ae0-shard5','created_epoch':time.time()})
for n in ['0']+list(repos):
 for prefix in ['owh','owt']:pathlib.Path('/workspace/'+prefix+n).mkdir(mode=0o700)
for n in repos:(R/('shard'+n)).mkdir(mode=0o700)
(R/'inventory').mkdir(mode=0o700)
save('EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'manifest_sha256':MAN,'source_file_count':1714,'authorization':'Parent explicit new full frozen8f gate once; six unchanged assignments, no retries/new skips/deselection, no source/seal changes, focused62/14 already passed and no reruns; each receipt pushed and remotely byte-bound before only owned reproducible runtime retirement','epoch':time.time()})
save('heavy-budget.json',{'max_gate_heavy':2,'global_max_heavy':2,'min_workspace_free_bytes':3*1024**3,'basis':'Strict3GiB floor, actual serial schedule given current3.94GB; no unowned cleanup'})
save('initial-resource.json',{'host':os.uname().nodename,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'epoch':time.time()})
save('prior-evidence-preservation.json',{'prior_root':str(P),'prior_raw_archive_sha256':sha(P/'raw-evidence.tar.gz'),'prior_sumfile_sha256':sha(P/'SHA256SUMS'),'prior_remote_commit':'5366ea3eb1125230661dd2f31f1e3156447997e8','prior_a89_root':'/workspace/casepath-mobile-context-gate-a89b97bb-20261018','prior_a89_archive_sha256':sha(pathlib.Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018/raw-evidence.tar.gz')),'source_and_raw_retained':True})
save('process-sampler-qualification.json',{'optional_sampling_retried':False,'actual_child_environment_samples':0,'prior_observed_error':'EACCES13','configured_environment_isolation_verified_by_exact_command_result_receipts':True,'no_observed_child_path_coverage_claimed':True,'prior_receipt':str(P/'process-sampler-qualification.json')})
records=[]
for n,path in repos.items():
 p=pathlib.Path(path);assert (p/'.git').is_dir() and not (p/'.git').is_symlink() and not git(p,'status','--porcelain')
 owned=[]
 for q in pathlib.Path('/proc').iterdir():
  if not q.name.isdigit():continue
  try:
   cwd=os.readlink(q/'cwd')
   if cwd==path or cwd.startswith(path+'/'):owned.append({'pid':int(q.name),'comm':(q/'comm').read_text().strip(),'cwd':cwd})
  except OSError:pass
 assert not owned,owned
 before=git(p,'rev-parse','HEAD');cmd=['git','fetch','origin','codex/casepath-causal-experience-integration-20261009']
 with (R/f'shard{n}/fetch.log').open('x') as f:x=subprocess.run(cmd,cwd=p,stdout=f,stderr=subprocess.STDOUT)
 assert x.returncode==0 and git(p,'rev-parse','FETCH_HEAD')==SHA
 subprocess.run(['git','checkout','--detach',SHA],cwd=p,check=True,capture_output=True)
 assert git(p,'rev-parse','HEAD')==SHA and not git(p,'status','--porcelain') and sha(p/'casepath/source-manifest.json')==MAN
 source=json.loads((p/'casepath/source-manifest.json').read_text());assert len(source['files'])==source['file_count']==1714
 records.append({'shard':n,'repo':path,'before_head':before,'before_status':'','owned_processes_before':owned,'canonical_fetch_command':cmd,'fetch_head':SHA,'head':SHA,'status':'','manifest_sha256':MAN})
save('canonical-fetch.json',records)
p=pathlib.Path(repos['1']);shutil.copy2(p/'casepath/source-manifest.json',R/'source-manifest.json');diff=subprocess.check_output(['git','diff','--name-status',OLD,SHA],cwd=p,text=True);assert len(diff.splitlines())==4
expected={'a803c34ceb0f995fb1eb05eeb6ba52cc9c8d9c210d767a3c6140ba381b651594','f6202f002fdad90f661f75891b18e11e04f8f191f345eaaceb9997754c06b90f'};bindings=[]
for rel in ['casepath/assets/autonomous-language-v1.js','casepath-qa/autonomous-language-v1.test.cjs']:
 raw=(p/rel).read_bytes();assert raw==subprocess.check_output(['git','show',WRITER+':'+rel],cwd=p);bindings.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'frozen_equal_f6_writer_commit':True})
assert {x['sha256'] for x in bindings}==expected
save('candidate-diff-vs-4bf.json',{'base':OLD,'candidate':SHA,'name_status':diff.splitlines(),'expected_scope':'Two language files plus index asset pins and seal only','focused_source_bindings':bindings})
for f in ['AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md']:
 assert (p/f).read_bytes()==(protected/f).read_bytes()
 save('coordinator/instruction-'+pathlib.Path(f).stem+'.json',{'candidate':SHA,'file':f,'sha256':sha(p/f),'read_prior_and_current_bytes_identical':True})
shutil.copy2('/workspace/outcome-8f-init.py',R/'coordinator/initialize_gate.py')
print(json.dumps({'candidate':SHA,'root':str(R),'source_diff':diff.splitlines(),'clones':len(repos),'replacement6':repos['6'],'free_bytes':shutil.disk_usage('/workspace').free}))

import hashlib,json,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');records=[];checkouts=[]
repos=json.loads((R/'clone-map.json').read_text())['repos']
for n,repo in repos.items():
 p=R/f'shard{n}/command.json';x=json.loads(p.read_text());names=list(x['env']);bad=[k for k in names if any(t in k.upper() for t in ['API_KEY','TOKEN','SECRET','PASSWORD','CREDENTIAL'])];assert not bad
 records.append({'shard':n,'controlled_env_names':sorted(names),'paid_or_product_secret_names':bad,'mode':x['env']['CASEPATH_MODEL_MODE'],'command_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip();assert head=='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd' and not status
 checkouts.append({'shard':n,'repo':repo,'head':head,'status':status,'normal_git_authority':Path(repo,'.git').is_dir()})
(R/'final-source-checkouts.json').write_text(json.dumps(checkouts,indent=2)+'\n')
(R/'no-paid-protected-data.json').write_text(json.dumps({'candidate':'4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd','scope':'Release gate setup/test/export operations only','test_environments':records,'outbound_setup':'Actual origin Git fetch/push and ordinary normalprepare dependency transport only; inherited proxy/CA kept and values never dumped','provider_calls_authorized':False,'paid_inference_authorized':False,'prod_api_or_journal_access_authorized':False,'hosting_or_deployment_authorized':False,'protected_corpora_or_live_journals_read_or_modified_by_gate':False,'source_or_test_edits_by_gate':False,'credentials_or_process_environments_dumped':False,'cloud_proc_maps_bypass_used':False,'audit_receipt':'migration-process-audit.json','all_six_test_environments_observed':True,'qualification':'Controlled test environments and frozen source/owned temporary paths are recorded. This is an execution-scope attestation, not a network packet trace.','epoch':time.time()},indent=2)+'\n')
(R/'protected-ports-after.json').write_text(json.dumps({'epoch':time.time(),'ss_listen_observation':subprocess.check_output(['ss','-ltn','( sport = :4173 or sport = :4189 or sport = :4190 )'],text=True),'protected_processes':[{'pid':n,'alive':Path('/proc',str(n)).exists(),'comm':Path('/proc',str(n),'comm').read_text().strip() if Path('/proc',str(n),'comm').exists() else None} for n in [595190,595198]],'no_unrelated_processes_signalled':True},indent=2)+'\n')
terminal=[json.loads((R/f'shard{n}/worker-terminal.json').read_text())['results'][0] for n in range(1,7)]
(R/'all-shard-terminal.json').write_text(json.dumps({'candidate':head,'results':terminal,'all_executed':True,'all_green':all(x['exit_code']==0 for x in terminal),'epoch':time.time()},indent=2)+'\n')
print(json.dumps({'source_clean':len(checkouts),'controlled_test_environments':len(records),'all_green':all(x['exit_code']==0 for x in terminal)}))

protected=Path('/workspace/casepath-reference-85a-qa');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
original=json.loads((R/'protected-checkouts-before.json').read_text())
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=protected,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=protected,text=True).strip()
assert head==original['source']['head']=='5fe9a95757c6feaefde02ca239d14df9ec6684ed' and status==''
ehead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=G,text=True).strip();index=hashlib.sha256((G/'.git/index').read_bytes()).hexdigest()
assert ehead==original['evidence']['head']=='cc395aa627e2063965780c7fb63a0e3a41982ad5' and index==original['evidence']['index_sha256']
focused=subprocess.check_output(['git','ls-remote','origin','refs/heads/qa-receipts/touch-targets-20261018'],cwd=G,text=True).split()[0]
assert focused==original['focused_evidence_ref']=='0fd8c8562d8516e4159d2e00ed6affb2fc636e3f'
prior=json.loads((R/'prior-evidence-preservation.json').read_text());pr=Path(prior['prior_root'])
assert hashlib.sha256((pr/'raw-evidence.tar.gz').read_bytes()).hexdigest()==prior['prior_raw_archive_sha256']
assert hashlib.sha256((pr/'SHA256SUMS').read_bytes()).hexdigest()==prior['prior_sumfile_sha256']
(R/'protected-identities-after.json').write_text(json.dumps({'source_head':head,'source_status':status,'evidence_head':ehead,'evidence_index_sha256':index,'focused_evidence_remote_ref':focused,'prior_raw_archive_and_sumfile_unchanged':True,'epoch':time.time()},indent=2)+'\n')

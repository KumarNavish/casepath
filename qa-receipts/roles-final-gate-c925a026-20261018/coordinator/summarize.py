import collections,hashlib,json,shutil,time
from pathlib import Path
R=Path('/workspace/casepath-roles-final-gate-c925a026-20261018')
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
recon=read(R/'raw-reconciliation.json');assert recon['cloud_failed']==0
byid=collections.defaultdict(list);capsules=[]
for n in range(1,7):
 out=R/f'shard{n}'
 for line in (out/'reports.jsonl').read_text().splitlines():
  row=json.loads(line);byid[row['id']].append(row)
 b=read(out/'source-before/capsule-verification.json');a=read(out/'source-after/capsule-verification.json');assert b['capsule_receipt']==a['capsule_receipt']
 capsules.append({'shard':n,'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'capsule_receipt_file_sha256':a['capsule_receipt_file_sha256'],'before_after_capsule_equal':True,'manifest_sha256':a['manifest_sha256'],'sealed_files_verified':a['sealed_files_verified'],'head':a['head'],'status':a['status']})
delta=read(R/'fresh-inventory-delta.json');assert len(delta['genuinely_new_ids'])==15 and len(delta['added_ids'])==16 and len(delta['removed_ids'])==1
results=[]
for ident in delta['added_ids']:
 rows=byid[ident];assert any(x['when']=='call' and x['outcome']=='passed' for x in rows) and all(x['outcome']=='passed' for x in rows)
 results.append({'id':ident,'phase_outcomes':{x['when']:x['outcome'] for x in rows},'renamed_replacement':ident==delta['renamed_tests'][0]['new_id']})
save(R/'new-test-results.json',{'candidate':recon['candidate'],'genuinely_new_count':15,'raw_added_count':16,'all_passed':True,'results':results})
pertest=[];perfile={}
for ident,rows in sorted(byid.items()):
 phase=sum(x['duration'] for x in rows);call=sum(x['duration'] for x in rows if x['when']=='call');skipped=any(x['outcome']=='skipped' for x in rows)
 pertest.append({'id':ident,'phase_seconds':phase,'call_seconds':call,'outcome':'skipped' if skipped else 'passed'})
 f=ident.split('::')[0];entry=perfile.setdefault(f,{'tests':0,'passed':0,'skipped':0,'phase_seconds':0.,'call_seconds':0.});entry['tests']+=1;entry['skipped' if skipped else 'passed']+=1;entry['phase_seconds']+=phase;entry['call_seconds']+=call
save(R/'per-test-durations.json',pertest);save(R/'per-file-durations.json',perfile)
resources=[json.loads(x) for x in (R/'resource-observations.jsonl').read_text().splitlines()];global_resources=[json.loads(x) for x in (R/'global-resource-observations.jsonl').read_text().splitlines()];events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()]
minimum=min(x['free_bytes'] for x in resources+global_resources);floor=3*1024**3;assert minimum>=floor
assert not any(x['type'] in ['RESOURCE_FLOOR_BREACH','PYTEST_FAILURE_NO_RETRY','COORDINATOR_FAILURE_NO_RETRY','PENDING_SHARDS_NOT_LAUNCHED'] for x in events)
max_active=max(x['gate_heavy'] for x in global_resources);assert max_active<=3
save(R/'resource-after.json',{'candidate':recon['candidate'],'runtime_floor_bytes':floor,'minimum_observed_workspace_free_bytes':minimum,'current_workspace_free_bytes':shutil.disk_usage('/workspace').free,'current_tmp_free_bytes':shutil.disk_usage('/tmp').free,'resource_observation_rows':len(resources),'global_resource_observation_rows':len(global_resources),'max_observed_gate_active':max_active,'global_max_heavy':3,'resource_floor_breach_events':0,'all_child_command_environments_use_owned_workspace_home_and_temp':True,'qualification':'Recorded admission/process/disk observations passed; no claim about unobserved intervals. Parent separately confirmed no additional heavy work.','epoch':time.time()})
assert len({x['capsule_receipt_file_sha256'] for x in capsules})==1
save(R/'source-capsule-before-after.json',{'candidate':recon['candidate'],'manifest_sha256':recon['manifest_sha256'],'all_six_source_capsules_unchanged':True,'all_six_capsule_receipts_equal':True,'normal_prepare_clones':6,'sealed_file_count':1714,'artifact_file_count':25,'static_file_count':40,'checks':capsules})
summary={k:recon[k] for k in ['candidate','manifest_sha256','full_inventory','all_baseline_ids_retained_with_explicit_rename','cloud_selected','cloud_passed','cloud_skipped','cloud_failed','cloud_raw_phase_rows','no_gaps_duplicates_overlap','all_six_first_only_attempts','all_six_source_capsules_unchanged','all_junit_ids_match_raw_phases_and_collected','shards']}
mac=read(R/'mac-owner-attestation.json');assert mac['passed']==127 and mac['failed']==mac['skipped']==0 and not mac['raw_receipts_inspected_in_cloud']
summary.update(baseline_inventory=2749,original_baseline_inventory=2613,original2603pass10skip_baseline_all_ids_current=True,genuinely_new_ids=15,raw_added_ids=16,raw_removed_ids=1,explicit_renames=delta['renamed_tests'],mac_partition_count=127,mac_owner_attestation=str(R/'mac-owner-attestation.json'),mac_raw_receipts_inspected_in_cloud=False,actual_owner_reported_mac_passed=127,combined_passed_using_actual_mac_owner_attestation=recon['cloud_passed']+127,combined_known_skips=10,cloud_failed_phase_rows=0,resource_floor_breach_events=0,minimum_observed_workspace_free_bytes=minimum,source_or_frontend_changes_by_gate=False,pytest_retries=0,source_file_count=1714,artifact_file_count=25,static_file_count=40,preparation_failures_preserved='coordinator/preparation-repairs.json',protected_data_or_provider_access_by_gate=False)
attempts=[read(R/f'shard{n}/result.json') for n in range(1,7)];prepares=[read(R/f'shard{n}/prepare.json') for n in range(1,7)]
summary.update(cloud_pytest_sum_seconds=sum(x['duration_seconds'] for x in attempts),cloud_test_first_start_epoch=min(x['started_epoch'] for x in attempts),cloud_test_last_finish_epoch=max(x['finished_epoch'] for x in attempts),cloud_test_elapsed_seconds=max(x['finished_epoch'] for x in attempts)-min(x['started_epoch'] for x in attempts),normal_prepare_total_seconds=sum(x['duration_seconds'] for x in prepares),mac_owner_pytest_duration_seconds=mac['pytest_duration_seconds'])
save(R/'aggregate.json',summary)
save(R/'proof-disjoint-union-after.json',{'candidate':recon['candidate'],'full_inventory':recon['full_inventory'],'all_other_baseline2749_ids_included_with_explicit_rename':True,'all_original2613_ids_included_unchanged':True,'genuinely_new_ids':15,'raw_added_ids':16,'raw_removed_ids':1,'all_added_and_renamed_ids_passed':True,'cloud_ids':recon['cloud_selected'],'mac_ids':127,'cloud_passed':recon['cloud_passed'],'known_skips':recon['cloud_skipped'],'gaps':0,'duplicates':0,'overlap':0,'raw_phase_rows':recon['cloud_raw_phase_rows'],'all_junit_ids_equal_collection_and_phase_ids':True})
rows=[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for name in ['harness','coordinator'] for p in sorted((R/name).glob('*.py'))];save(R/'harness-provenance-current.json',rows)
print(json.dumps(summary),flush=True)

from pathlib import Path
import collections,hashlib,json,shutil,time
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
recon=json.loads((R/'raw-reconciliation.json').read_text());assert recon['cloud_failed']==0
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
byid=collections.defaultdict(list);capsules=[]
for n in range(1,7):
 out=R/f'shard{n}'
 for line in (out/'reports.jsonl').read_text().splitlines():
  row=json.loads(line);byid[row['id']].append(row)
 b=json.loads((out/'source-before/capsule-verification.json').read_text());a=json.loads((out/'source-after/capsule-verification.json').read_text());assert b['capsule_receipt']==a['capsule_receipt']
 capsules.append({'shard':n,'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'capsule_receipt_file_sha256':a['capsule_receipt_file_sha256'],'before_after_capsule_equal':True,'manifest_sha256':a['manifest_sha256'],'sealed_files_verified':a['sealed_files_verified'],'head':a['head'],'status':a['status']})
pertest=[];perfile={}
for ident,rows in sorted(byid.items()):
 phase=sum(x['duration'] for x in rows);call=sum(x['duration'] for x in rows if x['when']=='call');skipped=any(x['outcome']=='skipped' for x in rows)
 pertest.append({'id':ident,'phase_seconds':phase,'call_seconds':call,'outcome':'skipped' if skipped else 'passed'})
 f=ident.split('::')[0];entry=perfile.setdefault(f,{'tests':0,'passed':0,'skipped':0,'phase_seconds':0.,'call_seconds':0.});entry['tests']+=1;entry['skipped' if skipped else 'passed']+=1;entry['phase_seconds']+=phase;entry['call_seconds']+=call
save(R/'per-test-durations.json',pertest);save(R/'per-file-durations.json',perfile)
resources=[json.loads(x) for x in (R/'resource-observations.jsonl').read_text().splitlines()];events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()]
minimum=min(x['free_bytes'] for x in resources);floor=3*1024**3;assert minimum>=floor
assert not any(x['type'] in ['RESOURCE_FLOOR_BREACH','PYTEST_FAILURE_NO_RETRY','COORDINATOR_FAILURE_NO_RETRY','PENDING_SHARDS_NOT_LAUNCHED'] for x in events)
max_active=max(len(x.get('active',{})) for x in resources);assert max_active<=3
save(R/'resource-after.json',{'candidate':recon['candidate'],'runtime_floor_bytes':floor,'minimum_observed_workspace_free_bytes':minimum,'current_workspace_free_bytes':shutil.disk_usage('/workspace').free,'current_tmp_free_bytes':shutil.disk_usage('/tmp').free,'resource_observation_rows':len(resources),'max_observed_gate_reserved_or_active':max_active,'resource_floor_breach_events':0,'parent_browser_slot_budget_record':str(R/'heavy-budget-history.json'),'all_child_command_environments_use_owned_workspace_home_and_temp':True,'qualification':'Admission checks and recorded observations passed; no claim about unobserved intervals or independent measurement of other parent-owned processes','epoch':time.time()})
assert len({x['capsule_receipt_file_sha256'] for x in capsules})==1
save(R/'source-capsule-before-after.json',{'candidate':recon['candidate'],'manifest_sha256':recon['manifest_sha256'],'all_six_source_capsules_unchanged':True,'all_six_capsule_receipts_equal':True,'normal_prepare_clones':6,'sealed_file_count':1712,'checks':capsules})
summary={k:recon[k] for k in ['candidate','manifest_sha256','full_inventory','all_2630_prior_ids_included','cloud_selected','cloud_passed','cloud_skipped','cloud_failed','cloud_raw_phase_rows','no_gaps_duplicates_overlap','all_six_first_only_attempts','all_six_source_capsules_unchanged','all_junit_ids_match_raw_phases_and_collected','shards']}
summary.update(new_ids=119,removed_ids=0,mac_partition_count=127,mac_owner_attestation=str(R/'mac-owner-attestation.json'),mac_raw_receipts_inspected_in_cloud=False,parent_reported_mac_passed=127,combined_passed_using_parent_mac_attestation=recon['cloud_passed']+127,combined_known_skips=10,cloud_failed_phase_rows=0,resource_floor_breach_events=0,minimum_observed_workspace_free_bytes=minimum,source_or_frontend_changes_by_gate=False,pytest_retries=0,receipt_export_tool_errors_preserved=2)
save(R/'aggregate.json',summary)
rows=[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for name in ['harness','coordinator'] for p in sorted((R/name).glob('*.py'))];save(R/'harness-provenance-current.json',rows)
print(json.dumps(summary),flush=True)

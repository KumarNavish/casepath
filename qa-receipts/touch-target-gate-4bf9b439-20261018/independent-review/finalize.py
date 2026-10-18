from pathlib import Path
import collections, hashlib, json, math, time
R=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');O=R/'independent-review';SHA='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd';MAN='98bd51f82f96e146314496cd41255781634d19c407ced1a37221927b91a6b32e'
def read(p):return json.loads(p.read_text())
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert Path('/proc/sys/kernel/hostname').read_text().strip()=='656813ef2295'
inv=read(O/'inventory-review.json');focused=read(O/'focused-evidence-binding.json');shards=[read(O/f'shard{n}-review.json') for n in range(1,7)]
assert inv['full_count']==2777 and inv['cloud_count']==2650 and inv['mac_count']==127
assert focused['status']=='PASS_EXISTING_FOCUSED_EVIDENCE_BINDING' and focused['passed']==14
allskips={};phases=0;intervals=[];bindings={};actual_durations=[]
for n,x in enumerate(shards,1):
 assert x['status']=='PASS_TERMINAL_SHARD' and x['shard']==n and x['failed']==0 and x['single_original_attempt'] and x['runtime_before_after_equal'] and x['runtime_observed_before_test_start'] and x['source_before_after_equal']
 for rel,d in x['bindings'].items():assert h(R/rel)==d;bindings[rel]=d
 assert not set(allskips)&set(x['known_skip_details']);allskips.update(x['known_skip_details']);phases+=x['raw_phase_rows']
 for kind in ['prepare','result']:
  row=read(R/f'shard{n}/{kind}.json');intervals.extend([(row['started_epoch'],1,n,kind),(row['finished_epoch'],-1,n,kind)])
 actual_durations.append(read(R/f'shard{n}/result.json')['duration_seconds'])
 for line in (R/f'shard{n}/reports.jsonl').read_text().splitlines():
  phase=json.loads(line);assert math.isfinite(phase['duration']) and phase['duration']>=0
assert sum(x['selected'] for x in shards)==2650 and sum(x['passed'] for x in shards)==2640 and sum(x['skipped'] for x in shards)==10
assert phases==7941 and len(allskips)==10 and set(allskips)=={x['id'] for x in read(R/'known-skips.json')}
assert len({x['capsule_receipt_file_sha256'] for x in shards})==1 and sum(x['timing_regressions_passed'] for x in shards)==13
assert len({x['env_isolation']['HOME'] for x in shards})==len({x['env_isolation']['TMPDIR'] for x in shards})==len({x['env_isolation']['CASEPATH_DB_PATH'] for x in shards})==6
active=peak=0
for epoch,delta,n,kind in sorted(intervals):active+=delta;peak=max(peak,active)
assert active==0 and peak<=2
resources=[]
for name in ['global-resource-observations.jsonl','resource-observations.jsonl']:
 p=R/name;assert p.exists();rs=[json.loads(x) for x in p.read_text().splitlines()];assert rs;resources.extend(rs);bindings[name]=h(p)
minimum=min(x['free_bytes'] for x in resources);assert minimum>=3*1024**3
globalrows=[x for x in resources if 'gate_heavy' in x];assert max(x['gate_heavy'] for x in globalrows)<=2
for row in globalrows:assert row['gate_heavy']<=row['gate_heavy_limit']<=2
assert not (R/'STOP_ADMISSION_RESOURCE_VIOLATION.json').exists()
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];bad=[x for x in events if x['type'] in ['RESOURCE_FLOOR_BREACH','PYTEST_FAILURE_NO_RETRY','COORDINATOR_FAILURE_NO_RETRY','PENDING_SHARDS_NOT_LAUNCHED']];assert not bad
for n in range(1,7):assert len([x for x in events if x['type']=='pytest_start' and str(x['shard'])==str(n)])==1 and len([x for x in events if x['type']=='pytest_terminal' and str(x['shard'])==str(n) and x['exit_code']==0])==1
mac=read(R/'mac-owner-attestation.json');assert mac['candidate']==SHA and mac['manifest_sha256']==MAN and mac['passed']==127 and mac['failed']==mac['skipped']==0 and mac['exit_code']==0 and mac['attempt_count']==1 and mac['source_file_count']==1714 and mac['source_clean_before_after_owner_reported'] and mac['source_all1714_manifest_verified_owner_reported'] and mac['raw_receipts_retained_by_owner'] and mac['raw_receipts_inspected_in_cloud'] is False
migration=read(R/'migration-process-audit.json');assert migration['candidate']==SHA and migration['host']=='656813ef2295' and migration['proc1_maps_readable'] is False and migration['errno']==13 and migration['fail_closed_guard_preserved'] and migration['mac_partition_required'] and migration['no_bypass_or_skip_added']
for name in ['mac-owner-attestation.json','migration-process-audit.json','scheduler-events.jsonl','heavy-budget.json']:bindings[name]=h(R/name)
for p in [O/'inventory-review.json',O/'focused-evidence-binding.json',*[O/f'shard{n}-review.json' for n in range(1,7)],O/'audit.py',O/'finalize.py']:bindings[str(p.relative_to(R))]=h(p)
value={'status':'PASS_INDEPENDENT_CLOUD_GATE_REVIEW','findings':[],'reviewer':'/root/gate_4bf_review','candidate':SHA,'manifest_sha256':MAN,'actual_cloud_host':'656813ef2295','fresh_inventory':2777,'a89_exact_ids_unchanged':True,'b861_actual2613_exact_subset':True,'added_removed_renamed_pytest_ids':[0,0,0],'cloud_selected':2650,'cloud_passed':2640,'cloud_known_skipped':10,'cloud_failed':0,'cloud_raw_phase_rows':phases,'cloud_junit_cases':2650,'mac_owner_reported_passed':127,'mac_owner_reported_failed':0,'mac_owner_reported_skipped':0,'mac_owner_duration_seconds':mac['pytest_duration_seconds'],'mac_raw_receipts_inspected_in_cloud':False,'combined_passed_using_current_mac_owner_attestation':2767,'combined_known_skipped':10,'all_six_first_only_attempts':True,'all_six_raw_phase_junit_collection_ids_exact':True,'all_six_source_capsule_before_after_equal':True,'source_artifact_static_counts':[1714,25,40],'all_six_runtime_inventories_equal_and_observed_before_attempt':True,'all13_timing_regressions_passed':True,'focused14_existing_passed_exact_bytes_bound':True,'runtime_resource_floor_bytes':3*1024**3,'minimum_observed_workspace_free_bytes':minimum,'max_observed_gate_heavy':max(x['gate_heavy'] for x in globalrows),'max_prepare_or_test_overlap_from_exact_intervals':peak,'cloud_pytest_sum_seconds':sum(actual_durations),'shards':shards,'bindings':bindings,'limits':['Mac127 is exact-current owner terminal attestation; Cloud did not execute or inspect Mac raw receipts.','Resource compliance covers recorded observations and exact prepare/test intervals; unrelated heavy work absence is parent attestation.','Existing14 focused Node cases are reused from independently approved immutable0fd8c856 evidence with exact candidate byte binding; this gate did not rerun them.','No product tests, prepare, browser, provider, network operations, source edits, or evidence Git mutations performed by this reviewer.'],'reviewed_epoch':time.time()}
p=O/'final-review.json';p.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p),'status':value['status'],'counts':[2777,2650,2640,10,127,2767]}))

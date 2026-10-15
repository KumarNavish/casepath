import collections, hashlib, json, os, shutil, subprocess, time, xml.etree.ElementTree as ET
from pathlib import Path

R=Path('/workspace/casepath-saved-history-gate-5086624c-20261015')
SHA='5086624c8a024ba298819e5e27d749efbd0cc7fc'
MANIFEST='39f03a9ebb1287c5e03f57a444ea97bb079dc44e84cff90a86805c19fba35c3f'
NAMES=[f'shard{i}' for i in range(1,7)]
def save(p,x): p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

terminal=json.loads((R/'all-shard-terminal.json').read_text())
assert terminal['all_executed'] and terminal['all_green'],terminal
repo=Path('/workspace/casepath-release-ae0-shard6')
env=json.loads((R/'inventory/prepare.json').read_text())['env']
# Collection reuses physical shard6; all six actual source-after proofs are already retained.
after=[]; equality=[]; commands=[x for x in json.loads((R/'source-proof-commands.json').read_text()) if x['phase']!='after']
for name in NAMES:
    p=R/name
    before=json.loads((p/'source-before/capsule-verification.json').read_text())
    proof=json.loads((p/'source-after/capsule-verification.json').read_text())
    assert before['capsule_receipt']==proof['capsule_receipt']
    assert before['capsule_receipt_file_sha256']==proof['capsule_receipt_file_sha256']
    assert before['manifest_sha256']==proof['manifest_sha256']==MANIFEST
    assert proof['source_artifact_static_bindings_verified'] and proof['sealed_files_verified']==1709
    assert proof['head']==SHA and proof['status']==''
    after.append(proof); equality.append({'name':name,'head':SHA,'manifest_sha256':MANIFEST,'capsule_receipt_file_sha256':proof['capsule_receipt_file_sha256'],'unchanged_at_actual_verification':True,'runtime_retired_after_actual_source_proof':name=='shard1'})
    assert proof['capsule_receipt']['artifact_file_count']==25 and proof['capsule_receipt']['static_file_count']==39
    clone=Path('/workspace/casepath-release-ae0-'+name)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=clone,text=True).strip()==SHA and not subprocess.check_output(['git','status','--porcelain'],cwd=clone,text=True).strip()
    e=json.loads((p/'prepare.json').read_text())['env']
    commands.append({'name':name,'phase':'after','cwd':str(clone),'command':[str(clone/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),name,'after'],'env':e,'exit_code':0,'raw_log':str(p/'verify-after.log'),'raw_proof':str(p/'source-after/capsule-verification.json')})
save(R/'source-proof-commands.json',commands)
save(R/'capsule-verification-after.json',after)
save(R/'source-capsule-before-after.json',equality)
assert (repo/'casepath-api/artifacts/artifact-manifest.json').read_bytes()==(R/'artifact-manifest.json').read_bytes()

command=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'coordinator/coordinator-reconcile.py')]
with (R/'coordinator/reconciliation.log').open('x') as f:
    start=time.time(); result=subprocess.run(command,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
save(R/'coordinator/reconciliation-command.json',{'command':command,'cwd':str(repo),'env':env,'exit_code':result.returncode,'started_epoch':start,'finished_epoch':time.time()})
assert result.returncode==0
reconciled=json.loads((R/'coordinator/coordinator-independent-reconciliation.json').read_text())

sm=json.loads((R/'shard-map.json').read_text()); phases=[]; selected=[]; junitids=[]
perfile=collections.defaultdict(lambda:{'ids':set(),'phase_seconds':0.,'call_seconds':0.})
for n in range(1,7):
    p=R/f'shard{n}'; assigned=sm['shards'][str(n)]
    selected.extend(x['id'] for x in json.loads((p/'collected.json').read_text()))
    reports=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()]
    phases.extend(reports)
    for row in reports:
        f=row['id'].split('::')[0]; d=perfile[f]; d['ids'].add(row['id']);d['phase_seconds']+=row['duration']
        if row['when']=='call': d['call_seconds']+=row['duration']
    idx={(Path(i.split('::')[0]).stem+('.'+'.'.join(i.split('::')[1:-1]) if len(i.split('::'))>2 else ''),i.split('::')[-1]):i for i in assigned}
    for c in ET.parse(p/'junit.xml').findall('.//testcase'):
        matches=[i for (suffix,name),i in idx.items() if name==c.attrib['name'] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix))]
        assert len(matches)==1
        junitids.append(matches[0])
assigned=[i for v in sm['shards'].values() for i in v]
executed={x['id'] for x in phases}
for rows in [selected,junitids]: assert len(rows)==len(set(rows))==2486 and set(rows)==set(assigned)
assert executed==set(assigned)
for filename,data in [('selected-cloud-ids.txt',selected),('executed-cloud-ids.txt',executed),('junit-cloud-ids.txt',junitids)]: (R/filename).write_text('\n'.join(sorted(data))+'\n')
observed=[x for x in phases if x['outcome']=='skipped']; assert len(observed)==10
save(R/'observed-known-skips.json',observed)
save(R/'per-file-durations.json',{f:{'tests':len(v['ids']),'phase_seconds':v['phase_seconds'],'call_seconds':v['call_seconds']} for f,v in perfile.items()})
save(R/'per-test-durations.json',phases)
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()]
starts=[x for x in events if x['type']=='start'];finish=[x for x in events if x['type']=='finish']
assert len(starts)==len(finish)==6 and {x['shard'] for x in starts}==set(range(1,7))
assert all(len(x['active'])<=3 for x in events if 'active' in x)
assert all(x['free_bytes']>=3*1024**3 for x in starts)
blocked=[x for x in events if x['type']=='blocked_before_attempt']
assert len(blocked)==1 and blocked[0]['shard']==6 and blocked[0]['free_bytes']<3*1024**3
assert json.loads((R/'coordinator/initial-shard6-after-resource-recovery.json').read_text())['retry'] is False
observations=[json.loads(x) for x in (R/'resource-observations.jsonl').read_text().splitlines()]
native_intervals=[]
for n in range(1,7):
    result=json.loads((R/f'shard{n}/result.json').read_text()); native_intervals.extend([(result['started_epoch'],1,n),(result['finished_epoch'],-1,n)])
native_active=0;max_native_active=0
for epoch,delta,n in sorted(native_intervals):
    native_active+=delta;max_native_active=max(max_native_active,native_active)
assert native_active==0 and max_native_active<=3

resource={'epoch':time.time(),'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'minimum_observed_workspace_free_bytes':min(x['free_bytes'] for x in observations),'minimum_prelaunch_headroom_bytes':3*1024**3,'post_prepare_headroom_check_passed':json.loads((R/'prepare-summary.json').read_text())['adequate_headroom'],'all_attempt_start_headroom_checks_passed':True,'all_terminal_event_headroom_checks_passed':all(x['free_bytes']>=3*1024**3 for x in finish),'below_floor_terminal_events':[x for x in finish if x['free_bytes']<3*1024**3],'prelaunch_resource_blocks':blocked,'completed_runtime_retirement_receipt':str(R/'completed-shard1-runtime-retirement.json'),'previously_protected_server_pid595190_present':subprocess.run(['ps','-p','595190','-o','pid,ppid,comm'],capture_output=True,text=True).returncode==0}
assert resource['free_bytes']>=3*1024**3
save(R/'resource-after.json',resource)
proof={'candidate':SHA,'status':reconciled['status'],'mac_source_clean_before':None,'mac_source_clean_after':True,'collection_physical_clone':'shard6','full_inventory':2613,'cloud_assigned':2486,'cloud_raw_passed':2476,'cloud_known_skipped':10,'cloud_failed':0,'mac_partition':127,'mac_owner_attested_passed':127,'mac_raw_inspected_in_cloud':False,'no_overlap_or_gaps':True,'selected_collected_executed_junit_cloud_ids_identical':True,'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'mac_ids_sha256':digest(R/'mac-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'all_6_source_capsules_unchanged_at_actual_verification':True,'source_artifact_static_counts':[1709,25,39],'all_attempts_first_only':True,'max_heavy_active_observed':max(len(x['active']) for x in events if 'active' in x),'resource_after':resource}
save(R/'proof-disjoint-union-after.json',proof)
aggregate={**reconciled,'full_gate_complete':True,'source_verification_physical_clones':6,'collection_reuses_physical_clone':'shard6','completed_runtimes_retired_after_actual_source_after_proofs':[1],'completed_runtime_retirement_receipt':str(R/'completed-shard1-runtime-retirement.json'),'prelaunch_resource_block_did_not_execute_or_retry_shard6':True,'resource_after':resource,'native_attempt_interval_max_concurrency':max_native_active,'no_automatic_retries':True,'manifest_sha256':MANIFEST,'full_inventory_ids_sha256':proof['full_ids_sha256'],'cloud_ids_sha256':proof['cloud_ids_sha256'],'mac_ids_sha256':proof['mac_ids_sha256'],'source_artifact_static_counts':[1709,25,39],'all_six_capsules_verified_before_after':True,'capsule_receipt_file_sha256':after[0]['capsule_receipt_file_sha256'],'headroom_gib_after':resource['free_bytes']/1024**3,'max_heavy_active_observed':proof['max_heavy_active_observed'],'raw_phase_rows':len(phases),'artifact_manifest_sha256':digest(R/'artifact-manifest.json'),'no_product_edits':True,'no_seal_deploy_provider_or_product_requests':True}
save(R/'aggregate.json',aggregate)
save(R/'harness-provenance-final.json',[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for p in sorted([*R.joinpath('harness').glob('*.py'),*R.joinpath('coordinator').glob('*.py')])])
print(json.dumps({k:v for k,v in aggregate.items() if k not in ['known_skips','shards']}),flush=True)

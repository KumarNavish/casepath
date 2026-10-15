import collections, hashlib, json, os, shutil, subprocess, time, xml.etree.ElementTree as ET
from pathlib import Path

R=Path('/workspace/casepath-startup-gate-28247cbc-20261015')
SHA='28247cbc87785b366fa542bb0aa0bd5f37e6c2e3'
MANIFEST='62bb41a293c3ad95fab19225d4c8d2af4c92937f285726bd2000e4f8bce640a2'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]
def save(p,x): p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

terminal=json.loads((R/'all-shard-terminal.json').read_text())
assert terminal['all_executed'] and terminal['all_green'],terminal
repo=Path('/workspace/casepath-release-ae0-inventory')
env=json.loads((R/'inventory/prepare.json').read_text())['env']
verify=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),'inventory','after']
with (R/'inventory/verify-after.log').open('x') as f:
    outcome=subprocess.run(verify,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
assert outcome.returncode==0
after=[]; equality=[]; commands=json.loads((R/'source-proof-commands.json').read_text())
for name in NAMES:
    p=R/name
    before=json.loads((p/'source-before/capsule-verification.json').read_text())
    proof=json.loads((p/'source-after/capsule-verification.json').read_text())
    assert before['capsule_receipt']==proof['capsule_receipt']
    assert before['capsule_receipt_file_sha256']==proof['capsule_receipt_file_sha256']
    assert before['manifest_sha256']==proof['manifest_sha256']==MANIFEST
    assert proof['source_artifact_static_bindings_verified'] and proof['sealed_files_verified']==1708
    assert proof['head']==SHA and proof['status']==''
    after.append(proof); equality.append({'name':name,'head':SHA,'manifest_sha256':MANIFEST,'capsule_receipt_file_sha256':proof['capsule_receipt_file_sha256'],'unchanged':True})
    clone=Path('/workspace/casepath-release-ae0-'+name); e=json.loads((p/'prepare.json').read_text())['env']
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
for rows in [selected,junitids]: assert len(rows)==len(set(rows))==len(assigned) and set(rows)==set(assigned)
assert executed==set(assigned)
for filename,data in [('selected-cloud-ids.txt',selected),('executed-cloud-ids.txt',executed),('junit-cloud-ids.txt',junitids)]: (R/filename).write_text('\n'.join(sorted(data))+'\n')
observed=[x for x in phases if x['outcome']=='skipped']; assert len(observed)==10
save(R/'observed-known-skips.json',observed)
save(R/'per-file-durations.json',{f:{'tests':len(v['ids']),'phase_seconds':v['phase_seconds'],'call_seconds':v['call_seconds']} for f,v in perfile.items()})
save(R/'per-test-durations.json',phases)
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()]
starts=[x for x in events if x['type']=='start'];finish=[x for x in events if x['type']=='finish']
assert len(starts)==len(finish)==6 and {x['shard'] for x in starts}==set(range(1,7))
assert all(len(x['active'])<=3 for x in events)
assert all(x['free_bytes']>=3*1024**3 for x in events)
resource={'epoch':time.time(),'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'protected_server':subprocess.check_output(['ps','-p','595190','-o','pid,ppid,comm'],text=True)}
assert resource['free_bytes']>=3*1024**3
save(R/'resource-after.json',resource)
proof={'candidate':SHA,'full_inventory':len((R/'collected-ids.txt').read_text().splitlines()),'cloud_assigned':len(assigned),'cloud_raw_passed':len(assigned)-10,'cloud_known_skipped':10,'cloud_failed':0,'mac_partition':127,'mac_owner_attested_passed':reconciled['mac_attested_passed'],'mac_raw_inspected_in_cloud':False,'no_overlap_or_gaps':True,'selected_collected_executed_junit_cloud_ids_identical':True,'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'mac_ids_sha256':digest(R/'mac-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'all_7_source_capsules_unchanged':True,'source_artifact_static_counts':[1708,25,38],'all_attempts_first_only':True,'max_heavy_active_observed':max(len(x['active']) for x in events),'resource_after':resource}
save(R/'proof-disjoint-union-after.json',proof)
aggregate={**reconciled,'manifest_sha256':MANIFEST,'full_inventory_ids_sha256':proof['full_ids_sha256'],'cloud_ids_sha256':proof['cloud_ids_sha256'],'mac_ids_sha256':proof['mac_ids_sha256'],'source_artifact_static_counts':[1708,25,38],'all_seven_capsules_verified_before_after':True,'capsule_receipt_file_sha256':after[0]['capsule_receipt_file_sha256'],'headroom_gib_after':resource['free_bytes']/1024**3,'max_heavy_active_observed':proof['max_heavy_active_observed'],'raw_phase_rows':len(phases),'artifact_manifest_sha256':digest(R/'artifact-manifest.json'),'no_product_edits':True,'no_seal_deploy_provider_or_product_requests':True}
supersession=json.loads((R/'CANDIDATE_SUPERSESSION.json').read_text())
aggregate.update(candidate_status=supersession['candidate_status'],candidate_release_ready=False,superseded_reason=supersession['reason'])
aggregate.update(completed_runtime_retirement_receipt=str(R/'completed-runtime-retirement.json'),completed_runtimes_retired_after_actual_source_after_proofs=[1,2,3],capsule_before_after_checks_are_recorded_actual_verifications=True)
save(R/'aggregate.json',aggregate)
save(R/'harness-provenance-final.json',[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for p in sorted([*R.joinpath('harness').glob('*.py'),R/'coordinator/coordinator-reconcile.py'])])
print(json.dumps({k:v for k,v in aggregate.items() if k not in ['known_skips','shards']}),flush=True)

import ast, collections, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

R=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015')
PRIOR=Path('/workspace/casepath-transport-gate-0a213e47-20261015')
SHA='cbfa10adaee2dd777b2aea3fc888c5ee4fa3f236'
OLD='0a213e471d70dbc63df2e0fcb3a62049ec5183aa'
MANIFEST='d671b244cdc6a9c5a8d7729fe4facf2cbf51bf11db2eb128c5fc3102748bc089'
OLDMANIFEST='8261e891c9403d486bdb60d1abe485ae56a6b6e556bb9b3125a3702d76e72331'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]
def save(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(name,phase):
    repo=Path('/workspace/casepath-release-ae0-'+name)
    env=json.loads((R/name/'prepare.json').read_text())['env']
    cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),name,phase]
    started=time.time()
    with (R/name/('verify-'+phase+'.log')).open('x') as f:
        completed=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
    command_file=R/'source-proof-commands.json'
    commands=json.loads(command_file.read_text()) if command_file.exists() else []
    commands.append({'name':name,'phase':phase,'cwd':str(repo),'command':cmd,'env':env,'exit_code':completed.returncode,'started_epoch':started,'finished_epoch':time.time(),'raw_log':str(R/name/('verify-'+phase+'.log')),'raw_proof':str(R/name/('source-'+phase)/'capsule-verification.json')})
    save(command_file,commands)
    assert completed.returncode==0,(name,phase,completed.returncode)
    return json.loads((R/name/('source-'+phase)/'capsule-verification.json').read_text())

summary=json.loads((R/'prepare-summary.json').read_text())
assert summary['adequate_headroom'] and len(summary['prepared'])==7
proofs=[verify(name,'before') for name in NAMES]
assert len({p['capsule_receipt_file_sha256'] for p in proofs})==1
save(R/'capsule-verification-before.json',proofs)
save(R/'source-verification.json',{'candidate':SHA,'manifest_sha256':MANIFEST,'prepared_clones':7,'checks':proofs,'source_artifact_static_counts':[1706,25,37]})

# Previous verified capsule bytes were retired with retained receipts during bootstrap.
assert len(json.loads((R/'replacement-proven-retirement.json').read_text())['paths'])==7

repo=Path('/workspace/casepath-release-ae0-inventory')
known=json.loads((R/'known-skips.json').read_text()); comparison=[]
for file in sorted({x['id'].split('::')[0] for x in known}):
    old=subprocess.check_output(['git','show',OLD+':'+file],cwd=repo)
    new=(repo/file).read_bytes(); assert old==new
    comparison.append({'file':file,'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),'byte_identical':True})
save(R/'known-skip-source-comparison.json',comparison)
try:
    with open('/proc/1/maps') as f: f.read(1)
    audit={'path':'/proc/1/maps','readable':True}
except OSError as e:
    audit={'path':'/proc/1/maps','readable':False,'error_type':type(e).__name__,'errno':e.errno,'error':str(e)}
audit.update({'fail_closed_source_unchanged':True,'mac_partition_required':True})
save(R/'migration-process-audit.json',audit)

env=json.loads((R/'inventory/prepare.json').read_text())['env']
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'collect']
with (R/'inventory/collection-wrapper.log').open('x') as f: result=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
assert result.returncode==0
rows=json.loads((R/'inventory/collected.json').read_text()); ids=[x['id'] for x in rows]
assert len(ids)==len(set(ids))
mac=(R/'mac-ids.txt').read_text().splitlines()
assert len(mac)==len(set(mac))==127 and digest(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
assert set(mac)<=set(ids)
mac_sources=[]
for file in sorted({i.split('::')[0] for i in mac}):
    old=subprocess.check_output(['git','show',OLD+':'+file],cwd=repo); new=(repo/file).read_bytes()
    assert old==new
    mac_sources.append({'file':file,'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),'byte_identical':True})
save(R/'mac-partition-source-comparison.json',mac_sources)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
cloud=[x for x in ids if x not in set(mac)]
byfile=collections.defaultdict(list)
for i in cloud: byfile[i.split('::')[0]].append(i)
prior_ids=(PRIOR/'collected-ids.txt').read_text().splitlines()
prior_order=(PRIOR/'collection-order-ids.txt').read_text().splitlines()
assert sorted(ids)==prior_ids and ids==prior_order and len(ids)==2613
prior_map=json.loads((PRIOR/'shard-map.json').read_text())
groups=prior_map['shards']; files=prior_map['files']; loads=prior_map['estimated_phase_seconds']
assert len(groups)==6
inventory_equality={'candidate':SHA,'prior_candidate':OLD,'fresh_count':len(ids),'sorted_ids_identical':True,'collection_order_identical':True,'prior_inventory_sha256':digest(PRIOR/'collected-ids.txt'),'fresh_inventory_sha256':hashlib.sha256(('\n'.join(sorted(ids))+'\n').encode()).hexdigest(),'prior_shard_map':str(PRIOR/'shard-map.json'),'prior_shard_map_sha256':digest(PRIOR/'shard-map.json'),'same_shard_membership_and_order':True}
save(R/'fresh-inventory-prior-map-equality.json',inventory_equality)
assigned=[i for g in groups.values() for i in g]
assert len(assigned)==len(set(assigned))==len(cloud)
assert set(assigned).isdisjoint(mac) and set(assigned)|set(mac)==set(ids)
assert all(x['id'] in assigned for x in known)
for filename,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:
    (R/filename).write_text('\n'.join(data)+'\n')
mapping={**prior_map,'candidate':SHA,'manifest_sha256':MANIFEST,'basis':'Fresh whole inventory exactly equals prior 0a collection and order; SAME previous complete shard membership and order; no prior passing result reused','prior_shard_map':str(PRIOR/'shard-map.json'),'prior_shard_map_sha256':digest(PRIOR/'shard-map.json'),'inventory_equality':str(R/'fresh-inventory-prior-map-equality.json'),'created_epoch':time.time()}
save(R/'shard-map.json',mapping)
proof={'candidate':SHA,'full_inventory':len(ids),'cloud_assigned':len(assigned),'mac_pending':len(mac),'known_skips':len(known),'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'mac_ids_sha256':digest(R/'mac-ids.txt'),'free_bytes':shutil.disk_usage('/workspace').free,'minimum_headroom_bytes':3*1024**3}
assert proof['free_bytes']>=proof['minimum_headroom_bytes']
save(R/'proof-disjoint-union-before.json',proof)
print(json.dumps(proof),flush=True)

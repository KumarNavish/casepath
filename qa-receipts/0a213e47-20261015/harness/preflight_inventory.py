import ast, collections, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

R=Path('/workspace/casepath-transport-gate-0a213e47-20261015')
PRIOR=Path('/workspace/casepath-map-first-gate-d0d0fa7f-20261015')
SHA='0a213e471d70dbc63df2e0fcb3a62049ec5183aa'
OLD='d0d0fa7f9041f7405f1d8393bacd47d4332ee79b'
MANIFEST='8261e891c9403d486bdb60d1abe485ae56a6b6e556bb9b3125a3702d76e72331'
OLDMANIFEST='cf3bfbe377fb6bd2a3dd4f44f3c3ec1c3fce8864ba19840b822abf30fa1bdd8f'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]
def save(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(name,phase):
    repo=Path('/workspace/casepath-release-ae0-'+name)
    env=json.loads((R/name/'prepare.json').read_text())['env']
    cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),name,phase]
    with (R/name/('verify-'+phase+'.log')).open('x') as f:
        completed=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
    assert completed.returncode==0,(name,phase,completed.returncode)
    return json.loads((R/name/('source-'+phase)/'capsule-verification.json').read_text())

summary=json.loads((R/'prepare-summary.json').read_text())
assert summary['adequate_headroom'] and len(summary['prepared'])==7
proofs=[verify(name,'before') for name in NAMES]
assert len({p['capsule_receipt_file_sha256'] for p in proofs})==1
save(R/'capsule-verification-before.json',proofs)
save(R/'source-verification.json',{'candidate':SHA,'manifest_sha256':MANIFEST,'prepared_clones':7,'checks':proofs,'source_artifact_static_counts':[1706,25,37]})

# The replacement capsules are proven before retiring the former current caches.
retired=[]; before=shutil.disk_usage('/workspace').free
for name in NAMES:
    repo=Path('/workspace/casepath-release-ae0-'+name)
    p=repo/'.runtime/casepath-dev-v2/source-capsules'/OLDMANIFEST
    raw=(p/'CAPSULE_RECEIPT.json').read_bytes()
    oldproof=json.loads((PRIOR/name/'source-after/capsule-verification.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==oldproof['capsule_receipt_file_sha256']
    target=R/'retirement-receipts'/(name+'-'+OLDMANIFEST+'-CAPSULE_RECEIPT.json'); target.write_bytes(raw)
    row={'path':str(p),'prior_receipt_sha256':hashlib.sha256(raw).hexdigest(),'receipt_retained':str(target),'prior_successful_gate_proof':str(PRIOR/name/'source-after/capsule-verification.json'),'replacement_receipt_sha256':proofs[0]['capsule_receipt_file_sha256']}
    for child in p.rglob('*'):
        if child.is_dir(): child.chmod(0o700)
    p.chmod(0o700); shutil.rmtree(p); retired.append(row)
save(R/'replacement-proven-retirement.json',{'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'paths':retired,'retained':'venvs, source, evidence, journals, failed fixtures, active new capsules'})

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
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
cloud=[x for x in ids if x not in set(mac)]
byfile=collections.defaultdict(list)
for i in cloud: byfile[i.split('::')[0]].append(i)
prior=json.loads((PRIOR/'per-file-durations.json').read_text())
duration={f:prior[f]['phase_seconds'] if f in prior else max(.05,len(v)*.1) for f,v in byfile.items()}
groups={str(i):[] for i in range(1,7)}; files={str(i):[] for i in range(1,7)}; loads={str(i):0. for i in range(1,7)}
for file in sorted(byfile,key=lambda f:(-duration[f],f)):
    n=min(loads,key=lambda n:(loads[n],int(n)))
    groups[n].extend(byfile[file]);files[n].append(file);loads[n]+=duration[file]
assigned=[i for g in groups.values() for i in g]
assert len(assigned)==len(set(assigned))==len(cloud)
assert set(assigned).isdisjoint(mac) and set(assigned)|set(mac)==set(ids)
assert all(x['id'] in assigned for x in known)
for filename,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:
    (R/filename).write_text('\n'.join(data)+'\n')
mapping={'candidate':SHA,'manifest_sha256':MANIFEST,'basis':'Fresh whole inventory; exact fixed127 Mac complement assigned away; LPT whole-file packing from actual prior d0 raw durations; no prior passing result reused','duration_source':str(PRIOR/'per-file-durations.json'),'duration_source_sha256':digest(PRIOR/'per-file-durations.json'),'new_files_estimated':{f:duration[f] for f in byfile if f not in prior},'shards':groups,'files':files,'estimated_phase_seconds':loads,'counts':{n:len(v) for n,v in groups.items()},'max_active_heavy':3,'launcher_port_conflicts':'Mac CLI/local_data_root/journal restart partition kept whole; cloud launcher uses mocked/fake processes; no fixed real bind in cloud complement; normal clone runtimes and short HOME/TMP isolated per shard','created_epoch':time.time()}
save(R/'shard-map.json',mapping)
proof={'candidate':SHA,'full_inventory':len(ids),'cloud_assigned':len(assigned),'mac_pending':len(mac),'known_skips':len(known),'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'mac_ids_sha256':digest(R/'mac-ids.txt'),'free_bytes':shutil.disk_usage('/workspace').free,'minimum_headroom_bytes':3*1024**3}
assert proof['free_bytes']>=proof['minimum_headroom_bytes']
save(R/'proof-disjoint-union-before.json',proof)
print(json.dumps(proof),flush=True)

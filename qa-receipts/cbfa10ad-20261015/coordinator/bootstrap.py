import ast, hashlib, json, os, shutil, socket, subprocess, time
from pathlib import Path
R=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015')
P=Path('/workspace/casepath-transport-gate-0a213e47-20261015')
SHA='cbfa10adaee2dd777b2aea3fc888c5ee4fa3f236'
OLD='0a213e471d70dbc63df2e0fcb3a62049ec5183aa'
MAN='d671b244cdc6a9c5a8d7729fe4facf2cbf51bf11db2eb128c5fc3102748bc089'
OLDMAN='8261e891c9403d486bdb60d1abe485ae56a6b6e556bb9b3125a3702d76e72331'
NAMES=['inventory']+[f'shard{i}' for i in range(1,7)]
def save(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args): return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
assert socket.gethostname()=='656813ef2295'
assert R.is_dir() and {x.name for x in R.iterdir()}=={'coordinator'}
assert {x.name for x in (R/'coordinator').iterdir()}=={'root-source-review.json','root-reviewed-diff.patch'}
for name in ['harness','coordinator','retirement-receipts']+NAMES: (R/name).mkdir(mode=0o700,exist_ok=(name=='coordinator'))
for n in range(7):
 for prefix in ['ch','ct']:
  p=Path('/workspace/'+prefix+str(n)); assert not p.exists(); p.mkdir(mode=0o700)
resource={'epoch':time.time(),'host':socket.gethostname(),'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'workspace_free':shutil.disk_usage('/workspace').free,'tmp_free':shutil.disk_usage('/tmp').free,'protected_server':subprocess.check_output(['ps','-p','595190','-o','pid,ppid,comm'],text=True),'environment_names':sorted(os.environ)}
save(R/'resource-before.json',resource)
paths=[*P.joinpath('harness').glob('*.py'),P/'coordinator/coordinator-reconcile.py']
provenance=[]
for p in paths:
 target=R/p.relative_to(P)
 raw=p.read_text().replace(str(P),str(R)).replace(OLD,SHA).replace(OLDMAN,MAN).replace('/workspace/oh','/workspace/ch').replace('/workspace/ot','/workspace/ct')
 target.write_text(raw)
 provenance.append({'path':target.relative_to(R).as_posix(),'prior_path':str(p),'prior_sha256':digest(p),'adapted_sha256':digest(target)})
for name in ['known-skips.json','mac-ids.txt']:
 shutil.copyfile(P/name,R/name)
# Retire only exactly identified, previously verified disposable capsule bytes.
retired=[]; free_before=shutil.disk_usage('/workspace').free
for name in NAMES:
 repo=Path('/workspace/casepath-release-ae0-'+name)
 assert (repo/'.git').is_dir() and git(repo,'rev-parse','HEAD')==OLD and not git(repo,'status','--porcelain')
 proofpath=P/name/'source-after/capsule-verification.json'; proof=json.loads(proofpath.read_text())
 cap=repo/'.runtime/casepath-dev-v2/source-capsules'/OLDMAN
 assert str(cap)==proof['capsule_root'] and proof['head']==OLD and proof['manifest_sha256']==OLDMAN and proof['source_artifact_static_bindings_verified'] and proof['sealed_files_verified']==1706
 receipt=cap/'CAPSULE_RECEIPT.json'; raw=receipt.read_bytes()
 assert digest(receipt)==proof['capsule_receipt_file_sha256'] and json.loads(raw)==proof['capsule_receipt']
 retained=R/'retirement-receipts'/(name+'-'+OLDMAN+'-CAPSULE_RECEIPT.json'); retained.write_bytes(raw)
 for p in cap.rglob('*'):
  assert not p.is_symlink()
  if p.is_dir(): p.chmod(0o700)
 cap.chmod(0o700); shutil.rmtree(cap)
 retired.append({'path':str(cap),'prior_successful_gate_proof':str(proofpath),'prior_proof_sha256':digest(proofpath),'prior_receipt_sha256':hashlib.sha256(raw).hexdigest(),'receipt_retained':str(retained)})
save(R/'replacement-proven-retirement.json',{'before_free_bytes':free_before,'after_free_bytes':shutil.disk_usage('/workspace').free,'paths':retired,'retained':'venvs, Git/source, old raw evidence and receipts, journals, failed fixtures; protected server untouched'})
# Adapt preflight to fresh equality proof and the SAME prior complete shard membership.
p=R/'harness/preflight_inventory.py'; s=p.read_text()
s=s.replace("PRIOR=Path('/workspace/casepath-map-first-gate-d0d0fa7f-20261015')",'PRIOR=Path('+repr(str(P))+')')
s=s.replace("OLD='d0d0fa7f9041f7405f1d8393bacd47d4332ee79b'","OLD='"+OLD+"'")
s=s.replace("OLDMANIFEST='cf3bfbe377fb6bd2a3dd4f44f3c3ec1c3fce8864ba19840b822abf30fa1bdd8f'","OLDMANIFEST='"+OLDMAN+"'")
a=s.index('# The replacement capsules are proven'); b=s.index("repo=Path('/workspace/casepath-release-ae0-inventory')",a)
s=s[:a]+"# Previous verified capsule bytes were retired with retained receipts during bootstrap.\nassert len(json.loads((R/'replacement-proven-retirement.json').read_text())['paths'])==7\n\n"+s[b:]
a=s.index("prior=json.loads((PRIOR/'per-file-durations.json')"); b=s.index('assigned=[i for g in groups.values() for i in g]',a)
s=s[:a]+"""prior_ids=(PRIOR/'collected-ids.txt').read_text().splitlines()
prior_order=(PRIOR/'collection-order-ids.txt').read_text().splitlines()
assert sorted(ids)==prior_ids and ids==prior_order and len(ids)==2613
prior_map=json.loads((PRIOR/'shard-map.json').read_text())
groups=prior_map['shards']; files=prior_map['files']; loads=prior_map['estimated_phase_seconds']
assert len(groups)==6
inventory_equality={'candidate':SHA,'prior_candidate':OLD,'fresh_count':len(ids),'sorted_ids_identical':True,'collection_order_identical':True,'prior_inventory_sha256':digest(PRIOR/'collected-ids.txt'),'fresh_inventory_sha256':hashlib.sha256(('\\n'.join(sorted(ids))+'\\n').encode()).hexdigest(),'prior_shard_map':str(PRIOR/'shard-map.json'),'prior_shard_map_sha256':digest(PRIOR/'shard-map.json'),'same_shard_membership_and_order':True}
save(R/'fresh-inventory-prior-map-equality.json',inventory_equality)
"""+s[b:]
a=s.index("mapping={'candidate':"); b=s.index("save(R/'shard-map.json',mapping)",a)
s=s[:a]+"""mapping={**prior_map,'candidate':SHA,'manifest_sha256':MANIFEST,'basis':'Fresh whole inventory exactly equals prior 0a collection and order; SAME previous complete shard membership and order; no prior passing result reused','prior_shard_map':str(PRIOR/'shard-map.json'),'prior_shard_map_sha256':digest(PRIOR/'shard-map.json'),'inventory_equality':str(R/'fresh-inventory-prior-map-equality.json'),'created_epoch':time.time()}
"""+s[b:]
p.write_text(s)
# Preserve truthful pending Mac status until the current exact-candidate attestation arrives.
p=R/'harness/finalize.py'; s=p.read_text(); s=s.replace("'mac_owner_attested_passed':127", "'mac_owner_attested_passed':reconciled['mac_attested_passed']")
p.write_text(s)
for row in provenance: row['adapted_sha256']=digest(R/row['path'])
save(R/'harness-provenance.json',provenance)
save(R/'EXECUTION_AUTHORIZATION.json',{'signal':'FINAL_GATE_AUTHORIZED','candidate':SHA,'manifest_sha256':MAN,'source':'Root owner delegated explicitly authorized exact frozen full six-shard deterministic gate; one attempt per shard; no retries','max_heavy_active':3,'mac_attestation':'PENDING'})
source=Path('/workspace/casepath-stream-transport-20261015')
assert git(source,'rev-parse','FETCH_HEAD')==SHA
for name in NAMES:
 repo=Path('/workspace/casepath-release-ae0-'+name); out=R/name
 commands=[['git','fetch',str(source),SHA],['git','checkout','--detach',SHA]]
 with (out/'fetch.log').open('x') as log:
  for cmd in commands: subprocess.run(cmd,cwd=repo,check=True,stdout=log,stderr=subprocess.STDOUT)
 assert git(repo,'rev-parse','HEAD')==SHA and not git(repo,'status','--porcelain')
 assert digest(repo/'casepath/source-manifest.json')==MAN
 save(out/'checkout.json',{'commands':commands,'cwd':str(repo),'head':SHA,'status':'','manifest_sha256':MAN,'local_canonical_source':str(source)})
shutil.copyfile(Path('/workspace/casepath-release-ae0-inventory/casepath/source-manifest.json'),R/'source-manifest.json')
shutil.copyfile(Path('/workspace/casepath-release-ae0-inventory/casepath-api/artifacts/artifact-manifest.json'),R/'artifact-manifest.json')
save(R/'canonical-fetch.json',{'candidate':SHA,'canonical_source':str(source),'canonical_fetch_head':git(source,'rev-parse','FETCH_HEAD'),'canonical_working_head_preserved':git(source,'rev-parse','HEAD'),'isolated_clone_count':7,'all_clean':True,'manifest_sha256':MAN})
for p in [*R.joinpath('harness').glob('*.py'),R/'coordinator/coordinator-reconcile.py']: ast.parse(p.read_text())
print(json.dumps({'output_root':str(R),'retired_verified_capsules':len(retired),'all_seven_clean_at':SHA,'free_bytes':shutil.disk_usage('/workspace').free,'protected_server_pid':595190,'mac_status':'PENDING'}),flush=True)

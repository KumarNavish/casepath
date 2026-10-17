import hashlib,io,json,subprocess,time
from pathlib import Path

OUT=Path(__file__).resolve().parent
REPO=Path('/workspace/casepath-release-ae0-shard6')
SHA='c925a0267971edb52fea5f2bd9653a2495b7ac15'
EXPECTED='1d4da0d965b790395b2d45979f04cc5e8f391b8a8accbeee7a6b1253d472c758'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=REPO)
manifest_raw=git('show',f'{SHA}:casepath/source-manifest.json')
assert hashlib.sha256(manifest_raw).hexdigest()==EXPECTED
manifest=json.loads(manifest_raw)
rows=manifest['files']
assert len(rows)==1714 and len({row['path'] for row in rows})==1714
requests=''.join(f'{SHA}:{row["path"]}\n' for row in rows).encode()
run=subprocess.run(['git','cat-file','--batch'],cwd=REPO,input=requests,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
stream=io.BytesIO(run.stdout)
for row in rows:
    header=stream.readline().decode().split()
    assert len(header)==3 and header[1]=='blob',(row['path'],header)
    data=stream.read(int(header[2]))
    assert stream.read(1)==b'\n'
    assert len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
assert not stream.read()
pins={
 '401f0a707f01dc502e3e4d2b86271426b8372c97':[
  'casepath/assets/autonomous-workspace-v1.js','casepath/assets/autonomous-workspace-v1.css',
  'casepath/assets/autonomous-entry-v1.js','casepath/tools/build_static_site.py','casepath/index.html'],
 '7bd58dc8e0fd66a7f7edd9ad0de105d35acd3cc5':[
  'casepath/assets/autonomous-language-v1.js','casepath-qa/autonomous-language-v1.test.cjs'],
 '5975246c74ce14bc48763d9c6cc8a98a8fa3bfee':[
  'casepath-qa/autonomous-workspace-v1.test.cjs','casepath-qa/unified-product-browser-v1.test.cjs',
  'casepath/tools/test_build_deployment_identity.py'],
 'cb648a3e8a7c5ef3605f25273afc14c3a247d52b':[
  'casepath-api/casepath_api/autonomous_store_v1.py','casepath-api/casepath_api/hosted_storage_v1.py',
  'casepath-api/tests/test_autonomous_knowledge_reads_v1.py',
  'casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py',
  'casepath-api/tests/test_hosted_source_batch_v1.py']}
verified=[]
for commit,paths in pins.items():
    for path in paths:
        canonical=git('show',f'{SHA}:{path}')
        worker=git('show',f'{commit}:{path}')
        assert canonical==worker,path
        verified.append({'path':path,'worker_commit':commit,'sha256':hashlib.sha256(canonical).hexdigest()})
allowed={row['path'] for row in verified}|{'casepath/index.html','casepath/source-manifest.json'}
changed=set(git('diff','--name-only','65a796a5dfb21f4cdbe0a3d1a4925b931710b30c',SHA).decode().splitlines())
assert changed==allowed,(changed-allowed,allowed-changed)
old='casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py::test_warm_read_has_two_fresh_compact_proofs_without_raw_bytes_or_writes'
new=old.replace('two_fresh_compact_proofs','one_final_atomic_proof')
old_inventory=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017/collected-ids.txt').read_bytes()
assert old_inventory.decode().splitlines().count(old)==1
test_source=git('show',f'{SHA}:casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py').decode()
assert 'def '+new.split('::')[-1]+'(' in test_source
assert 'def '+old.split('::')[-1]+'(' not in test_source
result={'candidate':SHA,'manifest_sha256':EXPECTED,'sealed_files_verified':len(rows),
 'against':'immutable canonical Git blobs, independent of prepared working trees',
 'source_paths_exact_worker_bytes':verified,'only_expected_changed_paths':sorted(changed),
 'instructions_unchanged_from65':not bool(git('diff','--name-only','65a796a5dfb21f4cdbe0a3d1a4925b931710b30c',SHA,'--','AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md').strip()),
 'baseline_inventory_ids':len(old_inventory.decode().splitlines()),
 'baseline_inventory_sha256':hashlib.sha256(old_inventory).hexdigest(),
 'explicit_renamed_ids':[{'old_id':old,'new_id':new}],
 'tests_executed_by_this_check':0,'source_modified':False,'verified_epoch':time.time()}
(OUT/'source-identity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'candidate':SHA,'sealed_files':len(rows),'worker_files':len(verified),'expected_changed_paths':len(changed),'renamed_ids':1,'passed':True}))

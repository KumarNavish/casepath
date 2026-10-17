import hashlib,io,json,subprocess,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
REPO=Path('/workspace/casepath-release-ae0-shard6')
FRONT=Path('/workspace/casepath-knowledge-startup-render-20261018')
SHA='abf3c90eb351bbd0cffe7ca65ad4c3a7a292f67c'
BASE='c925a0267971edb52fea5f2bd9653a2495b7ac15'
EXPECTED='46a2fc752a399545ea4c67049e0ef82f45a42eab4d0131d4adbad1d9596801aa'
def git(*args,repo=REPO):return subprocess.check_output(['git',*args],cwd=repo)
manifest_raw=git('show',f'{SHA}:casepath/source-manifest.json')
assert hashlib.sha256(manifest_raw).hexdigest()==EXPECTED
rows=json.loads(manifest_raw)['files']
assert len(rows)==len({row['path'] for row in rows})==1714
requests=''.join(f'{SHA}:{row["path"]}\n' for row in rows).encode()
run=subprocess.run(['git','cat-file','--batch'],cwd=REPO,input=requests,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
stream=io.BytesIO(run.stdout)
for row in rows:
 header=stream.readline().decode().split();assert len(header)==3 and header[1]=='blob'
 data=stream.read(int(header[2]));assert stream.read(1)==b'\n'
 assert len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
assert not stream.read()
pins=[(FRONT,'a83ef2acd71d6cfc47dd61337e2dd0bb6eff7c33',[
 'casepath/assets/autonomous-entry-v1.js','casepath/assets/autonomous-workspace-v1.js',
 'casepath-qa/autonomous-workspace-v1.test.cjs','casepath-qa/sites-autonomous-entry.test.cjs']),
 (REPO,'0ff22cce40e6e29b481e698753eac4371e195c75',[
 'casepath-api/casepath_api/hosted_app_v1.py','casepath-api/casepath_api/hosted_proxy_v1.py',
 'casepath/tools/sites_worker.mjs','casepath-api/tests/test_hosted_proxy_v1.py','casepath-qa/sites-proxy.test.cjs'])]
verified=[]
for repo,commit,paths in pins:
 for path in paths:
  canonical=git('show',f'{SHA}:{path}');worker=git('show',f'{commit}:{path}',repo=repo)
  assert canonical==worker,path
  verified.append({'path':path,'worker_commit':commit,'sha256':hashlib.sha256(canonical).hexdigest()})
allowed={row['path'] for row in verified}|{'casepath/index.html','casepath/source-manifest.json'}
changed=set(git('diff','--name-only',BASE,SHA).decode().splitlines());assert changed==allowed
index=git('show',f'{SHA}:casepath/index.html').decode()
for path in ['casepath/assets/autonomous-entry-v1.js','casepath/assets/autonomous-workspace-v1.js']:
 new=hashlib.sha256(git('show',f'{SHA}:{path}')).hexdigest();old=hashlib.sha256(git('show',f'{BASE}:{path}')).hexdigest()
 assert new in index;index=index.replace(new,old)
assert index==git('show',f'{BASE}:casepath/index.html').decode()
assert not git('diff','--name-only',BASE,SHA,'--','AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md').strip()
old_ids=Path('/workspace/casepath-roles-final-gate-c925a026-20261018/collected-ids.txt').read_bytes()
assert len(old_ids.decode().splitlines())==2764
result={'candidate':SHA,'manifest_sha256':EXPECTED,'sealed_files_verified':1714,'source_paths_exact_worker_bytes':verified,
 'only_expected_changed_paths':sorted(changed),'index_only_existing_script_hash_pins_changed':True,
 'instructions_unchanged_from_c925':True,'baseline_c925_inventory_ids':2764,'baseline_c925_inventory_sha256':hashlib.sha256(old_ids).hexdigest(),
 'tests_executed_by_this_check':0,'source_modified':False,'verified_epoch':time.time()}
(OUT/'source-identity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'candidate':SHA,'sealed_files':1714,'worker_files':len(verified),'changed_paths':len(changed)}))

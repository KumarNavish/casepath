import hashlib,io,json,subprocess,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
REPO=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
FRONT=Path('/workspace/casepath-knowledge-startup-render-20261018')
SHA='4a03578bcaecd0cc4948d36747d96ce68e905244'
BASE='abf3c90eb351bbd0cffe7ca65ad4c3a7a292f67c'
EXPECTED='2a88cc939faa82c47132970a67275f2f6bda6fd20a98cb7dcdf22d463fe61a50'
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
worker='105ef1abf9cfd872f1898dab2d155c3de36e5f28'
assert git('rev-parse',SHA+'^').decode().strip()==worker
assert git('diff','--name-only',worker,SHA).decode().splitlines()==['casepath/source-manifest.json']
changed=set(git('diff','--name-only',BASE,SHA).decode().splitlines())
assert changed=={'casepath/tools/sites_worker.mjs','casepath/source-manifest.json'}
path='casepath/tools/sites_worker.mjs';raw=git('show',f'{SHA}:{path}')
assert raw==git('show',f'{worker}:{path}')
assert hashlib.sha256(raw).hexdigest()=='d5930a5937cd73321f25feef114db7600b9d5070111f5c859ec838ad5428a085'
verified=[{'path':path,'worker_commit':worker,'sha256':hashlib.sha256(raw).hexdigest()}]
assert git('show',f'{SHA}:casepath/index.html')==git('show',f'{BASE}:casepath/index.html')
assert not git('diff','--name-only',BASE,SHA,'--','AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md').strip()
old_ids=Path('/workspace/casepath-roles-final-gate-c925a026-20261018/collected-ids.txt').read_bytes()
assert len(old_ids.decode().splitlines())==2764
result={'candidate':SHA,'manifest_sha256':EXPECTED,'sealed_files_verified':1714,'source_paths_exact_worker_bytes':verified,
 'only_expected_changed_paths':sorted(changed),'index_byte_identical_to_failed_abf':True,
 'instructions_unchanged_from_failed_abf':True,'frontend_bytes_unchanged':True,'only_seal_added_after_worker':True,'baseline_c925_inventory_ids':2764,'baseline_c925_inventory_sha256':hashlib.sha256(old_ids).hexdigest(),
 'tests_executed_by_this_check':0,'source_modified':False,'verified_epoch':time.time()}
(OUT/'source-identity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'candidate':SHA,'sealed_files':1714,'worker_files':len(verified),'changed_paths':len(changed)}))

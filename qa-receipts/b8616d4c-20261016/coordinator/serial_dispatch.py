import hashlib,json,os,shutil,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
SHA='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
MAN='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
MIN=3*1024**3
BRANCH='qa-receipts/b8616d4c-20261016'
D=G/BRANCH
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=G,text=True).strip()
def event(x):
 x['epoch']=time.time()
 with (R/'scheduler-events.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
 print(json.dumps(x),flush=True)
def checkpoint(label):
 # Only authored harness, exact raw receipts and proofs; retain fixture/runtime data locally.
 files=[]
 for p in sorted(R.rglob('*')):
  rel=p.relative_to(R)
  if p.is_symlink() or not p.is_file() or any(x in rel.parts for x in ['pycache','pytest-tmp','uv-cache','home','tmp','artifact-registry']):continue
  if p.suffix in ['.json','.jsonl','.txt','.log','.py','.xml','.cfg','.gz'] and p.name not in ['dispatch-wrapper.log','checkpoint-SHA256SUMS.txt','checkpoint-raw.tar.gz']:
   if p.name=='checkpoint-receipt.json':continue
   files.append(p)
 checks=''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in files)
 (R/'checkpoint-SHA256SUMS.txt').write_text(checks)
 archive=R/'checkpoint-raw.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=6) as t:
  for p in files+[R/'checkpoint-SHA256SUMS.txt']:t.add(p,arcname=p.relative_to(R),recursive=False)
 with tarfile.open(archive,'r:gz') as t:
  for p in files:
   assert hashlib.sha256(t.extractfile(p.relative_to(R).as_posix()).read()).hexdigest()==digest(p)
 if git('branch','--show-current')!=BRANCH:
  assert not git('status','--porcelain');subprocess.run(['git','switch','-c',BRANCH],cwd=G,check=True)
 D.mkdir(parents=True,exist_ok=True)
 for p in files+[R/'checkpoint-SHA256SUMS.txt',archive]:
  q=D/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 subprocess.run(['git','add','--',BRANCH],cwd=G,check=True)
 subprocess.run(['git','commit','-m',f'qa: b861 fullgate {label} raw receipts'],cwd=G,check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['git','push','--set-upstream','origin',BRANCH],cwd=G,check=True,stdout=subprocess.DEVNULL)
 remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+BRANCH],cwd=G,text=True).split()[0];assert remote==git('rev-parse','HEAD')
 row={'label':label,'branch':BRANCH,'commit':remote,'archive_sha256':digest(archive),'raw_files':len(files),'epoch':time.time()}
 save(R/'checkpoint-receipt.json',row);event({'type':'checkpoint_pushed',**row})
 return row
def verify(n,phase):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}');env=json.loads((out/'prepare.json').read_text())['env']
 cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),f'shard{n}',phase];start=time.time()
 with (out/f'verify-{phase}.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 commands=json.loads((R/'source-proof-commands.json').read_text());commands.append({'name':f'shard{n}','phase':phase,'command':cmd,'cwd':str(repo),'env':env,'exit_code':p.returncode,'started_epoch':start,'finished_epoch':time.time()});save(R/'source-proof-commands.json',commands)
 assert p.returncode==0,(n,phase)
def retire_runtime(n,checkpoint_receipt):
 repo=Path(f'/workspace/casepath-release-ae0-shard{n}');out=R/f'shard{n}'
 before=json.loads((out/'source-before/capsule-verification.json').read_text());after=json.loads((out/'source-after/capsule-verification.json').read_text())
 assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 assert json.loads((out/'result.json').read_text())['exit_code']==0
 assert digest(D/f'shard{n}/source-after/capsule-verification.json')==digest(out/'source-after/capsule-verification.json')
 assert digest(D/f'shard{n}/reports.jsonl')==digest(out/'reports.jsonl')
 assert git('rev-parse','HEAD')==checkpoint_receipt['commit']
 paths=[repo/'.runtime/casepath-dev-v2/source-capsules'/MAN,repo/'.runtime/casepath-dev-v2/venv']
 record={'candidate':SHA,'shard':n,'paths':list(map(str,paths)),'before_free_bytes':shutil.disk_usage('/workspace').free,'pre_post_source_capsule_proofs_and_raw_receipts_archived_and_durably_pushed':True,'evidence_commit':checkpoint_receipt['commit'],'archive_sha256':checkpoint_receipt['archive_sha256'],'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'preserved':'All source/Git/refs/raw receipts/unique and failed fixtures/journals/runtime home/tmp/boots','epoch':time.time()}
 for p in paths:
  assert p.is_dir() and not p.is_symlink()
  for root,dirs,files in os.walk(p):os.chmod(root,0o700)
  shutil.rmtree(p)
 record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'completed-shard{n}-runtime-retirement.json',record);event({'type':'runtime_retired','shard':n,'free_bytes':record['after_free_bytes'],'evidence_commit':checkpoint_receipt['commit']})
def prepare(n):
 repo=Path(f'/workspace/casepath-release-ae0-shard{n}');out=R/f'shard{n}'
 env=dict(os.environ);env.update(HOME=f'/workspace/bh{n}',TMPDIR=f'/workspace/bt{n}',TMP=f'/workspace/bt{n}',TEMP=f'/workspace/bt{n}')
 with (out/'prepare-wrapper.log').open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/'harness/prepare_clones.py'),f'shard{n}'],cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0,n
 verify(n,'before')
 summary=json.loads((R/'prepare-summary.json').read_text());summary['prepared'].append({'name':f'shard{n}','exit_code':0});summary.update(free_bytes=shutil.disk_usage('/workspace').free);save(R/'prepare-summary.json',summary)
 cache=Path('/workspace/.cache/uv')
 if cache.exists():
  # The pinned normal prepare finished and its full source proof is retained before retiring only a reproducible cache.
  archive=R/'retirement-receipts'/f'shard{n}-normal-prepare-before-uv-cache-retirement.tar.gz'
  with tarfile.open(archive,'w:gz') as t:
   for p in [out/'prepare.json',out/'prepare.log',out/'source-before/CAPSULE_RECEIPT.json',out/'source-before/capsule-verification.json']:t.add(p,arcname=p.relative_to(R),recursive=False)
  row={'candidate':SHA,'shard':n,'path':str(cache),'archive':str(archive),'archive_sha256':digest(archive),'before_free_bytes':shutil.disk_usage('/workspace').free,'owned_successful_current_normal_prepare_cache_only':True}
  shutil.rmtree(cache);row['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'finished-prepare{n}-uv-cache-retirement.json',row)
assert json.loads((R/'EXECUTION_AUTHORIZATION.json').read_text())['signal']=='FINAL_GATE_AUTHORIZED'
proof=json.loads((R/'proof-disjoint-union-before.json').read_text());assert proof['candidate']==SHA and proof['no_overlap_or_gaps'] and proof['full_inventory']==2613
with (R/'FULL_GATE_PROCESS_STARTED.json').open('x') as f:json.dump({'candidate':SHA,'pid':os.getpid(),'epoch':time.time(),'max_active_heavy':1,'host_ceiling':3,'no_automatic_retry':True,'resource_floor_bytes':MIN,'sequential_separate_normal_clones':True},f,indent=2)
rows=[]
for n in range(1,7):
 if n>1:prepare(n)
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}');env=json.loads((out/'prepare.json').read_text())['env']
 free=shutil.disk_usage('/workspace').free
 assert free>=MIN,('resource floor',n,free)
 assert not (out/'ATTEMPT_STARTED.json').exists()
 event({'type':'start','shard':n,'active':[n],'free_bytes':free,'home':env['HOME'],'tmp':env['TMPDIR']})
 cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',str(n)]
 with (out/'wrapper.log').open('x') as log:
  p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
  event({'type':'native_process_started','shard':n,'pid':p.pid,'command':cmd,'active':[n],'free_bytes':shutil.disk_usage('/workspace').free})
  while p.poll() is None:
   with (R/'resource-observations.jsonl').open('a') as f:f.write(json.dumps({'epoch':time.time(),'shard':n,'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free})+'\n')
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:pass
 verify(n,'after')
 row={'shard':n,'exit_code':p.returncode,'source_after_exit_code':0,'result_path':str(out/'result.json'),'attempt_count':1};rows.append(row)
 event({'type':'finish',**row,'active':[],'free_bytes':shutil.disk_usage('/workspace').free})
 save(R/'all-shard-terminal.json',{'candidate':SHA,'results':rows,'all_executed':len(rows)==6,'all_green':all(x['exit_code']==0 and x['source_after_exit_code']==0 for x in rows),'epoch':time.time()})
 receipt=checkpoint(f'shard{n}-terminal')
 if p.returncode:raise SystemExit(p.returncode)
 if n<6:retire_runtime(n,receipt)
print(json.dumps({'all_native_shards_terminal':True,'candidate':SHA,'results':rows}),flush=True)

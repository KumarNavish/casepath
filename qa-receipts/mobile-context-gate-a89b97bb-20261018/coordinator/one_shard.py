import concurrent.futures,hashlib,io,json,os,shutil,subprocess,tarfile,threading,time
from pathlib import Path
R=Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
SHA='a89b97bb8eecdd8e98771c99ca879d4e253f7881';MAN='416eea6c4831046fca1bab76ec7072bc116cdc2912a169b094341d3a2ee68b0a'
MIN=3*1024**3;PREPARE_BYTES=300*1024**2;RESERVE=150*1024**2
repos=json.loads((R/'clone-map.json').read_text())['repos'];lock=threading.RLock();prepare_lock=threading.Lock();active={};rows=[];stop_launch=threading.Event()
base_env={'HOME':'/workspace/a9h0','TMPDIR':'/workspace/a9t0','TMP':'/workspace/a9t0','TEMP':'/workspace/a9t0','PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
transport=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS'];process_env=dict(base_env);process_env.update({k:os.environ[k] for k in transport if k in os.environ})
def budget():
 value=json.loads((R/'heavy-budget.json').read_text())['max_gate_heavy']
 assert value in [1,2,3]
 return value
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def event(value):
 with lock:
  row={'epoch':time.time(),**value}
  with (R/'scheduler-events.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
  print(json.dumps(row),flush=True)
def observe(n):
 with lock:
  row={'epoch':time.time(),'shard':n,'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'active':dict(active)}
  with (R/'resource-observations.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
  if row['free_bytes']<MIN:
   stop_launch.set();event({'type':'RESOURCE_FLOOR_BREACH','shard':n,'free_bytes':row['free_bytes'],'active':dict(active)})
def checked(cmd,repo,env,log):
 with log.open('x') as stream:p=subprocess.run(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT)
 return p.returncode
def verify(n,phase):
 repo=Path(repos[n]);cmd=['/usr/bin/python3',str(R/'coordinator/verify.py'),n,phase]
 code=checked(cmd,repo,base_env,R/f'shard{n}/verify-{phase}-wrapper.log');assert code==0,('source_verify',n,phase,code)
def archive(n):
 out=R/f'shard{n}';archive_dir=R/'retirement-receipts';archive_dir.mkdir(exist_ok=True);target=archive_dir/f'shard{n}-raw.tar.gz'
 files=[p for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and not any(x in p.relative_to(out).parts for x in ['pycache','pytest-tmp','uv-cache','home','tmp','artifact-registry'])]
 with tarfile.open(target,'w:gz',compresslevel=3) as t:
  for p in files:t.add(p,arcname=p.relative_to(out).as_posix(),recursive=False)
 with tarfile.open(target,'r:gz') as t:
  for p in files:assert hashlib.sha256(t.extractfile(p.relative_to(out).as_posix()).read()).hexdigest()==digest(p)
 record={'shard':n,'archive':str(target),'archive_sha256':digest(target),'raw_archive_byte_verified':True,'files':{p.relative_to(out).as_posix():digest(p) for p in files},'pushed':False}
 save(archive_dir/f'shard{n}-raw-archive.json',record);return record
def retire(n,arch):
 out=R/f'shard{n}';repo=Path(repos[n]);before=json.loads((out/'source-before/capsule-verification.json').read_text());after=json.loads((out/'source-after/capsule-verification.json').read_text());assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 assert json.loads((out/'result.json').read_text())['exit_code']==0 and arch['raw_archive_byte_verified']
 paths=[repo/'.runtime/casepath-dev-v2/source-capsules'/MAN,repo/'.runtime/casepath-dev-v2/venv']
 record={'candidate':SHA,'shard':n,'paths':list(map(str,paths)),'before_free_bytes':shutil.disk_usage('/workspace').free,'exact_source_and_capsule_before_after_equal':True,'raw_receipts_preserved_and_archive_byte_verified':True,'archive_sha256':arch['archive_sha256'],'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'authorization':'Parent allows newly completed owned runtime/capsule/cache retirement after exact proofs and raw receipt preservation'}
 for p in paths:
  assert p.is_dir() and not p.is_symlink()
  for directory,dirs,files in os.walk(p):os.chmod(directory,0o700)
  shutil.rmtree(p)
 record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'completed-shard{n}-runtime-retirement.json',record);event({'type':'completed_runtime_retired','shard':n,'free_bytes':record['after_free_bytes']})
def one(n):
 out=R/f'shard{n}';repo=Path(repos[n]);seen_failed=set()
 with lock:
  active[n]='reserved';assert len(active)<=budget();event({'type':'heavy_slot_reserved','shard':n,'active':dict(active)})
 try:
  if not (out/'prepare.json').exists():
   with prepare_lock:
    assert shutil.disk_usage('/workspace').free>=MIN+PREPARE_BYTES
    with lock:active[n]='prepare'
    event({'type':'prepare_start','shard':n,'free_bytes':shutil.disk_usage('/workspace').free})
    code=checked(['/usr/bin/python3',str(R/'harness/prepare_clones.py'),f'shard{n}'],repo,process_env,out/'prepare-wrapper.log');assert code==0,('prepare',n,code)
    cache=out/'uv-cache';record={'path':str(cache),'normal_prepare_exit_code':0,'before_free_bytes':shutil.disk_usage('/workspace').free,'only_owned_reproducible_cache':True}
    if cache.exists():shutil.rmtree(cache)
    record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(out/'prepare-cache-retirement.json',record)
  if not (out/'source-before/capsule-verification.json').exists():verify(n,'before')
  env=json.loads((out/'prepare.json').read_text())['env'];assert shutil.disk_usage('/workspace').free>=MIN
  with lock:active[n]='pytest'
  cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',n]
  with (out/'wrapper.log').open('x') as stream:
   p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT);event({'type':'pytest_start','shard':n,'pid':p.pid,'command':cmd,'free_bytes':shutil.disk_usage('/workspace').free})
   while p.poll() is None:
    observe(n)
    reports=out/'reports.jsonl'
    if reports.exists():
     for line in reports.read_text().splitlines():
      try:row=json.loads(line)
      except json.JSONDecodeError:continue
      key=(row['id'],row['when'])
      if row['outcome']=='failed' and key not in seen_failed:
       seen_failed.add(key);stop_launch.set();event({'type':'PYTEST_FAILURE_NO_RETRY','shard':n,'id':row['id'],'phase':row['when'],'raw_reports':str(reports)})
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:pass
  code=p.returncode;event({'type':'pytest_terminal','shard':n,'exit_code':code})
  if code:stop_launch.set()
  verify(n,'after');arch=archive(n)
  event({'type':'raw_archive_ready_for_push_before_retirement','shard':n,'archive_sha256':arch['archive_sha256']})
  row={'shard':int(n),'exit_code':code,'source_after_exit_code':0,'attempt_count':1,'result_path':str(out/'result.json')}
 except BaseException as e:
  stop_launch.set();event({'type':'COORDINATOR_FAILURE_NO_RETRY','shard':n,'exception':repr(e)})
  row={'shard':int(n),'coordinator_exception':repr(e),'attempt_count':int((out/'ATTEMPT_STARTED.json').exists())}
 finally:
  with lock:
   active.pop(n,None)
   if 'row' in locals():rows.append(row)
   save(R/f'shard{n}/worker-terminal.json',{'candidate':SHA,'results':sorted(rows,key=lambda x:x['shard']),'all_executed':len(rows)==6,'all_green':len(rows)==6 and all(x.get('exit_code')==0 for x in rows),'epoch':time.time()})
   event({'type':'shard_finished','shard':n,'active':dict(active),'free_bytes':shutil.disk_usage('/workspace').free})
 return row

import sys
assert len(sys.argv)==2
n=sys.argv[1];assert n in repos
row=one(n)
raise SystemExit(0 if row.get("exit_code")==0 else 1)

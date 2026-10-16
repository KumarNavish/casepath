import concurrent.futures,hashlib,io,json,os,shutil,subprocess,tarfile,threading,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
P=Path('/workspace/casepath-transport-gate-evidence-git-20261015/qa-receipts/b8616d4c-20261016')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9';MAN='83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382'
OLDMAN='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
MIN=3*1024**3;RESERVE=80*1024**2;PREPARE_BYTES=300*1024**2
lock=threading.RLock();prepare_lock=threading.Lock();archive_lock=threading.Lock();active={};rows=[]
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def event(x):
 with lock:
  x={'epoch':time.time(),**x}
  with (R/'scheduler-events.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
  print(json.dumps(x),flush=True)
def observe(n):
 with lock:
  row={'epoch':time.time(),'shard':n,'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'active':dict(active)}
  with (R/'resource-observations.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  if row['free_bytes']<MIN:event({'type':'resource_floor_breach','free_bytes':row['free_bytes'],'active':dict(active)})
def git(repo,*a):return subprocess.check_output(['git',*a],cwd=repo,text=True).strip()
def retire_prior_capsule():
 repo=Path('/workspace/casepath-release-ae0-shard6');capsule=repo/'.runtime/casepath-dev-v2/source-capsules'/OLDMAN
 before=shutil.disk_usage('/workspace').free;proof=json.loads((P/'shard6/source-after/capsule-verification.json').read_text());receipt=capsule/'CAPSULE_RECEIPT.json'
 assert proof['manifest_sha256']==OLDMAN and digest(receipt)==proof['capsule_receipt_file_sha256']
 manifest=json.loads((capsule/'casepath/source-manifest.json').read_text());assert digest(capsule/'casepath/source-manifest.json')==OLDMAN
 for row in manifest['files']:
  p=capsule/row['path'];assert not p.is_symlink() and p.stat().st_size==row['size_bytes'] and digest(p)==row['sha256']
 archive=R/'retirement-receipts/prior-shard6-capsule';archive.mkdir();shutil.copy2(receipt,archive/'CAPSULE_RECEIPT.json');shutil.copy2(P/'shard6/source-after/capsule-verification.json',archive/'capsule-verification.json')
 record={'path':str(capsule),'manifest_sha256':OLDMAN,'source_files_verified':1709,'prior_evidence_commit':'474c63348f40355c555886faaf5fb1d612aecc9a','prior_capsule_receipt_sha256':digest(receipt),'before_free_bytes':before,'preserved':'Current84 capsule, reused venv, Git, source, all fixtures/journals/raw receipts'}
 for root,dirs,files in os.walk(capsule):os.chmod(root,0o700)
 shutil.rmtree(capsule);record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/'retirement-receipts/prior-shard6-capsule-retirement.json',record);event({'type':'prior_proved_completed_capsule_retired','free_bytes':record['after_free_bytes']})
def verify(n,phase):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
 if (out/f'source-{phase}/capsule-verification.json').exists():return
 env=json.loads((out/'prepare.json').read_text())['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),f'shard{n}',phase];start=time.time()
 with (out/f'verify-{phase}.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 with lock:
  path=R/'source-proof-commands.json';records=json.loads(path.read_text());records.append({'name':f'shard{n}','phase':phase,'command':cmd,'cwd':str(repo),'env':env,'exit_code':p.returncode,'started_epoch':start,'finished_epoch':time.time()});save(path,records)
 assert p.returncode==0,(n,phase)
def snapshot(n):
 # The archive is local evidence only. Root independently reviews and pushes final receipts.
 with archive_lock:
  out=R/f'shard{n}';archive=R/'retirement-receipts'/f'shard{n}-raw.tar.gz';files={}
  for p in sorted(out.rglob('*')):
   if p.is_file() and not p.is_symlink() and not any(x in p.relative_to(out).parts for x in ['pycache','pytest-tmp','uv-cache','home','tmp','artifact-registry']):files[p.relative_to(out).as_posix()]=p.read_bytes()
  with tarfile.open(archive,'w:gz',compresslevel=3) as t:
   for rel,raw in files.items():
    info=tarfile.TarInfo(rel);info.size=len(raw);info.mode=0o600;t.addfile(info,io.BytesIO(raw))
  with tarfile.open(archive,'r:gz') as t:
   for rel,raw in files.items():assert t.extractfile(rel).read()==raw
  receipt={'shard':n,'archive':str(archive),'archive_sha256':digest(archive),'local_archive_verified':True,'files':{rel:hashlib.sha256(raw).hexdigest() for rel,raw in files.items()},'root_push_pending':True};save(R/'retirement-receipts'/f'shard{n}-raw-archive.json',receipt);return receipt
def retire(n,receipt):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}');before=json.loads((out/'source-before/capsule-verification.json').read_text());after=json.loads((out/'source-after/capsule-verification.json').read_text());assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256'];assert json.loads((out/'result.json').read_text())['exit_code']==0 and receipt['local_archive_verified']
 paths=[repo/'.runtime/casepath-dev-v2/source-capsules'/MAN,repo/'.runtime/casepath-dev-v2/venv'];row={'candidate':SHA,'shard':n,'paths':list(map(str,paths)),'before_free_bytes':shutil.disk_usage('/workspace').free,'pre_post_source_capsule_proofs_and_raw_receipts_locally_archived_and_verified':True,'canonical_source_verified_before':json.loads((out/'checkout.json').read_text())['head'],'archive_sha256':receipt['archive_sha256'],'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'raw_receipts_preserved':True,'root_push_pending':True}
 for p in paths:
  assert p.is_dir() and not p.is_symlink()
  for root,dirs,files in os.walk(p):os.chmod(root,0o700)
  shutil.rmtree(p)
 row['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'completed-shard{n}-runtime-retirement.json',row);event({'type':'runtime_retired','shard':n,'free_bytes':row['after_free_bytes']})
def one(n):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
 with lock:
  active[n]='starting';event({'type':'heavy_slot_reserved','shard':n,'active':dict(active),'free_bytes':shutil.disk_usage('/workspace').free});assert len(active)<=3
 if not (out/'prepare.json').exists():
  with prepare_lock:
   with lock:active[n]='prepare';event({'type':'prepare_start','shard':n,'active':dict(active),'free_bytes':shutil.disk_usage('/workspace').free})
   cmd=['/usr/bin/python3',str(R/'harness/prepare_clones.py'),f'shard{n}']
   with (out/'prepare-wrapper.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env={'HOME':'/workspace/kh0','TMPDIR':'/workspace/kt0','TMP':'/workspace/kt0','TEMP':'/workspace/kt0',**{k:v for k,v in os.environ.items() if k in ['PATH','HTTP_PROXY','HTTPS_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE']}},stdout=f,stderr=subprocess.STDOUT)
   assert p.returncode==0,('prepare',n)
   cache=out/'uv-cache';record={'path':str(cache),'normal_prepare_exit_code':0,'before_free_bytes':shutil.disk_usage('/workspace').free,'reason':'Completed owned reproducible uv cache; package signature/checksum/TLS guards unchanged'}
   shutil.rmtree(cache);record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'finished-prepare{n}-uv-cache-retirement.json',record)
 verify(n,'before');assert shutil.disk_usage('/workspace').free>=MIN
 env=json.loads((out/'prepare.json').read_text())['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',str(n)]
 with lock:active[n]='test';event({'type':'start','shard':n,'active':dict(active),'free_bytes':shutil.disk_usage('/workspace').free,'home':env['HOME'],'tmp':env['TMPDIR']})
 with (out/'wrapper.log').open('x') as f:
  p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);event({'type':'native_process_started','shard':n,'pid':p.pid,'command':cmd})
  while p.poll() is None:
   observe(n)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:pass
 code=p.returncode;verify(n,'after');receipt=snapshot(n)
 if code==0:retire(n,receipt)
 row={'shard':n,'exit_code':code,'source_after_exit_code':0,'result_path':str(out/'result.json'),'attempt_count':1}
 with lock:
  active.pop(n);rows.append(row);event({'type':'finish',**row,'active':dict(active),'free_bytes':shutil.disk_usage('/workspace').free});save(R/'all-shard-terminal.json',{'candidate':SHA,'results':sorted(rows,key=lambda x:x['shard']),'all_executed':len(rows)==6,'all_green':all(x['exit_code']==0 for x in rows),'epoch':time.time()})
 return row
assert json.loads((R/'EXECUTION_AUTHORIZATION.json').read_text())['signal']=='FINAL_GATE_AUTHORIZED'
with (R/'FULL_GATE_PROCESS_STARTED.json').open('x') as f:json.dump({'candidate':SHA,'pid':os.getpid(),'max_heavy':3,'floor_bytes':MIN,'epoch':time.time(),'no_retries':True},f,indent=2)
retire_prior_capsule();pending=[6,1,2,3,4,5];running={};failures=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 while pending or running:
  for future,n in list(running.items()):
   if future.done():
    try:
     result=future.result()
     if result['exit_code']:failures.append(result)
    except BaseException as e:
     failures.append({'shard':n,'exception':repr(e)});event({'type':'coordinator_failure','shard':n,'exception':repr(e)})
     raise
    del running[future]
  if pending and len(running)<3:
   n=pending[0];needed=0 if (R/f'shard{n}/prepare.json').exists() else PREPARE_BYTES
   # Each reservation includes complete normal prepare plus bounded active scratch headroom.
   with lock:free=shutil.disk_usage('/workspace').free;admit=free>=MIN+needed+RESERVE*(len(running)+1)
   if admit:pending.pop(0);running[pool.submit(one,n)]=n
  if running:time.sleep(2)
  elif pending:raise RuntimeError('Insufficient proved headroom for next normal prepare')
event({'type':'all_native_shards_terminal','results':sorted(rows,key=lambda x:x['shard']),'failures':failures})

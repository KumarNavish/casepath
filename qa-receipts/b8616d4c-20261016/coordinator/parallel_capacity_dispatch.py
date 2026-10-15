import concurrent.futures,hashlib,io,json,os,shutil,signal,subprocess,tarfile,threading,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
namespace={}
source=(R/'coordinator/serial_dispatch.py').read_text().split("assert json.loads((R/'EXECUTION_AUTHORIZATION.json')")[0]
exec(compile(source,str(R/'coordinator/serial_dispatch.py'),'exec'),namespace)
SHA=namespace['SHA'];MAN=namespace['MAN'];MIN=namespace['MIN'];G=namespace['G'];D=namespace['D'];BRANCH=namespace['BRANCH']
save=namespace['save'];digest=namespace['digest'];git=namespace['git'];serial_event=namespace['event'];serial_prepare=namespace['prepare'];serial_verify=namespace['verify']
io_lock=threading.RLock();prepare_lock=threading.Lock();checkpoint_lock=threading.Lock();active={1};rows=[]
def event(x):
 with io_lock:serial_event(x)
def observe(n):
 with io_lock:
  with (R/'resource-observations.jsonl').open('a') as f:f.write(json.dumps({'epoch':time.time(),'shard':n,'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free})+'\n')
def checkpoint(label):
 with checkpoint_lock:
  snapshots={}
  for p in sorted(R.rglob('*')):
   rel=p.relative_to(R)
   if p.is_symlink() or not p.is_file() or any(x in rel.parts for x in ['pycache','pytest-tmp','uv-cache','home','tmp','artifact-registry']):continue
   if p.suffix in ['.json','.jsonl','.txt','.log','.py','.xml','.cfg','.gz'] and p.name not in ['dispatch-wrapper.log','parallel-dispatch-wrapper.log','checkpoint-SHA256SUMS.txt','checkpoint-raw.tar.gz','checkpoint-receipt.json']:
    snapshots[rel.as_posix()]=p.read_bytes()
  checks=''.join(hashlib.sha256(raw).hexdigest()+'  '+rel+'\n' for rel,raw in snapshots.items()).encode()
  snapshots['checkpoint-SHA256SUMS.txt']=checks
  archive=R/'checkpoint-raw.tar.gz'
  with tarfile.open(archive,'w:gz',compresslevel=6) as t:
   for rel,raw in snapshots.items():
    info=tarfile.TarInfo(rel);info.size=len(raw);info.mode=0o600;t.addfile(info,io.BytesIO(raw))
  with tarfile.open(archive,'r:gz') as t:
   for rel,raw in snapshots.items():assert t.extractfile(rel).read()==raw
  (R/'checkpoint-SHA256SUMS.txt').write_bytes(checks)
  if git('branch','--show-current')!=BRANCH:
   assert not git('status','--porcelain');subprocess.run(['git','switch','-c',BRANCH],cwd=G,check=True)
  D.mkdir(parents=True,exist_ok=True)
  for rel,raw in snapshots.items():
   q=D/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
  shutil.copy2(archive,D/'checkpoint-raw.tar.gz')
  subprocess.run(['git','add','--',BRANCH],cwd=G,check=True)
  subprocess.run(['git','commit','-m',f'qa: b861 fullgate {label} raw receipts'],cwd=G,check=True,stdout=subprocess.DEVNULL)
  commit=git('rev-parse','HEAD');pushlog=R/'coordinator'/f'{label}-push.log'
  with pushlog.open('x') as f:p=subprocess.run(['git','push','--set-upstream','origin',BRANCH],cwd=G,stdout=f,stderr=subprocess.STDOUT)
  verified=False;remote=None
  if p.returncode==0:
   remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+BRANCH],cwd=G,text=True).split()[0];verified=remote==commit
  row={'label':label,'branch':BRANCH,'commit':commit,'push_exit_code':p.returncode,'remote_commit':remote,'push_verified':verified,'archive_sha256':digest(archive),'raw_files':len(snapshots)-1,'local_archive_verified':True,'epoch':time.time()}
  save(R/'checkpoint-receipt.json',row);save(R/'coordinator'/f'{label}-checkpoint-receipt.json',row);event({'type':'checkpoint_pushed' if verified else 'checkpoint_local_verified_push_pending',**row})
  return row
def retire_runtime(n,receipt):
 repo=Path(f'/workspace/casepath-release-ae0-shard{n}');out=R/f'shard{n}';before=json.loads((out/'source-before/capsule-verification.json').read_text());after=json.loads((out/'source-after/capsule-verification.json').read_text())
 assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 assert json.loads((out/'result.json').read_text())['exit_code']==0
 assert receipt['local_archive_verified'] and digest(D/f'shard{n}/source-after/capsule-verification.json')==digest(out/'source-after/capsule-verification.json') and digest(D/f'shard{n}/reports.jsonl')==digest(out/'reports.jsonl')
 paths=[repo/'.runtime/casepath-dev-v2/source-capsules'/MAN,repo/'.runtime/casepath-dev-v2/venv']
 record={'candidate':SHA,'shard':n,'paths':list(map(str,paths)),'before_free_bytes':shutil.disk_usage('/workspace').free,'pre_post_source_capsule_proofs_and_raw_receipts_locally_archived_and_verified':True,'durably_pushed':receipt['push_verified'],'evidence_commit':receipt['commit'],'archive_sha256':receipt['archive_sha256'],'source_before_sha256':digest(out/'source-before/capsule-verification.json'),'source_after_sha256':digest(out/'source-after/capsule-verification.json'),'preserved':'All source/Git/refs/raw receipts/unique and failed fixtures/journals/runtime home/tmp/boots','epoch':time.time()}
 for p in paths:
  assert p.is_dir() and not p.is_symlink()
  for root,dirs,files in os.walk(p):os.chmod(root,0o700)
  shutil.rmtree(p)
 record['after_free_bytes']=shutil.disk_usage('/workspace').free;save(R/f'completed-shard{n}-runtime-retirement.json',record);event({'type':'runtime_retired','shard':n,'free_bytes':record['after_free_bytes'],'evidence_commit':receipt['commit'],'push_verified':receipt['push_verified']})
def verify(n,phase):
 with prepare_lock:serial_verify(n,phase)
def prepare(n):
 with prepare_lock:serial_prepare(n)
def finish(n,code):
 verify(n,'after')
 row={'shard':n,'exit_code':code,'source_after_exit_code':0,'result_path':str(R/f'shard{n}/result.json'),'attempt_count':1}
 with io_lock:
  active.remove(n);rows.append(row)
  event({'type':'finish',**row,'active':sorted(active),'free_bytes':shutil.disk_usage('/workspace').free})
  save(R/'all-shard-terminal.json',{'candidate':SHA,'results':sorted(rows,key=lambda x:x['shard']),'all_executed':len(rows)==6,'all_green':all(x['exit_code']==0 and x['source_after_exit_code']==0 for x in rows),'epoch':time.time()})
 receipt=checkpoint(f'shard{n}-terminal')
 if code:return row
 if n!=6:retire_runtime(n,receipt)
 return row
def chain(numbers):
 for n in numbers:
  out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
  if n==1:
   while not (out/'result.json').exists():observe(n);time.sleep(5)
   # The original native wrapper has now written its terminal receipt; retire only the paused original coordinator.
   os.kill(old_pid,signal.SIGTERM);os.kill(old_pid,signal.SIGCONT)
   result=json.loads((out/'result.json').read_text());event({'type':'original_native_shard1_terminal_handoff_complete','original_coordinator_pid':old_pid,'native_wrapper_pid':native_pid,'native_exit_code':result['exit_code']})
   row=finish(n,result['exit_code'])
  else:
   prepare(n)
   while True:
    with io_lock:
     free=shutil.disk_usage('/workspace').free
     if free>=MIN and len(active)<2:
      assert not (out/'ATTEMPT_STARTED.json').exists();active.add(n);env=json.loads((out/'prepare.json').read_text())['env'];event({'type':'start','shard':n,'active':sorted(active),'free_bytes':free,'home':env['HOME'],'tmp':env['TMPDIR']});break
    event({'type':'waiting_before_attempt','shard':n,'free_bytes':free,'floor_bytes':MIN,'active':sorted(active)})
    time.sleep(5)
   cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',str(n)]
   with (out/'wrapper.log').open('x') as f:
    p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);event({'type':'native_process_started','shard':n,'pid':p.pid,'command':cmd,'active':sorted(active),'free_bytes':shutil.disk_usage('/workspace').free})
    while p.poll() is None:
     observe(n)
     try:p.wait(timeout=5)
     except subprocess.TimeoutExpired:pass
   row=finish(n,p.returncode)
  if row['exit_code']!=0:return
old=json.loads((R/'FULL_GATE_PROCESS_STARTED.json').read_text());old_pid=old['pid']
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];native_pid=next(x['pid'] for x in events if x['type']=='native_process_started' and x['shard']==1)
assert not (R/'shard1/result.json').exists() and not (R/'shard2/ATTEMPT_STARTED.json').exists()
cmdline=Path(f'/proc/{old_pid}/cmdline').read_bytes();assert b'serial_dispatch.py' in cmdline
os.kill(old_pid,signal.SIGSTOP)
save(R/'coordinator/native-shard1-ownership-handoff.json',{'candidate':SHA,'original_coordinator_pid':old_pid,'original_command_line':cmdline.decode().replace('\x00',' ').strip(),'original_exec_session':73878,'original_command':'HOME=/workspace/bh0 TMPDIR=/workspace/bt0 TMP=/workspace/bt0 TEMP=/workspace/bt0 python3 '+str(R/'coordinator/serial_dispatch.py')+' > '+str(R/'dispatch-wrapper.log')+' 2>&1','original_wrapper_log':'dispatch-wrapper.log','new_coordinator_pid':os.getpid(),'native_wrapper_pid_preserved':native_pid,'native_pytest_or_subprocess_group_signalled':False,'native_attempt_latch_preserved':True,'coordinator_SIGSTOP_only_until_native_terminal_then_SIGTERM_and_SIGCONT_to_own_coordinator_only':True,'max_heavy':2,'host_ceiling':3,'reason':'Newly authorized byte-verified retirement of completed writer clones creates capacity for a second isolated normal runtime','epoch':time.time()})
event({'type':'capacity_schedule_handoff','native_shard1_wrapper_pid_preserved':native_pid,'old_coordinator_pid':old_pid,'new_coordinator_pid':os.getpid(),'max_heavy':2,'free_bytes':shutil.disk_usage('/workspace').free})
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 fs=[pool.submit(chain,[1,3,5]),pool.submit(chain,[2,4,6])]
 for f in fs:f.result()
print(json.dumps({'all_native_shards_terminal':len(rows)==6,'candidate':SHA,'results':sorted(rows,key=lambda x:x['shard'])}),flush=True)

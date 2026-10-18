import collections,hashlib,json,os,pathlib,shutil,subprocess,time
R=pathlib.Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';MIN=3*1024**3
with (R/'SERIAL_DRIVER_STARTED.json').open('x') as f:json.dump({'pid':os.getpid(),'epoch':time.time(),'candidate':SHA,'max_heavy':1,'reason':'Only proven disk-safe admission with currently available3.94GB; six unchanged shards once each'},f)
transport=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS'];env={k:os.environ[k] for k in transport if k in os.environ};env.update(HOME='/workspace/rsh0',TMPDIR='/workspace/rst0',TMP='/workspace/rst0',TEMP='/workspace/rst0',PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8',PYTHONDONTWRITEBYTECODE='1')
def event(kind,**kw):
 x={'epoch':time.time(),'kind':kind,**kw}
 with (R/'serial-driver-events.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
 print(json.dumps(x),flush=True)
def call(script,args,log):
 with (R/'coordinator'/log).open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/'coordinator'/script),*args],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0,(script,args,p.returncode,str(R/'coordinator'/log))
def clean_processes(n):
 repo=json.loads((R/'clone-map.json').read_text())['repos'][n]
 for attempt in range(10):
  rows=[]
  for d in pathlib.Path('/proc').iterdir():
   if not d.name.isdigit():continue
   try:
    cwd=os.readlink(d/'cwd')
    if cwd==repo or cwd.startswith(repo+'/'):rows.append({'pid':int(d.name),'comm':(d/'comm').read_text().strip(),'cwd':cwd})
   except OSError:pass
  if not rows:break
  time.sleep(1)
 assert not rows,rows
 (R/f'shard{n}/owned-processes-before-runtime-retirement.json').write_text(json.dumps({'candidate':SHA,'repo':repo,'owned_processes':rows,'epoch':time.time(),'no_unrelated_process_signalled':True},indent=2)+'\n')
try:
 for i in range(1,7):
  n=str(i);out=R/f'shard{n}'
  if i==1:
   assert (out/'ATTEMPT_STARTED.json').exists()
   while not (out/'worker-terminal.json').exists():
    if (R/'STOP_ADMISSION_RESOURCE_VIOLATION.json').exists():raise RuntimeError('resource violation; freeze admission')
    time.sleep(3)
  else:
   assert not (out/'PREPARE_STARTED.json').exists() and not (out/'ATTEMPT_STARTED.json').exists()
   assert not (R/'STOP_ADMISSION_RESOURCE_VIOLATION.json').exists()
   assert shutil.disk_usage('/workspace').free>=MIN+500*1024**2
   event('prepare_admission',shard=n,free_bytes=shutil.disk_usage('/workspace').free)
   call('stage_one.py',[n],f'driver-stage{n}.log')
   event('prepared_before_first_test',shard=n,free_bytes=shutil.disk_usage('/workspace').free)
   call('scan_export.py',[],f'driver-prepare{n}-secret-scan.log')
   call('export_receipts.py',[f'Preserve exactaddc shard{n} normalprepare and pretest proofs before owned cache retirement'],f'driver-prepare{n}-export.log')
   call('retire_pushed_cache.py',[n],f'driver-cache{n}-retirement.log')
   assert shutil.disk_usage('/workspace').free>=MIN
   event('test_admission',shard=n,free_bytes=shutil.disk_usage('/workspace').free)
   call('one_shard.py',[n],f'driver-shard{n}.log')
  terminal=json.loads((out/'worker-terminal.json').read_text());result=json.loads((out/'result.json').read_text())
  assert result['exit_code']==0 and terminal['results'][0]['exit_code']==0
  clean_processes(n)
  rs=[json.loads(x) for x in (out/'reports.jsonl').read_text().splitlines()];outcomes=collections.Counter(x['outcome'] for x in rs if x['when']=='call');skips=sum(x['outcome']=='skipped' for x in rs)
  event('terminal_raw_ready',shard=n,exit_code=0,call_outcomes=dict(outcomes),skips=skips,duration_seconds=result['duration_seconds'])
  call('scan_export.py',[],f'driver-terminal{n}-secret-scan.log')
  call('export_receipts.py',[f'Preserve exactaddc shard{n} terminal raw collection phases JUnit source and full-runtime proofs'],f'driver-terminal{n}-export.log')
  call('retire_pushed_runtime.py',[n],f'driver-runtime{n}-retirement.log')
  event('terminal_durably_pushed_and_owned_runtime_retired',shard=n,free_bytes=shutil.disk_usage('/workspace').free)
 event('all_six_terminal_and_pushed',candidate=SHA)
except BaseException as e:
 event('DRIVER_STOP_NO_RETRY',exception=repr(e));raise

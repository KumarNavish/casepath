import concurrent.futures,json,os,shutil,signal,subprocess,threading,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
# Reuse the reviewed first-only runner, source proof, snapshot archive and push-error handling.
source=(R/'coordinator/parallel_capacity_dispatch.py').read_text().split("old=json.loads((R/'FULL_GATE_PROCESS_STARTED.json')")[0]
exec(compile(source,str(R/'coordinator/parallel_capacity_dispatch.py'),'exec'),globals())
old_controller=json.loads((R/'coordinator/native-shard1-ownership-handoff.json').read_text())['new_coordinator_pid']
while True:
 events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()]
 completed={x['shard'] for x in events if x['type']=='finish'}
 running={n for n in range(1,7) if (R/f'shard{n}/ATTEMPT_STARTED.json').exists() and n not in completed}
 stable=len(running)<=2 and all((R/f'completed-shard{n}-runtime-retirement.json').exists() for n in completed) and not (G/'.git/index.lock').exists()
 if stable:
  prior_proc=Path(f'/proc/{old_controller}/cmdline')
  cmdline=prior_proc.read_bytes() if prior_proc.exists() else b'Previously exited parallel_capacity_dispatch.py (packaging author metadata failure preserved)'
  assert b'parallel_capacity_dispatch.py' in cmdline
  if prior_proc.exists():os.kill(old_controller,signal.SIGSTOP)
  latest=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];finished={x['shard'] for x in latest if x['type']=='finish'}
  if finished==completed:break
  if prior_proc.exists():os.kill(old_controller,signal.SIGCONT)
 time.sleep(2)
initial_adopted=sorted(running);active=set(initial_adopted);rows=[x for x in json.loads((R/'all-shard-terminal.json').read_text())['results'] if x['shard'] in completed]
save(R/'coordinator/two-to-three-native-ownership-handoff.json',{'candidate':SHA,'previous_coordinator_pid':old_controller,'previous_command_line':cmdline.decode().replace('\x00',' ').strip(),'previous_exec_session':76209,'previous_wrapper_log':'parallel-dispatch-wrapper.log','previous_exact_command':'HOME=/workspace/bh0 TMPDIR=/workspace/bt0 TMP=/workspace/bt0 TEMP=/workspace/bt0 python3 '+str(R/'coordinator/parallel_capacity_dispatch.py')+' > '+str(R/'parallel-dispatch-wrapper.log')+' 2>&1','new_coordinator_pid':os.getpid(),'adopted_running_native_shards':initial_adopted,'completed_first_only_shards':sorted(completed),'no_native_wrapper_pytest_or_subprocess_group_signalled':True,'existing_native_attempt_latches_unchanged':True,'previous_own_coordinator_SIGSTOP_only_until_all_adopted_native_wrappers_terminal_then_SIGTERM_and_SIGCONT':True,'max_heavy':3,'minimum_prelaunch_free_bytes':MIN,'epoch':time.time()})
event({'type':'capacity_schedule_handoff_to_three','old_coordinator_pid':old_controller,'new_coordinator_pid':os.getpid(),'adopted_native_shards':initial_adopted,'max_heavy':3,'free_bytes':shutil.disk_usage('/workspace').free})
controller_terminated=False
def terminate_previous_if_safe():
 global controller_terminated
 with io_lock:
  if not controller_terminated and all((R/f'shard{n}/result.json').exists() for n in initial_adopted):
   try:os.kill(old_controller,signal.SIGTERM);os.kill(old_controller,signal.SIGCONT)
   except ProcessLookupError:pass
   controller_terminated=True
   event({'type':'previous_two_worker_coordinator_terminal_after_adopted_native_wrappers','old_coordinator_pid':old_controller,'native_wrappers_all_terminal':initial_adopted,'native_pytest_or_subprocess_group_signalled':False})
def run_one(n):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
 if n in initial_adopted:
  while not (out/'result.json').exists():observe(n);time.sleep(5)
  terminate_previous_if_safe();result=json.loads((out/'result.json').read_text());return finish(n,result['exit_code'])
 prepare(n)
 while True:
  with io_lock:
   free=shutil.disk_usage('/workspace').free
   if free>=MIN and len(active)<3:
    assert not (out/'ATTEMPT_STARTED.json').exists();active.add(n);env=json.loads((out/'prepare.json').read_text())['env'];event({'type':'start','shard':n,'active':sorted(active),'free_bytes':free,'home':env['HOME'],'tmp':env['TMPDIR']});break
  event({'type':'waiting_before_attempt','shard':n,'free_bytes':free,'floor_bytes':MIN,'active':sorted(active)});time.sleep(5)
 cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'run',str(n)]
 with (out/'wrapper.log').open('x') as f:
  p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);event({'type':'native_process_started','shard':n,'pid':p.pid,'command':cmd,'active':sorted(active),'free_bytes':shutil.disk_usage('/workspace').free})
  while p.poll() is None:
   observe(n)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:pass
 return finish(n,p.returncode)
pending=[n for n in range(1,7) if n not in completed and n not in initial_adopted]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 futures=[pool.submit(run_one,n) for n in initial_adopted+pending]
 for f in concurrent.futures.as_completed(futures):
  row=f.result()
  if row['exit_code']!=0:
   # No retries and no new queued tests after a failed shard; already running native attempts finish normally.
   for other in futures:other.cancel()
terminate_previous_if_safe()
print(json.dumps({'all_native_shards_terminal':len(rows)==6,'candidate':SHA,'results':sorted(rows,key=lambda x:x['shard'])}),flush=True)

import json,os,pathlib,shutil,time
R=pathlib.Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018')
with (R/'PROCESS_OBSERVER_STARTED.json').open('x') as f:json.dump({'pid':os.getpid(),'epoch':time.time(),'sample_interval_seconds':3,'scope':'Own gate process tree; safe environment names and path classification only; no credential values'},f)
selectors=[str(R/'coordinator/one_shard.py'),str(R/'coordinator/stage_one.py'),str(R/'harness/run_shard.py')]
path_keys=['HOME','TMPDIR','TMP','TEMP','CASEPATH_DB_PATH','CASEPATH_ARTIFACT_REGISTRY_PATH','CASEPATH_QA_ARTIFACTS']
while not (R/'STOP_PROCESS_OBSERVER').exists():
 procs={};roots=[]
 for d in pathlib.Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   args=[x.decode(errors='replace') for x in (d/'cmdline').read_bytes().split(b'\0') if x]
   status=(d/'status').read_text().splitlines();ppid=int(next(x.split()[1] for x in status if x.startswith('PPid:')))
   procs[int(d.name)]={'p':d,'args':args,'ppid':ppid}
   if any(s in args for s in selectors):roots.append(int(d.name))
  except (OSError,StopIteration,ValueError):pass
 owned=set(roots)
 changed=True
 while changed:
  new={pid for pid,p in procs.items() if p['ppid'] in owned}-owned;changed=bool(new);owned.update(new)
 rows=[]
 for pid in sorted(owned):
  p=procs[pid]['p']
  try:
   cwd=os.readlink(p/'cwd');raw=(p/'environ').read_bytes().split(b'\0');env={kv.split(b'=',1)[0].decode():kv.split(b'=',1)[1].decode(errors='replace') for kv in raw if b'=' in kv}
   paths={k:('workspace' if env[k].startswith('/workspace/') else 'tmp' if env[k].startswith('/tmp/') else 'other') for k in path_keys if k in env}
   rows.append({'pid':pid,'ppid':procs[pid]['ppid'],'comm':(p/'comm').read_text().strip(),'cwd_class':'workspace' if cwd.startswith('/workspace/') else 'tmp' if cwd.startswith('/tmp/') else 'other','selected_env_names_present':sorted(paths),'selected_path_classes':paths})
  except OSError:pass
 row={'epoch':time.time(),'workspace_free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'own_process_samples':rows,'sample_only_not_exhaustive':True}
 with (R/'own-process-environment-observations.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 time.sleep(3)

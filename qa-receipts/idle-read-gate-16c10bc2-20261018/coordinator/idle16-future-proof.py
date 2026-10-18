from pathlib import Path
import hashlib,json,os,subprocess,time,shutil
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');E=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');T=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');roots=[E/'shard5/pytest-tmp',E/'shard6/pytest-tmp',T/'shard4/pytest-tmp',T/'shard5/pytest-tmp',T/'shard6/pytest-tmp'];durable=[]
for old,c in [(E,'9d7e4f0bfd2e1dca18e11ba79282ddb0272a5f28'),(T,'5366ea3eb1125230661dd2f31f1e3156447997e8')]:
 x=subprocess.run(['/usr/bin/python3',str(old/'coordinator/verify_pushed_bundle.py'),c],capture_output=True,text=True);assert x.returncode==0;durable.append(json.loads(x.stdout))
rows=[]
for p in roots:
 assert p.is_dir() and not p.is_symlink();out=p.parent;result=json.loads((out/'result.json').read_text());assert result['exit_code']==0;reports=[json.loads(x) for x in (out/'reports.jsonl').read_text().splitlines()];assert all(x['outcome']=='passed' for x in reports)
 entries=[]
 for q in sorted(p.rglob('*')):
  if q.is_symlink():entries.append({'path':q.relative_to(p).as_posix(),'symlink':os.readlink(q)})
  elif q.is_file():entries.append({'path':q.relative_to(p).as_posix(),'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'size':q.stat().st_size})
 rows.append({'path':str(p),'passed_result_sha256':hashlib.sha256((out/'result.json').read_bytes()).hexdigest(),'passed_reports_sha256':hashlib.sha256((out/'reports.jsonl').read_bytes()).hexdigest(),'inventory':entries,'allocated_bytes':sum(q.lstat().st_blocks*512 for q in p.rglob('*'))})
owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a==str(p) or a.startswith(str(p)+'/') for a in args for p in roots):owned.append({'pid':q.name})
 except OSError:pass
assert not owned
p={'candidate':'16c10bc21c1b2b3b6602cb028028adf28e20823b','authorization':'Root explicitly authorizes only these five exact prior passed synthetic-fixture pytest-tmp paths after immutable proof/remote verification/no-activejob checks; all raw/source/Git and DBs outside roots preserved','durable_prior_full_gate_verification':durable,'paths':rows,'owned_processes':owned,'no_search_beyond_explicit_paths':True,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()};(R/'future-admission-scratch-proof.json').write_text(json.dumps(p,indent=2)+'\n');shutil.copy2('/workspace/idle16-future-proof.py',R/'coordinator/idle16-future-proof.py');print(json.dumps({'proved_exact_paths':len(rows),'allocated_bytes':sum(x['allocated_bytes'] for x in rows),'old_terminal_all_phases_passed':True}))

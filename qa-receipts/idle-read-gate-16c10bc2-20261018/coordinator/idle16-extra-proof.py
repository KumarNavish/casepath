from pathlib import Path
import os,json,subprocess,hashlib,shutil,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');P=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');E=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');repos=json.loads((R/'clone-map.json').read_text())['repos'];roots=[]
for n,repo in repos.items():roots += [(P/f'shard{n}/pytest-tmp','addc_passed_fixture_scratch'),(Path(repo)/'casepath-public','addc_ignored_generated_static')]
roots.append((E/'shard4/pytest-tmp','conditional_extra8f_passed_fixture_scratch'))
q=subprocess.run(['/usr/bin/python3',str(E/'coordinator/verify_pushed_bundle.py'),'9d7e4f0bfd2e1dca18e11ba79282ddb0272a5f28'],capture_output=True,text=True);assert q.returncode==0;qproof=json.loads(q.stdout)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for p,kind in roots:
 if not p.exists():records.append({'path':str(p),'kind':kind,'exists':False});continue
 assert p.is_dir() and not p.is_symlink();rows=[]
 for a in sorted(p.rglob('*')):
  if a.is_symlink():rows.append({'path':a.relative_to(p).as_posix(),'symlink':os.readlink(a)})
  elif a.is_file():rows.append({'path':a.relative_to(p).as_posix(),'bytes':a.stat().st_size,'sha256':sha(a)})
 if kind=='addc_ignored_generated_static':
  repo=p.parent;assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='16c10bc21c1b2b3b6602cb028028adf28e20823b';assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip();assert subprocess.run(['git','-C',str(repo),'check-ignore','-q','casepath-public']).returncode==0
 records.append({'path':str(p),'kind':kind,'exists':True,'allocated_bytes':sum(a.lstat().st_blocks*512 for a in p.rglob('*')),'content_inventory':rows})
owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a==str(p) or a.startswith(str(p)+'/') for a in args for p,k in roots):owned.append({'pid':q.name})
 except OSError:pass
assert not owned
for n in range(1,7):assert json.loads((P/f'shard{n}/result.json').read_text())['exit_code']==0
assert json.loads((E/'shard4/result.json').read_text())['exit_code']==0
proof={'candidate':'16c10bc21c1b2b3b6602cb028028adf28e20823b','authorization':'Parent explicitly approves completed addc pytest-tmp directories +six ignored generated casepath-public directories, and ONLY IF still below unchanged500MiB prepare reservation then one exact completed8f shard4/pytest-tmp; no further search/cleanup','addc_remote_commit':'6953f0eb9c325fdef906d01321a9d198432fd0c4','addc397_checksums_verified':True,'addc_SHA256SUMS_sha256':sha(P/'SHA256SUMS'),'extra8f_pushed_verification':qproof,'all_source_and_raw_receipts_preserved':True,'owned_processes':owned,'paths':records,'free_before_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()};(R/'additional-derived-retirement-proof.json').write_text(json.dumps(proof,indent=2)+'\n');shutil.copy2('/workspace/idle16-extra-proof.py',R/'coordinator/idle16-extra-proof.py');print(json.dumps({'additional_proof_ready':True,'allocated_primary_bytes':sum(x.get('allocated_bytes',0) for x in records if not x['kind'].startswith('conditional')),'conditional_extra8f_bytes':records[-1].get('allocated_bytes',0)}))

from pathlib import Path
import json,hashlib,subprocess,shutil,os,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');B='qa-receipts/idle-read-gate-16c10bc2-20261018';C='7d81520bf51369be5a7794aa49010af9305ba6da'
def git(*a):return subprocess.check_output(['git','-C',str(G),*a]).decode().strip()
assert git('ls-remote','origin','refs/heads/'+B).split()[0]==C
subprocess.run(['git','-C',str(G),'fetch','origin','refs/heads/'+B],check=True,capture_output=True);raw=subprocess.check_output(['git','-C',str(G),'show','FETCH_HEAD:'+B+'/approved-retirement-proof.json']);assert raw==(R/'approved-retirement-proof.json').read_bytes();d=json.loads(raw)
roots=[Path(x['path']) for x in d['approved_derived_paths']];owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a.startswith(str(p)+'/') or a==str(p) for a in args for p in roots):owned.append({'pid':q.name})
 except OSError:pass
assert not owned
w=d['source_branch'];assert subprocess.check_output(['git','-C',w['path'],'rev-parse',w['branch']],text=True).strip()==w['head']
before=shutil.disk_usage('/workspace').free
for p in roots:
 assert p.is_dir() and not p.is_symlink()
 for directory,dirs,files in os.walk(p):os.chmod(directory,0o700)
 shutil.rmtree(p)
r={'proof_commit':C,'remote_actual_proof_bytes_match':True,'remote_proof_sha256':hashlib.sha256(raw).hexdigest(),'retired_only':[str(p) for p in roots],'owned_targeted_processes_before_delete':owned,'source_evidence_review_export_commits_and_prior_full_gates_preserved':True,'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()};(R/'approved-retirement-result.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copy2('/workspace/idle16-retire.py',R/'coordinator/idle16-retire.py');print(json.dumps(r));assert r['after_free_bytes']>=3*1024**3+500*1024**2

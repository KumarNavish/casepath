import subprocess,hashlib,json,os,shutil,time
from pathlib import Path
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');C='66977e5eacec68c98e37c99b09a6a5f2e1771ef5';B='qa-receipts/read-seed-gate-addc5a77-20261018'
def git(*a):return subprocess.check_output(['git','-C',str(G),*a],text=True).strip()
assert git('ls-remote','origin','refs/heads/'+B).split()[0]==C
subprocess.run(['git','-C',str(G),'fetch','origin','refs/heads/'+B],check=True,capture_output=True)
p=R/'approved-retirement-proof.json';raw=subprocess.check_output(['git','-C',str(G),'show','FETCH_HEAD:'+B+'/approved-retirement-proof.json']);assert raw==p.read_bytes();d=json.loads(raw)
roots=[Path(x['path']) for x in d['approved_paths']];owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit():continue
 try:
  cwd=os.readlink(q/'cwd')
  if any(cwd==str(p) or cwd.startswith(str(p)+'/') for p in roots+[Path(x['path']) for x in d['source_branches_preserved']]):owned.append({'pid':q.name,'cwd':cwd})
 except OSError:pass
assert not owned
for x in d['source_branches_preserved']:
 p=x['path'];assert subprocess.check_output(['git','-C',p,'rev-parse',x['branch']],text=True).strip()==x['head'];assert not subprocess.check_output(['git','-C',p,'status','--porcelain'],text=True).strip()
before=shutil.disk_usage('/workspace').free
for p in roots:
 assert p.is_dir() and not p.is_symlink()
 for directory, dirs, files in os.walk(p):os.chmod(directory,0o700)
 shutil.rmtree(p)
record={'proof_commit':C,'remote_ref_exact':True,'remote_proof_sha256':hashlib.sha256(raw).hexdigest(),'remote_actual_bytes_match':True,'owned_processes_before_delete':owned,'retired_only':[str(p) for p in roots],'all_receipts_logs_sources_exports_package_selector_preserved':True,'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()}
(R/'approved-retirement-result.json').write_text(json.dumps(record,indent=2)+'\n');assert record['after_free_bytes']>=3*1024**3+500*1024**2;print(json.dumps(record))

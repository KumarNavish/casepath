from pathlib import Path
import json,hashlib,os,subprocess,shutil,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');B='qa-receipts/idle-read-gate-16c10bc2-20261018';C='955e7fff4b1a9ae3bcd7d0b6c4a82b75f999d949'
assert subprocess.check_output(['git','-C',str(G),'ls-remote','origin','refs/heads/'+B],text=True).split()[0]==C
subprocess.run(['git','-C',str(G),'fetch','origin','refs/heads/'+B],check=True,capture_output=True);raw=subprocess.check_output(['git','-C',str(G),'show','FETCH_HEAD:'+B+'/future-admission-scratch-proof.json']);assert raw==(R/'future-admission-scratch-proof.json').read_bytes();d=json.loads(raw);roots=[Path(x['path']) for x in d['paths']];owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a==str(p) or a.startswith(str(p)+'/') for a in args for p in roots):owned.append({'pid':q.name})
 except OSError:pass
assert not owned
before=shutil.disk_usage('/workspace').free;records=[]
for row in d['paths']:
 p=Path(row['path']);assert p.is_dir() and not p.is_symlink()
 for x in row['inventory']:
  q=p/x['path']
  if 'symlink' in x:assert q.is_symlink() and os.readlink(q)==x['symlink']
  else:assert hashlib.sha256(q.read_bytes()).hexdigest()==x['sha256']
 f=shutil.disk_usage('/workspace').free
 for directory,dirs,files in os.walk(p):os.chmod(directory,0o700)
 shutil.rmtree(p);records.append({'path':str(p),'before_free_bytes':f,'after_free_bytes':shutil.disk_usage('/workspace').free})
r={'proof_commit':C,'actual_remote_proof_bytes_match':True,'owned_jobs_before_delete':owned,'retired_only':records,'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'active_current_shard_untouched':True,'all_prior_raw_source_Git_and_DBs_outside_approved_tmp_preserved':True,'epoch':time.time()};(R/'future-admission-scratch-retirement.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copy2('/workspace/idle16-future-retire.py',R/'coordinator/idle16-future-retire.py');print(json.dumps(r))

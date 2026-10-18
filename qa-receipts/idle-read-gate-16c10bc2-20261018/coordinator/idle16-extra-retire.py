from pathlib import Path
import subprocess,hashlib,json,shutil,os,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');B='qa-receipts/idle-read-gate-16c10bc2-20261018';C='faca3517e8a14a445b057578facc1b04c76ee9fc';NEED=3*1024**3+500*1024**2
assert subprocess.check_output(['git','-C',str(G),'ls-remote','origin','refs/heads/'+B],text=True).split()[0]==C
subprocess.run(['git','-C',str(G),'fetch','origin','refs/heads/'+B],check=True,capture_output=True);raw=subprocess.check_output(['git','-C',str(G),'show','FETCH_HEAD:'+B+'/additional-derived-retirement-proof.json']);assert raw==(R/'additional-derived-retirement-proof.json').read_bytes();d=json.loads(raw);roots=[Path(x['path']) for x in d['paths'] if x['exists']];owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a==str(p) or a.startswith(str(p)+'/') for a in args for p in roots):owned.append({'pid':q.name})
 except OSError:pass
assert not owned
records=[];before=shutil.disk_usage('/workspace').free
for row in d['paths']:
 if not row['exists']:continue
 p=Path(row['path'])
 if row['kind'].startswith('conditional') and shutil.disk_usage('/workspace').free>=NEED:continue
 assert p.is_dir() and not p.is_symlink()
 for x in row['content_inventory']:
  q=p/x['path']
  if 'symlink' in x:assert q.is_symlink() and os.readlink(q)==x['symlink']
  else:assert hashlib.sha256(q.read_bytes()).hexdigest()==x['sha256']
 f=shutil.disk_usage('/workspace').free
 for directory,dirs,files in os.walk(p):os.chmod(directory,0o700)
 shutil.rmtree(p);records.append({'path':str(p),'kind':row['kind'],'before_free_bytes':f,'after_free_bytes':shutil.disk_usage('/workspace').free})
r={'proof_commit':C,'actual_remote_proof_bytes_matched':True,'no_owned_jobs_before_delete':owned,'retired_only':records,'before_free_bytes':before,'after_free_bytes':shutil.disk_usage('/workspace').free,'unchanged_admission_bytes':NEED,'prepare_guard_satisfied':shutil.disk_usage('/workspace').free>=NEED,'all_source_raw_receipts_phase_JUnit_commands_envs_and_DBs_outside_pytest_tmp_preserved':True,'epoch':time.time()};(R/'additional-derived-retirement-result.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copy2('/workspace/idle16-extra-retire.py',R/'coordinator/idle16-extra-retire.py');print(json.dumps(r));assert r['prepare_guard_satisfied']

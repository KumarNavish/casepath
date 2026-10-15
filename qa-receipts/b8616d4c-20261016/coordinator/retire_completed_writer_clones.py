import hashlib,json,os,shutil,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
expected={'casepath-startup-itinerary-js-20261016':'c57faa59f7533b1317166a8cb484a40e2b76b75e','casepath-stage-edge-css-20261016':'b8f9a694dbf4016a9da269a88fd263ddce6993ac'}
url=subprocess.check_output(['git','remote','get-url','origin'],cwd=G,text=True).strip()
archive_root=R.parent/(R.name+'-preserved-writer-clones');archive_root.mkdir()
records=[]
for name,sha in expected.items():
 p=Path('/workspace')/name
 def git(*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
 assert p.resolve()==p and (p/'.git').is_dir() and git('rev-parse','--verify','HEAD^{commit}')==sha and not git('status','--porcelain','--untracked-files=all')
 branch=git('branch','--show-current');remote=subprocess.check_output(['git','ls-remote',url,'refs/heads/'+branch],cwd=G,text=True).split()[0];assert remote==sha
 untracked=git('ls-files','--others','--exclude-standard').splitlines();ignored=git('ls-files','--others','--ignored','--exclude-standard').splitlines();assert not untracked
 assert all('/__pycache__/' in x and x.endswith('.pyc') for x in ignored),ignored
 external=[];alternates=p/'.git/objects/info/alternates'
 if alternates.exists():
  for row in alternates.read_text().splitlines():
   other=(p/'.git/objects'/row).resolve();assert other.is_dir() and str(other).startswith('/workspace/') and not any(str(other).startswith('/workspace/'+n+'/') for n in expected)
   external.append({'object_store':str(other),'preserved_external_shared_Git_objects':True})
 files=[]
 for f in sorted(p.rglob('*')):
  if f.is_file() and not f.is_symlink():files.append({'path':f.relative_to(p).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size})
 archive=archive_root/(name+'.tar.gz')
 with tarfile.open(archive,'w:gz',compresslevel=3) as t:t.add(p,arcname=name)
 with tarfile.open(archive,'r:gz') as t:
  for row in files:assert hashlib.sha256(t.extractfile(name+'/'+row['path']).read()).hexdigest()==row['sha256']
 record={'path':str(p),'head':sha,'branch':branch,'remote_exact_verified':remote,'status':'','untracked':untracked,'ignored_only_reproducible_python_caches':ignored,'all_refs_preserved':git('for-each-ref','--format=%(refname) %(objectname)').splitlines(),'recovery_archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_size_bytes':archive.stat().st_size,'all_regular_files_byte_verified_in_archive':len(files),'external_Git_dependencies_preserved':external,'raw_task_receipts_durable_commit':'45ee77add89ff73da991dd320ccfcc6d52175c55','source_and_Git_metadata_in_archive':True,'file_roster':files,'before_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()}
 (R/'retirement-receipts'/(name+'-recovery-proof.json')).write_text(json.dumps(record,indent=2)+'\n')
 shutil.rmtree(p)
 record.pop('file_roster');record['after_free_bytes']=shutil.disk_usage('/workspace').free;records.append(record)
(R/'completed-writer-clone-retirement.json').write_text(json.dumps({'user_authorized_completed_clean_pushed_writer_clones_only':True,'records':records,'six_AE0_normal_validation_clones_preserved':True,'focused_evidence_Git_clone_preserved':True},indent=2)+'\n')
print(json.dumps({'retired_clones':list(expected),'free_bytes':shutil.disk_usage('/workspace').free,'recovery_archives_total_bytes':sum(x['archive_size_bytes'] for x in records)}),flush=True)

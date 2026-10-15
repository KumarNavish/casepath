import hashlib,json,os,shutil,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');p=Path('/workspace/casepath-map-first-stage-20261015')
def git(*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
assert p.resolve()==p and (p/'.git').is_dir() and not git('status','--porcelain','--untracked-files=all')
assert not git('ls-files','--others','--exclude-standard') and not git('ls-files','--others','--ignored','--exclude-standard')
url=subprocess.check_output(['git','remote','get-url','origin'],cwd=G,text=True).strip()
durable=[]
for row in git('for-each-ref','--format=%(refname) %(objectname)','refs/heads').splitlines():
 ref,sha=row.split();remote=subprocess.check_output(['git','ls-remote',url,ref],cwd=G,text=True).split()[0]
 subprocess.run(['git','fetch',url,ref],cwd=p,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 assert git('rev-parse','--verify','FETCH_HEAD^{commit}')==remote
 assert subprocess.run(['git','merge-base','--is-ancestor',sha,remote],cwd=p).returncode==0
 durable.append({'local_ref':ref,'local_sha':sha,'remote_branch_tip':remote,'local_commit_reachable_from_canonical_remote_branch':True})
raw=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=p);rows=[]
for entry in raw.rstrip(b'\0').split(b'\0'):
 meta,path=entry.split(b'\t',1);mode,sha,stage=meta.decode().split();path=path.decode();assert stage=='0' and '\n' not in path and not (p/path).is_symlink();rows.append({'path':path,'blob_sha1':sha,'mode':mode})
actual=subprocess.check_output(['git','hash-object','--stdin-paths'],input=''.join(x['path']+'\n' for x in rows),cwd=p,text=True).splitlines();assert actual==[x['blob_sha1'] for x in rows]
archive_root=R.parent/(R.name+'-preserved-writer-clones');archive=archive_root/'completed-map-first-stage-Git-metadata.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=3) as t:t.add(p/'.git',arcname=p.name+'/.git')
with tarfile.open(archive,'r:gz') as t:
 for f in (p/'.git').rglob('*'):
  if f.is_file() and not f.is_symlink():assert t.extractfile(p.name+'/.git/'+f.relative_to(p/'.git').as_posix()).read()==f.read_bytes()
bindings=[]
alternate=p/'.git/objects/info/alternates'
if alternate.exists():
 for line in alternate.read_text().splitlines():
  other=(p/'.git/objects'/line).resolve();assert other.is_dir() and not str(other).startswith(str(p)+'/');bindings.append(str(other))
record={'path':str(p),'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'status':'','ignored_or_untracked_files':[],'all_tracked_source_file_Git_blobs_verified':len(rows),'local_refs_durably_reachable_from_canonical_remote_branches':durable,'source_file_blob_roster':rows,'Git_metadata_recovery_archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_size_bytes':archive.stat().st_size,'shared_external_Git_object_stores_preserved':bindings,'authoritative_raw_evidence_outside_clone_preserved':True,'user_authorization':'Root relayed explicit permission to retire clean pushed completed CasePath gate task checkouts; full source archive optional when commits demonstrably durable remotely','before_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()}
(R/'retirement-receipts/completed-map-stage-before-retirement.json').write_text(json.dumps(record,indent=2)+'\n')
shutil.rmtree(p);record.pop('source_file_blob_roster');record['after_free_bytes']=shutil.disk_usage('/workspace').free
(R/'completed-map-stage-clone-retirement.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)

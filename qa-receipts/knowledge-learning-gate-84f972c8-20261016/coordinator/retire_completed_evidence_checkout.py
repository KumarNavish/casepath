import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
repo=Path('/workspace/casepath-startup-itinerary-evidence-git-20261016')
proofrepo=Path('/workspace/casepath-release-ae0-shard1')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9'
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
assert not git(repo,'status','--porcelain') and (repo/'.git').is_dir()
head=git(repo,'rev-parse','HEAD');assert head=='45ee77add89ff73da991dd320ccfcc6d52175c55'
branch=git(repo,'branch','--show-current');remote=git(proofrepo,'ls-remote','https://github.com/KumarNavish/casepath.git','refs/heads/'+branch).split()[0];assert remote==head
assert not git(repo,'ls-files','--others','--exclude-standard')
rows=[]
for line in git(repo,'ls-files','--stage').splitlines():
 metadata,name=line.split('\t',1);mode,oid,stage=metadata.split();assert stage=='0' and mode in ['100644','100755']
 if name.startswith('qa-receipts/'):continue
 p=repo/name;raw=p.read_bytes();blob=subprocess.check_output(['git','cat-file','blob',oid],cwd=repo);assert raw==blob and not p.is_symlink()
 rows.append({'path':name,'git_blob':oid,'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)})
record={'action':'retire_only_reproducible_tracked_product_source_of_completed_evidence_checkout','path':str(repo),'head':head,'canonical_branch':branch,'canonical_remote_head_verified':remote,'all_refs_preserved':git(repo,'for-each-ref','--format=%(refname) %(objectname)').splitlines(),'normal_Git_directory_preserved':True,'all_tracked_qa_receipts_and_ignored_untracked_files_runtime_fixtures_journals_and_receipts_preserved':True,'tracked_files_verified_byte_equal_Git':rows,'before_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()}
(R/'retirement-receipts/completed-evidence-checkout-before.json').write_text(json.dumps(record,indent=2)+'\n')
for row in rows:(repo/row['path']).unlink()
record['after_free_bytes']=shutil.disk_usage('/workspace').free
(R/'retirement-receipts/completed-evidence-checkout.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'files':len(rows),'reclaimed_bytes':record['after_free_bytes']-record['before_free_bytes'],'free_bytes':record['after_free_bytes']}),flush=True)

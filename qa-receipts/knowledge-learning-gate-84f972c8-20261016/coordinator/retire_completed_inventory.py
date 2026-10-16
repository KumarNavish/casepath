import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
repo=Path('/workspace/casepath-release-ae0-inventory')
proofrepo=Path('/workspace/casepath-release-ae0-shard1')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9'
def git(p,*a):return subprocess.check_output(['git',*a],cwd=p,text=True).strip()
assert not git(repo,'status','--porcelain') and (repo/'.git').is_dir()
head=git(repo,'rev-parse','HEAD');assert head=='28247cbc87785b366fa542bb0aa0bd5f37e6c2e3'
assert subprocess.run(['git','merge-base','--is-ancestor',head,SHA],cwd=proofrepo).returncode==0
remote=git(proofrepo,'ls-remote','https://github.com/KumarNavish/casepath.git','refs/heads/codex/casepath-causal-experience-integration-20261009').split()[0];assert remote==SHA
assert not git(repo,'ls-files','--others','--exclude-standard')
rows=[]
for line in git(repo,'ls-files','--stage').splitlines():
 metadata,name=line.split('\t',1);mode,oid,stage=metadata.split();assert stage=='0' and mode in ['100644','100755']
 p=repo/name;raw=p.read_bytes();blob=subprocess.check_output(['git','cat-file','blob',oid],cwd=repo);assert raw==blob and not p.is_symlink()
 rows.append({'path':name,'git_blob':oid,'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)})
record={'action':'retire_only_reproducible_tracked_files_of_completed_inventory_checkout','path':str(repo),'head':head,'canonical_descendant':SHA,'canonical_remote_head_verified':remote,'all_refs_preserved':git(repo,'for-each-ref','--format=%(refname) %(objectname)').splitlines(),'normal_Git_directory_preserved':True,'all_ignored_untracked_files_runtime_fixtures_journals_and_receipts_preserved':True,'tracked_files_verified_byte_equal_Git':rows,'before_free_bytes':shutil.disk_usage('/workspace').free,'epoch':time.time()}
(R/'retirement-receipts/completed-inventory-checkout-before.json').write_text(json.dumps(record,indent=2)+'\n')
for row in rows:(repo/row['path']).unlink()
record['after_free_bytes']=shutil.disk_usage('/workspace').free
(R/'retirement-receipts/completed-inventory-checkout.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'files':len(rows),'reclaimed_bytes':record['after_free_bytes']-record['before_free_bytes'],'free_bytes':record['after_free_bytes']}),flush=True)

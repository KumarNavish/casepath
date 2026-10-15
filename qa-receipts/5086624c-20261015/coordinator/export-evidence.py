import hashlib,json,shutil,subprocess,sys
from pathlib import Path
R=Path('/workspace/casepath-saved-history-gate-5086624c-20261015')
G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
BRANCH='qa-receipts/5086624c-20261015'
D=G/'qa-receipts/5086624c-20261015'
def git(*args):return subprocess.check_output(['git',*args],cwd=G,text=True).strip()
assert not git('status','--porcelain')
assert git('rev-parse','HEAD')=='26548cdd4e2bc237a742de985bbec3e821d8d5a3'
assert json.loads((R/'aggregate.json').read_text())['status']=='PASSED_WITH_MAC_OWNER_ATTESTATION'
assert json.loads((R/'coordinator/export-secret-pattern-review.json').read_text())['unproven_matches']==0
assert hashlib.sha256((R/'coordinator/root-independent-raw-reconciliation.json').read_bytes()).hexdigest()==sys.argv[1]
assert not D.exists()
subprocess.run(['git','switch','-c',BRANCH],cwd=G,check=True)
D.mkdir()
for line in (R/'raw-evidence-files-SHA256SUMS.txt').read_text().splitlines():
 sha,relative=line.split('  ',1);p=R/relative;assert not p.is_symlink() and p.is_file();assert '..' not in Path(relative).parts;assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 target=D/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for name in ['raw-evidence-files-SHA256SUMS.txt','raw-bundle.json']:shutil.copyfile(R/name,D/name)
raw=json.loads((R/'raw-bundle.json').read_text());p=Path(raw['archive']);assert hashlib.sha256(p.read_bytes()).hexdigest()==raw['archive_sha256'];shutil.copyfile(p,D/'raw-evidence.tar.gz')
retirement=json.loads((R/'completed-shard1-runtime-retirement.json').read_text());p=Path(retirement['archive']);assert hashlib.sha256(p.read_bytes()).hexdigest()==retirement['archive_sha256'];shutil.copyfile(p,D/'completed1-pre-runtime-retirement.tar.gz')
files=sorted(p for p in D.rglob('*') if p.is_file())
(D/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(D).as_posix()+'\n' for p in files))
for line in (D/'SHA256SUMS').read_text().splitlines():
 sha,relative=line.split('  ',1);assert hashlib.sha256((D/relative).read_bytes()).hexdigest()==sha
assert all(line[3:].startswith('qa-receipts/5086624c-20261015/') or line[3:]=='qa-receipts/5086624c-20261015/' for line in git('status','--porcelain').splitlines())
print(json.dumps({'branch':BRANCH,'export_root':str(D),'file_count_including_checksum_manifest':len(files)+1,'total_bytes':sum(p.stat().st_size for p in D.rglob('*') if p.is_file()),'export_checksum_manifest_sha256':hashlib.sha256((D/'SHA256SUMS').read_bytes()).hexdigest(),'raw_archive_sha256':raw['archive_sha256']}),flush=True)

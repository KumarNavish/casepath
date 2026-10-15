import hashlib,json,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');BRANCH='qa-receipts/b8616d4c-20261016';D=G/BRANCH
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=G,text=True).strip()
assert git('branch','--show-current')==BRANCH
aggregate=json.loads((R/'aggregate.json').read_text());assert aggregate['full_cloud_gate_complete'] and aggregate['cloud_failed']==0 and aggregate['cloud_passed']==2476 and aggregate['cloud_known_skipped']==10
assert json.loads((R/'coordinator/export-secret-pattern-review.json').read_text())['unproven_matches']==0
for line in (R/'raw-evidence-files-SHA256SUMS.txt').read_text().splitlines():
 sha,rel=line.split('  ',1);p=R/rel;assert not p.is_symlink() and p.is_file() and '..' not in Path(rel).parts and digest(p)==sha
 q=D/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
for name in ['raw-evidence-files-SHA256SUMS.txt','raw-bundle.json']:shutil.copy2(R/name,D/name)
bundle=json.loads((R/'raw-bundle.json').read_text());p=Path(bundle['archive']);assert digest(p)==bundle['archive_sha256'];shutil.copy2(p,D/'raw-evidence.tar.gz')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(D/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(D).as_posix()+'\n' for p in files))
for line in (D/'SHA256SUMS').read_text().splitlines():
 sha,rel=line.split('  ',1);assert digest(D/rel)==sha
subprocess.run(['git','add','--',BRANCH],cwd=G,check=True)
changed=git('diff','--cached','--name-only').splitlines();assert changed and all(p.startswith(BRANCH+'/') for p in changed)
subprocess.run(['git','commit','-m','qa: verify full b861 Cloud gate and preserve all raw receipts'],cwd=G,check=True,stdout=subprocess.DEVNULL)
subprocess.run(['git','push','--set-upstream','origin',BRANCH],cwd=G,check=True,stdout=subprocess.DEVNULL)
commit=git('rev-parse','HEAD');remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+BRANCH],cwd=G,text=True).split()[0];assert commit==remote and not git('status','--porcelain')
record={'candidate':'b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b','branch':BRANCH,'commit':commit,'remote_verified':True,'subtree':BRANCH,'export_files_including_checksum_manifest':len(files)+1,'export_total_bytes':sum(p.stat().st_size for p in D.rglob('*') if p.is_file()),'export_checksum_manifest_sha256':digest(D/'SHA256SUMS'),'raw_archive_sha256':bundle['archive_sha256'],'epoch':time.time()}
(R/'coordinator/final-export-receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)

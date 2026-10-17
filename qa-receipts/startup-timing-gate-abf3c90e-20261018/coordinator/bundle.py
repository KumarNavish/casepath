import hashlib,json,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-timing-gate-abf3c90e-20261018')
result=json.loads((R/'raw-reconciliation.json').read_text());assert result['cloud_failed']==0 and result['all_six_first_only_attempts']
excluded_dirs={'home','tmp','pycache','uv-cache','artifact-registry','pytest-tmp','__pycache__'}
excluded_files={'SHA256SUMS','raw-evidence-files-SHA256SUMS.txt','raw-bundle.json','raw-evidence.tar.gz'}
included=[p for p in sorted(R.rglob('*')) if p.is_file() and not p.is_symlink() and not any(x in excluded_dirs for x in p.relative_to(R).parts) and p.name not in excluded_files and (p.suffix in {'.py','.json','.jsonl','.txt','.log','.xml'} or p.name.endswith('-raw.tar.gz'))]
assert len(included)==len(set(included))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checksum=R/'raw-evidence-files-SHA256SUMS.txt';checksum.write_text(''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in included))
archive=R/'raw-evidence.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=6) as t:
 for p in included+[checksum]:t.add(p,arcname=p.relative_to(R).as_posix(),recursive=False)
with tarfile.open(archive,'r:gz') as t:
 assert len(t.getmembers())==len(included)+1
 for p in included+[checksum]:assert hashlib.sha256(t.extractfile(p.relative_to(R).as_posix()).read()).hexdigest()==digest(p)
record={'candidate':result['candidate'],'manifest_sha256':result['manifest_sha256'],'archive':str(archive),'archive_sha256':digest(archive),'archive_size_bytes':archive.stat().st_size,'raw_file_count':len(included),'checksum_manifest_sha256':digest(checksum),'all_archive_members_byte_verified':True,'contains_runtime_databases':False,'includes':'Every selected QA receipt, source/artifact manifest, raw collect/order, all six assignment arguments/commands/controlled test environments/prepare transport-variable names/phase reports/JUnit/durations/latches, capsule before-after source/static/artifact proofs, exact rename and old baseline coverage, Mac owner attestation, root independent reviews, resource/process observations and retirement proofs, preserved preparation failures','explicit_exclusions':['venv and capsule byte copies (exact hashed source/capsule/artifact/static receipt proofs retained)','dependency caches and pycache','mutable HOME/TMP/DB/artifact registry','passing fixture bytes; any failed fixture bytes remain preserved on host (no failed test in this gate)','isolated Git index binary and transport records created after final commit','Mac raw files remain on Mac; actual owner attestation included; no Cloud raw Mac inspection claimed'],'created_epoch':time.time()}
(R/'raw-bundle.json').write_text(json.dumps(record,indent=2)+'\n')
(R/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(included+[checksum,archive,R/'raw-bundle.json'])))
print(json.dumps(record),flush=True)

from pathlib import Path
import hashlib,json,tarfile,time
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
result=json.loads((R/'raw-reconciliation.json').read_text());assert result['cloud_failed']==0 and result['all_six_first_only_attempts']
exclude={'SHA256SUMS','raw-evidence-files-SHA256SUMS.txt','raw-bundle.json','raw-evidence.tar.gz'}
included=[p for p in sorted(R.iterdir()) if p.is_file() and p.name not in exclude and p.suffix in {'.json','.jsonl','.txt','.log'}]
for name in ['harness','coordinator','inventory']+[f'shard{n}' for n in range(1,7)]:
 directory=R/name
 included.extend(p for p in sorted(directory.iterdir()) if p.is_file() and p.suffix in {'.py','.json','.jsonl','.txt','.log','.xml'})
 if name.startswith('shard'):
  for phase in ['before','after']:included.extend(p for p in sorted((directory/f'source-{phase}').iterdir()) if p.is_file())
for p in sorted((R/'retirement-receipts').iterdir()):
 if p.is_file() and (p.suffix=='.json' or p.name.endswith('-raw.tar.gz')):included.append(p)
assert len(included)==len(set(included)) and all(not p.is_symlink() for p in included)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checksum=R/'raw-evidence-files-SHA256SUMS.txt';checksum.write_text(''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(included)))
archive=R/'raw-evidence.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=6) as t:
 for p in sorted(included)+[checksum]:t.add(p,arcname=p.relative_to(R).as_posix(),recursive=False)
with tarfile.open(archive,'r:gz') as t:
 for p in sorted(included)+[checksum]:assert hashlib.sha256(t.extractfile(p.relative_to(R).as_posix()).read()).hexdigest()==digest(p)
record={'candidate':result['candidate'],'manifest_sha256':result['manifest_sha256'],'archive':str(archive),'archive_sha256':digest(archive),'archive_size_bytes':archive.stat().st_size,'raw_file_count':len(included),'checksum_manifest_sha256':digest(checksum),'all_archive_members_byte_verified':True,'contains_runtime_databases':False,'excludes':['venvs','source capsule bytes (exact before/after receipt proofs included)','dependency caches','pycache','runtime databases','passing/failed temporary fixture bytes (retained separately on host if present)'],'includes':'All raw collection, commands/controlled environments, phase observer, JUnit, first-attempt latch, normal prepare, source/capsule proofs, map and delta, source/artifact manifest, resources, cleanup provenance and shard terminal/retirement receipts','created_epoch':time.time()}
(R/'raw-bundle.json').write_text(json.dumps(record,indent=2)+'\n')
(R/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(included+[checksum,archive,R/'raw-bundle.json'])))
print(json.dumps(record),flush=True)

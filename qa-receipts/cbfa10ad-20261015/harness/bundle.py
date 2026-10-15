import hashlib, json, tarfile, time
from pathlib import Path
R=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015')
aggregate=json.loads((R/'aggregate.json').read_text())
assert aggregate['status']=='CANCELLED_SUPERSEDED' and aggregate['full_gate_complete'] is False and aggregate['final_green_claim'] is False
included=[]
for p in sorted(R.iterdir()):
    if p.is_file() and p.suffix in {'.json','.jsonl','.txt','.log','.md'} and p.name not in {'raw-evidence-files-SHA256SUMS.txt','raw-bundle.json'}:
        included.append(p)
for name in ['harness','coordinator','review','retirement-receipts']:
    directory=R/name
    if directory.exists():
        included.extend(p for p in sorted(directory.rglob('*')) if p.is_file() and not p.is_symlink() and p.suffix in {'.py','.json','.jsonl','.txt','.log','.md','.xml','.patch','.diff'})
for name in ['inventory']+[f'shard{i}' for i in range(1,7)]:
    directory=R/name
    included.extend(p for p in sorted(directory.iterdir()) if p.is_file() and p.suffix in {'.json','.jsonl','.txt','.log','.xml'})
    for phase in ['before','after']:
        included.extend(p for p in sorted((directory/('source-'+phase)).iterdir()) if p.is_file())
assert len(included)==len(set(included))
assert all(not p.is_symlink() for p in included)
checksums=R/'raw-evidence-files-SHA256SUMS.txt'
checksums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(included)))
archive=R.parent/(R.name+'-raw-evidence.tar.gz')
with tarfile.open(archive,'w:gz',compresslevel=6) as tf:
    for p in sorted(included)+[checksums]: tf.add(p,arcname=R.name+'/'+p.relative_to(R).as_posix(),recursive=False)
record={'candidate':'cbfa10adaee2dd777b2aea3fc888c5ee4fa3f236','archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_size_bytes':archive.stat().st_size,'file_count_excluding_checksum_manifest':len(included),'checksum_manifest':str(checksums),'checksum_manifest_sha256':hashlib.sha256(checksums.read_bytes()).hexdigest(),'created_epoch':time.time(),'gate_status':aggregate['status'],'full_gate_complete':False,'includes':'every available native raw collection/attempt/phase/JUnit/result/prepare/source proof (interrupted attempt outputs remain incomplete or absent as observed), exact assignment IDs, source and artifact manifests, authorization, resource and cleanup receipts, QA scripts, coordinator and independent review evidence available at bundle creation','excludes':'dependency caches, pycache, temporary passing fixtures and runtime DBs; original evidence and failed fixtures remain preserved on host; Mac raw phase/JUnit receipts absent in Cloud'}
(R/'raw-bundle.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)

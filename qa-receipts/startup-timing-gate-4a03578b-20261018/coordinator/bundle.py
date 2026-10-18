import hashlib,json,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-startup-timing-gate-4a03578b-20261018')
result=json.loads((R/'raw-reconciliation.json').read_text());assert result['cloud_failed']==0 and result['all_six_first_only_attempts']
# Preserve the established original archives; describe their owned fixture DB snapshots accurately.
fixture_db_members=[]
clones=json.loads((R/'clone-map.json').read_text())['repos']
source_repo=Path(clones['1'])
source_bindings={rel:hashlib.sha256((source_repo/rel).read_bytes()).hexdigest() for rel in ['casepath-api/casepath_api/storage.py','casepath-api/casepath_api/app.py']}
for n in range(1,7):
 out=R/f'shard{n}';archive_path=R/f'retirement-receipts/shard{n}-raw.tar.gz';command=json.loads((out/'command.json').read_text());env=command['env']
 assert env['CASEPATH_DB_PATH']==str(out/'casepath.db') and env['CASEPATH_QA_ARTIFACTS']==str(out)
 with tarfile.open(archive_path,'r:gz') as tf:
  for member in tf.getmembers():
   if not member.isfile() or not member.name.endswith(('.db','.sqlite','.sqlite3','-wal','-shm')):continue
   assert member.name in {'casepath.db','agent-work-v1.sqlite3'},('Unknown database-named archive member',archive_path,member.name)
   fixture_db_members.append({'shard':n,'archive_member':archive_path.relative_to(R).as_posix()+'::'+member.name,'snapshot_size_bytes':member.size,'owned_test_path':str(out/member.name),'command_receipt':f'shard{n}/command.json','command_receipt_sha256':hashlib.sha256((out/'command.json').read_bytes()).hexdigest(),'controlled_CASEPATH_DB_PATH':env['CASEPATH_DB_PATH'],'controlled_CASEPATH_QA_ARTIFACTS':env['CASEPATH_QA_ARTIFACTS'],'binding':'casepath.db selected by CASEPATH_DB_PATH; agent-work-v1.sqlite3 uses storage.path.parent in sealed app.py:392','sealed_source_file_sha256':source_bindings})
scope={'candidate':result['candidate'],'original_per_shard_archive_bytes_preserved':True,'contains_owned_deterministic_fixture_database_snapshots':bool(fixture_db_members),'exact_nested_fixture_database_members':fixture_db_members,'direct_mutable_database_files_excluded':True,'unrelated_or_production_databases_excluded':True,'qualification':'Known original per-shard snapshots only, proven by isolated command environments and sealed storage.py:67/app.py:392. No database content inspection or export expansion. No production histories, credentials, or production journals transported. Mac verifier must not interpret nested original fixture snapshots as excluded database bytes.'}
(R/'raw-archive-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
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
record={'candidate':result['candidate'],'manifest_sha256':result['manifest_sha256'],'archive':str(archive),'archive_sha256':digest(archive),'archive_size_bytes':archive.stat().st_size,'raw_file_count':len(included),'checksum_manifest_sha256':digest(checksum),'all_archive_members_byte_verified':True,'contains_runtime_databases':bool(fixture_db_members),'nested_owned_fixture_database_members':fixture_db_members,'database_scope_receipt':'raw-archive-scope.json','includes':'Every selected QA receipt, source/artifact manifest, raw collect/order, all six assignment arguments/commands/controlled test environments/prepare transport-variable names/phase reports/JUnit/durations/latches, capsule before-after source/static/artifact proofs, historical rename proof and unchanged exact baseline coverage, Mac owner attestation, root independent reviews, resource/process observations and retirement proofs, prior failed-gate durable reference and runtime recovery proof','explicit_exclusions':['venv and capsule byte copies (exact hashed source/capsule/artifact/static receipt proofs retained)','dependency caches and pycache','mutable HOME/TMP/direct DB/artifact registry; exact nested owned fixture DB snapshots retained inside original per-shard raw archives','passing fixture bytes; any failed fixture bytes remain preserved on host (no failed test in this gate)','isolated Git index binary and transport records created after final commit','Mac raw files remain on Mac; actual owner attestation included; no Cloud raw Mac inspection claimed'],'created_epoch':time.time()}
(R/'raw-bundle.json').write_text(json.dumps(record,indent=2)+'\n')
(R/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(included+[checksum,archive,R/'raw-bundle.json'])))
print(json.dumps(record),flush=True)

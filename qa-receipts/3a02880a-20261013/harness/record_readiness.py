import hashlib,json,shutil,time
from pathlib import Path
ROOT=Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
SHA='3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
names=['inventory']+[f'shard{i}' for i in range(1,7)]
records=[json.loads((ROOT/name/'source-before/capsule-verification.json').read_text()) for name in names]
assert len({r['capsule_receipt_file_sha256'] for r in records})==1
assert all(r['head']==SHA and not r['status'] for r in records)
proof=json.loads((ROOT/'proof-disjoint-union-before.json').read_text())
inventory=json.loads((ROOT/'inventory/result.json').read_text())
assert inventory['exit_code']==0 and inventory['after_head']==SHA and not inventory['after_status']
free=shutil.disk_usage('/workspace').free
assert free>=3*1024**3
readiness={'candidate':SHA,'ready_shards':list(range(1,7)),'prepared_normal_clones':7,'counts':proof['counts'],
    'full_inventory':2571,'cloud_assigned':2444,'mac_excluded':127,'inventory_exit_code':0,'source_before':records,
    'capsule_receipt_file_sha256':records[0]['capsule_receipt_file_sha256'],
    'workspace_free_bytes':free,'minimum_headroom_bytes':3*1024**3,'adequate_headroom':True,
    'cleanup_performed':False,'old_runtime_capsules_receipts_journals_failed_fixtures_preserved':True,
    'full_shard_tests_launched_by_preparation_agent':False,'verified_epoch':time.time()}
(ROOT/'phase2-readiness.json').write_text(json.dumps(readiness,indent=2))
omission={'candidate':SHA,'sealed_launcher_unchanged':True,
    'outer_prepare_coordinator_inventory_test_env':{'HOME':'own short/workspace/g3ahN','TMPDIR':'own short/workspace/g3atN','TMP':'same as TMPDIR','TEMP':'same as TMPDIR'},
    'launcher_stdlib_probes':{'contract':'run_clean_stdlib_python uses env -i and intentionally omits TMPDIR/TMP/TEMP','tempfile_module_or_api_used_in_launcher_stdlib_prepare_probes':False,'capsule_staging_path':'explicit runtime/source-capsules/.<manifest>.<pid>.<uuid>.tmp; no /tmp creation'},
    'launcher_locked_repository_scripts':{'contract':'run_clean_locked_python uses env -i and TMPDIR=runtime/tmp only, without TMP/TEMP','tempfile_preference':'explicit TMPDIR under each normalclone/workspace path'},
    'scope':'Exact source preserved; no shim, no launcher changes, no migration-audit weakening. Transport values not saved; only names/presence recorded for setup.'}
(ROOT/'launcher-temp-environment-contract.json').write_text(json.dumps(omission,indent=2))
provenance={}
old=Path('/workspace/casepath-quiet-completion-gate-0d9f9e22-20261013/harness')
for name in ['run_shard.py','casepath_shard_observer.py','verify_prepared_capsules.py']:
    provenance[name]={'origin':str(old/name),'origin_sha256':hashlib.sha256((old/name).read_bytes()).hexdigest(),'current_sha256':hashlib.sha256((ROOT/'harness'/name).read_bytes()).hexdigest()}
assert provenance['casepath_shard_observer.py']['origin_sha256']==provenance['casepath_shard_observer.py']['current_sha256']
(ROOT/'harness-provenance.json').write_text(json.dumps({'files':provenance,'changes':'Normal harness candidate/output/manifest/collect repo paths and short HOME/TMPDIR/TMP/TEMP only; observer bytes unchanged; verifier per-name phases only.'},indent=2))
print(json.dumps({key:readiness[key] for key in ['candidate','ready_shards','counts','workspace_free_bytes','capsule_receipt_file_sha256']}))

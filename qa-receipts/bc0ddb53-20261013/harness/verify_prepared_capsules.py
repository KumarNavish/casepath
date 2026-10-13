import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

ROOT = Path('/tmp/casepath-release-bc0-20261013')
SHA = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114'
MANIFEST_SHA = 'a7df9ddc28afd6f69b6a36e65ed5f2ac7d129648d64c01d4eea48c8b199386fd'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()

def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()

def verify_one(name):
    repo = Path('/workspace/casepath-release-ae0-' + name)
    out = ROOT / name
    prepare = json.loads((out / 'prepare.json').read_text())
    assert prepare['exit_code'] == 0 and prepare['after_head'] == SHA and not prepare['after_status']
    assert git(repo, 'rev-parse', 'HEAD') == SHA and not git(repo, 'status', '--porcelain')
    assert (repo / '.git').is_dir()
    capsule = repo / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST_SHA
    receipt_path = capsule / 'CAPSULE_RECEIPT.json'
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    semantic = dict(receipt)
    stated = semantic.pop('receipt_sha256')
    assert stated == digest(canonical(semantic))
    assert receipt['contract'] == 'casepath.sealed-source-capsule/1.0.0'
    assert stat.S_IMODE(capsule.stat().st_mode) == 0o500 and not capsule.is_symlink()
    source_raw = (repo / 'casepath/source-manifest.json').read_bytes()
    assert digest(source_raw) == MANIFEST_SHA == receipt['source_manifest_file_sha256']
    assert (capsule / 'casepath/source-manifest.json').read_bytes() == source_raw
    source = json.loads(source_raw)
    assert len(source['files']) == source['file_count'] == receipt['source_file_count'] == 1680
    assert receipt['source_roster_sha256'] == digest(canonical(source['files']))
    for row in source['files']:
        for root in [repo, capsule]:
            path = root / row['path']
            raw = path.read_bytes()
            assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
    artifact_rel = 'casepath-api/artifacts/artifact-manifest.json'
    artifact_raw = (repo / artifact_rel).read_bytes()
    assert source['artifact_manifest']['path'] == artifact_rel
    assert source['artifact_manifest']['sha256'] == receipt['artifact_manifest_file_sha256'] == digest(artifact_raw)
    assert (capsule / artifact_rel).read_bytes() == artifact_raw
    artifact = json.loads(artifact_raw)
    assert len(artifact['files']) == artifact['file_count'] == receipt['artifact_file_count'] == 25
    for row in artifact['files']:
        for root in [repo, capsule]:
            path = root / 'casepath-api/artifacts' / row['path']
            raw = path.read_bytes()
            assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
    sys.path.insert(0, str(repo / 'casepath/tools'))
    from build_static_site import verify_inventory
    from build_deployment_identity import build_payload
    static_rows = []
    for root in [repo, capsule]:
        public = root / 'casepath-public'
        verify_inventory(public)
        rows = []
        for path in sorted(public.rglob('*')):
            assert not path.is_symlink()
            if path.is_file():
                raw = path.read_bytes()
                rows.append({'path':path.relative_to(public).as_posix(), 'sha256':digest(raw), 'size_bytes':len(raw), 'executable':bool(path.stat().st_mode & stat.S_IXUSR)})
                if path.name != 'deployment.json':
                    assert raw == (root / 'casepath' / path.relative_to(public)).read_bytes()
        assert len(rows) == receipt['static_file_count'] == 37
        assert digest(canonical(rows)) == receipt['static_inventory_sha256']
        assert json.loads((public / 'deployment.json').read_text()) == build_payload(os.environ)
        static_rows.append(rows)
    assert static_rows[0] == static_rows[1]
    shutil.copy2(receipt_path, out / 'CAPSULE_RECEIPT.json')
    record = {'name':name, 'repo':str(repo), 'head':SHA, 'status':'', 'normal_clone':True,
              'manifest_sha256':MANIFEST_SHA, 'sealed_files_verified':1680,
              'capsule_root':str(capsule), 'capsule_receipt_path':str(receipt_path),
              'capsule_receipt_file_sha256':digest(receipt_raw), 'capsule_receipt':receipt,
              'source_artifact_static_bindings_verified':True,
              'existing_cli_prepare_verifies_repository_and_capsule_release':True,
              'static_helper':'build_static_site.verify_inventory and build_deployment_identity.build_payload',
              'prepare_exit_code':0, 'prepare_duration_seconds':prepare['duration_seconds'],
              'verified_epoch':time.time()}
    (out / 'capsule-verification.json').write_text(json.dumps(record, indent=2))
    print(json.dumps({'name':name, 'capsule_receipt_file_sha256':record['capsule_receipt_file_sha256'], 'source_artifact_static':[1680,25,37]}), flush=True)

if len(sys.argv) > 1:
    verify_one(sys.argv[1])
else:
    records = []
    names = ['inventory'] + [f'shard{i}' for i in range(1,7)]
    for name in names:
        repo = Path('/workspace/casepath-release-ae0-' + name)
        prepare = json.loads((ROOT / name / 'prepare.json').read_text())
        env = dict(prepare['env'])
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONSAFEPATH='1')
        subprocess.run([str(repo / '.runtime/casepath-dev-v2/venv/bin/python'), '-P', __file__, name], env=env, cwd=repo, check=True)
        records.append(json.loads((ROOT / name / 'capsule-verification.json').read_text()))
    assert len({r['capsule_receipt_file_sha256'] for r in records}) == 1
    source_path = ROOT / 'source-verification.json'
    shutil.copy2(source_path, ROOT / 'source-verification-phase1.json')
    source = json.loads(source_path.read_text())
    source.update(prepared_clones=7, phase='All seven normal clones prepared; source, artifact, static and capsule bindings verified',
                  canonical_fetched_heads=[json.loads((ROOT / name / 'prepare.json').read_text())['canonical_fetched_head'] for name in names],
                  checks=records, capsule_source_artifact_static_counts=[1680,25,37],
                  all_capsule_receipts_equal=True, capsule_receipt_file_sha256=records[0]['capsule_receipt_file_sha256'])
    source_path.write_text(json.dumps(source, indent=2))
    (ROOT / 'running-seal-verification.json').write_text(json.dumps(records, indent=2))
    (ROOT / 'capsule-verification.json').write_text(json.dumps(records, indent=2))
    (ROOT / 'phase2-readiness.json').write_text(json.dumps({'candidate':SHA, 'prepared_clones':7,
        'ready_shards':[1,2,3,5,6], 'serial_preparation_complete':True, 'full_shard_tests_launched_by_preparation_agent':False,
        'counts':{'1':242,'2':554,'3':229,'4':324,'5':563,'6':478}, 'verified_epoch':time.time()}, indent=2))
    print(json.dumps({'all7_ready':True, 'capsule_receipt_file_sha256':records[0]['capsule_receipt_file_sha256']}))

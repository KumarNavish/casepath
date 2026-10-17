import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

ROOT = Path('/workspace/casepath-startup-timing-gate-abf3c90e-20261018')
SHA = 'abf3c90eb351bbd0cffe7ca65ad4c3a7a292f67c'
MANIFEST_SHA = '46a2fc752a399545ea4c67049e0ef82f45a42eab4d0131d4adbad1d9596801aa'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()

def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()

def verify_one(name):
    repo = Path(json.loads((ROOT / 'clone-map.json').read_text())['repos'][name[5:]])
    prepared_out = ROOT / name
    out = prepared_out / ('source-' + (sys.argv[2] if len(sys.argv)>2 else 'before'))
    out.mkdir(exist_ok=False)
    prepare = json.loads((prepared_out / 'prepare.json').read_text())
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
    assert len(source['files']) == source['file_count'] == receipt['source_file_count'] == 1714
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
        assert len(rows) == receipt['static_file_count'] == 40
        assert digest(canonical(rows)) == receipt['static_inventory_sha256']
        assert json.loads((public / 'deployment.json').read_text()) == build_payload(os.environ)
        static_rows.append(rows)
    assert static_rows[0] == static_rows[1]
    shutil.copy2(receipt_path, out / 'CAPSULE_RECEIPT.json')
    record = {'name':name, 'repo':str(repo), 'head':SHA, 'status':'', 'normal_clone':True,
              'manifest_sha256':MANIFEST_SHA, 'sealed_files_verified':1714,
              'capsule_root':str(capsule), 'capsule_receipt_path':str(receipt_path),
              'capsule_receipt_file_sha256':digest(receipt_raw), 'capsule_receipt':receipt,
              'source_artifact_static_bindings_verified':True,
              'existing_cli_prepare_verifies_repository_and_capsule_release':True,
              'static_helper':'build_static_site.verify_inventory and build_deployment_identity.build_payload',
              'prepare_exit_code':0, 'prepare_duration_seconds':prepare['duration_seconds'],
              'verified_epoch':time.time()}
    (out / 'capsule-verification.json').write_text(json.dumps(record, indent=2))
    if sys.argv[2]=='after' and (prepared_out/'runtime-before.json').exists():
        sys.path.insert(0,str(ROOT/'harness'))
        from runtime_inventory import capture_runtime
        capture_runtime(repo,prepared_out,'after')
    print(json.dumps({'name':name, 'capsule_receipt_file_sha256':record['capsule_receipt_file_sha256'], 'source_artifact_static':[1714, 25, 40]}), flush=True)

if __name__ == '__main__':
    assert len(sys.argv) == 3
    verify_one(sys.argv[1])

"""Evidence-only cross-check of completed receipts; executes no tests or writes to source."""
import ast
import collections
import hashlib
import json
from pathlib import Path
import socket
import stat
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path('/tmp/casepath-release-2af5-20261013')
SHA = '2af5e4897284b0b1eab7a82a4e98273ae481b77b'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()

def id_digest(ids):
    return digest(('\n'.join(sorted(ids)) + '\n').encode())

def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')

def skip_tuple(row):
    path, line, reason = ast.literal_eval(row['skip_reason'])
    return row['id'], row['when'], path[path.index('casepath-api/'):], line, reason

full = (ROOT / 'collected-ids.txt').read_text().splitlines()
mac = (ROOT / 'mac-ids.txt').read_text().splitlines()
mapping = json.loads((ROOT / 'shard-map.json').read_text())['shards']
reference = json.loads((ROOT / 'known-skip-reference.json').read_text())
reference_skips = {row['id']: skip_tuple(row) for row in reference}
assert len(full) == len(set(full)) == 2517 and len(mac) == len(set(mac)) == 127
executed, skipped, summaries, capsules = [], [], [], []
per_files = collections.defaultdict(collections.Counter)
for shard, assigned in mapping.items():
    out = ROOT / ('shard' + shard)
    repo = Path('/workspace/casepath-release-ae0-shard' + shard)
    rows = [json.loads(line) for line in (out / 'reports.jsonl').read_text().splitlines()]
    items = json.loads((out / 'collected.json').read_text())
    collected = [item['id'] for item in items]
    phases = collections.Counter((row['id'], row['when']) for row in rows)
    assert all(count == 1 for count in phases.values())
    assert set(assigned) == set(collected) == {row['id'] for row in rows}
    assert len(assigned) == len(set(assigned)) == len(collected)
    junit = []
    for case in ET.parse(out / 'junit.xml').findall('.//testcase'):
        matches = []
        for item in items:
            parts = item['id'].split('::')
            ending = '.'.join([Path(parts[0]).stem] + parts[1:-1])
            classname = case.get('classname') or ''
            if case.get('name') == parts[-1] and ((not classname and parts[0].startswith('casepath/tools/')) or classname == ending or classname.endswith('.' + ending)):
                matches.append(item['id'])
        assert len(matches) == 1 and case.find('failure') is None and case.find('error') is None
        junit.append(matches[0])
    assert len(junit) == len(set(junit)) == len(assigned) and set(junit) == set(assigned)
    skipped.extend(row for row in rows if row['outcome'] == 'skipped')
    assert not any(row['outcome'] == 'failed' for row in rows)
    for test_id in assigned:
        actual = [row for row in rows if row['id'] == test_id]
        skip_rows = [row for row in actual if row['outcome'] == 'skipped']
        if skip_rows:
            assert len(skip_rows) == 1 and skip_tuple(skip_rows[0]) == reference_skips[test_id]
            expected_phases = {'setup', 'teardown'} if skip_rows[0]['when'] == 'setup' else {'setup', 'call', 'teardown'}
        else:
            expected_phases = {'setup', 'call', 'teardown'}
            assert all(row['outcome'] == 'passed' for row in actual)
        assert {row['when'] for row in actual} == expected_phases
        counts = per_files[test_id.split('::')[0]]
        counts['tests'] += 1
        counts['skipped' if skip_rows else 'passed'] += 1
        counts['observer_seconds'] += sum(row['duration'] for row in actual)
    result = json.loads((out / 'result.json').read_text())
    command = json.loads((out / 'command.json').read_text())
    assert result['exit_code'] == 0 and result['after_head'] == SHA and not result['after_status']
    assert command['env']['CASEPATH_SOURCE_COMMIT'] == SHA and command['env']['CASEPATH_MODEL_MODE'] == 'deterministic_reference'
    assert not any(any(token in key.upper() for token in ['API_KEY', 'SECRET', 'TOKEN', 'CREDENTIAL', 'PROXY']) for key in command['env'])
    assert not any(arg == '-k' or arg.startswith('--deselect') for arg in command['command'])
    assert (repo / '.git').is_dir() and subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True)
    executed.extend(junit)
    summaries.append({'shard': int(shard), 'tests': len(junit), 'passed': len(junit) - sum(row['outcome'] == 'skipped' for row in rows), 'skipped': sum(row['outcome'] == 'skipped' for row in rows), 'failed': 0, 'exit_code': 0, 'duration_seconds': result['duration_seconds'], 'assigned_collected_phase_junit_equal': True, 'ids_sha256': id_digest(junit), 'junit_sha256': digest((out / 'junit.xml').read_bytes())})
assert len(executed) == len(set(executed)) == 2390 and set(executed).isdisjoint(mac) and set(executed) | set(mac) == set(full)
assert len(skipped) == 10 and sorted(map(skip_tuple, skipped)) == sorted(map(skip_tuple, reference))
save('known-skip-observed-comparison.json', {'candidate': SHA, 'equal_id_phase_source_line_reason': True, 'new_or_missing': [], 'count': 10, 'records': [dict(zip(['id', 'phase', 'source', 'line', 'reason'], skip_tuple(row))) for row in sorted(skipped, key=lambda row: row['id'])]})
for name in ['inventory'] + [f'shard{i}' for i in range(1, 7)]:
    repo = Path('/workspace/casepath-release-ae0-' + name)
    prepared = json.loads((ROOT / name / 'capsule-verification.json').read_text())
    capsule = Path(prepared['capsule_root'])
    receipt_raw = (capsule / 'CAPSULE_RECEIPT.json').read_bytes()
    receipt = json.loads(receipt_raw)
    semantic = dict(receipt)
    stated = semantic.pop('receipt_sha256')
    assert stated == digest(canonical(semantic))
    assert digest(receipt_raw) == prepared['capsule_receipt_file_sha256'] == digest((ROOT / name / 'CAPSULE_RECEIPT.json').read_bytes())
    assert stat.S_IMODE(capsule.stat().st_mode) == 0o500 and not capsule.is_symlink()
    manifest_raw = (repo / 'casepath/source-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    assert digest(manifest_raw) == prepared['manifest_sha256'] == receipt['source_manifest_file_sha256']
    assert (capsule / 'casepath/source-manifest.json').read_bytes() == manifest_raw
    assert len(manifest['files']) == receipt['source_file_count'] == 1680
    for row in manifest['files']:
        for root in [repo, capsule]:
            path = root / row['path']
            raw = path.read_bytes()
            assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256']
    artifact_rel = 'casepath-api/artifacts/artifact-manifest.json'
    artifact_raw = (repo / artifact_rel).read_bytes()
    artifact = json.loads(artifact_raw)
    assert digest(artifact_raw) == receipt['artifact_manifest_file_sha256'] == manifest['artifact_manifest']['sha256']
    assert (capsule / artifact_rel).read_bytes() == artifact_raw and len(artifact['files']) == 25
    for row in artifact['files']:
        for root in [repo, capsule]:
            path = root / 'casepath-api/artifacts' / row['path']
            raw = path.read_bytes()
            assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256']
    inventories = []
    for root in [repo, capsule]:
        rows = []
        for path in sorted((root / 'casepath-public').rglob('*')):
            assert not path.is_symlink()
            if path.is_file():
                raw = path.read_bytes()
                relative = path.relative_to(root / 'casepath-public').as_posix()
                rows.append({'path': relative, 'sha256': digest(raw), 'size_bytes': len(raw), 'executable': bool(path.stat().st_mode & stat.S_IXUSR)})
                if path.name != 'deployment.json':
                    assert raw == (root / 'casepath' / relative).read_bytes()
        assert len(rows) == receipt['static_file_count'] == 37 and digest(canonical(rows)) == receipt['static_inventory_sha256']
        inventories.append(rows)
    assert inventories[0] == inventories[1]
    capsules.append({'name': name, 'source_files': 1680, 'artifacts': 25, 'static_files': 37, 'capsule_receipt_sha256': digest(receipt_raw), 'read_only_post_run_bytes_equal': True})
assert len({row['capsule_receipt_sha256'] for row in capsules}) == 1
save('root-post-run-capsule-verification.json', {'candidate': SHA, 'checks': capsules, 'no_copy_or_permissions_changed': True, 'ancillary_error': 'shard3 post-run standard verifier passed integrity assertions then failed shutil.copy2 over existing read-only evidence receipt; original exit1/log retained; independent read-only checks passed.'})
attestation = json.loads((ROOT / 'mac-coordinator-attestation.json').read_text())
assert attestation['candidate'] == SHA and attestation['passed'] == 127 and attestation['failed'] == attestation['skipped'] == 0 and attestation['assigned_sorted_sha256'] == id_digest(mac)
save('per-file-durations.json', [dict(path=path, **dict(counts)) for path, counts in sorted(per_files.items())])
save('root-independent-coverage-verification.json', {'candidate': SHA, 'host': socket.gethostname(), 'cloud': {'tests': 2390, 'passed': 2380, 'skipped': 10, 'failed': 0}, 'mac_attested': {'passed': 127, 'failed': 0, 'skipped': 0, 'pytest_seconds': 123.21}, 'combined': {'tests': 2517, 'passed': 2507, 'skipped': 10, 'failed': 0}, 'full_ids_sha256': id_digest(full), 'cloud_ids_sha256': id_digest(executed), 'mac_ids_sha256': id_digest(mac), 'missing': [], 'duplicates': [], 'extra': [], 'deselected': [], 'retry_count': 0, 'shards': summaries, 'source_capsules_post_verified': True, 'verified_epoch': time.time(), 'mac_basis': 'Explicit integration-owner attestation, raw Mac JUnit not Cloud-parsed'})
print(json.dumps({'root_independent_verification': 'passed', 'combined': [2507, 0, 10], 'full_count': 2517, 'capsules_verified': 7, 'known_skip_id_phase_source_line_reason_equal': True}, indent=2))

import ast
import collections
import datetime
import hashlib
import json
import pathlib
import socket
import stat
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = pathlib.Path('/tmp/casepath-release-bc0-20261013')
OUT = ROOT / 'shard5'
REPO = pathlib.Path('/workspace/casepath-release-ae0-shard5')
SHA = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114'
MANIFEST_SHA = 'a7df9ddc28afd6f69b6a36e65ed5f2ac7d129648d64c01d4eea48c8b199386fd'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()

def ids_digest(values):
    return sha(('\n'.join(sorted(values)) + '\n').encode())

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')

result = json.loads((OUT / 'result.json').read_text())
command = json.loads((OUT / 'command.json').read_text())
mapping = json.loads((ROOT / 'shard-map.json').read_text())
assigned = mapping['shards']['5']
items = json.loads((OUT / 'collected.json').read_text())
collected = [item['id'] for item in items]
arguments = (OUT / 'pytest-arguments.txt').read_text().splitlines()
reports = [json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()]
byid = collections.defaultdict(list)
for row in reports:
    byid[row['id']].append(row)
assert socket.gethostname() == '656813ef2295'
assert mapping['candidate'] == command['candidate'] == result['candidate'] == SHA
assert result['started_epoch'] == command['started_epoch']
assert result['finished_epoch'] >= result['started_epoch']
assert len(assigned) == len(set(assigned)) == len(collected) == len(set(collected)) == len(byid) == 563
assert set(assigned) == set(collected) == set(byid)
assert arguments == assigned
mac_ids = set((ROOT / 'mac-ids.txt').read_text().splitlines())
assert len(mac_ids) == 127 and set(assigned).isdisjoint(mac_ids)

counts = collections.Counter()
outcomes = {}
durations = {}
skips = []
failures = []
for test_id, rows in byid.items():
    phases = [row['when'] for row in rows]
    assert len(phases) == len(set(phases)), (test_id, 'duplicate phases')
    assert set(phases).issubset({'setup', 'call', 'teardown'})
    assert {'setup', 'teardown'}.issubset(phases)
    setup = next(row for row in rows if row['when'] == 'setup')
    assert ('call' in phases) == (setup['outcome'] == 'passed'), test_id
    if any(row['outcome'] == 'failed' for row in rows):
        outcome = 'failed'
        for row in rows:
            if row['outcome'] == 'failed':
                failures.append(row)
    elif any(row['outcome'] == 'skipped' for row in rows):
        outcome = 'skipped'
        skipped = [row for row in rows if row['outcome'] == 'skipped']
        assert len(skipped) == 1
        row = skipped[0]
        location, line, reason = ast.literal_eval(row['skip_reason'])
        skips.append({'id': test_id, 'phase': row['when'], 'path': location, 'line': line, 'reason': reason, 'observer_longrepr': row['skip_reason']})
    else:
        assert set(phases) == {'setup', 'call', 'teardown'}
        assert all(row['outcome'] == 'passed' for row in rows)
        outcome = 'passed'
    outcomes[test_id] = outcome
    counts[outcome] += 1
    durations[test_id] = {'id': test_id, 'outcome': outcome, 'phases': [{'when': row['when'], 'outcome': row['outcome'], 'duration_seconds': row['duration'], 'utc_epoch': row['utc_epoch']} for row in rows], 'observer_duration_seconds': sum(row['duration'] for row in rows)}

cases = ET.parse(OUT / 'junit.xml').findall('.//testcase')
junit_ids = []
junit_counts = collections.Counter()
for case in cases:
    matches = []
    for item in items:
        parts = item['id'].split('::')
        ending = '.'.join([pathlib.Path(parts[0]).stem] + parts[1:-1])
        classname = case.get('classname') or ''
        if case.get('name') == parts[-1] and ((not classname and parts[0].startswith('casepath/tools/')) or classname == ending or classname.endswith('.' + ending)):
            matches.append(item['id'])
    assert len(matches) == 1, (case.attrib, matches)
    test_id = matches[0]
    junit_ids.append(test_id)
    junit_outcome = 'failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
    assert junit_outcome == outcomes[test_id], (test_id, junit_outcome, outcomes[test_id])
    junit_counts[junit_outcome] += 1
    durations[test_id]['junit_duration_seconds'] = float(case.get('time'))
assert len(junit_ids) == len(set(junit_ids)) == len(assigned)
assert set(junit_ids) == set(assigned)
assert counts == junit_counts
reference = {row['id']: ast.literal_eval(row['skip_reason'])[-1] for row in json.loads((ROOT / 'known-skip-reference.json').read_text()) if row['id'] in assigned}
assert {row['id']: row['reason'] for row in skips} == reference, 'changed, extra or missing skips'

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True)
assert head == result['after_head'] == SHA and not status and not result['after_status']
assert (REPO / '.git').is_dir()
manifest_raw = (REPO / 'casepath/source-manifest.json').read_bytes()
manifest = json.loads(manifest_raw)
assert sha(manifest_raw) == command['manifest_sha256'] == result['manifest_sha256'] == MANIFEST_SHA
capsule = REPO / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST_SHA
receipt_raw = (capsule / 'CAPSULE_RECEIPT.json').read_bytes()
receipt = json.loads(receipt_raw)
receipt_semantic = dict(receipt)
receipt_stated = receipt_semantic.pop('receipt_sha256')
assert sha(canonical(receipt_semantic)) == receipt_stated
assert receipt['contract'] == 'casepath.sealed-source-capsule/1.0.0'
assert stat.S_IMODE(capsule.stat().st_mode) == 0o500 and not capsule.is_symlink()
assert (OUT / 'CAPSULE_RECEIPT.json').read_bytes() == receipt_raw
assert (capsule / 'casepath/source-manifest.json').read_bytes() == manifest_raw
assert receipt['source_manifest_file_sha256'] == MANIFEST_SHA
assert manifest['file_count'] == len(manifest['files']) == receipt['source_file_count'] == 1680
assert receipt['source_roster_sha256'] == sha(canonical(manifest['files']))
for row in manifest['files']:
    for base in (REPO, capsule):
        path = base / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and sha(raw) == row['sha256'], str(path)

artifact_rel = 'casepath-api/artifacts/artifact-manifest.json'
artifact_raw = (REPO / artifact_rel).read_bytes()
artifact = json.loads(artifact_raw)
assert manifest['artifact_manifest']['path'] == artifact_rel
assert manifest['artifact_manifest']['sha256'] == receipt['artifact_manifest_file_sha256'] == sha(artifact_raw)
assert (capsule / artifact_rel).read_bytes() == artifact_raw
assert len(artifact['files']) == artifact['file_count'] == receipt['artifact_file_count'] == 25
for row in artifact['files']:
    for base in (REPO, capsule):
        path = base / 'casepath-api/artifacts' / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and sha(raw) == row['sha256'], str(path)

inventories = []
for base in (REPO, capsule):
    public = base / 'casepath-public'
    rows = []
    for path in sorted(public.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            raw = path.read_bytes()
            rows.append({'path': path.relative_to(public).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw), 'executable': bool(path.stat().st_mode & stat.S_IXUSR)})
            if path.name != 'deployment.json':
                assert raw == (base / 'casepath' / path.relative_to(public)).read_bytes()
    assert len(rows) == receipt['static_file_count'] == 37
    assert sha(canonical(rows)) == receipt['static_inventory_sha256']
    inventories.append(rows)
assert inventories[0] == inventories[1]
preverification = json.loads((OUT / 'capsule-verification.json').read_text())
assert preverification['source_artifact_static_bindings_verified']
assert preverification['capsule_receipt_file_sha256'] == sha(receipt_raw)
assert preverification['capsule_receipt'] == receipt
source_record = {'repo': str(REPO), 'head': head, 'status': status, 'normal_clone': True, 'source_manifest_sha256': MANIFEST_SHA, 'sealed_files_verified': 1680, 'capsule_root': str(capsule), 'capsule_receipt_sha256': receipt_stated, 'capsule_receipt_file_sha256': sha(receipt_raw), 'source_artifact_static_counts': [1680, 25, 37], 'source_artifact_static_bindings_verified': True, 'verified_epoch': time.time()}
save('post-run-source-verification.json', source_record)
save('skip-details.json', skips)
save('failure-details.json', failures)
save('per-test-durations.json', [durations[test_id] for test_id in sorted(durations)])
summary = {'candidate': SHA, 'host': socket.gethostname(), 'shard': 5, 'tests': len(assigned), 'passed': counts['passed'], 'failed': counts['failed'], 'skipped': counts['skipped'], 'exit_code': result['exit_code'], 'started_epoch': result['started_epoch'], 'finished_epoch': result['finished_epoch'], 'started_utc': datetime.datetime.fromtimestamp(result['started_epoch'], datetime.timezone.utc).isoformat(), 'finished_utc': datetime.datetime.fromtimestamp(result['finished_epoch'], datetime.timezone.utc).isoformat(), 'duration_seconds': result['duration_seconds'], 'observer_duration_seconds': sum(row['duration'] for row in reports), 'junit_duration_seconds': sum(float(case.get('time')) for case in cases), 'observer_phase_count': len(reports), 'observer_phase_counts': dict(collections.Counter(row['when'] for row in reports)), 'assigned_collected_executed_junit_equal': True, 'per_id_observer_junit_outcome_equal': True, 'duplicates': 0, 'missing': 0, 'extra': 0, 'assigned_sorted_sha256': ids_digest(assigned), 'collected_sorted_sha256': ids_digest(collected), 'executed_sorted_sha256': ids_digest(byid), 'junit_sorted_sha256': ids_digest(junit_ids), 'mac_ids_excluded': 127, 'after_head': head, 'after_status': status, 'sealed_files_verified': 1680, 'source_manifest_sha256': MANIFEST_SHA, 'capsule_receipt_file_sha256': sha(receipt_raw), 'source_artifact_static_counts': [1680,25,37], 'new_or_changed_skips': False, 'skip_details': skips, 'status': 'passed' if result['exit_code'] == 0 and not failures else 'failed'}
save('terminal-summary.json', summary)
files = [path for path in sorted(OUT.iterdir()) if path.is_file() and path.name != 'terminal-checksums.json']
save('terminal-checksums.json', {path.name: {'size_bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())} for path in files})
print(json.dumps(summary, indent=2))

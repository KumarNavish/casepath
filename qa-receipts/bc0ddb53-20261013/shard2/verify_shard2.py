import ast
import collections
import datetime
import hashlib
import json
from pathlib import Path
import socket
import stat
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path('/tmp/casepath-release-bc0-20261013')
OUT = ROOT / 'shard2'
REPO = Path('/workspace/casepath-release-ae0-shard2')
SHA = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114'
MANIFEST = 'a7df9ddc28afd6f69b6a36e65ed5f2ac7d129648d64c01d4eea48c8b199386fd'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode()


def ids_digest(ids):
    return digest(('\n'.join(sorted(ids)) + '\n').encode())


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2) + '\n')


def relative_skip(row):
    path, line, reason = ast.literal_eval(row['skip_reason'])
    path = Path(path)
    canonical_path = row['id'].split('::')[0]
    assert str(path).endswith('/' + canonical_path), row
    return {'id': row['id'], 'file': canonical_path, 'line': line,
            'reason': reason, 'phase': row['when']}


result = json.loads((OUT / 'result.json').read_text())
assigned = json.loads((ROOT / 'shard-map.json').read_text())['shards']['2']
collected_rows = json.loads((OUT / 'collected.json').read_text())
collected = [r['id'] for r in collected_rows]
reports = [json.loads(l) for l in (OUT / 'reports.jsonl').read_text().splitlines()]
by_id = collections.defaultdict(list)
for row in reports:
    by_id[row['id']].append(row)
assert len(assigned) == len(set(assigned)) == 554
assert (OUT / 'ids.txt').read_text().splitlines() == assigned
assert (OUT / 'pytest-arguments.txt').read_text().splitlines() == assigned
assert len(collected) == len(set(collected)) == len(by_id) == len(assigned)
assert set(assigned) == set(collected) == set(by_id)
assert not set(assigned) & set((ROOT / 'mac-ids.txt').read_text().splitlines())

outcomes = {}
skips = []
durations = []
for node, rows in by_id.items():
    phases = [r['when'] for r in rows]
    assert len(phases) == len(set(phases)), (node, phases)
    if any(r['outcome'] == 'failed' for r in rows):
        outcomes[node] = 'failed'
    elif any(r['outcome'] == 'skipped' for r in rows):
        outcomes[node] = 'skipped'
        skip_rows = [r for r in rows if r['outcome'] == 'skipped']
        assert len(skip_rows) == 1, node
        skips.append(relative_skip(skip_rows[0]))
    else:
        assert set(phases) == {'setup', 'call', 'teardown'}, (node, phases)
        assert all(r['outcome'] == 'passed' for r in rows), node
        outcomes[node] = 'passed'
    durations.append({'id': node, 'outcome': outcomes[node],
                      'observer_duration_seconds': sum(r['duration'] for r in rows)})

cases = ET.parse(OUT / 'junit.xml').findall('.//testcase')
junit = {}
for case in cases:
    matches = []
    for row in collected_rows:
        parts = row['id'].split('::')
        ending = '.'.join([Path(parts[0]).stem] + parts[1:-1])
        classname = case.get('classname') or ''
        if case.get('name') == parts[-1] and (
                not classname and parts[0].startswith('casepath/tools/')
                or classname == ending or classname.endswith('.' + ending)):
            matches.append(row['id'])
    assert len(matches) == 1, (case.attrib, matches)
    node = matches[0]
    assert node not in junit, node
    junit[node] = ('failed' if case.find('failure') is not None or case.find('error') is not None
                   else 'skipped' if case.find('skipped') is not None else 'passed')
    next(r for r in durations if r['id'] == node)['junit_duration_seconds'] = float(case.get('time'))
assert len(junit) == 554 and set(junit) == set(assigned)
assert junit == outcomes, 'Per-ID observer and JUnit outcomes differ'
known_skips = [relative_skip(r) for r in json.loads((ROOT / 'known-skip-reference.json').read_text())
               if r['id'] in set(assigned)]
assert sorted(skips, key=lambda r: r['id']) == sorted(known_skips, key=lambda r: r['id'])

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True)
assert socket.gethostname() == '656813ef2295'
assert head == result['candidate'] == result['after_head'] == SHA
assert not status and not result['after_status'] and (REPO / '.git').is_dir()
source_raw = (REPO / 'casepath/source-manifest.json').read_bytes()
assert digest(source_raw) == result['manifest_sha256'] == MANIFEST
source = json.loads(source_raw)
capsule = REPO / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST
assert stat.S_IMODE(capsule.stat().st_mode) == 0o500 and not capsule.is_symlink()
receipt_raw = (capsule / 'CAPSULE_RECEIPT.json').read_bytes()
receipt = json.loads(receipt_raw)
assert receipt_raw == (OUT / 'CAPSULE_RECEIPT.json').read_bytes()
semantic = dict(receipt)
assert semantic.pop('receipt_sha256') == digest(canonical(semantic))
assert receipt['contract'] == 'casepath.sealed-source-capsule/1.0.0'
assert receipt['source_manifest_file_sha256'] == MANIFEST
assert source_raw == (capsule / 'casepath/source-manifest.json').read_bytes()
assert len(source['files']) == source['file_count'] == receipt['source_file_count'] == 1680
assert receipt['source_roster_sha256'] == digest(canonical(source['files']))
for row in source['files']:
    for root in (REPO, capsule):
        path = root / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
artifact_rel = 'casepath-api/artifacts/artifact-manifest.json'
artifact_raw = (REPO / artifact_rel).read_bytes()
assert source['artifact_manifest']['path'] == artifact_rel
assert source['artifact_manifest']['sha256'] == receipt['artifact_manifest_file_sha256'] == digest(artifact_raw)
assert (capsule / artifact_rel).read_bytes() == artifact_raw
artifact = json.loads(artifact_raw)
assert len(artifact['files']) == artifact['file_count'] == receipt['artifact_file_count'] == 25
for row in artifact['files']:
    for root in (REPO, capsule):
        path = root / 'casepath-api/artifacts' / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
static_inventories = []
for root in (REPO, capsule):
    public = root / 'casepath-public'
    inventory = []
    for path in sorted(public.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            raw = path.read_bytes()
            inventory.append({'path': path.relative_to(public).as_posix(), 'sha256': digest(raw),
                              'size_bytes': len(raw), 'executable': bool(path.stat().st_mode & stat.S_IXUSR)})
            if path.name != 'deployment.json':
                assert raw == (root / 'casepath' / path.relative_to(public)).read_bytes()
    assert len(inventory) == receipt['static_file_count'] == 37
    assert digest(canonical(inventory)) == receipt['static_inventory_sha256']
    static_inventories.append(inventory)
assert static_inventories[0] == static_inventories[1]

counts = collections.Counter(outcomes.values())
summary = {'tests': len(assigned), 'passed': counts['passed'], 'failed': counts['failed'],
           'skipped': counts['skipped'], 'exit_code': result['exit_code'],
           'duration_seconds': result['duration_seconds'],
           'junit_duration_seconds': sum(float(c.get('time')) for c in cases),
           'assigned_collected_executed_junit_equal': True,
           'per_id_observer_junit_outcomes_equal': True,
           'coverage': {'missing': 0, 'duplicates': 0, 'extra': 0},
           'assigned_sorted_sha256': ids_digest(assigned),
           'executed_sorted_sha256': ids_digest(by_id),
           'junit_sorted_sha256': ids_digest(junit),
           'after_head': head, 'after_status': status, 'sealed_files_verified': 1680,
           'source_manifest_sha256': MANIFEST, 'capsule_receipt_file_sha256': digest(receipt_raw),
           'capsule_source_artifact_static_verified': [1680, 25, 37],
           'started_epoch': result['started_epoch'], 'finished_epoch': result['finished_epoch'],
           'started_utc': datetime.datetime.fromtimestamp(result['started_epoch'], datetime.UTC).isoformat(),
           'finished_utc': datetime.datetime.fromtimestamp(result['finished_epoch'], datetime.UTC).isoformat(),
           'attempt_directory': 'shard2',
           'status': 'passed' if result['exit_code'] == 0 and counts['failed'] == 0 else 'failed',
           'skip_records': skips, 'source_edits': False, 'retries': 0,
           'verified_epoch': time.time()}
save('shard-summary.json', summary)
save('worker-verification.json', summary)
save('worker-skips.json', skips)
save('worker-per-test-durations.json', sorted(durations, key=lambda r: r['id']))
for name, ids in [('worker-junit-canonical-ids.txt', junit), ('worker-observer-canonical-ids.txt', by_id)]:
    (OUT / name).write_text('\n'.join(sorted(ids)) + '\n')
for phase in ['setup', 'call', 'teardown']:
    failures = [r for r in reports if r['when'] == phase and r['outcome'] == 'failed']
    if failures:
        (OUT / ('failure-' + phase + '.txt')).write_text('\n\n'.join(r['id'] + '\n' + r['failure'] for r in failures) + '\n')
checksums = {p.name: {'size_bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
             for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'worker-checksums.json'}
save('worker-checksums.json', checksums)
print(json.dumps(summary, indent=2))

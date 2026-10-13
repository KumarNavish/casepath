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
OUT = ROOT / 'shard3'
REPO = pathlib.Path('/workspace/casepath-release-ae0-shard3')
SHA = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114'
MANIFEST_SHA = 'a7df9ddc28afd6f69b6a36e65ed5f2ac7d129648d64c01d4eea48c8b199386fd'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def id_digest(ids):
    return digest(('\n'.join(sorted(ids)) + '\n').encode())


def utc(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()


assigned = json.loads((ROOT / 'shard-map.json').read_text())['shards']['3']
ids_file = (OUT / 'ids.txt').read_text().splitlines()
arguments = (OUT / 'pytest-arguments.txt').read_text().splitlines()
items = json.loads((OUT / 'collected.json').read_text())
collected = [row['id'] for row in items]
reports = [json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()]
byid = collections.defaultdict(list)
for row in reports:
    byid[row['id']].append(row)
assert len(assigned) == len(set(assigned)) == 229
assert assigned == ids_file == arguments
assert len(collected) == len(set(collected)) == len(byid) == len(assigned)
assert set(assigned) == set(collected) == set(byid)
mac = (ROOT / 'mac-ids.txt').read_text().splitlines()
assert len(mac) == len(set(mac)) == 127 and set(assigned).isdisjoint(mac)
known = {row['id']: ast.literal_eval(row['skip_reason'])[-1]
         for row in json.loads((ROOT / 'known-skip-reference.json').read_text())}
counts = collections.Counter()
durations = []
skips = []
failures = []
outcomes = {}
for identity, rows in byid.items():
    assert len(rows) == len({row['when'] for row in rows}), (identity, 'duplicate phase')
    if any(row['outcome'] == 'failed' for row in rows):
        outcome = 'failed'
        failures.extend(row for row in rows if row['outcome'] == 'failed')
    elif any(row['outcome'] == 'skipped' for row in rows):
        outcome = 'skipped'
        skipped = [row for row in rows if row['outcome'] == 'skipped']
        assert len(skipped) == 1
        skip = skipped[0]
        path, line, reason = ast.literal_eval(skip['skip_reason'])
        skips.append({'id': identity, 'when': skip['when'], 'file': path,
                      'line': line, 'reason': reason, 'raw_longrepr': skip['skip_reason']})
    else:
        assert {row['when'] for row in rows} == {'setup', 'call', 'teardown'}
        assert all(row['outcome'] == 'passed' for row in rows)
        outcome = 'passed'
    outcomes[identity] = outcome
    counts[outcome] += 1
    durations.append({'id': identity, 'outcome': outcome,
                      'observer_duration_seconds': sum(row['duration'] for row in rows),
                      'phase_durations_seconds': {row['when']: row['duration'] for row in rows}})
expected_skips = {identity: reason for identity, reason in known.items() if identity in assigned}
actual_skips = {row['id']: row['reason'] for row in skips}
assert expected_skips == actual_skips, (expected_skips, actual_skips)
cases = ET.parse(OUT / 'junit.xml').findall('.//testcase')
junit_ids = []
junit_counts = collections.Counter()
for case in cases:
    matches = []
    for row in items:
        parts = row['id'].split('::')
        ending = '.'.join([pathlib.Path(parts[0]).stem] + parts[1:-1])
        classname = case.get('classname')
        if case.get('name') == parts[-1] and ((not classname and parts[0].startswith('casepath/tools/')) or classname == ending or classname.endswith('.' + ending)):
            matches.append(row['id'])
    assert len(matches) == 1, (case.attrib, matches)
    identity = matches[0]
    junit_ids.append(identity)
    outcome = 'failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
    assert outcome == outcomes[identity], (identity, outcome, outcomes[identity])
    junit_counts[outcome] += 1
    next(row for row in durations if row['id'] == identity)['junit_duration_seconds'] = float(case.get('time'))
assert len(junit_ids) == len(set(junit_ids)) == len(assigned)
assert set(junit_ids) == set(assigned) and counts == junit_counts
result = json.loads((OUT / 'result.json').read_text())
runner_exit = json.loads((OUT / 'runner-exit.json').read_text())
head = git('rev-parse', 'HEAD')
status = git('status', '--porcelain')
assert socket.gethostname() == '656813ef2295'
assert head == result['after_head'] == result['candidate'] == SHA
assert not status and not result['after_status'] and (REPO / '.git').is_dir()
assert runner_exit['exit_code'] == result['exit_code']
source_raw = (REPO / 'casepath/source-manifest.json').read_bytes()
assert digest(source_raw) == result['manifest_sha256'] == MANIFEST_SHA
source = json.loads(source_raw)
capsule = REPO / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST_SHA
receipt_raw = (capsule / 'CAPSULE_RECEIPT.json').read_bytes()
receipt = json.loads(receipt_raw)
receipt_semantic = dict(receipt)
assert receipt_semantic.pop('receipt_sha256') == digest(canonical(receipt_semantic))
assert receipt['contract'] == 'casepath.sealed-source-capsule/1.0.0'
assert not capsule.is_symlink() and stat.S_IMODE(capsule.stat().st_mode) == 0o500
assert len(source['files']) == source['file_count'] == receipt['source_file_count'] == 1680
assert receipt['source_manifest_file_sha256'] == MANIFEST_SHA
assert receipt['source_roster_sha256'] == digest(canonical(source['files']))
assert (capsule / 'casepath/source-manifest.json').read_bytes() == source_raw
assert (OUT / 'CAPSULE_RECEIPT.json').read_bytes() == receipt_raw
initial_capsule = json.loads((OUT / 'capsule-verification.json').read_text())
assert initial_capsule['capsule_receipt_file_sha256'] == digest(receipt_raw)
for row in source['files']:
    for root in [REPO, capsule]:
        path = root / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
artifact_relative = 'casepath-api/artifacts/artifact-manifest.json'
artifact_raw = (REPO / artifact_relative).read_bytes()
assert source['artifact_manifest']['path'] == artifact_relative
assert source['artifact_manifest']['sha256'] == receipt['artifact_manifest_file_sha256'] == digest(artifact_raw)
assert (capsule / artifact_relative).read_bytes() == artifact_raw
artifact = json.loads(artifact_raw)
assert len(artifact['files']) == artifact['file_count'] == receipt['artifact_file_count'] == 25
for row in artifact['files']:
    for root in [REPO, capsule]:
        path = root / 'casepath-api/artifacts' / row['path']
        raw = path.read_bytes()
        assert not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], str(path)
static_rosters = []
for root in [REPO, capsule]:
    public = root / 'casepath-public'
    roster = []
    for path in sorted(public.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            raw = path.read_bytes()
            roster.append({'path': path.relative_to(public).as_posix(), 'sha256': digest(raw),
                           'size_bytes': len(raw), 'executable': bool(path.stat().st_mode & stat.S_IXUSR)})
            if path.name != 'deployment.json':
                assert raw == (root / 'casepath' / path.relative_to(public)).read_bytes()
    assert len(roster) == receipt['static_file_count'] == 37
    assert digest(canonical(roster)) == receipt['static_inventory_sha256']
    static_rosters.append(roster)
assert static_rosters[0] == static_rosters[1]
seal = {'head': head, 'status': status, 'normal_clone': True,
        'source_manifest_sha256': MANIFEST_SHA, 'sealed_source_files_verified': 1680,
        'capsule_source_files_verified': 1680, 'artifact_files_verified': 25,
        'static_files_verified': 37, 'capsule_receipt_file_sha256': digest(receipt_raw),
        'capsule_receipt': receipt, 'verified_epoch': time.time()}
(OUT / 'post-run-seal-verification.json').write_text(json.dumps(seal, indent=2) + '\n')
(OUT / 'per-test-durations.json').write_text(json.dumps(sorted(durations, key=lambda row: row['id']), indent=2) + '\n')
(OUT / 'outcomes.json').write_text(json.dumps(outcomes, sort_keys=True, indent=2) + '\n')
(OUT / 'skips.json').write_text(json.dumps(skips, indent=2) + '\n')
(OUT / 'failures.json').write_text(json.dumps(failures, indent=2) + '\n')
for failure in failures:
    with (OUT / ('failure-' + failure['when'] + '.txt')).open('a') as handle:
        handle.write(failure['id'] + '\n' + failure['failure'] + '\n')
summary = {'shard': 3, 'candidate': SHA, 'host': socket.gethostname(),
           'command': ['python', str(ROOT / 'harness/run_shard.py'), 'run', '3'],
           'pytest_command': result['command'], 'cwd': result['cwd'],
           'exit_code': result['exit_code'], 'runner_exit_code': runner_exit['exit_code'],
           'started_epoch': result['started_epoch'], 'finished_epoch': result['finished_epoch'],
           'started_utc': utc(result['started_epoch']), 'finished_utc': utc(result['finished_epoch']),
           'duration_seconds': result['duration_seconds'],
           'observer_duration_seconds': sum(row['observer_duration_seconds'] for row in durations),
           'junit_duration_seconds': sum(row['junit_duration_seconds'] for row in durations),
           'assigned': len(assigned), 'collected': len(collected), 'observed': len(byid),
           'junit': len(junit_ids), 'passed': counts['passed'], 'failed': counts['failed'],
           'skipped': counts['skipped'], 'assigned_collected_observed_junit_equal': True,
           'missing': 0, 'duplicates': 0, 'extra': 0,
           'assigned_sorted_sha256': id_digest(assigned), 'collected_sorted_sha256': id_digest(collected),
           'observed_sorted_sha256': id_digest(byid), 'junit_sorted_sha256': id_digest(junit_ids),
           'mac_excluded_count': 127, 'mac_overlap': 0,
           'expected_skip_ids_and_reasons_unchanged': True, 'skips': skips,
           'failed_ids': sorted({row['id'] for row in failures}),
           'failure_fixture_state_retained': bool(failures), 'seal': seal,
           'raw_logs': ['runner.log', 'pytest.log', 'reports.jsonl', 'junit.xml'],
           'outcomes_artifact': 'outcomes.json', 'durations_artifact': 'per-test-durations.json',
           'artifact_checksums': 'worker-artifact-sha256.json',
           'no_rerun': True, 'source_edits': False,
           'status': 'passed' if result['exit_code'] == 0 and counts['failed'] == 0 else 'failed'}
(OUT / 'worker-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
paths = [path for path in OUT.iterdir() if path.is_file() and path.suffix in ('.json', '.jsonl', '.xml', '.log', '.txt', '.py') and path.name != 'worker-artifact-sha256.json']
checksums = {path.name: {'size_bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())} for path in sorted(paths)}
(OUT / 'worker-artifact-sha256.json').write_text(json.dumps(checksums, sort_keys=True, indent=2) + '\n')
print(json.dumps({key: summary[key] for key in ['shard', 'status', 'assigned', 'collected', 'observed', 'junit', 'passed', 'failed', 'skipped', 'duration_seconds', 'exit_code', 'started_utc', 'finished_utc']}))

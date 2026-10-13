import ast
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path('/tmp/casepath-release-bc0-20261013')
OUT = ROOT / 'shard6'
REPO = Path('/workspace/casepath-release-ae0-shard6')
SHA = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114'
MANIFEST_SHA = 'a7df9ddc28afd6f69b6a36e65ed5f2ac7d129648d64c01d4eea48c8b199386fd'
errors = []

def check(condition, label):
    if not condition:
        errors.append(label)
    return bool(condition)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()

def id_digest(ids):
    return digest(('\n'.join(sorted(ids)) + '\n').encode())

def read_json(path):
    return json.loads(path.read_text())

def utc(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()

mapping = read_json(ROOT / 'shard-map.json')
assigned = mapping['shards']['6']
items = read_json(OUT / 'collected.json')
collected = [r['id'] for r in items]
reports = [json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()]
result = read_json(OUT / 'result.json')
command = read_json(OUT / 'command.json')
by_id = collections.defaultdict(list)
for report in reports:
    by_id[report['id']].append(report)
    check(report['when'] in {'setup', 'call', 'teardown'}, 'unknown phase: ' + report['id'])
    check(report['outcome'] in {'passed', 'skipped', 'failed'}, 'unknown outcome: ' + report['id'])
    check(math.isfinite(report['duration']) and report['duration'] >= 0, 'invalid duration: ' + report['id'])

assigned_set = set(assigned)
check(len(assigned) == len(assigned_set) == 478, 'assignment count or uniqueness')
check(len(collected) == len(set(collected)) == 478, 'collection count or uniqueness')
check(assigned == (OUT / 'ids.txt').read_text().splitlines(), 'ids.txt order/content mismatch')
check(assigned == (OUT / 'pytest-arguments.txt').read_text().splitlines(), 'argument order/content mismatch')
check(assigned_set == set(collected) == set(by_id), 'assignment/collection/observer identity mismatch')
check(not assigned_set.intersection((ROOT / 'mac-ids.txt').read_text().splitlines()), 'Mac IDs executed on Cloud')
for item in items:
    check(item['id'] == item['file'] + '::' + item['pytest_nodeid'].split('::', 1)[1], 'noncanonical collection ID')

outcomes = {}
skips = []
failures = []
durations = []
for test_id, rows in sorted(by_id.items()):
    phases = [r['when'] for r in rows]
    check(len(phases) == len(set(phases)), 'duplicate observer phase: ' + test_id)
    failed = [r for r in rows if r['outcome'] == 'failed']
    skipped = [r for r in rows if r['outcome'] == 'skipped']
    if failed:
        outcome = 'failed'
        failures.extend(failed)
    elif skipped:
        outcome = 'skipped'
        check(len(skipped) == 1, 'multiple skipped phases: ' + test_id)
        check(set(phases) == ({'setup', 'teardown'} if skipped[0]['when'] == 'setup' else {'setup', 'call', 'teardown'}), 'incomplete skipped phases: ' + test_id)
        for row in skipped:
            path, line, reason = ast.literal_eval(row['skip_reason'])
            relative = Path(path).resolve().relative_to(REPO).as_posix()
            skips.append({'id': test_id, 'when': row['when'], 'file': relative, 'line': line, 'reason': reason})
    else:
        outcome = 'passed'
        check(set(phases) == {'setup', 'call', 'teardown'} and all(r['outcome'] == 'passed' for r in rows), 'incomplete passing phases: ' + test_id)
    outcomes[test_id] = outcome
    durations.append({'id': test_id, 'outcome': outcome, 'observer_duration_seconds': sum(r['duration'] for r in rows)})

expected_skips = []
for row in read_json(ROOT / 'known-skip-reference.json'):
    if row['id'] in assigned_set:
        path, line, reason = ast.literal_eval(row['skip_reason'])
        expected_skips.append({'id': row['id'], 'when': row['when'], 'file': row['id'].split('::', 1)[0], 'line': line, 'reason': reason})
check(len(expected_skips) == 9, 'expected skip intersection count')
check(sorted(skips, key=lambda r: r['id']) == sorted(expected_skips, key=lambda r: r['id']), 'new/missing/changed canonical skip ID/file/line/reason/phase')

junit = ET.parse(OUT / 'junit.xml')
cases = junit.findall('.//testcase')
junit_ids = []
junit_outcomes = {}
junit_rows = []
duration_by_id = {r['id']: r for r in durations}
for case in cases:
    matches = []
    cn = case.get('classname') or ''
    for item in items:
        parts = item['id'].split('::')
        ending = '.'.join([Path(parts[0]).stem] + parts[1:-1])
        if case.get('name') == parts[-1] and ((not cn and parts[0].startswith('casepath/tools/')) or cn == ending or cn.endswith('.' + ending)):
            matches.append(item['id'])
    check(len(matches) == 1, 'JUnit canonical identity match: ' + str(case.attrib))
    if len(matches) != 1:
        continue
    test_id = matches[0]
    junit_ids.append(test_id)
    outcome = 'failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
    junit_outcomes[test_id] = outcome
    seconds = float(case.get('time'))
    check(math.isfinite(seconds) and seconds >= 0, 'invalid JUnit duration: ' + test_id)
    junit_rows.append({'id': test_id, 'outcome': outcome, 'duration_seconds': seconds})
    duration_by_id[test_id]['junit_duration_seconds'] = seconds
check(len(cases) == len(junit_ids) == len(set(junit_ids)) == 478, 'JUnit count or uniqueness')
check(set(junit_ids) == assigned_set, 'JUnit gap/extra')
check(junit_outcomes == outcomes, 'per-ID JUnit/observer outcome mismatch')
check(result['candidate'] == command['candidate'] == SHA and result['command'] == command['command'] and result['env'] == command['env'], 'command/result changed')
check(result['started_epoch'] == command['started_epoch'] and result['finished_epoch'] >= result['started_epoch'], 'run timestamp mismatch')
expected_env_names = {'HOME', 'LANG', 'LC_ALL', 'PATH', 'NODE_PATH', 'PYTHONHASHSEED', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX', 'PYTHONPATH', 'SOURCE_DATE_EPOCH', 'TMPDIR', 'TZ', 'CASEPATH_MODEL_MODE', 'CASEPATH_SOURCE_COMMIT', 'CASEPATH_DB_PATH', 'CASEPATH_ARTIFACT_REGISTRY_PATH', 'CASEPATH_UV', 'CASEPATH_ENV_LOCK_HELD', 'CASEPATH_ENV_READY', 'UV_CACHE_DIR', 'UV_LINK_MODE', 'CASEPATH_QA_REPOSITORY', 'CASEPATH_QA_ARTIFACTS'}
check(set(result['env']) == expected_env_names, 'unexpected/missing sanitized environment variables')
check(result['env']['CASEPATH_MODEL_MODE'] == 'deterministic_reference' and result['env']['CASEPATH_SOURCE_COMMIT'] == SHA, 'deterministic/frozen environment')
for name in ['HOME', 'TMPDIR', 'PYTHONPYCACHEPREFIX', 'CASEPATH_DB_PATH', 'CASEPATH_ARTIFACT_REGISTRY_PATH', 'UV_CACHE_DIR', 'CASEPATH_QA_ARTIFACTS']:
    check(Path(result['env'][name]).resolve().is_relative_to(OUT), 'nonisolated path: ' + name)
check(result['command'] == [str(REPO / '.runtime/casepath-dev-v2/venv/bin/python'), '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'casepath_shard_observer', '--junitxml=' + str(OUT / 'junit.xml'), '--durations=0', '--basetemp=' + str(OUT / 'pytest-tmp'), '@' + str(OUT / 'pytest-arguments.txt')], 'frozen command arguments changed')
for row in read_json(ROOT / 'harness-provenance.json')['files']:
    check(digest((ROOT / 'harness' / row['file']).read_bytes()) == row['new_sha256'], 'harness provenance mismatch: ' + row['file'])

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True)
check(head == result['after_head'] == SHA and not status and not result['after_status'], 'post-run frozen checkout/cleanliness')
check((REPO / '.git').is_dir(), 'not normal clone')
check(socket.gethostname() == '656813ef2295', 'wrong execution host')
manifest_raw = (REPO / 'casepath/source-manifest.json').read_bytes()
manifest = json.loads(manifest_raw)
capsule = REPO / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST_SHA
receipt_raw = (capsule / 'CAPSULE_RECEIPT.json').read_bytes()
receipt = json.loads(receipt_raw)
semantic = dict(receipt)
receipt_sha = semantic.pop('receipt_sha256')
check(receipt_sha == digest(canonical(semantic)), 'capsule semantic receipt SHA')
check(receipt['contract'] == 'casepath.sealed-source-capsule/1.0.0', 'capsule contract')
check(stat.S_IMODE(capsule.stat().st_mode) == 0o500 and not capsule.is_symlink(), 'capsule mode/symlink')
check(digest(manifest_raw) == receipt['source_manifest_file_sha256'] == MANIFEST_SHA, 'manifest SHA binding')
check((capsule / 'casepath/source-manifest.json').read_bytes() == manifest_raw, 'capsule/repo manifest bytes')
check(len(manifest['files']) == manifest['file_count'] == receipt['source_file_count'] == 1680, 'sealed count')
check(receipt['source_roster_sha256'] == digest(canonical(manifest['files'])), 'source roster SHA')
for row in manifest['files']:
    for tree in [REPO, capsule]:
        path = tree / row['path']
        raw = path.read_bytes()
        check(not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], 'sealed source mismatch: ' + str(path))
artifact_rel = 'casepath-api/artifacts/artifact-manifest.json'
artifact_raw = (REPO / artifact_rel).read_bytes()
artifact = json.loads(artifact_raw)
check(manifest['artifact_manifest']['path'] == artifact_rel and manifest['artifact_manifest']['sha256'] == receipt['artifact_manifest_file_sha256'] == digest(artifact_raw), 'artifact manifest binding')
check((capsule / artifact_rel).read_bytes() == artifact_raw, 'capsule/repo artifact manifest bytes')
check(len(artifact['files']) == artifact['file_count'] == receipt['artifact_file_count'] == 25, 'artifact count')
for row in artifact['files']:
    for tree in [REPO, capsule]:
        path = tree / 'casepath-api/artifacts' / row['path']
        raw = path.read_bytes()
        check(not path.is_symlink() and len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], 'artifact mismatch: ' + str(path))
sys.path.insert(0, str(REPO / 'casepath/tools'))
from build_static_site import verify_inventory
from build_deployment_identity import build_payload
static_inventory = []
for tree in [REPO, capsule]:
    public = tree / 'casepath-public'
    verify_inventory(public)
    rows = []
    for path in sorted(public.rglob('*')):
        check(not path.is_symlink(), 'static symlink: ' + str(path))
        if path.is_file():
            raw = path.read_bytes()
            rows.append({'path': path.relative_to(public).as_posix(), 'sha256': digest(raw), 'size_bytes': len(raw), 'executable': bool(path.stat().st_mode & stat.S_IXUSR)})
            if path.name != 'deployment.json':
                check(raw == (tree / 'casepath' / path.relative_to(public)).read_bytes(), 'static/source mismatch: ' + str(path))
    check(len(rows) == receipt['static_file_count'] == 37 and digest(canonical(rows)) == receipt['static_inventory_sha256'], 'static inventory binding')
    check(read_json(public / 'deployment.json') == build_payload(result['env']), 'deployment metadata identity')
    static_inventory.append(rows)
check(static_inventory[0] == static_inventory[1], 'capsule/repo static inventory')
check(receipt_raw == (OUT / 'CAPSULE_RECEIPT.json').read_bytes(), 'prepared/current receipt mismatch')
check(read_json(OUT / 'capsule-verification.json')['capsule_receipt_file_sha256'] == digest(receipt_raw), 'prepared/current receipt file SHA mismatch')

counts = collections.Counter(outcomes.values())
coverage = {'missing': len(assigned_set - set(by_id)), 'extra': len(set(by_id) - assigned_set), 'assignment_duplicates': len(assigned) - len(assigned_set), 'collection_duplicates': len(collected) - len(set(collected)), 'junit_duplicates': len(junit_ids) - len(set(junit_ids)), 'assigned_collected_observer_junit_equal': assigned_set == set(collected) == set(by_id) == set(junit_ids)}
summary = {'candidate': SHA, 'host': socket.gethostname(), 'tests': len(assigned), 'passed': counts['passed'], 'failed': counts['failed'], 'skipped': counts['skipped'], 'exit_code': result['exit_code'], 'status': 'passed' if result['exit_code'] == 0 and counts['failed'] == 0 and not errors else 'failed', 'started_epoch': result['started_epoch'], 'started_utc': utc(result['started_epoch']), 'finished_epoch': result['finished_epoch'], 'finished_utc': utc(result['finished_epoch']), 'duration_seconds': result['duration_seconds'], 'observer_duration_seconds': sum(r['duration'] for r in reports), 'junit_duration_seconds': sum(float(c.get('time')) for c in cases), 'observer_phase_reports': len(reports), 'phase_counts': dict(collections.Counter(r['when'] for r in reports)), 'coverage': coverage, 'assigned_sorted_sha256': id_digest(assigned), 'collected_sorted_sha256': id_digest(collected), 'observer_sorted_sha256': id_digest(by_id), 'junit_sorted_sha256': id_digest(junit_ids), 'after_head': head, 'after_status': status, 'source_manifest_sha256': MANIFEST_SHA, 'sealed_files_verified': 1680, 'capsule_source_artifact_static_counts': [1680, 25, 37], 'capsule_receipt_file_sha256': digest(receipt_raw), 'capsule_receipt': receipt, 'expected_fixture_skips': sorted(expected_skips, key=lambda r: r['id']), 'actual_fixture_skips': sorted(skips, key=lambda r: r['id']), 'skip_ids_files_lines_reasons_phases_equal': sorted(skips, key=lambda r: r['id']) == sorted(expected_skips, key=lambda r: r['id']), 'validation_errors': errors, 'verified_epoch': time.time()}
(OUT / 'terminal-validation.json').write_text(json.dumps(summary, indent=2) + '\n')
(OUT / 'per-test-durations.json').write_text(json.dumps(durations, indent=2) + '\n')
(OUT / 'junit-canonical-ids.json').write_text(json.dumps(junit_rows, indent=2) + '\n')
(OUT / 'failures.json').write_text(json.dumps(failures, indent=2) + '\n')
artifacts = {}
for path in sorted(OUT.iterdir()):
    if path.is_file() and path.name != 'terminal-artifact-sha256.json':
        artifacts[path.name] = {'size_bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())}
(OUT / 'terminal-artifact-sha256.json').write_text(json.dumps(artifacts, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k not in {'capsule_receipt', 'actual_fixture_skips', 'expected_fixture_skips'}}, indent=2))
raise SystemExit(0 if summary['status'] == 'passed' else 1)

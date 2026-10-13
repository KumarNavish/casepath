from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
from _pytest.junitxml import mangle_test_address

ROOT = Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
OUT = ROOT / 'attempt2-shard6'
CANDIDATE = '3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
TARGET = 'casepath-api/tests/test_autonomous_adversarial_v1.py::test_submit_reassesses_arrival_after_outcome_before_knowledge_publication'
assert (OUT / 'result.json').exists(), 'Root-owned recheck is not terminal'
assigned = json.loads((ROOT / 'shard-map.json').read_text())['shards']['6']
arguments = (OUT / 'pytest-arguments.txt').read_text().splitlines()
collection = json.loads((OUT / 'collected.json').read_text())
collected = [row['id'] for row in collection]
reports = [json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()]
result = json.loads((OUT / 'result.json').read_text())
latch = json.loads((OUT / 'ATTEMPT_STARTED.json').read_text())
expected, mapping = {}, []
for row in collection:
    names = mangle_test_address(row['pytest_nodeid'])
    key = ('.'.join(names[:-1]), names[-1])
    assert key not in expected, 'Ambiguous JUnit identity'
    expected[key] = row['id']
    mapping.append({'id': row['id'], 'pytest_nodeid': row['pytest_nodeid'], 'junit_classname': key[0], 'junit_name': key[1]})

cases = ET.parse(OUT / 'junit.xml').findall('.//testcase')
xml_ids, unmatched, xml_outcomes = [], [], {}
for case in cases:
    key = (case.attrib['classname'], case.attrib['name'])
    if key not in expected:
        unmatched.append(key)
        continue
    identity = expected[key]
    xml_ids.append(identity)
    outcome = ('failed' if case.find('failure') is not None else 'error' if case.find('error') is not None
               else 'skipped' if case.find('skipped') is not None else 'passed')
    xml_outcomes[identity] = outcome

by_phase = {w: [r['id'] for r in reports if r['when'] == w] for w in ('setup', 'call', 'teardown')}
by_id = defaultdict(list)
for report in reports:
    by_id[report['id']].append(report)
skips = [r for r in reports if r['outcome'] == 'skipped']
known = json.loads((ROOT / 'known-skips.json').read_text())
own_known = [r for r in known if r['id'] in set(assigned)]
failures = [{'id': r['id'], 'when': r['when'], 'duration_seconds': r['duration'], 'utc_epoch': r['utc_epoch'],
             'trace_sha256': hashlib.sha256(r['failure'].encode()).hexdigest()} for r in reports if r['outcome'] == 'failed']
duplicate_counts = {name: len(ids) - len(set(ids)) for name, ids in
                    {'assigned': assigned, 'arguments': arguments, 'collected': collected, 'junit': xml_ids, **by_phase}.items()}
baseline = json.loads((OUT / 'worker-monitor-receipt.json').read_text())
preserved = {name: hashlib.sha256((ROOT / 'shard6' / name).read_bytes()).hexdigest() for name in baseline['original_raw_evidence_sha256']}
original_arguments = (ROOT / 'shard6/pytest-arguments.txt').read_text().splitlines()
checks = {
    'assigned_count_338': len(assigned) == 338,
    'arguments_exact_assigned': arguments == assigned,
    'arguments_exact_original': arguments == original_arguments,
    'collected_exact_assigned_set': set(collected) == set(assigned),
    'junit_exact_assigned_set': set(xml_ids) == set(assigned),
    'junit_no_unmatched': not unmatched,
    'raw_exact_assigned_set': set(by_id) == set(assigned),
    'each_phase_exact_assigned_set': all(set(ids) == set(assigned) for ids in by_phase.values()),
    'no_duplicate_ids': not any(duplicate_counts.values()),
    'exact_setup_call_teardown_order': all([r['when'] for r in rows] == ['setup', 'call', 'teardown'] for rows in by_id.values()),
    'raw_junit_outcome_match': all(xml_outcomes.get(r['id']) == r['outcome'] for r in reports if r['when'] == 'call'),
    'only_known_fixture_skips': {(r['id'], r['when']) for r in skips} == {(r['id'], r['when']) for r in own_known},
    'no_deselections': re.search(r'\b\d+ deselected\b', (OUT / 'pytest.log').read_text()) is None,
    'candidate_after_head_clean': result['after_head'] == CANDIDATE and not result['after_status'],
    'root_started_authorized_attempt2': latch['attempt_number'] == 2 and latch['one_resource_isolated_recheck_authorized'] and latch['prior_original_attempt_preserved'],
    'original_raw_evidence_preserved': preserved == baseline['original_raw_evidence_sha256'],
}
phase_counts = {f'{w}/{o}': n for (w, o), n in Counter((r['when'], r['outcome']) for r in reports).items()}
evidence_paths = [OUT / name for name in ('command.json', 'ATTEMPT_STARTED.json', 'result.json', 'collected.json', 'reports.jsonl', 'pytest.log', 'junit.xml', 'pytest-arguments.txt')]
proof = {
    'candidate': result['candidate'], 'shard': 6, 'attempt_number': 2, 'execution_owner': 'root',
    'worker_launched_tests': False, 'worker_polled_root_session': False, 'root_reported_exec_session_id': 19484,
    'observed_harness_pid': 712028, 'observed_pytest_pid': 712049,
    'terminal_exit_code': result['exit_code'], 'test_duration_seconds': result['duration_seconds'],
    'started_epoch': result['started_epoch'], 'finished_epoch': result['finished_epoch'],
    'assigned': len(assigned), 'arguments': len(arguments), 'collected': len(collected), 'junit': len(cases),
    'raw_unique_ids': len(by_id), 'raw_phases': len(reports), 'counts': dict(Counter(xml_outcomes.values())),
    'raw_phase_counts': phase_counts, 'phase_total_seconds': {w: sum(r['duration'] for r in reports if r['when'] == w) for w in by_phase},
    'duplicate_counts': duplicate_counts, 'checks': checks, 'junit_identity_mapping': mapping,
    'previously_failed_test_phases': [{k: r[k] for k in ('id', 'when', 'outcome', 'duration', 'utc_epoch')} for r in reports if r['id'] == TARGET],
    'failures': failures, 'skips': skips, 'assigned_known_skip_count': len(own_known),
    'after_head': result['after_head'], 'after_status': result['after_status'],
    'original_raw_evidence_sha256_after': preserved,
    'evidence_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_paths},
    'capsule_after_verification_owner': 'root; not run by this receipt worker', 'recorded_epoch': time.time(),
}
print(json.dumps({'counts': proof['counts'], 'raw_phase_counts': phase_counts, 'checks': checks, 'unmatched_junit': unmatched,
                  'failure_ids': [r['id'] for r in failures], 'duration_seconds': result['duration_seconds'],
                  'previously_failed_test_phases': proof['previously_failed_test_phases']}, indent=2))
assert all(checks.values()), 'Terminal ID evidence check failed'
with (OUT / 'worker-id-proof.json').open('x') as handle:
    json.dump(proof, handle, indent=2)

import ast
import collections
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from _pytest.junitxml import mangle_test_address

ROOT = Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
OUT = ROOT / 'shard3'
REPO = Path('/workspace/casepath-release-ae0-shard3')
SHA = '3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
assigned = json.loads((ROOT / 'shard-map.json').read_text())['shards']['3']
collected = json.loads((OUT / 'collected.json').read_text())
reports = [json.loads(line) for line in (OUT / 'reports.jsonl').read_text().splitlines()]
result = json.loads((OUT / 'result.json').read_text())
started = json.loads((OUT / 'ATTEMPT_STARTED.json').read_text())
collected_ids = [row['id'] for row in collected]
phase_rows = collections.defaultdict(list)
for row in reports:
    phase_rows[row['id']].append(row)

def junit_key(nodeid):
    names = mangle_test_address(nodeid)
    return ('.'.join(names[:-1]), names[-1])

junit_lookup = collections.defaultdict(list)
for row in collected:
    junit_lookup[junit_key(row['pytest_nodeid'])].append(row['id'])
junit = ET.parse(OUT / 'junit.xml').getroot()
junit_rows = []
unresolved_junit = []
for case in junit.iter('testcase'):
    key = (case.get('classname'), case.get('name'))
    ids = junit_lookup.get(key, [])
    if len(ids) != 1:
        unresolved_junit.append({'key': key, 'matches': ids})
    outcome = 'error' if case.find('error') is not None else 'failed' if case.find('failure') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
    junit_rows.append({'id': ids[0] if len(ids) == 1 else None, 'classname': key[0], 'name': key[1], 'outcome': outcome, 'time': case.get('time')})

duplicates = {node: dict(collections.Counter(row['when'] for row in values)) for node, values in phase_rows.items() if any(count != 1 for count in collections.Counter(row['when'] for row in values).values())}
phase_gaps = []
outcome_mismatches = []
for node in assigned:
    rows = phase_rows[node]
    phases = {row['when']: row for row in rows}
    expected = {'setup', 'teardown'}
    if phases.get('setup', {}).get('outcome') == 'passed':
        expected.add('call')
    if set(phases) != expected:
        phase_gaps.append({'id': node, 'actual': sorted(phases), 'expected': sorted(expected)})
    observed_junit = [row['outcome'] for row in junit_rows if row['id'] == node]
    expected_junit = 'error' if any(row['outcome'] == 'failed' and row['when'] != 'call' for row in rows) else 'failed' if any(row['outcome'] == 'failed' for row in rows) else 'skipped' if any(row['outcome'] == 'skipped' for row in rows) else 'passed'
    if observed_junit != [expected_junit]:
        outcome_mismatches.append({'id': node, 'observer': expected_junit, 'junit': observed_junit})

baseline = json.loads((ROOT / 'known-skip-source-comparison.json').read_text())
expected_skips = {row['id']: row for row in baseline['records'] if row['id'] in assigned}
actual_skips = [row for row in reports if row['outcome'] == 'skipped']
skip_comparisons = []
for row in actual_skips:
    known = expected_skips.get(row['id'])
    reason = ast.literal_eval(row['skip_reason'])
    actual = {'source': Path(reason[0]).relative_to(REPO).as_posix(), 'line': reason[1], 'reason': reason[2], 'phase': row['when']}
    matches = known is not None and all(actual[key] == known[key] for key in actual)
    skip_comparisons.append({'id': row['id'], **actual, 'known_skip_matches': matches})
source_checks = []
for row in baseline['records']:
    raw = (REPO / row['source']).read_bytes()
    source_checks.append({'id': row['id'], 'sha256_matches': hashlib.sha256(raw).hexdigest() == row['source_sha256'], 'line_text_matches': raw.decode().splitlines()[row['line'] - 1] == row['source_line_text']})

before = json.loads((OUT / 'source-before/capsule-verification.json').read_text())
after = json.loads((OUT / 'source-after/capsule-verification.json').read_text())
capsule_keys = ['head', 'status', 'manifest_sha256', 'sealed_files_verified', 'capsule_root', 'capsule_receipt_file_sha256', 'capsule_receipt', 'source_artifact_static_bindings_verified']
capsule_unchanged = all(before[key] == after[key] for key in capsule_keys)
raw = (OUT / 'pytest.log').read_text()
raw_summary = re.findall(r'\d+ passed[^\n]*|\d+ failed[^\n]*|\d+ error[^\n]*', raw)
summary_line = next((line for line in reversed(raw.splitlines()) if re.search(r'\d+ (?:passed|failed|skipped|errors?)', line) and ' in ' in line), '')
raw_counts = {name: 0 for name in ['passed', 'failed', 'skipped', 'error']}
for count, outcome in re.findall(r'(\d+) (passed|failed|skipped|errors?)', summary_line):
    raw_counts['error' if outcome.startswith('error') else outcome] = int(count)
junit_counts = collections.Counter(row['outcome'] for row in junit_rows)
duration_matches = re.findall(r'^([0-9.]+)s\s+(setup|call|teardown)\s+(.+)$', raw, re.MULTILINE)
duration_lookup = {row['pytest_nodeid']: row['id'] for row in collected}
duration_keys = [(duration_lookup.get(node), phase) for _, phase, node in duration_matches]
observer_keys = [(row['id'], row['when']) for row in reports]
duration_keys_valid = all(node is not None for node, _ in duration_keys)
unlisted_phases = sorted(set(observer_keys) - set(duration_keys))
unlisted_phase_explanation = any('durations < ' in line and 'hidden' in line for line in raw.splitlines())
mac_ids = set((ROOT / 'mac-ids.txt').read_text().splitlines())
mac_file_counts = dict(collections.Counter(node.split('::', 1)[0] for node in mac_ids))
junit_ids = [row['id'] for row in junit_rows]
checks = {
    'exact_334_assigned_collected': len(assigned) == len(collected_ids) == 334 and assigned == collected_ids,
    'unique_assigned_collected': len(assigned) == len(set(assigned)) and len(collected_ids) == len(set(collected_ids)),
    'exact_assigned_observer_ids': set(assigned) == set(phase_rows),
    'phase_gaps_absent': not phase_gaps,
    'duplicate_phases_absent': not duplicates,
    'exact_assigned_junit_ids': len(junit_ids) == len(assigned) and set(junit_ids) == set(assigned),
    'junit_ids_unique': len(junit_ids) == len(set(junit_ids)),
    'junit_identity_unambiguous': not unresolved_junit,
    'junit_observer_outcomes_equal': not outcome_mismatches,
    'actual_skips_exact_assigned_known_skips': {row['id'] for row in actual_skips} == set(expected_skips) and len(actual_skips) == len(expected_skips),
    'skip_source_reason_phase_equal': all(row['known_skip_matches'] for row in skip_comparisons),
    'all_10_known_skip_sources_unchanged': len(source_checks) == 10 and all(row['sha256_matches'] and row['line_text_matches'] for row in source_checks),
    'mac_127_excluded': len(mac_ids) == 127 and set(assigned).isdisjoint(mac_ids) and mac_file_counts == {'casepath-api/tests/test_cli_v1.py': 69, 'casepath-api/tests/test_local_data_root.py': 52, 'casepath-api/tests/test_journal_corpus_restart.py': 6},
    'no_deselection_in_raw_output': 'deselected' not in raw,
    'raw_terminal_counts_equal_junit': bool(summary_line) and raw_counts == {name: junit_counts.get(name, 0) for name in raw_counts},
    'raw_duration_ids_and_phases_valid': duration_keys_valid and set(duration_keys).issubset(set(observer_keys)) and len(duration_keys) == len(set(duration_keys)),
    'raw_phase_durations_complete_or_explicitly_hidden': not unlisted_phases or unlisted_phase_explanation,
    'single_attempt_marker_matches_result': started['candidate'] == result['candidate'] == SHA and started['started_epoch'] == result['started_epoch'] and started['retry_allowed'] is False,
    'source_after_clean_exact_head': after['head'] == result['after_head'] == SHA and after['status'] == result['after_status'] == '',
    'capsule_source_artifact_static_unchanged': capsule_unchanged,
}
record = {
    'candidate': SHA, 'shard': 3, 'checks': checks, 'all_checks_passed': all(checks.values()),
    'assigned_count': len(assigned), 'collected_count': len(collected_ids), 'junit_count': len(junit_rows),
    'reports_count': len(reports), 'phase_counts': dict(collections.Counter(row['when'] for row in reports)),
    'phase_outcome_counts': dict(collections.Counter(row['outcome'] for row in reports)),
    'junit_outcome_counts': dict(collections.Counter(row['outcome'] for row in junit_rows)),
    'failed_node_ids': sorted({row['id'] for row in reports if row['outcome'] == 'failed'}),
    'failed_phases': [row for row in reports if row['outcome'] == 'failed'],
    'skipped_node_ids': sorted({row['id'] for row in actual_skips}),
    'mac_excluded_file_counts': mac_file_counts,
    'skip_comparisons': skip_comparisons, 'all_known_skip_source_checks': source_checks,
    'phase_gaps': phase_gaps, 'duplicate_phases': duplicates, 'unresolved_junit': unresolved_junit,
    'outcome_mismatches': outcome_mismatches, 'missing_collected': sorted(set(assigned) - set(collected_ids)),
    'extra_collected': sorted(set(collected_ids) - set(assigned)),
    'missing_observer': sorted(set(assigned) - set(phase_rows)), 'extra_observer': sorted(set(phase_rows) - set(assigned)),
    'missing_junit': sorted(set(assigned) - set(junit_ids)), 'extra_junit': sorted(set(junit_ids) - set(assigned), key=str),
    'exit_code': result['exit_code'], 'started_epoch': result['started_epoch'], 'finished_epoch': result['finished_epoch'],
    'duration_seconds': result['duration_seconds'], 'raw_terminal_summary': raw_summary,
    'raw_terminal_summary_line': summary_line, 'raw_terminal_outcome_counts': raw_counts,
    'raw_duration_phase_count': len(duration_keys), 'raw_duration_unlisted_phases': unlisted_phases,
    'raw_unlisted_durations_explicitly_hidden': unlisted_phase_explanation,
    'capsule_receipt_file_sha256': after['capsule_receipt_file_sha256'],
    'evidence_hashes': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in ['ATTEMPT_STARTED.json', 'command.json', 'result.json', 'collected.json', 'reports.jsonl', 'junit.xml', 'pytest.log', 'source-before/capsule-verification.json', 'source-after/capsule-verification.json']},
}
with (OUT / 'reconciliation.json').open('x') as handle:
    handle.write(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: record[key] for key in ['all_checks_passed', 'assigned_count', 'collected_count', 'junit_count', 'reports_count', 'phase_counts', 'junit_outcome_counts', 'failed_node_ids', 'skipped_node_ids', 'exit_code', 'duration_seconds', 'raw_terminal_summary']}, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)

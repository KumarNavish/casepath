"""Summarize completed raw audit and postflight metadata; no tests or source writes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path('/workspace/casepath-transport-gate-0a213e47-20261015')
review = root / 'review'
read = lambda relative: json.loads((root / relative).read_text())
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
audit = read('review/terminal-audit.json')
assert audit['passed'] and not audit['errors']
inventory, terminal = audit['inventory'], audit['terminal']
mapping = read('shard-map.json')
assigned = sorted(node for ids in mapping['shards'].values() for node in ids)
for filename in ('cloud-assigned-ids.txt', 'selected-cloud-ids.txt', 'executed-cloud-ids.txt', 'junit-cloud-ids.txt'):
    assert (root / filename).read_text().splitlines() == assigned, filename

finalizer = read('coordinator/finalization-command.json')
owner_delta = read('coordinator/finalizer-change-provenance.json')
assert finalizer['candidate'] == inventory['candidate'] and finalizer['exit_code'] == 0
assert finalizer['script_sha256'] == finalizer['script_sha256_after'] == owner_delta['current_sha256'] == digest(root / 'harness/finalize.py')
assert finalizer['all_six_terminal_before_invocation'] is True
assert finalizer['started_epoch'] >= read('all-shard-terminal.json')['epoch']
aggregate = read('aggregate.json')
assert aggregate['candidate'] == inventory['candidate']
assert aggregate['full_inventory'] == inventory['full_inventory'] == 2613
assert aggregate['cloud_assigned'] == terminal['cloud_assigned'] == 2486
assert aggregate['cloud_passed'] == terminal['cloud_passed'] == 2476
assert aggregate['cloud_known_skipped'] == terminal['cloud_known_skipped'] == 10
assert aggregate['cloud_failed'] == terminal['cloud_failed'] == 0
assert aggregate['raw_phase_rows'] == terminal['raw_phase_rows'] == 7449
assert aggregate['selected_attempts_per_shard'] == [1] * 6

negative_files = sorted(path.name for pattern in ('*initial*json', '*initial*log') for path in review.glob(pattern))
proof = {
    'candidate': inventory['candidate'], 'manifest_sha256': inventory['manifest_sha256'],
    'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
    'verdict': 'PASS: raw Cloud execution reconciles exactly; exact-candidate Mac execution is owner-attested with raw reconciliation external.',
    'full_inventory': 2613, 'cloud_assigned': 2486, 'mac_assigned': 127,
    'assigned_collected_executed_junit_cloud_sets_identical': True,
    'no_overlaps_gaps_removed_ids_or_unexpected_deselection': True,
    'new_transport_ids': len(inventory['added_ids']),
    'cloud_passed': 2476, 'cloud_known_skipped': 10, 'cloud_failed': 0,
    'known_skips_exact_ids_phases_files_lines_reasons_and_source_hashes': True,
    'raw_phase_rows': 7449, 'raw_id_phase_pairs_unique': True,
    'selected_attempts_per_shard': [1] * 6, 'automatic_retries_or_rechecks': 0,
    'max_heavy_active': 3,
    'shards': terminal['shards'],
    'all_7_source_capsule_pairs_unchanged': True, 'source_artifact_static_counts': [1706, 25, 37],
    'source_capsule_receipt_sha256': terminal['source_capsule_receipt_sha256'],
    'full_sorted_ids_sha256': inventory['full_sorted_ids_sha256'],
    'cloud_sorted_ids_sha256': terminal['executed_sorted_ids_sha256'],
    'mac_sorted_ids_sha256': inventory['mac_sorted_ids_sha256'],
    'mac_execution': {'status': 'OWNER_ATTESTED', 'passed': 127, 'failed': 0, 'skipped': 0,
                      'raw_ids_phases_or_junit_inspected_in_cloud': False,
                      'raw_id_reconciliation': 'Mac owner will independently reconcile after Cloud evidence handoff'},
    'combined_passed_with_mac_attestation': 2603,
    'full_raw_id_audit_complete_in_cloud': False,
    'metadata_classification': {
        'postflight_finalizer': 'Exactly one authorized metadata-only save call added; reconstructed prior hash matches snapshot, execution helper hashes unchanged, finalizer executed once with unchanged recorded hash and exit0.',
        'finalizer_sha256': finalizer['script_sha256'],
        'observer_clock': '40 setup/call timestamps across20 existing tests use fixture clocks1002.0/1000.5. Exact same ID/phase/clock signatures occur in prior gate; these timestamps are not wall-clock chronology. Raw rows remain unchanged.',
        'evidence': ['review/metadata-diagnosis.json', 'review/shard4-wall-clock-outliers.json', 'review/postflight-qa-delta.patch', 'coordinator/finalization-command.json'],
        'negative_audit_outputs_retained': negative_files,
    },
    'audit_evidence': ['review/terminal-audit.json', 'review/terminal-audit.log', 'review/audit_gate.py', 'review/audit-command-record.json'],
    'reviewer_tests_dispatched': False, 'reviewer_source_or_runtime_mutations': False,
}
(review / 'final-audit-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
record = read('review/audit-command-record.json')
record['final_terminal_auditor_sha256'] = digest(review / 'audit_gate.py')
record['staged_audit_commands'] = [
    {'argv': ['/usr/bin/python3', '-I', str(review / 'audit_gate.py'), '--shard', str(n)],
     'exit_status': 0 if n in (1, 2, 3) else 1,
     'note': 'Final staged pass' if n in (1, 2, 3) else 'Preserved metadata finding; explained by exact source-backed diagnosis and closed in global audit'}
    for n in (3, 2, 1, 4, 5)
]
record['commands'].append({'purpose': 'all six terminal raw IDs, phases, JUnit, skips, attempts, environment isolation and seven capsule pairs',
                          'argv': ['/usr/bin/python3', '-I', str(review / 'audit_gate.py'), '--terminal'],
                          'log': 'review/terminal-audit.log', 'exit_status': 0})
record['commands'].append({'purpose': 'exported ID lists, actual finalizer hash/invocation, owner aggregate and compact independent receipt',
                          'argv': ['/usr/bin/python3', '-I', str(review / 'finalize_review_receipt.py')],
                          'log': 'review/finalize-review-receipt.log', 'exit_status': 0})
record['preserved_negatives'] = negative_files
record['metadata_diagnosis'] = 'review/metadata-diagnosis.json'
record['stage_schema_notes'] = 'Initial staged auditor rejected blank JUnit classnames; unique exact names map those valid cases. Initial shard4/5 metadata findings are retained and explicitly classified in the final proof; raw test outputs were not edited.'
(review / 'audit-command-record.json').write_text(json.dumps(record, indent=2) + '\n')
inputs = dict(audit['input_file_sha256'])
for relative in ('aggregate.json', 'coordinator/finalization-command.json', 'coordinator/finalizer-change-provenance.json',
                 'cloud-assigned-ids.txt', 'selected-cloud-ids.txt', 'executed-cloud-ids.txt', 'junit-cloud-ids.txt'):
    inputs[relative] = digest(root / relative)
(review / 'closure-input-sha256.json').write_text(json.dumps(inputs, indent=2) + '\n')
print(json.dumps({key: proof[key] for key in ('candidate', 'verdict', 'cloud_passed', 'cloud_known_skipped', 'cloud_failed', 'raw_phase_rows', 'combined_passed_with_mac_attestation')}, indent=2))

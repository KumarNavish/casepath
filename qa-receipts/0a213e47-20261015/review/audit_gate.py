"""Read-only independent raw gate audit. Never imports repository code or runs tests."""
import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/casepath-transport-gate-0a213e47-20261015')
OLD = Path('/workspace/casepath-map-first-gate-d0d0fa7f-20261015')
SHA = '0a213e471d70dbc63df2e0fcb3a62049ec5183aa'
MANIFEST = '8261e891c9403d486bdb60d1abe485ae56a6b6e556bb9b3125a3702d76e72331'
MAC_SHA = 'e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
MAC_FILES = {'casepath-api/tests/test_cli_v1.py': 69,
             'casepath-api/tests/test_local_data_root.py': 52,
             'casepath-api/tests/test_journal_corpus_restart.py': 6}
errors, inputs = [], {}


def check(value, label, detail=None):
    if not value:
        errors.append({'check': label, 'detail': detail})


def raw(path):
    data = path.read_bytes()
    inputs[str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)] = hashlib.sha256(data).hexdigest()
    return data


def read_json(path):
    return json.loads(raw(path))


def lines(path):
    return raw(path).decode().splitlines()


def digest_ids(ids):
    return hashlib.sha256(('\n'.join(sorted(ids)) + '\n').encode()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def skip_signature(row):
    location, line, reason = ast.literal_eval(row['skip_reason'])
    relative = row['id'].split('::', 1)[0]
    check(str(location).endswith('/' + relative), 'skip location matches exact test source path', row)
    return {'id': row['id'], 'when': row['when'], 'file': relative, 'line': line, 'reason': reason}


def source_proof(directory):
    proof = read_json(directory / 'capsule-verification.json')
    receipt_raw = raw(directory / 'CAPSULE_RECEIPT.json')
    receipt = json.loads(receipt_raw)
    check(hashlib.sha256(receipt_raw).hexdigest() == proof['capsule_receipt_file_sha256'], 'capsule snapshot file hash', str(directory))
    check(receipt == proof['capsule_receipt'], 'capsule snapshot content', str(directory))
    semantic = dict(receipt)
    seal = semantic.pop('receipt_sha256')
    check(hashlib.sha256(canonical(semantic)).hexdigest() == seal, 'capsule semantic seal', str(directory))
    check(proof['head'] == SHA and proof['status'] == '' and proof['normal_clone'] is True,
          'clean exact normal clone', str(directory))
    check(proof['manifest_sha256'] == MANIFEST and proof['sealed_files_verified'] == 1706,
          'manifest identity and 1706 source files', str(directory))
    check(proof['source_artifact_static_bindings_verified'] is True and proof['prepare_exit_code'] == 0,
          'prepared source/artifact/static bindings', str(directory))
    check(receipt['source_manifest_file_sha256'] == MANIFEST and receipt['source_file_count'] == 1706
          and receipt['artifact_file_count'] == 25 and receipt['static_file_count'] == 37,
          'capsule source/artifact/static counts', str(directory))
    return proof


def source_pair(path, started=None, finished=None):
    before, after = [source_proof(path / ('source-' + phase)) for phase in ('before', 'after')]
    check(before['capsule_receipt_file_sha256'] == after['capsule_receipt_file_sha256']
          and before['capsule_receipt'] == after['capsule_receipt'], 'source capsule unchanged', path.name)
    if started is not None:
        check(before['verified_epoch'] <= started <= finished <= after['verified_epoch'],
              'capsule verification brackets actual attempt', path.name)
    return before['capsule_receipt_file_sha256']


def inventory_audit():
    authorization = read_json(ROOT / 'EXECUTION_AUTHORIZATION.json')
    check(authorization['signal'] == 'FINAL_GATE_AUTHORIZED' and authorization['candidate'] == SHA
          and authorization['manifest_sha256'] == MANIFEST and authorization['max_heavy_active'] == 3,
          'explicit frozen gate authorization unchanged')
    binding = read_json(ROOT / 'review/canonical-source-binding.json')
    check(binding['candidate'] == SHA and binding['manifest_sha256'] == MANIFEST
          and binding['only_manifest_changed'] is True and binding['four_authored_files_match_independent_prior_review'] is True,
          'frozen canonical binds independent prior transport review')
    collected = [row['id'] for row in read_json(ROOT / 'inventory/collected.json')]
    check(len(collected) == len(set(collected)), 'fresh inventory unique')
    check(collected == lines(ROOT / 'collection-order-ids.txt'), 'fresh raw inventory equals collection-order IDs')
    check(sorted(collected) == lines(ROOT / 'collected-ids.txt'), 'fresh raw inventory equals full sorted IDs exactly')
    sm = read_json(ROOT / 'shard-map.json')
    check(sm['candidate'] == SHA and sm['manifest_sha256'] == MANIFEST, 'map exact frozen identity')
    shards = sm['shards']
    check(set(shards) == {str(i) for i in range(1, 7)}, 'six shards only')
    check(sm['counts'] == {shard: len(ids) for shard, ids in shards.items()}, 'map count metadata exact')
    assigned = [node for rows in shards.values() for node in rows]
    if (ROOT / 'cloud-assigned-ids.txt').exists():
        check(sorted(assigned) == lines(ROOT / 'cloud-assigned-ids.txt'), 'cloud assigned ID artifact exact')
    mac = lines(ROOT / 'mac-ids.txt')
    check(len(mac) == len(set(mac)) == 127 and digest_ids(mac) == MAC_SHA, 'fixed Mac 127 identity')
    check(dict(Counter(node.split('::')[0] for node in mac)) == MAC_FILES, 'fixed Mac per-file counts')
    check(len(assigned) == len(set(assigned)), 'all cloud assignments unique')
    check(not set(assigned) & set(mac), 'cloud/Mac disjoint')
    check(set(assigned) | set(mac) == set(collected), 'cloud plus Mac equals fresh full inventory')
    file_owner = defaultdict(set)
    for shard, ids in shards.items():
        for node in ids:
            file_owner[node.split('::')[0]].add(shard)
    check(all(len(owners) == 1 for owners in file_owner.values()), 'whole-file partitions')
    old_ids = set(lines(OLD / 'collected-ids.txt'))
    added, removed = sorted(set(collected) - old_ids), sorted(old_ids - set(collected))
    check(not removed, 'no baseline test IDs removed', removed)
    check(len(added) == 42 and all(node.startswith(('casepath-api/tests/test_autonomous_operations_v1.py::test_operation_transport_',
                                                 'casepath-api/tests/test_autonomous_operations_v1.py::test_real_operation_transport_')) for node in added),
          '42 new operation transport parametrizations only', added)
    old_known = {row['id']: skip_signature(row) for row in read_json(OLD / 'known-skips.json')}
    known = {row['id']: skip_signature(row) for row in read_json(ROOT / 'known-skips.json')}
    check(len(known) == 10 and known == old_known, 'known 10 skip IDs/phases/files/lines/reasons unchanged')
    check(set(known) <= set(assigned), 'known skips assigned to cloud')
    old_manifest_raw = raw(OLD / 'source-manifest.json')
    check(hashlib.sha256(old_manifest_raw).hexdigest() == 'cf3bfbe377fb6bd2a3dd4f44f3c3ec1c3fce8864ba19840b822abf30fa1bdd8f',
          'prior gate source manifest pinned')
    old_manifest = {row['path']: row['sha256'] for row in json.loads(old_manifest_raw)['files']}
    manifest_path = ROOT / 'source-manifest.json'
    if not manifest_path.exists():
        manifest_path = Path('/workspace/casepath-release-ae0-inventory/casepath/source-manifest.json')
    manifest_raw = raw(manifest_path)
    check(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST, 'current source manifest exact hash')
    source_manifest = json.loads(manifest_raw)
    fresh_manifest = {row['path']: row['sha256'] for row in source_manifest['files']}
    check(len(fresh_manifest) == source_manifest['file_count'] == 1706, 'exact source roster count')
    for file in {row['file'] for row in known.values()}:
        check(old_manifest[file] == fresh_manifest[file], 'known skip source byte-identical', file)
    inventory_result = read_json(ROOT / 'inventory/result.json')
    check(inventory_result['exit_code'] == 0 and inventory_result['candidate'] == inventory_result['after_head'] == SHA
          and inventory_result['after_status'] == '' and inventory_result['manifest_sha256'] == MANIFEST,
          'fresh collection successful at frozen source')
    check('--collect-only' in inventory_result['command'], 'inventory did not execute tests')
    predicted = None
    if sm.get('duration_source'):
        duration_path = Path(sm['duration_source'])
        durations_raw = raw(duration_path)
        check(hashlib.sha256(durations_raw).hexdigest() == sm['duration_source_sha256'], 'map duration source hash')
        durations = json.loads(durations_raw)
        predicted = {shard: sum(durations[file]['phase_seconds'] for file in set(node.split('::')[0] for node in ids)) for shard, ids in shards.items()}
        if 'estimated_phase_seconds' in sm:
            check(all(abs(predicted[s] - sm['estimated_phase_seconds'][s]) < 0.0001 for s in shards), 'map predicted durations independently summed')
        # One indivisible slow file may dominate a shard. Every other shard
        # must stay within the standard whole-file LPT imbalance envelope.
        largest_file = max(durations[file]['phase_seconds'] for file in file_owner)
        check(max(predicted.values()) - min(predicted.values()) <= largest_file + 0.0001,
              'whole-file duration balance envelope', predicted)
    inventory_capsule = source_proof(ROOT / 'inventory/source-before')['capsule_receipt_file_sha256']
    if (ROOT / 'inventory/source-after/capsule-verification.json').exists():
        check(source_pair(ROOT / 'inventory') == inventory_capsule, 'inventory before/after capsule identical')
    return {'candidate': SHA, 'manifest_sha256': MANIFEST, 'full_inventory': len(collected),
            'full_sorted_ids_sha256': digest_ids(collected), 'cloud_assigned': len(assigned),
            'cloud_sorted_ids_sha256': digest_ids(assigned), 'mac_assigned': len(mac),
            'mac_sorted_ids_sha256': digest_ids(mac), 'mac_per_file': MAC_FILES,
            'added_ids': added, 'removed_ids': removed, 'counts': {s: len(v) for s, v in shards.items()},
            'predicted_phase_seconds': predicted, 'known_skip_signatures': sorted(known.values(), key=lambda r: r['id']),
            'inventory_capsule_receipt_sha256': inventory_capsule,
            'mac_execution_status': 'pending unless an exact current-candidate receipt is separately supplied'}, shards, known


def match_junit(case, assigned):
    name, classname = case.get('name'), case.get('classname', '')
    suffix = '::' + name
    matches = []
    for node in assigned:
        if not node.endswith(suffix):
            continue
        parts = node[:-len(suffix)].split('::')
        expected = Path(parts[0]).stem + ('.' + '.'.join(parts[1:]) if len(parts) > 1 else '')
        if not classname or classname == expected or classname.endswith('.' + expected):
            matches.append(node)
    check(len(matches) == 1, 'JUnit unique node ID mapping', {'name': name, 'classname': classname, 'matches': matches})
    return matches[0] if len(matches) == 1 else None


def terminal_audit(shards, known, selected=None):
    metadata = read_json(ROOT / 'review/metadata-diagnosis.json')
    authorized_finalizer = read_json(ROOT / 'coordinator/finalizer-change-provenance.json')
    baseline_harness = read_json(ROOT / 'review/audit-harness-snapshot.json')
    baseline_harness.update(read_json(ROOT / 'review/additional-harness-snapshot.json'))
    for relative, expected_hash in baseline_harness.items():
        if relative.startswith('harness/'):
            observed_hash = hashlib.sha256(raw(ROOT / relative)).hexdigest()
            if relative == 'harness/finalize.py':
                allowed = metadata['postflight_qa_delta']
                check(expected_hash == allowed['before_sha256'] == authorized_finalizer['snapshot_sha256']
                      and observed_hash == allowed['current_sha256'] == authorized_finalizer['current_sha256']
                      and allowed['reconstructed_before_hash_matches_original_snapshot'] is True
                      and authorized_finalizer['affects_test_invocations_or_raw_outcomes'] is False,
                      'postflight-only finalizer metadata delta exactly proven and recorded', relative)
            else:
                check(observed_hash == expected_hash, 'frozen gate execution harness unchanged during audit', relative)
    summaries, all_executed, all_skips, all_receipts = [], [], {}, []
    isolated_environments = []
    for number in selected or range(1, 7):
        path = ROOT / ('shard' + str(number))
        assigned = shards[str(number)]
        check(lines(path / 'pytest-arguments.txt') == assigned, 'pytest args equal map order', number)
        if (path / 'assigned-ids.txt').exists():
            check(lines(path / 'assigned-ids.txt') == assigned, 'assigned IDs equal map order', number)
        collected = [row['id'] for row in read_json(path / 'collected.json')]
        check(collected == assigned, 'raw shard collection equals assigned order', number)
        reports = [json.loads(line) for line in lines(path / 'reports.jsonl')]
        by_id = defaultdict(list)
        for row in reports:
            by_id[row['id']].append(row)
            check(row['id'] in assigned, 'raw report ID assigned', row)
            check(row['outcome'] in {'passed', 'skipped'}, 'raw report outcome nonfailed', row)
        check(set(by_id) == set(assigned), 'all assigned IDs have raw reports', number)
        for node, rows in by_id.items():
            phases = [row['when'] for row in rows]
            check(len(phases) == len(set(phases)), 'unique raw phases per ID', {'shard': number, 'id': node, 'phases': phases})
            skipped = [row for row in rows if row['outcome'] == 'skipped']
            if skipped:
                check(len(skipped) == 1, 'one skip phase per ID', node)
                signature = skip_signature(skipped[0])
                check(signature == known.get(node), 'observed skip exact known signature', signature)
                check(set(phases) == ({'setup', 'teardown'} if signature['when'] == 'setup' else {'setup', 'call', 'teardown'}),
                      'skipped ID raw phase set', node)
                all_skips[node] = signature
            else:
                check(set(phases) == {'setup', 'call', 'teardown'} and all(row['outcome'] == 'passed' for row in rows),
                      'passed ID exact three successful phases', node)
        junit = ET.fromstring(raw(path / 'junit.xml'))
        cases = junit.findall('.//testcase')
        mapped, junit_skips = [], []
        for case in cases:
            node = match_junit(case, assigned)
            mapped.append(node)
            check(case.find('failure') is None and case.find('error') is None, 'JUnit no failure/error', {'shard': number, 'id': node})
            skipped = case.find('skipped')
            if skipped is not None:
                junit_skips.append(node)
                expected = all_skips.get(node, {}).get('reason', '').removeprefix('Skipped: ')
                check(skipped.get('message') == expected, 'JUnit skip reason equals raw known reason', node)
        check(len(mapped) == len(set(mapped)) == len(assigned) and set(mapped) == set(assigned), 'JUnit exact ID set', number)
        check(set(junit_skips) == {node for node in assigned if node in all_skips}, 'JUnit/raw exact skip ID set', number)
        suite_totals = {key: sum(int(suite.get(key, 0)) for suite in junit.iter('testsuite')) for key in ('tests', 'failures', 'errors', 'skipped')}
        check(suite_totals == {'tests': len(assigned), 'failures': 0, 'errors': 0, 'skipped': len(junit_skips)}, 'JUnit suite aggregate totals', number)
        latch = read_json(path / 'ATTEMPT_STARTED.json')
        result, command = read_json(path / 'result.json'), read_json(path / 'command.json')
        check(latch['candidate'] == SHA and latch.get('attempt_number', 1) == 1 and latch['retry_allowed'] is False,
              'single nonretry attempt latch', number)
        check(result['candidate'] == result['after_head'] == SHA and result['manifest_sha256'] == MANIFEST
              and result['after_status'] == '' and result['exit_code'] == 0, 'successful runner exact unchanged source', number)
        check(latch['command'] == command['command'] == result['command'] and latch['started_epoch'] == command['started_epoch'] == result['started_epoch'],
              'latch/command/result same attempt', number)
        check(result['started_epoch'] <= result['finished_epoch'] and abs(result['duration_seconds'] - result['finished_epoch'] + result['started_epoch']) < 0.001,
              'runner times consistent', number)
        outside = [row for row in reports if not result['started_epoch'] <= row['utc_epoch'] <= result['finished_epoch']]
        if outside:
            # Existing fixture patches the shared time.time read by the
            # observer. Preserve its exact prior-gate clock signatures; these
            # rows cannot substantiate wall-clock chronology.
            clock = metadata['observer_timestamp_limitation']
            prior_path = OLD / ('shard' + str(clock['prior_shard']))
            prior_result = read_json(prior_path / 'result.json')
            prior_rows = [json.loads(line) for line in lines(prior_path / 'reports.jsonl')]
            prior_outside = [row for row in prior_rows if row['id'].startswith(clock['file'] + '::')
                             and not prior_result['started_epoch'] <= row['utc_epoch'] <= prior_result['finished_epoch']]
            signature = lambda row: (row['id'], row['when'], row['utc_epoch'])
            check(number == 4 and len(outside) == clock['rows'] == 40
                  and sorted(map(signature, outside)) == sorted(map(signature, prior_outside))
                  and clock['fixture_source_matches_prior_gate'] is True and clock['observer_identical_to_prior'] is True,
                  'only exact source-proven prior fixture clock outliers; not wall-clock evidence', number)
        environment = result['env']
        check(environment['CASEPATH_SOURCE_COMMIT'] == SHA and environment['CASEPATH_MODEL_MODE'] == 'deterministic_reference'
              and all(environment[key] != '/tmp' for key in ('TMPDIR', 'TMP', 'TEMP')), 'sterile deterministic bounded temp environment', number)
        check(not any('TOKEN' in key or 'SECRET' in key or 'API_KEY' in key for key in environment), 'no credential bindings in test environment', number)
        check(environment['TMPDIR'] == environment['TMP'] == environment['TEMP'] == '/workspace/ot' + str(number)
              and environment['HOME'] == '/workspace/oh' + str(number), 'exact dedicated short shard HOME/TMP paths', number)
        isolated_environments.append(environment)
        all_receipts.append(source_pair(path, result['started_epoch'], result['finished_epoch']))
        all_executed.extend(by_id)
        summaries.append({'shard': number, 'assigned': len(assigned), 'raw_phase_rows': len(reports),
                          'passed': len(assigned) - len(junit_skips), 'skipped': len(junit_skips),
                          'runner_exit': result['exit_code'], 'attempts': 1, 'runner_seconds': result['duration_seconds']})
    if selected is not None:
        return {'scope': 'selected terminal shard raw evidence only', 'global_gate_closed': False,
                'shards': summaries, 'source_capsule_receipt_sha256': all_receipts[0]}
    assigned = [node for ids in shards.values() for node in ids]
    check(len(all_executed) == len(set(all_executed)) == len(assigned) and set(all_executed) == set(assigned), 'global executed/assigned exact disjoint union')
    check(set(all_skips) == set(known), 'exactly known 10 skip IDs observed')
    check(len(set(all_receipts)) == 1, 'same capsule receipt across shards')
    for key in ('HOME', 'TMPDIR', 'CASEPATH_DB_PATH', 'CASEPATH_ARTIFACT_REGISTRY_PATH', 'PYTHONPYCACHEPREFIX', 'UV_CACHE_DIR'):
        check(len({environment[key] for environment in isolated_environments}) == 6,
              'six independent environment paths', key)
    scheduler = [json.loads(line) for line in lines(ROOT / 'scheduler-events.jsonl')]
    starts, finishes = Counter(), Counter()
    active, peak = set(), 0
    for row in scheduler:
        number = row['shard']
        event = row.get('event', row.get('type'))
        if event == 'start':
            check(number not in active, 'scheduler no duplicate concurrent attempt', number)
            starts[number] += 1
            active.add(number)
        else:
            check(event == 'finish' and number in active and row['exit_code'] == row['source_after_exit_code'] == 0
                  and row['attempt_count'] == 1, 'scheduler valid successful first-attempt finish', row)
            finishes[number] += 1
            active.discard(number)
        check(set(row['active']) == active, 'scheduler active list exact', row)
        check(row['free_bytes'] >= 3 * 1024**3, 'scheduler retains required 3GiB headroom', row)
        peak = max(peak, len(active))
    check(starts == finishes == Counter({number: 1 for number in range(1, 7)}) and not active, 'scheduler exactly one terminal attempt per six shards')
    check(peak <= 3, 'maximum three heavy shards active')
    terminal = read_json(ROOT / 'all-shard-terminal.json')
    check(terminal['candidate'] == SHA and terminal['all_executed'] is True and terminal['all_green'] is True,
          'owner terminal status exact and successful')
    check({row['shard'] for row in terminal['results']} == set(range(1, 7)) and len(terminal['results']) == 6
          and all(row['exit_code'] == row['source_after_exit_code'] == 0 and row['attempt_count'] == 1 for row in terminal['results']),
          'all six terminal rows represent one successful source-verified attempt')
    inventory_result = read_json(ROOT / 'inventory/result.json')
    check(source_pair(ROOT / 'inventory', inventory_result['started_epoch'], inventory_result['finished_epoch']) == all_receipts[0],
          'inventory and six shards share unchanged capsule')
    mac_path = ROOT / 'coordinator/mac-attestation.json'
    mac = None
    if mac_path.exists():
        mac = read_json(mac_path)
        check(mac['candidate'] == SHA and mac['manifest_sha256'] == MANIFEST, 'Mac receipt exact candidate/manifest')
        check(mac['passed'] == 127 and mac['failed'] == mac['skipped'] == 0 and mac['exit_code'] == 0, 'Mac owner attests actual 127 successful')
        check(mac['partition'] == MAC_FILES and mac['source_file_count'] == 1706 and mac['source_clean_before_after'] is True,
              'Mac owner attests fixed source/file partition')
        check(mac['raw_mac_receipts_local_to_mac'] is True and mac['raw_mac_junit_or_phase_rows_inspected_in_cloud'] is False,
              'Mac raw receipt limitation explicit')
    return {'shards': summaries, 'cloud_assigned': len(assigned), 'cloud_passed': sum(row['passed'] for row in summaries),
            'cloud_known_skipped': len(all_skips), 'cloud_failed': 0 if not errors else None,
            'raw_phase_rows': sum(row['raw_phase_rows'] for row in summaries), 'peak_active_heavy': peak,
            'selected_attempts': dict(starts), 'executed_sorted_ids_sha256': digest_ids(all_executed),
            'source_capsule_receipt_sha256': all_receipts[0], 'mac_attestation_present': mac is not None,
            'mac_execution_status': 'current-candidate owner attestation; raw receipts may remain external' if mac else 'pending; no current-candidate receipt supplied',
            'combined_passed_with_mac_attestation': len(assigned) - len(all_skips) + 127 if mac and not errors else None,
            'combined_execution_green_with_mac_attestation': bool(mac) and not errors,
            'full_raw_id_audit_complete_in_cloud': False,
            'raw_mac_ids_phases_or_junit_inspected_by_this_reviewer': False,
            'mac_raw_id_reconciliation_status': 'Mac owner will independently reconcile after Cloud evidence handoff' if mac else 'pending',
            'observer_timestamp_limitation': metadata['observer_timestamp_limitation'],
            'authorized_postflight_qa_delta': metadata['postflight_qa_delta']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--terminal', action='store_true')
    parser.add_argument('--shard', type=int, choices=range(1, 7))
    args = parser.parse_args()
    stage = 'shard' + str(args.shard) if args.shard else 'terminal' if args.terminal else 'inventory'
    result = {'stage': stage, 'audit_utc': datetime.now(timezone.utc).isoformat(), 'read_only_audit': True,
              'tests_dispatched': False, 'source_or_runtime_mutated': False}
    try:
        inventory, shards, known = inventory_audit()
        result['inventory'] = inventory
        if args.terminal:
            result['terminal'] = terminal_audit(shards, known)
        elif args.shard:
            result['terminal_shard'] = terminal_audit(shards, known, [args.shard])
    except Exception as error:
        errors.append({'check': 'audit input/schema available and valid', 'detail': repr(error)})
    result.update(passed=not errors, errors=errors, input_file_sha256=inputs)
    output = ROOT / 'review' / (stage + '-audit.json')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'input_file_sha256'}, indent=2))
    raise SystemExit(0 if result['passed'] else 1)

import base64, hashlib, json, sys, time
from pathlib import Path
sys.path.insert(0, '/workspace/casepath-polish-gate-inventory-20261013/casepath-api')
from casepath_api.workspace_corpus import digest_value

root = Path('/workspace/casepath-reference-polish-default-generator-20261013')
path = root / 'native-default-generated.json'
started = time.monotonic()
data = json.loads(path.read_bytes())
previous_export = json.loads(Path('/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json').read_bytes())
prefix_count, event_checks = 0, 0
rows = []
for cid, saved in data['snapshots'].items():
    state = saved['state']
    start = saved['replay_start']
    assert state['outcome']['assessment_status'] == 'complete'
    assert start['contract'] == 'casepath.reference-replay-start/1.0.0'
    assert start['claim_id'] == cid and start['run_id'] == state['run_id']
    assert start['profile_id'] == 'synthetic-nine-v2'
    assert start['profile_sha256'] == data['profile_sha256'] == '18c2ff55eb39324fee225b2b44330079715d1de11234d2367a2ed172b59c0869'
    context = state['semantic_contexts'][state['run_id']]
    assert sorted(start['source_artifact_ids']) == sorted(s['artifact_id'] for s in context['sources'])
    assert len(set(start['source_artifact_ids'])) == len(start['source_artifact_ids'])
    all_prefixes = data['prefixes'][cid]
    assert len(all_prefixes) == state['revision'] + 1
    before = data['before_v1_snapshots'][cid]['state']
    assert all_prefixes[str(before['revision'])]['state'] == before
    opening = all_prefixes[str(start['from_seq'])]
    assert opening['state']['state_sha256'] == start['state_sha256']
    assert opening['state']['last_event_sha256'] == start['event_sha256']
    assert opening['state']['run_id'] == start['run_id'] and opening['state']['outcome'] is None
    assert opening['events'][-1]['kind'] == 'process.prepared'
    for seq in range(state['revision'] + 1):
        dto = all_prefixes[str(seq)]
        current = dto['state']
        assert dto['through_seq'] == current['revision'] == seq
        assert dto['replay_start'] == start
        assert dto['current_revision'] == state['revision']
        assert dto['current_state_sha256'] == state['state_sha256']
        assert current['state_sha256'] == digest_value({k: v for k, v in current.items() if k != 'state_sha256'})
        prior = None
        for number, event in enumerate(dto['events'], 1):
            assert event['sequence'] == event['seq'] == number
            assert event['previous_event_sha256'] == prior
            material = {k: v for k, v in event.items() if k not in {'event_sha256', 'resulting_state_sha256', 'seq', 'revision', 'state_sha256', 'timestamp'}}
            assert digest_value(material) == event['event_sha256']
            assert event['resulting_state_sha256'] == event['state_sha256']
            prior = event['event_sha256']
            event_checks += 1
        assert current['last_event_sha256'] == prior
        prefix_count += 1
    for descriptor in state['source_descriptors']:
        identity = cid + '/' + descriptor['artifact_id']
        raw = data['raw_sources'][identity]
        assert raw == previous_export['raw_sources'][identity]
        assert hashlib.sha256(base64.b64decode(raw)).hexdigest() == descriptor['sha256']
    rows.append({'claim_id': cid, 'revision': state['revision'], 'state_sha256': state['state_sha256'], 'replay_start': start, 'old_v1_state_preserved': True})
assert len(rows) == 9 and prefix_count == 393 and len(data['raw_sources']) == 57
result = {'commit': 'b7358d033baf86e885b52bb14e20f11aff88f0e4', 'generator_input_override_absent': True,
          'generator_source': 'Unmodified referenceFixture(true) extracted from the existing QA file; execFileSync used migrated 256MiB bound.',
          'output_bytes': path.stat().st_size, 'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'claims': 9, 'prefixes': prefix_count, 'event_hash_checks': event_checks, 'physical_sources': 57,
          'all_state_and_event_hashes_valid': True, 'all_replay_start_metadata_bound_to_actual_prepared_prefix': True,
          'old_v1_states_preserved_within_new_generated_journal': True, 'all_raw_source_bytes_match_prior_export': True,
          'prior_cross_export_failure': 'Both generators use real engine states but different claim order: prior exporter sorts profile IDs; default helper starts heating first. First mismatch at seq11 is compatible_knowledge count0 versus2; different valid journal hashes are expected. Original comparison failure and diagnostic retained. No generator rerun.',
          'validation_seconds': time.monotonic() - started, 'rows': rows, 'exit_code': 0}
(root / 'validated-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('output_bytes', 'claims', 'prefixes', 'event_hash_checks', 'physical_sources', 'validation_seconds', 'exit_code')}))

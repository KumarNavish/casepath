"""A deployment seed is only a candidate for native validation and fresh SQL proof."""
import base64
from copy import deepcopy
import json
import sqlite3

import pytest

from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError
from test_hosted_knowledge_warm_proof_v1 import native_proof_store


COMMIT = 'a' * 40


def material(store):
    with sqlite3.connect(store.path.parent / 'native.sqlite3') as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence')]
    sources = [{'sha256': path.name, 'content_base64': base64.b64encode(path.read_bytes()).decode('ascii')}
               for path in sorted((store.path.parent / 'autonomous-sources-v1').iterdir())]
    return rows, sources


def candidate(store):
    from casepath_api.hosted_read_seed_v1 import decode_seed, pack_seed
    rows, sources = material(store)
    raw = pack_seed(COMMIT, rows, sources)
    return decode_seed(raw, deployment_commit=COMMIT)


def pristine(store):
    return (not getattr(store, '_summary_cache', {}) and not store._extractions
            and not getattr(store, '_knowledge_byte_cache', None) and not store._source_store._cache
            and store._source_store._size == 0 and not getattr(store._source_store, '_knowledge_schema', None))


def test_valid_seed_replays_locally_then_one_fresh_atomic_proof_before_admission(native_proof_store, monkeypatch):
    server, store, knowledge = native_proof_store
    store._read_only = True
    native = AutonomousStore.open_read_only(store.path.parent / 'native.sqlite3')
    expected = AutonomousKnowledge(native, {}).learning_view()
    seed = candidate(store)
    original = deepcopy(seed)
    assert pristine(store)
    assert store.admit_read_seed(seed, deployment_commit=COMMIT) is True
    assert seed == original and len(server.requests) == 1
    assert not server.raw_journal and not server.raw_sources and server.open_streams == 0
    commands = [item.get('stmt', {}).get('sql', '') for item in server.requests[0]['requests']]
    assert commands[0] == 'BEGIN' and commands[-2:] == ['COMMIT', '']
    assert sum('casepath-journal-bytes-v1:set:' in sql for sql in commands) == 1
    assert sum('casepath-source-bytes-v1:set:' in sql for sql in commands) == 1
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Admitted unchanged seed replayed'))
    seed['journal_rows'][0]['created_at'] = 'caller-only change'
    seed['sources'].clear()
    server.reset()
    assert knowledge.learning_view() == expected
    assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources


@pytest.mark.parametrize('change', ['missing_source', 'extra_source', 'bad_chain', 'wrong_release'])
def test_bad_candidate_never_uses_raw_fallback_or_changes_actual_caches(native_proof_store, change):
    from casepath_api.hosted_read_seed_v1 import SeedError
    server, store, _ = native_proof_store
    store._read_only = True
    seed = candidate(store)
    if change == 'missing_source':
        seed['sources'].pop()
    elif change == 'extra_source':
        from hashlib import sha256
        raw = b'Unreferenced isolated fixture bytes.'
        seed['sources'].append({'sha256': sha256(raw).hexdigest(),
                                'content_base64': base64.b64encode(raw).decode()})
        seed['sources'].sort(key=lambda row: row['sha256'])
    elif change == 'bad_chain':
        seed['journal_rows'][0]['event_json'] = '{}'
    else:
        seed['deployment_commit'] = 'b' * 40
    with pytest.raises((SeedError, AutonomousStoreError)):
        store.admit_read_seed(seed, deployment_commit=COMMIT)
    assert pristine(store) and not server.requests


@pytest.mark.parametrize('column,value', [('created_at', 'changed'), ('sequence', 1.5)])
def test_confirmed_typed_journal_mismatch_discards_seed_without_actual_cache_admission(native_proof_store, column, value):
    server, store, _ = native_proof_store
    store._read_only = True
    seed = candidate(store)
    with sqlite3.connect(server.path) as db:
        db.execute('UPDATE claim_loop_events SET ' + column + '=?', (value,))
    assert store.admit_read_seed(seed, deployment_commit=COMMIT) is False
    assert pristine(store) and len(server.requests) == 1


@pytest.mark.parametrize('fault', ['malformed_root', 'transport'])
def test_unconfirmed_proof_never_falls_back_or_admits(native_proof_store, monkeypatch, fault):
    from casepath_api.hosted_sql_v1 import HostedStorageError
    server, store, _ = native_proof_store
    store._read_only = True
    seed = candidate(store)
    if fault == 'transport':
        server.fail_next('timeout')
    else:
        original = server._statement
        def malformed(db, statement):
            result = original(db, statement)
            if 'casepath-journal-bytes-v1:set:' in statement['sql']:
                names = [row['name'] for row in result['cols']]
                result['rows'][0][names.index('concat_bytes')] = server._value(0)
            return result
        monkeypatch.setattr(server, '_statement', malformed)
    with pytest.raises((HostedStorageError, AutonomousStoreError)):
        store.admit_read_seed(seed, deployment_commit=COMMIT)
    assert pristine(store) and len(server.requests) == 1


@pytest.mark.parametrize('raw', [b'{"contract":1,"contract":2}', b'{"sequence":1.0}', b'{"x":NaN}',
    b'{"x":9223372036854775808}', b'[]'])
def test_decoder_rejects_duplicate_keys_numbers_and_non_objects(raw):
    from casepath_api.hosted_read_seed_v1 import decode_seed, SeedError
    with pytest.raises(SeedError):
        decode_seed(raw, deployment_commit=COMMIT)


def test_decoder_preserves_event_json_and_rejects_bool_sequence_and_noncanonical_base64(native_proof_store):
    from casepath_api.hosted_read_seed_v1 import decode_seed, pack_seed, SeedError
    _, store, _ = native_proof_store
    rows, sources = material(store)
    raw = pack_seed(COMMIT, rows, sources)
    assert decode_seed(raw, deployment_commit=COMMIT)['journal_rows'] == rows
    for change in ('bool', 'base64', 'keys'):
        value = json.loads(raw)
        if change == 'bool':
            value['journal_rows'][0]['sequence'] = True
        elif change == 'base64':
            value['sources'][0]['content_base64'] += '\n'
        else:
            value['journal_rows'][0]['unknown_authority'] = 'omitted'
        with pytest.raises(SeedError):
            decode_seed(json.dumps(value).encode(), deployment_commit=COMMIT)


@pytest.mark.parametrize('change', ['content', 'extra_chunk', 'schema'])
def test_complete_source_chunk_and_schema_mismatch_never_admits_candidate(native_proof_store, change):
    server, store, _ = native_proof_store
    store._read_only = True
    seed = candidate(store)
    with sqlite3.connect(server.path) as db:
        digest = seed['sources'][0]['sha256']
        if change == 'content':
            db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
            db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0',
                       (b'Changed isolated bytes.', digest))
        elif change == 'extra_chunk':
            db.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', (digest, 99, b'extra'))
        else:
            db.execute('ALTER TABLE autonomous_source_chunks ADD COLUMN hidden_authority TEXT')
    assert store.admit_read_seed(seed, deployment_commit=COMMIT) is False
    assert pristine(store) and len(server.requests) == 1 and not server.raw_sources


def test_local_validation_precedes_final_proof_and_post_validation_hook_precedes_admission(native_proof_store, monkeypatch):
    from casepath_api.hosted_storage_v1 import HostedAutonomousStore
    server, store, _ = native_proof_store
    store._read_only = True
    seed = candidate(store)
    original = HostedAutonomousStore._validated_states
    def change_after_validation(stage, rows, **kwargs):
        states = original(stage, rows, **kwargs)
        rows[0]['created_at'] = 'changed after successful final proof'
        return states
    monkeypatch.setattr(HostedAutonomousStore, '_validated_states', change_after_validation)
    with pytest.raises(AutonomousStoreError, match='Certified journal bytes differ'):
        store.admit_read_seed(seed, deployment_commit=COMMIT)
    assert pristine(store) and len(server.requests) == 1


def test_admission_is_startup_only_and_existing_reads_still_verify_remote_mutation(native_proof_store):
    from casepath_api.hosted_read_seed_v1 import SeedError
    server, store, knowledge = native_proof_store
    seed = candidate(store)
    with pytest.raises(SeedError):
        store.admit_read_seed(seed, deployment_commit=COMMIT)
    store._read_only = True
    assert store.admit_read_seed(seed, deployment_commit=COMMIT)
    server.reset()
    with pytest.raises(SeedError):
        store.admit_read_seed(seed, deployment_commit=COMMIT)
    assert not server.requests
    with sqlite3.connect(server.path) as db:
        db.execute("UPDATE claim_loop_events SET created_at='invalid persisted mutation'")
    with pytest.raises(AutonomousStoreError):
        knowledge.learning_view()


@pytest.mark.parametrize('change', ['duplicate_row', 'duplicate_source', 'oversize', 'bad_hash', 'missing_column'])
def test_decoder_enforces_exact_rosters_and_size_bounds(native_proof_store, monkeypatch, change):
    from casepath_api import hosted_read_seed_v1 as seed_module
    _, store, _ = native_proof_store
    value = candidate(store)
    if change == 'duplicate_row':
        value['journal_rows'].append(value['journal_rows'][0])
    elif change == 'duplicate_source':
        value['sources'].append(value['sources'][0])
    elif change == 'bad_hash':
        value['sources'][0]['sha256'] = '0' * 64
    elif change == 'missing_column':
        del value['journal_rows'][0]['event_json']
    else:
        monkeypatch.setattr(seed_module, 'MAX_SEED_BYTES', 10)
    with pytest.raises(seed_module.SeedError):
        seed_module.decode_seed(json.dumps(value).encode(), deployment_commit=COMMIT)


def test_file_load_checks_checksum_release_regular_file_and_missing_fallback(native_proof_store, tmp_path):
    from hashlib import sha256
    from casepath_api.hosted_read_seed_v1 import load_seed, pack_seed, SeedError
    _, store, _ = native_proof_store
    assert load_seed(tmp_path / 'absent.json', deployment_commit=COMMIT, expected_sha256=None) is None
    rows, sources = material(store)
    raw = pack_seed(COMMIT, rows, sources)
    path = tmp_path / 'seed.json'
    path.write_bytes(raw)
    assert load_seed(path, deployment_commit=COMMIT, expected_sha256=sha256(raw).hexdigest()) == candidate(store)
    for commit, digest in ((COMMIT, None), (COMMIT, '0' * 64), ('b' * 40, sha256(raw).hexdigest())):
        with pytest.raises(SeedError):
            load_seed(path, deployment_commit=commit, expected_sha256=digest)
    link = tmp_path / 'link.json'
    link.symlink_to(path)
    with pytest.raises(OSError):
        load_seed(link, deployment_commit=COMMIT, expected_sha256=sha256(raw).hexdigest())
    import os
    fifo = tmp_path / 'fifo.json'
    os.mkfifo(fifo)
    with pytest.raises(SeedError):
        load_seed(fifo, deployment_commit=COMMIT, expected_sha256=sha256(raw).hexdigest())


def test_candidate_preserves_native_complete_row_byte_bound(native_proof_store):
    from casepath_api.hosted_read_seed_v1 import decode_seed, MAX_ROW_BYTES, SeedError
    _, store, _ = native_proof_store
    value = candidate(store)
    value['journal_rows'][0]['created_at'] = 'x' * (MAX_ROW_BYTES - 1024)
    with pytest.raises(SeedError):
        decode_seed(json.dumps(value).encode(), deployment_commit=COMMIT)

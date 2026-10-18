"""Independent bounded adversarial checks; synthetic native/HTTP fixtures only."""
import base64
import json
import sqlite3

import pytest

from casepath_api.autonomous_store_v1 import AutonomousStoreError
from casepath_api.hosted_read_seed_v1 import SeedError, decode_seed, pack_seed
from test_hosted_knowledge_warm_proof_v1 import native_proof_store

COMMIT = 'a' * 40


def seed_for(store):
    with sqlite3.connect(store.path.parent / 'native.sqlite3') as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence')]
    sources = [{'sha256': path.name, 'content_base64': base64.b64encode(path.read_bytes()).decode('ascii')}
               for path in sorted((store.path.parent / 'autonomous-sources-v1').iterdir())]
    return decode_seed(pack_seed(COMMIT, rows, sources), deployment_commit=COMMIT)


def cache_objects(store):
    return tuple({key: (type(value), id(value)) for key, value in vars(obj).items()}
                 for obj in (store, store._source_store))


def test_complete_valid_seed_with_duplicate_same_contract_key_is_rejected(native_proof_store):
    _, store, _ = native_proof_store
    value = seed_for(store)
    raw = json.dumps(value, separators=(',', ':')).encode()
    duplicate = b'{"contract":' + json.dumps(value['contract']).encode() + b',' + raw[1:]
    with pytest.raises(SeedError):
        decode_seed(duplicate, deployment_commit=COMMIT)


def test_noncanonical_base64_pad_bits_do_not_gain_admission(native_proof_store):
    _, store, _ = native_proof_store
    value = seed_for(store)
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    source = next(row for row in value['sources'] if row['content_base64'].endswith('='))
    encoded = source['content_base64']
    index = len(encoded) - (3 if encoded.endswith('==') else 2)
    mutated = encoded[:index] + alphabet[alphabet.index(encoded[index]) ^ 1] + encoded[index + 1:]
    assert base64.b64decode(mutated, validate=True) == base64.b64decode(encoded, validate=True)
    source['content_base64'] = mutated
    with pytest.raises(SeedError):
        decode_seed(json.dumps(value).encode(), deployment_commit=COMMIT)


def test_extra_chunk_rejects_seed_without_changing_any_live_cache_object(native_proof_store):
    server, store, _ = native_proof_store
    store._read_only = True
    value = seed_for(store)
    before = cache_objects(store)
    with sqlite3.connect(server.path) as db:
        digest = db.execute('SELECT sha256 FROM autonomous_source_chunks ORDER BY sha256 LIMIT 1').fetchone()[0]
        db.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', (digest, 999, b'extra'))
    assert store.admit_read_seed(value, deployment_commit=COMMIT) is False
    assert cache_objects(store) == before
    assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources


def test_malformed_typed_source_proof_does_not_change_live_cache_objects(native_proof_store, monkeypatch):
    server, store, _ = native_proof_store
    store._read_only = True
    value = seed_for(store)
    before = cache_objects(store)
    original = server._statement
    def malformed(db, statement):
        result = original(db, statement)
        if 'casepath-source-bytes-v1:set:' in statement['sql']:
            names = [column['name'] for column in result['cols']]
            result['rows'][0][names.index('valid_n')] = server._value(1.0)
        return result
    monkeypatch.setattr(server, '_statement', malformed)
    with pytest.raises(AutonomousStoreError):
        store.admit_read_seed(value, deployment_commit=COMMIT)
    assert cache_objects(store) == before
    assert len(server.requests) == 1 and not server.raw_journal and not server.raw_sources


def test_unknown_source_column_is_not_omitted_from_fresh_schema_proof(native_proof_store):
    server, store, _ = native_proof_store
    store._read_only = True
    value = seed_for(store)
    before = cache_objects(store)
    with sqlite3.connect(server.path) as db:
        db.execute('ALTER TABLE autonomous_source_chunks ADD COLUMN omitted_authority TEXT')
    assert store.admit_read_seed(value, deployment_commit=COMMIT) is False
    assert cache_objects(store) == before
    assert len(server.requests) == 1


def test_every_post_admission_read_still_rejects_changed_source_roster(native_proof_store):
    server, store, knowledge = native_proof_store
    store._read_only = True
    value = seed_for(store)
    assert store.admit_read_seed(value, deployment_commit=COMMIT) is True
    with sqlite3.connect(server.path) as db:
        digest = db.execute('SELECT sha256 FROM autonomous_source_chunks ORDER BY sha256 LIMIT 1').fetchone()[0]
        db.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', (digest, 999, b'extra'))
    server.reset()
    with pytest.raises(AutonomousStoreError):
        knowledge.learning_view()
    assert server.requests
    assert any('casepath-source-bytes-v1:set:' in entry.get('stmt', {}).get('sql', '')
               for entry in server.requests[0]['requests'])

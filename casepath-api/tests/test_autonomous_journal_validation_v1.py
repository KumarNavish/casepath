"""Normal and paid restart validation admits the exact autonomous namespace."""
import base64
from hashlib import sha256
import json
import sqlite3

import pytest

from casepath_api.autonomous_policy_v1 import initial_process, receipt
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.claim_loop_store import ClaimLoopStore
from casepath_api.validate_journal import JournalValidationError, validate_journal
from test_cli_v1 import _history_verifier_module


def append(store, state, kind, payload, key):
    return store.append(state['claim_id'], kind, payload, expected_revision=state['revision'],
                        expected_state_sha256=state['state_sha256'], idempotency_key=key)


@pytest.fixture
def saved(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    state = store.intake({'title': 'Read-only restart fixture', 'message': 'Inspect the supplied notice.', 'files': [{
        'file_name': 'notice.txt', 'media_type': 'text/plain',
        'content_base64': base64.b64encode(b'Original supporting notice for the restart fixture.').decode()}]}, 'intake.validator')
    state = append(store, state, 'work.started', {'run_id': 'autonomy.validator', 'policy_id': 'local/1'}, 'start.validator')
    graph, facts, obligations = initial_process(state['claim_id'], state['source_descriptors'][1:])
    state = append(store, state, 'process.prepared', {'graph': graph, 'facts': facts, 'obligations': obligations,
        'receipt': receipt(state, 'prepare', after_graph_sha256=graph['graph_sha256'])}, 'prepare.validator')
    acquired = store.acquire(state['claim_id'], state['source_descriptors'][1]['artifact_id'])
    state = append(store, state, 'sources.acquired', {'sources': [acquired]}, 'source.validator')
    state = append(store, state, 'work.context', {'workflow_id': 'autonomy.validator', 'context': {
        'claim_id': state['claim_id'], 'sources': state['acquired_sources']}}, 'context.validator')
    state = append(store, state, 'work.deferred', {'code': 'paused', 'reason': 'Pause fixture.'}, 'pause.validator')
    state = append(store, state, 'work.resumed', {'reason': 'Resume fixture.'}, 'resume.validator')
    state = append(store, state, 'work.deferred', {'code': 'model_unavailable', 'reason': 'No model is configured.'}, 'defer.validator')
    with sqlite3.connect(store.path) as connection:
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return store, state


def authority_hashes(store):
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in [store.path, *store.source_root.iterdir()]}


def test_both_restart_validators_accept_real_autonomous_bytes_without_initialization(saved, monkeypatch):
    store, state = saved
    before = authority_hashes(store)
    with sqlite3.connect(f'file:{store.path}?mode=ro', uri=True) as connection:
        schema = connection.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()

    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only validation invoked a writable constructor')

    monkeypatch.setattr(ClaimLoopStore, '__init__', forbidden)
    monkeypatch.setattr(AutonomousStore, '__init__', forbidden)
    result = validate_journal(store.path)
    readonly = AutonomousStore.open_read_only(store.path)
    assert readonly.get(state['claim_id']) == state
    assert result['event_count'] == state['revision'] == 8 and result['loop_count'] == 1
    verifier = _history_verifier_module()
    with sqlite3.connect(f'file:{store.path}?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        roster = verifier.validate_event_journal(connection)
        assert connection.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall() == schema
    assert len(roster) == state['revision']
    assert roster[-1]['event_sha256'] == state['last_event_sha256']
    assert authority_hashes(store) == before
    with pytest.raises(AutonomousStoreError, match='read-only'):
        append(readonly, state, 'work.phase', {'phase': 'forbidden', 'summary': 'Must not write.'}, 'forbidden.validator')
    with pytest.raises(AutonomousStoreError, match='read-only'):
        readonly.intake({'title': 'Must not write', 'message': 'A new message.'}, 'forbidden.intake')
    assert authority_hashes(store) == before


@pytest.mark.parametrize('fault', ['source_changed', 'source_missing', 'source_root_missing', 'event_changed'])
def test_semantic_validator_rejects_tampering_without_repairing_any_authority(saved, fault):
    store, state = saved
    artifact = store.source_root / state['source_descriptors'][1]['sha256']
    if fault == 'source_changed':
        artifact.write_bytes(b'Changed supporting content.')
    elif fault == 'source_missing':
        artifact.unlink()
    elif fault == 'source_root_missing':
        for path in store.source_root.iterdir():
            path.unlink()
        store.source_root.rmdir()
    else:
        with sqlite3.connect(store.path) as connection:
            event = json.loads(connection.execute('SELECT event_json FROM claim_loop_events WHERE sequence=8').fetchone()[0])
            event['payload']['reason'] = 'Unrecorded replacement.'
            connection.execute('UPDATE claim_loop_events SET event_json=? WHERE sequence=8', (json.dumps(event),))
    before = store.path.read_bytes()
    with pytest.raises(JournalValidationError, match='replay failed'):
        validate_journal(store.path)
    assert store.path.read_bytes() == before
    if fault == 'source_root_missing':
        assert not store.source_root.exists()
    elif fault == 'source_missing':
        assert not artifact.exists()
    elif fault == 'source_changed':
        assert artifact.read_bytes() == b'Changed supporting content.'


@pytest.mark.parametrize('session,loop', [
    ('foreign-session', 'autonomous.{claim}'),
    (SESSION_ID, 'foreign.{claim}'),
    (SESSION_ID, 'autonomous.'),
    ('casepath-workspace-local', 'autonomous.{claim}'),
])
def test_both_validators_reject_namespace_mixups(saved, session, loop):
    store, state = saved
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE claim_loop_events SET session_id=?,loop_id=?', (session, loop.format(claim=state['claim_id'])))
    with pytest.raises(JournalValidationError, match='namespace'):
        validate_journal(store.path)
    verifier = _history_verifier_module()
    with sqlite3.connect(f'file:{store.path}?mode=ro', uri=True) as connection:
        with pytest.raises(verifier.HistoryError):
            verifier.validate_event_journal(connection)


@pytest.mark.parametrize('fault', ['unknown_kind', 'wrong_parent_state', 'extra_generic_field'])
def test_history_validator_rejects_resealed_autonomous_contract_and_parent_changes(saved, fault):
    store, _ = saved
    verifier = _history_verifier_module()
    with sqlite3.connect(store.path) as connection:
        event = json.loads(connection.execute('SELECT event_json FROM claim_loop_events WHERE sequence=8').fetchone()[0])
        if fault == 'unknown_kind':
            event['kind'] = 'settlement.sent'
        elif fault == 'wrong_parent_state':
            event['expected_state_sha256'] = '0' * 64
        else:
            event['command'] = {'pretend_generic_authority': True}
        command = {key: event[key] for key in ('kind', 'payload', 'expected_revision', 'expected_state_sha256')}
        event['command_sha256'] = verifier.digest(verifier.canonical(command))
        event['event_sha256'] = verifier.digest(verifier.canonical({key: value for key, value in event.items()
                                                                    if key not in {'event_sha256', 'resulting_state_sha256'}}))
        connection.execute('UPDATE claim_loop_events SET command_sha256=?,event_sha256=?,event_json=? WHERE sequence=8',
                           (event['command_sha256'], event['event_sha256'], verifier.canonical(event).decode()))
    with sqlite3.connect(f'file:{store.path}?mode=ro', uri=True) as connection:
        with pytest.raises(verifier.HistoryError):
            verifier.validate_event_journal(connection)


def test_read_only_factory_and_validator_do_not_create_missing_paths(tmp_path):
    missing = tmp_path / 'missing' / 'claims.sqlite3'
    with pytest.raises(AutonomousStoreError, match='existing regular file'):
        AutonomousStore.open_read_only(missing)
    with pytest.raises(JournalValidationError, match='not readable'):
        validate_journal(missing)
    assert not missing.parent.exists()

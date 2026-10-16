"""Knowledge reads retain exact journal/source authority while avoiding replay work.

All claims, sources, model responses and Hrana streams are isolated deterministic
fixtures. No provider, production database, budget or corpus writes are involved.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import shutil
import sqlite3
from time import perf_counter

import httpx
import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge, DEFINITION_KEYS
from casepath_api.autonomous_policy_v1 import FAMILY_FLAGS
from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources, HostedStorageError
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
from hosted_hrana_fixture import MockHrana
from test_autonomous_controller_v1 import packet
from test_autonomous_knowledge_refinement_v1 import RecipeFixture, with_receipt


CLAIM_COUNT = 18


class CountedStore(AutonomousStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = {'get': 0, 'list': 0, 'validated_states': 0, 'knowledge_snapshot': 0, 'replay': 0}

    def get(self, *args, **kwargs):
        self.calls['get'] += 1
        return super().get(*args, **kwargs)

    def list(self, *args, **kwargs):
        self.calls['list'] += 1
        return super().list(*args, **kwargs)

    def validated_states(self):
        self.calls['validated_states'] += 1
        return super().validated_states()

    def knowledge_snapshot(self):
        self.calls['knowledge_snapshot'] += 1
        return super().knowledge_snapshot()

    def _replay(self, *args, **kwargs):
        self.calls['replay'] += 1
        return super()._replay(*args, **kwargs)


class SummaryOnlyAdapter:
    """The pre-existing custom store contract deliberately exposes summaries."""
    def __init__(self, store):
        self.store, self.list_calls, self.get_calls = store, 0, []

    def list(self):
        self.list_calls += 1
        return self.store.list_summaries()

    def get(self, claim_id):
        self.get_calls.append(claim_id)
        return self.store.get(claim_id)


def append(store, state, kind, payload, key):
    return store.append(state['claim_id'], kind, payload, expected_revision=state['revision'],
                        expected_state_sha256=state['state_sha256'], idempotency_key=key)


@pytest.fixture(scope='module')
def processed_roster(tmp_path_factory):
    root = tmp_path_factory.mktemp('knowledge-processed-roster')
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    store, model = AutonomousStore(root / 'claims.sqlite3'), RecipeFixture()
    controller = AutonomousController(store, policy, model)
    states = []
    try:
        for index in range(CLAIM_COUNT):
            incoming = packet() if index == 0 else with_receipt()
            incoming['title'] = f'Knowledge read fixture {index:02d}'
            incoming['message'] += f' Fixture claim {index:02d}.'
            for source in incoming['files']:
                raw = base64.b64decode(source['content_base64']) + f'\nFixture claim {index:02d}.'.encode()
                source['content_base64'] = base64.b64encode(raw).decode()
            state = controller.run(store.intake(incoming, f'knowledge.read.intake.{index:02d}')['claim_id'])
            assert state['outcome'], state.get('deferral')
            states.append(state)
        rejected = {'knowledge_id': 'knowledge_fixture_rejected', 'version': 1,
                    'qualification': {'status': 'quarantined', 'reason': 'Explicit isolated rejected candidate.'}}
        states[-1] = append(store, states[-1], 'knowledge.published', {'knowledge': rejected}, 'knowledge.read.rejected')
        assert len(model.calls) == 2 * CLAIM_COUNT
        assert [value['version'] for state in states for value in state['knowledge_published']
                if value['qualification']['status'] == 'qualified'] == [1, 2]
        return store.path, store.source_root, policy, sorted(states, key=lambda state: state['claim_id'])
    finally:
        controller.shutdown()


def copied_store(processed_roster, tmp_path, store_type=AutonomousStore):
    original, sources, policy, states = processed_roster
    destination = tmp_path / 'claims.sqlite3'
    with sqlite3.connect(original) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    shutil.copytree(sources, tmp_path / 'autonomous-sources-v1')
    return store_type(destination), policy, states


def test_authoritative_view_matches_summary_adapter_and_reduces_each_claim_only_once(processed_roster, tmp_path):
    store, policy, states = copied_store(processed_roster, tmp_path, CountedStore)
    legacy = SummaryOnlyAdapter(AutonomousStore(store.path))
    expected = AutonomousKnowledge(legacy, policy).view()
    assert legacy.list_calls == 1 and len(legacy.get_calls) == CLAIM_COUNT
    assert [row['version'] for row in expected['versions']] == [1, 2]
    parent, child = expected['versions']
    assert child['parent_definition_sha256'] == parent['qualification']['definition_sha256']
    assert child['parent_knowledge_sha256'] == parent['knowledge_sha256']
    assert len(expected['uses']) == CLAIM_COUNT - 1
    assert expected['quarantined'] == [
        value for state in states for value in state['knowledge_published']
        if value['qualification']['status'] == 'quarantined']
    knowledge = AutonomousKnowledge(store, policy)
    assert knowledge.view() == expected
    assert store.calls == {'get': 0, 'list': 0, 'validated_states': 0, 'knowledge_snapshot': 1, 'replay': CLAIM_COUNT}
    assert knowledge.view() == expected
    assert store.calls == {'get': 0, 'list': 0, 'validated_states': 0, 'knowledge_snapshot': 2, 'replay': CLAIM_COUNT}
    assert len(store.list_summaries()) == CLAIM_COUNT
    assert knowledge.view() == expected
    assert store.calls['replay'] == CLAIM_COUNT  # Queue and knowledge share validated reducer state.


def test_compatible_selects_from_the_supplied_validated_view_without_another_read(processed_roster, tmp_path, monkeypatch):
    store, policy, _ = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    view = knowledge.view()
    expected = {family: knowledge.compatible(family) for family in FAMILY_FLAGS}
    monkeypatch.setattr(knowledge, 'view', lambda: pytest.fail('compatible reread the accepted journal'))
    assert {family: knowledge.compatible(family, view=view) for family in FAMILY_FLAGS} == expected
    assert expected['lease_termination_dispute']['version'] == 2
    empty = {'versions': [], 'uses': [], 'quarantined': []}
    assert all(knowledge.compatible(family, view=empty) is None for family in FAMILY_FLAGS)


def test_learning_replay_joins_exact_events_titles_and_frozen_version_pins(processed_roster, tmp_path):
    store, policy, states = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    original = knowledge.view()
    result = knowledge.learning_view()
    assert {key: result[key] for key in original} == original
    replay = result['learning_replay']
    assert replay['contract'] == 'casepath.knowledge-learning-replay/1.0.0'
    actual = []
    for state in states:
        events = store.events(state['claim_id'])
        for event in events:
            if event['kind'] in {'knowledge.used', 'knowledge.published'}:
                actual.append((state, event))
    assert len(replay['events']) == len(actual)
    projected = {event['event_id']: event for event in replay['events']}
    for state, recorded in actual:
        event = projected[recorded['event_sha256']]
        receipt = recorded['payload']['knowledge']
        assert event['at'] == recorded['created_at']
        assert event['sequence'] == recorded['sequence']
        assert event['command_sha256'] == recorded['command_sha256']
        assert event['idempotency_key'] == recorded['idempotency_key']
        assert event['claim_id'] == state['claim_id'] and event['claim_title'] == state['title']
        assert event['knowledge_id'] == receipt['knowledge_id'] and event['version'] == receipt['version']
        assert 'graph' not in event and 'facts' not in event and 'source_evidence' not in event
        if recorded['kind'] == 'knowledge.used':
            pin = next(pin for pin in state['semantic_contexts'][receipt['workflow_id']]['compatible_knowledge']
                       if pin['knowledge_id'] == receipt['knowledge_id'] and pin['version'] == receipt['version'])
            assert event['pin_status'] == 'exact' and event['knowledge_sha256'] == pin['knowledge_sha256']
            assert event['definition_sha256'] == receipt['definition_sha256']
        elif receipt['qualification']['status'] == 'qualified':
            assert event['source_claim_title'] == next(row['title'] for row in states if row['claim_id'] == receipt['source_claim_id'])
            assert event['qualification'] == receipt['qualification']
            assert len(event['qualification']['checks']) == 7
            assert event['qualification']['regression_cases'] == 243
        else:
            assert result['quarantined'][event['quarantine_index']] == receipt
            assert event['projection_status'] == 'quarantined'
    uses = [event['payload']['knowledge'] for _, event in actual if event['kind'] == 'knowledge.used']
    assert replay['totals'] == {'recorded_uses': len(uses), 'receiving_claims': CLAIM_COUNT - 1,
                                'avoided_rule_compilations': sum(use['avoided_rule_compilations'] for use in uses),
                                'avoided_rule_compilations_unknown': 0}
    assert replay['journal_heads'] == [{'claim_id': state['claim_id'], 'revision': state['revision'],
                                        'event_sha256': state['last_event_sha256'], 'state_sha256': state['state_sha256']}
                                       for state in states]
    child = next(event for event in replay['events'] if event['kind'] == 'knowledge.published' and event['version'] == 2)
    assert child['added_document_types'] == ['proof_of_receipt']
    assert child['definition_diff']['changed_definition_fields'] == ['evidence_recipes']
    assert child['definition_diff']['nodes']['before_count'] == child['definition_diff']['nodes']['after_count']
    assert child['definition_diff']['nodes']['added'] == child['definition_diff']['nodes']['removed'] == []


@pytest.mark.parametrize('mutation', ['missing_events', 'missing_pin', 'different_pin', 'different_definition'])
def test_learning_replay_preserves_unknown_time_or_pin_without_latest_fallback(processed_roster, mutation):
    _, _, policy, original = processed_roster
    states = deepcopy(original)
    selected = next(state for state in states if state['knowledge_uses'])
    selected_id = selected['claim_id']
    if mutation == 'missing_events':
        selected.pop('events')
    elif mutation == 'missing_pin':
        selected.pop('semantic_contexts')
    elif mutation == 'different_pin':
        for context in selected['semantic_contexts'].values():
            for pin in context['compatible_knowledge']:
                pin['knowledge_sha256'] = '0' * 64
    else:
        selected['knowledge_uses'][0]['definition_sha256'] = '0' * 64

    class States:
        def validated_states(self):
            return deepcopy(states)

    result = AutonomousKnowledge(States(), policy).learning_view()
    event = next(row for row in result['learning_replay']['events'] if row['kind'] == 'knowledge.used' and row['claim_id'] == selected_id)
    if mutation == 'missing_events':
        assert event['at'] is None and event['event_id'] is None and event['sequence'] is None
        assert result['learning_replay']['events'][-1] == event
    else:
        assert event['pin_status'] == 'unavailable' and event['knowledge_sha256'] is None
    assert result['uses'] == [{**value, 'claim_id': state['claim_id']} for state in states for value in state['knowledge_uses']]


def test_compact_knowledge_snapshot_copies_less_and_derived_cache_still_validates_every_read(processed_roster, tmp_path, monkeypatch):
    store, policy, _ = copied_store(processed_roster, tmp_path, CountedStore)
    full = store.validated_states()
    snapshot = store.knowledge_snapshot()
    assert len(json.dumps(snapshot)) < len(json.dumps(full)) / 4
    assert all('graph' not in state and 'acquired_sources' not in state and 'message' not in state for state in snapshot)
    snapshot[0]['events'].clear()
    snapshot[0]['knowledge_uses'].clear()
    assert store.validated_states() == full
    knowledge = AutonomousKnowledge(store, policy)
    expected = knowledge.learning_view()
    # A warm cache may skip derived work, but never the fresh authority read.
    monkeypatch.setattr(knowledge, '_project', lambda *args: pytest.fail('Repeated unchanged projection work'))
    before = store.calls['knowledge_snapshot']
    returned = knowledge.learning_view()
    assert store.calls['knowledge_snapshot'] == before + 1
    returned['learning_replay']['events'].clear()
    assert knowledge.learning_view() == expected
    source = store.source_root / full[0]['source_descriptors'][0]['sha256']
    source.write_bytes(b'A changed isolated original message.')
    with pytest.raises(AutonomousStoreError, match='source bytes differ'):
        knowledge.learning_view()


def test_learning_replay_keeps_unusual_recorded_use_identities_unresolved():
    uses = [{'knowledge_id': ['recorded-as-list'], 'version': 1, 'workflow_id': {}},
            {'knowledge_id': 'recorded.unknown', 'version': {'recorded': 1}, 'avoided_rule_compilations': True}]

    class States:
        def validated_states(self):
            return [{'claim_id': 'isolated.unknown', 'knowledge_published': [], 'knowledge_uses': deepcopy(uses)}]

    knowledge = AutonomousKnowledge(States(), {})
    original = {'versions': [], 'uses': [{**use, 'claim_id': 'isolated.unknown'} for use in uses], 'quarantined': []}
    assert knowledge.view() == original
    replay = knowledge.learning_view()['learning_replay']
    assert all(row['pin_status'] == 'unavailable' and row['knowledge_sha256'] is None and row['at'] is None for row in replay['events'])
    assert replay['totals'] == {'recorded_uses': 2, 'receiving_claims': 1,
                                'avoided_rule_compilations': 0, 'avoided_rule_compilations_unknown': 2}


def test_learning_endpoint_is_additive_read_only_and_preserves_native_pin_fields(processed_roster, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from casepath_api.autonomous_api_v1 import create_autonomous_router

    store, policy, _ = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    original = knowledge.view()
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: SimpleNamespace(knowledge=knowledge)))
    before = store.path.read_bytes()
    monkeypatch.setattr(store, 'append', lambda *a, **k: pytest.fail('Knowledge endpoint attempted an event write'))
    monkeypatch.setattr(store, '_publish', lambda *a, **k: pytest.fail('Knowledge endpoint attempted a source write'))
    with TestClient(app) as client:
        response = client.get('/api/claim-loops/v1/autonomous/knowledge')
        assert response.status_code == 200, response.text
        result = response.json()
        assert {key: result[key] for key in original} == original
        assert result['learning_replay']['totals']['recorded_uses'] == len(original['uses'])
        for expected, version in zip(original['versions'], result['versions']):
            assert {key: version[key] for key in ('knowledge_id', 'version', 'knowledge_sha256', 'qualification')} == {
                key: expected[key] for key in ('knowledge_id', 'version', 'knowledge_sha256', 'qualification')}
    assert store.path.read_bytes() == before


@pytest.mark.parametrize('mutation', ['conflicting_definition', 'parent_identity'])
def test_full_state_and_summary_adapters_preserve_immutable_quarantine_rules(processed_roster, mutation):
    _, _, policy, original_states = processed_roster
    states = deepcopy(original_states)
    versions = sorted([value for state in states for value in state['knowledge_published']
                       if value['qualification']['status'] == 'qualified'], key=lambda value: value['version'])
    if mutation == 'conflicting_definition':
        corrupt = deepcopy(versions[0])
        corrupt['evidence_recipes'].clear()
        corrupt['qualification']['definition_sha256'] = digest_value({key: corrupt[key] for key in DEFINITION_KEYS})
        states.append({'claim_id': 'fixture.conflicting.definition', 'knowledge_published': [corrupt], 'knowledge_uses': []})
    else:
        corrupt = versions[1]
        corrupt['parent_knowledge_sha256'] = '0' * 64
    corrupt['knowledge_sha256'] = digest_value({key: value for key, value in corrupt.items() if key != 'knowledge_sha256'})

    class FullStates:
        def validated_states(self):
            return deepcopy(states)

    class Summaries:
        def __init__(self):
            self.get_calls = []

        def list(self):
            return [{'claim_id': state['claim_id']} for state in states]

        def get(self, claim_id):
            self.get_calls.append(claim_id)
            return deepcopy(next(state for state in states if state['claim_id'] == claim_id))

    summaries = Summaries()
    fast = AutonomousKnowledge(FullStates(), policy).view()
    assert fast == AutonomousKnowledge(summaries, policy).view()
    assert len(summaries.get_calls) == len(states)
    reasons = [value['qualification']['reason'] for value in fast['quarantined']]
    assert 'knowledge parent lineage differs' in reasons
    if mutation == 'conflicting_definition':
        assert fast['versions'] == []
        assert 'knowledge version has conflicting immutable definitions' in reasons
    else:
        assert [value['version'] for value in fast['versions']] == [1]
    assert fast['uses'] == [{**value, 'claim_id': state['claim_id']} for state in states for value in state['knowledge_uses']]


def test_new_accepted_head_is_observed_by_a_warm_knowledge_read(processed_roster, tmp_path):
    store, policy, _ = copied_store(processed_roster, tmp_path, CountedStore)
    knowledge = AutonomousKnowledge(store, policy)
    before = knowledge.view()
    writer = AutonomousStore(store.path)
    state = writer.list()[-1]
    new_use = {'knowledge_id': before['versions'][-1]['knowledge_id'], 'version': 2,
               'workflow_id': 'fixture.fresh.head'}
    advanced = append(writer, state, 'knowledge.used', {'knowledge': new_use}, 'knowledge.read.fresh.head')
    after = knowledge.view()
    assert after['versions'] == before['versions'] and after['quarantined'] == before['quarantined']
    assert after['uses'] == before['uses'] + [{**new_use, 'claim_id': state['claim_id']}]
    assert store.calls['replay'] == CLAIM_COUNT + 1
    assert next(value for value in store.validated_states() if value['claim_id'] == state['claim_id']) == advanced


@pytest.mark.parametrize('column', ['event_json', 'created_at'])
def test_earlier_row_tampering_is_rejected_with_an_unchanged_head(processed_roster, tmp_path, column):
    store, policy, _ = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    knowledge.view()  # Warm the exact-row reducer cache.
    state = store.validated_states()[0]
    with sqlite3.connect(store.path) as db:
        head = db.execute('SELECT event_sha256 FROM claim_loop_events WHERE loop_id=? ORDER BY sequence DESC LIMIT 1',
                          ('autonomous.' + state['claim_id'],)).fetchone()[0]
        if column == 'event_json':
            event = json.loads(db.execute('SELECT event_json FROM claim_loop_events WHERE loop_id=? AND sequence=1',
                                        ('autonomous.' + state['claim_id'],)).fetchone()[0])
            event['payload']['title'] = 'An unaccepted replacement title.'
            db.execute('UPDATE claim_loop_events SET event_json=? WHERE loop_id=? AND sequence=1',
                       (json.dumps(event), 'autonomous.' + state['claim_id']))
        else:
            db.execute("UPDATE claim_loop_events SET created_at='2000-01-01T00:00:00Z' WHERE loop_id=? AND sequence=1",
                       ('autonomous.' + state['claim_id'],))
        assert db.execute('SELECT event_sha256 FROM claim_loop_events WHERE loop_id=? ORDER BY sequence DESC LIMIT 1',
                          ('autonomous.' + state['claim_id'],)).fetchone()[0] == head
    with pytest.raises(AutonomousStoreError, match='journal event identity or hash differs'):
        knowledge.view()


@pytest.mark.parametrize('mutation', ['changed', 'missing'])
@pytest.mark.parametrize('read', ['knowledge', 'states', 'summaries'])
def test_warm_projections_revalidate_original_source_bytes(processed_roster, tmp_path, mutation, read):
    store, policy, _ = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    knowledge.view()
    state = store.validated_states()[0]
    source = store.source_root / state['source_descriptors'][1]['sha256']
    if mutation == 'changed':
        source.write_bytes(b'Changed original supporting evidence.')
    else:
        source.unlink()
    operation = {'knowledge': knowledge.view, 'states': store.validated_states, 'summaries': store.list_summaries}[read]
    with pytest.raises(AutonomousStoreError, match='source bytes'):
        operation()


def test_returned_full_states_and_knowledge_cannot_mutate_shared_cached_authority(processed_roster, tmp_path):
    store, policy, expected = copied_store(processed_roster, tmp_path)
    assert store.validated_states() == expected
    states = store.validated_states()
    states[0]['source_descriptors'][0]['file_name'] = 'replacement.txt'
    states[0]['events'].clear()
    states[0]['graph']['conditions'].clear()
    next(state for state in states if state['knowledge_published'])['knowledge_published'][0]['qualification']['status'] = 'corrupt'
    assert store.validated_states() == expected
    knowledge = AutonomousKnowledge(store, policy)
    original = deepcopy(knowledge.view())
    returned = knowledge.view()
    returned['versions'][0]['graph']['nodes'].clear()
    returned['uses'][0]['version'] = 999
    returned['quarantined'][0]['qualification']['reason'] = 'An unaccepted replacement.'
    assert knowledge.view() == original
    assert store.validated_states() == expected


@pytest.mark.parametrize('mutation', ['claim_deleted', 'head_deleted', 'later_sequence_deleted'])
def test_warm_reads_reject_missing_accepted_claims_or_events(processed_roster, tmp_path, mutation):
    store, policy, _ = copied_store(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    knowledge.view()
    state = store.validated_states()[0]
    with sqlite3.connect(store.path) as db:
        if mutation == 'claim_deleted':
            db.execute('DELETE FROM claim_loop_events WHERE loop_id=?', ('autonomous.' + state['claim_id'],))
        else:
            sequence = state['revision'] if mutation == 'head_deleted' else state['revision'] - 2
            db.execute('DELETE FROM claim_loop_events WHERE loop_id=? AND sequence=?',
                       ('autonomous.' + state['claim_id'], sequence))
    with pytest.raises(AutonomousStoreError, match='disappeared|regressed|journal event identity or hash differs'):
        knowledge.view()


def test_controller_reads_one_view_for_all_families_before_interpretation(processed_roster, tmp_path):
    store, policy, _ = copied_store(processed_roster, tmp_path)

    class CountingKnowledge(AutonomousKnowledge):
        def __init__(self):
            super().__init__(store, policy)
            self.views, self.compatible_calls = [], []

        def view(self):
            value = super().view()
            self.views.append(value)
            return value

        def compatible(self, family, *, view=None):
            self.compatible_calls.append((family, view))
            return super().compatible(family, view=view)

    knowledge = CountingKnowledge()

    class InspectingModel(RecipeFixture):
        def interpret(self, context, identity):
            assert len(knowledge.views) == 1
            assert [family for family, _ in knowledge.compatible_calls] == list(FAMILY_FLAGS)
            assert all(view is knowledge.views[0] for _, view in knowledge.compatible_calls)
            assert context['compatible_knowledge'][0]['version'] == 2
            return super().interpret(context, identity)

    model = InspectingModel()
    controller = AutonomousController(store, policy, model)
    controller.knowledge = knowledge
    try:
        state = controller.run(store.intake(with_receipt(), 'knowledge.read.controller')['claim_id'])
        assert state['outcome'], state.get('deferral')
        assert state['knowledge_uses'][0]['version'] == 2
        assert len(model.calls) == 2
        assert len(knowledge.compatible_calls) == len(FAMILY_FLAGS)
        assert len(knowledge.views) >= 2  # The later pin/qualification lookup remains fresh.
    finally:
        controller.shutdown()


class CountMockHrana(MockHrana):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_bytes, self.journal_pages = [], []

    def _statement(self, connection, stmt):
        result = super()._statement(connection, stmt)
        names = [column['name'] for column in result['cols']]
        if 'event_json' in names:
            offset = names.index('event_json')
            raw_bytes = sum(len(row[offset].get('value', '').encode()) for row in result['rows'])
            self.journal_pages.append((len(result['rows']), raw_bytes))
        return result

    def handle(self, request):
        response = super().handle(request)
        self.response_bytes.append(len(response.content))
        return response

    def reset_counts(self):
        self.requests.clear()
        self.response_bytes.clear()
        self.journal_pages.clear()


def hosted_copy(processed_roster, tmp_path):
    original, source_root, policy, states = processed_roster
    server = CountMockHrana(tmp_path / 'hosted.sqlite3')
    journal = HostedJournal(tmp_path / 'unused-hosted-placeholder', server.connection)
    # Copy exact journal cells and original bytes with fixture-only local SQL.
    with sqlite3.connect(original) as source, sqlite3.connect(server.path) as target:
        rows = source.execute('SELECT * FROM claim_loop_events WHERE session_id=?', (SESSION_ID,)).fetchall()
        target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', rows)
        for path in source_root.iterdir():
            raw = path.read_bytes()
            assert sha256(raw).hexdigest() == path.name
            target.executemany('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', [
                (path.name, index, raw[offset:offset + HostedSources.CHUNK_BYTES])
                for index, offset in enumerate(range(0, len(raw), HostedSources.CHUNK_BYTES))])
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(server.connection))
    return server, store, policy, states


def statements(requests):
    for request in requests:
        for operation in request['requests']:
            if operation['type'] == 'execute':
                yield operation['stmt']['sql']
            elif operation['type'] == 'batch':
                yield from (step['stmt']['sql'] for step in operation['batch']['steps'])
            elif operation['type'] == 'sequence':
                yield operation['sql']


def test_hosted_18_claim_cold_and_warm_views_use_bounded_read_only_pages(processed_roster, tmp_path, monkeypatch):
    server, store, policy, states = hosted_copy(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    expected = AutonomousKnowledge(SummaryOnlyAdapter(AutonomousStore(processed_roster[0])), policy).view()
    replays = []
    original_replay = store._replay

    def counted_replay(rows, **kwargs):
        replays.append(len(rows))
        return original_replay(rows, **kwargs)

    def forbidden_provider(*args, **kwargs):
        pytest.fail('A knowledge projection attempted real provider/network dispatch')

    monkeypatch.setattr(store, '_replay', counted_replay)
    monkeypatch.setattr(store, 'get', lambda *a, **k: pytest.fail('Knowledge performed per-claim get'))
    monkeypatch.setattr(store, 'list', lambda *a, **k: pytest.fail('Knowledge requested reconstructed list'))
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', forbidden_provider)
    measurements = []
    try:
        for temperature in ('cold', 'warm'):
            server.reset_counts()
            replay_before = len(replays)
            started = perf_counter()
            assert knowledge.view() == expected
            elapsed = perf_counter() - started
            assert len(replays) == CLAIM_COUNT
            replay_count = len(replays) - replay_before
            assert replay_count == (CLAIM_COUNT if temperature == 'cold' else 0)
            sql = list(statements(server.requests))
            assert all(statement.strip().split()[0].upper() in {'SELECT', 'BEGIN', 'COMMIT', 'ROLLBACK', 'PRAGMA'}
                       for statement in sql)
            assert any(statement.strip().upper() == 'BEGIN' for statement in sql)
            assert all('IMMEDIATE' not in statement.upper() for statement in sql)
            assert len(server.journal_pages) > 1  # This roster actually exercises journal pagination.
            assert sum(count for count, _ in server.journal_pages) == sum(state['revision'] for state in states)
            assert max(count for count, _ in server.journal_pages) <= store.KNOWLEDGE_PAGE_ROWS
            assert max(size for _, size in server.journal_pages) <= 4 * 1024 * 1024
            assert max(server.response_bytes) <= 9 * 1024 * 1024
            assert len(server.requests) <= 48
            assert server.open_streams == 0
            measurements.append({'temperature': temperature, 'http_requests': len(server.requests),
                                 'journal_pages': len(server.journal_pages),
                                 'largest_response_bytes': max(server.response_bytes),
                                 'total_response_bytes': sum(server.response_bytes),
                                 'source_pages': sum('FROM autonomous_source_chunks' in statement for statement in sql),
                                 'mock_elapsed_seconds': round(elapsed, 6), 'replayed_claims': replay_count})
        assert measurements[1]['http_requests'] < measurements[0]['http_requests']
        # Preserve the actual old full-list-then-get path for a measured baseline.
        legacy_store = HostedAutonomousStore(store.path, journal=store.journal,
                                            source_store=HostedSources(server.connection))
        legacy_replays = []
        original_legacy_replay = legacy_store._replay

        def counted_legacy_replay(rows, **kwargs):
            legacy_replays.append(len(rows))
            return original_legacy_replay(rows, **kwargs)

        monkeypatch.setattr(legacy_store, '_replay', counted_legacy_replay)

        class LegacyFullList:
            def list(self):
                return AutonomousStore.list(legacy_store)

            def get(self, claim_id):
                return legacy_store.get(claim_id)

        legacy = AutonomousKnowledge(LegacyFullList(), policy)
        for index, temperature in enumerate(('legacy_cold', 'legacy_warm')):
            server.reset_counts()
            assert legacy.view() == expected
            replay_count = len(legacy_replays) - index * 2 * CLAIM_COUNT
            assert replay_count == 2 * CLAIM_COUNT
            assert len(server.requests) > measurements[index]['http_requests']
            assert server.open_streams == 0
            measurements.append({'temperature': temperature, 'http_requests': len(server.requests),
                                 'journal_pages': len(server.journal_pages),
                                 'largest_response_bytes': max(server.response_bytes), 'replayed_claims': replay_count})
        print('Knowledge read measurements:', json.dumps(measurements, sort_keys=True))
    finally:
        server.close()


def test_hosted_journal_pages_keep_one_snapshot_while_a_peer_appends(tmp_path, monkeypatch):
    seed_root = tmp_path / 'seed'
    seed_root.mkdir()
    seed = AutonomousStore(seed_root / 'claims.sqlite3')
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    states = sorted([seed.intake({'title': f'Paged fixture {index}', 'message': 'Original fixture. ' + 'a' * 4000,
                                'files': []}, f'knowledge.snapshot.{index}') for index in range(3)],
                    key=lambda state: state['claim_id'])
    server, store, _, _ = hosted_copy((seed.path, seed.source_root, policy, states), tmp_path)
    with sqlite3.connect(server.path) as db:
        assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    peer = AutonomousStore(server.path, seed.source_root)
    monkeypatch.setattr(store, 'JOURNAL_PAGE_BYTES', 16 * 1024)
    original_statement = server._statement
    advanced = []
    use = {'knowledge_id': 'knowledge_fixture_snapshot', 'version': 1}

    def append_between_pages(connection, stmt):
        result = original_statement(connection, stmt)
        if not advanced and result['rows'] and 'event_json' in [column['name'] for column in result['cols']]:
            advanced.append(append(peer, states[-1], 'knowledge.used', {'knowledge': use}, 'knowledge.snapshot.advance'))
        return result

    monkeypatch.setattr(server, '_statement', append_between_pages)
    knowledge = AutonomousKnowledge(store, policy)
    try:
        server.reset_counts()
        assert knowledge.view() == {'versions': [], 'uses': [], 'quarantined': []}
        assert advanced and advanced[0]['revision'] == states[-1]['revision'] + 1
        assert len(server.journal_pages) > 2
        assert sum(count for count, _ in server.journal_pages) == len(states)
        assert max(size for _, size in server.journal_pages) <= store.JOURNAL_PAGE_BYTES
        assert knowledge.view()['uses'] == [{**use, 'claim_id': states[-1]['claim_id']}]
        assert next(state for state in store.validated_states() if state['claim_id'] == states[-1]['claim_id']) == advanced[0]
        assert server.open_streams == 0
    finally:
        server.close()


@pytest.mark.parametrize('loop_id,sequence', [('', -1), ('', 1), ('autonomous.fixture', -1)])
def test_hosted_first_page_rejects_malformed_namespace_and_sequence(tmp_path, monkeypatch, loop_id, sequence):
    server = CountMockHrana(tmp_path / 'malformed.sqlite3')
    journal = HostedJournal(tmp_path / 'unused-malformed-placeholder', server.connection)
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(server.connection))
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    with sqlite3.connect(server.path) as db:
        db.execute('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                   (SESSION_ID, loop_id, sequence, 'malformed', 'a' * 64, 'b' * 64, '{}', 'fixture'))
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Malformed paging keys reached replay'))
    try:
        with pytest.raises(AutonomousStoreError, match='Journal read page identity or size differs'):
            AutonomousKnowledge(store, policy).view()
        assert server.open_streams == 0
    finally:
        server.close()


def test_hosted_paging_does_not_hide_a_later_sequence_gap(tmp_path, monkeypatch):
    seed = AutonomousStore(tmp_path / 'seed.sqlite3')
    policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
    state = seed.intake({'title': 'Later page gap fixture', 'message': 'Original source.', 'files': []}, 'gap.intake')
    state = append(seed, state, 'work.phase', {'phase': 'first', 'summary': 'First recorded phase.'}, 'gap.first')
    state = append(seed, state, 'work.phase', {'phase': 'later', 'summary': 'Later recorded phase.'}, 'gap.later')
    server, store, _, _ = hosted_copy((seed.path, seed.source_root, policy, [state]), tmp_path)
    monkeypatch.setattr(store, 'JOURNAL_PAGE_ROWS', 1)
    monkeypatch.setattr(store, 'KNOWLEDGE_PAGE_ROWS', 1)
    with sqlite3.connect(server.path) as db:
        db.execute('DELETE FROM claim_loop_events WHERE sequence=2')
    try:
        server.reset_counts()
        with pytest.raises(AutonomousStoreError, match='journal event identity or hash differs'):
            AutonomousKnowledge(store, policy).view()
        assert [count for count, _ in server.journal_pages] == [1, 1, 0]
        assert server.open_streams == 0
    finally:
        server.close()


def test_warm_learning_cache_rejects_a_new_hash_consistent_unknown_event(tmp_path):
    store = AutonomousStore(tmp_path / 'unknown-event.sqlite3')
    state = store.intake({'title': 'Isolated unknown event fixture', 'message': 'Original evidence.', 'files': []}, 'unknown.intake')
    knowledge = AutonomousKnowledge(store, {})
    assert knowledge.learning_view()['learning_replay']['events'] == []
    advanced = append(store, state, 'work.phase', {'phase': 'testing', 'summary': 'A bounded fixture phase.'}, 'unknown.phase')
    with sqlite3.connect(store.path) as db:
        encoded = db.execute('SELECT event_json FROM claim_loop_events WHERE loop_id=? AND sequence=?',
                             ('autonomous.' + state['claim_id'], advanced['revision'])).fetchone()[0]
        event = json.loads(encoded)
        event['kind'] = 'knowledge.unknown'
        event['command_sha256'] = digest_value({key: event[key] for key in
                                               ('kind', 'payload', 'expected_revision', 'expected_state_sha256')})
        event['event_sha256'] = digest_value({key: value for key, value in event.items()
                                             if key not in {'event_sha256', 'resulting_state_sha256'}})
        db.execute('UPDATE claim_loop_events SET event_json=?,command_sha256=?,event_sha256=? WHERE loop_id=? AND sequence=?',
                   (json.dumps(event), event['command_sha256'], event['event_sha256'],
                    'autonomous.' + state['claim_id'], advanced['revision']))
    with pytest.raises(AutonomousStoreError, match='unsupported autonomous event kind'):
        knowledge.learning_view()


@pytest.mark.parametrize('mutation', ['changed', 'missing'])
def test_hosted_warm_knowledge_rechecks_cached_source_bytes(processed_roster, tmp_path, mutation):
    server, store, policy, states = hosted_copy(processed_roster, tmp_path)
    knowledge = AutonomousKnowledge(store, policy)
    try:
        before = knowledge.view()
        assert before['versions']
        digest = states[0]['source_descriptors'][1]['sha256']
        assert digest in store._source_store._cache
        with sqlite3.connect(server.path) as db:
            if mutation == 'changed':
                db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
                db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0',
                           (b'Changed persisted supporting evidence.', digest))
            else:
                db.execute('DROP TRIGGER autonomous_source_chunks_no_delete')
                db.execute('DELETE FROM autonomous_source_chunks WHERE sha256=?', (digest,))
        with pytest.raises(AutonomousStoreError, match='Persistent .*bytes'):
            knowledge.view()
        assert server.open_streams == 0
    finally:
        server.close()


@pytest.mark.parametrize('phase', ['SELECT', 'COMMIT'])
def test_hosted_unconfirmed_journal_page_or_commit_returns_no_projection(processed_roster, tmp_path, monkeypatch, phase):
    server, store, policy, _ = hosted_copy(processed_roster, tmp_path)
    connections = []
    original_connect = server.connection

    def tracked_connection():
        connection = original_connect()
        connections.append(connection)
        return connection

    store.journal.connect = tracked_connection
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Unconfirmed rows reached reducer admission'))
    try:
        server.reset_counts()
        server.fail_next('timeout', sql_prefix=phase)
        with pytest.raises(HostedStorageError, match='unconfirmed'):
            AutonomousKnowledge(store, policy).view()
        assert len(connections) == 1 and connections[0]._closed
        sql = list(statements(server.requests))
        assert sum(statement.strip().upper().startswith(phase) for statement in sql) == 1
        assert not any(statement.strip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE'} for statement in sql)
    finally:
        # A lost response can retain an unknown rotated server baton; the mock
        # owns and closes that indeterminate stream, as a remote stream expiry would.
        server.close()
    assert server.open_streams == 0

"""Canonical originals enter the existing stream only through explicit admission."""
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_store_v1 import AutonomousStore

PREFIX = '/api/claim-loops/v1/autonomous'
HEADERS = {'X-CasePath-Agent-Work': '1'}


@pytest.fixture(scope='module')
def corpus():
    return CanonicalCorpus()


@pytest.fixture
def api(tmp_path, corpus):
    store = AutonomousStore(tmp_path / 'canonical.sqlite3')
    submitted = []
    service = SimpleNamespace(store=store, submit=submitted.append)
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus))
    with TestClient(app) as client:
        yield client, store, submitted


def test_all_original_reads_have_no_events_or_dispatch(api, corpus):
    client, store, submitted = api
    rows = client.get(PREFIX + '/claims?limit=200').json()
    assert rows['total'] == 150 and len(rows['claims']) == 150
    assert {r['claim_id'] for r in rows['claims']} == set(corpus.ids)
    assert all(r['mode'] == 'unprocessed' and r['revision'] == 0 for r in rows['claims'])
    for cid in corpus.ids:
        snap = client.get(f'{PREFIX}/claims/{cid}/snapshot').json()
        state = snap['state']
        assert state == corpus.preview_state(cid)
        assert snap['events'] == [] and snap['current_revision'] == 0 and snap['cursor_sha256'] is None
        assert state['graph'] is None and state['evaluation'] is None and state['acquired_sources'] == []
    assert store.list() == [] and submitted == []


def test_installed_corpus_distinguishes_unknown_and_unprocessed_without_writes(api, corpus):
    client, store, submitted = api
    with store.journal.connect() as db:
        before = tuple(db.iterdump())
    sources_before = {path.relative_to(store.source_root): path.read_bytes()
                      for path in store.source_root.rglob('*') if path.is_file()}
    cid = corpus.ids[0]
    preview = corpus.preview_state(cid)
    for suffix in ('', '/snapshot', '/events'):
        unknown = client.get(f'{PREFIX}/claims/clm_0000000000000000{suffix}')
        assert unknown.status_code == 404
        assert unknown.json()['detail'] == 'Unknown original claim.'
        response = client.get(f'{PREFIX}/claims/{cid}{suffix}')
        assert response.status_code == 200
        result = response.json()
        assert result['current_revision'] == 0 and result['events'] == []
        assert result['current_state_sha256'] == preview['state_sha256']
        assert result['cursor_sha256'] is None
        if suffix != '/events':
            assert result['mode'] == 'unprocessed' and result['current_event_sha256'] is None
            assert result['state'] == preview
            assert result['state']['graph'] is None and result['state']['evaluation'] is None
            assert result['state']['acquired_sources'] == []
    with store.journal.connect() as db:
        assert tuple(db.iterdump()) == before
    assert {path.relative_to(store.source_root): path.read_bytes()
            for path in store.source_root.rglob('*') if path.is_file()} == sources_before
    assert store.list() == [] and submitted == []


def test_original_source_preview_is_not_admission(api, corpus):
    client, store, submitted = api
    cid = 'clm_7dbd7c7d1c4ddf90'
    before = corpus.preview_state(cid)
    for descriptor in before['source_descriptors']:
        path = f"{PREFIX}/sources/{cid}/{descriptor['artifact_id']}"
        download = client.get(path)
        assert download.status_code == 200
        assert sha256(download.content).hexdigest() == descriptor['sha256']
        assert download.headers['x-content-sha256'] == descriptor['sha256']
        preview = client.get(path + '/preview').json()
        assert preview['preview_only'] is True and preview['evidence_admitted'] is False
        assert preview['artifact_id'] == descriptor['artifact_id'] and 'receipt_sha256' not in preview
        assert client.get(path + '/text').status_code == 409
    assert store.list() == [] and submitted == []
    assert client.get(f'{PREFIX}/claims/{cid}').json()['state'] == before


def test_explicit_start_exact_retry_stale_and_unknown_fail_closed(api, corpus):
    client, store, submitted = api
    cid = corpus.ids[0]
    preview = corpus.preview_state(cid)
    body = {'expected_revision': 0, 'expected_state_sha256': preview['state_sha256'],
            'idempotency_key': 'original-api-start-1'}
    path = f'{PREFIX}/claims/{cid}/start'
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json=body, headers={**HEADERS, 'Origin': 'https://elsewhere.test'}).status_code == 403
    assert client.post(path, json={**body, 'expected_state_sha256': '0'*64}, headers=HEADERS).status_code == 409
    assert client.post(path, json={**body, 'expected_revision': 1}, headers=HEADERS).status_code == 409
    result = client.post(path, json=body, headers=HEADERS)
    assert result.status_code == 202, result.text
    state = result.json()
    assert state['claim_id'] == cid and state['revision'] == 1 and state['acquired_sources'] == []
    assert state['original_binding'] == preview['original_binding']
    assert client.post(path, json=body, headers=HEADERS).json() == state
    assert submitted == [cid]
    assert client.post(path, json={**body, 'idempotency_key': 'original-other-key'}, headers=HEADERS).status_code == 409
    assert client.post(PREFIX+'/claims/clm_0000000000000000/start', json=body, headers=HEADERS).status_code == 404
    for descriptor in state['source_descriptors']:
        assert store.artifact(cid, descriptor['artifact_id'])[0] == corpus.artifact(cid, descriptor['artifact_id'])[0]


def test_atomic_snapshot_and_legacy_events_never_mix_a_writer_head(api, monkeypatch):
    client, store, submitted = api
    state = store.intake({'title': 'Concurrent read', 'message': 'Original message', 'files': []}, 'atomic-intake-1')
    cid = state['claim_id']
    def forbidden(*args, **kwargs):
        raise AssertionError('separate state/event read must not be used')
    monkeypatch.setattr(store, 'get', forbidden)
    monkeypatch.setattr(store, 'events', forbidden)
    original = store.snapshot
    def advancing(*args, **kwargs):
        snap = original(*args, **kwargs)
        store.append(cid, 'work.deferred', {'code': 'paused', 'reason': 'Paused after read.'},
                     expected_revision=snap['state']['revision'], expected_state_sha256=snap['state']['state_sha256'],
                     idempotency_key=f"advance-{snap['state']['revision']}")
        return snap
    monkeypatch.setattr(store, 'snapshot', advancing)
    for suffix in ('snapshot', 'events'):
        result = client.get(f'{PREFIX}/claims/{cid}/{suffix}').json()
        assert result['events'][-1]['state_sha256'] == result['current_state_sha256']
        if suffix == 'snapshot':
            assert result['state']['revision'] == result['current_revision']
            assert result['state']['state_sha256'] == result['current_state_sha256']
            assert result['cursor_sha256'] == result['state']['last_event_sha256']
    assert submitted == []


def test_verified_prefix_replay_is_read_only_and_keeps_live_head(api, corpus):
    client, store, submitted = api
    cid = corpus.ids[1]
    preview = corpus.preview_state(cid)
    admitted = store.admit_original(cid, corpus.packet(cid), expected_revision=0,
                    expected_state_sha256=preview['state_sha256'], idempotency_key='replay-start-1')['state']
    head = store.append(cid, 'work.deferred', {'code': 'paused', 'reason': 'Historical pause.'},
                        expected_revision=1, expected_state_sha256=admitted['state_sha256'], idempotency_key='replay-pause-1')
    result = client.get(f'{PREFIX}/claims/{cid}/replay?through_seq=1').json()
    assert result['mode'] == 'replay' and result['replay_only'] is True
    assert result['state'] == admitted and result['current_revision'] == 2
    assert result['current_state_sha256'] == head['state_sha256']
    assert len(result['events']) == 1 and result['cursor_sha256'] == admitted['last_event_sha256']
    assert client.get(f'{PREFIX}/claims/{cid}/replay?through_seq=3').status_code == 409
    zero = client.get(f'{PREFIX}/claims/{cid}/replay?through_seq=0').json()
    assert zero['state'] == preview and zero['current_revision'] == 2 and zero['events'] == []
    assert store.get(cid) == head and submitted == []


def test_paged_search_preserves_legacy_records_and_original_metadata(api, corpus):
    client, store, submitted = api
    historical = store.intake({'title': 'Historic custom intake', 'message': 'Saved separately', 'files': []}, 'historic-intake-1')
    result = client.get(PREFIX+'/claims?limit=3&offset=2').json()
    assert result['total'] == 151 and len(result['claims']) == 3 and result['offset'] == 2
    search = client.get(PREFIX+'/claims?q=Historic%20custom').json()['claims']
    assert len(search) == 1 and search[0]['claim_id'] == historical['claim_id']
    assert search[0]['mode'] == 'saved' and search[0]['origin'] == 'native_intake'
    assert client.get(PREFIX+'/claims/clm_0000000000000000').status_code == 404
    assert submitted == []


def test_bad_journal_never_falls_back_to_unprocessed_or_zero_replay(api, corpus):
    client, store, submitted = api
    cid = corpus.ids[2]
    preview = corpus.preview_state(cid)
    store.admit_original(cid, corpus.packet(cid), expected_revision=0,
                         expected_state_sha256=preview['state_sha256'], idempotency_key='tamper-start-1')
    with store.journal.connect() as db:
        db.execute("UPDATE claim_loop_events SET event_json='{}'")
    for suffix in ('', '/snapshot', '/events', '/replay?through_seq=0', '/replay?through_seq=1'):
        assert client.get(f'{PREFIX}/claims/{cid}{suffix}').status_code == 409
    assert client.get(PREFIX+'/claims').status_code == 409
    assert submitted == []


def test_domain_browsing_is_exact_metadata_without_operational_labels(api, corpus):
    client, store, submitted = api
    result = client.get(PREFIX+'/claims').json()
    assert result['domain_counts'] == {'defect_mold_heating': 50, 'lease_termination_dispute': 50, 'rent_increase_dispute': 50}
    for domain in result['domain_counts']:
        filtered = client.get(PREFIX+'/claims', params={'domain': domain}).json()
        assert filtered['total'] == 50 and len(filtered['claims']) == 50
        assert all(r['browse_metadata']['domain'] == domain and r['browse_metadata']['browsing_only'] is True
                   for r in filtered['claims'])
    assert store.list() == [] and submitted == []


def test_exact_hosted_start_retry_recovers_a_busy_lease_without_new_admission(tmp_path, corpus):
    from casepath_api.hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease
    from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
    from casepath_api.hosted_sql_v1 import TursoDatabase
    from hosted_hrana_fixture import MockHrana
    remote = MockHrana(tmp_path / 'retry.db')
    database = TursoDatabase('libsql://fixture.turso.io', 'fixture-token-' * 4, client_factory=remote.client)
    lease = HostedWorkflowLease(database.connect)
    lease.initialize()
    journal = HostedJournal(tmp_path / 'remote-journal', lease.connect)
    store = HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(lease.connect))
    service = HostedAutonomousController(store, corpus._corpus.static_policy(), lease=lease)
    futures = []
    submit = service._executor.submit
    def capture(*args, **kwargs):
        future = submit(*args, **kwargs)
        futures.append(future)
        return future
    service._executor.submit = capture
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus))
    cid = corpus.ids[0]
    body = {'expected_revision': 0, 'expected_state_sha256': corpus.preview_state(cid)['state_sha256'],
            'idempotency_key': 'hosted-busy-start-1'}
    token = lease.acquire()
    try:
        with TestClient(app) as client:
            path = f'{PREFIX}/claims/{cid}/start'
            first = client.post(path, json=body, headers=HEADERS)
            assert first.status_code == 202
            futures[0].result(timeout=5)
            assert store.get(cid)['revision'] == 1 and cid in service._waiting
            lease.release(token)
            token = None
            assert client.get(f'{PREFIX}/claims/{cid}/snapshot').json()['state']['revision'] == 1
            assert len(futures) == 1, 'GET must not recover or submit work'
            assert client.post(path, json=body, headers=HEADERS).json() == first.json()
            assert len(futures) == 2, 'explicit exact retry must recover the parked accepted job'
            futures[-1].result(timeout=15)
            head = store.get(cid)
            assert head['run_id'] is not None and head['deferral']['code'] == 'model_unavailable'
            assert sum(event['kind'] == 'intake' for event in store.events(cid)) == 1
            assert client.post(path, json=body, headers=HEADERS).json() == first.json()
            assert len(futures) == 2, 'settled deferral must not create another physical attempt'
            assert store.get(cid) == head
    finally:
        if token is not None:
            lease.release(token)
        service.shutdown()
        remote.close()

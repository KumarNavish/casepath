"""Public read recovery, never inference or real storage/network access."""
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import httpx
import pytest

from casepath_api import hosted_app_v1, hosted_read_reliability_v1 as reliability, hosted_sql_v1 as sql
from hosted_hrana_fixture import MockHrana
from test_public_hosted_read_only_v1 import saved_runtime, HEADERS, ORIGIN, TOKEN, PREFIX, rows, statements


@pytest.fixture
def public(saved_runtime, tmp_path, monkeypatch):
    server, database, _, _, pending, *_ = saved_runtime
    # Only the two backoff sleeps are suppressed; transport faults still pass
    # through the real Hrana client, response decoder and source validation.
    monkeypatch.setattr(reliability, 'time', SimpleNamespace(monotonic=time.monotonic, sleep=lambda _: None))
    app = hosted_app_v1.create_hosted_app(database=database, environment={
        'CASEPATH_SITE_ORIGIN': ORIGIN, 'CASEPATH_PROXY_TOKEN': TOKEN, 'CASEPATH_SOURCE_COMMIT': 'a' * 40},
        runtime_directory=tmp_path / 'public')
    with TestClient(app) as client:
        yield server, client, pending


def transient_failures(server, count=3, *, kind='timeout', sql_prefix='BEGIN'):
    for _ in range(count):
        server.fail_next(kind, sql_prefix=sql_prefix)


def test_first_lost_begin_response_restarts_the_complete_read_without_row_change(public):
    server, client, _ = public
    before, start = rows(server.path), len(server.requests)
    transient_failures(server, 1)
    response = client.get(PREFIX + '/claims?limit=1', headers=HEADERS)
    assert response.status_code == 200 and len(response.json()['claims']) == 1
    assert response.headers['x-casepath-read-source'] == 'primary'
    calls = server.requests[start:]
    begins = [call for call in calls if any(item.get('stmt', {}).get('sql') == 'BEGIN' for item in call['requests'])]
    assert len(begins) >= 2 and all(call['baton'] is None for call in begins)
    assert all(command.lstrip().split()[0].upper() in {'SELECT', 'BEGIN', 'COMMIT'} for command in statements(calls))
    assert rows(server.path) == before


def test_persistent_read_failure_is_honest_without_exact_cached_query(public):
    server, client, _ = public
    before, start, began = rows(server.path), len(server.requests), time.monotonic()
    transient_failures(server)
    response = client.get(PREFIX + '/claims?q=uncached-query', headers=HEADERS)
    assert response.status_code == 503 and response.headers['cache-control'] == 'no-store'
    assert 'x-casepath-read-source' not in response.headers
    assert len(server.requests[start:]) == reliability.MAX_ATTEMPTS
    assert time.monotonic() - began < reliability.READ_SECONDS
    assert rows(server.path) == before


@pytest.mark.parametrize('suffix', ['/claims', '/knowledge', '/claims/{claim_id}/events', '/claims/{claim_id}/snapshot',
                                  '/claims/{claim_id}', '/claims/{claim_id}/replay?through_seq=1'])
def test_last_verified_exact_projection_survives_only_transient_exhaustion(public, suffix):
    server, client, pending = public
    path = PREFIX + suffix.format(claim_id=pending['claim_id'])
    first = client.get(path, headers=HEADERS)
    assert first.status_code == 200
    before = rows(server.path)
    transient_failures(server, kind='http_error', sql_prefix=None)
    fallback = client.get(path, headers=HEADERS)
    assert fallback.status_code == 200 and fallback.content == first.content
    assert fallback.headers['x-casepath-read-source'] == 'last-verified'
    assert fallback.headers['cache-control'] == 'no-store'
    assert rows(server.path) == before
    fresh = client.get(path, headers=HEADERS)
    assert fresh.status_code == 200 and fresh.headers['x-casepath-read-source'] == 'primary'


@pytest.mark.parametrize('fault', ['origin', 'missing_result'])
def test_protocol_failure_does_not_retry_or_use_or_retain_old_projection(public, fault):
    server, client, _ = public
    path = PREFIX + '/knowledge'
    assert client.get(path, headers=HEADERS).status_code == 200
    start = len(server.requests)
    server.fail_next(fault)
    assert client.get(path, headers=HEADERS).status_code == 503
    assert len(server.requests) - start == 1
    transient_failures(server, sql_prefix=None)
    assert client.get(path, headers=HEADERS).status_code == 503


@pytest.mark.parametrize('statement', ['BEGIN IMMEDIATE', 'DELETE FROM proof', 'SELECT 1; DELETE FROM proof',
                                     '/* hidden */ UPDATE proof SET value=2'])
def test_retry_context_rejects_write_or_multistatement_before_transport(tmp_path, statement):
    server = MockHrana(tmp_path / 'read-guard.db')
    guarded = reliability.HostedReadReliability('a' * 40, ready=lambda: True)
    calls = []
    def endpoint():
        calls.append(True)
        with server.connection() as db:
            db.execute(statement)
        return {'unsafe': True}
    try:
        with pytest.raises(sql.HostedStorageError, match='cannot execute'):
            guarded.protect(endpoint, '/claims')()
        assert calls == [True] and server.requests == []
    finally:
        server.close()


def test_write_with_lost_commit_acknowledgement_is_never_retried(tmp_path):
    server = MockHrana(tmp_path / 'write-no-retry.db')
    try:
        with server.connection() as db:
            db.executescript('CREATE TABLE proof(value INTEGER);')
        server.fail_next('timeout', sql_prefix='COMMIT')
        with pytest.raises(sql.HostedStorageError):
            with server.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO proof VALUES (7)')
        assert sum(command == 'INSERT INTO proof VALUES (7)' for command in statements(server.requests)) == 1
        with server.connection() as db:
            assert db.execute('SELECT value FROM proof').fetchall()[0][0] == 7
    finally:
        server.close()


@pytest.mark.parametrize('failure', [httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout])
def test_only_classified_connection_failures_allow_fresh_attempts(tmp_path, monkeypatch, failure):
    server = MockHrana(tmp_path / 'connect.db')
    attempts = []
    def handle(request):
        attempts.append(request)
        assert all(0 < value <= 2 for value in request.extensions['timeout'].values())
        if len(attempts) == 1:
            raise failure('fixture transport failure', request=request)
        return server.handle(request)
    monkeypatch.setattr(reliability, 'time', SimpleNamespace(monotonic=time.monotonic, sleep=lambda _: None))
    def endpoint():
        with sql.LibsqlConnection(server.origin, 'fixture-token-' * 4,
                                 client=httpx.Client(transport=httpx.MockTransport(handle))) as db:
            return {'value': db.read_snapshot([('SELECT 1 AS value', ())])[0].fetchone()['value']}
    try:
        response = reliability.HostedReadReliability('a' * 40, ready=lambda: True).protect(endpoint, '/claims')()
        assert response.status_code == 200 and json.loads(response.body) == {'value': 1}
        assert len(attempts) == 2
    finally:
        server.close()


def test_one_cumulative_deadline_stops_later_attempts_and_network_calls(monkeypatch, tmp_path):
    now, attempts = [1.0], []
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda duration: now.__setitem__(0, now[0] + duration))
    monkeypatch.setattr(reliability, 'time', clock)
    monkeypatch.setattr(sql, 'time', clock)
    server = MockHrana(tmp_path / 'deadline.db')
    def endpoint():
        attempts.append(True)
        now[0] += reliability.READ_SECONDS
        with server.connection() as db:
            return {'value': db.execute('SELECT 1').fetchone()[0]}
    try:
        with pytest.raises(sql.HostedReadDeadline):
            reliability.HostedReadReliability('a' * 40, ready=lambda: True).protect(endpoint, '/claims')()
        assert attempts == [True] and server.requests == []
    finally:
        server.close()


def test_cache_is_bounded_and_separate_per_release_and_streaming_is_excluded(monkeypatch):
    monkeypatch.setattr(reliability, 'MAX_ENTRIES', 2)
    cached = reliability.HostedReadReliability('a' * 40, ready=lambda: True)
    cached._remember(('a' * 40, '/claims', '{"offset":0}'), b'one')
    cached._remember(('a' * 40, '/claims', '{"offset":1}'), b'two')
    cached._remember(('a' * 40, '/claims', '{"offset":2}'), b'three')
    assert len(cached._cache) == 2 and cached._bytes == 8
    assert not reliability.HostedReadReliability('b' * 40, ready=lambda: True)._cache
    assert not any(path.endswith('/operations') for path in reliability.PATHS)
    cached.clear()
    assert cached._bytes == 0 and not cached._cache
    monkeypatch.setattr(reliability, 'MAX_ENTRY_BYTES', 2)
    cached._remember(('a' * 40, '/claims', '{}'), b'too large')
    cached._remember(('a' * 40, '/claims', 'x' * (reliability.MAX_KEY_BYTES + 1)), b'1')
    assert not cached._cache and cached._bytes == 0


def test_readiness_cannot_be_admitted_from_a_previously_encoded_projection(monkeypatch):
    ready, failed = [True], [False]
    monkeypatch.setattr(reliability, 'time', SimpleNamespace(monotonic=time.monotonic, sleep=lambda _: None))
    cache = reliability.HostedReadReliability('a' * 40, ready=lambda: ready[0])
    def endpoint():
        if failed[0]:
            raise sql.HostedReadTransient('fixture')
        return {'saved': True}
    wrapped = cache.protect(endpoint, '/claims')
    assert wrapped().status_code == 200
    ready[0], failed[0] = False, True
    with pytest.raises(sql.HostedReadTransient):
        wrapped()


def test_lock_acquisition_shares_read_deadline_and_never_releases_an_unheld_lock(monkeypatch):
    from casepath_api import hosted_read_timing_v1 as timing
    calls = []
    lock = SimpleNamespace(acquire=lambda **kwargs: calls.append(kwargs) or False,
                           release=lambda: pytest.fail('failed acquisition must not release lock'))
    monkeypatch.setattr(timing, 'monotonic', lambda: 7.5)
    token = sql.READ_ONLY_DEADLINE.set(8.0)
    try:
        with pytest.raises(sql.HostedReadDeadline):
            with timing.read_lock(lock):
                pytest.fail('expired lock cannot enter projection')
        assert calls == [{'timeout': 0.5}]
    finally:
        sql.READ_ONLY_DEADLINE.reset(token)


def test_unknown_claim_does_not_evict_other_verified_projections(public):
    server, client, _ = public
    path = PREFIX + '/knowledge'
    first = client.get(path, headers=HEADERS)
    assert first.status_code == 200
    before = rows(server.path)
    missing = client.get(PREFIX + '/claims/clm_0000000000000000', headers=HEADERS)
    assert missing.status_code == 404 and 'x-casepath-read-source' not in missing.headers
    transient_failures(server, kind='http_error', sql_prefix=None)
    fallback = client.get(path, headers=HEADERS)
    assert fallback.status_code == 200 and fallback.content == first.content
    assert fallback.headers['x-casepath-read-source'] == 'last-verified'
    assert rows(server.path) == before


@pytest.mark.parametrize('status', [409, 422])
def test_integrity_http_failures_invalidate_verified_projections(monkeypatch, status):
    from fastapi import HTTPException
    phase = ['ok']
    monkeypatch.setattr(reliability, 'time', SimpleNamespace(monotonic=time.monotonic, sleep=lambda _: None))
    cache = reliability.HostedReadReliability('a' * 40, ready=lambda: True)
    def endpoint():
        if phase[0] == 'integrity':
            raise HTTPException(status_code=status, detail='Saved state could not be verified.')
        if phase[0] == 'transient':
            raise sql.HostedReadTransient('fixture')
        return {'saved': True}
    wrapped = cache.protect(endpoint, '/claims')
    healthy = cache.protect(endpoint, '/knowledge')
    assert healthy().status_code == 200
    phase[0] = 'integrity'
    with pytest.raises(HTTPException) as rejected:
        wrapped()
    assert rejected.value.status_code == status
    phase[0] = 'transient'
    with pytest.raises(sql.HostedReadTransient):
        healthy()

"""Read-only request bounds and closed dispatch; MockHrana, no real network."""
from hashlib import sha256
from pathlib import Path
import runpy
import sqlite3
from types import SimpleNamespace

import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api.agent_work.store import WorkStore
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease, _CURRENT_OWNER
from casepath_api.hosted_storage_v1 import HostedJournal

operator = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/admit_reference.py'))


def statements(server, start):
    result = []
    for request in server.requests[start:]:
        for operation in request['requests']:
            if operation['type'] == 'execute':
                result.append(operation['stmt'])
            elif operation['type'] == 'batch':
                result.extend(step['stmt'] for step in operation['batch']['steps'])
    return result


def initialized(server, tmp_path):
    lease = HostedWorkflowLease(server.connection)
    lease.initialize()
    HostedJournal(tmp_path / 'unused-journal', server.connection)
    work = WorkStore(tmp_path / 'unused-work', connection_factory=server.connection)
    work.close()
    return lease


def test_inventory_pages_2000_normal_journal_shaped_rows_without_limit_one(tmp_path):
    server = MockHrana(tmp_path / 'inventory.sqlite')
    try:
        initialized(server, tmp_path)
        with sqlite3.connect(server.path) as db:
            db.execute('CREATE TABLE read_fixture_rows(id INTEGER PRIMARY KEY,record_json TEXT,record_sha256 TEXT)')
            payload = '{"claim":"synthetic","summary":"' + 'source-backed observation ' * 40 + '"}'
            db.executemany('INSERT INTO read_fixture_rows VALUES(?,?,?)',
                           [(i, payload, sha256((payload + str(i)).encode()).hexdigest()) for i in range(2000)])
        start = len(server.requests)
        before, values = operator['inventory'](server.connection)
        assert before['tables']['read_fixture_rows']['count'] == 2000
        assert len(values['read_fixture_rows']['rows']) == 2000
        reads = [row for row in statements(server, start)
                 if row['sql'].startswith('SELECT ') and 'FROM "read_fixture_rows"' in row['sql']
                 and 'ORDER BY' in row['sql']]
        assert len(reads) == 32
        assert all(row['args'][-1]['value'] == '64' for row in reads)
        assert len(server.requests) - start < 160
        assert not any(row['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE'))
                       for row in statements(server, start))
    finally:
        server.close()


def test_inventory_large_escaped_unicode_and_blob_rows_keep_wire_bounds_and_exact_bytes(tmp_path):
    from casepath_api.hosted_sql_v1 import MAX_BYTES
    server = MockHrana(tmp_path / 'large.sqlite')
    try:
        initialized(server, tmp_path)
        payload = '"\n🧭\\\x00' * 75_000
        blob = bytes(range(256)) * 200
        with sqlite3.connect(server.path) as db:
            db.execute('CREATE TABLE large_fixture_rows(id INTEGER PRIMARY KEY,value TEXT,blob BLOB,nullable TEXT)')
            db.executemany('INSERT INTO large_fixture_rows VALUES(?,?,?,?)', [(i, payload, blob, None) for i in range(5)])
        start = len(server.requests)
        before, values = operator['inventory'](server.connection)
        actual = [operator['_unwire'](row) for row in values['large_fixture_rows']['rows']]
        assert actual == [(i, payload, blob, None) for i in range(5)]
        reads = [row for row in statements(server, start) if 'FROM "large_fixture_rows"' in row['sql'] and 'ORDER BY' in row['sql']]
        assert len(reads) == 3
        assert all(row['args'][-1]['value'] == '2' for row in reads)
        with server.connection() as db:
            table = operator['table_info'](db, 'large_fixture_rows')
            bound = operator['read_row_bound'](db, 'large_fixture_rows', table)
        exact = operator['_migration']['wire_size'](actual[0])
        assert exact <= bound
        assert 2 * bound < 8 * 1024 * 1024 < MAX_BYTES
        assert before['tables']['large_fixture_rows']['count'] == 5
    finally:
        server.close()


@pytest.mark.parametrize('hosted', [False, True])
def test_closed_dispatch_never_reads_store_gate_sources_or_lease(hosted):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('Closed dispatch attempted authority work')
    store = SimpleNamespace(get=forbidden, list=forbidden)
    if hosted:
        service = HostedAutonomousController(store, {}, lease=SimpleNamespace(acquire=forbidden), enforce_intake_gate=True)
    else:
        service = AutonomousController(store, {}, enforce_intake_gate=True)
    service.intake_projection = forbidden
    service.shutdown()
    assert service.submit('unprocessed') is None
    assert service.run('unprocessed') is None
    assert service.resume() is None
    assert service._learn('unprocessed', 'unused') is None
    if hosted:
        service.wake_pending(force_discovery=True)
        service._remember('unprocessed', ('run', None))
        service._start('unprocessed')
        service._recover_pending(None)
        assert service._recovery_job({}) is None
    assert not calls and not service._jobs


def test_inventory_wal_snapshot_keeps_sparse_keyset_consistent_when_writer_commits_after_bound(tmp_path, monkeypatch):
    server = MockHrana(tmp_path / 'wal.sqlite')
    try:
        initialized(server, tmp_path)
        original_rows = [(i * 2, 'Original record ' + str(i)) for i in range(70)]
        with sqlite3.connect(server.path) as db:
            assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
            db.execute('CREATE TABLE wal_fixture_rows(id INTEGER PRIMARY KEY,value TEXT)')
            db.executemany('INSERT INTO wal_fixture_rows VALUES(?,?)', original_rows)
        globals_ = operator['inventory'].__globals__
        original_bound = globals_['read_row_bound']
        inserted = []
        def interleave(db, name, table):
            bound = original_bound(db, name, table)
            if name == 'wal_fixture_rows' and not inserted:
                with sqlite3.connect(server.path) as writer:
                    writer.executemany('INSERT INTO wal_fixture_rows VALUES(?,?)',
                                       [(3, 'New record before page boundary'), (9999, 'New record after page boundary')])
                inserted.append(True)
            return bound
        monkeypatch.setitem(globals_, 'read_row_bound', interleave)
        before, values = operator['inventory'](server.connection)
        assert inserted
        assert before['tables']['wal_fixture_rows']['count'] == 70
        assert [operator['_unwire'](row) for row in values['wal_fixture_rows']['rows']] == original_rows
        after, _ = operator['inventory'](server.connection)
        assert after['tables']['wal_fixture_rows']['count'] == 72
        assert after['tables']['wal_fixture_rows']['content_sha256'] != before['tables']['wal_fixture_rows']['content_sha256']
    finally:
        server.close()


def test_base_future_completion_after_shutdown_never_reads_authority():
    callbacks, reads = [], []
    def get(claim):
        reads.append(claim)
        return {'claim_id': claim, 'policy_id': None, 'source_descriptors': [], 'deferral': None}
    store = SimpleNamespace(get=get)
    service = AutonomousController(store, {}, enforce_intake_gate=True)
    service.intake_projection = lambda state: {'eligible': True}
    future = SimpleNamespace(done=lambda: False, add_done_callback=callbacks.append)
    service._executor.submit = lambda *args: future
    service.submit('explicit-scheduler-spy')
    assert len(callbacks) == 1
    service.shutdown()
    reads.clear()
    callbacks[0](future)
    assert reads == []


def test_closed_base_controller_cannot_borrow_unrelated_hosted_owner():
    service = AutonomousController(SimpleNamespace(get=lambda claim: pytest.fail('Unrelated owner read')), {})
    service.shutdown()
    token = _CURRENT_OWNER.set(SimpleNamespace(lease=object()))
    try:
        assert service.run('unrelated-owner') is None
        assert service._learn('unrelated-owner', 'unused') is None
    finally:
        _CURRENT_OWNER.reset(token)

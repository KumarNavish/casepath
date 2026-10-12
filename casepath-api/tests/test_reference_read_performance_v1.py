"""Read-only request bounds and closed dispatch; MockHrana, no real network."""
from hashlib import sha256
import json
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
                 and row['sql'].startswith('SELECT "')]
        assert len(reads) == 32
        assert [row['args'][-1]['value'] for row in reads] == ['64'] * 31 + ['16']
        assert len(server.requests) - start < 180
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
        reads = [row for row in statements(server, start) if 'FROM "large_fixture_rows"' in row['sql']
                 and row['sql'].startswith('SELECT "')]
        assert len(reads) == 3
        assert [row['args'][-1]['value'] for row in reads] == ['2', '2', '1']
        with server.connection() as db:
            table = operator['table_info'](db, 'large_fixture_rows')
            count, bound, _ = operator['_candidate_page'](db, 'large_fixture_rows', table, None)
            assert count == 5
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
        original_bound = globals_['_candidate_page']
        inserted = []
        def interleave(db, name, table, last):
            bound = original_bound(db, name, table, last)
            if name == 'wal_fixture_rows' and not inserted:
                with sqlite3.connect(server.path) as writer:
                    writer.executemany('INSERT INTO wal_fixture_rows VALUES(?,?)',
                                       [(3, 'New record before page boundary'), (9999, 'New record after page boundary')])
                inserted.append(True)
            return bound
        monkeypatch.setitem(globals_, '_candidate_page', interleave)
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


@pytest.mark.parametrize('sparse', [False, True])
def test_work_calls_candidate_prefixes_dense_sparse_composite_keys_and_escaped_json(tmp_path, sparse):
    server = MockHrana(tmp_path / 'calls.sqlite')
    try:
        initialized(server, tmp_path)
        payload = json.dumps({'text': '"\n🧭\\' * 250, 'null': None, 'nested': [1, -1.25, True]}, ensure_ascii=False)
        with sqlite3.connect(server.path) as db:
            db.executemany('INSERT INTO work_calls VALUES(?,?,?,?,?,?,?,?)',
                [('fixture.' + str(i // 100).zfill(3), 'executor' if i % 2 else 'planner',
                  'call.' + str(i * 7 if sparse else i).zfill(8), 'a' * 64,
                  'fixture.inspection', 'completed', payload, '2026-10-12T00:00:00Z') for i in range(2000)])
            expected = db.execute('SELECT * FROM work_calls ORDER BY run_id,role,call_id').fetchall()
        start = len(server.requests)
        before, values = operator['inventory'](server.connection)
        actual = [operator['_unwire'](row) for row in values['work_calls']['rows']]
        assert actual == expected and len({row[:3] for row in actual}) == 2000
        assert before['tables']['work_calls'] == operator['table_digest'](expected, values['work_calls']['columns'])
        calls = [row for row in statements(server, start) if 'FROM "work_calls"' in row['sql']]
        metadata = [row for row in calls if row['sql'].startswith('SELECT count(*)')]
        payloads = [row for row in calls if row['sql'].startswith('SELECT "')]
        assert len(metadata) == len(payloads) == 32
        assert all('FROM (SELECT ' in row['sql'] and row['sql'].endswith(' LIMIT ?)')
                   and row['args'][-1]['value'] == '64' for row in metadata)
        assert all(' ORDER BY "run_id","role","call_id" LIMIT ?' in row['sql'] for row in calls)
        assert [row['args'][-1]['value'] for row in payloads] == ['64'] * 31 + ['16']
        assert not any(row['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE'))
                       for row in statements(server, start))
    finally:
        server.close()


@pytest.mark.parametrize('large_key', [False, True])
def test_oversized_row_or_primary_key_refuses_before_payload_transport(tmp_path, large_key):
    server = MockHrana(tmp_path / 'oversized.sqlite')
    try:
        initialized(server, tmp_path)
        oversized = '\x01' * (6 * 1024 * 1024)
        with sqlite3.connect(server.path) as db:
            db.execute('CREATE TABLE oversized_fixture(key TEXT PRIMARY KEY,value TEXT)')
            db.execute('INSERT INTO oversized_fixture VALUES(?,?)',
                       (oversized if large_key else 'safe-key', '' if large_key else oversized))
        start = len(server.requests)
        with pytest.raises(operator['Refused'], match='transport bound'):
            operator['inventory'](server.connection)
        reads = [row for row in statements(server, start) if 'FROM "oversized_fixture"' in row['sql']]
        assert len(reads) == 1 and reads[0]['sql'].startswith('SELECT count(*)')
        assert all(arg.get('value') != oversized for row in reads for arg in row['args'])
    finally:
        server.close()


def test_nullable_composite_key_refuses_at_later_candidate_page_and_alias_scalar_types_are_exact(tmp_path):
    server = MockHrana(tmp_path / 'nullable.sqlite')
    try:
        initialized(server, tmp_path)
        with sqlite3.connect(server.path) as db:
            db.execute('CREATE TABLE nullable_fixture(a TEXT,b INTEGER,value TEXT,PRIMARY KEY(a,b))')
            db.executemany('INSERT INTO nullable_fixture VALUES(?,?,?)',
                           [(str(i).zfill(3), i, 'exact row') for i in range(70)])
            db.execute('INSERT INTO nullable_fixture VALUES(?,?,?)', ('090', None, 'must refuse'))
            db.execute('CREATE TABLE scalar_fixture(key BLOB PRIMARY KEY,__reference_wire_bound TEXT,value REAL,nullable TEXT)')
            db.executemany('INSERT INTO scalar_fixture VALUES(?,?,?,?)',
                           [(bytes([i]), '\x00"🧭', value, None) for i, value in enumerate((1e308, -1e308, 0.0, -0.0))])
            expected = db.execute('SELECT * FROM scalar_fixture ORDER BY key').fetchall()
        with server.connection() as db:
            db.execute('BEGIN')
            table = operator['table_info'](db, 'scalar_fixture')
            assert list(operator['bounded_rows'](db, 'scalar_fixture', table)) == expected
            assert operator['table_digest'](expected, table['columns'])['count'] == 4
        start = len(server.requests)
        with pytest.raises(operator['Refused'], match='nullable primary key'):
            operator['inventory'](server.connection)
        reads = [row for row in statements(server, start) if 'FROM "nullable_fixture"' in row['sql']]
        assert sum(row['sql'].startswith('SELECT count(*)') for row in reads) == 2
        assert sum(row['sql'].startswith('SELECT "') for row in reads) == 1
    finally:
        server.close()


@pytest.mark.parametrize('tail_large', [False, True])
@pytest.mark.parametrize('key_name', ['__wire_bound', '__null_key', '__reference_candidate_wire_bound',
                                    '__reference_candidate_null_key', '__WIRE_BOUND', '__NULL_KEY',
                                    '__REFERENCE_CANDIDATE_WIRE_BOUND', '__REFERENCE_CANDIDATE_NULL_KEY',
                                    '__REFERENCE_WIRE_BOUND'])
def test_candidate_aliases_cannot_shadow_real_primary_key_order_and_oversize_tail(tmp_path, key_name, tail_large):
    server = MockHrana(tmp_path / 'alias.sqlite')
    try:
        initialized(server, tmp_path)
        with sqlite3.connect(server.path) as db:
            db.execute('CREATE TABLE alias_fixture(' + operator['q'](key_name) + ' INTEGER PRIMARY KEY,payload TEXT)')
            db.executemany('INSERT INTO alias_fixture VALUES(?,?)',
                           [(i, 'large' * 100 if (i >= 64) == tail_large else 'x') for i in range(128)])
            expected = db.execute('SELECT * FROM alias_fixture ORDER BY ' + operator['q'](key_name)).fetchall()
        before, values = operator['inventory'](server.connection)
        assert [operator['_unwire'](row) for row in values['alias_fixture']['rows']] == expected
        assert before['tables']['alias_fixture'] == operator['table_digest'](expected, [key_name, 'payload'])
        with sqlite3.connect(server.path) as db:
            db.execute('INSERT INTO alias_fixture VALUES(?,?)', (128, '\x01' * (6 * 1024 * 1024)))
        start = len(server.requests)
        with pytest.raises(operator['Refused'], match='transport bound'):
            operator['inventory'](server.connection)
        payloads = [row for row in statements(server, start) if 'FROM "alias_fixture"' in row['sql']
                    and row['sql'].startswith('SELECT "')]
        assert len(payloads) == 2
        assert all(row['args'][-1]['value'] == '64' for row in payloads)
    finally:
        server.close()

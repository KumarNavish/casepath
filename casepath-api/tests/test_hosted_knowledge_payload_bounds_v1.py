"""Native synthetic journals bound full-row work before remote serialization."""
import sqlite3

import pytest

from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
from hosted_hrana_fixture import MockHrana


@pytest.fixture(scope='module')
def large_native_journal(tmp_path_factory):
    root = tmp_path_factory.mktemp('native-large-journal')
    store = AutonomousStore(root / 'claims.sqlite3')
    for index in range(35):
        # Intake permits 100,000 original characters; the native source reader
        # records its explicit extraction limit without discarding the bytes.
        message = (f'Isolated synthetic customer statement {index}. ' * 3000)[:100_000]
        store.intake({'title': f'Large original fixture {index}', 'message': message, 'files': []},
                     f'payload.bound.intake.{index}')
    return store.path, store.source_root


class ObservedRows(MockHrana):
    def __init__(self, path):
        super().__init__(path)
        self.pages = []

    def _statement(self, connection, statement):
        observed = []

        def full_payload(value):
            observed.append(len(value.encode()))
            return 1

        # A view's additional SQL column exposes when a full authority row is
        # evaluated, independently of wall-clock timing or optimizer opcodes.
        connection.create_function('fixture_full_payload', 1, full_payload)
        result = super()._statement(connection, statement)
        names = [column['name'] for column in result['cols']]
        if 'event_json' in names:
            self.pages.append({'returned_rows': len(result['rows']), 'payload_evaluations': len(observed),
                               'evaluated_event_bytes': sum(observed)})
        return result


@pytest.mark.parametrize('candidate_limit', [128, 2048])
def test_byte_cutoff_precedes_full_row_materialization_and_retains_every_authority_column(
        large_native_journal, tmp_path, candidate_limit):
    original, sources = large_native_journal
    server = ObservedRows(tmp_path / 'hosted.sqlite3')
    journal = HostedJournal(tmp_path / 'unused', server.connection)
    with sqlite3.connect(original) as source, sqlite3.connect(server.path) as target:
        rows = source.execute('SELECT * FROM claim_loop_events WHERE session_id=? ORDER BY loop_id,sequence',
                              (SESSION_ID,)).fetchall()
        target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', rows)
        # A same-loop/sequence row in another namespace detects an incomplete
        # join key. Extra SQL columns remain part of exact cache identity.
        target.execute('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', ('fixture.other-session', *rows[0][1:]))
        target.execute('ALTER TABLE claim_loop_events RENAME TO fixture_accepted_events')
        target.execute("ALTER TABLE fixture_accepted_events ADD COLUMN fixture_note TEXT NOT NULL DEFAULT 'original'")
        target.execute('UPDATE fixture_accepted_events SET fixture_note=loop_id')
        target.execute('CREATE VIEW claim_loop_events AS SELECT *, fixture_full_payload(event_json) AS fixture_probe '
                       'FROM fixture_accepted_events')
    store = HostedAutonomousStore(journal.path, source_root=sources, journal=journal,
                                  source_store=HostedSources(server.connection))
    store.KNOWLEDGE_PAGE_ROWS = candidate_limit
    try:
        actual = store._paged_state_rows(candidate_limit, count_candidates=True)
        assert len(server.pages) >= 2  # The byte budget, rather than row count, limits this fixture.
        assert len(actual) == len(rows)
        names = ('session_id', 'loop_id', 'sequence', 'idempotency_key', 'command_sha256',
                 'event_sha256', 'event_json', 'created_at')
        assert [tuple(row[name] for name in names) for row in actual] == rows
        assert all(row['fixture_note'] == row['loop_id'] and row['fixture_probe'] == 1 for row in actual)
        assert all(page['payload_evaluations'] == page['returned_rows'] for page in server.pages), server.pages
        assert sum(page['evaluated_event_bytes'] for page in server.pages) == sum(len(row[6].encode()) for row in rows)
        before = store._journal_snapshot(actual)
        with sqlite3.connect(server.path) as target:
            target.execute("UPDATE fixture_accepted_events SET fixture_note='changed' WHERE session_id=? AND loop_id=?",
                           (SESSION_ID, actual[0]['loop_id']))
        after = store._journal_snapshot(store._paged_state_rows(candidate_limit, count_candidates=True))
        assert before != after  # Unknown SQL columns cannot disappear from the cache key.
        assert server.open_streams == 0
    finally:
        server.close()


def test_single_native_event_above_page_budget_is_returned_without_truncation(tmp_path):
    seed = AutonomousStore(tmp_path / 'native.sqlite3')
    state = seed.intake({'title': 'Native page boundary fixture', 'message': 'Original customer statement.'}, 'page.boundary.intake')
    knowledge = {'knowledge_id': 'fixture.large.refusal', 'qualification': {
        'status': 'quarantined', 'reason': 'r' * (HostedAutonomousStore.JOURNAL_PAGE_BYTES - 256)}}
    state = seed.append(state['claim_id'], 'knowledge.published', {'knowledge': knowledge},
                        expected_revision=state['revision'], expected_state_sha256=state['state_sha256'],
                        idempotency_key='page.boundary.publication')
    server = MockHrana(tmp_path / 'hosted.sqlite3')
    journal = HostedJournal(tmp_path / 'unused', server.connection)
    with sqlite3.connect(seed.path) as source, sqlite3.connect(server.path) as target:
        rows = source.execute('SELECT * FROM claim_loop_events ORDER BY loop_id,sequence').fetchall()
        target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', rows)
    assert len(rows[-1][6].encode()) > HostedAutonomousStore.JOURNAL_PAGE_BYTES
    store = HostedAutonomousStore(journal.path, journal=journal)
    try:
        actual = store._knowledge_rows()
        assert [row['event_json'] for row in actual] == [row[6] for row in rows]
        assert server.open_streams == 0
    finally:
        server.close()


def test_row_above_absolute_bound_is_rejected_before_replay(tmp_path, monkeypatch):
    server = MockHrana(tmp_path / 'oversized.sqlite3')
    journal = HostedJournal(tmp_path / 'unused', server.connection)
    store = HostedAutonomousStore(journal.path, journal=journal)
    # Deliberately invalid raw pagination input, never accepted as native state.
    with sqlite3.connect(server.path) as target:
        target.execute('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',
                       (SESSION_ID, 'autonomous.fixture-oversize', 1, 'fixture.oversize', 'a' * 64, 'b' * 64,
                        'r' * (store.JOURNAL_ROW_BYTES + 1), '2026-10-16T00:00:00+00:00'))
    monkeypatch.setattr(store, '_replay', lambda *a, **k: pytest.fail('Oversized raw row reached replay'))
    try:
        with pytest.raises(AutonomousStoreError, match='Journal read page identity or size differs'):
            store.knowledge_snapshot()
        assert server.open_streams == 0
    finally:
        server.close()

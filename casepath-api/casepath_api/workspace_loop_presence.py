"""Read-only distinction between an uncreated review and a damaged existing journal."""
from typing import Any


def has_loop_records(store: Any, *, session_id: str, loop_id: str) -> bool:
    if not session_id or not loop_id:
        raise ValueError('Loop identity is required.')
    tables = (
        ('claim_loop_events', 'session_id', 'loop_id'),
        ('claim_loop_checkpoints', 'session_id', 'loop_id'),
        ('claim_loop_corrections', 'source_session_id', 'source_loop_id'),
        ('claim_loop_correction_artifacts', 'session_id', 'loop_id'),
        ('claim_loop_tool_artifacts', 'session_id', 'loop_id'),
        ('claim_loop_acquisitions', 'session_id', 'loop_id'),
        ('claim_loop_client_requests', 'session_id', 'loop_id'),
    )
    with store.connect() as connection:
        connection.execute('BEGIN')
        present = any(connection.execute(
            f'SELECT 1 FROM {table} WHERE {session_column}=? AND {loop_column}=? LIMIT 1',
            (session_id, loop_id),
        ).fetchone() is not None for table, session_column, loop_column in tables)
        connection.commit()
    return present

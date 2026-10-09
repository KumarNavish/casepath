"""Direct libSQL persistence for ephemeral compute; no local write replica.

The remote primary commits reservations before the existing model adapter may
send HTTP. A failed or ambiguous database operation is never retried here.
"""
from collections import OrderedDict
from hashlib import sha256
from pathlib import Path
from threading import RLock

from .autonomous_store_v1 import AutonomousStore, AutonomousStoreError, MAX_FILE_BYTES


from .hosted_sql_v1 import HostedStorageError, LibsqlConnection, TursoDatabase

JOURNAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_loop_events (
 session_id TEXT NOT NULL, loop_id TEXT NOT NULL, sequence INTEGER NOT NULL,
 idempotency_key TEXT NOT NULL, command_sha256 TEXT NOT NULL,
 event_sha256 TEXT NOT NULL, event_json TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(session_id,loop_id,sequence),
 UNIQUE(session_id,loop_id,idempotency_key), UNIQUE(session_id,loop_id,event_sha256)
);
CREATE INDEX IF NOT EXISTS claim_loop_event_tail ON claim_loop_events(session_id,loop_id,sequence);
CREATE TABLE IF NOT EXISTS autonomous_source_chunks (
 sha256 TEXT NOT NULL, chunk_index INTEGER NOT NULL, content BLOB NOT NULL,
 PRIMARY KEY(sha256,chunk_index)
);
CREATE TRIGGER IF NOT EXISTS autonomous_source_chunks_no_update BEFORE UPDATE ON autonomous_source_chunks
 BEGIN SELECT RAISE(ABORT,'source bytes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS autonomous_source_chunks_no_delete BEFORE DELETE ON autonomous_source_chunks
 BEGIN SELECT RAISE(ABORT,'source bytes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS autonomous_source_chunks_no_replace BEFORE INSERT ON autonomous_source_chunks
 WHEN EXISTS(SELECT 1 FROM autonomous_source_chunks WHERE sha256=NEW.sha256 AND chunk_index=NEW.chunk_index)
 BEGIN SELECT RAISE(ABORT,'source bytes are immutable'); END;
"""


class HostedJournal:
    def __init__(self, path, connection_factory):
        self.path = Path(path)
        self.connect = connection_factory
        with self.connect() as db:
            db.executescript(JOURNAL_SCHEMA)


class HostedSources:
    """Immutable original bytes, committed before an event can reference them."""
    CHUNK_BYTES = 256 * 1024
    CACHE_BYTES = 64 * 1024 * 1024

    def __init__(self, connection_factory):
        self.connect = connection_factory
        self._cache, self._size, self._lock = OrderedDict(), 0, RLock()

    def _remember(self, digest, raw):
        with self._lock:
            if digest not in self._cache:
                self._cache[digest] = raw
                self._size += len(raw)
            self._cache.move_to_end(digest)
            while self._size > self.CACHE_BYTES:
                _, removed = self._cache.popitem(last=False)
                self._size -= len(removed)
        return raw

    def read(self, digest):
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise AutonomousStoreError('Source identity is invalid.')
        with self._lock:
            cached = self._cache.get(digest)
            if cached is not None:
                self._cache.move_to_end(digest)
                return cached
        rows = []
        with self.connect() as db:
            # Keep each response below the remote service's result-size limit.
            for offset in range(0, MAX_FILE_BYTES // self.CHUNK_BYTES + 1, 8):
                page = db.execute('SELECT chunk_index,content FROM autonomous_source_chunks WHERE sha256=? '
                                  'ORDER BY chunk_index LIMIT 8 OFFSET ?', (digest, offset)).fetchall()
                rows.extend(page)
                if len(page) < 8:
                    break
        if not rows or [row['chunk_index'] for row in rows] != list(range(len(rows))):
            raise AutonomousStoreError('Persistent original source bytes are incomplete.')
        raw = b''.join(row['content'] for row in rows)
        if len(raw) > MAX_FILE_BYTES or sha256(raw).hexdigest() != digest:
            raise AutonomousStoreError('Persistent source bytes differ from their hash.')
        return self._remember(digest, raw)

    def publish(self, raw):
        if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
            raise AutonomousStoreError('Source exceeds its persistence bound.')
        digest = sha256(raw).hexdigest()
        with self.connect() as db:
            # Each chunk commits independently. A crash can leave unreferenced
            # chunks; an exact upload can fill the remainder. No descriptor is
            # admitted until complete hash-verified readback succeeds. This
            # avoids holding Turso's five-second transaction over a large file.
            for index, offset in enumerate(range(0, max(1, len(raw)), self.CHUNK_BYTES)):
                db.execute('INSERT INTO autonomous_source_chunks SELECT ?,?,? WHERE NOT EXISTS '
                           '(SELECT 1 FROM autonomous_source_chunks WHERE sha256=? AND chunk_index=?)',
                           (digest, index, raw[offset:offset + self.CHUNK_BYTES], digest, index))
        # An ambiguous commit cannot acknowledge intake.
        if self.read(digest) != raw:
            raise AutonomousStoreError('Persistent source publication differs.')
        return digest

    def verify_many(self, digests):
        """Freshly hash-check persisted bytes once per result source roster.

        A cached blob accelerates repeated reducer reads but cannot establish
        that the remote primary still has that exact complete chunk inventory.
        Retain the extraction cache; refresh original bytes before exposing a
        verified journal projection, including a recorded historical prefix.
        """
        with self._lock:
            for digest in dict.fromkeys(digests):
                cached = self._cache.pop(digest, None)
                if cached is not None:
                    self._size -= len(cached)
                self.read(digest)


class HostedAutonomousStore(AutonomousStore):
    @staticmethod
    def _journal_snapshot(rows):
        # Include names AND every SQL column/value, including raw event_json.
        return tuple(tuple((name, row[name]) for name in row.keys()) for row in rows)

    def _commit_command(self, claim_id, command, command_hash, idempotency_key):
        with self.journal.connect() as connection:
            rows = self._rows(connection, claim_id)
        for attempt in range(2):
            snapshot = self._journal_snapshot(rows)
            prepared, result = self._prepare_append(rows, claim_id, command, command_hash, idempotency_key)
            with self.journal.connect() as connection:
                connection.execute('BEGIN IMMEDIATE')  # Existing wrapper fences and renews here.
                current = self._rows(connection, claim_id)
                if self._journal_snapshot(current) == snapshot:
                    self._insert_prepared(connection, prepared)
                    # __exit__ must acknowledge COMMIT before this returns.
                    return {"state": result, "replayed": prepared is None}
                connection.rollback()
            rows = current  # Reprepare only after releasing the write transaction.
        raise AutonomousStoreError('stale claim revision or state hash')


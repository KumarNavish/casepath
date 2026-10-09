"""Direct libSQL persistence for ephemeral compute; no local write replica.

The remote primary commits reservations before the existing model adapter may
send HTTP. A failed or ambiguous database operation is never retried here.
"""
from collections import OrderedDict
from hashlib import sha256
import json
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
    PAGE_CHUNKS = 8
    BATCH_DIGESTS = 128

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

    @staticmethod
    def _digests(digests):
        values = set()
        for digest in digests:
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise AutonomousStoreError('Source identity is invalid.')
            values.add(digest)
        return sorted(values)

    def _fetch_many(self, digests, *, return_digest=None):
        """Read all requested chunks with bounded pages on one connection.

        Eight 256-KiB blobs cap a page at two MiB before wire encoding. Oversize
        or wrongly typed chunks return metadata and NULL rather than an unbounded
        blob. Keyset pagination verifies ordering and cannot skip a later-page
        gap. Keep one file buffer at a time and retain the existing bounded cache.
        """
        max_chunks = (MAX_FILE_BYTES + self.CHUNK_BYTES - 1) // self.CHUNK_BYTES
        result = None
        with self.connect() as db:
            for start in range(0, len(digests), self.BATCH_DIGESTS):
                batch = digests[start:start + self.BATCH_DIGESTS]
                wanted, seen = set(batch), set()
                current, raw, count, previous_size = None, bytearray(), 0, None
                after_digest, after_index = '', -1

                def finish():
                    nonlocal result
                    if current is None:
                        return
                    content = bytes(raw)
                    expected_count = max(1, (len(content) + self.CHUNK_BYTES - 1) // self.CHUNK_BYTES)
                    if count != expected_count or sha256(content).hexdigest() != current:
                        raise AutonomousStoreError('Persistent source bytes or chunk roster differ from their hash.')
                    self._remember(current, content)
                    seen.add(current)
                    if current == return_digest:
                        result = content

                placeholders = ','.join('?' for _ in batch)
                query = ('SELECT sha256,chunk_index,length(content) AS size_bytes,'
                         "CASE WHEN typeof(content)='blob' AND length(content)<=? THEN content ELSE NULL END AS content "
                         'FROM autonomous_source_chunks WHERE sha256 IN (' + placeholders + ') '
                         'AND (sha256>? OR (sha256=? AND chunk_index>?)) '
                         'ORDER BY sha256,chunk_index LIMIT 8')
                max_pages = (len(batch) * max_chunks + self.PAGE_CHUNKS - 1) // self.PAGE_CHUNKS + 1
                for _ in range(max_pages):
                    page = db.execute(query, (self.CHUNK_BYTES, *batch, after_digest, after_digest, after_index)).fetchall()
                    if len(page) > self.PAGE_CHUNKS:
                        raise AutonomousStoreError('Persistent source page exceeds its bound.')
                    for row in page:
                        digest, index, size, chunk = (row[key] for key in ('sha256', 'chunk_index', 'size_bytes', 'content'))
                        if (digest not in wanted or type(index) is not int or type(size) is not int
                                or not isinstance(chunk, bytes) or not 0 <= size <= self.CHUNK_BYTES or len(chunk) != size
                                or (digest, index) <= (after_digest, after_index)):
                            raise AutonomousStoreError('Persistent source chunk identity or size is invalid.')
                        if digest != current:
                            finish()
                            current, raw, count, previous_size = digest, bytearray(), 0, None
                        if (index != count or count >= max_chunks
                                or previous_size is not None and previous_size != self.CHUNK_BYTES
                                or len(raw) + size > MAX_FILE_BYTES):
                            raise AutonomousStoreError('Persistent original source chunk roster is incomplete or oversized.')
                        raw.extend(chunk)
                        count, previous_size = count + 1, size
                        after_digest, after_index = digest, index
                    if len(page) < self.PAGE_CHUNKS:
                        break
                else:
                    raise AutonomousStoreError('Persistent source chunk roster exceeds its bound.')
                finish()
                if seen != wanted:
                    raise AutonomousStoreError('Persistent original source bytes are incomplete.')
        return result

    def read(self, digest):
        self._digests([digest])
        with self._lock:
            cached = self._cache.get(digest)
            if cached is not None:
                self._cache.move_to_end(digest)
                return cached
            return self._fetch_many([digest], return_digest=digest)

    def read_many(self, digests):
        """Populate only missing byte-cache entries; this admits no evidence."""
        values = self._digests(digests)
        with self._lock:
            missing = [digest for digest in values if digest not in self._cache]
            if missing:
                self._fetch_many(missing)

    def prefetch_journal_sources(self, rows):
        """Bounded byte lookups from the same rows the existing engine will replay.

        Source descriptors are checked before a lookup, but no event or state is
        accepted here. Full chain/reducer validation and the fresh final source
        verification remain mandatory before any journal result is returned.
        """
        digests = set()
        for row in rows:
            try:
                event = json.loads(row['event_json'])
                if event.get('kind') not in {'intake', 'sources.arrived'}:
                    continue
                sources = event['payload']['sources']
                if not isinstance(sources, list) or not 1 <= len(sources) <= 21:
                    raise AutonomousStoreError('Journal source lookup roster is invalid.')
                for descriptor in sources:
                    AutonomousStore._descriptor_metadata(descriptor, event['claim_id'])
                    digests.add(descriptor['sha256'])
            except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
                raise AutonomousStoreError('Journal source lookup is malformed.') from exc
        self.read_many(digests)

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
            values = self._digests(digests)
            for digest in values:
                cached = self._cache.pop(digest, None)
                if cached is not None:
                    self._size -= len(cached)
            if values:
                self._fetch_many(values)


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


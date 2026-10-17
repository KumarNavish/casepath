"""Direct libSQL persistence for ephemeral compute; no local write replica.

The remote primary commits reservations before the existing model adapter may
send HTTP. A failed or ambiguous database operation is never retried here.
"""
from collections import OrderedDict
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from types import MethodType

from .autonomous_store_v1 import AutonomousStore, AutonomousStoreError, MAX_FILE_BYTES, SESSION_ID


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


# Proofs are derived from validated raw SQL values, never journal heads or JSON.
# Fixed-width typed cells and row digests make the ordered aggregate injective
# up to SHA-256; the count/length checks reject missing or malformed digests.
_PROOF_ROWS = 16384
_JOURNAL_COLUMNS = ('session_id', 'loop_id', 'sequence', 'idempotency_key',
                    'command_sha256', 'event_sha256', 'event_json', 'created_at')
_SOURCE_COLUMNS = ('sha256', 'chunk_index', 'content')


def _schema_query(table):
    return ("SELECT 'column' AS kind,name,type AS detail,\"notnull\" AS required,dflt_value AS default_value,pk,hidden "
            "FROM pragma_table_xinfo('" + table + "') UNION ALL "
            "SELECT type,name,sql,NULL,NULL,NULL,NULL FROM sqlite_schema WHERE tbl_name='" + table + "' "
            "ORDER BY kind,name")


def _schema_identity(rows):
    return tuple(tuple((key, type(row[key]), row[key]) for key in row.keys()) for row in rows)


def _standard_schema(rows, columns):
    expected_keys = ('kind', 'name', 'detail', 'required', 'default_value', 'pk', 'hidden')
    if any(tuple(row.keys()) != expected_keys for row in rows):
        return False
    names = {row['name']: row for row in rows if row['kind'] == 'column'}
    if set(names) != set(columns):
        return False
    integer = 'sequence' if columns == _JOURNAL_COLUMNS else 'chunk_index'
    keys = ('session_id', 'loop_id', 'sequence') if columns == _JOURNAL_COLUMNS else ('sha256', 'chunk_index')
    for name in columns:
        row = names[name]
        expected = 'INTEGER' if name == integer else 'BLOB' if name == 'content' else 'TEXT'
        if (type(row['detail']) is not str or row['detail'].upper() != expected
                or type(row['required']) is not int or row['required'] != 1
                or row['default_value'] is not None or type(row['pk']) is not int
                or row['pk'] != (keys.index(name) + 1 if name in keys else 0)
                or type(row['hidden']) is not int or row['hidden'] != 0):
            return False
    tables = [row for row in rows if row['kind'] in {'table', 'view'}]
    return (len(tables) == 1 and tables[0]['kind'] == 'table' and isinstance(tables[0]['detail'], str)
            and tables[0]['detail'].lstrip().upper().startswith('CREATE TABLE '))


def _cell_frame(value):
    if type(value) is str:
        kind, raw = 't', value.encode('utf-8')
    elif type(value) is int and -(2 ** 63) <= value < 2 ** 63:
        kind, raw = 'i', str(value).encode('ascii')
    elif type(value) is bytes:
        kind, raw = 'b', value
    else:
        raise ValueError('Value is not eligible for an exact SQL byte proof.')
    return kind + format(len(raw), '016x') + sha256(raw).hexdigest()


def _proof_expected(rows, columns, domain):
    if len(rows) > _PROOF_ROWS:
        raise ValueError('Proof roster exceeds its bound.')
    integer = 'sequence' if columns == _JOURNAL_COLUMNS else 'chunk_index'
    hashes = []
    for row in rows:
        if set(row.keys()) != set(columns):
            raise ValueError('Proof cannot omit an unknown SQL column.')
        for name in columns:
            expected = int if name == integer else bytes if name == 'content' else str
            if type(row[name]) is not expected:
                raise ValueError('Proof requires exact native SQL storage types.')
        hashes.append(sha256((domain + ':row:' + ''.join(_cell_frame(row[name]) for name in columns)).encode('ascii')).hexdigest())
    return (len(rows), len(rows), len(rows) * 64,
            sha256((domain + ':set:' + ''.join(hashes)).encode('ascii')).hexdigest())


def _proof_query(table, columns, domain, where, order):
    frames = []
    for name in columns:
        raw = 'COALESCE(CAST(' + name + " AS BLOB),X'')"
        frames.append("(CASE typeof(" + name + ") WHEN 'text' THEN 't' WHEN 'integer' THEN 'i' "
                      "WHEN 'blob' THEN 'b' WHEN 'real' THEN 'r' WHEN 'null' THEN 'n' ELSE '?' END)"
                      "||printf('%016x',length(" + raw + "))||lower(hex(crypto_sha256(" + raw + ')))')
    # ORDER BY + LIMIT is a non-flattening barrier: aggregation consumes the
    # canonical complete-PK order, bounded to the cached roster plus one row.
    return ("SELECT count(*) AS n,COALESCE(sum(CASE WHEN length(row_sha)=64 AND row_sha NOT GLOB '*[^0-9a-f]*' "
            "THEN 1 ELSE 0 END),0) AS valid_n,length(CAST(COALESCE(group_concat(row_sha,''),'') AS BLOB)) AS concat_bytes,"
            "lower(hex(crypto_sha256(CAST('" + domain + ":set:'||COALESCE(group_concat(row_sha,''),'') AS BLOB)))) AS root "
            "FROM (SELECT lower(hex(crypto_sha256(CAST('" + domain + ":row:'||" + '||'.join(frames) +
            ' AS BLOB)))) AS row_sha FROM ' + table + ' WHERE ' + where + ' ORDER BY ' + order + ' LIMIT ?)')


def _proof_matches(cursor, expected):
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise AutonomousStoreError('Fresh SQL byte proof has an invalid result roster.')
    row = rows[0]
    values = tuple(row[key] for key in ('n', 'valid_n', 'concat_bytes', 'root'))
    if (any(type(value) is not int for value in values[:3]) or not 0 <= values[0] <= _PROOF_ROWS + 1
            or values[1] != values[0] or values[2] != values[0] * 64
            or type(values[3]) is not str or len(values[3]) != 64
            or any(char not in '0123456789abcdef' for char in values[3])):
        raise AutonomousStoreError('Fresh SQL byte proof is malformed or truncated.')
    return values == expected


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

    def _fetch_many(self, digests, *, return_digest=None, check=lambda: None, page_chunks=None):
        """Read all requested chunks with bounded pages on one connection.

        Eight 256-KiB blobs cap a page at two MiB before wire encoding. Oversize
        or wrongly typed chunks return metadata and NULL rather than an unbounded
        blob. Keyset pagination verifies ordering and cannot skip a later-page
        gap. Keep one file buffer at a time and retain the existing bounded cache.
        """
        max_chunks = (MAX_FILE_BYTES + self.CHUNK_BYTES - 1) // self.CHUNK_BYTES
        compact_pages = page_chunks is not None
        if compact_pages and (type(page_chunks) is not int or not self.PAGE_CHUNKS <= page_chunks <= 128):
            raise AutonomousStoreError('Persistent source page row bound is invalid.')
        page_chunks = self.PAGE_CHUNKS if page_chunks is None else page_chunks
        result = None
        check()
        with self.connect() as db:
            read_once = getattr(db, 'execute_read_once', None)
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
                if compact_pages:
                    # Knowledge can collect many small originals in one page,
                    # while retaining the existing two-MiB raw blob budget.
                    # Invalid blobs return metadata and NULL, just as above.
                    query = ('SELECT sha256,chunk_index,size_bytes,content,__candidate_count FROM '
                             '(SELECT *,sum(__page_bytes) OVER (ORDER BY sha256,chunk_index) AS __total,'
                             'row_number() OVER (ORDER BY sha256,chunk_index) AS __position,count(*) OVER () AS __candidate_count FROM '
                             '(SELECT sha256,chunk_index,length(content) AS size_bytes,'
                             "CASE WHEN typeof(content)='blob' AND length(content)<=? THEN content ELSE NULL END AS content,"
                             "CASE WHEN typeof(content)='blob' AND length(content)<=? THEN length(content) ELSE 0 END AS __page_bytes "
                             'FROM autonomous_source_chunks WHERE sha256 IN (' + placeholders + ') '
                             'AND (sha256>? OR (sha256=? AND chunk_index>?)) '
                             'ORDER BY sha256,chunk_index LIMIT ?)) '
                             'WHERE __total<=? OR __position=1 ORDER BY sha256,chunk_index')
                max_pages = (len(batch) * max_chunks + self.PAGE_CHUNKS - 1) // self.PAGE_CHUNKS + 1
                for _ in range(max_pages):
                    check()
                    parameters = ((self.CHUNK_BYTES, self.CHUNK_BYTES, *batch, after_digest, after_digest, after_index,
                                   page_chunks, 2 * 1024 * 1024) if compact_pages else
                                  (self.CHUNK_BYTES, *batch, after_digest, after_digest, after_index))
                    # Bulk raw bodies explicitly retire their HTTP socket;
                    # compact proofs keep the shared pool. Local SQLite keeps
                    # its ordinary execute API and receives no transport flag.
                    page = (read_once(query, parameters, close_http=True) if read_once is not None
                            else db.execute(query, parameters)).fetchall()
                    if len(page) > page_chunks:
                        raise AutonomousStoreError('Persistent source page exceeds its bound.')
                    if compact_pages and sum(len(row['content']) for row in page if isinstance(row['content'], bytes)) > 2 * 1024 * 1024:
                        raise AutonomousStoreError('Persistent source page exceeds its byte bound.')
                    if compact_pages and page and any(type(row['__candidate_count']) is not int
                            or not len(page) <= row['__candidate_count'] <= page_chunks
                            or row['__candidate_count'] != page[0]['__candidate_count'] for row in page):
                        raise AutonomousStoreError('Persistent source page count is invalid.')
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
                    # A short page establishes EOF only if its SQL candidate
                    # count also proves the byte cap did not truncate it.
                    if (not page or not compact_pages and len(page) < self.PAGE_CHUNKS
                            or compact_pages and len(page) < page_chunks and page[0]['__candidate_count'] == len(page)):
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

    def read_many(self, digests, *, page_chunks=None):
        """Populate only missing byte-cache entries; this admits no evidence."""
        values = self._digests(digests)
        with self._lock:
            missing = [digest for digest in values if digest not in self._cache]
            if missing:
                self._fetch_many(missing, page_chunks=page_chunks)

    def prefetch_journal_sources(self, rows, *, page_chunks=None):
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
        self.read_many(digests, page_chunks=page_chunks)

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

    def verify_many(self, digests, *, check=lambda: None, page_chunks=None):
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
                self._fetch_many(values, check=check, page_chunks=page_chunks)


    def _knowledge_source_queries(self, values):
        queries, expected = [(_schema_query('autonomous_source_chunks'), ())], []
        for start in range(0, len(values), self.BATCH_DIGESTS):
            batch = values[start:start + self.BATCH_DIGESTS]
            rows = []
            for digest in batch:
                raw = self._cache.get(digest)
                if raw is None:
                    raise AutonomousStoreError('Original byte proof cache was evicted before verification.')
                rows.extend({'sha256': digest, 'chunk_index': index, 'content': raw[offset:offset + self.CHUNK_BYTES]}
                            for index, offset in enumerate(range(0, max(1, len(raw)), self.CHUNK_BYTES)))
            if len(rows) > _PROOF_ROWS or len(queries) >= 128:
                raise AutonomousStoreError('Original byte proof roster exceeds its bound.')
            expected.append(_proof_expected(rows, _SOURCE_COLUMNS, 'casepath-source-bytes-v1'))
            query = _proof_query('autonomous_source_chunks', _SOURCE_COLUMNS, 'casepath-source-bytes-v1',
                                 'sha256 IN (' + ','.join('?' for _ in batch) + ')', 'sha256,chunk_index')
            queries.append((query, (*batch, len(rows) + 1)))
        return queries, expected

    def _knowledge_source_proof(self, values):
        queries, expected = self._knowledge_source_queries(values)
        with self.connect() as db:
            if not hasattr(db, 'read_snapshot'):
                return None
            cursors = db.read_snapshot(queries)
        schema = cursors[0].fetchall()
        if not _standard_schema(schema, _SOURCE_COLUMNS):
            raise AutonomousStoreError('Original byte proof requires the complete native source schema.')
        return _schema_identity(schema), cursors[1:], expected

    def verify_knowledge_many(self, digests):
        """New post-reducer snapshot proves every cached original chunk byte.

        Cache bytes already passed the native full-file SHA and chunk validators.
        Missing/evicted bytes and schema changes use the original eight-chunk
        reader, followed by a new coherent certificate. Exact schema identity is
        admitted only by the successful journal post-validation hook.
        """
        values = self._digests(digests)
        with self._lock:
            if not values:
                return
            missing = [digest for digest in values if digest not in self._cache]
            if missing:
                self._fetch_many(missing)
            result = self._knowledge_source_proof(values)
            if result is None:
                self.verify_many(values)
                return
            schema, cursors, expected = result
            previous = getattr(self, '_knowledge_schema', None)
            if previous is not None and previous != schema:
                # A confirmed schema miss is not a transport retry. Revalidate
                # all raw bytes and then certify them in a NEW final snapshot.
                self.verify_many(values)
                fresh = self._knowledge_source_proof(values)
                if fresh is None or fresh[0] != schema:
                    raise AutonomousStoreError('Original byte schema changed during fresh verification.')
                schema, cursors, expected = fresh
            if not all(_proof_matches(cursor, proof) for cursor, proof in zip(cursors, expected)):
                self.verify_many(values)
                raise AutonomousStoreError('Persistent source bytes changed during fresh verification.')
            return schema


class HostedAutonomousStore(AutonomousStore):
    JOURNAL_PAGE_ROWS = 128
    KNOWLEDGE_PAGE_ROWS = 2048
    JOURNAL_PAGE_BYTES = 4 * 1024 * 1024
    JOURNAL_ROW_BYTES = JOURNAL_PAGE_BYTES + 64 * 1024
    KNOWLEDGE_RAW_PAGE_BYTES = 256 * 1024

    def list(self, *, statuses=None):
        # Startup discovery needs the same full accepted states as knowledge,
        # without per-claim remote reads. Scheduling semantics remain with the
        # controller; this read never admits or resumes work itself.
        return [state for state in self.validated_states()
                if statuses is None or state['status'] in statuses]

    def _state_rows(self):
        return self._paged_state_rows(self.JOURNAL_PAGE_ROWS)

    def _validated_summary_states(self):
        # Collection and Knowledge share one certified raw-row authority path,
        # under the existing ordered summary lock and final source verification.
        return self._validated_knowledge_snapshot()[1]

    def _validated_knowledge_snapshot(self):
        self._knowledge_pending = None
        cached = getattr(self, '_knowledge_byte_cache', None)
        sources = self._source_store
        journal_connect, source_connect = self.journal.connect, getattr(sources, 'connect', None)
        same_primary = (journal_connect is source_connect or
                        isinstance(journal_connect, MethodType) and isinstance(source_connect, MethodType)
                        and journal_connect.__self__ is source_connect.__self__
                        and journal_connect.__func__ is source_connect.__func__)
        if cached is not None and isinstance(sources, HostedSources) and same_primary:
            # Summary -> source is the existing lock order. Keep every cached
            # original present and unchanged through local validation, the final
            # atomic certificate, and admission. A candidate has no authority.
            with sources._lock:
                result = self._cached_knowledge_snapshot(cached, sources)
                if result is not None:
                    return result
        return super()._validated_knowledge_snapshot()

    def _cached_knowledge_snapshot(self, cached, sources):
        frozen_rows, schema, proof = cached
        rows = [dict(row) for row in frozen_rows]
        streams = {}
        for row in rows:
            streams.setdefault(row['loop_id'].removeprefix('autonomous.'), []).append(row)
        summaries = getattr(self, '_summary_cache', {})
        if (set(summaries) != set(streams) or any(
                summaries[claim_id][0] != self._journal_snapshot(claim_rows)
                for claim_id, claim_rows in streams.items())):
            return None
        digests = sources._digests(source['sha256'] for claim_id in streams
                                  for source in summaries[claim_id][1]['source_descriptors'])
        source_schema = getattr(sources, '_knowledge_schema', None)
        # The combined request has two journal SELECTs and one source schema
        # SELECT, leaving 125 source batches. Larger rosters retain the original
        # separate certificates and their unchanged 128-SELECT bounds.
        if (not digests or source_schema is None or any(digest not in sources._cache for digest in digests)
                or len(digests) > 125 * sources.BATCH_DIGESTS):
            return None
        certified = []

        def verify(current_digests):
            if sources._digests(current_digests) != digests:
                raise AutonomousStoreError('Validated source roster differs from the cached candidate.')
            source_queries, expected = sources._knowledge_source_queries(digests)
            query = _proof_query('claim_loop_events', _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1',
                                 'session_id=?', 'loop_id,sequence')
            with self.journal.connect() as db:
                if not hasattr(db, 'read_snapshot'):
                    return
                cursors = db.read_snapshot([(_schema_query('claim_loop_events'), ()),
                    (query, (SESSION_ID, len(rows) + 1)), *source_queries])
            if len(cursors) != 3 + len(expected):
                raise AutonomousStoreError('Atomic byte proof has an invalid result roster.')
            current_schema = cursors[0].fetchall()
            current_sources = cursors[2].fetchall()
            # Only a confirmed schema/byte mismatch may take the old bounded
            # path. Transport failures, malformed roots and unconfirmed COMMIT
            # propagate directly; they never authorize a retry or a payload.
            journal_matches = _proof_matches(cursors[1], proof)
            if (not _standard_schema(current_schema, _JOURNAL_COLUMNS)
                    or _schema_identity(current_schema) != schema
                    or not journal_matches):
                self._knowledge_byte_cache = None
                return
            if (not _standard_schema(current_sources, _SOURCE_COLUMNS)
                    or _schema_identity(current_sources) != source_schema):
                return
            source_matches = [_proof_matches(cursor, value) for cursor, value in zip(cursors[3:], expected)]
            if not all(source_matches):
                sources.verify_many(digests)
                raise AutonomousStoreError('Persistent source bytes changed during fresh verification.')
            certified.append(True)

        # This performs the same complete row identity and descriptor/original
        # hash checks as the old warm path, before any final snapshot is read.
        states = self._validated_states(rows, source_verifier=verify)
        if not certified:
            return None
        self._knowledge_pending = cached
        self._after_validated_knowledge_states(rows, states)
        return rows, states

    def _knowledge_rows(self):
        self._knowledge_pending = None
        cached = getattr(self, '_knowledge_byte_cache', None)
        if cached is not None:
            with self.journal.connect() as db:
                frozen_rows, schema, proof = cached
                query = _proof_query('claim_loop_events', _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1',
                                     'session_id=?', 'loop_id,sequence')
                schema_cursor, proof_cursor = db.read_snapshot([
                    (_schema_query('claim_loop_events'), ()), (query, (SESSION_ID, len(frozen_rows) + 1))])
                current_schema = schema_cursor.fetchall()
                if (_standard_schema(current_schema, _JOURNAL_COLUMNS)
                        and _schema_identity(current_schema) == schema and _proof_matches(proof_cursor, proof)):
                    self._knowledge_pending = cached
                    return [dict(row) for row in frozen_rows]
        self._knowledge_byte_cache = None
        return self._collect_knowledge_rows()

    def _collect_knowledge_rows(self):
        # Each bounded raw page is independently CLOSED by the server. Never
        # hold Turso's five-second transaction across raw body transfers.
        # A final fresh complete-roster certificate supplies snapshot authority.
        rows, after_loop, after_sequence = [], '', -1
        schema = None
        while True:
            query, parameters = self._journal_page_query(self.JOURNAL_PAGE_ROWS, rows, after_loop, after_sequence)
            with self.journal.connect() as db:
                if not hasattr(db, 'read_snapshot'):
                    return self._state_rows()
                queries = [(query, parameters)]
                if schema is None:
                    queries.insert(0, (_schema_query('claim_loop_events'), ()))
                cursors = db.read_snapshot(queries, close_http=True)
            if schema is None:
                schema = cursors[0].fetchall()
                if not _standard_schema(schema, _JOURNAL_COLUMNS):
                    # An eight-column root cannot certify unknown authority.
                    # Do not replace a bounded cold read with an unbounded raw
                    # body or an interactive transaction spanning transfers.
                    self._knowledge_pending = None
                    raise AutonomousStoreError('Knowledge byte proof requires the complete native journal schema.')
            page = cursors[-1].fetchall()
            if not page:
                break
            if len(page) > self.JOURNAL_PAGE_ROWS:
                raise AutonomousStoreError('Journal read page exceeds its bound.')
            for row in page:
                loop, sequence, size = (row[key] for key in ('loop_id', 'sequence', '__read_size'))
                if (type(loop) is not str or not loop.startswith('autonomous.') or type(sequence) is not int
                        or sequence < 1 or type(size) is not int or not 0 < size <= self.JOURNAL_ROW_BYTES
                        or (loop, sequence) <= (after_loop, after_sequence)):
                    raise AutonomousStoreError('Journal read page identity or size differs.')
                rows.append({key: row[key] for key in row.keys()
                             if key not in {'__read_size', '__read_total', '__read_position'}})
                after_loop, after_sequence = loop, sequence
            if len(rows) > _PROOF_ROWS:
                raise AutonomousStoreError('Journal byte proof roster exceeds its bound.')
        try:
            proof = _proof_expected(rows, _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1')
        except (ValueError, UnicodeError) as exc:
            raise AutonomousStoreError('Journal raw values cannot establish an exact byte proof.') from exc
        query = _proof_query('claim_loop_events', _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1',
                             'session_id=?', 'loop_id,sequence')
        with self.journal.connect() as db:
            schema_cursor, proof_cursor = db.read_snapshot([
                (_schema_query('claim_loop_events'), ()), (query, (SESSION_ID, len(rows) + 1))])
        if _schema_identity(schema_cursor.fetchall()) != _schema_identity(schema) or not _proof_matches(proof_cursor, proof):
            raise AutonomousStoreError('Journal changed while collecting independently closed raw pages.')
        # Every eligible value is immutable str/int. Keep private tuple rows;
        # callers and validators receive separate dictionaries, never aliases.
        self._knowledge_pending = (tuple(tuple(row.items()) for row in rows), _schema_identity(schema), proof)
        return rows

    def _validated_knowledge_states(self, rows):
        if not isinstance(self._source_store, HostedSources):
            return self._validated_states(rows)
        schemas = []

        def verify(digests):
            schemas.append(self._source_store.verify_knowledge_many(digests))

        states = self._validated_states(rows, source_verifier=verify)
        # Admit only after _validated_states returned, using the certificate
        # returned by this call rather than a shared temporary source mode.
        with self._source_store._lock:
            self._source_store._knowledge_schema = schemas[0]
        return states

    def _after_validated_knowledge_states(self, rows, states):
        # _summary_cache alone is insufficient: it is populated before final
        # source verification. Only this successful post-validation hook admits.
        pending = getattr(self, '_knowledge_pending', None)
        if pending is not None:
            try:
                same = (tuple(tuple(row.items()) for row in rows) == pending[0]
                        and _proof_expected(rows, _JOURNAL_COLUMNS, 'casepath-journal-bytes-v1') == pending[2])
            except (ValueError, UnicodeError):
                same = False
            if not same:
                self._knowledge_byte_cache = self._knowledge_pending = None
                raise AutonomousStoreError('Certified journal bytes differ from the fully validated rows.')
        self._knowledge_byte_cache = pending

    def _journal_page_query(self, page_rows, rows, after_loop, after_sequence):
        size = '+'.join('COALESCE(length(CAST(' + key + ' AS BLOB)),0)' for key in _JOURNAL_COLUMNS) + '+1024'
        query = ('SELECT j.*,p.__read_size,p.__read_total,p.__read_position FROM '
                 '(SELECT *,sum(__read_size) OVER (ORDER BY loop_id,sequence) AS __read_total,'
                 'row_number() OVER (ORDER BY loop_id,sequence) AS __read_position FROM '
                 '(SELECT session_id,loop_id,sequence,(' + size + ') AS __read_size FROM claim_loop_events WHERE session_id=? '
                 'AND (? OR loop_id>? OR (loop_id=? AND sequence>?)) '
                 'ORDER BY loop_id,sequence LIMIT ?)) AS p CROSS JOIN claim_loop_events AS j '
                 'WHERE (p.__read_total<=? OR p.__read_position=1) '
                 'AND j.session_id=p.session_id AND j.loop_id=p.loop_id AND j.sequence=p.sequence '
                 'ORDER BY p.loop_id,p.sequence')
        return query, (SESSION_ID, not rows, after_loop, after_loop, after_sequence, page_rows,
                       min(self.JOURNAL_PAGE_BYTES, self.KNOWLEDGE_RAW_PAGE_BYTES))

    def _paged_state_rows(self, page_rows, *, count_candidates=False):
        """Bounded journal pages from one read snapshot, before source work.

        The raw byte budget leaves room for Hrana's JSON escaping within its
        existing transport bound. Pagination includes every SQL column; the
        temporary size/order columns never enter the accepted-state cache.
        """
        columns = ('session_id', 'loop_id', 'sequence', 'idempotency_key',
                   'command_sha256', 'event_sha256', 'event_json', 'created_at')
        size = '+'.join('COALESCE(length(CAST(' + key + ' AS BLOB)),0)' for key in columns) + '+1024'
        # Keep SELECT as the outer verb so owned workflow connections recognize
        # this as a read without weakening their fenced-write guard.
        count = ',count(*) OVER () AS __read_candidates' if count_candidates else ''
        query = ('SELECT * FROM (SELECT *,sum(__read_size) OVER (ORDER BY loop_id,sequence) AS __read_total,'
                 'row_number() OVER (ORDER BY loop_id,sequence) AS __read_position' + count + ' FROM '
                 '(SELECT *,(' + size + ') AS __read_size FROM claim_loop_events WHERE session_id=? '
                 'AND (? OR loop_id>? OR (loop_id=? AND sequence>?)) '
                 'ORDER BY loop_id,sequence LIMIT ?)) '
                 'WHERE __read_total<=? OR __read_position=1 ORDER BY loop_id,sequence')
        if count_candidates:
            # Knowledge windows only keys and sizes. Carrying every payload
            # through the window materializes the entire candidate roster
            # before the byte cut. Fetch complete rows after that cut in this
            # same snapshot; j.* retains every authority column for the cache.
            query = ('SELECT j.*,p.__read_size,p.__read_total,p.__read_position,p.__read_candidates FROM '
                     '(SELECT *,sum(__read_size) OVER (ORDER BY loop_id,sequence) AS __read_total,'
                     'row_number() OVER (ORDER BY loop_id,sequence) AS __read_position' + count + ' FROM '
                     '(SELECT session_id,loop_id,sequence,(' + size + ') AS __read_size FROM claim_loop_events WHERE session_id=? '
                     'AND (? OR loop_id>? OR (loop_id=? AND sequence>?)) ORDER BY loop_id,sequence LIMIT ?)) AS p '
                     'CROSS JOIN claim_loop_events AS j WHERE (p.__read_total<=? OR p.__read_position=1) '
                     'AND j.session_id=p.session_id AND j.loop_id=p.loop_id AND j.sequence=p.sequence ORDER BY p.loop_id,p.sequence')
        rows, after_loop, after_sequence = [], '', -1
        with self.journal.connect() as connection:
            # A read transaction fixes the accepted head across all pages. It
            # ends before replay/extraction/source checks and never renews a
            # writer lease or acquires an IMMEDIATE transaction.
            connection.execute('BEGIN')
            while True:
                page = connection.execute(query, (SESSION_ID, not rows, after_loop, after_loop, after_sequence,
                                                  page_rows, self.JOURNAL_PAGE_BYTES)).fetchall()
                if not page:
                    break
                if len(page) > page_rows:
                    raise AutonomousStoreError('Journal read page exceeds its bound.')
                if count_candidates and any(type(row['__read_candidates']) is not int
                        or not len(page) <= row['__read_candidates'] <= page_rows
                        or row['__read_candidates'] != page[0]['__read_candidates'] for row in page):
                    raise AutonomousStoreError('Journal read page count is invalid.')
                for row in page:
                    loop, sequence, byte_size = (row[key] for key in ('loop_id', 'sequence', '__read_size'))
                    if (not isinstance(loop, str) or not loop.startswith('autonomous.')
                            or type(sequence) is not int or sequence < 1
                            or type(byte_size) is not int or not 0 < byte_size <= self.JOURNAL_ROW_BYTES
                            or (loop, sequence) <= (after_loop, after_sequence)):
                        raise AutonomousStoreError('Journal read page identity or size differs.')
                    rows.append({key: row[key] for key in row.keys()
                                 if key not in {'__read_size', '__read_total', '__read_position', '__read_candidates'}})
                    after_loop, after_sequence = loop, sequence
                if count_candidates and len(page) < page_rows and page[0]['__read_candidates'] == len(page):
                    break
            connection.commit()
        return rows

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


"""Immutable operation sidecars; public readers never create or admit traces.

The operator verifies a sidecar by native recomputation before admission. Its
transaction then compares the exact exported journal rows before inserting only
the new sidecar tables. Earlier events, sources and Knowledge remain untouched.
"""
from hashlib import sha256
import gzip
import json
import re
import zlib

from .autonomous_store_v1 import SESSION_ID
from .workspace_corpus import canonical_json_bytes, digest_value

MAX_TRACE_BYTES = 24 * 1024 * 1024
CHUNK_BYTES = 128 * 1024
PAGE_CHUNKS = 8
_HASH = re.compile(r'[a-f0-9]{64}')
_COLUMNS = ('session_id', 'loop_id', 'sequence', 'idempotency_key',
            'command_sha256', 'event_sha256', 'event_json', 'created_at')
SCHEMA = """
CREATE TABLE IF NOT EXISTS autonomous_operation_traces (
 sidecar_sha256 TEXT PRIMARY KEY, claim_id TEXT NOT NULL, run_id TEXT NOT NULL,
 head_state_sha256 TEXT NOT NULL, head_event_sha256 TEXT NOT NULL,
 profile_sha256 TEXT NOT NULL, input_sha256 TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, compressed_sha256 TEXT NOT NULL,
 content_bytes INTEGER NOT NULL, compressed_bytes INTEGER NOT NULL,
 chunk_count INTEGER NOT NULL,
 UNIQUE(claim_id,run_id,head_state_sha256,head_event_sha256,profile_sha256)
);
CREATE TABLE IF NOT EXISTS autonomous_operation_trace_chunks (
 sidecar_sha256 TEXT NOT NULL, chunk_index INTEGER NOT NULL, content BLOB NOT NULL,
 PRIMARY KEY(sidecar_sha256,chunk_index)
);
"""
for _table in ('autonomous_operation_traces', 'autonomous_operation_trace_chunks'):
    SCHEMA += f"""
CREATE TRIGGER IF NOT EXISTS {_table}_no_update BEFORE UPDATE ON {_table}
 BEGIN SELECT RAISE(ABORT,'operation traces are immutable'); END;
CREATE TRIGGER IF NOT EXISTS {_table}_no_delete BEFORE DELETE ON {_table}
 BEGIN SELECT RAISE(ABORT,'operation traces are immutable'); END;
"""
    _key = ('sidecar_sha256=NEW.sidecar_sha256 OR (claim_id=NEW.claim_id AND run_id=NEW.run_id '
            'AND head_state_sha256=NEW.head_state_sha256 AND head_event_sha256=NEW.head_event_sha256 '
            'AND profile_sha256=NEW.profile_sha256)' if _table.endswith('traces') else
            'sidecar_sha256=NEW.sidecar_sha256 AND chunk_index=NEW.chunk_index')
    SCHEMA += f"""
CREATE TRIGGER IF NOT EXISTS {_table}_no_replace BEFORE INSERT ON {_table}
 WHEN EXISTS(SELECT 1 FROM {_table} WHERE {_key})
 BEGIN SELECT RAISE(ABORT,'operation traces are immutable'); END;
"""


class OperationTraceError(ValueError):
    pass


def initialize_operation_trace_storage(connection_factory):
    """Explicit private operator setup; never called by a public reader."""
    with connection_factory() as connection:
        connection.executescript(SCHEMA)


def _sealed(sidecar):
    if not isinstance(sidecar, dict) or sidecar.get('contract') != 'casepath.operation-sidecar/1.0.0':
        raise OperationTraceError('Operation sidecar contract differs.')
    material = {key: value for key, value in sidecar.items() if key != 'sidecar_sha256'}
    if (set(sidecar) != {'contract', 'input_sha256', 'frames', 'sidecar_sha256'}
            or not isinstance(sidecar['input_sha256'], str)
            or not _HASH.fullmatch(sidecar['input_sha256'])
            or sidecar['sidecar_sha256'] != digest_value(material)):
        raise OperationTraceError('Operation sidecar content seal differs.')
    frames = sidecar['frames']
    if (not isinstance(frames, list) or len(frames) < 2 or any(not isinstance(frame, dict) for frame in frames)
            or frames[0].get('type') != 'binding' or frames[-1].get('type') != 'result'):
        raise OperationTraceError('Operation sidecar is incomplete.')
    binding, result = frames[0], frames[-1]
    if (binding.get('input_sha256') != sidecar['input_sha256']
            or result.get('exact_output_verified') is not True
            or result.get('state_sha256') != binding.get('current_state_sha256')
            or result.get('current_event_sha256') != binding.get('current_event_sha256')
            or result.get('current_revision') != binding.get('current_revision')
            or result.get('trace_sha256') != digest_value([digest_value(frame) for frame in frames[:-1]])):
        raise OperationTraceError('Operation sidecar final binding differs.')
    for key in ('current_state_sha256', 'current_event_sha256', 'profile_sha256'):
        if not isinstance(binding.get(key), str) or not _HASH.fullmatch(binding[key]):
            raise OperationTraceError('Operation sidecar authority is invalid.')
    if not all(isinstance(binding.get(key), str) and binding[key] for key in ('claim_id', 'run_id')):
        raise OperationTraceError('Operation sidecar claim/run identity is invalid.')
    encoded = canonical_json_bytes(sidecar)
    if len(encoded) > MAX_TRACE_BYTES:
        raise OperationTraceError('Operation sidecar exceeds its byte bound.')
    return binding, encoded


class OperationTraceStore:
    def __init__(self, connection_factory):
        self.connect = connection_factory

    def read(self, claim_id, *, head_state_sha256, head_event_sha256, run_id, profile_sha256, check=lambda: None):
        """Read one exact admitted trace, refusing damaged or oversized chunks."""
        identity = (claim_id, run_id, head_state_sha256, head_event_sha256, profile_sha256)
        check()
        with self.connect() as connection:
            check()
            if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                                  ('autonomous_operation_traces',)).fetchone() is None:
                return None
            check()
            row = connection.execute('SELECT * FROM autonomous_operation_traces WHERE claim_id=? AND run_id=? '
                                     'AND head_state_sha256=? AND head_event_sha256=? AND profile_sha256=?', identity).fetchone()
            if row is None:
                return None
            if (type(row['content_bytes']) is not int or not 0 < row['content_bytes'] <= MAX_TRACE_BYTES
                    or type(row['compressed_bytes']) is not int or not 0 < row['compressed_bytes'] <= MAX_TRACE_BYTES
                    or type(row['chunk_count']) is not int
                    or row['chunk_count'] != (row['compressed_bytes'] + CHUNK_BYTES - 1) // CHUNK_BYTES):
                raise OperationTraceError('Persisted operation trace size is invalid.')
            compressed, after = bytearray(), -1
            while True:
                check()
                page = connection.execute('SELECT chunk_index,length(content) AS size_bytes, '
                                          "CASE WHEN typeof(content)='blob' AND length(content)<=? THEN content ELSE NULL END AS content "
                                          'FROM autonomous_operation_trace_chunks WHERE sidecar_sha256=? AND chunk_index>? '
                                          'ORDER BY chunk_index LIMIT ?',
                                          (CHUNK_BYTES, row['sidecar_sha256'], after, PAGE_CHUNKS)).fetchall()
                for chunk in page:
                    content, index = chunk['content'], chunk['chunk_index']
                    if (type(index) is not int or index != after + 1 or index >= row['chunk_count']
                            or not isinstance(content, bytes) or chunk['size_bytes'] != len(content)
                            or not 0 < len(content) <= CHUNK_BYTES
                            or index < row['chunk_count'] - 1 and len(content) != CHUNK_BYTES
                            or len(compressed) + len(content) > row['compressed_bytes']):
                        raise OperationTraceError('Persisted operation trace chunk differs.')
                    compressed.extend(content)
                    after = index
                if len(page) < PAGE_CHUNKS:
                    break
            if (after + 1 != row['chunk_count'] or len(compressed) != row['compressed_bytes']
                    or sha256(compressed).hexdigest() != row['compressed_sha256']):
                raise OperationTraceError('Persisted operation trace bytes differ.')
        check()
        try:
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            encoded = decompressor.decompress(bytes(compressed), MAX_TRACE_BYTES + 1)
            if (len(encoded) != row['content_bytes'] or len(encoded) > MAX_TRACE_BYTES
                    or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail
                    or sha256(encoded).hexdigest() != row['content_sha256']):
                raise OperationTraceError('Persisted operation trace decompression differs.')
            sidecar = json.loads(encoded)
            check()
            binding, canonical = _sealed(sidecar)
        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OperationTraceError('Persisted operation trace cannot be decoded.') from error
        if (canonical != encoded or sidecar['sidecar_sha256'] != row['sidecar_sha256']
                or sidecar['input_sha256'] != row['input_sha256']
                or (binding['claim_id'], binding['run_id'], binding['current_state_sha256'],
                    binding['current_event_sha256'], binding['profile_sha256']) != identity):
            raise OperationTraceError('Persisted operation trace identity differs.')
        return sidecar


def admit_operation_trace(connection_factory, bundle, sidecar):
    """Private append-only admission after full native recomputation and exact CAS.

    The caller supplies the direct private database connection, not a public
    controller or HTTP route. Initialize the sidecar schema explicitly first.
    """
    from .autonomous_operations_v1 import verify_operation_sidecar
    verify_operation_sidecar(bundle, sidecar)
    binding, encoded = _sealed(sidecar)
    if bundle['claim_id'] != binding['claim_id']:
        raise OperationTraceError('Operation input belongs to another claim.')
    expected = [{key: row[key] for key in _COLUMNS} for row in bundle['rows']]
    compressed = gzip.compress(encoded, mtime=0)
    if len(compressed) > MAX_TRACE_BYTES:
        raise OperationTraceError('Compressed operation sidecar exceeds its bound.')
    reader = OperationTraceStore(connection_factory)
    existing = reader.read(binding['claim_id'], head_state_sha256=binding['current_state_sha256'],
                           head_event_sha256=binding['current_event_sha256'], run_id=binding['run_id'],
                           profile_sha256=binding['profile_sha256'])
    if existing is not None and existing != sidecar:
        raise OperationTraceError('An exact run already has another immutable operation trace.')
    with connection_factory() as connection:
        connection.execute('BEGIN IMMEDIATE')
        rows = connection.execute('SELECT ' + ','.join(_COLUMNS) +
                                  ' FROM claim_loop_events WHERE session_id=? AND loop_id=? ORDER BY sequence',
                                  (SESSION_ID, 'autonomous.' + binding['claim_id'])).fetchall()
        if [{key: row[key] for key in _COLUMNS} for row in rows] != expected:
            raise OperationTraceError('Saved journal changed before operation trace admission.')
        prior = connection.execute('SELECT sidecar_sha256 FROM autonomous_operation_traces WHERE claim_id=? AND run_id=? '
                                   'AND head_state_sha256=? AND head_event_sha256=? AND profile_sha256=?',
                                   (binding['claim_id'], binding['run_id'], binding['current_state_sha256'],
                                    binding['current_event_sha256'], binding['profile_sha256'])).fetchone()
        if prior is not None:
            if prior['sidecar_sha256'] != sidecar['sidecar_sha256']:
                raise OperationTraceError('Another immutable trace was admitted for this run.')
            return {'sidecar_sha256': sidecar['sidecar_sha256'], 'admitted': False, 'idempotent': True}
        chunks = [compressed[start:start + CHUNK_BYTES] for start in range(0, len(compressed), CHUNK_BYTES)]
        values = (sidecar['sidecar_sha256'], binding['claim_id'], binding['run_id'], binding['current_state_sha256'],
                  binding['current_event_sha256'], binding['profile_sha256'], sidecar['input_sha256'],
                  sha256(encoded).hexdigest(), sha256(compressed).hexdigest(), len(encoded), len(compressed), len(chunks))
        connection.execute('INSERT INTO autonomous_operation_traces VALUES (' + ','.join('?' for _ in values) + ')', values)
        for index, chunk in enumerate(chunks):
            connection.execute('INSERT INTO autonomous_operation_trace_chunks VALUES (?,?,?)',
                               (sidecar['sidecar_sha256'], index, chunk))
    return {'sidecar_sha256': sidecar['sidecar_sha256'], 'admitted': True, 'idempotent': False}

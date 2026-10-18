"""Untrusted, server-only original bytes for optional hosted startup acceleration.

The JSON contains no reducer states, schemas or SQL. Decoding supplies candidates;
only native replay and a new complete atomic primary proof can admit cache state.
"""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from threading import RLock
from types import SimpleNamespace

from .autonomous_store_v1 import AutonomousStoreError, MAX_FILE_BYTES, SESSION_ID


CONTRACT = 'casepath.hosted-read-seed/1'
MAX_SEED_BYTES = 128 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_ROWS = 16384
MAX_SOURCES = 125 * 128
MAX_ROW_BYTES = 4 * 1024 * 1024 + 64 * 1024
JOURNAL_COLUMNS = ('session_id', 'loop_id', 'sequence', 'idempotency_key',
                   'command_sha256', 'event_sha256', 'event_json', 'created_at')
_HASH = re.compile(r'[a-f0-9]{64}\Z')
_COMMIT = re.compile(r'[a-f0-9]{40}\Z')


class SeedError(AutonomousStoreError):
    """Malformed or ineligible candidate; no candidate details are exposed."""


def _require(condition):
    if not condition:
        raise SeedError('The optional saved-read seed is invalid or ineligible.')


def _integer(value):
    _require(len(value) <= 20)
    number = int(value)
    _require(-(2 ** 63) <= number < 2 ** 63)
    return number


def _number(value):
    raise SeedError('The optional saved-read seed requires native integers.')


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _candidate(value, deployment_commit):
    _require(type(deployment_commit) is str and _COMMIT.fullmatch(deployment_commit))
    _require(type(value) is dict and set(value) == {'contract', 'deployment_commit', 'journal_rows', 'sources'})
    _require(value['contract'] == CONTRACT and value['deployment_commit'] == deployment_commit)
    rows, originals = value['journal_rows'], value['sources']
    _require(type(rows) is list and len(rows) <= MAX_ROWS)
    _require(type(originals) is list and len(originals) <= MAX_SOURCES)
    copied, previous, row_bytes = [], None, 0
    for row in rows:
        _require(type(row) is dict and set(row) == set(JOURNAL_COLUMNS))
        size_bytes = 1024
        for name in JOURNAL_COLUMNS:
            if name == 'sequence':
                _require(type(row[name]) is int and 1 <= row[name] < 2 ** 63)
                size_bytes += len(str(row[name]))
            else:
                _require(type(row[name]) is str)
                size = len(row[name].encode('utf-8'))
                _require(size <= MAX_ROW_BYTES)
                size_bytes += size
        _require(size_bytes <= MAX_ROW_BYTES)
        row_bytes += size_bytes
        _require(row_bytes <= 32 * 1024 * 1024 and row['session_id'] == SESSION_ID)
        identity = (row['loop_id'], row['sequence'])
        _require(previous is None or previous < identity)
        previous = identity
        copied.append({name: row[name] for name in JOURNAL_COLUMNS})
    sources, raw_sources, total, previous = [], {}, 0, None
    for item in originals:
        _require(type(item) is dict and set(item) == {'sha256', 'content_base64'})
        digest, encoded = item['sha256'], item['content_base64']
        _require(type(digest) is str and _HASH.fullmatch(digest) and (previous is None or previous < digest))
        _require(type(encoded) is str and len(encoded) <= 4 * ((MAX_FILE_BYTES + 2) // 3))
        raw = base64.b64decode(encoded, validate=True)
        _require(1 <= len(raw) <= MAX_FILE_BYTES and base64.b64encode(raw).decode('ascii') == encoded)
        _require(sha256(raw).hexdigest() == digest)
        total += len(raw)
        _require(total <= MAX_SOURCE_BYTES)
        sources.append({'sha256': digest, 'content_base64': encoded})
        raw_sources[digest], previous = raw, digest
    return {'contract': CONTRACT, 'deployment_commit': deployment_commit,
            'journal_rows': copied, 'sources': sources}, raw_sources


def decode_seed(raw, *, deployment_commit):
    """Strict bounded JSON candidate; event_json text is preserved verbatim."""
    try:
        _require(type(raw) is bytes and len(raw) <= MAX_SEED_BYTES)
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object,
                           parse_int=_integer, parse_float=_number, parse_constant=_number)
        return _candidate(value, deployment_commit)[0]
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise SeedError('The optional saved-read seed could not be decoded.') from None


def pack_seed(deployment_commit, journal_rows, sources):
    """Pack raw candidates only; successful packing establishes no authority."""
    try:
        candidate = _candidate({'contract': CONTRACT, 'deployment_commit': deployment_commit,
                                'journal_rows': journal_rows, 'sources': sources}, deployment_commit)[0]
        raw = json.dumps(candidate, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                         allow_nan=False).encode('utf-8')
        _require(len(raw) <= MAX_SEED_BYTES)
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SeedError('The optional saved-read seed could not be packed.') from None


def load_seed(path, *, deployment_commit, expected_sha256):
    """Missing files retain cold startup; configured invalid bytes fail closed."""
    try:
        descriptor = os.open(Path(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_NONBLOCK', 0))
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        _require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_SEED_BYTES)
        _require(type(expected_sha256) is str and _HASH.fullmatch(expected_sha256))
        raw = source.read(MAX_SEED_BYTES + 1)
    _require(len(raw) <= MAX_SEED_BYTES and sha256(raw).hexdigest() == expected_sha256)
    return decode_seed(raw, deployment_commit=deployment_commit)


def admit_seed(store, candidate, *, deployment_commit):
    """Startup-only: stage native caches, certify every byte, then install once.

    False means a confirmed current SQL/schema mismatch and permits the existing
    cold reader. Malformed proofs and uncertain transport propagate without retry.
    The caller must not publish this pristine read-only store before admission.
    """
    from types import MethodType
    from . import hosted_storage_v1 as hs
    _require(type(store) is hs.HostedAutonomousStore and store._read_only is True)
    actual_sources = store._source_store
    _require(type(actual_sources) is hs.HostedSources and store.storage is None)
    first, second = store.journal.connect, actual_sources.connect
    _require(first is second or isinstance(first, MethodType) and isinstance(second, MethodType)
             and first.__self__ is second.__self__ and first.__func__ is second.__func__)
    try:
        value, originals = _candidate(candidate, deployment_commit)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SeedError('The optional saved-read seed candidate is invalid.') from None

    def pristine():
        return (not getattr(store, '_summary_cache', {}) and not store._extractions
                and getattr(store, '_knowledge_byte_cache', None) is None
                and getattr(store, '_knowledge_pending', None) is None
                and not actual_sources._cache and actual_sources._size == 0
                and getattr(actual_sources, '_knowledge_schema', None) is None)

    class CandidateSources(hs.HostedSources):
        def _fetch_many(self, *args, **kwargs):
            # An omitted original must never turn this candidate into raw SQL.
            raise SeedError('The optional saved-read seed lacks a referenced original.')

    with store._summary_lock, actual_sources._lock:
        _require(pristine())
        stage = hs.HostedAutonomousStore.__new__(hs.HostedAutonomousStore)
        stage._read_only, stage.storage = True, None
        stage.journal = SimpleNamespace(path=store.journal.path, connect=first)
        stage.path, stage.source_root = store.path, store.source_root
        stage._extractions, stage._extraction_lock, stage._summary_lock = {}, RLock(), RLock()
        stage._source_store = CandidateSources(first)
        for digest, raw in originals.items():
            stage._source_store._remember(digest, raw)
        rows = value['journal_rows']
        proof = hs._proof_expected(rows, hs._JOURNAL_COLUMNS, 'casepath-journal-bytes-v1')
        frozen = tuple(tuple(row.items()) for row in rows)
        certified = []

        def verify(digests):
            _require(stage._source_store._digests(digests) == list(originals))
            source_queries, expected = stage._source_store._knowledge_source_queries(list(originals))
            query = hs._proof_query('claim_loop_events', hs._JOURNAL_COLUMNS,
                                   'casepath-journal-bytes-v1', 'session_id=?', 'loop_id,sequence')
            with first() as db:
                _require(hasattr(db, 'read_snapshot'))
                cursors = db.read_snapshot([(hs._schema_query('claim_loop_events'), ()),
                    (query, (SESSION_ID, len(rows) + 1)), *source_queries])
            _require(len(cursors) == 3 + len(expected))
            journal_schema, source_schema = cursors[0].fetchall(), cursors[2].fetchall()
            journal_matches = hs._proof_matches(cursors[1], proof)
            source_matches = [hs._proof_matches(cursor, item) for cursor, item in zip(cursors[3:], expected)]
            if (not hs._standard_schema(journal_schema, hs._JOURNAL_COLUMNS)
                    or not hs._standard_schema(source_schema, hs._SOURCE_COLUMNS)
                    or not journal_matches or not all(source_matches)):
                return
            certified.append((hs._schema_identity(journal_schema), hs._schema_identity(source_schema)))

        states = stage._validated_states(rows, source_verifier=verify)
        if not certified:
            return False
        stage._knowledge_pending = (frozen, certified[0][0], proof)
        stage._after_validated_knowledge_states(rows, states)
        _require(pristine())
        # No caller object is installed: rows were copied and all derived values
        # were created by native replay in the detached stage before certification.
        store._summary_cache, store._extractions = stage._summary_cache, stage._extractions
        store._knowledge_byte_cache = stage._knowledge_byte_cache
        actual_sources._cache, actual_sources._size = stage._source_store._cache, stage._source_store._size
        actual_sources._knowledge_schema = certified[0][1]
        return True

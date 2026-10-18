#!/usr/bin/env python3
"""Mac operator: export an untrusted, release-bound read seed using SELECT only.

No journal, work-store, lease, schema initialization, or provider is constructed.
Independently closed small reads acquire candidates; the existing native seed
admission supplies all replay/source checks and the final atomic SQL proof.
"""
import argparse
import base64
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
from threading import RLock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'casepath-api'))

from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, MAX_FILE_BYTES, SESSION_ID
from casepath_api.hosted_read_seed_v1 import (
    MAX_ROWS, MAX_ROW_BYTES, MAX_SOURCE_BYTES, MAX_SOURCES, decode_seed, pack_seed,
)
from casepath_api.hosted_sql_v1 import HostedStorageError, REQUEST_SECONDS, TursoDatabase, _http_client
from casepath_api.hosted_storage_v1 import (
    HostedAutonomousStore, HostedSources, _JOURNAL_COLUMNS, _SOURCE_COLUMNS,
    _schema_identity, _schema_query, _standard_schema,
)

SLICE_BYTES = 32 * 1024
RESPONSE_BYTES = 64 * 1024
METADATA_ROWS = 4
SHORT_TEXT_BYTES = 256
SCHEMA_BYTES = 12 * 1024
MAX_JOURNAL_BYTES = 32 * 1024 * 1024
MAX_EXPORT_REQUESTS = 4096
MAX_EXPORT_SECONDS = 3600
MAX_EXPORT_WIRE_BYTES = 256 * 1024 * 1024
_COMMIT = re.compile('[0-9a-f]{40}')


class Refused(AutonomousStoreError):
    pass


class _BoundedResponse:
    def __init__(self, response, consume):
        self.response, self.consume = response, consume

    def __getattr__(self, key):
        return getattr(self.response, key)

    def iter_bytes(self):
        size = 0
        for chunk in self.response.iter_bytes():
            size += len(chunk)
            if size > RESPONSE_BYTES:
                raise HostedStorageError('Export response exceeds its small-transfer bound.')
            self.consume(len(chunk))
            yield chunk


class _BoundedClient:
    """Keep the native SDK timeouts, zero retries and independent 12s deadline."""
    def __init__(self):
        self.client = _http_client()
        self.started, self.requests, self.wire_bytes = time.monotonic(), 0, 0

    def _consume(self, size, *, reserve_request=False):
        remaining = MAX_EXPORT_SECONDS - (REQUEST_SECONDS if reserve_request else 0)
        if time.monotonic() - self.started > remaining or self.wire_bytes + size > MAX_EXPORT_WIRE_BYTES:
            raise HostedStorageError('Export exceeded its fixed total time or wire-byte budget.')
        self.wire_bytes += size

    @staticmethod
    def _read_only(body):
        try:
            requests = json.loads(body)['requests']
            if type(requests) is not list or not requests:
                raise ValueError()
            for request in requests:
                if request == {'type': 'close'}:
                    continue
                if request['type'] != 'execute':
                    raise ValueError()
                sql = request['stmt']['sql'].strip()
                if sql.upper() in {'BEGIN', 'COMMIT', 'ROLLBACK'}:
                    continue
                # The native snapshot validator checks this too. At the
                # exporter boundary, refuse every other protocol operation
                # and stacked statement before it can reach the HTTP client.
                unquoted = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|"
                                  r"--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/", ' ', sql)
                if sql.split(None, 1)[0].upper() != 'SELECT' or ';' in unquoted.rstrip().removesuffix(';'):
                    raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            raise HostedStorageError('Export transport accepts read-only SQL and close operations only.') from None

    @contextmanager
    def stream(self, *args, **kwargs):
        body = kwargs.get('content')
        if not isinstance(body, bytes) or len(body) > RESPONSE_BYTES:
            raise HostedStorageError('Export request exceeds its small-transfer bound.')
        self._read_only(body)
        if self.requests >= MAX_EXPORT_REQUESTS:
            raise HostedStorageError('Export exceeded its fixed request-count budget.')
        self._consume(len(body), reserve_request=True)
        self.requests += 1
        with self.client.stream(*args, **kwargs) as response:
            yield _BoundedResponse(response, self._consume)

    def close(self):
        self.client.close()


class _SchemaCursor:
    def __init__(self, cursor, expected):
        self.cursor, self.expected = cursor, expected

    def fetchall(self):
        rows = self.cursor.fetchall()
        if _schema_identity(rows) != self.expected:
            raise Refused('Remote schema changed during read-seed acquisition.')
        return rows


class _PinnedConnection:
    def __init__(self, connection, schemas):
        self.connection, self.schemas = connection, schemas

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)

    def read_snapshot(self, queries, **kwargs):
        cursors = self.connection.read_snapshot(queries, **kwargs)
        return tuple(_SchemaCursor(cursor, self.schemas[sql]) if sql in self.schemas else cursor
                     for (sql, _), cursor in zip(queries, cursors))


def _read(connect, sql, parameters=()):
    with connect() as db:
        cursors = db.read_snapshot([(sql, parameters)], close_http=True)
    if len(cursors) != 1:
        raise Refused('Export read has an invalid result roster.')
    return cursors[0].fetchall()


def _schema(connect, table, columns):
    # Bound each schema string before serialization, including trigger SQL.
    # A conservative JSON bound reserves room for Hrana's typed-cell envelopes.
    names = ('kind', 'name', 'detail', 'required', 'default_value', 'pk', 'hidden')
    bound = '+'.join('64+6*COALESCE(length(CAST(' + name + ' AS BLOB)),0)' for name in names)
    query = _schema_query(table)
    metadata = _read(connect, 'SELECT count(*) AS n,COALESCE(sum(' + bound + '),0) AS wire_bytes FROM (' + query + ')')
    if (len(metadata) != 1 or type(metadata[0]['n']) is not int or not 1 <= metadata[0]['n'] <= 64
            or type(metadata[0]['wire_bytes']) is not int or not 0 < metadata[0]['wire_bytes'] <= SCHEMA_BYTES):
        raise Refused('Remote schema exceeds its bounded metadata contract.')
    # Recheck the complete payload bound in its own snapshot; a changed schema
    # cannot turn a previously small metadata result into a large raw response.
    gate = 'SELECT count(*)<=64 AND COALESCE(sum(' + bound + '),0)<=? FROM (' + query + ')'
    rows = _read(connect, 'SELECT ' + ','.join(names) + ' FROM (' + query + ') WHERE (' + gate + ') LIMIT 65',
                 (SCHEMA_BYTES,))
    if (len(rows) != metadata[0]['n'] or not _standard_schema(rows, columns)
            or sum(64 + 6 * len(str(row[name]).encode()) for row in rows for name in names) > SCHEMA_BYTES):
        raise Refused('Remote schema differs from the complete native schema.')
    return _schema_identity(rows)


def _metadata(connect, table, columns, *, digests=None):
    journal = columns == _JOURNAL_COLUMNS
    keys = ('session_id', 'loop_id', 'sequence') if journal else ('sha256', 'chunk_index')
    integer = keys[-1]
    projection = []
    for key in keys:
        if key == integer:
            projection.append("CASE WHEN typeof(" + key + ")='integer' THEN " + key + ' ELSE NULL END AS ' + key)
        else:
            maximum = SHORT_TEXT_BYTES if journal else 64
            projection.append("CASE WHEN typeof(" + key + ")='text' AND length(CAST(" + key + ' AS BLOB))<=' +
                              str(maximum) + ' THEN ' + key + ' ELSE NULL END AS ' + key)
    for name in columns:
        projection += ['typeof(' + name + ') AS ' + name + '__type',
                       'length(CAST(' + name + ' AS BLOB)) AS ' + name + '__bytes']
        if journal and name not in keys and name != 'event_json':
            projection.append("CASE WHEN typeof(" + name + ")='text' AND length(CAST(" + name +
                              ' AS BLOB))<=' + str(SHORT_TEXT_BYTES) + ' THEN ' + name + ' ELSE NULL END AS ' + name)
    after = None
    result = []
    while True:
        where = 'session_id=?' if journal else 'sha256 IN (' + ','.join('?' for _ in digests) + ')'
        parameters = (SESSION_ID,) if journal else tuple(digests)
        if after is not None:
            where += ' AND (' + ','.join(keys) + ')>(' + ','.join('?' for _ in keys) + ')'
            parameters += after
        page = _read(connect, 'SELECT ' + ','.join(projection) + ' FROM ' + table + ' WHERE ' + where +
                     ' ORDER BY ' + ','.join(keys) + ' LIMIT ' + str(METADATA_ROWS), parameters)
        if len(page) > METADATA_ROWS:
            raise Refused('Export metadata page exceeds its row bound.')
        for row in page:
            identity = tuple(row[key] for key in keys)
            if (any(type(row[key]) is not (int if key == integer else str) for key in keys)
                    or row[integer] < (1 if journal else 0) or after is not None and identity <= after):
                raise Refused('Export metadata has an invalid primary key.')
            total = 0
            for name in columns:
                expected = 'integer' if name == integer else 'blob' if name == 'content' else 'text'
                size = row[name + '__bytes']
                if row[name + '__type'] != expected or type(size) is not int or size < 0:
                    raise Refused('Export metadata has a nonnative SQL storage type or length.')
                total += size
            if (journal and (row['session_id'] != SESSION_ID or not row['loop_id'].startswith('autonomous.')
                            or total + 1024 > MAX_ROW_BYTES)
                    or not journal and (row['sha256'] not in digests
                                        or row['content__bytes'] > HostedSources.CHUNK_BYTES)):
                raise Refused('Export metadata exceeds its native row contract.')
            result.append(dict(row))
            if len(result) > MAX_ROWS:
                raise Refused('Export metadata roster exceeds its row bound.')
            after = identity
        if len(page) < METADATA_ROWS:
            return result


def _field(connect, table, name, row, keys):
    kind, size = row[name + '__type'], row[name + '__bytes']
    if kind == 'integer':
        value = row[name]
        if len(str(value).encode('ascii')) != size:
            raise Refused('Export integer byte length differs.')
        return value
    # At most four metadata rows carry six short strings of <=256 UTF-8
    # bytes each. Even worst-case JSON escaping stays below the 64-KiB cap.
    # The final native proof binds these exact values to all acquired slices.
    if kind == 'text' and name in row and type(row[name]) is str:
        if len(row[name].encode('utf-8')) != size:
            raise Refused('Export short TEXT byte length differs.')
        return row[name]
    where = ' AND '.join(key + '=?' for key in keys)
    query = ('SELECT typeof(' + name + ') AS kind,length(CAST(' + name + ' AS BLOB)) AS size_bytes,'
             'CASE WHEN typeof(' + name + ')=? AND length(CAST(' + name + ' AS BLOB))=? THEN '
             'substr(CAST(' + name + ' AS BLOB),?,?) ELSE NULL END AS payload FROM ' + table +
             ' WHERE ' + where + ' LIMIT 2')
    raw = bytearray()
    for offset in range(0, max(1, size), SLICE_BYTES):
        wanted = min(SLICE_BYTES, size - offset)
        page = _read(connect, query, (kind, size, offset + 1, wanted, *(row[key] for key in keys)))
        if (len(page) != 1 or page[0]['kind'] != kind or type(page[0]['size_bytes']) is not int
                or page[0]['size_bytes'] != size or type(page[0]['payload']) is not bytes
                or len(page[0]['payload']) != wanted):
            raise Refused('Remote field type, length, primary key or slice changed during acquisition.')
        raw.extend(page[0]['payload'])
    try:
        value = bytes(raw).decode('utf-8', errors='strict') if kind == 'text' else bytes(raw)
    except UnicodeError as exc:
        raise Refused('Remote TEXT is not exact UTF-8.') from exc
    if name in keys and value != row[name]:
        raise Refused('Remote primary key bytes differ from metadata.')
    return value


def _source_digests(rows):
    digests = set()
    try:
        for row in rows:
            event = json.loads(row['event_json'])
            if event.get('kind') not in {'intake', 'sources.arrived'}:
                continue
            descriptors = event['payload']['sources']
            if type(descriptors) is not list or not 1 <= len(descriptors) <= 21:
                raise Refused('Journal source lookup roster is invalid.')
            for descriptor in descriptors:
                AutonomousStore._descriptor_metadata(descriptor, event['claim_id'])
                digests.add(descriptor['sha256'])
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise Refused('Journal source lookup is malformed.') from exc
    if len(digests) > MAX_SOURCES:
        raise Refused('Source roster exceeds its bound.')
    return sorted(digests)


def _collect(connect):
    schemas = {_schema_query(table): _schema(connect, table, columns) for table, columns in (
        ('claim_loop_events', _JOURNAL_COLUMNS), ('autonomous_source_chunks', _SOURCE_COLUMNS))}
    metadata = _metadata(connect, 'claim_loop_events', _JOURNAL_COLUMNS)
    if sum(1024 + sum(row[name + '__bytes'] for name in _JOURNAL_COLUMNS) for row in metadata) > MAX_JOURNAL_BYTES:
        raise Refused('Journal bytes exceed the seed bound.')
    rows = [{name: _field(connect, 'claim_loop_events', name, row, ('session_id', 'loop_id', 'sequence'))
             for name in _JOURNAL_COLUMNS} for row in metadata]
    digests = _source_digests(rows)
    chunks = []
    for start in range(0, len(digests), HostedSources.BATCH_DIGESTS):
        chunks.extend(_metadata(connect, 'autonomous_source_chunks', _SOURCE_COLUMNS,
                                digests=digests[start:start + HostedSources.BATCH_DIGESTS]))
        if len(chunks) > MAX_ROWS:
            raise Refused('Source chunk roster exceeds its bound.')
    if sum(row['content__bytes'] for row in chunks) > MAX_SOURCE_BYTES:
        raise Refused('Original bytes exceed the aggregate seed bound.')
    # Validate the entire selected chunk roster before reading any original
    # payload, so a known gap or oversized later file stops acquisition early.
    rosters, position = [], 0
    for digest in digests:
        selected, total, previous = [], 0, None
        while position < len(chunks) and chunks[position]['sha256'] == digest:
            row = chunks[position]
            size = row['content__bytes']
            if (row['chunk_index'] != len(selected) or previous is not None and previous != HostedSources.CHUNK_BYTES
                    or total + size > MAX_FILE_BYTES):
                raise Refused('Original chunk roster is incomplete or oversized.')
            selected.append(row)
            total, previous, position = total + size, size, position + 1
        if not total or len(selected) != (total + HostedSources.CHUNK_BYTES - 1) // HostedSources.CHUNK_BYTES:
            raise Refused('Original chunk roster is missing, empty or incomplete.')
        rosters.append((digest, selected))
    if position != len(chunks):
        raise Refused('Original chunk roster differs from the selected source identities.')
    sources = []
    for digest, selected in rosters:
        raw = b''.join(_field(connect, 'autonomous_source_chunks', 'content', row, ('sha256', 'chunk_index'))
                       for row in selected)
        if sha256(raw).hexdigest() != digest:
            raise Refused('Original bytes differ from their native hash.')
        sources.append({'sha256': digest, 'content_base64': base64.b64encode(raw).decode('ascii')})
    return rows, sources, schemas


def _pristine(connect, root):
    store = HostedAutonomousStore.__new__(HostedAutonomousStore)
    store._read_only, store.storage = True, None
    store.path = root / 'unused-journal-placeholder'
    store.journal = SimpleNamespace(path=store.path, connect=connect)
    store.source_root, store._source_store = root, HostedSources(connect)
    store._extractions, store._extraction_lock, store._summary_lock = {}, RLock(), RLock()
    return store


def _output_path(output):
    output = Path(output)
    if '..' in output.parts:
        raise Refused('Seed output must not contain parent traversal.')
    output = output.absolute()
    if output.is_symlink() or output.exists():
        raise Refused('Seed output must be a new private file; overwrite is refused.')
    if not output.parent.is_dir():
        raise Refused('Seed output requires an existing private upload directory.')
    # Mac adds this private artifact only to a temporary official upload
    # archive/source copy after canonical source verification and sealing.
    for parent in (output.parent, *output.parents):
        if parent.is_symlink():
            raise Refused('Seed output ancestors must not be symlinks.')
        marker = parent / '.git'
        if marker.is_file() or marker.is_dir() and (marker / 'HEAD').is_file():
            raise Refused('Seed output must remain outside every Git checkout.')
    parent = output.parent.resolve(strict=True)
    if parent != output.parent:
        raise Refused('Seed output requires a canonical private upload directory.')
    return parent / output.name


def export_seed(connect, *, deployment_commit, output, check_budget=lambda: None):
    """Acquire once, natively validate/prove once, then publish a new 0600 file."""
    if type(deployment_commit) is not str or not _COMMIT.fullmatch(deployment_commit):
        raise Refused('An exact lowercase 40-hex target deployment commit is required.')
    output = _output_path(output)
    rows, sources, schemas = _collect(connect)
    raw = pack_seed(deployment_commit, rows, sources)
    candidate = decode_seed(raw, deployment_commit=deployment_commit)
    pinned = lambda: _PinnedConnection(connect(), schemas)
    with tempfile.TemporaryDirectory(prefix='casepath-read-seed-validation-') as folder:
        store = _pristine(pinned, Path(folder))
        if not store.admit_read_seed(candidate, deployment_commit=deployment_commit):
            raise Refused('Remote journal or source bytes changed before the final atomic proof.')
    check_budget()
    output = _output_path(output)
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.hosted-read-seed-' + secrets.token_hex(16)
    created = False
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        created = True
        with os.fdopen(fd, 'wb') as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        _output_path(output)
        current = output.parent.stat()
        opened = os.fstat(directory)
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise Refused('Private upload directory changed before publication.')
        os.link(temporary, output.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.fsync(directory)
    finally:
        try:
            if created:
                os.unlink(temporary, dir_fd=directory)
        finally:
            os.close(directory)
    return {'deployment_commit': deployment_commit, 'sha256': sha256(raw).hexdigest(),
            'bytes': len(raw), 'journal_rows': len(rows), 'sources': len(sources)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if sys.platform != 'darwin':
        raise SystemExit('Read-seed acquisition is restricted to the authorized Mac operator.')
    try:
        database = TursoDatabase(os.environ.get('CASEPATH_TURSO_URL'), os.environ.get('TURSO_AUTH_TOKEN'),
                                 client_factory=_BoundedClient, reuse_http=True)
        try:
            receipt = export_seed(database.connect, deployment_commit=args.deployment_commit, output=args.output,
                                  check_budget=lambda: database._shared_client._consume(0))
        finally:
            database.close()
    except (AutonomousStoreError, HostedStorageError, OSError, ValueError):
        # Never include endpoint, credentials, SQL values, journal or source data.
        raise SystemExit('Read-seed export refused or failed; no read was retried. Preserve any existing output.') from None
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()

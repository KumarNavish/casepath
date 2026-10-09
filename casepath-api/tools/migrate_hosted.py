#!/usr/bin/env python3
"""Exact, resumable migration; default inspection is local and read-only.

Root runs snapshot only after stopping every local writer, and migrate/verify
only with hosted writers/inference disabled. No deletion, replacement, update,
credential argument, automatic network retry, or long remote transaction.

  python casepath-api/tools/migrate_hosted.py inspect
  python casepath-api/tools/migrate_hosted.py snapshot --snapshot /private/tmp/casepath-frozen --writers-stopped
  python casepath-api/tools/migrate_hosted.py migrate --snapshot /private/tmp/casepath-frozen --writers-stopped --receipt /private/tmp/migration.json
  python casepath-api/tools/migrate_hosted.py verify --snapshot /private/tmp/casepath-frozen --writers-stopped --receipt /private/tmp/verification.json

Network modes import TursoDatabase/HostedSources from --hosting-root and read
CASEPATH_TURSO_URL and TURSO_AUTH_TOKEN only from the environment. Successful
verification compares every table row and every original source byte, not a
sample. An uncertain operation stops; rerun against the SAME frozen snapshot.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import subprocess
import sys

HOSTING = Path(__file__).resolve().parents[2]
SOURCE = HOSTING / '.runtime/casepath-data-v1'
DATABASES = ('casepath.db', 'agent-work-v1.sqlite3')
MAX_SOURCE = 16 * 1024 * 1024
WRITE_BYTES, READ_BYTES, MAX_ROWS, MAX_PARAMETERS = 2 * 1024 * 1024, 8 * 1024 * 1024, 64, 900
HASH = re.compile(r'[0-9a-f]{64}')


class Refused(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    if path.is_symlink() or not path.is_file():
        raise Refused('Expected a regular file: ' + str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def q(name):
    return '"' + name.replace('"', '""') + '"'


def typed_cell(value):
    if value is None:
        return b'n', b''
    if type(value) is int:
        return b'i', str(value).encode('ascii')
    if type(value) is float and math.isfinite(value):
        return b'f', struct.pack('!d', value)
    if isinstance(value, str):
        return b's', value.encode('utf-8')
    if isinstance(value, bytes):
        return b'b', value
    raise Refused('Unsupported persisted scalar type.')


def row_bytes(row):
    result = bytearray()
    for value in row:
        marker, raw = typed_cell(value)
        result.extend(marker + len(raw).to_bytes(8, 'big') + raw)
    return bytes(result)


def wire_cell(value):
    # Same supported scalar encoding as the reviewed Hrana transport.
    if value is None:
        return {'type': 'null'}
    if type(value) is int:
        return {'type': 'integer', 'value': str(value)}
    if type(value) is float and math.isfinite(value):
        return {'type': 'float', 'value': value}
    if isinstance(value, str):
        return {'type': 'text', 'value': value}
    if isinstance(value, bytes):
        return {'type': 'blob', 'base64': base64.b64encode(value).decode('ascii')}
    raise Refused('Unsupported protocol scalar type.')


def wire_size(row):
    return len(json.dumps([wire_cell(value) for value in row], allow_nan=False, separators=(',', ':')).encode())


def local_connect(path):
    wal = Path(str(path) + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise Refused('A nonempty WAL cannot be inspected using immutable=1.')
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
    connection.execute('PRAGMA query_only=ON')
    return connection


def schema_objects(connection):
    return [dict(zip(('type', 'name', 'tbl_name', 'sql'), tuple(row))) for row in connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY type,name")]


def table_info(connection, name):
    columns = [list(row) for row in connection.execute('PRAGMA table_xinfo(' + q(name) + ')')]
    if not columns or any(column[6] != 0 for column in columns):
        raise Refused('Generated/hidden columns require a separate reviewed migration: ' + name)
    keys = [column[1] for column in sorted(columns, key=lambda column: column[5]) if column[5]]
    if not keys:
        raise Refused('Table lacks a resumable primary key: ' + name)
    return {'columns': [column[1] for column in columns], 'column_definitions': columns, 'primary_key': keys,
            'foreign_keys': [list(row) for row in connection.execute('PRAGMA foreign_key_list(' + q(name) + ')')]}


def ordered_rows(connection, name, table):
    return connection.execute('SELECT ' + ','.join(q(column) for column in table['columns']) + ' FROM ' + q(name)
                              + ' ORDER BY ' + ','.join(q(key) for key in table['primary_key']))


def table_digest(rows, columns):
    digest = hashlib.sha256(canonical(columns)); count = maximum = content_bytes = 0
    for row in rows:
        raw = row_bytes(tuple(row)); digest.update(len(raw).to_bytes(8, 'big')); digest.update(raw)
        count += 1; maximum = max(maximum, wire_size(tuple(row))); content_bytes += len(raw)
    return {'count': count, 'content_sha256': digest.hexdigest(), 'content_bytes': content_bytes,
            'max_wire_row_bytes': maximum}


def inventory(root):
    report = {'databases': {}, 'sources': []}
    for name in DATABASES:
        path = root / name; before = file_hash(path)
        with closing(local_connect(path)) as connection:
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise Refused('SQLite integrity check failed: ' + name)
            objects = schema_objects(connection)
            if any(item['type'] not in {'table', 'index', 'trigger', 'view'} or 'VIRTUAL TABLE' in item['sql'].upper() for item in objects):
                raise Refused('Unsupported schema object requires review.')
            tables = {}
            for item in objects:
                if item['type'] != 'table':
                    continue
                table = table_info(connection, item['name'])
                table.update(table_digest(ordered_rows(connection, item['name'], table), table['columns']))
                # Keyset paging must not omit nullable SQLite PRIMARY KEY rows.
                nulls = ' OR '.join(q(key) + ' IS NULL' for key in table['primary_key'])
                if connection.execute('SELECT 1 FROM ' + q(item['name']) + ' WHERE ' + nulls + ' LIMIT 1').fetchone():
                    raise Refused('Nullable primary-key content requires review: ' + item['name'])
                tables[item['name']] = table
            report['databases'][name] = {'file': before, 'schema': objects, 'tables': tables,
                'user_version': connection.execute('PRAGMA user_version').fetchone()[0],
                'application_id': connection.execute('PRAGMA application_id').fetchone()[0]}
        if file_hash(path) != before:
            raise Refused('Source database changed during inspection; stop all writers.')
    source_root = root / 'autonomous-sources-v1'
    if source_root.is_symlink() or not source_root.is_dir():
        raise Refused('Original source directory is absent or unsafe.')
    for path in sorted(source_root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            raise Refused('Unexpected source entry; preserve it and obtain review.')
        identity = file_hash(path)
        if not HASH.fullmatch(path.name) or path.parent != source_root or path.name != identity['sha256'] or identity['bytes'] > MAX_SOURCE:
            raise Refused('Original source name/bytes/hash differ; do not publish it.')
        report['sources'].append({'path': path.name, **identity})
    report['manifest_sha256'] = sha(canonical(report))
    return report


def external_path(path, args):
    result = path.resolve()
    if result.is_relative_to(args.hosting_root.resolve()) or result.is_relative_to(args.source_root.resolve()):
        raise Refused('Snapshot/receipt must remain outside source and runtime.')
    return result


def save(path, value):
    # Local evidence only; never store credentials or exception text.
    temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def snapshot(args):
    target = external_path(args.snapshot, args)
    if target.exists():
        raise Refused('Snapshot path already exists; reuse its complete manifest or choose a new path. Nothing was removed.')
    before = inventory(args.source_root)
    target.mkdir(mode=0o700, parents=False)
    for name in DATABASES:
        with closing(local_connect(args.source_root / name)) as origin, closing(sqlite3.connect(target / name)) as backup:
            origin.backup(backup)
        (target / name).chmod(0o600)
    shutil.copytree(args.source_root / 'autonomous-sources-v1', target / 'autonomous-sources-v1', symlinks=False)
    copied = inventory(target)
    after = inventory(args.source_root)
    if after != before:
        raise Refused('Original state changed during backup; snapshot is incomplete and must not be migrated.')
    for name in DATABASES:
        if copied['databases'][name]['tables'] != before['databases'][name]['tables'] or copied['databases'][name]['schema'] != before['databases'][name]['schema']:
            raise Refused('SQLite backup content/schema differs.')
    if copied['sources'] != before['sources']:
        raise Refused('Source backup differs.')
    manifest = {'contract': 'casepath.hosted-migration-snapshot/1.0.0', 'created_at': datetime.now(timezone.utc).isoformat(),
                'source_root': str(args.source_root.resolve()), 'source_inventory': before, 'snapshot_inventory': copied,
                'original_files_unchanged': True, 'complete': True}
    manifest['snapshot_sha256'] = sha(canonical(manifest))
    save(target / 'SNAPSHOT.json', manifest)
    return manifest


SQL_TOKEN = re.compile(r"/\*.*?\*/|--[^\n]*|'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`(?:[^`]|``)*`|\[[^\]]*\]|[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]", re.S)


def sql_identity(sql):
    tokens = [token if token[0] in "'\"`[" else token.casefold() for token in SQL_TOKEN.findall(sql)
              if not token.startswith(('/*', '--')) and token != ';']
    return tokens


def remote_rows(connection, name, table):
    columns, keys = table['columns'], table['primary_key']; last = None
    limit = max(1, min(MAX_ROWS, READ_BYTES // max(256, table.get('max_wire_row_bytes', 256) + 128)))
    while True:
        where = '' if last is None else ' WHERE (' + ','.join(q(key) for key in keys) + ') > (' + ','.join('?' for _ in keys) + ')'
        sql = 'SELECT ' + ','.join(q(column) for column in columns) + ' FROM ' + q(name) + where + ' ORDER BY ' + ','.join(q(key) for key in keys) + ' LIMIT ?'
        page = connection.execute(sql, tuple(last or ()) + (limit,)).fetchall()
        for row in page:
            values = tuple(row)
            if any(values[columns.index(key)] is None for key in keys):
                raise Refused('Remote nullable primary key would evade keyset verification.')
            yield values
        if len(page) < limit:
            return
        last = tuple(page[-1][key] for key in keys)


def insert_sql(name, columns, rows):
    # Exact existing rows are skipped BEFORE append-only BEFORE INSERT triggers.
    # A conflicting existing key attempts an ordinary INSERT and aborts the
    # entire statement; it is never replaced or updated, even after a race.
    aliases = ','.join(q(column) for column in columns)
    values = ','.join('(' + ','.join('?' for _ in columns) + ')' for _ in rows)
    equality = ' AND '.join('existing.' + q(column) + ' IS incoming.' + q(column) for column in columns)
    sql = 'WITH incoming(' + aliases + ') AS (VALUES ' + values + ') INSERT INTO ' + q(name) + '(' + aliases + ') SELECT ' + aliases + ' FROM incoming WHERE NOT EXISTS (SELECT 1 FROM ' + q(name) + ' existing WHERE ' + equality + ')'
    return sql, tuple(value for row in rows for value in row)


def migration(args):
    frozen = external_path(args.snapshot, args)
    manifest = json.loads((frozen / 'SNAPSHOT.json').read_text())
    if manifest.get('snapshot_sha256') != sha(canonical({key: value for key, value in manifest.items() if key != 'snapshot_sha256'})) or not manifest.get('complete'):
        raise Refused('Frozen snapshot manifest is incomplete or altered.')
    current = inventory(frozen)
    if current != manifest['snapshot_inventory']:
        raise Refused('Frozen backup bytes, schema, rows or source files changed.')
    sys.path.insert(0, str(args.hosting_root.resolve() / 'casepath-api'))
    from casepath_api.hosted_sql_v1 import TursoDatabase
    from casepath_api.hosted_storage_v1 import HostedSources, JOURNAL_SCHEMA
    database = TursoDatabase(os.environ['CASEPATH_TURSO_URL'], os.environ['TURSO_AUTH_TOKEN'])
    extra = sqlite3.connect(':memory:')
    extra.executescript(JOURNAL_SCHEMA)
    chunk_objects = [item for item in schema_objects(extra) if item['tbl_name'] == 'autonomous_source_chunks']
    chunk_table = table_info(extra, 'autonomous_source_chunks'); chunk_table['max_wire_row_bytes'] = 360000
    extra.close()
    schemas, tables = {}, {}
    for filename, data in current['databases'].items():
        for item in data['schema']:
            key = (item['type'], item['name'])
            if key in schemas:
                raise Refused('Source databases have colliding schema identities.')
            schemas[key] = item
        for name, table in data['tables'].items():
            if name in tables:
                raise Refused('Source databases have colliding table names.')
            tables[name] = {**table, 'database': filename}
    for item in chunk_objects:
        schemas[(item['type'], item['name'])] = item
    report = {'contract': 'casepath.hosted-migration-readback/1.0.0', 'snapshot_sha256': manifest['snapshot_sha256'],
        'mode': args.mode, 'phase': 'remote_preflight', 'tables': {}, 'sources': [], 'completed': False,
        'limits': {'write_payload_bytes': WRITE_BYTES, 'read_payload_target_bytes': READ_BYTES, 'rows_per_statement': MAX_ROWS,
                   'explicit_remote_transactions': False, 'automatic_network_retries': False},
        'hosting_modules': {name: file_hash(args.hosting_root / 'casepath-api/casepath_api' / name) for name in ('hosted_sql_v1.py', 'hosted_storage_v1.py')}}
    receipt = external_path(args.receipt, args)
    save(receipt, report)
    with ExitStack() as stack:
        locals_ = {name: stack.enter_context(closing(local_connect(frozen / name))) for name in DATABASES}
        with database.connect() as remote:
            present = {(item['type'], item['name']): item for item in schema_objects(remote)}
            foreign = [item['name'] for key, item in present.items() if key not in schemas and item['tbl_name'] != 'hosted_workflow_lease']
            if foreign:
                raise Refused('Unexpected remote schema objects: ' + ','.join(foreign))
            if ('table', 'hosted_workflow_lease') in present:
                lease = remote.execute("SELECT owner,expires_at,CAST(strftime('%s','now') AS INTEGER) AS now FROM hosted_workflow_lease WHERE singleton=1").fetchone()
                if lease is None or lease['owner'] is not None and lease['expires_at'] > lease['now']:
                    raise Refused('Remote ownership is active or unconfirmed; disable all hosted writers.')
            for key, item in present.items():
                if key in schemas and sql_identity(item['sql']) != sql_identity(schemas[key]['sql']):
                    raise Refused('Remote schema differs: ' + item['name'])
            # Validate ALL existing rows before creating schema or publishing.
            for name, table in tables.items():
                if ('table', name) not in present:
                    continue
                actual = table_info(remote, name)
                if actual != {key: table[key] for key in ('columns', 'column_definitions', 'primary_key', 'foreign_keys')}:
                    raise Refused('Remote column/key definitions differ: ' + name)
                where = ' AND '.join(q(key) + ' IS ?' for key in table['primary_key'])
                for row in remote_rows(remote, name, table):
                    key = tuple(row[table['columns'].index(column)] for column in table['primary_key'])
                    match = locals_[table['database']].execute('SELECT ' + ','.join(q(column) for column in table['columns']) + ' FROM ' + q(name) + ' WHERE ' + where, key).fetchone()
                    if match is None or row_bytes(row) != row_bytes(tuple(match)):
                        raise Refused('Remote existing row differs or is outside the snapshot: ' + name)
            known_sources = {item['sha256']: item for item in current['sources']}
            if ('table', 'autonomous_source_chunks') in present:
                for digest, index, content in remote_rows(remote, 'autonomous_source_chunks', chunk_table):
                    item = known_sources.get(digest)
                    if item is None:
                        raise Refused('Remote original source is outside this snapshot.')
                    raw = (frozen / 'autonomous-sources-v1' / item['path']).read_bytes()
                    expected_chunks = max(1, (len(raw) + HostedSources.CHUNK_BYTES - 1) // HostedSources.CHUNK_BYTES)
                    if not 0 <= index < expected_chunks or content != raw[index * HostedSources.CHUNK_BYTES:(index + 1) * HostedSources.CHUNK_BYTES]:
                        raise Refused('Remote source chunk differs; no overwrite is allowed.')
            if args.mode == 'migrate':
                report['phase'] = 'schema'; save(receipt, report)
                for kind in ('table', 'index', 'view', 'trigger'):
                    for key, item in sorted(schemas.items()):
                        if item['type'] == kind and key not in present:
                            remote.execute(item['sql'])  # One autocommit DDL statement.
            elif any(key not in present for key in schemas):
                raise Refused('Remote schema is incomplete; verification cannot pass.')
        if args.mode == 'migrate':
            report['phase'] = 'sources'; save(receipt, report)
            publisher = HostedSources(database.connect)
            for item in current['sources']:
                raw = (frozen / 'autonomous-sources-v1' / item['path']).read_bytes()
                if publisher.publish(raw) != item['sha256'] or HostedSources(database.connect).read(item['sha256']) != raw:
                    raise Refused('Published source full readback differs.')
            # Parents first; never disable foreign keys or uniqueness checks.
            remaining, finished = set(tables), set()
            while remaining:
                ready = sorted(name for name in remaining if all(foreign[2] in finished for foreign in tables[name]['foreign_keys']))
                if not ready:
                    raise Refused('Foreign-key dependency cycle requires separate review.')
                for name in ready:
                    table = tables[name]; report.update(phase='rows', current_table=name); save(receipt, report)
                    with database.connect() as remote:
                        batch, size = [], 0
                        for row in ordered_rows(locals_[table['database']], name, table):
                            row = tuple(row); length = wire_size(row)
                            if length > WRITE_BYTES:
                                raise Refused('One row exceeds the reviewed wire bound.')
                            if batch and (len(batch) >= MAX_ROWS or (len(batch) + 1) * len(table['columns']) > MAX_PARAMETERS or size + length > WRITE_BYTES):
                                remote.execute(*insert_sql(name, table['columns'], batch)); batch, size = [], 0
                            batch.append(row); size += length
                        if batch:
                            remote.execute(*insert_sql(name, table['columns'], batch))
                    finished.add(name); remaining.remove(name)
        report['phase'] = 'full_readback'; save(receipt, report)
        with database.connect() as remote:
            final_schema = {(item['type'], item['name']): item for item in schema_objects(remote)}
            if any(key not in final_schema or sql_identity(final_schema[key]['sql']) != sql_identity(item['sql']) for key, item in schemas.items()):
                raise Refused('Final remote schema differs or is incomplete.')
            if any(key not in schemas and item['tbl_name'] != 'hosted_workflow_lease' for key, item in final_schema.items()):
                raise Refused('Final remote schema has unreviewed extra objects.')
            for name, table in sorted(tables.items()):
                result = table_digest(remote_rows(remote, name, table), table['columns'])
                expected = {key: table[key] for key in result}
                if result != expected:
                    raise Refused('Full remote table content/count differs: ' + name)
                report['tables'][name] = result; save(receipt, report)
            chunk_count = 0
            for digest, index, content in remote_rows(remote, 'autonomous_source_chunks', chunk_table):
                item = known_sources.get(digest)
                if item is None:
                    raise Refused('Unexpected original source discovered during final readback.')
                raw = (frozen / 'autonomous-sources-v1' / item['path']).read_bytes()
                expected_chunks = max(1, (len(raw) + HostedSources.CHUNK_BYTES - 1) // HostedSources.CHUNK_BYTES)
                if not 0 <= index < expected_chunks or content != raw[index * HostedSources.CHUNK_BYTES:(index + 1) * HostedSources.CHUNK_BYTES]:
                    raise Refused('Final source chunk differs.')
                chunk_count += 1
            expected_count = sum(max(1, (item['bytes'] + HostedSources.CHUNK_BYTES - 1) // HostedSources.CHUNK_BYTES) for item in current['sources'])
            if chunk_count != expected_count:
                raise Refused('Source chunk roster is incomplete or extended.')
        for item in current['sources']:
            # Fresh reader forces full remote readback; no publication cache.
            raw = HostedSources(database.connect).read(item['sha256'])
            if raw != (frozen / 'autonomous-sources-v1' / item['path']).read_bytes():
                raise Refused('Original source full readback differs.')
            report['sources'].append(item)
        if inventory(frozen) != current:
            raise Refused('Frozen snapshot changed during migration.')
    report.update(phase='verified', completed=True, tables_verified=len(tables), original_files_verified=len(current['sources']),
                  verified_at=datetime.now(timezone.utc).isoformat(), model_calls=0, provider_calls=0)
    save(receipt, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('inspect', 'snapshot', 'migrate', 'verify'))
    parser.add_argument('--source-root', type=Path, default=SOURCE)
    parser.add_argument('--hosting-root', type=Path, default=HOSTING)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--writers-stopped', action='store_true', help='Root confirms local and hosted writers/inference are disabled.')
    args = parser.parse_args()
    if args.mode != 'inspect' and (args.snapshot is None or not args.writers_stopped):
        parser.error('snapshot/network modes require --snapshot and explicit --writers-stopped confirmation')
    if args.mode in {'migrate', 'verify'} and args.receipt is None:
        parser.error('network modes require an outside-source --receipt path')
    result = inventory(args.source_root) if args.mode == 'inspect' else snapshot(args) if args.mode == 'snapshot' else migration(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print('MIGRATION REFUSED: ' + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:
        # Transport/server exceptions may contain credentials or SQL arguments.
        # Do not expose them or automatically retry an ambiguous operation.
        print('MIGRATION STOPPED: ' + type(error).__name__ + '; inspect the receipt and rerun the same frozen snapshot after review.', file=sys.stderr)
        raise SystemExit(3) from None

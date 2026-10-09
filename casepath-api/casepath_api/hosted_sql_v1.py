"""Bounded synchronous Hrana v2 transport for the authoritative cloud database.

A database acknowledgement is required before a caller can dispatch model HTTP.
Protocol/transport failures poison the connection; SQL errors retain its latest
baton so the caller can roll back. No request is retried.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import logging
import math
import re
import time
from urllib.parse import urlsplit

import httpx


class HostedStorageError(RuntimeError):
    pass


class HostedSQLFailure(HostedStorageError):
    """A received SQL error, distinct from an uncertain transport outcome."""


MAX_BYTES = 32 * 1024 * 1024
REQUEST_SECONDS = 12.0
INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1
_LOG = logging.getLogger(__name__)


def _https_origin(url):
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.hostname
                 and parsed.port in (None, 443) and parsed.username is None
                 and parsed.password is None and parsed.path in ('', '/')
                 and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise HostedStorageError('The persistent database origin is invalid.')
    return 'https://' + parsed.hostname.lower()


def _encode(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, bool):
        value = int(value)
    if type(value) is int:
        if not INT64_MIN <= value <= INT64_MAX:
            raise HostedStorageError('Database integer exceeds the signed 64-bit range.')
        return {'type': 'integer', 'value': str(value)}
    if type(value) is float and math.isfinite(value):
        return {'type': 'float', 'value': value}
    if isinstance(value, str):
        return {'type': 'text', 'value': value}
    if isinstance(value, bytes):
        return {'type': 'blob', 'base64': base64.b64encode(value).decode('ascii')}
    raise HostedStorageError('Unsupported database parameter type.')


def _decode(value):
    if not isinstance(value, dict):
        raise ValueError('invalid value')
    kind = value.get('type')
    data = value.get('value')
    if kind == 'null':
        return None
    if kind == 'integer' and isinstance(data, str) and re.fullmatch(r'-?(0|[1-9][0-9]*)', data):
        number = int(data)
        if INT64_MIN <= number <= INT64_MAX:
            return number
    if kind == 'float' and type(data) in (int, float) and math.isfinite(data):
        return float(data)
    if kind == 'text' and isinstance(data, str):
        return data
    if kind == 'blob' and isinstance(value.get('base64'), str):
        # Turso emits standard base64 without trailing padding. Accept both
        # forms while retaining strict alphabet/structure validation.
        encoded = value['base64']
        return base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True)
    raise ValueError('invalid value')


class _Row:
    """The sqlite3.Row behavior used by CasePath: index, name, keys and dict."""
    def __init__(self, names, values):
        self._names, self._values = names, values

    def keys(self):
        return self._names

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            raise KeyError(key) from None


@dataclass(frozen=True)
class _Result:
    names: tuple
    rows: tuple
    rowcount: int
    lastrowid: int | None


class _Cursor:
    def __init__(self, result):
        self._result, self._position = result, 0
        self.rowcount, self.lastrowid = result.rowcount, result.lastrowid
        self.description = tuple((name, None, None, None, None, None, None) for name in result.names)

    def fetchone(self):
        if self._position == len(self._result.rows):
            return None
        values = self._result.rows[self._position]
        self._position += 1
        return _Row(self._result.names, values)

    def fetchall(self):
        return list(self)

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class LibsqlConnection:
    """Small DB-API-compatible surface backed by bounded Hrana HTTP requests."""
    def __init__(self, url, token, *, client=None):
        self._origin = _https_origin(url)
        self._base = self._origin
        self._token = token
        self._client = client if client is not None else httpx.Client(
            follow_redirects=False, trust_env=False,
            transport=httpx.HTTPTransport(retries=0),
            timeout=httpx.Timeout(connect=3, read=4, write=4, pool=2))
        self._baton = None
        self._poisoned = self._closed = self._in_transaction = False
        self._cache = {}

    def __repr__(self):
        return 'LibsqlConnection(credential=<redacted>)'

    @property
    def in_transaction(self):
        return self._in_transaction

    def _usable(self):
        if self._closed or self._poisoned:
            raise HostedStorageError('The persistent database connection is no longer usable.')

    def _uncertain(self):
        self._poisoned = True
        self._cache.clear()
        raise HostedStorageError('The persistent database operation is unconfirmed.') from None

    def _send(self, requests, *, ending=False):
        self._usable()
        payload = json.dumps({'baton': self._baton, 'requests': requests},
                             allow_nan=False, separators=(',', ':')).encode()
        if len(payload) > MAX_BYTES:
            raise HostedStorageError('The persistent database request exceeds its size bound.')
        deadline = time.monotonic() + REQUEST_SECONDS
        phase = 'request'
        try:
            with self._client.stream('POST', self._base + '/v2/pipeline',
                    headers={'Authorization': 'Bearer ' + self._token,
                             'Content-Type': 'application/json', 'Accept-Encoding': 'identity'}, content=payload) as response:
                phase = 'http_status_and_encoding'
                if response.status_code != 200 or response.headers.get('content-encoding', 'identity') != 'identity':
                    raise ValueError('HTTP failure')
                phase = 'response_body'
                body = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline or len(body) + len(chunk) > MAX_BYTES:
                        raise ValueError('response bound')
                    body.extend(chunk)
                if time.monotonic() > deadline:
                    raise ValueError('response deadline')
            def invalid_constant(_):
                raise ValueError('invalid JSON constant')
            phase = 'response_json'
            result = json.loads(body, parse_constant=invalid_constant)
            baton, base = result['baton'], result['base_url']
            entries = result['results']
            if not (baton is None or isinstance(baton, str) and 0 < len(baton) <= 65536):
                raise ValueError('invalid baton')
            phase = 'response_origin'
            if base is not None and _https_origin(base) != self._origin:
                raise ValueError('unexpected database origin')
            phase = 'response_protocol'
            if not isinstance(entries, list) or len(entries) != len(requests):
                raise ValueError('invalid response count')
            for request, entry in zip(requests, entries):
                if not isinstance(entry, dict):
                    raise ValueError('invalid response')
                if entry.get('type') == 'ok':
                    if not isinstance(entry.get('response'), dict) or entry['response'].get('type') != request['type']:
                        raise ValueError('invalid response type')
                elif entry.get('type') != 'error' or not isinstance(entry.get('error'), dict):
                    raise ValueError('invalid response type')
            if self._in_transaction and baton is None and not ending:
                raise ValueError('transaction stream closed')
        except Exception as error:
            # Fixed phase labels and exception classes only: no SQL, parameters,
            # response bodies, endpoint URLs, batons, or credential values.
            _LOG.warning('hosted_database_failure phase=%s category=%s', phase, type(error).__name__)
            self._uncertain()
        # A SQL error still rotates the baton. Save it before raising.
        self._baton = baton
        if base is not None:
            self._base = _https_origin(base)
        if any(entry['type'] == 'error' for entry in entries):
            self._cache.clear()
            raise HostedSQLFailure('The persistent database rejected the SQL statement.') from None
        return [entry['response'] for entry in entries]

    def _result(self, value):
        try:
            cols, rows = value['cols'], value['rows']
            if not isinstance(cols, list) or not isinstance(rows, list):
                raise ValueError('invalid rows')
            names = tuple(column['name'] for column in cols)
            if any(name is not None and not isinstance(name, str) for name in names):
                raise ValueError('invalid columns')
            if any(not isinstance(row, list) or len(row) != len(names) for row in rows):
                raise ValueError('invalid row length')
            decoded = tuple(tuple(_decode(item) for item in row) for row in rows)
            count, rowid = value['affected_row_count'], value.get('last_insert_rowid')
            if type(count) is not int or count < 0:
                raise ValueError('invalid count')
            if rowid is not None:
                rowid = _decode({'type': 'integer', 'value': rowid})
            return _Result(names, decoded, count, rowid)
        except Exception:
            self._uncertain()

    @staticmethod
    def _statement(sql, parameters=()):
        if not isinstance(sql, str) or not sql.strip() or not isinstance(parameters, (tuple, list)):
            raise HostedStorageError('Invalid database statement.')
        args = [_encode(value) for value in parameters]
        statement = {'sql': sql, 'args': args, 'want_rows': True}
        key = json.dumps(statement, allow_nan=False, separators=(',', ':'), sort_keys=True)
        kind = sql.strip().split(None, 1)[0].rstrip(';').upper()
        return statement, key, kind

    def execute(self, sql, parameters=()):
        self._usable()
        statement, key, kind = self._statement(sql, parameters)
        if kind == 'SELECT' and self._in_transaction and key in self._cache:
            return _Cursor(self._cache[key])
        if kind != 'SELECT':
            self._cache.clear()
        ending = kind in ('COMMIT', 'ROLLBACK', 'END')
        response = self._send([{'type': 'execute', 'stmt': statement}], ending=ending)[0]
        result = self._result(response.get('result'))
        if kind == 'BEGIN':
            if self._baton is None:
                self._uncertain()
            self._in_transaction = True
        elif ending:
            self._in_transaction = False
        return _Cursor(result)

    def prefetch(self, queries):
        """Cache (SELECT SQL, positional parameters) pairs within this transaction."""
        self._usable()
        if not self._in_transaction:
            raise HostedStorageError('Database prefetch requires an active transaction.')
        statements, keys = [], []
        for sql, parameters in queries:
            statement, key, kind = self._statement(sql, parameters)
            if kind != 'SELECT':
                raise HostedStorageError('Database prefetch accepts SELECT statements only.')
            if key not in self._cache and key not in keys:
                statements.append(statement)
                keys.append(key)
            if len(statements) > 128:
                raise HostedStorageError('Database prefetch exceeds its statement bound.')
        if not statements:
            return
        steps = [{'stmt': statement, **({'condition': {'type': 'ok', 'step': i-1}} if i else {})}
                 for i, statement in enumerate(statements)]
        response = self._send([{'type': 'batch', 'batch': {'steps': steps}}])[0]
        try:
            results = response['result']['step_results']
            errors = response['result']['step_errors']
            if not isinstance(results, list) or not isinstance(errors, list) or len(results) > len(keys) or len(errors) > len(keys):
                raise ValueError('invalid batch length')
            results = results + [None] * (len(keys) - len(results))
            errors = errors + [None] * (len(keys) - len(errors))
            if any(error is not None and not isinstance(error, dict) for error in errors):
                raise ValueError('invalid batch error')
        except Exception:
            self._uncertain()
        if any(error is not None for error in errors):
            self._cache.clear()
            raise HostedSQLFailure('The persistent database rejected a prefetched query.') from None
        parsed = [self._result(result) for result in results]
        self._cache.update(zip(keys, parsed))

    def executescript(self, sql):
        self._usable()
        self._cache.clear()
        own_transaction = not self._in_transaction
        if own_transaction:
            self.execute('BEGIN IMMEDIATE')
        try:
            self._send([{'type': 'sequence', 'sql': sql}])
            if own_transaction:
                self.commit()
        except BaseException:
            if own_transaction:
                try:
                    self.rollback()
                except Exception:
                    pass  # Preserve the original failure, including unknown commit.
            raise

    def commit(self):
        self._usable()
        if self._in_transaction:
            self.execute('COMMIT')

    def rollback(self):
        self._usable()
        if self._in_transaction:
            self.execute('ROLLBACK')

    def close(self):
        if self._closed:
            return
        try:
            if self._baton is not None and not self._poisoned:
                try:
                    self._send([{'type': 'close'}], ending=True)
                except Exception:
                    pass  # Closing cannot undo an acknowledged COMMIT.
        finally:
            self._closed = True
            self._cache.clear()
            self._client.close()

    def __enter__(self):
        self._usable()
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.commit()
            else:
                try:
                    self.rollback()
                except Exception:
                    pass  # Never obscure the exception that caused rollback.
        finally:
            self.close()
        return False


class TursoDatabase:
    def __init__(self, url, token, *, client_factory=None):
        if not isinstance(url, str) or not url.startswith('libsql://'):
            raise ValueError('A remote libSQL database URL is required.')
        try:
            self._url = _https_origin('https://' + url[len('libsql://'):])
        except HostedStorageError:
            raise ValueError('A remote libSQL database URL is required.') from None
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError('A server database credential is required.')
        self._token, self._client_factory = token, client_factory

    def __repr__(self):
        return 'TursoDatabase(credential=<redacted>)'

    def connect(self):
        client = self._client_factory() if self._client_factory is not None else None
        return LibsqlConnection(self._url, self._token, client=client)

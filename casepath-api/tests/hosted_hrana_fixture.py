import json
import httpx
from casepath_api.hosted_sql_v1 import LibsqlConnection, _https_origin, _encode, _decode

class MockHrana:
    """Test helper: one real SQLite connection per Hrana stream, one shared file.

    Pytest usage:
        server = MockHrana(tmp_path / 'database.sqlite')
        connect = server.connection
        try:
            store = WorkStore(tmp_path / 'unused', connection_factory=connect)
            ...
        finally:
            server.close()

    Call fail_next('timeout', sql_prefix='COMMIT') to lose a COMMIT response
    after SQLite committed it. requests retains SQL payloads, never auth headers.
    Trailing nulls in batch response arrays are omitted by default deliberately.
    This helper creates no network connections and does not use user credentials.
    """
    def __init__(self, path, *, origin='https://fixture.turso.io', trim_trailing_nulls=True):
        import sqlite3
        from threading import RLock
        self.path, self.origin = str(path), _https_origin(origin)
        self._sqlite3, self._lock = sqlite3, RLock()
        self._streams, self._counter, self._faults = {}, 0, []
        self.requests, self.trim_trailing_nulls = [], trim_trailing_nulls

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle), follow_redirects=False, trust_env=False)

    def connection(self):
        return LibsqlConnection(self.origin, 'fixture-secret-' * 4, client=self.client())

    def fail_next(self, kind, *, sql_prefix=None):
        self._faults.append((kind, sql_prefix.upper() if sql_prefix else None))

    @property
    def open_streams(self):
        return len(self._streams)

    @staticmethod
    def _value(value):
        wire = _encode(value)
        if wire['type'] == 'blob':
            wire['base64'] = wire['base64'].rstrip('=')
        return wire

    def _statement(self, connection, stmt):
        cursor = connection.execute(stmt['sql'], tuple(_decode(arg) for arg in stmt.get('args', [])))
        return {'cols': [{'name': col[0], 'decltype': None} for col in cursor.description or ()],
                'rows': [[self._value(value) for value in row] for row in cursor.fetchall()],
                'affected_row_count': max(0, cursor.rowcount),
                'last_insert_rowid': str(cursor.lastrowid) if cursor.lastrowid is not None else None}

    @staticmethod
    def _condition(condition, results, errors):
        if condition is None:
            return True
        kind = condition['type']
        if kind == 'ok':
            return results[condition['step']] is not None
        if kind == 'error':
            return errors[condition['step']] is not None
        if kind == 'not':
            return not MockHrana._condition(condition['cond'], results, errors)
        if kind in ('and', 'or'):
            parts = [MockHrana._condition(part, results, errors) for part in condition['conds']]
            return all(parts) if kind == 'and' else any(parts)
        raise ValueError('unsupported mock condition')

    def _operation(self, connection, request):
        kind = request['type']
        if kind == 'execute':
            return {'type': kind, 'result': self._statement(connection, request['stmt'])}
        if kind == 'sequence':
            pending = ''
            for char in request['sql']:
                pending += char
                if char == ';' and self._sqlite3.complete_statement(pending):
                    connection.execute(pending)
                    pending = ''
            if pending.strip():
                connection.execute(pending)
            return {'type': kind}
        if kind == 'batch':
            results, errors = [], []
            for step in request['batch']['steps']:
                if not self._condition(step.get('condition'), results, errors):
                    results.append(None); errors.append(None); continue
                try:
                    results.append(self._statement(connection, step['stmt'])); errors.append(None)
                except self._sqlite3.Error:
                    results.append(None); errors.append({'message': 'Fixture SQL failure', 'code': 'SQLITE_ERROR'})
            if self.trim_trailing_nulls:
                while results and results[-1] is None:
                    results.pop()
                while errors and errors[-1] is None:
                    errors.pop()
            return {'type': kind, 'result': {'step_results': results, 'step_errors': errors}}
        if kind == 'close':
            connection.close()  # Real SQLite rollback of any still-open transaction.
            return {'type': kind}
        raise ValueError('unsupported mock operation')

    def handle(self, request):
        with self._lock:
            assert str(request.url) == self.origin + '/v2/pipeline'
            data = json.loads(request.content)
            self.requests.append(data)
            incoming = data.get('baton')
            if incoming is None:
                connection = self._sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=0.05)
                connection.execute('PRAGMA foreign_keys=ON')
            else:
                connection = self._streams.pop(incoming, None)
                if connection is None:
                    return httpx.Response(400, json={'message': 'Invalid or expired fixture baton'})
            entries, closed = [], False
            for operation in data['requests']:
                try:
                    if closed:
                        raise self._sqlite3.OperationalError('stream closed')
                    response = self._operation(connection, operation)
                    entries.append({'type': 'ok', 'response': response})
                    closed = operation['type'] == 'close'
                except self._sqlite3.Error:
                    entries.append({'type': 'error', 'error': {'message': 'Fixture SQL failure', 'code': 'SQLITE_ERROR'}})
            self._counter += 1
            baton = None if closed else 'mock-baton-' + str(self._counter)
            if baton is not None:
                self._streams[baton] = connection
            body = {'baton': baton, 'base_url': None, 'results': entries}
            fault = None
            if self._faults:
                kind, prefix = self._faults[0]
                if prefix is None or any(item.get('stmt', {}).get('sql', '').upper().startswith(prefix)
                                         for item in data['requests']):
                    self._faults.pop(0)
                    fault = kind
            if fault == 'timeout':
                raise httpx.ReadTimeout('Simulated lost response', request=request)
            if fault == 'http_error':
                return httpx.Response(503, json={'message': 'Fixture HTTP error'})
            if fault == 'origin':
                body['base_url'] = 'https://unexpected.example'
            if fault == 'missing_result':
                body['results'] = []
            if fault == 'closed_baton':
                body['baton'] = None
            return httpx.Response(200, json=body)

    def close(self):
        with self._lock:
            for connection in self._streams.values():
                connection.close()
            self._streams.clear()

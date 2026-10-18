"""Bounded local guard/MockTransport checks; no sockets or SQLite operations."""
import ast
from contextlib import contextmanager
import hashlib
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path
import sys
import tempfile
import threading

R = Path(__file__).resolve().parent
repo = Path('/workspace/casepath-release-ae0-shard3')
sys.path.insert(0, str(repo / 'casepath-api'))
spec = importlib.util.spec_from_file_location('native_phase_probe', R / 'native_phase_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
import httpx
from casepath_api import hosted_sql_v1 as sql, hosted_storage_v1 as hs

passed = []
ast.parse((R / 'native_phase_probe.py').read_text())
passed.append('syntax')
store = hs.HostedAutonomousStore.__new__(hs.HostedAutonomousStore)
allowed = probe._sealed_queries(hs, store)
proof_sql = hs._proof_query('claim_loop_events', hs._JOURNAL_COLUMNS,
    'casepath-journal-bytes-v1', 'session_id=?', 'loop_id,sequence')
def execute(text, args=()):
    return {'type': 'execute', 'stmt': sql.LibsqlConnection._statement(text, args)[0]}
commands = [execute('BEGIN'), execute(hs._schema_query('claim_loop_events')),
    execute(proof_sql, ('fixture-session', 1)), execute('COMMIT'), {'type': 'close'}]
def payload(rows):
    return json.dumps({'baton': None, 'requests': rows}).encode()
dispatches = []
secret = 'PRIVATE_FIXTURE_MUST_NOT_APPEAR'
def handler(request):
    dispatches.append(True)
    callback = request.extensions['trace']
    for name in ('connect_tcp', 'start_tls'):
        callback('connection.' + name + '.started', {'host': secret})
        callback('connection.' + name + '.complete', {'return_value': secret})
    return httpx.Response(200, content=b'local fixture body', headers={'content-encoding': 'identity'})

with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False) as client:
    observer = probe._Client(client, 'https://fixture.turso.io', allowed, probe._Budget(30, 1), sql)
    kinds, _ = observer._guard(('POST', 'https://fixture.turso.io/v2/pipeline'), {'content': payload(commands)})
    assert kinds == ['BEGIN', 'journal_schema', 'journal_proof', 'COMMIT', 'close']
    passed.append('exact_proof_query_with_quoted_question_marks_admitted')
    invalid = [execute('CREATE TABLE forbidden(x)'), execute('INSERT INTO forbidden VALUES(1)'),
               execute("SELECT load_extension('x')"), execute('SELECT 1; DELETE FROM forbidden'),
               {'type': 'sequence', 'sql': 'SELECT 1'}]
    for item in invalid:
        try:
            with observer.stream('POST', 'https://fixture.turso.io/v2/pipeline', content=payload([item, {'type': 'close'}])):
                raise AssertionError('invalid request entered transport')
        except probe.ProbeRefused:
            pass
    assert not dispatches
    passed.append('all_unknown_sql_and_protocol_denied_before_dispatch')
    for method, url in [('GET', 'https://fixture.turso.io/v2/pipeline'),
                        ('POST', 'https://other.invalid/v2/pipeline'),
                        ('POST', 'https://fixture.turso.io/other')]:
        try:
            observer._guard((method, url), {'content': payload(commands)})
            raise AssertionError('unexpected destination admitted')
        except probe.ProbeRefused:
            pass
    passed.append('method_origin_path_pinned')
    with observer.stream('POST', 'https://fixture.turso.io/v2/pipeline',
                         content=payload(commands), headers={'Authorization': 'Bearer ' + secret}) as response:
        assert b''.join(response.iter_bytes()) == b'local fixture body'
    row = observer.records[0]
    assert row['response_bytes'] == len(b'local fixture body') and row['headers_seconds'] >= 0 and row['body_seconds'] >= 0
    assert {x['event'] for x in row['trace']} == {'connect_tcp', 'start_tls'}
    assert secret not in json.dumps(observer.records)
    passed.append('headers_body_trace_and_redaction_mock_only')
    try:
        with observer.stream('POST', 'https://fixture.turso.io/v2/pipeline', content=payload(commands)):
            raise AssertionError('request limit ignored')
    except probe.ProbeRefused:
        pass
    assert len(dispatches) == 1
    passed.append('request_budget_denied_before_second_dispatch')

locks = {}
raw = threading.RLock()
wrapped = probe._WaitLock(raw, 'test', locks, probe._Budget(30, 1))
with wrapped:
    with wrapped:
        pass
acquired, release = threading.Event(), threading.Event()
def hold():
    with raw:
        acquired.set()
        assert release.wait(2)
thread = threading.Thread(target=hold)
thread.start()
assert acquired.wait(2)
timer = threading.Timer(0.02, release.set)
timer.start()
with wrapped:
    pass
thread.join(2)
timer.join(2)
assert not thread.is_alive() and locks['test']['calls'] == 3 and locks['test']['wait_seconds'] > 0
passed.append('reentrant_and_contended_lock_measurement')

calls = []
def timeout(request):
    calls.append(True)
    raise httpx.ReadTimeout(secret)
db = sql.TursoDatabase('libsql://fixture.turso.io', 'fixture-only-' * 4, reuse_http=True)
db._shared_client.close()
# Local test only: replace the private client with a no-socket MockTransport.
db._shared_client = httpx.Client(transport=httpx.MockTransport(timeout), follow_redirects=False, trust_env=False)
original = db._shared_client
try:
    with tempfile.TemporaryDirectory(dir=R) as directory:
        result = probe.run_probe(db, directory, expected_origin='https://fixture.turso.io',
                                 idle_seconds=31, max_requests=1, max_seconds=45)
        assert result['all_ok'] is False and len(result['phases']) == 1
        assert result['phases'][0]['error_category'] == 'HostedStorageError'
        assert len(calls) == 1 and result['total_requests'] == 1
        assert db._shared_client is original and not original.is_closed and not list(Path(directory).iterdir())
        assert secret not in json.dumps(result)
    passed.append('actual_constructor_bypass_failure_stops_without_retry_and_restores_private_client')
finally:
    db.close()

receipt = {'verdict': 'PASS', 'checks': passed, 'check_count': len(passed),
    'probe_sha256': hashlib.sha256((R / 'native_phase_probe.py').read_bytes()).hexdigest(),
    'dependencies': {name: version(name) for name in ('httpx', 'httpcore', 'fastapi', 'starlette', 'pydantic')},
    'qualifications': ['MockTransport only: no real sockets, database operations, SQLite creation, services or credentials.',
        'Trace events are injected mock events; no native connection-reuse or performance claim.',
        'Cloud FastAPI/Starlette differ from pinned Mac runtime; no encoding/native timing acceptance claimed.',
        'The full successful four-phase native sequence is not executed in Cloud.'],
    'native_or_production_requests': 0, 'sqlite_operations': 0, 'product_edits': 0}
(R / 'local-checks.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))

"""Private export uses exact, small reads and the native seed admission path."""
import base64
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sqlite3
import tempfile
from types import SimpleNamespace

import pytest

from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.hosted_sql_v1 import HostedStorageError
from casepath_api.hosted_storage_v1 import JOURNAL_SCHEMA, HostedSources
from hosted_hrana_fixture import MockHrana

export = runpy.run_path(str(Path(__file__).parents[1] / 'tools/export_read_seed.py'))
COMMIT = 'a' * 40
READ_BODY = json.dumps({'baton': None, 'requests': [
    {'type': 'execute', 'stmt': {'sql': 'SELECT 1', 'args': [], 'want_rows': True}}, {'type': 'close'}]}).encode()


@pytest.fixture
def tmp_path():
    # The product gate keeps TMPDIR inside its checkout. Export fixtures need
    # a private directory outside Git so the real destination guard is tested.
    with tempfile.TemporaryDirectory(
        prefix='casepath-export-tests-', dir=Path('/tmp').resolve()
    ) as directory:
        yield Path(directory)


class ObservedHrana(MockHrana):
    def __init__(self, path):
        super().__init__(path)
        self.body_sizes = []
        self.after = None

    def handle(self, request):
        response = super().handle(request)
        self.body_sizes.append(len(response.content))
        if self.after is not None:
            self.after(json.loads(request.content))
        return response


@pytest.fixture
def native(tmp_path):
    local = AutonomousStore(tmp_path / 'native.sqlite3')
    # Force a UTF-8 codepoint over the slice boundary and a multi-chunk blob.
    raw = (b'x' * 32767 + '€'.encode() + bytes(range(256))) * 9
    state = local.intake({'title': 'Bounded export fixture', 'message': 'Original synthetic statement.',
                         'files': [{'file_name': 'original.bin', 'media_type': 'application/octet-stream',
                                    'content_base64': base64.b64encode(raw).decode()}]}, 'export.fixture.intake')
    local.append(state['claim_id'], 'knowledge.published', {'knowledge': {
        'knowledge_id': 'fixture.large.refusal', 'qualification': {'status': 'quarantined',
        'reason': '€' * 30000}}}, expected_revision=state['revision'],
        expected_state_sha256=state['state_sha256'], idempotency_key='export.fixture.publication')
    server = ObservedHrana(tmp_path / 'hosted.sqlite3')
    with sqlite3.connect(local.path) as source, sqlite3.connect(server.path) as target:
        target.executescript(JOURNAL_SCHEMA)
        rows = source.execute('SELECT * FROM claim_loop_events WHERE session_id=? ORDER BY loop_id,sequence',
                              (SESSION_ID,)).fetchall()
        # Native replay accepts equivalent JSON whitespace; the raw SQL proof
        # must preserve those original TEXT bytes instead of reserializing it.
        rows = [(*row[:6], json.dumps(json.loads(row[6]), ensure_ascii=False, indent=2) + '\n', row[7])
                for row in rows]
        target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)', rows)
        for path in local.source_root.iterdir():
            content = path.read_bytes()
            target.executemany('INSERT INTO autonomous_source_chunks VALUES (?,?,?)',
                [(path.name, index, content[start:start + HostedSources.CHUNK_BYTES])
                 for index, start in enumerate(range(0, max(1, len(content)), HostedSources.CHUNK_BYTES))])
    yield local, server, rows
    server.close()


def test_exact_native_export_is_small_select_only_and_never_initializes(native, tmp_path, monkeypatch):
    local, server, rows = native
    output = tmp_path / 'private-package/hosted-read-seed-v1.json'
    output.parent.mkdir(mode=0o700)
    monkeypatch.setattr(export['HostedAutonomousStore'], '__init__', lambda *a, **k: pytest.fail('store init'))
    receipt = export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    value = json.loads(output.read_bytes())
    assert set(value) == {'contract', 'deployment_commit', 'journal_rows', 'sources'}
    assert value['deployment_commit'] == COMMIT
    assert [tuple(row[key] for key in export['_JOURNAL_COLUMNS']) for row in value['journal_rows']] == rows
    assert {item['sha256']: base64.b64decode(item['content_base64'], validate=True) for item in value['sources']} == {
        path.name: path.read_bytes() for path in local.source_root.iterdir()}
    assert receipt['sha256'] == sha256(output.read_bytes()).hexdigest()
    assert output.stat().st_mode & 0o777 == 0o600
    assert max(server.body_sizes) <= export['RESPONSE_BYTES'] == 64 * 1024
    statements = [entry['stmt']['sql'] for request in server.requests for entry in request['requests']
                  if entry['type'] == 'execute']
    assert all(sql.startswith(('SELECT', 'BEGIN', 'COMMIT')) for sql in statements)
    assert any('substr(CAST(content AS BLOB)' in sql for sql in statements)
    assert not any(sql.startswith('SELECT typeof(' + key + ')') for sql in statements for key in
                   ('session_id', 'loop_id', 'idempotency_key', 'command_sha256', 'event_sha256', 'created_at'))
    assert not any('SELECT *' in sql or 'SELECT j.*' in sql for sql in statements)
    assert server.open_streams == 0


@pytest.mark.parametrize('failure', ['timeout', 'missing_result'])
def test_failed_slice_never_retries_or_publishes(native, tmp_path, failure):
    _, server, _ = native
    output = tmp_path / 'never-published.json'
    server.fail_next(failure, sql_prefix='SELECT typeof(event_json)')
    with pytest.raises(HostedStorageError):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    assert not output.exists()
    failed = [request for request in server.requests if any(entry.get('stmt', {}).get('sql', '').startswith(
        'SELECT typeof(event_json)') for entry in request['requests'])]
    assert len(failed) == 1


@pytest.mark.parametrize('mutation', ['old_row', 'extra_chunk', 'schema'])
def test_mutation_before_final_atomic_proof_never_publishes(native, tmp_path, mutation):
    _, server, _ = native
    output = tmp_path / 'never-published.json'
    mutated = []

    def change(request):
        if mutated or not any('substr(CAST(content AS BLOB)' in item.get('stmt', {}).get('sql', '')
                              for item in request['requests']):
            return
        mutated.append(True)
        with sqlite3.connect(server.path) as target:
            if mutation == 'old_row':
                target.execute("UPDATE claim_loop_events SET created_at=created_at||' ' WHERE sequence=1")
            elif mutation == 'extra_chunk':
                digest = target.execute('SELECT sha256 FROM autonomous_source_chunks ORDER BY sha256 LIMIT 1').fetchone()[0]
                target.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)', (digest, 99, b'extra'))
            else:
                target.execute('CREATE INDEX fixture_schema_change ON claim_loop_events(created_at)')
    server.after = change
    with pytest.raises(AutonomousStoreError):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    assert mutated and not output.exists()


def test_existing_output_is_preserved_before_any_read(native, tmp_path):
    _, server, _ = native
    output = tmp_path / 'existing.json'
    output.write_bytes(b'preserve')
    with pytest.raises(AutonomousStoreError):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    assert output.read_bytes() == b'preserve' and not server.requests


def test_missing_private_upload_directory_stops_before_any_read(native, tmp_path):
    _, server, _ = native
    output = tmp_path / 'missing/hosted-read-seed-v1.json'
    with pytest.raises(AutonomousStoreError, match='existing private upload directory'):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    assert not server.requests and not output.parent.exists()


@pytest.mark.parametrize('destination', ['arbitrary', 'exact_ignored', 'traversal', 'symlink'])
def test_output_stays_outside_git_and_rejects_unsafe_paths(native, tmp_path, destination):
    _, server, _ = native
    checkout = tmp_path / 'checkout'
    (checkout / '.git').mkdir(parents=True)
    (checkout / '.git/HEAD').write_text('ref: refs/heads/main\n')
    if destination == 'arbitrary':
        output = checkout / 'payload.json'
    elif destination == 'exact_ignored':
        output = checkout / 'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json'
    elif destination == 'traversal':
        output = tmp_path / 'private/../payload.json'
    else:
        (tmp_path / 'alias').symlink_to(checkout, target_is_directory=True)
        output = tmp_path / 'alias/payload.json'
    with pytest.raises(AutonomousStoreError):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output)
    assert not server.requests and not output.exists()


def test_cli_is_mac_only_without_reading_credentials(monkeypatch):
    monkeypatch.setattr(export['sys'], 'platform', 'linux')
    with pytest.raises(SystemExit, match='Mac'):
        export['main'](['--deployment-commit', COMMIT, '--output', '/tmp/not-created-seed.json'])


def test_export_transport_bounds_final_proof_request_and_response(monkeypatch):
    calls = []

    class Response:
        def iter_bytes(self):
            yield b'x' * 32768
            yield b'x' * 32769

    class Client:
        @contextmanager
        def stream(self, *args, **kwargs):
            calls.append(kwargs['content'])
            yield Response()

        def close(self):
            pass

    monkeypatch.setitem(export['_BoundedClient'].__init__.__globals__, '_http_client', Client)
    client = export['_BoundedClient']()
    with pytest.raises(HostedStorageError, match='request'):
        with client.stream('POST', 'https://fixture.invalid', content=b'x' * 65537):
            pytest.fail('oversized final proof request entered transport')
    assert calls == []
    with pytest.raises(HostedStorageError, match='response'):
        with client.stream('POST', 'https://fixture.invalid', content=READ_BODY) as response:
            list(response.iter_bytes())
    assert len(calls) == 1


@pytest.mark.parametrize('operation', [
    {'type': 'execute', 'stmt': {'sql': 'INSERT INTO forbidden VALUES (1)'}},
    {'type': 'execute', 'stmt': {'sql': 'SELECT 1; DELETE FROM forbidden'}},
    {'type': 'sequence', 'sql': 'CREATE TABLE forbidden(x)'},
    {'type': 'batch', 'batch': {'steps': []}},
])
def test_export_transport_refuses_mutation_protocol_before_dispatch(operation, monkeypatch):
    monkeypatch.setitem(export['_BoundedClient'].__init__.__globals__, '_http_client',
                        lambda: SimpleNamespace(stream=lambda *a, **k: pytest.fail('write reached client')))
    client = export['_BoundedClient']()
    with pytest.raises(HostedStorageError, match='read-only'):
        with client.stream('POST', 'https://fixture.invalid', content=json.dumps({'requests': [operation]}).encode()):
            pytest.fail('write entered stream')


@pytest.mark.parametrize('bound', ['requests', 'request_bytes', 'response_bytes', 'elapsed'])
def test_export_fixed_total_budget_stops_without_retry(bound, monkeypatch):
    calls = []

    class Client:
        @contextmanager
        def stream(self, *args, **kwargs):
            calls.append(1)
            yield SimpleNamespace(iter_bytes=lambda: iter([b'fixed fixture response']))

    globals_ = export['_BoundedClient'].__init__.__globals__
    monkeypatch.setitem(globals_, '_http_client', Client)
    client = export['_BoundedClient']()
    if bound == 'requests':
        client.requests = export['MAX_EXPORT_REQUESTS']
    elif bound == 'request_bytes':
        client.wire_bytes = export['MAX_EXPORT_WIRE_BYTES'] - len(READ_BODY) + 1
    elif bound == 'response_bytes':
        client.wire_bytes = export['MAX_EXPORT_WIRE_BYTES'] - len(READ_BODY)
    else:
        monkeypatch.setitem(globals_, 'time', SimpleNamespace(monotonic=lambda: client.started +
                            export['MAX_EXPORT_SECONDS'] - export['REQUEST_SECONDS'] + 1))
    with pytest.raises(HostedStorageError, match='budget'):
        with client.stream('POST', 'https://fixture.invalid', content=READ_BODY) as response:
            list(response.iter_bytes())
    assert len(calls) == (1 if bound == 'response_bytes' else 0)


def test_elapsed_budget_rechecked_after_final_proof_before_publication(native, tmp_path):
    _, server, _ = native
    output = tmp_path / 'never.json'

    def expired():
        raise HostedStorageError('fixed elapsed budget expired')

    with pytest.raises(HostedStorageError, match='expired'):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=output, check_budget=expired)
    assert not output.exists()
    assert any('crypto_sha256' in entry.get('stmt', {}).get('sql', '')
               for request in server.requests for entry in request['requests'])


@pytest.mark.parametrize('mutation', ['blob_event_json', 'gap', 'oversized_chunk'])
def test_invalid_metadata_stops_before_corresponding_payload(native, tmp_path, mutation):
    _, server, _ = native
    with sqlite3.connect(server.path) as target:
        if mutation == 'blob_event_json':
            target.execute('UPDATE claim_loop_events SET event_json=CAST(event_json AS BLOB)')
        elif mutation == 'gap':
            target.execute('DROP TRIGGER autonomous_source_chunks_no_delete')
            target.execute('DELETE FROM autonomous_source_chunks WHERE chunk_index=0 AND sha256 IN '
                           '(SELECT sha256 FROM autonomous_source_chunks WHERE chunk_index=1)')
        else:
            target.execute('DROP TRIGGER autonomous_source_chunks_no_update')
            target.execute('UPDATE autonomous_source_chunks SET content=? WHERE chunk_index=0',
                           (b'x' * (HostedSources.CHUNK_BYTES + 1),))
    with pytest.raises(AutonomousStoreError):
        export['export_seed'](server.connection, deployment_commit=COMMIT, output=tmp_path / 'never.json')
    payloads = [entry['stmt']['sql'] for request in server.requests for entry in request['requests']
                if entry['type'] == 'execute' and ' AS payload FROM ' in entry['stmt']['sql']]
    if mutation == 'blob_event_json':
        assert payloads == []
    else:
        assert not any('substr(CAST(content AS BLOB)' in sql for sql in payloads)
    assert not (tmp_path / 'never.json').exists()

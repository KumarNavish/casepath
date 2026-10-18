"""Temporary native READ-ONLY phase probe; the private Mac caller owns authentication.

Use a dedicated, quiescent, unmodified default TursoDatabase(reuse_http=True), an existing empty local
directory and the explicitly supplied HTTPS origin. No app/store initialization,
credentials/environment access, retries, writes or response contents are exported.
Encoding matches FastAPI's no-response-model primitives, not a complete API run.
The overall budget is cooperative; each send reserves the SDK's full 12s deadline.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
from threading import RLock
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

COMMIT = '8f230fd4ad455a15a7a53803ae7b857a4db2aaff'
HASHES = {
    'autonomous_knowledge_v1': '5a36ec3d418063abb44c34c653a45c3a8804527fbd8cd362c77be5a45654c464',
    'autonomous_store_v1': 'ae42896a74867342117dc407bcadd3ba3a01f494fecca489969b00943744a06f',
    'hosted_storage_v1': '737820c41572e97841bde2ff7b87b91e668cb7dce1be93296576c53ff0a858dd',
    'hosted_sql_v1': 'bc04fdabbb4dbe793668177c27e46080784113503c4c064cd231aba69df45fd9',
    'workspace_corpus': 'b47c7fc60177d8405d068f405cf44908dc696af73f1b649057ff0720ddddc3a1',
    'causal_process_v1': '99dc46ea4d0d141c5bcc8c5db9a67caf5fbbffebcde874bf5179a164b448195c',
}
TOTAL_BYTES = 256 * 1024 * 1024


class ProbeRefused(RuntimeError):
    """A fixed-category local guard failure; never contains private details."""


def _require(value):
    if not value:
        raise ProbeRefused()


class _Budget:
    def __init__(self, seconds, requests):
        self.deadline, self.max_requests = time.perf_counter() + seconds, requests
        self.requests = self.bytes = 0

    def check(self, reserve=0):
        _require(time.perf_counter() + reserve <= self.deadline)

    def add(self, count):
        self.bytes += count
        _require(self.bytes <= TOTAL_BYTES)


class _WaitLock:
    def __init__(self, lock, name, metrics, budget):
        self.lock, self.name, self.metrics, self.budget = lock, name, metrics, budget

    def acquire(self, *args, **kwargs):
        self.budget.check()
        started = time.perf_counter()
        acquired = self.lock.acquire(*args, **kwargs)
        row = self.metrics.setdefault(self.name, {'calls': 0, 'wait_seconds': 0.0})
        row['calls'] += 1
        row['wait_seconds'] += time.perf_counter() - started
        return acquired

    def release(self):
        return self.lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def _timed(metrics, name, fn, budget):
    def call(*args, **kwargs):
        budget.check()
        started = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            row = metrics.setdefault(name, {'calls': 0, 'seconds': 0.0})
            row['calls'] += 1
            row['seconds'] += time.perf_counter() - started
    return call


def _patch(stack, obj, name, replacement):
    owned, old = name in vars(obj), getattr(obj, name)
    setattr(obj, name, replacement)
    stack.callback(lambda: setattr(obj, name, old) if owned else delattr(obj, name))


def _sealed_queries(hs, store):
    allowed = {hs._schema_query('claim_loop_events'): 'journal_schema',
               hs._schema_query('autonomous_source_chunks'): 'source_schema',
               store._journal_page_query(128, [], '', -1)[0]: 'journal_page',
               hs._proof_query('claim_loop_events', hs._JOURNAL_COLUMNS,
                   'casepath-journal-bytes-v1', 'session_id=?', 'loop_id,sequence'): 'journal_proof'}
    for count in range(1, 129):
        placeholders = ','.join('?' for _ in range(count))
        query = ('SELECT sha256,chunk_index,length(content) AS size_bytes,'
                 "CASE WHEN typeof(content)='blob' AND length(content)<=? THEN content ELSE NULL END AS content "
                 'FROM autonomous_source_chunks WHERE sha256 IN (' + placeholders + ') '
                 'AND (sha256>? OR (sha256=? AND chunk_index>?)) '
                 'ORDER BY sha256,chunk_index LIMIT 8')
        allowed[query] = 'source_page'
        allowed[hs._proof_query('autonomous_source_chunks', hs._SOURCE_COLUMNS,
            'casepath-source-bytes-v1', 'sha256 IN (' + placeholders + ')', 'sha256,chunk_index')] = 'source_proof'
    return allowed


class _Client:
    def __init__(self, client, origin, allowed, budget, sql):
        self.client, self.origin, self.allowed, self.budget, self.sql = client, origin, allowed, budget, sql
        self.records = []

    def _guard(self, args, kwargs):
        _require(args == ('POST', self.origin + '/v2/pipeline'))
        body = kwargs.get('content')
        _require(type(body) is bytes and len(body) <= self.sql.MAX_BYTES)
        payload = json.loads(body)
        _require(set(payload) == {'baton', 'requests'})
        _require(payload['baton'] is None or type(payload['baton']) is str and len(payload['baton']) <= 65536)
        commands = payload['requests']
        _require(type(commands) is list and 1 <= len(commands) <= 131)
        kinds = []
        for command in commands:
            if command == {'type': 'close'}:
                kinds.append('close')
                continue
            _require(set(command) == {'type', 'stmt'} and command['type'] == 'execute')
            stmt = command['stmt']
            _require(set(stmt) == {'sql', 'args', 'want_rows'} and stmt['want_rows'] is True)
            text, parameters = stmt['sql'], stmt['args']
            _require(type(text) is str and ';' not in text and type(parameters) is list)
            unquoted = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", '', text)
            _require(len(parameters) == unquoted.count('?'))
            _require(text in self.allowed or text in ('BEGIN', 'COMMIT', 'ROLLBACK'))
            if text in ('BEGIN', 'COMMIT', 'ROLLBACK'):
                _require(not parameters)
            kinds.append(self.allowed.get(text, text))
        _require(kinds == ['close'] or kinds == ['ROLLBACK'] or
                 len(kinds) == 2 and kinds[0] in set(self.allowed.values()) and kinds[1] == 'close' or
                 len(kinds) >= 4 and kinds[0] == 'BEGIN' and kinds[-2:] == ['COMMIT', 'close']
                 and all(kind in set(self.allowed.values()) for kind in kinds[1:-2]))
        return kinds, len(body)

    @contextmanager
    def stream(self, *args, **kwargs):
        kinds, request_bytes = self._guard(args, kwargs)
        self.budget.check(self.sql.REQUEST_SECONDS)
        _require(self.budget.requests < self.budget.max_requests)
        _require(self.budget.bytes + request_bytes + self.sql.MAX_BYTES <= TOTAL_BYTES)
        self.budget.requests += 1
        self.budget.add(request_bytes)
        started, events = time.perf_counter(), {}
        row = {'index': len(self.records), 'kinds': kinds, 'request_bytes': request_bytes,
               'response_bytes': 0, 'headers_seconds': None, 'body_seconds': None, 'trace': []}
        self.records.append(row)
        extensions = dict(kwargs.get('extensions') or {})
        previous_trace = extensions.get('trace')

        def trace(event, info):
            # Deliberately ignore info: it can contain addresses, SSL objects or exceptions.
            prefix, stage = event.rsplit('.', 1)
            label = prefix.rsplit('.', 1)[-1]
            if label in {'connect_tcp', 'start_tls', 'receive_response_headers', 'receive_response_body'}:
                if stage == 'started':
                    events[prefix] = time.perf_counter()
                elif stage in {'complete', 'failed'} and prefix in events:
                    _require(len(row['trace']) < 128)
                    row['trace'].append({'event': label, 'ok': stage == 'complete',
                                         'seconds': time.perf_counter() - events.pop(prefix)})
            if previous_trace is not None:
                previous_trace(event, info)

        extensions['trace'] = trace
        kwargs['extensions'] = extensions
        try:
            with self.client.stream(*args, **kwargs) as response:
                row['headers_seconds'] = time.perf_counter() - started
                row['http_status'] = response.status_code
                observer = self

                class Response:
                    def __getattr__(self, name):
                        return getattr(response, name)

                    def iter_bytes(self):
                        body_started = time.perf_counter()
                        try:
                            for chunk in response.iter_bytes():
                                observer.budget.check()
                                observer.budget.add(len(chunk))
                                row['response_bytes'] += len(chunk)
                                _require(row['response_bytes'] <= observer.sql.MAX_BYTES)
                                yield chunk
                        finally:
                            row['body_seconds'] = time.perf_counter() - body_started
                yield Response()
        except BaseException as error:
            row['error_category'] = type(error).__name__
            raise
        finally:
            row['total_seconds'] = time.perf_counter() - started
            row['connect_tcp_observed'] = any(item['event'] == 'connect_tcp' for item in row['trace'])


class _Connection:
    def __init__(self, connection, metrics, budget):
        self.connection = connection
        self.read_snapshot = _timed(metrics, 'read_snapshot', connection.read_snapshot, budget)
        self.execute_read_once = _timed(metrics, 'execute_read_once', connection.execute_read_once, budget)

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)


def _run_probe(database, existing_directory, *, expected_origin, idle_seconds,
               max_requests, max_seconds):
    """Four fixed phases; return redacted receipts and stop at the first failure.

    The caller must keep the supplied database private/quiescent throughout.
    The probe swaps only that object's client and its newly created local objects.
    No absent connect trace proves reuse; connect_tcp includes DNS. Inclusive
    method timings overlap. Residual arithmetic excludes inclusive read-method
    durations (including protocol/JSON CPU) and measured lock acquisition time.
    """
    _require(type(max_requests) is int and 1 <= max_requests <= 160)
    _require(type(max_seconds) in (int, float) and 45 <= max_seconds <= 300)
    _require(type(idle_seconds) in (int, float) and 30 < idle_seconds <= 60 and idle_seconds < max_seconds)
    budget, metrics, locks = _Budget(max_seconds, max_requests), {}, {}
    root = Path(existing_directory)
    _require(not root.is_symlink() and root.is_dir() and not any(root.iterdir()))
    parsed = urlsplit(expected_origin)
    _require(parsed.scheme == 'https' and parsed.hostname and parsed.port in (None, 443)
             and parsed.username is None and parsed.password is None and not parsed.path
             and not parsed.query and not parsed.fragment and expected_origin == 'https://' + parsed.hostname)
    from casepath_api import autonomous_knowledge_v1 as ak, autonomous_store_v1 as ast
    from casepath_api import hosted_storage_v1 as hs, hosted_sql_v1 as sql, workspace_corpus as wc, causal_process_v1 as cp
    from fastapi.encoders import jsonable_encoder
    from starlette.responses import JSONResponse
    repo = Path(hs.__file__).resolve().parents[2]
    budget.check()
    identity = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True,
                              check=True, timeout=10).stdout.decode().strip()
    _require(identity == COMMIT)
    _require(subprocess.run(['git', '-C', str(repo), 'diff', '--quiet', '--no-ext-diff', '--no-textconv',
                            'HEAD', '--'], capture_output=True, timeout=10).returncode == 0)
    hashes = {}
    for module in (ak, ast, hs, sql, wc, cp):
        path = Path(module.__file__).resolve()
        _require(path.parent == repo / 'casepath-api' / 'casepath_api')
        hashes[module.__name__.rsplit('.', 1)[-1]] = sha256(path.read_bytes()).hexdigest()
    _require(hashes == HASHES and type(database) is sql.TursoDatabase)
    client = database._shared_client
    _require(client is not None and not database._closed and database._url == expected_origin)
    _require(database._client_factory is None)  # Preserve the product transport's retries=0.
    _require(client.follow_redirects is False and client.is_closed is False)
    _require(sql.REQUEST_SECONDS == 12 and sql.MAX_BYTES == 32 * 1024 * 1024)
    report = {'contract': 'casepath.native-knowledge-phase-probe/1', 'source_commit': identity,
              'source_sha256': hashes, 'dependencies': {name: version(name) for name in
                  ('httpx', 'httpcore', 'fastapi', 'starlette', 'pydantic')}, 'python': platform.python_version(),
              'schema_initialization': False, 'remote_writes_allowed': False, 'phases': [],
              'limits': {'requests': max_requests, 'seconds': max_seconds, 'total_wire_bytes': TOTAL_BYTES},
              'notes': ['native validator probe; no complete ASGI request', 'method timings are inclusive and overlap',
                        'probe-owned locks measure local acquisition overhead, not hosted contention or request dispatch',
                        'residual subtracts inclusive read methods and lock acquisition, not pure network or CPU time',
                        'wire byte counts cover request/response payload bodies, excluding HTTP and TLS framing',
                        'connect_tcp includes DNS; absent connect events do not guarantee socket reuse',
                        'overall bound is cooperative; sends reserve the SDK request deadline']}
    observer = _Client(client, expected_origin, {}, budget, sql)
    original_connect = database.connect
    connect = lambda: _Connection(original_connect(), metrics, budget)
    journal = SimpleNamespace(path=root / 'remote-read-only-placeholder', connect=connect)
    store = hs.HostedAutonomousStore.__new__(hs.HostedAutonomousStore)
    store._read_only, store.storage, store.path, store.journal, store.source_root = True, None, journal.path, journal, root
    store._source_store, store._extractions = hs.HostedSources(connect), {}
    store._extraction_lock, store._summary_lock = RLock(), RLock()
    knowledge = ak.AutonomousKnowledge(store, wc.PublicCorpus(wc.default_workspace_corpus_root()).static_policy())
    observer.allowed = _sealed_queries(hs, store)
    with ExitStack() as stack:
        _patch(stack, database, '_shared_client', observer)
        for obj, attr, name in ((knowledge, '_projection_lock', 'projection'), (store, '_summary_lock', 'summary'),
                                (store, '_extraction_lock', 'extraction'), (store._source_store, '_lock', 'source')):
            _patch(stack, obj, attr, _WaitLock(getattr(obj, attr), name, locks, budget))
        for obj, attr in ((store, '_validated_states'), (store, '_replay'), (store, '_validate_descriptor'),
                          (store, '_extract'), (store, '_after_validated_knowledge_states'),
                          (store._source_store, '_knowledge_source_queries'), (knowledge, '_project')):
            _patch(stack, obj, attr, _timed(metrics, attr, getattr(obj, attr), budget))
        for name in ('cold_population', 'first_warm', 'idle_warm', 'immediate_repeat'):
            metrics.clear()
            locks.clear()
            phase = {'name': name, 'ok': False}
            report['phases'].append(phase)
            first, started = len(observer.records), time.perf_counter()
            try:
                if name == 'idle_warm':
                    idle_started = time.perf_counter()
                    while time.perf_counter() - idle_started < idle_seconds:
                        budget.check(sql.REQUEST_SECONDS)
                        time.sleep(max(0, min(0.25, idle_seconds - (time.perf_counter() - idle_started))))
                    phase['idle_seconds'] = time.perf_counter() - idle_started
                start = time.perf_counter()
                value = knowledge.learning_view()
                phase['knowledge_seconds'] = time.perf_counter() - start
                start = time.perf_counter()
                encoded = jsonable_encoder(value)
                phase['jsonable_encoder_seconds'] = time.perf_counter() - start
                start = time.perf_counter()
                raw = JSONResponse(encoded).body
                phase['jsonresponse_render_seconds'] = time.perf_counter() - start
                budget.check()
                phase.update(ok=True, response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw),
                             versions=len(value['versions']), uses=len(value['uses']), quarantined=len(value['quarantined']),
                             journal_heads=len(value.get('learning_replay', {}).get('journal_heads', [])))
            except Exception as error:
                phase['error_category'] = type(error).__name__
            phase.update(total_seconds=time.perf_counter() - started, methods=dict(metrics), locks=dict(locks),
                         http_indices=list(range(first, len(observer.records))))
            if 'knowledge_seconds' in phase:
                transport = sum(metrics.get(key, {}).get('seconds', 0) for key in ('read_snapshot', 'execute_read_once'))
                phase['outside_read_methods_and_lock_acquisition_seconds'] = (
                    phase['knowledge_seconds'] - transport - sum(row['wait_seconds'] for row in locks.values()))
            if not phase['ok']:
                break
    response_hashes = [row['response_sha256'] for row in report['phases'] if row['ok']]
    report.update(http=observer.records, total_wire_bytes=budget.bytes, total_requests=budget.requests,
                  responses_identical=len(set(response_hashes)) == 1 if len(response_hashes) > 1 else None,
                  all_ok=len(report['phases']) == 4 and all(row['ok'] for row in report['phases']))
    return report


def run_probe(database, existing_directory, *, expected_origin, idle_seconds=35,
              max_requests=160, max_seconds=300):
    """Return a redacted dict; setup/guard failures never export exception text.

    See _run_probe for isolation, timing and cooperative-deadline limitations.
    Run only with a private caller-created client; this function owns no secrets.
    """
    try:
        return _run_probe(database, existing_directory, expected_origin=expected_origin,
                          idle_seconds=idle_seconds, max_requests=max_requests, max_seconds=max_seconds)
    except Exception as error:
        return {'contract': 'casepath.native-knowledge-phase-probe/1', 'all_ok': False,
                'setup_or_cleanup_failed': True, 'error_category': type(error).__name__}

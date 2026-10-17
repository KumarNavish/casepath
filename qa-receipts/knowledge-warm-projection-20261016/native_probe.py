"""Read-only native probe; the Mac owner supplies an authenticated database.

Import run_probe(database, existing_directory). This file reads no environment
credentials, initializes no schema, and exports no event/source bytes or SQL
parameters. The supplied database must own a reusable HTTP client.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
import time
from types import SimpleNamespace


class _Response:
    def __init__(self, response, record):
        self.response, self.record = response, record

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_bytes(self, *args, **kwargs):
        try:
            for chunk in self.response.iter_bytes(*args, **kwargs):
                self.record['response_bytes'] += len(chunk)
                yield chunk
        finally:
            self.record['body_end_seconds'] = time.perf_counter() - self.record.pop('_started')


class _Client:
    def __init__(self, client):
        self.client, self.records = client, []

    def __getattr__(self, name):
        return getattr(self.client, name)

    @contextmanager
    def stream(self, *args, **kwargs):
        # Inspect statement kinds/hashes only, never parameters or headers.
        payload = json.loads(kwargs['content'])
        statements = [request['stmt']['sql'] for request in payload['requests']
                      if request['type'] == 'execute']
        kinds = [statement.strip().split(None, 1)[0].upper() for statement in statements]
        if any(kind not in {'SELECT', 'BEGIN', 'COMMIT', 'ROLLBACK'} for kind in kinds):
            raise AssertionError('Native probe refused a non-read statement.')
        if any(request['type'] not in {'execute', 'close'} for request in payload['requests']):
            raise AssertionError('Native probe refused a non-read protocol operation.')
        started = time.perf_counter()
        record = {'index': len(self.records), 'kinds': kinds,
                  'close_requested': payload['requests'][-1]['type'] == 'close',
                  'sql_sha256': [sha256(value.encode()).hexdigest() for value in statements],
                  'raw_journal_page': any('claim_loop_events' in value and 'event_json' in value
                                          and 'crypto_sha256' not in value and 'sqlite_schema' not in value
                                          for value in statements),
                  'request_bytes': len(kwargs['content']), 'response_bytes': 0,
                  'headers_seconds': None, 'body_end_seconds': None,
                  'error_category': None, '_started': started}
        self.records.append(record)
        try:
            with self.client.stream(*args, **kwargs) as response:
                record['headers_seconds'] = time.perf_counter() - started
                record['http_status'] = response.status_code
                yield _Response(response, record)
        except Exception as error:
            record['error_category'] = type(error).__name__
            raise
        finally:
            record.pop('_started', None)
            record['total_seconds'] = time.perf_counter() - started
            if record['body_end_seconds'] is not None:
                record['body_seconds'] = record['body_end_seconds'] - record['headers_seconds']


class _Connection:
    def __init__(self, connection, acknowledgements):
        self.connection = connection
        original = connection._send

        def observed(requests, **kwargs):
            responses = original(requests, **kwargs)
            for request, response in zip(requests, responses):
                if request['type'] != 'execute':
                    continue
                kind = request['stmt']['sql'].strip().split(None, 1)[0].upper()
                if kind in {'BEGIN', 'COMMIT', 'ROLLBACK'}:
                    result = response['result']
                    acknowledgements.append({'kind': kind,
                        'columns': len(result['cols']), 'rows': len(result['rows']),
                        'affected_row_count': result['affected_row_count'],
                        'last_insert_rowid': result.get('last_insert_rowid')})
            return responses

        connection._send = observed

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)


def run_probe(database, existing_directory, *, rounds=2, closed_page_gap_seconds=0):
    """Return redacted cold/warm timings using the actual candidate validators.

    An optional <=6s gap between CLOSED raw journal reads checks that cold
    collection does not depend on an interactive transaction surviving it.
    No expiry/mutation is introduced in the remote database.
    """
    if type(rounds) is not int or not 1 <= rounds <= 3:
        raise ValueError('Probe rounds must be bounded to 1..3.')
    if not 0 <= closed_page_gap_seconds <= 6:
        raise ValueError('Closed-page gap must be bounded to 0..6 seconds.')
    root = Path(existing_directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Supply an existing scoped local probe directory.')
    client = getattr(database, '_shared_client', None)
    if client is None:
        raise ValueError('Supply TursoDatabase(reuse_http=True).')
    from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
    from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedSources
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    from casepath_api import autonomous_knowledge_v1, autonomous_store_v1, hosted_storage_v1, hosted_sql_v1

    observer, acknowledgements = _Client(client), []
    database._shared_client = observer
    original_connect = database.connect
    gap_done = False

    def connect():
        nonlocal gap_done
        if not gap_done and closed_page_gap_seconds and observer.records:
            previous = observer.records[-1]
            if (previous['raw_journal_page'] and previous['body_end_seconds'] is not None
                    and 'total_seconds' in previous):
                time.sleep(closed_page_gap_seconds)
                gap_done = True
        return _Connection(original_connect(), acknowledgements)

    # Do not instantiate HostedJournal, whose constructor initializes schema.
    journal = SimpleNamespace(path=root / 'remote-read-only-placeholder', connect=connect)
    store = HostedAutonomousStore.__new__(HostedAutonomousStore)
    store._read_only, store.storage = True, None
    store.path, store.journal, store.source_root = journal.path, journal, root
    store._source_store = HostedSources(connect)
    store._extractions, store._extraction_lock, store._summary_lock = {}, RLock(), RLock()
    knowledge = AutonomousKnowledge(store, PublicCorpus(default_workspace_corpus_root()).static_policy())
    report = {'contract': 'casepath.native-knowledge-proof-probe/1',
              'source_sha256': {module.__name__: sha256(Path(module.__file__).read_bytes()).hexdigest()
                                for module in (autonomous_knowledge_v1, autonomous_store_v1,
                                               hosted_storage_v1, hosted_sql_v1)},
              'schema_initialization': False, 'remote_writes': False,
              'shared_http_client': True, 'closed_page_gap_seconds': closed_page_gap_seconds,
              'rounds': [], 'http': observer.records, 'acknowledgements': acknowledgements}
    try:
        for index in range(rounds):
            start, first = time.perf_counter(), len(observer.records)
            row = {'index': index, 'kind': 'cold' if index == 0 else 'warm'}
            try:
                value = knowledge.learning_view()
                raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
                row.update(ok=True, projection_sha256=sha256(raw).hexdigest(),
                           projection_bytes=len(raw), versions=len(value['versions']),
                           uses=len(value['uses']), quarantined=len(value['quarantined']))
            except Exception as error:
                row.update(ok=False, error_category=type(error).__name__)
            row.update(seconds=time.perf_counter() - start,
                       http_indices=list(range(first, len(observer.records))),
                       response_bytes=sum(item['response_bytes'] for item in observer.records[first:]))
            report['rounds'].append(row)
            if not row['ok']:
                break  # No automatic retry of a failed cold/warm validation.
        report['closed_page_gap_exercised'] = gap_done
        report['raw_pages_closed'] = all(item['close_requested'] for item in observer.records
                                         if item['raw_journal_page'])
        report['all_ok'] = (len(report['rounds']) == rounds and all(row['ok'] for row in report['rounds'])
                            and report['raw_pages_closed']
                            and (not closed_page_gap_seconds or gap_done))
        return report
    finally:
        database._shared_client = client

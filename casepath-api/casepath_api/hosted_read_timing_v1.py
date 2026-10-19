"""Request-local, numeric read diagnostics; never retain SQL or source content."""
from contextlib import contextmanager
from contextvars import ContextVar
from math import isfinite
from time import monotonic

CURRENT_READ = ContextVar('casepath_read_timings', default=None)
CURRENT_SHAPE = ContextVar('casepath_read_shape', default=0)
# Shape codes: 0 other; 1 combined final proof; 2 journal proof;
# 3 raw journal page; 4 source proof. No query or parameter text is retained.
MAX_PRIMARY_DIAGNOSTICS, MAX_STATEMENT_DIAGNOSTICS = 8, 64


@contextmanager
def primary_shape(code):
    token = CURRENT_SHAPE.set(code if type(code) is int and 0 <= code <= 4 else 0)
    try:
        yield
    finally:
        CURRENT_SHAPE.reset(token)


def record_primary_statements(entries):
    values = CURRENT_READ.get()
    if values is None or values['primary_count'] > MAX_PRIMARY_DIAGNOSTICS:
        return
    record = values['primary_requests'][-1]
    statements = [entry['response'].get('result') for entry in entries
                  if entry['response'].get('type') == 'execute']
    record['statement_count'] = len(statements)
    for index, result in enumerate(statements):
        if values.get('statement_count', 0) >= MAX_STATEMENT_DIAGNOSTICS:
            values['statements_omitted'] = values.get('statements_omitted', 0) + 1
            continue
        values['statement_count'] = values.get('statement_count', 0) + 1
        if not isinstance(result, dict):
            continue  # Core result validation still runs in the transport.
        duration, rows = result.get('query_duration_ms'), result.get('rows_read')
        duration = duration if type(duration) in (int, float) and 0 <= duration <= 999999999.999 and isfinite(duration) else None
        rows = rows if type(rows) is int and 0 <= rows <= 2**63 - 1 else None
        if duration is not None or rows is not None:
            record['statements'].append((index, duration, rows))


def statement_timing_fields(values):
    fields = []
    for number, record in enumerate(values.get('primary_requests', ()), 1):
        prefix = f'casepath_p{number}'
        fields.append(f'{prefix}_shape;desc="{record["shape"]}"')
        fields.append(f'{prefix}_statements;desc="{record.get("statement_count", 0)}"')
        for index, duration, rows in record['statements']:
            # Statement ordinals include BEGIN and COMMIT; desc is rows_read.
            field = f'{prefix}_s{index}'
            if duration is not None:
                field += f';dur={duration:.3f}'
            if rows is not None:
                field += f';desc="{rows}"'
            fields.append(field)
    if values.get('statements_omitted'):
        fields.append(f'casepath_statements_omitted;desc="{values["statements_omitted"]}"')
    return fields


@contextmanager
def measured(name):
    values = CURRENT_READ.get()
    if values is None:
        yield
        return
    started = monotonic()
    try:
        yield
    finally:
        values[name] = values.get(name, 0.0) + max(0.0, monotonic() - started)


@contextmanager
def read_lock(lock):
    with measured('lock'):
        lock.acquire()
    try:
        yield
    finally:
        lock.release()


@contextmanager
def primary_request():
    values = CURRENT_READ.get()
    if values is None:
        yield {}
        return
    values['primary_count'] = values.get('primary_count', 0) + 1
    if values['primary_count'] <= MAX_PRIMARY_DIAGNOSTICS:
        values.setdefault('primary_requests', []).append({'shape': CURRENT_SHAPE.get(), 'statements': []})
    started = {}

    def trace(event, info):
        # Ignore trace info: it can contain network addresses or request bytes.
        for prefix, name in (('connection.connect_tcp.', 'connect'), ('connection.start_tls.', 'tls'),
                             ('http11.receive_response_headers.', 'headers'), ('http11.receive_response_body.', 'body')):
            if event == prefix + 'started':
                started[name] = monotonic()
            elif event in (prefix + 'complete', prefix + 'failed') and name in started:
                values[name] = values.get(name, 0.0) + max(0.0, monotonic() - started.pop(name))

    with measured('primary'):
        yield {'extensions': {'trace': trace}}

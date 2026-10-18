"""Request-local, numeric read diagnostics; never retain SQL or source content."""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

CURRENT_READ = ContextVar('casepath_read_timings', default=None)


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

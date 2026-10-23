"""Bounded retries and last-verified projections for the public read service.

Retry the complete endpoint, never one statement in a partly consumed snapshot.
No streaming response or mutable/private composition uses this wrapper.
"""
from collections import OrderedDict
from functools import wraps
from inspect import signature
import json
import logging
import random
from threading import RLock
import time

from fastapi.encoders import jsonable_encoder
from fastapi.params import Param
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from .hosted_proxy_v1 import ReadTimedJSONResponse
from .hosted_sql_v1 import HostedReadDeadline, HostedReadTransient, READ_ONLY_DEADLINE


READ_SECONDS = 10.0  # Sites aborts the upstream request at 14 seconds.
MAX_ATTEMPTS = 3
# Three total attempts allow two inter-attempt waits, not three retries.
# The requested 900 ms ceiling is retained; it never adds a fourth attempt.
BACKOFF_SECONDS = (0.1, 0.3, 0.9)
MAX_ENTRIES, MAX_CACHE_BYTES, MAX_ENTRY_BYTES = 64, 16 * 1024 * 1024, 8 * 1024 * 1024
MAX_KEY_BYTES = 4096
PATHS = frozenset('/api/claim-loops/v1/autonomous/' + suffix for suffix in (
    'claims', 'knowledge', 'claims/{claim_id}', 'claims/{claim_id}/snapshot',
    'claims/{claim_id}/events', 'claims/{claim_id}/replay'))
_LOG = logging.getLogger(__name__)


class HostedReadReliability:
    def __init__(self, source_commit, *, ready):
        self.source_commit, self.ready = source_commit, ready
        self._cache, self._bytes, self._lock = OrderedDict(), 0, RLock()

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._bytes = 0

    def _forget(self, key):
        with self._lock:
            old = self._cache.pop(key, None)
            if old is not None:
                self._bytes -= len(old)

    def _remember(self, key, body):
        with self._lock:
            self._forget(key)
            if len(body) > MAX_ENTRY_BYTES or len(key[2]) > MAX_KEY_BYTES:
                return
            self._cache[key] = body
            self._bytes += len(body)
            while len(self._cache) > MAX_ENTRIES or self._bytes > MAX_CACHE_BYTES:
                _, removed = self._cache.popitem(last=False)
                self._bytes -= len(removed)

    def protect(self, endpoint, path):
        parameters = signature(endpoint)

        @wraps(endpoint)
        def read(*args, **kwargs):
            arguments = parameters.bind(*args, **kwargs)
            arguments.apply_defaults()
            values = {name: value.default if isinstance(value, Param) else value
                      for name, value in arguments.arguments.items()}
            # Keys retain every validated query/cursor and path identity. The
            # cache belongs to this app/source; it never survives a release.
            key = (self.source_commit, path, json.dumps(values, ensure_ascii=True,
                                                       allow_nan=False, sort_keys=True, separators=(',', ':')))
            deadline = time.monotonic() + READ_SECONDS
            failure = None
            for attempt in range(MAX_ATTEMPTS):
                if time.monotonic() >= deadline:
                    failure = HostedReadDeadline('The saved read deadline was exhausted.')
                    break
                token = READ_ONLY_DEADLINE.set(deadline)
                try:
                    response = ReadTimedJSONResponse(jsonable_encoder(endpoint(*args, **kwargs)))
                    if time.monotonic() >= deadline:
                        raise HostedReadDeadline('The saved read deadline was exhausted.')
                except HostedReadTransient as error:
                    failure = error
                    _LOG.warning('hosted_read_retry endpoint=%s attempt=%d category=%s',
                                 path, attempt + 1, type(error).__name__)
                except HTTPException as error:
                    # A missing claim says nothing about
                    # other validated projections. Forget only this exact key.
                    if error.status_code == 404:
                        self._forget(key)
                    else:
                        self.clear()
                    raise
                except BaseException:
                    # Integrity/protocol/validation errors cannot be hidden by
                    # a previously valid body, now or on a later failed read.
                    self.clear()
                    raise
                else:
                    self._remember(key, response.body)
                    response.headers['X-CasePath-Read-Source'] = 'primary'
                    response.headers['Cache-Control'] = 'no-store'
                    return response
                finally:
                    READ_ONLY_DEADLINE.reset(token)
                if isinstance(failure, HostedReadDeadline) or attempt + 1 == MAX_ATTEMPTS:
                    break
                delay = random.uniform(0.5, 1.5) * BACKOFF_SECONDS[attempt]
                if time.monotonic() + delay >= deadline:
                    break
                time.sleep(delay)
            # Only exhausted classified transient failures may use a fully
            # encoded successful projection. Never admit readiness from cache.
            with self._lock:
                body = self._cache.get(key) if self.ready() else None
                if body is not None:
                    self._cache.move_to_end(key)
            if body is not None:
                _LOG.warning('hosted_read_cached_projection endpoint=%s', path)
                return Response(body, media_type='application/json', headers={
                    'X-CasePath-Read-Source': 'last-verified', 'Cache-Control': 'no-store'})
            raise failure or HostedReadDeadline('The saved read deadline was exhausted.')

        return read

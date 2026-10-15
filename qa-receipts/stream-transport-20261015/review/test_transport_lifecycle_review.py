"""Independent bounded transport lifecycle review; no product source writes."""
import asyncio
from threading import Event
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from casepath_api import autonomous_operations_v1 as runtime
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_reference_policy_v1 import REFERENCE_POLICY_ID
from casepath_api.autonomous_reference_v1 import ReferenceProfile


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
@pytest.mark.parametrize('stop', ['close', 'disconnect', 'task_cancel'])
def test_iterator_close_or_disconnect_cancels_before_next_yield(monkeypatch, encoding, stop):
    disconnected, stopped = Event(), Event()
    captured = {}

    def recompute(_, *, send, cancellation, **kwargs):
        captured['cancellation'] = cancellation
        try:
            send({'type': 'binding'})
            if stop == 'task_cancel':
                assert cancellation.wait(1)
            else:
                for i in range(100):
                    send({'type': 'operation', 'id': i, 'text': 'x' * 400000})
        finally:
            stopped.set()

    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits(concurrency=1, total=100))
    monkeypatch.setattr(runtime, 'capture_operation_inputs', lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    service = SimpleNamespace(policy={'policy_id': REFERENCE_POLICY_ID}, store=SimpleNamespace())
    router = create_autonomous_router(lambda: service, read_only=True)
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/operations'))
    cid = ReferenceProfile().ids[0]

    async def exercise():
        async def receive():
            if disconnected.is_set():
                return {'type': 'http.disconnect'}
            await asyncio.Future()

        request = Request({'type': 'http', 'method': 'GET', 'path': '/',
                           'headers': [(b'accept-encoding', encoding.encode())]}, receive)
        response = await endpoint(cid, request, mode='live')
        iterator = response.body_iterator
        try:
            first = await anext(iterator)
            assert first
            if stop == 'close':
                await iterator.aclose()
            elif stop == 'task_cancel':
                task = asyncio.create_task(anext(iterator))
                await asyncio.sleep(0.01)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                disconnected.set()
                try:
                    await anext(iterator)
                except StopAsyncIteration:
                    pass
            # In gzip mode the next yield can be a footer: cancellation must
            # already be set so a blocked footer send cannot retain the worker.
            assert captured['cancellation'].is_set()
        finally:
            await iterator.aclose()
        assert await asyncio.to_thread(stopped.wait, 1)
        for _ in range(100):
            if runtime.PUBLIC_LIMITS.active == 0:
                break
            await asyncio.sleep(0.001)
        assert runtime.PUBLIC_LIMITS.active == 0

    asyncio.run(exercise())


@pytest.mark.parametrize('encoding', ['identity', 'gzip'])
def test_nonfitting_lookahead_stays_within_waiting_byte_budget(monkeypatch, encoding):
    first_large_queued, second_large_queued, stopped = Event(), Event(), Event()

    def recompute(_, *, send, **kwargs):
        try:
            send({'type': 'binding'})
            send({'type': 'operation', 'text': 'x' * 100})
            send({'type': 'checkpoint', 'text': 'a' * 1300000})
            first_large_queued.set()
            send({'type': 'checkpoint', 'text': 'b' * 1300000})
            second_large_queued.set()
        finally:
            stopped.set()

    monkeypatch.setattr(runtime, 'PUBLIC_LIMITS', runtime.PublicOperationLimits(concurrency=1, total=100))
    monkeypatch.setattr(runtime, 'capture_operation_inputs', lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, 'recompute_operations', recompute)
    service = SimpleNamespace(policy={'policy_id': REFERENCE_POLICY_ID}, store=SimpleNamespace())
    router = create_autonomous_router(lambda: service, read_only=True)
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/operations'))

    async def exercise():
        async def receive():
            await asyncio.Future()

        request = Request({'type': 'http', 'method': 'GET', 'path': '/',
                           'headers': [(b'accept-encoding', encoding.encode())]}, receive)
        response = await endpoint(ReferenceProfile().ids[0], request, mode='live')
        iterator = response.body_iterator
        try:
            assert await anext(iterator)
            assert await asyncio.to_thread(first_large_queued.wait, 1)
            # A small batch is in flight, and the first checkpoint is the
            # non-fitting lookahead. A second 1.3MB checkpoint must still block.
            assert await anext(iterator)
            await asyncio.sleep(0.03)
            assert not second_large_queued.is_set()
        finally:
            await iterator.aclose()
        assert await asyncio.to_thread(stopped.wait, 1)

    asyncio.run(exercise())

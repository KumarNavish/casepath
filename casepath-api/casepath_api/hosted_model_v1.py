"""Refresh public model metadata without enlarging the persisted allowance."""
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
import json
import time

import httpx

from .agent_work.openrouter import CATALOGUE, OpenRouterConfig, OpenRouterFactsWorker, choose_model
from .autonomous_model_v1 import AutonomousModelV1, AutonomousModelError
from .autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA


class HostedModel:
    def __init__(self, store, model, api_key, *, catalogue_client=None):
        self.store, self._model_id, self._key = store, model, api_key
        self._model, self._lock, self._catalogue_client = None, RLock(), catalogue_client
        self._refresh()

    def __repr__(self):
        return f'HostedModel(model={self._model_id!r}, credential=<redacted>)'

    def _refresh(self):
        with self._lock:
            if self._model is not None and (datetime.now(timezone.utc) - self._model._catalogue_fetched_at).total_seconds() < 43200:
                return self._model
            client = self._catalogue_client or httpx.Client(timeout=10, trust_env=False, follow_redirects=False)
            try:
                deadline = time.monotonic() + 15
                with client.stream('GET', CATALOGUE) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 8_000_000 or time.monotonic() > deadline:
                            raise ValueError('model catalogue exceeds its bound')
                packet = json.loads(payload)
                selected = choose_model(packet, model=self._model_id)
                entries = [row for row in packet['data'] if row.get('id') == self._model_id]
                if len(entries) != 1:
                    raise ValueError('model catalogue identity is not unique')
                config = OpenRouterConfig(model=selected['model'], canonical_model=selected.get('canonical_model'),
                    prompt_price=Decimal(selected['prompt_price']), completion_price=Decimal(selected['completion_price']),
                    request_price=Decimal(selected['request_price']), catalogue_entry_sha256=selected['catalogue_entry_sha256'],
                    context_length=selected['context_length'], reasoning_supported=selected['reasoning_supported'],
                    total_cost_limit=Decimal('0.02'))
                self._model = AutonomousModelV1(self.store, worker=OpenRouterFactsWorker(config, self._key),
                    schemas={'interpret': INTERPRET_SCHEMA, 'verify': VERIFY_SCHEMA}, catalogue_entry=entries[0])
                return self._model
            except Exception:
                raise AutonomousModelError('Current model capabilities and prices could not be verified. No model request was sent.') from None
            finally:
                if self._catalogue_client is None:
                    client.close()

    @property
    def config(self):
        return self._model.config

    def interpret(self, context, identity):
        return self._refresh().interpret(context, identity)

    def verify(self, context, proposal, identity):
        return self._refresh().verify(context, proposal, identity)

    def abandon(self, workflow_id, reason):
        return self.store.close_autonomous_workflow(workflow_id, reason)

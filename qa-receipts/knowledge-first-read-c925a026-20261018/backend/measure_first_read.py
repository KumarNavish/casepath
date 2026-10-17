"""Local-only first-served-read timing; unchanged c925 product, no real sockets."""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace

REPO = Path('/workspace/casepath-release-ae0-shard6')
OUT = Path('/workspace/knowledge-first-read-20261018/e')
sys.path[:0] = [str(REPO / 'casepath-api'), str(REPO / 'casepath-api/tests')]
import httpx
from fastapi import FastAPI
import fastapi.routing
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
import casepath_api.autonomous_knowledge_v1 as knowledge_module
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from test_autonomous_knowledge_reads_v1 import hosted_copy

def forbidden(*args, **kwargs):
    raise AssertionError('Real network is forbidden in this local-only profile')
httpx.HTTPTransport.handle_request = forbidden
original = Path('/workspace/atomic-proof-20261017/writer/t/reads/knowledge-processed-roster0/claims.sqlite3')
policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
native = AutonomousStore.open_read_only(original)
expected = AutonomousKnowledge(native, policy).learning_view()
fixture = OUT / 'native-fixture'
fixture.mkdir()
server, store, _, _ = hosted_copy((original, native.source_root, policy, None), fixture)
knowledge = AutonomousKnowledge(store, policy)
stats = {}

def timed(owner, name, label=None):
    original = getattr(owner, name)
    label = label or name
    def wrapped(*args, **kwargs):
        start = perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            value = stats.setdefault(label, {'calls': 0, 'seconds': 0})
            value['calls'] += 1
            value['seconds'] += perf_counter() - start
    setattr(owner, name, wrapped)

for owner, name in ((knowledge, '_project'), (knowledge, 'learning_view'),
                    (knowledge_module, '_learning_replay'), (store, '_replay'),
                    (store, 'knowledge_snapshot'), (store, '_validated_states'),
                    (store._source_store, 'prefetch_journal_sources'),
                    (JSONResponse, 'render')):
    timed(owner, name)
serialize = fastapi.routing.serialize_response
async def serialize_timed(*args, **kwargs):
    start = perf_counter()
    try:
        return await serialize(*args, **kwargs)
    finally:
        value = stats.setdefault('fastapi_serialize_response', {'calls': 0, 'seconds': 0})
        value['calls'] += 1
        value['seconds'] += perf_counter() - start
fastapi.routing.serialize_response = serialize_timed

app = FastAPI()
app.include_router(create_autonomous_router(lambda: SimpleNamespace(knowledge=knowledge), read_only=True))
app.add_event_handler('startup', knowledge.learning_view)
measurements = []
def capture(phase, before, started, **extra):
    measurements.append({'phase': phase, 'wall_seconds': perf_counter() - started,
        'calls': {key: {'calls': value['calls'] - before.get(key, {}).get('calls', 0),
                        'seconds': value['seconds'] - before.get(key, {}).get('seconds', 0)}
                  for key, value in stats.items()},
        'http_requests': len(server.requests), 'proof_response_bytes': sum(server.response_bytes),
        'raw_journal_pages': len(server.journal_pages), **extra})
try:
    start = perf_counter()
    with TestClient(app) as client:
        capture('startup', {}, start)
        for phase in ('first_poststartup', 'repeat_1', 'repeat_2'):
            server.reset_counts()
            before = {key: dict(value) for key, value in stats.items()}
            start = perf_counter()
            response = client.get('/api/claim-loops/v1/autonomous/knowledge')
            capture(phase, before, start, status=response.status_code, response_bytes=len(response.content),
                    response_sha256=hashlib.sha256(response.content).hexdigest())
            assert response.status_code == 200 and response.json() == expected
            assert len(server.requests) == 1 and not server.journal_pages
            assert stats['_project']['calls'] == stats['_learning_replay']['calls'] == 1
        public_path = Path('/workspace/knowledge-learning-coordinator-20261016/projection-6064.json')
        public = json.loads(public_path.read_bytes())
        public_app = FastAPI()
        public_app.include_router(create_autonomous_router(lambda: SimpleNamespace(
            knowledge=SimpleNamespace(learning_view=lambda: public)), read_only=True))
        public_measurements = []
        with TestClient(public_app) as public_client:
            for phase in ('public_first_encode', 'public_repeat_1', 'public_repeat_2'):
                before = {key: dict(value) for key, value in stats.items()}
                start = perf_counter()
                response = public_client.get('/api/claim-loops/v1/autonomous/knowledge')
                elapsed = perf_counter() - start
                assert response.status_code == 200 and response.json() == public
                public_measurements.append({'phase': phase, 'wall_seconds': elapsed,
                    'fastapi_encoding_seconds': stats['fastapi_serialize_response']['seconds'] - before['fastapi_serialize_response']['seconds'],
                    'json_render_seconds': stats['render']['seconds'] - before['render']['seconds'],
                    'response_bytes': len(response.content), 'response_sha256': hashlib.sha256(response.content).hexdigest()})
    result = {'candidate': 'c925a0267971edb52fea5f2bd9653a2495b7ac15',
        'qualification': 'Local CPU/ASGI timing only, mock Hrana; excludes real network/proxy/host wake and is not hosted acceptance.',
        'fixture_claims': len(expected['learning_replay']['journal_heads']), 'measurements': measurements,
        'public_export': {'path': str(public_path), 'sha256': hashlib.sha256(public_path.read_bytes()).hexdigest(),
                          'qualification': 'Existing filtered public synthetic projection; serialization-only, no admission authority.',
                          'measurements': public_measurements},
        'python': sys.version, 'source_sha256': {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
            for name in ('casepath-api/casepath_api/hosted_app_v1.py', 'casepath-api/casepath_api/hosted_storage_v1.py',
                         'casepath-api/casepath_api/autonomous_knowledge_v1.py', 'casepath-api/casepath_api/autonomous_api_v1.py')}}
    (OUT / 'measurements.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
finally:
    server.close()

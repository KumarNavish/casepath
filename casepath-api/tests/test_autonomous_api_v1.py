from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


def test_intake_api_headers_idempotency_saved_events_and_source_readback(tmp_path):
    store = AutonomousStore(tmp_path / 'claims.sqlite3')
    service = AutonomousController(store, PublicCorpus(default_workspace_corpus_root()).static_policy())
    service.submit = lambda claim: None
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service))
    prefix = '/api/claim-loops/v1/autonomous'
    packet = {'title': 'Incoming claim', 'message': 'A new termination notice arrived.', 'files': [], 'idempotency_key': 'intake-api-1'}
    with TestClient(app) as client:
        assert client.post(prefix + '/claims', json=packet).status_code == 403
        headers = {'X-CasePath-Agent-Work': '1'}
        assert client.post(prefix + '/claims', json=packet, headers={**headers, 'Origin': 'https://external.test'}).status_code == 403
        result = client.post(prefix + '/claims', json=packet, headers=headers)
        assert result.status_code == 202, result.text
        state = result.json()
        same = client.post(prefix + '/claims', json=packet, headers=headers).json()
        assert same == state
        assert client.post(prefix + '/claims', json={**packet, 'message': 'Different content.'}, headers=headers).status_code == 409
        claim_id = state['claim_id']
        events = client.get(f'{prefix}/claims/{claim_id}/events').json()
        assert events['events'][0]['state_sha256'] == state['state_sha256']
        artifact = state['acquired_sources'][0]
        path = f"{prefix}/sources/{claim_id}/{artifact['artifact_id']}"
        assert client.get(path).content == packet['message'].encode()
        assert client.get(path + '/text').json()['receipt_sha256'] == artifact['receipt_sha256']
        assert client.get(path.replace(claim_id, 'auto_missing')).status_code == 409
        command = {'idempotency_key': 'pause-api-1', 'expected_revision': state['revision'], 'expected_state_sha256': state['state_sha256']}
        paused = client.post(f'{prefix}/claims/{claim_id}/pause', json=command, headers=headers)
        assert paused.status_code == 200, paused.text
        assert paused.json()['deferral']['code'] == 'paused'
        assert service.run(claim_id)['state_sha256'] == paused.json()['state_sha256']
        stale = {**command, 'idempotency_key': 'resume-api-stale'}
        assert client.post(f'{prefix}/claims/{claim_id}/resume', json=stale, headers=headers).status_code == 409
        command = {'idempotency_key': 'resume-api-1', 'expected_revision': paused.json()['revision'],
                   'expected_state_sha256': paused.json()['state_sha256']}
        resumed = client.post(f'{prefix}/claims/{claim_id}/resume', json=command, headers=headers)
        assert resumed.status_code == 202, resumed.text
        assert resumed.json()['status'] == 'running' and resumed.json()['deferral'] is None
        assert client.post(f'{prefix}/claims/{claim_id}/resume', json=command, headers=headers).json() == resumed.json()
    service.shutdown()

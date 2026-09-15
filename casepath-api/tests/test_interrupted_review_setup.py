"""An uncreated evidence review is recoverable; a damaged journal is not absence."""
from pathlib import Path
import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.workspace_claim_loop_v1 import WORKSPACE_CLAIM_LOOP_SESSION_ID
from test_workspace_claim_loop_v1 import _system, _started_claim, _ensure


def client_for(root):
    storage, workspace, normal, facade = _system(root)
    claim_id, started = _started_claim(workspace)
    app = FastAPI()
    app.include_router(create_claim_loop_router(lambda:storage, service_getter=lambda:normal,
                       workspace_service_getter=lambda:workspace, workspace_loop_service_getter=lambda:facade))
    return storage, workspace, facade, claim_id, started, TestClient(app)


def test_review_setup_can_be_resumed_before_the_evidence_loop_exists(tmp_path):
    storage, workspace, facade, claim_id, started, client = client_for(tmp_path)
    before = workspace.detail(claim_id)
    response = client.get('/api/claim-loops/v1/workspace/claims/'+claim_id+'/loop')
    assert response.status_code == 404
    assert workspace.detail(claim_id)['state']['state_sha256'] == before['state']['state_sha256']
    created = _ensure(facade, claim_id, started)
    assert created['loop_state']['observations'] == []
    assert client.get('/api/claim-loops/v1/workspace/claims/'+claim_id+'/loop').status_code == 200


def test_a_checkpoint_without_its_events_is_not_treated_as_a_new_claim(tmp_path):
    storage, workspace, facade, claim_id, started, client = client_for(tmp_path)
    created = _ensure(facade, claim_id, started)
    loop_id = created['loop_state']['loop_id']
    # Disposable regression database only: retain the checkpoint and remove its journal.
    with sqlite3.connect(tmp_path/'casepath.db') as db:
        db.execute('DELETE FROM claim_loop_events WHERE session_id=? AND loop_id=?',
                   (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id))
    response = client.get('/api/claim-loops/v1/workspace/claims/'+claim_id+'/loop')
    assert response.status_code == 409
    assert 'historical revision' in response.json()['detail']

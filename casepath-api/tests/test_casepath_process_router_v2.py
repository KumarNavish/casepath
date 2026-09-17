from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.casepath_process_router_v2 import create_process_router_v2


def app_and_calls():
    calls = []
    def plan(case, held):
        calls.append((case, held))
        return {"contract": "casepath.process-service/2.0.0",
                "documents": ["receipt"], "requests": [], "next_action": None}
    def diff(before, after):
        return {"contract": "casepath.process-plan-diff/2.0.0",
                "withdrawn": [], "added": [], "before": before, "after": after}
    def status():
        return {"ready": True, "method_freeze_sha256": "abc"}
    app = FastAPI()
    app.include_router(create_process_router_v2(plan, diff, status))
    return app, calls


def test_plan_accepts_only_case_material_and_held_documents():
    app, calls = app_and_calls()
    client = TestClient(app)
    response = client.post("/api/paper-method/plan", json={
        "customer_message": "My bicycle was stolen.", "already_held": ["police report"]})
    assert response.status_code == 200
    assert response.json()["documents"] == ["receipt"]
    assert calls == [({"customer_message": "My bicycle was stolen."}, ["police report"])]


def test_unknown_client_fields_are_rejected():
    app, _ = app_and_calls()
    response = TestClient(app).post("/api/paper-method/plan", json={
        "customer_message": "x", "already_held": [], "graph": {"gold": True}})
    assert response.status_code == 422


def test_status_binds_runtime_freeze_identity():
    app, _ = app_and_calls()
    response = TestClient(app).get("/api/paper-method/status")
    assert response.status_code == 200
    assert response.json() == {
        "contract": "casepath.paper-method-status/2.0.0",
        "ready": True,
        "method_freeze_sha256": "abc",
    }


def test_diff_runs_same_planner_on_both_states():
    app, calls = app_and_calls()
    response = TestClient(app).post("/api/paper-method/diff", json={
        "before_customer_message": "before", "after_customer_message": "after",
        "already_held": ["claim form"]})
    assert response.status_code == 200
    assert calls == [({"customer_message": "before"}, ["claim form"]),
                     ({"customer_message": "after"}, ["claim form"])]

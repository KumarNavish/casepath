from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.agent_work.api import create_agent_work_router
from casepath_api.agent_work.contracts import Operation, Role
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.store import WorkStore, WorkStoreError, WorkCancelled


def test_work_history_validates_only_new_events_and_detects_old_tamper(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "work.sqlite3"
    store = WorkStore(path)
    run, _ = store.create("clm_test", "review-command-0001", {"facts_worker": "reference"})
    owner = "worker-1"
    assert store.acquire(run["run_id"], owner)
    assert len(store.snapshot(run["run_id"])["events"]) == 2

    validated: list[int] = []
    original = store._validate_events

    def count_validation(run, rows, **kwargs):
        validated.append(len(rows))
        return original(run, rows, **kwargs)

    monkeypatch.setattr(store, "_validate_events", count_validation)
    assert len(store.snapshot(run["run_id"])["events"]) == 2
    assert validated == []

    store.append(
        run["run_id"], owner,
        operation=Operation.AGENT_STARTED, role=Role.FACTS,
        object_kind="role", object_id=Role.FACTS.value,
        status="started", message="Reading the source", worker_kind="reference",
    )
    assert len(store.snapshot(run["run_id"])["events"]) == 3
    assert validated == [1]

    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER work_events_no_update")
        db.execute(
            "UPDATE work_events SET event_json=? WHERE run_id=? AND sequence=1",
            ("{}", run["run_id"]),
        )
    with pytest.raises(WorkStoreError, match="corrupt|incomplete|crossed"):
        store.snapshot(run["run_id"])


def test_cached_work_product_rejects_changed_persisted_bytes(tmp_path) -> None:
    path = tmp_path / "work.sqlite3"
    store = WorkStore(path)
    run, _ = store.create("clm_test", "review-command-product-0001", {"facts_worker": "reference"})
    owner = "worker-1"
    assert store.acquire(run["run_id"], owner)
    store.begin_call(run["run_id"], owner, Role.FACTS.value, "source-1", "open_source", {"source_id": "source-1"})
    store.complete_call(run["run_id"], owner, Role.FACTS.value, "source-1", {"ok": True}, [],
                        objects=[{"id": "source-1", "kind": "opened_source", "value": {"text": "Original source"}}])
    assert store.snapshot(run["run_id"])["objects"][0]["value"]["text"] == "Original source"
    assert store.snapshot(run["run_id"])["objects"][0]["value"]["text"] == "Original source"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE work_objects SET value_json=? WHERE run_id=? AND object_id=?",
                   ('{"text":"Changed"}', run["run_id"], "source-1"))
    with pytest.raises(WorkStoreError, match="work object differs"):
        store.snapshot(run["run_id"])


def test_workforce_reads_run_table_and_stream_replays_terminal_events(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = WorkStore(tmp_path / "work.sqlite3")
    run, _ = store.create(
        "clm_test", "review-command-0002",
        {"facts_worker": "reference", "context": {"subject": "Mould in bedroom"}},
    )
    assert store.acquire(run["run_id"], "worker-1")
    store.finish(run["run_id"], "worker-1", "completed", "Review complete")
    service = AgentWorkService(store, authority=object())
    try:
        def fail_snapshot(_run_id):
            raise AssertionError("roster read must not replay each work run")

        monkeypatch.setattr(store, "snapshot", fail_snapshot)
        roster = service.workforce()
        assert roster["runs"][0]["subject"] == "Mould in bedroom"
        assert roster["runs"][0]["status"] == "completed"
        monkeypatch.undo()

        app = FastAPI()
        app.include_router(create_agent_work_router(lambda: service))
        response = TestClient(app).get(
            f"/api/agent-work/v1/claims/clm_test/runs/{run['run_id']}/stream?after=1"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: work\n" in response.text
        assert "event: done\n" in response.text
        assert "id: 2\n" in response.text
        assert "id: 1\n" not in response.text
    finally:
        service.shutdown()


def test_stop_is_journaled_and_survives_reload(tmp_path) -> None:
    path = tmp_path / "work.sqlite3"
    store = WorkStore(path)
    queued, _ = store.create("clm_queued", "stop-queued-0001", {"facts_worker": "reference"})
    store.request_cancel(queued["run_id"])
    assert store.get_run(queued["run_id"])["status"] == "cancelled"
    assert store.acquire(queued["run_id"], "worker") is False

    running, _ = store.create("clm_running", "stop-running-0001", {"facts_worker": "reference"})
    assert store.acquire(running["run_id"], "worker")
    store.request_cancel(running["run_id"])
    with pytest.raises(WorkCancelled):
        store.heartbeat(running["run_id"], "worker")
    store.finish(running["run_id"], "worker", "cancelled", "Review stopped")
    reopened = WorkStore(path)
    assert reopened.snapshot(running["run_id"])["run"]["status"] == "cancelled"
    assert [event["operation"] for event in reopened.events(running["run_id"])[-2:]] == [
        "RUN_CANCEL_REQUESTED", "RUN_CANCELLED"
    ]

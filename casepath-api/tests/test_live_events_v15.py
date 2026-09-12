from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import threading
import time
from typing import Any

from fastapi.testclient import TestClient
import pytest

import casepath_api.app as app_module
from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.live_events import accepted_artifact_events, fact_events
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage


SESSION_A = "session-a-12345678"
SESSION_B = "session-b-12345678"


def headers(session_id: str = SESSION_A) -> dict[str, str]:
    return {"X-CasePath-Session": session_id}


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    storage = Storage(str(tmp_path / "events.db"))
    pipeline = ClaimPipeline(
        storage, model_mode=MODEL_MODE_REFERENCE, pace_seconds=0
    )
    monkeypatch.setattr(app_module, "storage", storage)
    monkeypatch.setattr(app_module, "pipeline", pipeline)
    monkeypatch.setattr(app_module, "held_out_pipeline", pipeline)
    return TestClient(app_module.app)


def create_completed_run(client: TestClient) -> tuple[str, dict[str, Any]]:
    response = client.post(
        "/api/runs",
        json={"claim_id": "DEMO-MOULD-002", "knowledge_mode": "current"},
        headers=headers(),
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    for _ in range(500):
        run_response = client.get(f"/api/runs/{run_id}", headers=headers())
        assert run_response.status_code == 200
        run = run_response.json()
        if run["status"] in {"complete", "failed"}:
            assert run["status"] == "complete", run.get("error")
            return run_id, run
        time.sleep(0.01)
    raise AssertionError("run timeout")


def decode_sse(body: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def recursively_contains_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return bool(forbidden & set(value)) or any(
            recursively_contains_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(recursively_contains_key(item, forbidden) for item in value)
    return False


def test_stream_replays_exact_audit_and_semantic_events_then_closes(
    client: TestClient,
):
    run_id, run = create_completed_run(client)

    response = client.get(f"/api/runs/{run_id}/events", headers=headers())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["connection"] == "keep-alive"
    assert response.headers["x-accel-buffering"] == "no"
    events = decode_sse(response.text)
    assert [item["sequence"] for item in events] == list(
        range(1, len(events) + 1)
    )
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "complete"
    assert events[-1]["entity"] == {
        "kind": "run",
        "id": run_id,
        "status": "complete",
    }
    audit_by_id = {item["event_id"]: item for item in run["events"]}
    mirrored = [item for item in events if item["type"] == "run.activity"]
    assert len(mirrored) == len(audit_by_id)
    assert all(
        item["audit_event"] == audit_by_id[item["audit_event"]["event_id"]]
        for item in mirrored
    )
    event_types = {item["type"] for item in events}
    assert {
        "fact.accepted",
        "legal_source.linked",
        "process_node.created",
        "branch.created",
        "evidence_requirement.linked",
        "precedent.selected",
        "verification.accepted",
    } <= event_types
    assert not recursively_contains_key(
        events,
        {"raw_output", "raw_response", "reasoning", "canonical_output"},
    )


def test_process_and_evidence_projection_follow_verification_gate(
    client: TestClient,
):
    run_id, _ = create_completed_run(client)
    events = decode_sse(
        client.get(f"/api/runs/{run_id}/events", headers=headers()).text
    )
    verified_sequence = max(
        item["sequence"]
        for item in events
        if item["type"] == "run.activity"
        and item["audit_event"].get("stage") == "verify"
        and item["audit_event"].get("status") == "completed"
    )
    projected = [
        item
        for item in events
        if item["type"]
        in {
            "process_node.created",
            "branch.created",
            "evidence_requirement.linked",
        }
    ]
    assert projected
    assert all(item["sequence"] > verified_sequence for item in projected)
    assert all(item["acceptance"]["state"] == "accepted" for item in projected)
    assert all(
        item["execution_trace"]["contract"]
        == "casepath.accepted-execution-trace/1.0.0"
        for item in projected
    )
    assert all(
        item["execution_trace"]["presentation_mode"]
        == "returned_action_replay"
        for item in projected
    )
    assert all(
        isinstance(item["acceptance"]["model_contribution_accepted"], bool)
        and isinstance(item["acceptance"]["deterministic_fallback_applied"], bool)
        for item in projected
    )
    assert all(
        len(item["execution_trace"]["input_bindings_hash"]) == 64
        and len(item["execution_trace"]["output_binding_hash"]) == 64
        for item in projected
    )


def test_semantic_execution_trace_separates_model_replay_from_tools(
    client: TestClient,
):
    run_id, _ = create_completed_run(client)
    events = decode_sse(
        client.get(f"/api/runs/{run_id}/events", headers=headers()).text
    )
    semantic = [
        item
        for item in events
        if item["type"]
        in {
            "fact.accepted",
            "legal_source.linked",
            "process_node.created",
            "branch.created",
            "evidence_requirement.linked",
            "precedent.selected",
            "verification.accepted",
        }
    ]
    assert semantic
    assert all(
        item["execution_trace"]["contract"]
        == "casepath.accepted-execution-trace/1.0.0"
        for item in semantic
    )
    assert all(
        len(item["execution_trace"]["input_bindings_hash"]) == 64
        and len(item["execution_trace"]["output_binding_hash"]) == 64
        for item in semantic
    )
    tool_events = [
        item
        for item in semantic
        if item["type"] in {"legal_source.linked", "precedent.selected"}
    ]
    assert tool_events
    assert all(
        item["execution_trace"]["presentation_mode"]
        == "deterministic_projection"
        and item["execution_trace"]["model_contribution_accepted"] is False
        for item in tool_events
    )
    legal_authority = {
        item["entity"]["kind"]: item["execution_trace"]["authority"]
        for item in tool_events
        if item["type"] == "legal_source.linked"
    }
    assert legal_authority == {
        "official_source": "versioned_official_source_registry",
        "handling_principle": "deterministic_operational_interpretation",
    }
    branch_events = [item for item in semantic if item["type"] == "branch.created"]
    verification_events = [
        item for item in semantic if item["type"] == "verification.accepted"
    ]
    assert branch_events and verification_events
    assert all(
        item["actor"]["type"] == "deterministic_tool"
        and item["acceptance"]["model_contribution_accepted"] is False
        for item in branch_events
    )
    assert all(
        item["actor"]["type"] == "deterministic_gate"
        and item["execution_trace"]["authority"]
        == "deterministic_whole_playbook_verification"
        and item["execution_trace"]["model_contribution_accepted"] is False
        for item in verification_events
    )


def test_hybrid_semantic_events_split_model_fields_from_app_structures():
    fact_record = {
        "fact_id": "fact_tenancy",
        "value": "Swiss residential tenancy",
        "source_refs": [],
    }
    node = {
        "node_id": "scope",
        "title": "Scope",
        "question": "Is this our claim?",
        "fact_ids": ["fact_tenancy"],
        "legal_source_ids": ["law_256"],
        "evidence_requirement_ids": ["lease"],
        "branches": [],
        "agent_decision_contributions": [
            {
                "contribution_id": "decision:scope",
                "fact_id": "fact_tenancy",
                "decision_value": "in_scope",
                "deterministic_fallback_applied": False,
            }
        ],
    }
    evidence = {
        "item_id": "lease",
        "title": "Lease agreement",
        "node_id": "scope",
        "node_ids": ["scope"],
        "fact_id": "fact_tenancy",
        "legal_basis_ids": ["law_256"],
        "why": "Shows the tenancy scope.",
        "status": "provided_sufficient",
        "artifact_ids": ["art_lease"],
        "document_options": ["Lease agreement"],
        "agent_contribution": [
            {
                "contribution_id": "evidence:lease:status",
                "field": "status",
                "deterministic_fallback_applied": False,
            },
            {
                "contribution_id": "evidence:lease:artifact_ids",
                "field": "artifact_ids",
                "deterministic_fallback_applied": True,
            },
        ],
    }
    agents = [
        {
            "agent_id": "process_decision_mapping",
            "call_id": "call-process",
            "input_artifact_hash": "4" * 64,
            "output_artifact_hash": "5" * 64,
        },
        {
            "agent_id": "evidence_checklist",
            "call_id": "call-evidence",
            "input_artifact_hash": "6" * 64,
            "output_artifact_hash": "7" * 64,
        },
        {
            "agent_id": "final_claim_brief_audit",
            "call_id": "call-final",
            "input_artifact_hash": "8" * 64,
            "output_artifact_hash": "9" * 64,
        },
    ]
    gates = [
        {
            "agent_id": "deterministic_process_gate",
            "output_artifact_hash": "1" * 64,
            "input_artifact_hash": "a" * 64,
            "source_call_id": "call-process",
        },
        {
            "agent_id": "deterministic_evidence_gate",
            "output_artifact_hash": "2" * 64,
            "input_artifact_hash": "b" * 64,
            "source_call_id": "call-evidence",
        },
        {
            "agent_id": "whole_playbook_gate",
            "output_artifact_hash": "3" * 64,
            "input_artifact_hash": "c" * 64,
            "source_call_id": "call-final",
        },
    ]
    final_brief = {
        "current_node_id": "scope",
        "next_action_node_id": "dispute",
        "supporting_fact_ids": ["fact_tenancy"],
        "audit_check_ids": ["source_grounded"],
        "field_contributions": [
            {
                "field": "current_node_id",
                "deterministic_fallback_applied": False,
            },
            {
                "field": "next_action_node_id",
                "deterministic_fallback_applied": True,
            },
        ],
    }
    events = accepted_artifact_events(
        {"facts": [fact_record], "canonicalization": {"diagnostics": {}}},
        {
            "nodes": [node],
            "edges": [],
            "current_node": "scope",
            "current_overlay": {
                "current_node_id": "scope",
                "next_action_node_id": "dispute",
            },
        },
        {"items": [evidence]},
        {
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "agents": agents,
            "deterministic_gates": gates,
            "final_claim_brief": final_brief,
        },
        {"valid": True, "checks": [{}], "rejected_proposals": []},
    )
    by_type = {item["type"]: item for item in events}

    decision = by_type["process_decision.accepted"]
    structure = by_type["process_node.created"]
    assert decision["actor"]["type"] == "nemotron_agent"
    assert decision["entity"]["value"] == {
        "process_node_id": "scope",
        "contributions": [
            {
                "contribution_id": "decision:scope",
                "decision_value": "in_scope",
            }
        ],
    }
    assert decision["execution_trace"]["model_owned_fields"] == [
        "decision_value"
    ]
    assert decision["links"]["fact_ids"] == ["fact_tenancy"]
    assert decision["execution_trace"]["input_fact_ids"] == [
        "fact_tenancy"
    ]
    assert decision["execution_trace"]["input_bindings_hash"] == sha256(
        json.dumps(
            [fact_record],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert structure["actor"]["type"] == "deterministic_tool"
    assert structure["acceptance"]["accepted_contribution_ids"] == []
    assert structure["acceptance"]["linked_model_contribution_ids"] == [
        "decision:scope"
    ]
    assert structure["execution_trace"]["accepted_contribution_ids"] == []
    assert structure["execution_trace"]["model_owned_fields"] == []

    selected_fields = by_type["evidence_fields.accepted"]
    requirement = by_type["evidence_requirement.linked"]
    assert selected_fields["actor"]["type"] == "nemotron_agent"
    assert selected_fields["entity"]["value"] == {
        "item_id": "lease",
        "status": "provided_sufficient",
    }
    assert selected_fields["execution_trace"]["model_owned_fields"] == [
        "status"
    ]
    assert selected_fields["execution_trace"]["fallback_fields"] == [
        "artifact_ids"
    ]
    assert requirement["actor"]["type"] == "deterministic_tool"
    assert requirement["acceptance"]["accepted_fields"] == []
    assert requirement["acceptance"]["linked_model_fields"] == ["status"]
    assert requirement["execution_trace"]["accepted_fields"] == []
    assert requirement["execution_trace"]["model_owned_fields"] == []
    assert requirement["execution_trace"]["source_call_id"] == "call-evidence"
    assert requirement["execution_trace"]["source_call_input_hash"] == "6" * 64
    assert requirement["execution_trace"]["source_call_output_hash"] == "7" * 64
    assert requirement["execution_trace"]["gate_input_hash"] == "b" * 64

    final_event = by_type["final_brief.accepted"]
    assert final_event["entity"]["value"] == {"current_node_id": "scope"}
    assert final_event["execution_trace"]["model_owned_fields"] == [
        "current_node_id"
    ]
    assert final_event["execution_trace"]["source_call_id"] == "call-final"
    assert final_event["execution_trace"]["source_call_input_hash"] == "8" * 64
    assert final_event["execution_trace"]["source_call_output_hash"] == "9" * 64
    assert final_event["execution_trace"]["gate_input_hash"] == "c" * 64
    verification_event = by_type["verification.accepted"]
    assert verification_event["actor"]["id"] == "whole_playbook_gate"
    assert verification_event["links"] == {
        "process_node_id": "scope",
        "next_action_node_id": "dispute",
    }
    assert verification_event["acceptance"]["artifact_hash"] == sha256(
        json.dumps(
            {"valid": True, "checks": [{}], "rejected_proposals": []},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert verification_event["acceptance"]["whole_playbook_gate_hash"] == "3" * 64


def test_fact_trace_owns_assertion_and_materializes_controlling_meaning():
    fact = {
        "fact_id": "fact_notification",
        "label": "Landlord notified",
        "value": "Notified on 15 July",
        "state": "known",
        "explanation": "The accepted bounded assertion is grounded in the email.",
        "controls_process": True,
        "decision_key": "notification",
        "normalized_value": "landlord_notified",
        "decision_value": "notification_proven",
        "semantic_role": None,
        "confidence": 0.99,
        "source_refs": [
            {
                "artifact_id": "art_notification_email",
                "locator_kind": "text_quote",
                "page": 1,
                "excerpt": "I notified the property manager by email on 15 July.",
                "agent": "OpenRouter Nemotron Canonicalizer",
            }
        ],
    }
    event = fact_events(
        {
            "facts": [fact],
            "canonicalization": {
                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                "call_id": "call-canonical",
                "input_artifact_hash": "1" * 64,
                "output_artifact_hash": "2" * 64,
                "cache_hit": False,
                "origin_call_id": "call-canonical",
                "usage_source": "provider_reported",
                "diagnostics": {
                    "accepted_fact_ids": ["fact_notification"],
                    "source_reference_projection_fact_ids": [],
                },
                "assertion_selections": [
                    {
                        "fact_id": "fact_notification",
                        "assertion_id": "assert_notification_known",
                        "model_owned_fields": [
                            "assertion_id",
                            "source_ref_ids",
                            "confidence",
                        ],
                        "materialized_fields": [
                            "value",
                            "state",
                            "explanation",
                            "normalized_value",
                            "decision_value",
                        ],
                        "attribution": "OpenRouter Nemotron Canonicalizer",
                        "deterministic_fallback_applied": False,
                    }
                ],
            },
        }
    )[0]

    trace = event["execution_trace"]
    assert event["acceptance"]["assertion_id"] == "assert_notification_known"
    assert trace["model_owned_fields"] == [
        "assertion_id",
        "source_ref_ids",
        "confidence",
    ]
    assert trace["materialized_from_model_assertion_fields"] == [
        "value",
        "state",
        "explanation",
        "normalized_value",
        "decision_value",
    ]
    assert not set(trace["materialized_from_model_assertion_fields"]) & set(
        trace["application_owned_fields"]
    )
    assert trace["model_selected_text_refs"] == fact["source_refs"]
    assert trace["authority"] == "model_assertion_materialized"


def test_memory_transformed_events_bind_to_memory_receipt_not_old_model_calls():
    memory = {
        "application_hash": "a" * 64,
        "verification_hash": "b" * 64,
        "after": {
            "process_dto_hash": "c" * 64,
            "checklist_dto_hash": "d" * 64,
        },
        "process_operations": [
            {"node_id": "ventilation_dispute", "operation_id": "add-node"}
        ],
        "evidence_operations": [
            {
                "item_id": "use_evidence",
                "operation_id": "move-evidence",
                "removed_from_node_ids": ["causation"],
                "added_to_node_id": "ventilation_dispute",
            }
        ],
    }
    events = accepted_artifact_events(
        {"facts": [], "canonicalization": {"diagnostics": {}}},
        {
            "nodes": [
                {
                    "node_id": "ventilation_dispute",
                    "fact_ids": [],
                    "legal_source_ids": [],
                    "branches": [],
                    "agent_decision_contributions": [
                        {
                            "contribution_id": "old-model-decision",
                            "decision_value": "conditional",
                            "deterministic_fallback_applied": False,
                        }
                    ],
                },
                {
                    "node_id": "causation",
                    "fact_ids": ["fact_cause"],
                    "legal_source_ids": [],
                    "branches": [],
                    "agent_decision_contributions": [
                        {
                            "contribution_id": "old-cause-decision",
                            "fact_id": "fact_cause",
                            "decision_value": "cause_unresolved",
                            "deterministic_fallback_applied": False,
                        }
                    ],
                },
                {
                    "node_id": "responsibility",
                    "fact_ids": [],
                    "legal_source_ids": [],
                    "branches": [],
                    "agent_decision_contributions": [],
                },
            ],
            "edges": [],
            "current_node": "ventilation_dispute",
        },
        {
            "items": [
                {
                    "item_id": "use_evidence",
                    "node_id": "ventilation_dispute",
                    "node_ids": ["ventilation_dispute"],
                    "fact_id": "fact_use",
                    "agent_contribution": [
                        {
                            "field": "status",
                            "deterministic_fallback_applied": False,
                        }
                    ],
                },
                {
                    "item_id": "lease",
                    "node_id": "scope",
                    "node_ids": ["scope"],
                    "fact_id": "fact_tenancy",
                    "agent_contribution": [
                        {
                            "field": "status",
                            "deterministic_fallback_applied": False,
                        }
                    ],
                },
            ]
        },
        {
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "agents": [],
            "deterministic_gates": [],
            "final_claim_brief": {"field_contributions": []},
        },
        {"valid": True, "checks": [], "rejected_proposals": []},
        memory,
    )
    assert not any(item["type"] == "process_decision.accepted" for item in events)
    assert not any(item["type"] == "evidence_fields.accepted" for item in events)
    process_events = {
        item["entity"]["id"]: item
        for item in events
        if item["type"] == "process_node.created"
    }
    evidence_events = {
        item["entity"]["id"]: item
        for item in events
        if item["type"] == "evidence_requirement.linked"
    }
    for event in [*process_events.values(), *evidence_events.values()]:
        expected_hash = (
            "c" * 64
            if event["type"] == "process_node.created"
            else "d" * 64
        )
        assert event["actor"]["type"] == "deterministic_tool"
        assert event["acceptance"]["source_call_id"] is None
        assert event["acceptance"]["artifact_hash"] == expected_hash
        assert event["acceptance"]["application_hash"] == "a" * 64
        assert event["execution_trace"]["memory_reverified"] is True
        assert event["acceptance"].get("linked_model_contribution_ids", []) == []
        assert event["acceptance"].get("linked_model_fields", []) == []
    assert process_events["ventilation_dispute"]["execution_trace"]["memory_transformed"] is True
    assert process_events["causation"]["execution_trace"]["memory_transformed"] is True
    assert process_events["causation"]["execution_trace"]["memory_operation_id"] == "move-evidence"
    assert process_events["responsibility"]["execution_trace"]["memory_transformed"] is False
    assert evidence_events["use_evidence"]["execution_trace"]["memory_transformed"] is True
    assert evidence_events["lease"]["execution_trace"]["memory_transformed"] is False
    verification = next(
        item for item in events if item["type"] == "verification.accepted"
    )
    assert verification["actor"]["id"] == (
        "deterministic_case_memory_verification"
    )
    assert verification["acceptance"]["artifact_hash"] == "b" * 64
    assert verification["acceptance"]["source_call_id"] is None


def test_stream_replay_after_cursor_and_session_isolation(client: TestClient):
    run_id, _ = create_completed_run(client)
    all_events = decode_sse(
        client.get(f"/api/runs/{run_id}/events", headers=headers()).text
    )
    cursor = all_events[len(all_events) // 2]["sequence"]

    replay = client.get(
        f"/api/runs/{run_id}/events?after={cursor}", headers=headers()
    )

    assert replay.status_code == 200
    replayed = decode_sse(replay.text)
    assert replayed == [item for item in all_events if item["sequence"] > cursor]
    assert client.get(f"/api/runs/{run_id}/events").status_code == 400
    assert (
        client.get(
            f"/api/runs/{run_id}/events", headers=headers(SESSION_B)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/runs/{run_id}/events?after=-1", headers=headers()
        ).status_code
        == 422
    )


def test_outbox_wakes_waiters_and_terminal_is_idempotent(tmp_path: Path):
    storage = Storage(str(tmp_path / "storage.db"))
    run_id = storage.create_run("claim", session_id=SESSION_A)
    revision = storage.stream_revision(run_id)

    worker = threading.Thread(
        target=lambda: storage.add_event(
            run_id,
            {
                "stage": "read",
                "agent": "Attachment Parsing Tool",
                "status": "started",
            },
        )
    )
    worker.start()
    changed = storage.wait_for_stream_change(run_id, revision, timeout=1)
    worker.join()
    assert changed != revision

    storage.patch_run(run_id, status="complete")
    storage.patch_run(run_id, status="complete")
    storage.add_event(
        run_id,
        {"stage": "review", "agent": "Reviewer", "status": "completed"},
    )
    events = storage.stream_events(run_id, session_id=SESSION_A)
    terminal = [item for item in events if item["type"] == "run.completed"]
    assert len(terminal) == 1
    assert events[-1] == terminal[0]

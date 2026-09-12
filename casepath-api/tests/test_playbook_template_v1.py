from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop import (
    ClaimLoopError,
    DEFAULT_EVIDENCE_TOOL_ID,
    DeterministicTemplateArtifactInterpreter,
    ToolResult,
    adapter_implementation_sha256_v1,
    _source_closure_digest_v1,
    project_claim_loop_artifacts_v1,
)
from casepath_api.claim_loop_contracts import ToolResultStatus
from casepath_api.claim_loop_service import ClaimLoopService
from casepath_api.foundation.common import digest_text, digest_value
from casepath_api.multi_agent import (
    AI_AGENT_IDS,
    DETERMINISTIC_GATE_IDS,
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.playbook_materializer import (
    PlaybookMaterializationError,
    build_template_cycle_verification_v1,
    materialize_template_cycle_v1,
    validate_template_legal_context_v1,
)
from casepath_api.playbook_template import PlaybookTemplate
from casepath_api.storage import Storage


SYNTHETIC_CLAIM_ID = "SYN-FH-001"
HISTORY_TEXT = (
    "The administrative record is closed. "
    "The current factual history does not yet resolve causation."
)
CAUSATION_SUPPORT_TEXT = "The factual history now supports causation."


class SyntheticFactualHistoryAdapter:
    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.synthetic-factual-history-adapter/1.0.0"
    implementation_source_sha256 = digest_text(Path(__file__).read_text())
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def execute(self, *, state, **_):
        return ToolResult(
            status=ToolResultStatus.OBSERVED,
            sanitized_content=CAUSATION_SUPPORT_TEXT,
            artifact_source_version=state.record_version,
            artifact_page_count=1,
            source_locator="synthetic-factual-history:causation-support",
        )


def _fact(
    *,
    fact_id: str,
    label: str,
    decision_key: str,
    normalized_value: str,
    decision_value: str,
    state: str,
    value: str,
    excerpt: str,
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "label": label,
        "value": value,
        "state": state,
        "explanation": value,
        "source_refs": [
            {
                "artifact_id": "factual_history",
                "locator_kind": "text_quote",
                "page": 1,
                "excerpt": excerpt,
                "agent": "Synthetic Factual History Projector",
            }
        ],
        "confidence": 1.0,
        "controls_process": True,
        "decision_key": decision_key,
        "normalized_value": normalized_value,
        "decision_value": decision_value,
        "semantic_role": fact_id,
    }


def _node(
    node_id: str,
    *,
    main_spine: bool,
    fact_ids: list[str],
    evidence_ids: list[str],
    branches: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "title": node_id.replace("_", " ").title(),
        "question": f"Resolve {node_id}.",
        "state": "future",
        "answer": "Not reached",
        "why": "Frozen synthetic factual-history contract.",
        "kind": "decision" if main_spine else "branch",
        "main_spine": main_spine,
        "fact_ids": fact_ids,
        "legal_source_ids": [],
        "evidence_requirement_ids": evidence_ids,
        "branches": branches or [],
        "activation": "always",
    }


def _item(
    item_id: str,
    *,
    fact_id: str,
    status: str,
    artifact_ids: list[str],
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "title": item_id.replace("_", " ").title(),
        "status": status,
        "node_id": "record_boundary",
        "fact_id": fact_id,
        "why": "Frozen synthetic factual-history requirement.",
        "legal_basis_ids": [],
        "artifact_ids": artifact_ids,
        "acceptable_alternatives": [],
        "applies_when": "always",
        "required_level": "mandatory",
        "current_path": True,
        "node_ids": ["record_boundary"],
    }


def _template_and_package() -> tuple[PlaybookTemplate, dict[str, object]]:
    facts = [
        _fact(
            fact_id="fact.record_boundary",
            label="Record boundary",
            decision_key="record_boundary",
            normalized_value="closed",
            decision_value="record_closed",
            state="known",
            value="The administrative record is closed.",
            excerpt="The administrative record is closed.",
        ),
        _fact(
            fact_id="fact.causation",
            label="Causation",
            decision_key="causation",
            normalized_value="unresolved",
            decision_value="causation_unresolved",
            state="unknown",
            value="Causation is unresolved.",
            excerpt="The current factual history does not yet resolve causation.",
        ),
    ]
    nodes = [
        _node(
            "intake", main_spine=True, fact_ids=[], evidence_ids=[]
        ),
        _node(
            "record_boundary",
            main_spine=True,
            fact_ids=["fact.record_boundary"],
            evidence_ids=["accepted_factual_history"],
            branches=[
                {
                    "branch_id": "record-unverified",
                    "target": "evidence_gap_record",
                }
            ],
        ),
        _node(
            "causation",
            main_spine=True,
            fact_ids=["fact.causation"],
            evidence_ids=["causation_support"],
            branches=[
                {"branch_id": "merits", "target": "merits_review"},
                {"branch_id": "denial", "target": "denial_review"},
                {
                    "branch_id": "causation-unresolved",
                    "target": "evidence_gap_causation",
                },
            ],
        ),
        _node(
            "merits_review", main_spine=False, fact_ids=[], evidence_ids=[]
        ),
        _node(
            "denial_review", main_spine=False, fact_ids=[], evidence_ids=[]
        ),
        _node(
            "evidence_gap_record",
            main_spine=False,
            fact_ids=[],
            evidence_ids=[],
        ),
        _node(
            "evidence_gap_causation",
            main_spine=False,
            fact_ids=[],
            evidence_ids=[],
        ),
    ]
    edge_pairs = [
        ["intake", "record_boundary"],
        ["record_boundary", "causation"],
        ["record_boundary", "evidence_gap_record"],
        ["causation", "merits_review"],
        ["causation", "denial_review"],
        ["causation", "evidence_gap_causation"],
    ]
    process = {
        "claim_id": SYNTHETIC_CLAIM_ID,
        "nodes": nodes,
        "edges": [
            {"source": source, "target": target, "state": "possible"}
            for source, target in edge_pairs
        ],
        "main_spine": ["intake", "record_boundary", "causation"],
        "current_node": "causation",
        "selected_path": [],
        "current_overlay": {},
    }
    items = [
        _item(
            "accepted_factual_history",
            fact_id="fact.record_boundary",
            status="provided_sufficient",
            artifact_ids=["factual_history"],
        ),
        {
            **_item(
                "causation_support",
                fact_id="fact.causation",
                status="provided_insufficient",
                artifact_ids=["factual_history"],
            ),
            "node_id": "causation",
            "node_ids": ["causation"],
        },
    ]
    route_program = {
        "start_path": ["intake"],
        "steps": [
            {
                "node_id": "record_boundary",
                "decision_key": "record_boundary",
                "transitions": {
                    "record_closed": {"kind": "continue"},
                    "record_unverified": {
                        "kind": "stop",
                        "target_node_id": "evidence_gap_record",
                        "selected_branch_id": "record-unverified",
                        "append_target": True,
                    },
                },
            },
            {
                "node_id": "causation",
                "decision_key": "causation",
                "transitions": {
                    "causation_supported": {
                        "kind": "stop",
                        "target_node_id": "merits_review",
                        "selected_branch_id": "merits",
                        "append_target": True,
                    },
                    "causation_not_supported": {
                        "kind": "stop",
                        "target_node_id": "denial_review",
                        "selected_branch_id": "denial",
                        "append_target": True,
                    },
                    "causation_unresolved": {
                        "kind": "stop",
                        "target_node_id": "evidence_gap_causation",
                        "selected_branch_id": "causation-unresolved",
                        "append_target": True,
                    },
                },
            },
        ],
    }
    record = {"facts": facts, "process": process, "checklist": {"items": items}}
    catalog = {
        "supported_claim_ids": [SYNTHETIC_CLAIM_ID],
        "claim_sha256_by_id": {SYNTHETIC_CLAIM_ID: digest_value(record)},
        "decision_options": {
            "record_boundary": {
                "closed": "record_closed",
                "unverified": "record_unverified",
            },
            "causation": {
                "supported": "causation_supported",
                "not_supported": "causation_not_supported",
                "unresolved": "causation_unresolved",
            },
        },
        "process_node_ids": [value["node_id"] for value in nodes],
        "process_edge_pairs": edge_pairs,
        "process_fact_ids_by_claim": {
            SYNTHETIC_CLAIM_ID: [
                "fact.record_boundary",
                "fact.causation",
            ]
        },
        "evidence_item_ids_by_claim": {
            SYNTHETIC_CLAIM_ID: [
                "accepted_factual_history",
                "causation_support",
            ]
        },
        "evidence_node_ids": {
            "accepted_factual_history": ["record_boundary"],
            "causation_support": ["causation"],
        },
        "evidence_fact_ids_by_claim": {
            SYNTHETIC_CLAIM_ID: {
                "accepted_factual_history": "fact.record_boundary",
                "causation_support": "fact.causation",
            }
        },
        "evidence_artifact_ids_by_claim": {
            SYNTHETIC_CLAIM_ID: ["factual_history"]
        },
        "base_evidence_status_by_claim": {
            SYNTHETIC_CLAIM_ID: {
                "accepted_factual_history": "provided_sufficient",
                "causation_support": "provided_insufficient",
            }
        },
        "legal_registry_version": "synthetic-factual-history/1.0.0",
        "legal_sources_sha256": digest_value([]),
        "same_six_agent_stategraph": True,
        "fail_closed_normalized_values": {
            "record_boundary": "unverified",
            "causation": "unresolved",
        },
        "route_program": route_program,
        "process_rendering_profile": {
            "answer_by_node": {
                "record_boundary": {
                    "record_closed": "Record closed",
                    "record_unverified": "Record boundary unverified",
                },
                "causation": {
                    "causation_supported": "Causation supported",
                    "causation_not_supported": "Causation not supported",
                    "causation_unresolved": "Causation unresolved",
                },
            },
            "blocked_node_ids": [],
            "loop_edge_pairs": [],
            "future_edge_sources": [],
        },
        "evidence_projection_mode": "current_path_only_v1",
        "evidence_artifact_capabilities": {
            "accepted_factual_history": ["factual_history_span"],
            "causation_support": ["factual_history_span"],
        },
        "maximum_controlling_facts": 2,
        "materializer_mode": "declarative_cycle_v1",
        "declarative_records": {SYNTHETIC_CLAIM_ID: record},
    }
    template = PlaybookTemplate.build(
        template_id="casepath.synthetic-factual-history-template",
        template_version="1.0.0",
        catalog=catalog,
    )
    package: dict[str, object] = {
        "claim_id": SYNTHETIC_CLAIM_ID,
        "customer_message": {
            "artifact_id": "message",
            "subject": "Factual-history replay",
            "body": "Assess only the supplied factual history.",
        },
        "artifacts": [
            {
                "artifact_id": "factual_history",
                "filename": "factual-history.txt",
                "media_type": "application/pdf",
                # Deliberately false caller-authored metadata. The graph must
                # derive capabilities from the template/checklist authority.
                "capabilities": ["caller_minted_unrelated_capability"],
                "extracted_pages": [{"page": 1, "text": HISTORY_TEXT}],
            }
        ],
    }
    return template, package


def _verification_builder(template: PlaybookTemplate, facts: list[dict[str, object]]):
    def build(
        cycle_facts: list[dict[str, object]],
        process: dict[str, object],
        checklist: dict[str, object],
    ) -> dict[str, object]:
        assert cycle_facts == facts
        return build_template_cycle_verification_v1(
            template=template,
            facts=cycle_facts,
            process=process,
            checklist=checklist,
        )

    return build


def test_non_mould_template_traverses_same_six_role_three_gate_graph(
    tmp_path: Path,
) -> None:
    template, package = _template_and_package()
    storage = Storage(str(tmp_path / "template-cycle.db"))
    orchestrator = NemotronMultiAgentOrchestrator(
        storage,
        agent_runner=DeterministicStructuredAgent(),
        playbook_template=template,
    )
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=orchestrator,
        playbook_template=template,
        pace_seconds=0,
    )
    initial = materialize_template_cycle_v1(
        template=template,
        claim_id=SYNTHETIC_CLAIM_ID,
        observable_package=package,
    )
    assert initial.process["current_overlay"]["next_action_node_id"] == (
        "evidence_gap_causation"
    )
    first = pipeline.analyze_cycle(
        source_run_id="synthetic-source-run",
        orchestration_id="synthetic-cycle-0001",
        observable_package=initial.observable_package,
        facts=list(initial.facts),
        process=deepcopy(initial.process),
        checklist=deepcopy(initial.checklist),
        verification=deepcopy(initial.verification),
        transport_mode="deterministic_test_double",
        cycle_verification_builder=_verification_builder(
            template, list(initial.facts)
        ),
    )
    audit = first["orchestration_audit"]
    assert audit["playbook_template_sha256"] == template.template_sha256
    assert tuple(value["agent_id"] for value in audit["agents"]) == AI_AGENT_IDS
    assert tuple(
        value["agent_id"] for value in audit["deterministic_gates"]
    ) == DETERMINISTIC_GATE_IDS
    assert all(value["call_count"] == 0 for value in audit["agents"])
    assert first["accepted_cycle_artifacts"]["process"] == initial.process

    excerpt = "The factual history now supports causation."
    revised_package = deepcopy(package)
    revised_package["artifacts"][0]["extracted_pages"][0]["text"] += (
        " " + excerpt
    )
    observation_payload = {
        "fact_id": "fact.causation",
        "evidence_item_id": "causation_support",
        "value": excerpt,
        "fact_state": "known",
        "normalized_value": "supported",
        "explanation": "The new factual-history span supports causation.",
        "evidence_status": "provided_sufficient",
        "source_refs": [
            {
                "source_id": "factual_history",
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": excerpt,
                "source_sha256": digest_text(
                    revised_package["artifacts"][0]["extracted_pages"][0][
                        "text"
                    ]
                ),
            }
        ],
        "observed_at": "2026-08-28T12:00:00+00:00",
    }
    observation = {
        **observation_payload,
        "observation_sha256": digest_value(observation_payload),
    }
    revised = materialize_template_cycle_v1(
        template=template,
        claim_id=SYNTHETIC_CLAIM_ID,
        observable_package=revised_package,
        observation_records=[observation],
    )
    assert revised.process["current_overlay"]["next_action_node_id"] == (
        "merits_review"
    )
    assert initial.facts[0] == revised.facts[0]
    second = pipeline.analyze_cycle(
        source_run_id="synthetic-source-run",
        orchestration_id="synthetic-cycle-0002",
        observable_package=revised.observable_package,
        facts=list(revised.facts),
        process=deepcopy(revised.process),
        checklist=deepcopy(revised.checklist),
        verification=deepcopy(revised.verification),
        transport_mode="deterministic_test_double",
        cycle_verification_builder=_verification_builder(
            template, list(revised.facts)
        ),
    )
    assert second["accepted_cycle_artifacts"]["process"] == revised.process
    assert second["orchestration_audit"]["playbook_template_sha256"] == (
        template.template_sha256
    )


def test_non_mould_full_source_run_remains_fail_closed(tmp_path: Path) -> None:
    template, _ = _template_and_package()
    storage = Storage(str(tmp_path / "template-create.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
            playbook_template=template,
        ),
        playbook_template=template,
        pace_seconds=0,
    )
    try:
        pipeline.create(SYNTHETIC_CLAIM_ID, session_id="synthetic")
    except ValueError as exc:
        assert "Mould-only" in str(exc)
    else:  # pragma: no cover - explicit boundary must remain closed
        raise AssertionError("non-Mould source run unexpectedly entered legacy stages")


def test_declarative_legal_context_is_exactly_template_bound() -> None:
    template, _ = _template_and_package()
    valid = {
        "contract": "casepath.synthetic-legal-context/1.0.0",
        "registry_version": "synthetic-factual-history/1.0.0",
        "sources": [],
    }
    assert len(
        validate_template_legal_context_v1(template=template, legal=valid)
    ) == 2
    with pytest.raises(
        PlaybookMaterializationError,
        match="legal context diverges",
    ):
        validate_template_legal_context_v1(
            template=template,
            legal={**valid, "registry_version": "caller-authored/9.9.9"},
        )
    with pytest.raises(
        PlaybookMaterializationError,
        match="field set is not closed",
    ):
        validate_template_legal_context_v1(
            template=template,
            legal={**valid, "unbound_note": "not authoritative"},
        )


def test_interpreter_source_closure_is_sensitive_to_template_bytes() -> None:
    exact = {
        "claim_loop.py": b"claim-loop-source",
        "playbook_template.py": b"template-source-v1",
    }
    mutated = {**exact, "playbook_template.py": b"template-source-v2"}
    assert _source_closure_digest_v1(exact) != _source_closure_digest_v1(mutated)


def test_factual_history_action_observation_replan_reaches_terminal_packet(
    tmp_path: Path,
) -> None:
    template, package = _template_and_package()
    storage = Storage(str(tmp_path / "factual-history-loop.db"))
    pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
            playbook_template=template,
        ),
        playbook_template=template,
        pace_seconds=0,
    )
    run_id = pipeline.create_declarative_source(
        SYNTHETIC_CLAIM_ID,
        observable_package=package,
        legal_research={
            "contract": "casepath.synthetic-legal-context/1.0.0",
            "registry_version": "synthetic-factual-history/1.0.0",
            "sources": [],
        },
        session_id="synthetic-factual-history",
    )
    run = storage.get_run(run_id, session_id="synthetic-factual-history")
    assert run is not None and run["status"] == "complete"
    interpreter = DeterministicTemplateArtifactInterpreter(
        template=template,
        assertions={
            "causation_support": {
                "assertion_id": "synthetic.causation-supported/1",
                "exact_content": CAUSATION_SUPPORT_TEXT,
                "normalized_value": "supported",
                "explanation": "The admitted factual-history span supports causation.",
            }
        },
    )
    adapter = SyntheticFactualHistoryAdapter()
    service = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: adapter},
        artifact_interpreter=interpreter,
        cycle_pipeline=pipeline,
        cycle_transport_mode="deterministic_test_double",
    )
    created = service.create(
        session_id="synthetic-factual-history",
        source_run_id=run_id,
        idempotency_key="create-factual-history-loop-0001",
    )
    initial = service.state(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    )
    assert initial.selected_action is None
    assert initial.phase.value == "compiled"
    assert initial.process["current_overlay"]["next_action_node_id"] == (
        "evidence_gap_causation"
    )

    completed = service.advance(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
        idempotency_key="advance-factual-history-loop-0001",
        expected_revision=created["revision"],
    )
    state = service.state(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    )
    assert completed["phase"] == "decision_ready"
    assert state.terminal_mode == "finalize"
    assert state.process["current_overlay"]["next_action_node_id"] == "merits_review"
    assert state.facts[0] == initial.facts[0]
    assert next(
        value for value in state.facts if value["fact_id"] == "fact.causation"
    )["normalized_value"] == "supported"
    assert [value.action.evidence_item_id for value in state.action_history] == [
        "causation_support"
    ]
    assert len(state.six_agent_cycle_receipt.agent_ids) == 6
    assert len(state.six_agent_cycle_receipt.deterministic_gate_ids) == 3
    assert state.six_agent_cycle_receipt.model_calls == 0
    assert state.six_agent_cycle_receipt.provider_calls == 0
    assert state.six_agent_cycle_receipt.cost_usd == 0.0
    satisfied = [
        value for value in state.obligations if value.status.value == "satisfied"
    ]
    provenance_keys = {
        (value.fact_id, value.evidence_item_id, value.source_ref_id)
        for value in state.provenance_edges
    }
    assert {value.obligation_id for value in satisfied} == {
        "accepted_factual_history",
        "causation_support",
    }
    assert all(value.source_ref_ids for value in satisfied)
    assert all(
        (value.fact_id, value.obligation_id, source_ref_id) in provenance_keys
        for value in satisfied
        for source_ref_id in value.source_ref_ids
    )
    assert state.sufficiency.provenance_complete is True
    tool_artifact = service.store.tool_artifact(
        state.projection_ledger[0].artifact_receipt_sha256
    )
    assert tool_artifact is not None
    assert (
        tool_artifact.interpretation.implementation_source_sha256
        == interpreter.implementation_source_sha256
    )
    tampered_accepted = deepcopy(state.accepted_artifacts)
    tampered_accepted["facts"][0]["source_refs"] = []
    with pytest.raises(ClaimLoopError, match="deterministic template gates"):
        project_claim_loop_artifacts_v1(
            accepted=tampered_accepted,
            observations=state.observations,
            corrections=state.corrections,
            projection_ledger=state.projection_ledger,
        )
    packet = service.packet(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    )
    assert packet["source_state_sha256"] == state.state_sha256
    assert packet["packet_sha256"] == digest_value(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    activity = service.audit(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    )["total_bound_activity"]
    assert activity["graph_traversal_count"] == 3
    assert activity["model_calls"] == activity["provider_calls"] == 0
    assert activity["credential_access_status"] == (
        "none_due_to_zero_provider_calls"
    )
    assert activity["cost_status"] == "exact"
    assert activity["cost_usd"] == 0.0
    restarted_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
            playbook_template=template,
        ),
        playbook_template=template,
        pace_seconds=0,
    )
    restarted = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicTemplateArtifactInterpreter(
            template=template,
            assertions={
                "causation_support": {
                    "assertion_id": "synthetic.causation-supported/1",
                    "exact_content": CAUSATION_SUPPORT_TEXT,
                    "normalized_value": "supported",
                    "explanation": (
                        "The admitted factual-history span supports causation."
                    ),
                }
            },
        ),
        cycle_pipeline=restarted_pipeline,
        cycle_transport_mode="deterministic_test_double",
    )
    recovered = restarted.state(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    )
    assert recovered == state
    assert restarted.packet(
        session_id="synthetic-factual-history",
        loop_id=created["loop_id"],
    ) == packet

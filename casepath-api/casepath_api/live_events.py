from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable


LIVE_EVENT_CONTRACT = "casepath.run-events/1.0.0"
EXECUTION_TRACE_CONTRACT = "casepath.accepted-execution-trace/1.0.0"
TERMINAL_RUN_STATUSES = frozenset({"complete", "failed"})


def _binding_hash(value: Any) -> str:
    """Hash only the bounded trace value that is already safe to stream."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _actor(
    actor_type: str,
    actor_id: str,
    label: str,
    *,
    model: str | None = None,
    call_id: str | None = None,
    cache_hit: bool | None = None,
    origin_call_id: str | None = None,
    usage_source: str | None = None,
    call_count: int | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": actor_type,
        "id": actor_id,
        "label": label,
        "model": model,
    }
    if call_id:
        value["call_id"] = call_id
    if cache_hit is not None:
        value["cache_hit"] = cache_hit
    if origin_call_id:
        value["origin_call_id"] = origin_call_id
    if usage_source:
        value["usage_source"] = usage_source
    if call_count is not None:
        value["call_count"] = call_count
    if outcome:
        value["outcome"] = outcome
    return value


def activity_event(audit_event: dict[str, Any]) -> dict[str, Any]:
    """Mirror the already-safe persisted audit event without rewriting its claims."""

    event = deepcopy(audit_event)
    return {
        "dedupe_key": f"activity:{event['event_id']}",
        "type": "run.activity",
        "stage": event.get("stage", "orchestrator"),
        "actor": _actor(
            str(event.get("actor_type") or "deterministic_tool"),
            str(event.get("agent_id") or event.get("agent") or "casepath"),
            str(event.get("agent") or event.get("label") or "CasePath"),
            model=event.get("model"),
            call_id=event.get("call_id"),
        ),
        "acceptance": {
            "state": event.get("status"),
            "scope": event.get("acceptance_scope"),
            "receipt_type": event.get("receipt_type"),
        },
        "entity": {
            "kind": "audit_event",
            "id": event["event_id"],
        },
        "links": {},
        "audit_event": event,
    }


def terminal_event(status: str) -> dict[str, Any]:
    if status not in TERMINAL_RUN_STATUSES:
        raise ValueError("unsupported terminal run status")
    event_type = "run.completed" if status == "complete" else "run.failed"
    return {
        "dedupe_key": f"terminal:{status}",
        "type": event_type,
        "status": status,
        "stage": status,
        "actor": _actor(
            "deterministic_gate",
            "run_terminal_boundary",
            "Run terminal boundary",
        ),
        "acceptance": {"state": status},
        "entity": {"kind": "run", "id": None, "status": status},
        "links": {},
    }


def fact_events(understanding: dict[str, Any]) -> list[dict[str, Any]]:
    canonicalization = understanding.get("canonicalization", {})
    diagnostics = canonicalization.get("diagnostics", {})
    accepted_ids = set(diagnostics.get("accepted_fact_ids", []))
    assertion_selections = {
        item["fact_id"]: item
        for item in canonicalization.get("assertion_selections", [])
        if isinstance(item, dict) and isinstance(item.get("fact_id"), str)
    }
    model = canonicalization.get("model")
    projected_ids = set(diagnostics.get("source_reference_projection_fact_ids", []))
    events: list[dict[str, Any]] = []
    for fact in understanding.get("facts", []):
        fact_id = str(fact["fact_id"])
        assertion_selection = assertion_selections.get(fact_id, {})
        model_contribution_accepted = fact_id in accepted_ids
        deterministic_fallback_applied = bool(model) and (
            not model_contribution_accepted
            or assertion_selection.get("deterministic_fallback_applied") is True
        )
        source_reference_projection_applied = fact_id in projected_ids
        selected_model_fields = (
            list(assertion_selection.get("model_owned_fields", []))
            if model_contribution_accepted
            and assertion_selection.get("attribution")
            == "OpenRouter Nemotron Canonicalizer"
            and not deterministic_fallback_applied
            else []
        )
        if source_reference_projection_applied:
            selected_model_fields = [
                field for field in selected_model_fields if field != "source_ref_ids"
            ]
        accepted_fields = selected_model_fields
        fallback_fields = (
            sorted(
                {
                    *(
                        assertion_selection.get(
                            "model_owned_fields", ["source_ref_ids", "confidence"]
                        )
                        if deterministic_fallback_applied
                        else []
                    ),
                    *(["source_ref_ids"] if source_reference_projection_applied else []),
                }
            )
        )
        materialized_from_model_assertion_fields = (
            list(assertion_selection.get("materialized_fields", []))
            if "assertion_id" in accepted_fields
            else []
        )
        model_selected_text_refs = [
            deepcopy(ref)
            for ref in fact.get("source_refs", [])
            if model_contribution_accepted
            and fact_id not in projected_ids
            and ref.get("locator_kind") == "text_quote"
            and ref.get("agent") == "OpenRouter Nemotron Canonicalizer"
        ]
        model_selected_locator_keys = {
            _binding_hash(ref) for ref in model_selected_text_refs
        }
        application_projected_source_refs = [
            deepcopy(ref)
            for ref in fact.get("source_refs", [])
            if _binding_hash(ref) not in model_selected_locator_keys
        ]
        fact_authority = (
            "mixed_model_and_deterministic_projection"
            if source_reference_projection_applied
            else "model_assertion_materialized"
            if materialized_from_model_assertion_fields
            else "model_contribution_accepted"
            if model_contribution_accepted
            else "deterministic_fallback"
            if deterministic_fallback_applied
            else "deterministic_reference_projection"
        )
        actor = _actor(
            "cached_model_replay"
            if model_contribution_accepted
            and canonicalization.get("cache_hit") is True
            else "nemotron_agent"
            if model_contribution_accepted
            else "deterministic_tool",
            "canonical_facts" if model_contribution_accepted else "canonical_fact_projection",
            (
                "Guarded Canonical Facts Agent"
                if model_contribution_accepted
                else "Canonical Fact Projection Tool"
            ),
            model=model if model_contribution_accepted else None,
            call_id=(
                canonicalization.get("call_id")
                if model_contribution_accepted
                else None
            ),
            cache_hit=(
                canonicalization.get("cache_hit") is True
                if model_contribution_accepted
                else None
            ),
            origin_call_id=(
                canonicalization.get("origin_call_id")
                if model_contribution_accepted
                else None
            ),
            usage_source=(
                canonicalization.get("usage_source")
                if model_contribution_accepted
                else None
            ),
            call_count=(
                (0 if canonicalization.get("cache_hit") is True else 1)
                if model_contribution_accepted
                else None
            ),
            outcome=(
                "cache_hit"
                if model_contribution_accepted
                and canonicalization.get("cache_hit") is True
                else "succeeded_with_guarded_fallback"
                if model_contribution_accepted
                and deterministic_fallback_applied
                else "succeeded"
                if model_contribution_accepted
                else None
            ),
        )
        cached_model_replay = (
            model_contribution_accepted
            and canonicalization.get("cache_hit") is True
        )
        events.append(
            {
                "dedupe_key": f"fact:{fact_id}",
                "type": "fact.accepted",
                "stage": "understand",
                "actor": actor,
                "acceptance": {
                    "state": "accepted",
                    "authority": fact_authority,
                    "model_contribution_accepted": model_contribution_accepted,
                    "deterministic_fallback_applied": deterministic_fallback_applied,
                    "accepted_fields": accepted_fields,
                    "fallback_fields": fallback_fields,
                    "assertion_id": assertion_selection.get("assertion_id"),
                    "materialized_from_model_assertion_fields": (
                        materialized_from_model_assertion_fields
                    ),
                    "cache_hit": cached_model_replay,
                },
                "entity": {
                    "kind": "fact",
                    "id": fact_id,
                    "value": deepcopy(fact),
                },
                "links": {
                    "source_refs": deepcopy(fact.get("source_refs", [])),
                },
                "execution_trace": {
                    "contract": EXECUTION_TRACE_CONTRACT,
                    "presentation_mode": (
                        "cached_result_replay"
                        if cached_model_replay
                        else "returned_action_replay"
                    ),
                    "authority": fact_authority,
                    "accepted_source_refs": deepcopy(fact.get("source_refs", [])),
                    "model_selected_text_refs": model_selected_text_refs,
                    "application_projected_source_refs": (
                        application_projected_source_refs
                    ),
                    "accepted_fields": accepted_fields,
                    "fallback_fields": fallback_fields,
                    "model_owned_fields": accepted_fields,
                    "assertion_id": assertion_selection.get("assertion_id"),
                    "materialized_from_model_assertion_fields": (
                        materialized_from_model_assertion_fields
                    ),
                    "application_owned_fields": [
                        field
                        for field in (
                            "label",
                            "value",
                            "state",
                            "explanation",
                            "controls_process",
                            "decision_key",
                            "normalized_value",
                            "decision_value",
                            "semantic_role",
                        )
                        if field not in materialized_from_model_assertion_fields
                    ],
                    "input_bindings_hash": _binding_hash(
                        {
                            "assertion_id": assertion_selection.get("assertion_id"),
                            "model_selected_text_refs": model_selected_text_refs,
                        }
                    ),
                    "source_call_id": canonicalization.get("call_id"),
                    "source_call_input_hash": canonicalization.get(
                        "input_artifact_hash"
                    ),
                    "source_call_output_hash": canonicalization.get(
                        "output_artifact_hash"
                    ),
                    "output_fact_id": fact_id,
                    "output_binding_hash": _binding_hash(fact),
                    "model_contribution_accepted": model_contribution_accepted,
                    "deterministic_fallback_applied": deterministic_fallback_applied,
                    "source_reference_projection_applied": source_reference_projection_applied,
                    "cache_hit": cached_model_replay,
                    "current_run_provider_call": (
                        model_contribution_accepted and not cached_model_replay
                    ),
                },
            }
        )
    return events


def legal_source_events(legal: dict[str, Any]) -> list[dict[str, Any]]:
    questions = legal.get("questions", [])
    events: list[dict[str, Any]] = []
    for source_kind, sources in (
        ("official_source", legal.get("sources", [])),
        ("handling_principle", legal.get("handling_principles", [])),
    ):
        for source in sources:
            source_id = str(source["source_id"])
            is_official_source = source_kind == "official_source"
            actor = _actor(
                "deterministic_tool",
                (
                    "official_law_registry"
                    if is_official_source
                    else "operational_interpretation_registry"
                ),
                (
                    "Swiss Legal Source Tool"
                    if is_official_source
                    else "Handling Interpretation Tool"
                ),
            )
            matching_questions = [
                question
                for question in questions
                if source_id
                in [
                    *question.get("source_ids", []),
                    *question.get("interpretation_ids", []),
                ]
            ]
            events.append(
                {
                    "dedupe_key": f"legal_source:{source_id}",
                    "type": "legal_source.linked",
                    "stage": "research",
                    "actor": actor,
                    "acceptance": {
                        "state": "linked",
                        "authority": (
                            "versioned_official_source_registry"
                            if is_official_source
                            else "deterministic_operational_interpretation"
                        ),
                        "registry_version": legal.get("registry_version"),
                    },
                    "entity": {
                        "kind": source_kind,
                        "id": source_id,
                        "value": deepcopy(source),
                    },
                    "links": {
                        "question_ids": [
                            question["question_id"] for question in matching_questions
                        ],
                        "process_node_ids": sorted(
                            {
                                node_id
                                for question in matching_questions
                                for node_id in question.get("process_node_ids", [])
                            }
                        ),
                    },
                    "execution_trace": {
                        "contract": EXECUTION_TRACE_CONTRACT,
                        "presentation_mode": "deterministic_projection",
                        "authority": (
                            "versioned_official_source_registry"
                            if is_official_source
                            else "deterministic_operational_interpretation"
                        ),
                        "input_question_ids": [
                            question["question_id"] for question in matching_questions
                        ],
                        "input_bindings_hash": _binding_hash(
                            [question["question_id"] for question in matching_questions]
                        ),
                        "output_source_id": source_id,
                        "output_binding_hash": _binding_hash(source),
                        "official_source_count": len(legal.get("sources", [])),
                        "handling_principle_count": len(
                            legal.get("handling_principles", [])
                        ),
                        "model_contribution_accepted": False,
                        "deterministic_fallback_applied": False,
                    },
                }
            )
    return events


def precedent_events(
    precedents: Iterable[dict[str, Any]], ranking_receipt: dict[str, Any]
) -> list[dict[str, Any]]:
    actor = _actor(
        "deterministic_tool",
        "historical_claims_retrieval",
        "Historical Retrieval Tool",
    )
    return [
        {
            "dedupe_key": f"precedent:{item['claim_id']}",
            "type": "precedent.selected",
            "stage": "experience",
            "actor": actor,
            "acceptance": {
                "state": "selected",
                "authority": "deterministic_precedent_ranking",
            },
            "entity": {
                "kind": "precedent",
                "id": item["claim_id"],
                "value": deepcopy(item),
            },
            "links": {"ranking_receipt": deepcopy(ranking_receipt)},
            "execution_trace": {
                "contract": EXECUTION_TRACE_CONTRACT,
                "presentation_mode": "deterministic_projection",
                "authority": "deterministic_precedent_ranking",
                "input_bindings_hash": _binding_hash(ranking_receipt),
                "output_precedent_id": item["claim_id"],
                "output_binding_hash": _binding_hash(item),
                "model_contribution_accepted": False,
                "deterministic_fallback_applied": False,
            },
        }
        for item in precedents
    ]


def accepted_artifact_events(
    understanding: dict[str, Any],
    process: dict[str, Any],
    checklist: dict[str, Any],
    orchestration: dict[str, Any],
    verification: dict[str, Any],
    memory_application: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Project only the graph and checklist that survived deterministic gates."""

    agents = {
        item.get("agent_id"): item for item in orchestration.get("agents", [])
    }
    gates = {
        item.get("agent_id"): item
        for item in orchestration.get("deterministic_gates", [])
    }
    process_agent = agents.get("process_decision_mapping", {})
    evidence_agent = agents.get("evidence_checklist", {})
    final_agent = agents.get("final_claim_brief_audit", {})
    process_cached_replay = process_agent.get("cache_hit") is True
    evidence_cached_replay = evidence_agent.get("cache_hit") is True
    final_cached_replay = final_agent.get("cache_hit") is True
    process_gate = gates.get("deterministic_process_gate", {})
    evidence_gate = gates.get("deterministic_evidence_gate", {})
    final_gate = gates.get("whole_playbook_gate", {})
    facts_by_id = {
        str(item.get("fact_id")): item
        for item in understanding.get("facts", [])
        if item.get("fact_id")
    }
    current_overlay = process.get("current_overlay", {})
    current_node_id = current_overlay.get("current_node_id") or process.get(
        "current_node"
    )
    next_action_node_id = current_overlay.get("next_action_node_id")

    def accepted_actor(
        source: dict[str, Any], fallback_id: str, label: str
    ) -> dict[str, Any]:
        model = orchestration.get("model") if source else None
        cache_hit = bool(model) and source.get("cache_hit") is True
        return _actor(
            "cached_model_replay"
            if cache_hit
            else "nemotron_agent"
            if model
            else "deterministic_tool",
            str(source.get("agent_id") or fallback_id),
            label,
            model=model,
            call_id=source.get("call_id"),
            cache_hit=cache_hit if model else None,
            origin_call_id=source.get("origin_call_id"),
            usage_source=source.get("usage_source"),
            call_count=source.get("call_count"),
            outcome=source.get("outcome"),
        )

    def model_presentation_mode(source: dict[str, Any]) -> str:
        return (
            "cached_result_replay"
            if source.get("cache_hit") is True
            else "returned_action_replay"
        )

    deterministic_process_actor = _actor(
        "deterministic_tool", "process_projection", "Process Projection Tool"
    )
    deterministic_evidence_actor = _actor(
        "deterministic_tool", "evidence_projection", "Evidence Projection Tool"
    )
    process_acceptance = {
        "state": "accepted",
        "gate_id": process_gate.get("agent_id") or "reference_process_validator",
        "artifact_hash": process_gate.get("output_artifact_hash"),
        "source_call_id": process_gate.get("source_call_id"),
    }
    evidence_acceptance = {
        "state": "accepted",
        "gate_id": evidence_gate.get("agent_id") or "reference_evidence_validator",
        "artifact_hash": evidence_gate.get("output_artifact_hash"),
        "source_call_id": evidence_gate.get("source_call_id"),
    }
    final_acceptance = {
        "state": "accepted",
        "gate_id": final_gate.get("agent_id") or "reference_verification_validator",
        "artifact_hash": final_gate.get("final_brief_artifact_hash")
        or final_gate.get("output_artifact_hash"),
        "whole_playbook_gate_hash": final_gate.get("output_artifact_hash"),
        "source_call_id": final_gate.get("source_call_id"),
    }
    memory_process_node_ids = {
        str(item.get("node_id"))
        for item in (memory_application or {}).get("process_operations", [])
        if item.get("node_id")
    }
    memory_process_operation_ids = {
        str(item.get("node_id")): str(item.get("operation_id"))
        for item in (memory_application or {}).get("process_operations", [])
        if item.get("node_id") and item.get("operation_id")
    }
    for operation in (memory_application or {}).get("evidence_operations", []):
        operation_id = operation.get("operation_id")
        if not operation_id:
            continue
        affected_node_ids = [
            *(operation.get("removed_from_node_ids") or []),
            operation.get("added_to_node_id"),
        ]
        for affected_node_id in affected_node_ids:
            if not affected_node_id:
                continue
            node_id = str(affected_node_id)
            memory_process_node_ids.add(node_id)
            memory_process_operation_ids.setdefault(node_id, str(operation_id))
    memory_evidence_ids = {
        str(item.get("item_id"))
        for item in (memory_application or {}).get("evidence_operations", [])
        if item.get("item_id")
    }
    memory_evidence_operation_ids = {
        str(item.get("item_id")): str(item.get("operation_id"))
        for item in (memory_application or {}).get("evidence_operations", [])
        if item.get("item_id") and item.get("operation_id")
    }
    memory_reverified = memory_application is not None
    events: list[dict[str, Any]] = []
    for node in process.get("nodes", []):
        node_id = str(node["node_id"])
        node_contributions = deepcopy(node.get("agent_decision_contributions", []))
        accepted_contribution_ids = [
            str(item.get("contribution_id"))
            for item in node_contributions
            if item.get("contribution_id")
            and item.get("deterministic_fallback_applied") is False
        ]
        fallback_contribution_ids = [
            str(item.get("contribution_id"))
            for item in node_contributions
            if item.get("contribution_id")
            and item.get("deterministic_fallback_applied") is True
        ]
        memory_transformed = node_id in memory_process_node_ids
        superseded_contribution_ids: list[str] = []
        superseded_fallback_contribution_ids: list[str] = []
        if memory_reverified:
            superseded_contribution_ids = accepted_contribution_ids
            superseded_fallback_contribution_ids = fallback_contribution_ids
            accepted_contribution_ids = []
            fallback_contribution_ids = []
        has_model_contribution = bool(accepted_contribution_ids)
        accepted_decision_value = {
            "process_node_id": node_id,
            "contributions": [
                {
                    "contribution_id": str(item.get("contribution_id")),
                    "decision_value": deepcopy(item.get("decision_value")),
                }
                for item in node_contributions
                if str(item.get("contribution_id")) in accepted_contribution_ids
            ],
        }
        accepted_decision_fact_ids = sorted(
            {
                str(item.get("fact_id"))
                for item in node_contributions
                if str(item.get("contribution_id"))
                in accepted_contribution_ids
                and item.get("fact_id")
            }
        )
        accepted_decision_inputs = [
            deepcopy(facts_by_id[fact_id])
            for fact_id in accepted_decision_fact_ids
            if fact_id in facts_by_id
        ]
        if has_model_contribution:
            events.append(
                {
                    "dedupe_key": f"process_decision:{node_id}",
                    "type": "process_decision.accepted",
                    "stage": "process",
                    "actor": accepted_actor(
                        process_agent,
                        "process_decision_mapping",
                        "Process Decision Mapping Agent",
                    ),
                    "acceptance": {
                        **process_acceptance,
                        "authority": "model_field_accepted_by_process_gate",
                        "model_contribution_accepted": True,
                        "deterministic_fallback_applied": False,
                        "accepted_contribution_ids": accepted_contribution_ids,
                        "accepted_fields": ["decision_value"],
                        "fallback_fields": [],
                        "cache_hit": process_cached_replay,
                    },
                    "entity": {
                        "kind": "process_decision",
                        "id": node_id,
                        "value": accepted_decision_value,
                    },
                    "links": {
                        "process_node_id": node_id,
                        "fact_ids": accepted_decision_fact_ids,
                    },
                    "execution_trace": {
                        "contract": EXECUTION_TRACE_CONTRACT,
                        "presentation_mode": model_presentation_mode(
                            process_agent
                        ),
                        "authority": "model_field_accepted_by_process_gate",
                        "input_fact_ids": accepted_decision_fact_ids,
                        "input_bindings_hash": _binding_hash(
                            accepted_decision_inputs
                        ),
                        "source_call_id": process_agent.get("call_id"),
                        "source_call_input_hash": process_agent.get(
                            "input_artifact_hash"
                        ),
                        "source_call_output_hash": process_agent.get(
                            "output_artifact_hash"
                        ),
                        "gate_input_hash": process_gate.get(
                            "input_artifact_hash"
                        ),
                        "accepted_contribution_ids": accepted_contribution_ids,
                        "fallback_contribution_ids": [],
                        "model_owned_fields": ["decision_value"],
                        "application_owned_fields": [],
                        "output_process_node_id": node_id,
                        "output_binding_hash": _binding_hash(
                            accepted_decision_value
                        ),
                        "model_contribution_accepted": True,
                        "deterministic_fallback_applied": False,
                        "cache_hit": process_cached_replay,
                        "current_run_provider_call": not process_cached_replay,
                    },
                }
            )
        memory_operation_id = memory_process_operation_ids.get(node_id)
        memory_after = (memory_application or {}).get("after", {})
        node_acceptance = {
            **(
                {
                    "state": "accepted",
                    "gate_id": "deterministic_case_memory_application",
                    "artifact_hash": memory_after.get("process_dto_hash"),
                    "source_call_id": None,
                    "application_hash": (memory_application or {}).get(
                        "application_hash"
                    ),
                    "operation_id": memory_operation_id,
                }
                if memory_reverified
                else process_acceptance
            ),
            "authority": (
                "deterministic_case_memory_transform"
                if memory_transformed
                else "deterministic_case_memory_reverified"
                if memory_reverified
                else "deterministic_process_projection"
                if has_model_contribution
                else "deterministic_fallback_projection"
                if fallback_contribution_ids
                else "deterministic_process_structure"
            ),
            "model_contribution_accepted": False,
            "deterministic_fallback_applied": bool(fallback_contribution_ids),
            "accepted_contribution_ids": [],
            "linked_model_contribution_ids": accepted_contribution_ids,
            "fallback_contribution_ids": fallback_contribution_ids,
        }
        events.append(
            {
                "dedupe_key": f"process_node:{node_id}",
                "type": "process_node.created",
                "stage": "process",
                "actor": deterministic_process_actor,
                "acceptance": node_acceptance,
                "entity": {
                    "kind": "process_node",
                    "id": node_id,
                    "value": deepcopy(node),
                },
                "links": {
                    "incoming_edges": [
                        deepcopy(edge)
                        for edge in process.get("edges", [])
                        if edge.get("target") == node_id
                    ],
                    "legal_source_ids": deepcopy(
                        node.get("legal_source_ids", [])
                    ),
                    "fact_ids": deepcopy(node.get("fact_ids", [])),
                },
                "execution_trace": {
                    "contract": EXECUTION_TRACE_CONTRACT,
                    "presentation_mode": "returned_action_replay",
                    "authority": node_acceptance["authority"],
                    "input_fact_ids": deepcopy(node.get("fact_ids", [])),
                    "input_legal_source_ids": deepcopy(
                        node.get("legal_source_ids", [])
                    ),
                    "input_bindings_hash": _binding_hash(
                        {
                            "fact_ids": node.get("fact_ids", []),
                            "legal_source_ids": node.get("legal_source_ids", []),
                        }
                    ),
                    "accepted_contribution_ids": [],
                    "fallback_contribution_ids": fallback_contribution_ids,
                    "superseded_contribution_ids": superseded_contribution_ids,
                    "superseded_fallback_contribution_ids": (
                        superseded_fallback_contribution_ids
                    ),
                    "linked_model_contribution_ids": accepted_contribution_ids,
                    "model_owned_fields": [],
                    "application_owned_fields": sorted(node),
                    "memory_transformed": memory_transformed,
                    "memory_reverified": memory_reverified,
                    "memory_operation_id": memory_operation_id,
                    "memory_application_hash": (
                        (memory_application or {}).get("application_hash")
                        if memory_reverified
                        else None
                    ),
                    "output_node_id": node_id,
                    "output_binding_hash": _binding_hash(node),
                    "model_contribution_accepted": False,
                    "deterministic_fallback_applied": bool(
                        fallback_contribution_ids
                    ),
                },
            }
        )
        for index, branch in enumerate(node.get("branches", [])):
            branch_id = str(
                branch.get("branch_id")
                or branch.get("node_id")
                or branch.get("target")
                or index
            )
            events.append(
                {
                    "dedupe_key": f"branch:{node_id}:{branch_id}",
                    "type": "branch.created",
                    "stage": "process",
                    "actor": deterministic_process_actor,
                    "acceptance": {
                        **(
                            {
                                "state": "accepted",
                                "gate_id": "deterministic_case_memory_application",
                                "artifact_hash": memory_after.get(
                                    "process_dto_hash"
                                ),
                                "source_call_id": None,
                                "application_hash": (
                                    memory_application or {}
                                ).get("application_hash"),
                            }
                            if memory_reverified
                            else process_acceptance
                        ),
                        "authority": (
                            "deterministic_case_memory_reverified"
                            if memory_reverified
                            else "deterministic_process_structure"
                        ),
                        "model_contribution_accepted": False,
                        "deterministic_fallback_applied": False,
                        "accepted_contribution_ids": [],
                        "fallback_contribution_ids": [],
                    },
                    "entity": {
                        "kind": "process_branch",
                        "id": f"{node_id}:{branch_id}",
                        "value": deepcopy(branch),
                    },
                    "links": {"process_node_id": node_id},
                    "execution_trace": {
                        "contract": EXECUTION_TRACE_CONTRACT,
                        "presentation_mode": "returned_action_replay",
                        "authority": (
                            "deterministic_case_memory_reverified"
                            if memory_reverified
                            else "deterministic_process_structure"
                        ),
                        "input_process_node_id": node_id,
                        "input_bindings_hash": _binding_hash(node_id),
                        "output_branch_id": branch_id,
                        "output_binding_hash": _binding_hash(branch),
                        "model_owned_fields": [],
                        "application_owned_fields": [
                            "branch_id",
                            "label",
                            "target",
                            "state",
                        ],
                        "memory_reverified": memory_reverified,
                        "memory_application_hash": (
                            (memory_application or {}).get("application_hash")
                            if memory_reverified
                            else None
                        ),
                        "model_contribution_accepted": False,
                        "deterministic_fallback_applied": False,
                    },
                }
            )
    for item in checklist.get("items", []):
        item_id = str(item["item_id"])
        field_contributions = deepcopy(item.get("agent_contribution", []))
        accepted_fields = [
            str(value.get("field"))
            for value in field_contributions
            if value.get("field")
            and value.get("deterministic_fallback_applied") is False
        ]
        fallback_fields = [
            str(value.get("field"))
            for value in field_contributions
            if value.get("field")
            and value.get("deterministic_fallback_applied") is True
        ]
        memory_transformed = item_id in memory_evidence_ids
        superseded_model_fields: list[str] = []
        superseded_fallback_fields: list[str] = []
        if memory_reverified:
            superseded_model_fields = accepted_fields
            superseded_fallback_fields = fallback_fields
            accepted_fields = []
            fallback_fields = []
        bounded_evidence_value = {
            "item_id": item_id,
            **(
                {"status": deepcopy(item.get("status"))}
                if "status" in accepted_fields
                else {}
            ),
            **(
                {"artifact_ids": deepcopy(item.get("artifact_ids", []))}
                if "artifact_ids" in accepted_fields
                else {}
            ),
        }
        if accepted_fields:
            events.append(
                {
                    "dedupe_key": f"evidence_fields:{item_id}",
                    "type": "evidence_fields.accepted",
                    "stage": "evidence",
                    "actor": accepted_actor(
                        evidence_agent,
                        "evidence_checklist",
                        "Evidence and Checklist Agent",
                    ),
                    "acceptance": {
                        **evidence_acceptance,
                        "authority": "model_fields_accepted_by_evidence_gate",
                        "model_contribution_accepted": True,
                        "deterministic_fallback_applied": bool(fallback_fields),
                        "accepted_fields": accepted_fields,
                        "fallback_fields": fallback_fields,
                        "cache_hit": evidence_cached_replay,
                    },
                    "entity": {
                        "kind": "evidence_fields",
                        "id": item_id,
                        "value": bounded_evidence_value,
                    },
                    "links": {
                        "evidence_requirement_id": item_id,
                        "process_node_ids": deepcopy(
                            item.get("node_ids") or [item.get("node_id")]
                        ),
                    },
                    "execution_trace": {
                        "contract": EXECUTION_TRACE_CONTRACT,
                        "presentation_mode": model_presentation_mode(
                            evidence_agent
                        ),
                        "authority": "model_fields_accepted_by_evidence_gate",
                        "input_bindings_hash": _binding_hash(
                            {
                                "item_id": item_id,
                                "process_node_ids": item.get("node_ids")
                                or [item.get("node_id")],
                            }
                        ),
                        "source_call_id": evidence_agent.get("call_id"),
                        "source_call_input_hash": evidence_agent.get(
                            "input_artifact_hash"
                        ),
                        "source_call_output_hash": evidence_agent.get(
                            "output_artifact_hash"
                        ),
                        "gate_input_hash": evidence_gate.get(
                            "input_artifact_hash"
                        ),
                        "accepted_fields": accepted_fields,
                        "fallback_fields": fallback_fields,
                        "model_owned_fields": accepted_fields,
                        "application_owned_fields": [],
                        "output_evidence_id": item_id,
                        "output_binding_hash": _binding_hash(
                            bounded_evidence_value
                        ),
                        "model_contribution_accepted": True,
                        "deterministic_fallback_applied": bool(
                            fallback_fields
                        ),
                        "cache_hit": evidence_cached_replay,
                        "current_run_provider_call": not evidence_cached_replay,
                    },
                }
            )
        memory_operation_id = memory_evidence_operation_ids.get(item_id)
        memory_after = (memory_application or {}).get("after", {})
        evidence_item_acceptance = {
            **(
                {
                    "state": "accepted",
                    "gate_id": "deterministic_case_memory_application",
                    "artifact_hash": memory_after.get("checklist_dto_hash"),
                    "source_call_id": None,
                    "application_hash": (memory_application or {}).get(
                        "application_hash"
                    ),
                    "operation_id": memory_operation_id,
                }
                if memory_reverified
                else evidence_acceptance
            ),
            "authority": (
                "deterministic_case_memory_transform"
                if memory_transformed
                else "deterministic_case_memory_reverified"
                if memory_reverified
                else "deterministic_evidence_projection"
                if accepted_fields
                else "deterministic_fallback_projection"
                if fallback_fields
                else "deterministic_evidence_structure"
            ),
            "model_contribution_accepted": False,
            "deterministic_fallback_applied": bool(fallback_fields),
            "accepted_fields": [],
            "linked_model_fields": accepted_fields,
            "fallback_fields": fallback_fields,
        }
        events.append(
            {
                "dedupe_key": f"evidence_requirement:{item_id}",
                "type": "evidence_requirement.linked",
                "stage": "evidence",
                "actor": deterministic_evidence_actor,
                "acceptance": evidence_item_acceptance,
                "entity": {
                    "kind": "evidence_requirement",
                    "id": item_id,
                    "value": deepcopy(item),
                },
                "links": {
                    "process_node_id": item.get("node_id"),
                    "fact_id": item.get("fact_id"),
                    "legal_source_ids": deepcopy(item.get("legal_basis_ids", [])),
                },
                "execution_trace": {
                    "contract": EXECUTION_TRACE_CONTRACT,
                    "presentation_mode": "returned_action_replay",
                    "authority": evidence_item_acceptance["authority"],
                    "input_process_node_ids": deepcopy(
                        item.get("node_ids") or [item.get("node_id")]
                    ),
                    "input_fact_id": item.get("fact_id"),
                    "input_bindings_hash": _binding_hash(
                        {
                            "process_node_ids": item.get("node_ids")
                            or [item.get("node_id")],
                            "fact_id": item.get("fact_id"),
                        }
                    ),
                    "source_call_id": (
                        None
                        if memory_reverified
                        else evidence_agent.get("call_id")
                    ),
                    "source_call_input_hash": (
                        None
                        if memory_reverified
                        else evidence_agent.get("input_artifact_hash")
                    ),
                    "source_call_output_hash": (
                        None
                        if memory_reverified
                        else evidence_agent.get("output_artifact_hash")
                    ),
                    "gate_input_hash": (
                        None
                        if memory_reverified
                        else evidence_gate.get("input_artifact_hash")
                    ),
                    "accepted_fields": [],
                    "fallback_fields": fallback_fields,
                    "linked_model_fields": accepted_fields,
                    "superseded_model_fields": superseded_model_fields,
                    "superseded_fallback_fields": superseded_fallback_fields,
                    "model_owned_fields": [],
                    "application_owned_fields": sorted(
                        key for key in item if key != "agent_contribution"
                    ),
                    "provenance_fields": (
                        ["agent_contribution"]
                        if "agent_contribution" in item
                        else []
                    ),
                    "memory_transformed": memory_transformed,
                    "memory_reverified": memory_reverified,
                    "memory_operation_id": memory_operation_id,
                    "memory_application_hash": (
                        (memory_application or {}).get("application_hash")
                        if memory_reverified
                        else None
                    ),
                    "output_evidence_id": item_id,
                    "output_binding_hash": _binding_hash(item),
                    "model_contribution_accepted": False,
                    "deterministic_fallback_applied": bool(fallback_fields),
                },
            }
        )

    final_field_contributions = deepcopy(
        orchestration.get("final_claim_brief", {}).get("field_contributions", [])
    )
    final_accepted_fields = [
        str(value.get("field"))
        for value in final_field_contributions
        if value.get("field") and value.get("deterministic_fallback_applied") is False
    ]
    final_fallback_fields = [
        str(value.get("field"))
        for value in final_field_contributions
        if value.get("field") and value.get("deterministic_fallback_applied") is True
    ]
    final_event_acceptance = {
        **final_acceptance,
        "authority": (
            "model_selected_with_deterministic_projection"
            if final_accepted_fields and not final_fallback_fields
            else "mixed_model_and_deterministic_projection"
            if final_accepted_fields
            else "deterministic_fallback_projection"
            if final_fallback_fields
            else "deterministic_verification_structure"
        ),
        "model_contribution_accepted": bool(final_accepted_fields),
        "deterministic_fallback_applied": bool(final_fallback_fields),
        "accepted_fields": final_accepted_fields,
        "fallback_fields": final_fallback_fields,
    }
    if final_accepted_fields and memory_application is None:
        final_brief = orchestration.get("final_claim_brief", {})
        bounded_final_value = {
            field: deepcopy(final_brief.get(field))
            for field in final_accepted_fields
        }
        events.append(
            {
                "dedupe_key": "final_brief:accepted",
                "type": "final_brief.accepted",
                "stage": "verify",
                "actor": accepted_actor(
                    final_agent,
                    "final_brief_projection",
                    "Final Claim Brief Audit Agent",
                ),
                "acceptance": {
                    **final_event_acceptance,
                    "cache_hit": final_cached_replay,
                },
                "entity": {
                    "kind": "final_brief",
                    "id": "final_claim_brief",
                    "value": bounded_final_value,
                },
                "links": {
                    "verification_id": "whole_playbook_verification",
                },
                "execution_trace": {
                    "contract": EXECUTION_TRACE_CONTRACT,
                    "presentation_mode": model_presentation_mode(final_agent),
                    "authority": final_event_acceptance["authority"],
                    "model_owned_fields": final_accepted_fields,
                    "application_owned_fields": [],
                    "input_bindings_hash": _binding_hash(
                        {
                            "process_node_id": current_node_id,
                            "next_action_node_id": next_action_node_id,
                        }
                    ),
                    "source_call_id": final_agent.get("call_id"),
                    "source_call_input_hash": final_agent.get(
                        "input_artifact_hash"
                    ),
                    "source_call_output_hash": final_agent.get(
                        "output_artifact_hash"
                    ),
                    "gate_input_hash": final_gate.get("input_artifact_hash"),
                    "output_binding_hash": _binding_hash(
                        bounded_final_value
                    ),
                    "model_contribution_accepted": bool(final_accepted_fields),
                    "deterministic_fallback_applied": bool(final_fallback_fields),
                    "cache_hit": final_cached_replay,
                    "current_run_provider_call": not final_cached_replay,
                },
            }
        )

    memory_verification = memory_application is not None
    verification_acceptance = (
        {
            "state": "accepted",
            "gate_id": "deterministic_case_memory_verification",
            "artifact_hash": memory_application.get("verification_hash"),
            "source_call_id": None,
            "application_hash": memory_application.get("application_hash"),
            "authority": "deterministic_case_memory_verification",
            "model_contribution_accepted": False,
            "deterministic_fallback_applied": False,
            "accepted_fields": [],
            "fallback_fields": [],
        }
        if memory_verification
        else {
            "state": "accepted",
            "gate_id": final_acceptance["gate_id"],
            "artifact_hash": _binding_hash(verification),
            "source_call_id": final_acceptance.get("source_call_id"),
            "final_brief_artifact_hash": final_acceptance.get("artifact_hash"),
            "whole_playbook_gate_hash": final_acceptance.get(
                "whole_playbook_gate_hash"
            ),
            "verification_report_hash": _binding_hash(verification),
            "whole_playbook_hash": verification.get("whole_playbook_hash"),
            "authority": "deterministic_whole_playbook_verification",
            "model_contribution_accepted": False,
            "deterministic_fallback_applied": False,
            "accepted_fields": [],
            "fallback_fields": [],
        }
    )
    verification_authority = verification_acceptance["authority"]
    events.append(
        {
            "dedupe_key": "verification:whole_playbook_verification",
            "type": "verification.accepted",
            "stage": "verify",
            "actor": _actor(
                "deterministic_gate",
                (
                    "deterministic_case_memory_verification"
                    if memory_verification
                    else "whole_playbook_gate"
                ),
                (
                    "Deterministic Case Memory Verification"
                    if memory_verification
                    else "Whole Playbook Verification Gate"
                ),
            ),
            "acceptance": verification_acceptance,
            "entity": {
                "kind": "verification",
                "id": "whole_playbook_verification",
                "value": {
                    "status": "passed" if verification.get("valid") is True else "failed",
                    "checks_total": len(verification.get("checks", [])),
                    "rejected_count": len(
                        verification.get("rejected_proposals", [])
                    ),
                },
            },
            "links": {
                "process_node_id": current_node_id,
                "next_action_node_id": next_action_node_id,
            },
            "execution_trace": {
                "contract": EXECUTION_TRACE_CONTRACT,
                "presentation_mode": "returned_action_replay",
                "authority": verification_authority,
                "input_process_node_id": current_node_id,
                "input_next_action_node_id": next_action_node_id,
                "input_bindings_hash": _binding_hash(
                    {
                        "process_node_id": current_node_id,
                        "next_action_node_id": next_action_node_id,
                    }
                ),
                "accepted_fields": [],
                "fallback_fields": [],
                "output_verification_id": "whole_playbook_verification",
                "output_binding_hash": _binding_hash(
                    {
                        "status": "passed"
                        if verification.get("valid") is True
                        else "failed",
                        "checks_total": len(verification.get("checks", [])),
                        "rejected_count": len(
                            verification.get("rejected_proposals", [])
                        ),
                    }
                ),
                "verification_report_hash": _binding_hash(verification),
                "whole_playbook_hash": verification.get("whole_playbook_hash"),
                "final_brief_artifact_hash": final_acceptance.get(
                    "artifact_hash"
                ),
                "whole_playbook_gate_hash": final_acceptance.get(
                    "whole_playbook_gate_hash"
                ),
                "memory_transformed": memory_verification,
                "memory_application_hash": (
                    memory_application.get("application_hash")
                    if memory_verification
                    else None
                ),
                "model_contribution_accepted": False,
                "deterministic_fallback_applied": False,
                "model_owned_fields": [],
                "application_owned_fields": [
                    "valid",
                    "checks",
                    "rejected_proposals",
                    "whole_playbook_hash",
                ],
            },
        }
    )

    rejected: list[dict[str, Any]] = []
    diagnostics = understanding.get("canonicalization", {}).get("diagnostics", {})
    rejected.extend(diagnostics.get("rejected_facts", []))
    for agent in orchestration.get("agents", []):
        for item in agent.get("rejected", []):
            rejected.append({"agent_id": agent.get("agent_id"), **item})
    rejected.extend(verification.get("rejected_proposals", []))
    for index, item in enumerate(rejected):
        rejection_id = str(
            item.get("fact_id")
            or item.get("item_id")
            or item.get("proposal_id")
            or item.get("contribution_id")
            or index
        )
        safe_rejection = {
            key: deepcopy(item[key])
            for key in (
                "fact_id",
                "item_id",
                "proposal_id",
                "contribution_id",
                "agent_id",
                "invariant",
                "reason",
            )
            if key in item
        }
        events.append(
            {
                "dedupe_key": f"verification_rejection:{index}:{rejection_id}",
                "type": "verification.rejected",
                "stage": "verify",
                "actor": _actor(
                    "deterministic_gate",
                    "verification_gate",
                    "Deterministic Verification Gate",
                ),
                "acceptance": {"state": "rejected"},
                "entity": {
                    "kind": "rejected_proposal",
                    "id": rejection_id,
                    "value": safe_rejection,
                },
                "links": {},
            }
        )
    return events


def encode_sse(event: dict[str, Any]) -> str:
    return (
        f"id: {event['sequence']}\n"
        f"event: {event['type']}\n"
        f"data: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def validate_event_draft(value: dict[str, Any]) -> None:
    required = {
        "dedupe_key",
        "type",
        "stage",
        "actor",
        "acceptance",
        "entity",
        "links",
    }
    if not required <= value.keys():
        raise ValueError("invalid live event draft")
    if not isinstance(value["dedupe_key"], str) or not value["dedupe_key"]:
        raise ValueError("invalid live event dedupe key")


__all__ = [
    "LIVE_EVENT_CONTRACT",
    "TERMINAL_RUN_STATUSES",
    "accepted_artifact_events",
    "activity_event",
    "encode_sse",
    "fact_events",
    "legal_source_events",
    "precedent_events",
    "terminal_event",
    "validate_event_draft",
]

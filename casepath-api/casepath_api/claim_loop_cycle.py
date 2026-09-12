from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any, Literal

from .claim_loop_contracts import (
    AcceptedCycleArtifactsV1,
    AcceptedRoleArtifactsV1,
    SixAgentCycleReceipt,
)
from .foundation.common import digest_value
from .multi_agent import (
    AI_AGENT_IDS,
    DETERMINISTIC_GATE_IDS,
    accepted_artifact_hash,
)


class ClaimLoopCycleError(ValueError):
    pass


def _closed_mapping(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ClaimLoopCycleError(f"{label} schema is invalid")
    return value


def _unique_mapping_rows(
    value: Any,
    *,
    keys: set[str],
    identity: str,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ClaimLoopCycleError(f"{label} roster is invalid")
    rows = [_closed_mapping(row, keys, label) for row in value]
    identities = [row.get(identity) for row in rows]
    if any(not isinstance(item, str) or not item for item in identities) or len(
        set(identities)
    ) != len(identities):
        raise ClaimLoopCycleError(f"{label} identities are invalid")
    return rows


def _validate_role_artifact_shapes(value: AcceptedRoleArtifactsV1) -> None:
    facts = list(value.canonical_facts)
    if not facts or len(
        {
            fact.get("fact_id")
            for fact in facts
            if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str)
        }
    ) != len(facts) or any(
        not isinstance(fact, dict)
        or not {"fact_id", "state", "value", "source_refs"} <= set(fact)
        or not isinstance(fact.get("source_refs"), list)
        for fact in facts
    ):
        raise ClaimLoopCycleError("canonical fact role artifact is invalid")

    plan = _closed_mapping(
        value.orchestrator_plan,
        {
            "contribution_type",
            "deterministic_coverage",
            "focus_fact_ids",
            "focus_source_ref_ids",
            "model_priority_attribution",
            "model_priority_fact_ids",
            "model_priority_task_codes",
            "priority_task_codes",
        },
        "orchestrator role artifact",
    )
    required_tasks = {
        "source_integrity",
        "process_decisions",
        "evidence_gaps",
        "final_brief",
    }
    if (
        plan.get("contribution_type") != "constrained_focus_prioritization"
        or set(plan.get("priority_task_codes", ())) != required_tasks
        or set(plan.get("model_priority_task_codes", ())) != required_tasks
        or not isinstance(plan.get("deterministic_coverage"), dict)
    ):
        raise ClaimLoopCycleError("orchestrator role artifact values are invalid")

    source = _closed_mapping(
        value.document_source_integrity,
        {"artifacts"},
        "source-integrity role artifact",
    )
    _unique_mapping_rows(
        source.get("artifacts"),
        keys={
            "artifact_id",
            "attribution",
            "confidence_basis_points",
            "deterministic_fallback_applied",
            "integrity_class",
            "source_ref_ids",
        },
        identity="artifact_id",
        label="source-integrity artifact",
    )

    process = _closed_mapping(
        value.process_decision_mapping,
        {"decisions"},
        "process-decision role artifact",
    )
    _unique_mapping_rows(
        process.get("decisions"),
        keys={
            "attribution",
            "confidence_basis_points",
            "contribution_id",
            "contribution_scope",
            "decision_key",
            "decision_value",
            "deterministic_fallback_applied",
            "fact_id",
            "model_owned_fields",
            "normalized_value",
            "source_ref_ids",
            "state",
        },
        identity="fact_id",
        label="process-decision artifact",
    )

    evidence = _closed_mapping(
        value.evidence_checklist,
        {"items"},
        "evidence role artifact",
    )
    evidence_rows = _unique_mapping_rows(
        evidence.get("items"),
        keys={
            "artifact_ids",
            "attribution",
            "confidence_basis_points",
            "deterministic_fallback_applied",
            "field_contributions",
            "item_id",
            "model_owned_fields",
            "source_ref_ids",
            "status",
        },
        identity="item_id",
        label="evidence artifact",
    )
    for row in evidence_rows:
        _unique_mapping_rows(
            row.get("field_contributions"),
            keys={
                "attribution",
                "confidence_basis_points",
                "contribution_id",
                "deterministic_fallback_applied",
                "field",
            },
            identity="contribution_id",
            label="evidence field contribution",
        )

    final = _closed_mapping(
        value.final_claim_brief_audit,
        {
            "attribution",
            "audit_check_ids",
            "confidence_basis_points",
            "contribution_scope",
            "current_node_id",
            "deterministic_fallback_applied",
            "field_contributions",
            "input_contribution_ids",
            "lineage_authority",
            "next_action_node_id",
            "source_ref_ids",
            "supporting_fact_ids",
            "upstream_contribution_ids",
        },
        "final-brief role artifact",
    )
    _unique_mapping_rows(
        final.get("field_contributions"),
        keys={
            "attribution",
            "confidence_basis_points",
            "contribution_id",
            "deterministic_fallback_applied",
            "field",
        },
        identity="contribution_id",
        label="final-brief field contribution",
    )
    if (
        final.get("contribution_scope")
        != "independent_final_claim_brief_audit"
        or set(final.get("input_contribution_ids", ()))
        != {
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
        }
    ):
        raise ClaimLoopCycleError("final-brief role artifact values are invalid")


def build_accepted_cycle_artifacts_v1(
    *,
    facts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    final_claim_brief: Mapping[str, Any],
    verification: Mapping[str, Any],
    graph_audit: Mapping[str, Any],
) -> AcceptedCycleArtifactsV1:
    role_artifacts = build_accepted_role_artifacts_v1(
        facts=facts,
        graph_audit=graph_audit,
    )
    payload = {
        "contract": "casepath.accepted-cycle-artifacts/1.0.0",
        "facts": [dict(value) for value in facts],
        "process": dict(process),
        "checklist": dict(checklist),
        "final_claim_brief": dict(final_claim_brief),
        "verification": dict(verification),
        "role_artifacts": role_artifacts.model_dump(mode="json"),
    }
    return AcceptedCycleArtifactsV1.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )


def build_accepted_role_artifacts_v1(
    *,
    facts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    graph_audit: Mapping[str, Any],
) -> AcceptedRoleArtifactsV1:
    specialist_artifacts = graph_audit.get("specialist_artifacts")
    expected_specialists = {
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
        "final_claim_brief_audit",
    }
    if not isinstance(specialist_artifacts, Mapping) or set(
        specialist_artifacts
    ) != expected_specialists:
        raise ClaimLoopCycleError("cycle specialist artifact roster is invalid")
    if any(
        not isinstance(specialist_artifacts[key], Mapping)
        for key in expected_specialists
    ):
        raise ClaimLoopCycleError("cycle specialist artifact is invalid")
    payload = {
        "contract": "casepath.accepted-role-artifacts/1.0.0",
        "canonical_facts": [dict(value) for value in facts],
        **{
            key: dict(specialist_artifacts[key])
            for key in sorted(expected_specialists)
        },
    }
    return AcceptedRoleArtifactsV1.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )


def validate_accepted_role_artifacts_v1(
    *,
    accepted_cycle_artifacts: AcceptedCycleArtifactsV1,
    graph_audit: Mapping[str, Any],
) -> None:
    agents = _indexed_receipts(
        graph_audit.get("agents"), expected_ids=AI_AGENT_IDS, label="agent"
    )
    roles = accepted_cycle_artifacts.role_artifacts
    _validate_role_artifact_shapes(roles)
    role_artifact_by_id = {
        "canonical_facts": list(roles.canonical_facts),
        "orchestrator_plan": roles.orchestrator_plan,
        "document_source_integrity": roles.document_source_integrity,
        "process_decision_mapping": roles.process_decision_mapping,
        "evidence_checklist": roles.evidence_checklist,
        "final_claim_brief_audit": roles.final_claim_brief_audit,
    }
    if (
        roles.canonical_facts != accepted_cycle_artifacts.facts
        or roles.final_claim_brief_audit
        != accepted_cycle_artifacts.final_claim_brief
        or any(
            agent.get("output_artifact_hash")
            != digest_value(role_artifact_by_id[agent["agent_id"]])
            for agent in agents
        )
    ):
        raise ClaimLoopCycleError(
            "cycle agent outputs do not bind accepted role artifacts"
        )


def _indexed_receipts(
    values: Any, *, expected_ids: tuple[str, ...], label: str
) -> tuple[dict[str, Any], ...]:
    if not isinstance(values, list):
        raise ClaimLoopCycleError(f"{label} roster is missing")
    by_id: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("agent_id"), str):
            raise ClaimLoopCycleError(f"{label} receipt is invalid")
        if value["agent_id"] in by_id:
            raise ClaimLoopCycleError(f"{label} roster contains a duplicate")
        by_id[value["agent_id"]] = value
    if set(by_id) != set(expected_ids):
        raise ClaimLoopCycleError(f"{label} roster differs from the StateGraph")
    return tuple(by_id[value] for value in expected_ids)


def derive_graph_activity_v1(
    graph_audit: Mapping[str, Any],
) -> tuple[int, Literal["exact", "unknown"], float | None]:
    """Derive provider activity from a complete graph audit without defaults."""

    audit = dict(graph_audit)
    audit_transport = audit.get("transport_mode")
    if audit_transport not in {"openrouter", "deterministic_test_double"}:
        raise ClaimLoopCycleError("cycle audit transport identity is invalid")
    expected_model_assisted = audit_transport == "openrouter"
    if audit.get("model_assisted") is not expected_model_assisted:
        raise ClaimLoopCycleError("cycle audit model-assistance identity is invalid")
    agents = _indexed_receipts(
        audit.get("agents"), expected_ids=AI_AGENT_IDS, label="agent"
    )
    calls = 0
    cost = 0.0
    cost_complete = True
    for agent in agents:
        if "call_count" not in agent:
            raise ClaimLoopCycleError("cycle agent call count is missing")
        call_count = agent["call_count"]
        if (
            not isinstance(call_count, int)
            or isinstance(call_count, bool)
            or call_count < 0
        ):
            raise ClaimLoopCycleError("cycle agent call count is invalid")
        if audit_transport == "openrouter":
            if (
                agent.get("actor_type") != "nemotron_agent"
                or agent.get("transport_mode") != "openrouter"
                or not isinstance(agent.get("model"), str)
                or not agent["model"]
                or not isinstance(agent.get("provider"), str)
                or not agent["provider"]
            ):
                raise ClaimLoopCycleError(
                    "model-assisted cycle agent provenance is incomplete"
                )
            if call_count == 0 and (
                agent.get("cache_hit") is not True
                or agent.get("outcome") != "cache_hit"
                or agent.get("usage_source") != "cache"
                or not isinstance(agent.get("call_id"), str)
                or not agent["call_id"]
                or not isinstance(agent.get("origin_call_id"), str)
                or not agent["origin_call_id"]
                or agent["origin_call_id"] == agent["call_id"]
            ):
                raise ClaimLoopCycleError(
                    "zero-call model activity lacks immutable cache provenance"
                )
        elif (
            agent.get("actor_type") != "deterministic_structured_agent"
            or agent.get("transport_mode") != "deterministic_test_double"
            or agent.get("model") is not None
            or agent.get("provider") is not None
            or call_count != 0
        ):
            raise ClaimLoopCycleError(
                "deterministic cycle agent provenance is inconsistent"
            )
        calls += call_count
        if call_count == 0:
            continue
        usage = agent.get("usage")
        if not isinstance(usage, Mapping):
            cost_complete = False
            continue
        actual_cost_usd = usage.get("actual_cost_usd")
        if (
            not isinstance(actual_cost_usd, (int, float))
            or isinstance(actual_cost_usd, bool)
            or not math.isfinite(float(actual_cost_usd))
            or float(actual_cost_usd) < 0.0
        ):
            cost_complete = False
            continue
        cost += float(actual_cost_usd)
    return (
        calls,
        "exact" if cost_complete else "unknown",
        round(cost, 8) if cost_complete else None,
    )


def validate_cycle_receipt_graph_binding_v1(
    *, receipt: SixAgentCycleReceipt, graph_audit: Mapping[str, Any]
) -> None:
    """Recompute every receipt activity/role binding from the persisted audit."""

    audit = dict(graph_audit)
    agents = _indexed_receipts(
        audit.get("agents"), expected_ids=AI_AGENT_IDS, label="agent"
    )
    gates = _indexed_receipts(
        audit.get("deterministic_gates"),
        expected_ids=DETERMINISTIC_GATE_IDS,
        label="gate",
    )
    calls, cost_status, cost_usd = derive_graph_activity_v1(audit)
    audit_transport = audit.get("transport_mode")
    if receipt.transport_mode == "accepted_source_run":
        if receipt.cycle_kind != "source_acceptance":
            raise ClaimLoopCycleError(
                "accepted source transport is restricted to source acceptance"
            )
    elif receipt.transport_mode != audit_transport:
        raise ClaimLoopCycleError(
            "cycle receipt transport differs from its persisted graph audit"
        )
    final_claim_brief = audit.get("final_claim_brief")
    topology = audit.get("execution_topology")
    if (
        receipt.graph_audit_sha256 != digest_value(audit)
        or receipt.orchestration_id != audit.get("orchestration_id")
        or not isinstance(topology, Mapping)
        or topology.get("implementation") != receipt.execution_implementation
        or receipt.agent_receipt_sha256s
        != tuple(digest_value(value) for value in agents)
        or receipt.gate_receipt_sha256s
        != tuple(digest_value(value) for value in gates)
        or not isinstance(final_claim_brief, Mapping)
        or receipt.final_claim_brief_sha256
        != digest_value(dict(final_claim_brief))
        or gates[-1].get("final_brief_artifact_hash")
        != receipt.final_claim_brief_sha256
        or receipt.model_calls != calls
        or receipt.provider_calls != calls
        or receipt.cost_status != cost_status
        or receipt.cost_usd != cost_usd
    ):
        raise ClaimLoopCycleError(
            "cycle receipt differs from its persisted graph audit"
        )


def build_six_agent_cycle_receipt_v1(
    *,
    source_run_id: str,
    loop_id: str,
    cycle_kind: Literal["source_acceptance", "observation", "correction"],
    prior_state_sha256: str | None,
    trigger_sha256: str,
    orchestration_id: str,
    playbook_template_sha256: str,
    observable_package: Mapping[str, Any],
    facts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    verification: Mapping[str, Any],
    graph_audit: Mapping[str, Any],
    accepted_cycle_artifacts: AcceptedCycleArtifactsV1 | Mapping[str, Any] | None = None,
    transport_mode: Literal[
        "accepted_source_run", "openrouter", "deterministic_test_double"
    ],
    model_calls: int,
    provider_calls: int,
    credential_access_status: Literal[
        "none_due_to_zero_provider_calls", "not_measured", "receipt_bound"
    ],
    credential_access_receipt_sha256s: tuple[str, ...],
    cost_status: Literal["exact", "unknown"],
    cost_usd: float | None,
) -> SixAgentCycleReceipt:
    """Bind one actual compiled-StateGraph traversal to exact loop inputs."""

    audit = dict(graph_audit)
    topology = audit.get("execution_topology")
    if (
        audit.get("all_required_agents_contributed") is not True
        or not isinstance(topology, Mapping)
        or topology.get("implementation") != "compiled_langgraph_stategraph"
        or audit.get("orchestration_id") != orchestration_id
    ):
        raise ClaimLoopCycleError("cycle audit is not an accepted compiled StateGraph run")
    agents = _indexed_receipts(
        audit.get("agents"), expected_ids=AI_AGENT_IDS, label="agent"
    )
    gates = _indexed_receipts(
        audit.get("deterministic_gates"),
        expected_ids=DETERMINISTIC_GATE_IDS,
        label="gate",
    )
    final_claim_brief = audit.get("final_claim_brief")
    if not isinstance(final_claim_brief, Mapping):
        raise ClaimLoopCycleError("cycle audit has no accepted final brief")
    if accepted_cycle_artifacts is None:
        accepted_cycle = build_accepted_cycle_artifacts_v1(
            facts=facts,
            process=process,
            checklist=checklist,
            final_claim_brief=final_claim_brief,
            verification=verification,
            graph_audit=audit,
        )
    else:
        try:
            accepted_cycle = AcceptedCycleArtifactsV1.model_validate(
                accepted_cycle_artifacts.model_dump(mode="json")
                if isinstance(accepted_cycle_artifacts, AcceptedCycleArtifactsV1)
                else dict(accepted_cycle_artifacts)
            )
        except (TypeError, ValueError) as exc:
            raise ClaimLoopCycleError("accepted cycle artifacts are invalid") from exc
    if (
        list(accepted_cycle.facts) != list(facts)
        or accepted_cycle.process != dict(process)
        or accepted_cycle.checklist != dict(checklist)
        or accepted_cycle.verification != dict(verification)
        or accepted_cycle.final_claim_brief != dict(final_claim_brief)
        or accepted_cycle.role_artifacts.canonical_facts
        != tuple(dict(value) for value in facts)
        or accepted_cycle.role_artifacts.final_claim_brief_audit
        != dict(final_claim_brief)
    ):
        raise ClaimLoopCycleError("accepted cycle artifacts differ from graph outputs")
    audit_transport = audit.get("transport_mode")
    if audit_transport not in {"openrouter", "deterministic_test_double"}:
        raise ClaimLoopCycleError("cycle audit transport identity is invalid")
    expected_actor_type = (
        "deterministic_structured_agent"
        if audit_transport == "deterministic_test_double"
        else "nemotron_agent"
    )
    if any(value.get("actor_type") != expected_actor_type for value in agents):
        raise ClaimLoopCycleError("cycle agent transport label is inaccurate")
    if audit_transport == "deterministic_test_double" and (
        audit.get("model_assisted") is not False
        or audit.get("model") is not None
    ):
        raise ClaimLoopCycleError("deterministic cycle audit claims a model")
    if audit_transport == "openrouter" and audit.get("model_assisted") is not True:
        raise ClaimLoopCycleError("model cycle audit omits model assistance")
    if audit_transport == "deterministic_test_double" and any(
        value.get("model") is not None
        or value.get("provider") is not None
        or value.get("call_count") != 0
        for value in agents
    ):
        raise ClaimLoopCycleError("deterministic cycle agent claims model activity")
    gate_by_id = {value["agent_id"]: value for value in gates}
    validate_accepted_role_artifacts_v1(
        accepted_cycle_artifacts=accepted_cycle,
        graph_audit=audit,
    )
    if (
        agents[0].get("output_artifact_hash")
        != digest_value(list(facts))
        or
        gate_by_id["deterministic_process_gate"].get("output_artifact_hash")
        != accepted_artifact_hash(process)
        or gate_by_id["deterministic_evidence_gate"].get("output_artifact_hash")
        != accepted_artifact_hash(checklist)
    ):
        raise ClaimLoopCycleError("cycle gates do not bind projected artifacts")
    whole_gate = gate_by_id["whole_playbook_gate"]
    if (
        whole_gate.get("final_brief_artifact_hash")
        != accepted_artifact_hash(final_claim_brief)
        or whole_gate.get("output_artifact_hash")
        != accepted_artifact_hash(
            {
                "process": dict(process),
                "checklist": dict(checklist),
                "final_brief": dict(final_claim_brief),
            }
        )
        or
        whole_gate.get("verification_report_hash")
        != accepted_artifact_hash(verification)
        or whole_gate.get("verification_whole_playbook_hash")
        != verification.get("whole_playbook_hash")
    ):
        raise ClaimLoopCycleError("cycle gate does not bind fresh verification")
    if transport_mode != "accepted_source_run" and audit.get(
        "transport_mode"
    ) != transport_mode:
        raise ClaimLoopCycleError("cycle audit transport identity changed")
    derived_calls, derived_cost_status, derived_cost_usd = (
        derive_graph_activity_v1(audit)
    )
    if (
        model_calls != derived_calls
        or provider_calls != derived_calls
        or cost_status != derived_cost_status
        or cost_usd != derived_cost_usd
    ):
        raise ClaimLoopCycleError("cycle activity differs from its graph audit")
    if transport_mode == "deterministic_test_double" and (
        model_calls != 0
        or provider_calls != 0
        or credential_access_status != "none_due_to_zero_provider_calls"
        or credential_access_receipt_sha256s
        or cost_status != "exact"
        or cost_usd != 0.0
    ):
        raise ClaimLoopCycleError("provider-free cycle reported external activity")
    payload = {
        "contract": "casepath.six-agent-cycle-receipt/1.0.0",
        "source_run_id": source_run_id,
        "loop_id": loop_id,
        "cycle_kind": cycle_kind,
        "prior_state_sha256": prior_state_sha256,
        "trigger_sha256": trigger_sha256,
        "orchestration_id": orchestration_id,
        "playbook_template_sha256": playbook_template_sha256,
        "observable_package_sha256": digest_value(dict(observable_package)),
        "facts_sha256": digest_value(list(facts)),
        "process_sha256": digest_value(dict(process)),
        "checklist_sha256": digest_value(dict(checklist)),
        "accepted_cycle_artifacts_sha256": accepted_cycle.receipt_sha256,
        "final_claim_brief_sha256": digest_value(dict(final_claim_brief)),
        "verification_sha256": digest_value(dict(verification)),
        "graph_audit_sha256": digest_value(audit),
        "agent_ids": list(AI_AGENT_IDS),
        "agent_receipt_sha256s": [digest_value(value) for value in agents],
        "deterministic_gate_ids": list(DETERMINISTIC_GATE_IDS),
        "gate_receipt_sha256s": [digest_value(value) for value in gates],
        "execution_implementation": "compiled_langgraph_stategraph",
        "transport_mode": transport_mode,
        "model_calls": model_calls,
        "provider_calls": provider_calls,
        "credential_access_status": credential_access_status,
        "credential_access_receipt_sha256s": list(
            credential_access_receipt_sha256s
        ),
        "cost_status": cost_status,
        "cost_usd": cost_usd,
    }
    receipt = SixAgentCycleReceipt.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )
    validate_cycle_receipt_graph_binding_v1(
        receipt=receipt, graph_audit=audit
    )
    return receipt


__all__ = [
    "ClaimLoopCycleError",
    "build_accepted_cycle_artifacts_v1",
    "build_accepted_role_artifacts_v1",
    "build_six_agent_cycle_receipt_v1",
    "derive_graph_activity_v1",
    "validate_cycle_receipt_graph_binding_v1",
    "validate_accepted_role_artifacts_v1",
]

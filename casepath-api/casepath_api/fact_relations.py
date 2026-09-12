from __future__ import annotations

from copy import deepcopy
from typing import Any


PROCESS_FACT_IDS_BY_CLAIM: dict[str, dict[str, list[str]]] = {
    "DEF-027-E0-DEMO": {
        "intake": [],
        "scope": ["fact_tenancy"],
        "dispute": ["fact_dispute"],
        "urgency": ["fact_health"],
        "notification": ["fact_notification"],
        "defect": ["fact_recurrence"],
        "causation": ["fact_cause", "fact_ventilation_allegation"],
        "responsibility": [],
        "remedy": [],
        "escalation": [],
        "resolution": [],
        "out_of_scope": [],
        "no_dispute": [],
        "urgent_escalation": [],
        "formal_notice": [],
        "building_defect": [],
        "tenant_use": [],
        "mixed_cause": [],
        "evidence_gap": [],
    },
    "DEMO-MOULD-002": {
        "intake": [],
        "scope": ["later_fact_tenancy"],
        "dispute": ["later_fact_dispute"],
        "urgency": ["later_fact_health"],
        "notification": ["later_fact_notification"],
        "defect": ["later_fact_recurrence", "later_fact_recent_window_work"],
        "causation": [
            "later_fact_cause",
            "later_fact_ventilation_allegation",
            "later_fact_recent_window_work",
        ],
        "responsibility": [],
        "remedy": [],
        "escalation": [],
        "resolution": [],
        "out_of_scope": [],
        "no_dispute": [],
        "urgent_escalation": [],
        "formal_notice": [],
        "building_defect": [],
        "tenant_use": [],
        "mixed_cause": [],
        "evidence_gap": [],
    },
}

EVIDENCE_FACT_ID_BY_CLAIM: dict[str, dict[str, str]] = {
    "DEF-027-E0-DEMO": {
        "claim_message": "fact_customer_objective",
        "source_integrity": "fact_source_integrity",
        "lease": "fact_tenancy",
        "policy_reference": "fact_policy_route",
        "customer_objective": "fact_customer_objective",
        "management_position": "fact_dispute",
        "health_safety_statement": "fact_health",
        "defect_notice": "fact_notification",
        "proof_of_delivery": "fact_notification",
        "dated_photos": "fact_recurrence",
        "recurrence_chronology": "fact_date_conflict",
        "technical_assessment": "fact_cause",
        "moisture_measurements": "fact_cause",
        "building_envelope": "fact_cause",
        "repair_history": "fact_repair_history",
        "use_evidence": "fact_tenant_use_cause",
        "remediation_plan": "fact_remedy_plan",
        "financial_impact": "fact_financial_remedy",
        "settlement_proposal": "fact_settlement_proposal",
        "conciliation_bundle": "fact_escalation_ready",
        "completion_record": "fact_resolution_complete",
    },
    "DEMO-MOULD-002": {
        "claim_message": "later_fact_customer_objective",
        "source_integrity": "later_fact_source_integrity",
        "lease": "later_fact_tenancy",
        "policy_reference": "later_fact_policy_route",
        "customer_objective": "later_fact_customer_objective",
        "management_position": "later_fact_dispute",
        "health_safety_statement": "later_fact_health",
        "defect_notice": "later_fact_notification",
        "proof_of_delivery": "later_fact_notification",
        "dated_photos": "later_fact_recurrence",
        "recurrence_chronology": "later_fact_recurrence",
        "repair_history": "later_fact_recent_window_work",
        "technical_assessment": "later_fact_cause",
        "moisture_measurements": "later_fact_cause",
        "building_envelope": "later_fact_cause",
        "use_evidence": "later_fact_ventilation_allegation",
        "remediation_plan": "later_fact_remedy_plan",
        "financial_impact": "later_fact_financial_remedy",
        "settlement_proposal": "later_fact_settlement_proposal",
        "conciliation_bundle": "later_fact_escalation_ready",
        "completion_record": "later_fact_resolution_complete",
    },
}

EVIDENCE_ARTIFACT_IDS_BY_CLAIM: dict[str, dict[str, list[str]]] = {
    "DEF-027-E0-DEMO": {
        "claim_message": ["message"],
        "source_integrity": [
            "art_lease",
            "art_notification",
            "art_management_reply",
            "art_photo",
            "art_timeline",
            "art_delivery",
        ],
        "lease": ["art_lease"],
        "policy_reference": ["intake"],
        "customer_objective": ["message"],
        "management_position": ["art_management_reply"],
        "health_safety_statement": ["message"],
        "defect_notice": ["art_notification"],
        "proof_of_delivery": ["art_delivery"],
        "dated_photos": ["art_photo"],
        "recurrence_chronology": ["art_timeline"],
        "technical_assessment": [],
        "moisture_measurements": [],
        "building_envelope": [],
        "repair_history": ["art_management_reply"],
        "use_evidence": [],
        "remediation_plan": [],
        "financial_impact": [],
        "settlement_proposal": [],
        "conciliation_bundle": [],
        "completion_record": [],
    },
    "DEMO-MOULD-002": {
        "claim_message": ["art_later_email"],
        "source_integrity": [
            "art_later_email",
            "art_later_photo",
            "art_window_notice",
            "art_later_lease",
            "art_later_notification",
            "art_later_management_reply",
        ],
        "lease": ["art_later_lease"],
        "policy_reference": ["intake"],
        "customer_objective": ["art_later_email"],
        "management_position": ["art_later_management_reply"],
        "health_safety_statement": ["art_later_email"],
        "defect_notice": ["art_later_notification"],
        "proof_of_delivery": ["art_later_management_reply"],
        "dated_photos": ["art_later_photo"],
        "recurrence_chronology": [
            "art_later_notification",
            "art_later_photo",
        ],
        "repair_history": ["art_window_notice"],
        "technical_assessment": [],
        "moisture_measurements": [],
        "building_envelope": [],
        "use_evidence": [],
        "remediation_plan": [],
        "financial_impact": [],
        "settlement_proposal": [],
        "conciliation_bundle": [],
        "completion_record": [],
    },
}

BASE_EVIDENCE_STATUS_BY_CLAIM: dict[str, dict[str, str]] = {
    "DEF-027-E0-DEMO": {
        "claim_message": "provided_sufficient",
        "source_integrity": "provided_sufficient",
        "lease": "provided_sufficient",
        "policy_reference": "provided_sufficient",
        "customer_objective": "provided_sufficient",
        "management_position": "provided_sufficient",
        "health_safety_statement": "provided_sufficient",
        "defect_notice": "provided_sufficient",
        "proof_of_delivery": "provided_sufficient",
        "dated_photos": "provided_sufficient",
        "recurrence_chronology": "provided_insufficient",
        "technical_assessment": "missing",
        "moisture_measurements": "conditional",
        "building_envelope": "conditional",
        "repair_history": "conditional",
        "use_evidence": "not_applicable",
        "remediation_plan": "not_applicable",
        "financial_impact": "conditional",
        "settlement_proposal": "conditional",
        "conciliation_bundle": "conditional",
        "completion_record": "not_applicable",
    },
    "DEMO-MOULD-002": {
        "claim_message": "provided_sufficient",
        "source_integrity": "provided_sufficient",
        "lease": "provided_sufficient",
        "policy_reference": "provided_sufficient",
        "customer_objective": "provided_sufficient",
        "management_position": "provided_sufficient",
        "health_safety_statement": "provided_sufficient",
        "defect_notice": "provided_sufficient",
        "proof_of_delivery": "provided_sufficient",
        "dated_photos": "provided_sufficient",
        "recurrence_chronology": "provided_insufficient",
        "repair_history": "provided_sufficient",
        "technical_assessment": "missing",
        "moisture_measurements": "conditional",
        "building_envelope": "missing",
        "use_evidence": "conditional",
        "remediation_plan": "not_applicable",
        "financial_impact": "conditional",
        "settlement_proposal": "conditional",
        "conciliation_bundle": "conditional",
        "completion_record": "not_applicable",
    },
}


def expected_evidence_status_variants(
    claim_id: str, *, include_governed_extension: bool
) -> list[dict[str, str]]:
    try:
        base = deepcopy(BASE_EVIDENCE_STATUS_BY_CLAIM[claim_id])
    except KeyError as exc:
        raise ValueError("unknown_claim_fact_contract") from exc
    if not include_governed_extension:
        return [base]
    conditional = deepcopy(base)
    conditional["building_envelope"] = "conditional"
    conditional["use_evidence"] = "conditional"
    if claim_id == "DEMO-MOULD-002":
        return [conditional]
    required_now = deepcopy(conditional)
    required_now["building_envelope"] = "missing"
    return [conditional, required_now]

SEMANTIC_FACT_ID_BY_CLAIM: dict[str, dict[str, str]] = {
    "DEF-027-E0-DEMO": {
        "management_ventilation_allegation": "fact_ventilation_allegation"
    },
    "DEMO-MOULD-002": {
        "management_ventilation_allegation": "later_fact_ventilation_allegation"
    },
}


def expected_process_fact_ids(
    claim_id: str, *, include_memory_extension: bool = False
) -> dict[str, list[str]]:
    try:
        result = deepcopy(PROCESS_FACT_IDS_BY_CLAIM[claim_id])
        if include_memory_extension:
            result["ventilation_dispute"] = [
                SEMANTIC_FACT_ID_BY_CLAIM[claim_id][
                    "management_ventilation_allegation"
                ]
            ]
        return result
    except KeyError as exc:
        raise ValueError("unknown_claim_fact_contract") from exc


def validate_fact_relations(
    *,
    claim_id: str,
    facts: list[dict[str, Any]],
    process: dict[str, Any],
    checklist: dict[str, Any],
    include_memory_extension: bool,
    allowed_artifact_extensions_by_item: dict[str, set[str]] | None = None,
) -> None:
    try:
        expected_process = expected_process_fact_ids(
            claim_id, include_memory_extension=include_memory_extension
        )
        expected_evidence = EVIDENCE_FACT_ID_BY_CLAIM[claim_id]
        expected_artifacts = EVIDENCE_ARTIFACT_IDS_BY_CLAIM[claim_id]
        expected_roles = SEMANTIC_FACT_ID_BY_CLAIM[claim_id]
    except KeyError as exc:
        raise ValueError("unknown_claim_fact_contract") from exc

    actual_process = {
        node.get("node_id"): node.get("fact_ids") for node in process.get("nodes", [])
    }
    actual_evidence = {
        item.get("item_id"): item.get("fact_id")
        for item in checklist.get("items", [])
    }
    actual_artifacts = {
        item.get("item_id"): item.get("artifact_ids")
        for item in checklist.get("items", [])
    }
    actual_roles = {
        fact.get("semantic_role"): fact.get("fact_id")
        for fact in facts
        if fact.get("semantic_role") is not None
    }
    if actual_process != expected_process:
        raise ValueError("process_fact_relationship")
    if actual_evidence != expected_evidence:
        raise ValueError("evidence_fact_relationship")
    # These maps define the bounded semantic artifact domain for each item, not
    # an answer key. The evidence gate may retain any coherent subset and status;
    # validate_evidence_model owns those dynamic status/artifact invariants.
    allowed_extensions = allowed_artifact_extensions_by_item or {}
    if set(allowed_extensions) - set(expected_artifacts):
        raise ValueError("evidence_artifact_extension_item")
    if set(actual_artifacts) != set(expected_artifacts) or any(
        not isinstance(actual_artifacts[item_id], list)
        or set(actual_artifacts[item_id])
        - set(expected_artifacts[item_id])
        - set(allowed_extensions.get(item_id, set()))
        for item_id in expected_artifacts
    ):
        raise ValueError("evidence_artifact_relationship")
    if actual_roles != expected_roles:
        raise ValueError("semantic_fact_relationship")

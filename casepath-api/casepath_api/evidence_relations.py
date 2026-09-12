from __future__ import annotations

from typing import Any


class EvidenceRelationError(ValueError):
    """Raised when process requirements and checklist ownership diverge."""


EVIDENCE_ITEM_IDS_BY_CLAIM: dict[str, tuple[str, ...]] = {
    "DEF-027-E0-DEMO": (
        "claim_message",
        "source_integrity",
        "lease",
        "policy_reference",
        "customer_objective",
        "management_position",
        "health_safety_statement",
        "defect_notice",
        "proof_of_delivery",
        "dated_photos",
        "recurrence_chronology",
        "technical_assessment",
        "moisture_measurements",
        "building_envelope",
        "repair_history",
        "use_evidence",
        "remediation_plan",
        "financial_impact",
        "settlement_proposal",
        "conciliation_bundle",
        "completion_record",
    ),
    "DEMO-MOULD-002": (
        "claim_message",
        "source_integrity",
        "lease",
        "policy_reference",
        "customer_objective",
        "management_position",
        "health_safety_statement",
        "defect_notice",
        "proof_of_delivery",
        "dated_photos",
        "recurrence_chronology",
        "repair_history",
        "technical_assessment",
        "moisture_measurements",
        "building_envelope",
        "use_evidence",
        "remediation_plan",
        "financial_impact",
        "settlement_proposal",
        "conciliation_bundle",
        "completion_record",
    ),
}


BASE_EVIDENCE_NODE_IDS: dict[str, tuple[str, ...]] = {
    "claim_message": ("intake",),
    "source_integrity": ("intake",),
    "lease": ("scope",),
    "policy_reference": ("scope",),
    "customer_objective": ("dispute",),
    "management_position": ("dispute",),
    "health_safety_statement": ("urgency",),
    "defect_notice": ("notification", "formal_notice"),
    "proof_of_delivery": ("notification", "formal_notice"),
    "dated_photos": ("defect",),
    "recurrence_chronology": ("defect",),
    "technical_assessment": (
        "causation",
        "responsibility",
        "building_defect",
        "tenant_use",
        "mixed_cause",
        "evidence_gap",
    ),
    "moisture_measurements": ("causation", "evidence_gap"),
    "building_envelope": (
        "causation",
        "building_defect",
        "mixed_cause",
        "evidence_gap",
    ),
    "repair_history": ("responsibility",),
    "use_evidence": ("causation", "tenant_use", "mixed_cause"),
    "remediation_plan": ("remedy", "building_defect"),
    "financial_impact": ("remedy",),
    "settlement_proposal": ("remedy", "mixed_cause"),
    "conciliation_bundle": ("escalation",),
    "completion_record": ("resolution",),
}


def validate_evidence_item_order(
    claim_id: str,
    items: list[dict[str, Any]],
) -> None:
    """Fail closed when a governed claim changes its public checklist order."""

    expected = EVIDENCE_ITEM_IDS_BY_CLAIM.get(claim_id)
    actual = tuple(item.get("item_id") for item in items)
    if expected is None or actual != expected:
        raise EvidenceRelationError(
            f"evidence item order does not match governed claim {claim_id!r}"
        )

BASE_PROCESS_NODE_IDS = (
    "intake",
    "scope",
    "dispute",
    "urgency",
    "notification",
    "defect",
    "causation",
    "responsibility",
    "remedy",
    "escalation",
    "resolution",
    "out_of_scope",
    "no_dispute",
    "urgent_escalation",
    "formal_notice",
    "building_defect",
    "tenant_use",
    "mixed_cause",
    "evidence_gap",
)

BASE_PROCESS_EDGE_PAIRS = (
    ("intake", "scope"),
    ("scope", "dispute"),
    ("scope", "out_of_scope"),
    ("dispute", "urgency"),
    ("dispute", "no_dispute"),
    ("urgency", "urgent_escalation"),
    ("urgency", "notification"),
    ("notification", "defect"),
    ("notification", "formal_notice"),
    ("defect", "causation"),
    ("causation", "building_defect"),
    ("causation", "tenant_use"),
    ("causation", "mixed_cause"),
    ("causation", "evidence_gap"),
    ("evidence_gap", "causation"),
    ("building_defect", "responsibility"),
    ("tenant_use", "responsibility"),
    ("mixed_cause", "responsibility"),
    ("responsibility", "remedy"),
    ("remedy", "resolution"),
    ("remedy", "escalation"),
    ("escalation", "resolution"),
)

MEMORY_EXTENSION_NODE_IDS = frozenset({"ventilation_dispute"})
MEMORY_EXTENSION_EDGE_PAIRS = frozenset(
    {
        ("evidence_gap", "ventilation_dispute"),
        ("ventilation_dispute", "causation"),
    }
)


def authoritative_evidence_node_ids(
    process: dict[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Return the only evidence-ownership topology accepted by this release."""

    expected = dict(BASE_EVIDENCE_NODE_IDS)
    node_ids = {node.get("node_id") for node in process.get("nodes", [])}
    if "ventilation_dispute" in node_ids:
        expected["management_position"] = (
            "dispute",
            "ventilation_dispute",
        )
        expected["use_evidence"] = ("ventilation_dispute",)
    return expected


def derive_evidence_relations(
    process: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Derive every checklist item's process ownership from the graph.

    Process nodes are the single authority for requirement membership. The
    returned order follows process-node order, making the first node a stable
    display primary while retaining every branch that consumes the item.
    """

    item_ids = [item.get("item_id") for item in items]
    if any(not isinstance(item_id, str) or not item_id for item_id in item_ids):
        raise EvidenceRelationError("evidence item IDs must be non-empty strings")
    if len(item_ids) != len(set(item_ids)):
        raise EvidenceRelationError("evidence item IDs must be unique")
    item_id_set = set(item_ids)
    node_ids: list[str] = []
    requirements_by_item: dict[str, list[str]] = {
        item_id: [] for item_id in item_ids
    }
    for node in process.get("nodes", []):
        node_id = node.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise EvidenceRelationError("process node IDs must be non-empty strings")
        if node_id in node_ids:
            raise EvidenceRelationError("process node IDs must be unique")
        node_ids.append(node_id)
        requirement_ids = node.get("evidence_requirement_ids")
        if not isinstance(requirement_ids, list):
            raise EvidenceRelationError(
                f"process node {node_id!r} evidence requirements must be a list"
            )
        if len(requirement_ids) != len(set(requirement_ids)):
            raise EvidenceRelationError(
                f"process node {node_id!r} has duplicate evidence requirements"
            )
        unknown = [item_id for item_id in requirement_ids if item_id not in item_id_set]
        if unknown:
            raise EvidenceRelationError(
                f"process node {node_id!r} references unknown evidence items"
            )
        for item_id in requirement_ids:
            requirements_by_item[item_id].append(node_id)

    unowned = [item_id for item_id, owners in requirements_by_item.items() if not owners]
    if unowned:
        raise EvidenceRelationError("every evidence item must belong to a process node")

    selected_path = process.get("selected_path")
    if not isinstance(selected_path, list):
        raise EvidenceRelationError("process selected path must be a list")
    unknown_path_nodes = set(selected_path) - set(node_ids)
    if unknown_path_nodes:
        raise EvidenceRelationError("process selected path contains an unknown node")
    active_nodes = set(selected_path)
    overlay = process.get("current_overlay")
    if not isinstance(overlay, dict):
        raise EvidenceRelationError("process current overlay must be an object")
    next_action = overlay.get("next_action_node_id")
    if not isinstance(next_action, str) or not next_action:
        raise EvidenceRelationError("process next action must be a non-empty node ID")
    if next_action not in node_ids:
        raise EvidenceRelationError("process next action is not a declared node")
    active_nodes.add(next_action)

    return {
        item_id: {
            "node_ids": owners,
            "node_id": owners[0],
            "current_path": bool(active_nodes.intersection(owners)),
        }
        for item_id, owners in requirements_by_item.items()
    }


def apply_evidence_relations(
    process: dict[str, Any],
    items: list[dict[str, Any]],
) -> None:
    relations = derive_evidence_relations(process, items)
    for item in items:
        item.update(relations[item["item_id"]])


def validate_evidence_relations(
    process: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    allowed_extension_node_ids: set[str] | None = None,
    enforce_release_topology: bool = False,
) -> None:
    expected = derive_evidence_relations(process, items)
    if not enforce_release_topology:
        for item in items:
            actual = {
                "node_ids": item.get("node_ids"),
                "node_id": item.get("node_id"),
                "current_path": item.get("current_path"),
            }
            if actual != expected[item["item_id"]]:
                raise EvidenceRelationError(
                    f"evidence item {item['item_id']!r} does not match process requirements"
                )
        return
    extension_node_ids = allowed_extension_node_ids or set()
    if "ventilation_dispute" in {
        node.get("node_id") for node in process.get("nodes", [])
    } and "ventilation_dispute" not in extension_node_ids:
        raise EvidenceRelationError(
            "the ventilation evidence topology requires an explicit extension boundary"
        )
    authoritative = authoritative_evidence_node_ids(process)
    if set(expected) != set(authoritative):
        raise EvidenceRelationError(
            "evidence item membership does not match the release topology"
        )
    for item in items:
        if tuple(expected[item["item_id"]]["node_ids"]) != authoritative[
            item["item_id"]
        ]:
            raise EvidenceRelationError(
                f"evidence item {item['item_id']!r} is assigned to the wrong process role"
            )
        actual = {
            "node_ids": item.get("node_ids"),
            "node_id": item.get("node_id"),
            "current_path": item.get("current_path"),
        }
        if actual != expected[item["item_id"]]:
            raise EvidenceRelationError(
                f"evidence item {item['item_id']!r} does not match process requirements"
            )


__all__ = [
    "BASE_EVIDENCE_NODE_IDS",
    "BASE_PROCESS_EDGE_PAIRS",
    "BASE_PROCESS_NODE_IDS",
    "EVIDENCE_ITEM_IDS_BY_CLAIM",
    "EvidenceRelationError",
    "apply_evidence_relations",
    "authoritative_evidence_node_ids",
    "derive_evidence_relations",
    "validate_evidence_item_order",
    "validate_evidence_relations",
]

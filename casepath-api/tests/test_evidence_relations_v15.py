from __future__ import annotations

from copy import deepcopy

import pytest

from casepath_api.evidence_relations import (
    EVIDENCE_ITEM_IDS_BY_CLAIM,
    EvidenceRelationError,
    apply_evidence_relations,
    derive_evidence_relations,
    validate_evidence_item_order,
    validate_evidence_relations,
)


def process() -> dict:
    return {
        "nodes": [
            {"node_id": "intake", "evidence_requirement_ids": ["message"]},
            {
                "node_id": "causation",
                "evidence_requirement_ids": ["assessment", "envelope"],
            },
            {
                "node_id": "evidence_gap",
                "evidence_requirement_ids": ["assessment", "envelope"],
            },
            {
                "node_id": "tenant_use",
                "evidence_requirement_ids": ["assessment", "use_evidence"],
            },
        ],
        "selected_path": ["intake", "causation", "evidence_gap"],
        "current_overlay": {"next_action_node_id": "evidence_gap"},
    }


def items() -> list[dict]:
    return [
        {"item_id": "message"},
        {"item_id": "assessment"},
        {"item_id": "envelope"},
        {"item_id": "use_evidence"},
    ]


def test_relations_preserve_all_consuming_nodes_and_recompute_path_membership():
    value = derive_evidence_relations(process(), items())
    assert value == {
        "message": {
            "node_ids": ["intake"],
            "node_id": "intake",
            "current_path": True,
        },
        "assessment": {
            "node_ids": ["causation", "evidence_gap", "tenant_use"],
            "node_id": "causation",
            "current_path": True,
        },
        "envelope": {
            "node_ids": ["causation", "evidence_gap"],
            "node_id": "causation",
            "current_path": True,
        },
        "use_evidence": {
            "node_ids": ["tenant_use"],
            "node_id": "tenant_use",
            "current_path": False,
        },
    }


def test_apply_then_validate_is_reciprocal():
    values = items()
    apply_evidence_relations(process(), values)
    validate_evidence_relations(process(), values)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("node_ids", ["tenant_use"]),
        ("node_id", "tenant_use"),
        ("current_path", False),
    ],
)
def test_existing_but_wrong_node_or_path_value_fails_closed(
    field: str,
    replacement,
):
    values = items()
    apply_evidence_relations(process(), values)
    assessment = next(item for item in values if item["item_id"] == "assessment")
    assessment[field] = replacement
    with pytest.raises(EvidenceRelationError, match="does not match process requirements"):
        validate_evidence_relations(process(), values)


def test_missing_reverse_requirement_fails_closed():
    graph = process()
    values = items()
    apply_evidence_relations(graph, values)
    tampered = deepcopy(graph)
    next(
        node for node in tampered["nodes"] if node["node_id"] == "evidence_gap"
    )["evidence_requirement_ids"].remove("assessment")
    with pytest.raises(EvidenceRelationError, match="does not match process requirements"):
        validate_evidence_relations(tampered, values)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda graph: graph["nodes"][0]["evidence_requirement_ids"].append(
            "unknown"
        ),
        lambda graph: graph["nodes"][0]["evidence_requirement_ids"].append(
            "message"
        ),
        lambda graph: graph["nodes"].append(
            {"node_id": "intake", "evidence_requirement_ids": []}
        ),
        lambda graph: graph["selected_path"].append("unknown"),
    ],
)
def test_invalid_process_requirement_authority_fails_closed(mutator):
    graph = process()
    mutator(graph)
    with pytest.raises(EvidenceRelationError):
        derive_evidence_relations(graph, items())


def test_unowned_item_fails_closed():
    values = items() + [{"item_id": "orphan"}]
    with pytest.raises(EvidenceRelationError, match="every evidence item"):
        derive_evidence_relations(process(), values)


def test_governed_checklist_order_is_claim_specific_and_fail_closed():
    for claim_id, item_ids in EVIDENCE_ITEM_IDS_BY_CLAIM.items():
        values = [{"item_id": item_id} for item_id in item_ids]
        validate_evidence_item_order(claim_id, values)
        values[-1], values[-2] = values[-2], values[-1]
        with pytest.raises(EvidenceRelationError, match="evidence item order"):
            validate_evidence_item_order(claim_id, values)

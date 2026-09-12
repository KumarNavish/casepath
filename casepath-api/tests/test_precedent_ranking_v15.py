from __future__ import annotations

from copy import deepcopy

import pytest

from casepath_api.precedent_ranking import (
    PRECEDENT_CORPUS_VERSION,
    PRECEDENT_RANKING_CONTRACT,
    rank_precedents,
)


def understanding(*, category: str = "Rental defect - mould and moisture") -> dict:
    return {
        "category": category,
        "subcategory": "Recurring moisture with disputed causation",
        "facts": [
            {"fact_id": "fact_cause", "state": "unknown"},
            {"fact_id": "fact_date_conflict", "state": "conflicting"},
        ],
    }


def process(*, current: str = "causation") -> dict:
    return {
        "current_overlay": {
            "current_node_id": current,
            "next_action_node_id": "evidence_gap",
        },
        "selected_path": ["intake", "scope", "causation", "evidence_gap"],
    }


def checklist(*, include_assessment: bool = True) -> dict:
    return {
        "items": [
            {
                "item_id": "technical_assessment",
                "current_path": include_assessment,
                "status": "missing",
            },
            {
                "item_id": "lease",
                "current_path": True,
                "status": "provided_sufficient",
            },
        ]
    }


def corpus() -> list[dict]:
    return [
        {
            "claim_id": "HIST-CAUSE",
            "title": "Causation assessment pattern",
            "review_status": "generated_reference",
            "provenance": "generated_reference_not_qualified_review",
            "why_useful": "Matches causation and technical assessment.",
            "ranking_categories": ["Rental defect - mould and moisture"],
            "ranking_process_node_ids": ["causation", "evidence_gap"],
            "ranking_fact_ids": ["fact_cause"],
            "ranking_evidence_item_ids": ["technical_assessment"],
            "shared_features": ["recurring moisture"],
        },
        {
            "claim_id": "HIST-SCOPE",
            "title": "Scope pattern",
            "review_status": "generated_reference",
            "provenance": "generated_reference_not_qualified_review",
            "why_useful": "Matches category but not current node.",
            "ranking_categories": ["Rental defect - mould and moisture"],
            "ranking_process_node_ids": ["scope"],
            "ranking_fact_ids": [],
            "ranking_evidence_item_ids": ["lease"],
            "shared_features": [],
        },
        {
            "claim_id": "HIST-NOTICE",
            "title": "Notice pattern",
            "review_status": "generated_reference",
            "provenance": "generated_reference_not_qualified_review",
            "why_useful": "Notification evidence reference.",
            "ranking_categories": ["Rental defect - mould and moisture"],
            "ranking_process_node_ids": ["notification"],
            "ranking_fact_ids": [],
            "ranking_evidence_item_ids": [],
            "shared_features": [],
        },
        {
            "claim_id": "HIST-UNRELATED",
            "title": "Unrelated pattern",
            "review_status": "generated_reference",
            "provenance": "generated_reference_not_qualified_review",
            "why_useful": "Deliberately unrelated negative control.",
            "ranking_categories": ["Travel dispute"],
            "ranking_process_node_ids": ["resolution"],
            "ranking_fact_ids": [],
            "ranking_evidence_item_ids": [],
            "shared_features": [],
        },
    ]


def ranked(**overrides) -> dict:
    return rank_precedents(
        current_claim_id="CURRENT",
        understanding=overrides.get("understanding", understanding()),
        process=overrides.get("process", process()),
        checklist=overrides.get("checklist", checklist()),
        memories=overrides.get("memories", []),
        corpus=overrides.get("corpus", corpus()),
    )


def test_exact_three_are_ranked_from_real_process_evidence_and_fact_context():
    value = ranked()
    assert len(value["results"]) == 3
    assert [item["claim_id"] for item in value["results"]] == [
        "HIST-CAUSE",
        "HIST-SCOPE",
        "HIST-NOTICE",
    ]
    assert value["receipt"]["contract"] == PRECEDENT_RANKING_CONTRACT
    assert value["receipt"]["corpus_version"] == PRECEDENT_CORPUS_VERSION
    assert value["receipt"]["selected_claim_ids"] == [
        "HIST-CAUSE",
        "HIST-SCOPE",
        "HIST-NOTICE",
    ]
    assert len(value["receipt"]["context_hash"]) == 64
    assert len(value["receipt"]["result_hash"]) == 64
    assert value["results"][0]["ranking"]["score_basis_points"] > value["results"][1]["ranking"]["score_basis_points"]
    assert "ranking_process_node_ids" not in value["results"][0]


def test_ranking_changes_when_process_or_evidence_context_changes():
    first = ranked()
    changed_process = deepcopy(process())
    changed_process["current_overlay"] = {
        "current_node_id": "scope",
        "next_action_node_id": "scope",
    }
    changed_process["selected_path"] = ["intake", "scope"]
    second = ranked(
        process=changed_process,
        checklist=checklist(include_assessment=False),
    )
    assert first["receipt"]["context_hash"] != second["receipt"]["context_hash"]
    assert first["receipt"]["candidate_scores"] != second["receipt"]["candidate_scores"]


def test_category_only_match_cannot_outrank_current_decision_relevance():
    value = ranked()
    scores = {
        item["claim_id"]: item["score_basis_points"]
        for item in value["receipt"]["candidate_scores"]
    }
    assert scores["HIST-CAUSE"] > scores["HIST-SCOPE"]


def test_memory_is_ranked_by_the_same_contract_and_keeps_unverified_status():
    value = ranked(
        memories=[
            {
                "memory_id": "memory_1",
                "claim_id": "REVIEWED-DEMO",
                "title": "Unverified reviewed demo",
                "review_status": "unverified_demo_memory",
                "category": "Rental defect - mould and moisture",
                "why_useful": "Case-specific disputed-causation memory.",
            }
        ]
    )
    memory = next(item for item in value["results"] if item["claim_id"] == "REVIEWED-DEMO")
    assert memory["review_status"] == "unverified_demo_memory"
    assert memory["memory_id"] == "memory_1"


def test_current_claim_is_excluded_and_small_corpus_fails_closed():
    values = corpus()[:3]
    values[0]["claim_id"] = "CURRENT"
    with pytest.raises(ValueError, match="cannot satisfy"):
        ranked(corpus=values)


def test_non_exact_result_count_is_rejected():
    with pytest.raises(ValueError, match="exactly three"):
        rank_precedents(
            current_claim_id="CURRENT",
            understanding=understanding(),
            process=process(),
            checklist=checklist(),
            memories=[],
            corpus=corpus(),
            limit=2,
        )

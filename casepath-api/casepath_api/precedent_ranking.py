from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any


PRECEDENT_RANKING_CONTRACT = "casepath.precedent-ranking/1.0.0"
PRECEDENT_CORPUS_VERSION = "generated-reference-patterns/2026-08-12"
_FEATURE_WEIGHTS = {
    "current_process_node": 50,
    "unresolved_fact": 30,
    "current_evidence_need": 20,
    "category": 10,
    "process_branch": 8,
    "shared_feature": 2,
}


def _stable_hash(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def ranking_context(
    understanding: dict[str, Any],
    process: dict[str, Any],
    checklist: dict[str, Any],
) -> dict[str, Any]:
    current_node = process["current_overlay"]["current_node_id"]
    next_action = process["current_overlay"]["next_action_node_id"]
    unresolved_fact_ids = sorted(
        value["fact_id"]
        for value in understanding.get("facts", [])
        if value.get("state") in {"unknown", "conflicting"}
    )
    current_evidence_need_ids = sorted(
        value["item_id"]
        for value in checklist.get("items", [])
        if value.get("current_path") is True
        and value.get("status") in {"missing", "conditional", "provided_insufficient"}
    )
    return {
        "category": understanding.get("category"),
        "subcategory": understanding.get("subcategory"),
        "current_process_node_id": current_node,
        "next_action_node_id": next_action,
        "selected_path": list(process.get("selected_path", [])),
        "unresolved_fact_ids": unresolved_fact_ids,
        "current_evidence_need_ids": current_evidence_need_ids,
    }


def _record_features(record: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "categories": set(record.get("ranking_categories", [])),
        "process_nodes": set(record.get("ranking_process_node_ids", [])),
        "fact_ids": set(record.get("ranking_fact_ids", [])),
        "evidence_ids": set(record.get("ranking_evidence_item_ids", [])),
        "shared_features": set(record.get("shared_features", [])),
    }


def _score_record(
    record: dict[str, Any],
    context: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]]:
    features = _record_features(record)
    factors: list[dict[str, Any]] = []

    def add(name: str, values: set[str], weight: int) -> None:
        for value in sorted(values):
            factors.append({"factor": name, "value": value, "weight": weight})

    if context["current_process_node_id"] in features["process_nodes"]:
        add(
            "current_process_node",
            {context["current_process_node_id"]},
            _FEATURE_WEIGHTS["current_process_node"],
        )
    fact_overlap = set(context["unresolved_fact_ids"]) & features["fact_ids"]
    add("unresolved_fact", fact_overlap, _FEATURE_WEIGHTS["unresolved_fact"])
    evidence_overlap = (
        set(context["current_evidence_need_ids"]) & features["evidence_ids"]
    )
    add(
        "current_evidence_need",
        evidence_overlap,
        _FEATURE_WEIGHTS["current_evidence_need"],
    )
    if context["category"] in features["categories"]:
        add("category", {context["category"]}, _FEATURE_WEIGHTS["category"])
    path_overlap = set(context["selected_path"]) & features["process_nodes"]
    add("process_branch", path_overlap, _FEATURE_WEIGHTS["process_branch"])
    textual_context = " ".join(
        [
            str(context.get("category", "")),
            str(context.get("subcategory", "")),
            str(context.get("current_process_node_id", "")),
            str(context.get("next_action_node_id", "")),
        ]
    ).lower()
    shared = {
        feature
        for feature in features["shared_features"]
        if feature.lower() in textual_context
    }
    add("shared_feature", shared, _FEATURE_WEIGHTS["shared_feature"])
    return sum(factor["weight"] for factor in factors), factors


def rank_precedents(
    *,
    current_claim_id: str,
    understanding: dict[str, Any],
    process: dict[str, Any],
    checklist: dict[str, Any],
    memories: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    limit: int = 3,
) -> dict[str, Any]:
    if limit != 3:
        raise ValueError("the flagship precedent contract requires exactly three results")
    context = ranking_context(understanding, process, checklist)
    records: list[dict[str, Any]] = []
    for memory in memories:
        if memory.get("claim_id") == current_claim_id:
            continue
        records.append(
            {
                "claim_id": memory["claim_id"],
                "title": memory.get(
                    "title", "Unverified demo recurring-mould memory"
                ),
                "review_status": memory.get(
                    "review_status", "unverified_demo_memory"
                ),
                "why_useful": (
                    "Unverified generated-demo memory with the same disputed-"
                    "causation branch; it may guide this case-specific path but "
                    "has no shared-rule authority."
                ),
                "provenance": "unverified_generated_demo_review_memory",
                "final_process": deepcopy(memory.get("final_process", [])),
                "evidence": deepcopy(memory.get("final_checklist", [])),
                "outcome": "Unverified demo memory",
                "memory_id": memory["memory_id"],
                "ranking_categories": [memory.get("category")],
                "ranking_process_node_ids": [
                    "causation",
                    "evidence_gap",
                    "tenant_use",
                ],
                "ranking_fact_ids": [
                    "fact_cause",
                    "later_fact_cause",
                    "fact_recurrence",
                    "later_fact_recurrence",
                    "later_fact_ventilation_allegation",
                ],
                "ranking_evidence_item_ids": [
                    "technical_assessment",
                    "moisture_measurements",
                    "building_envelope",
                    "use_evidence",
                ],
                "shared_features": memory.get(
                    "shared_features",
                    ["recurrence", "ventilation allegation", "cause unresolved"],
                ),
            }
        )
    records.extend(deepcopy(corpus))
    scored: list[dict[str, Any]] = []
    for record in records:
        if record.get("claim_id") == current_claim_id:
            continue
        score, factors = _score_record(record, context)
        scored.append(
            {
                "record": record,
                "claim_id": record["claim_id"],
                "score_basis_points": score,
                "factors": factors,
            }
        )
    scored.sort(key=lambda item: (-item["score_basis_points"], item["claim_id"]))
    selected = scored[:limit]
    if len(selected) != limit:
        raise ValueError("the precedent corpus cannot satisfy the exact-three contract")
    results: list[dict[str, Any]] = []
    for rank, value in enumerate(selected, start=1):
        record = value["record"]
        public = {
            key: deepcopy(record[key])
            for key in (
                "claim_id",
                "title",
                "review_status",
                "why_useful",
                "provenance",
                "shared_features",
                "final_process",
                "evidence",
                "reference_lesson",
                "outcome",
                "memory_id",
            )
            if key in record
        }
        public["ranking"] = {
            "contract": PRECEDENT_RANKING_CONTRACT,
            "corpus_version": PRECEDENT_CORPUS_VERSION,
            "rank": rank,
            "score_basis_points": value["score_basis_points"],
            "factors": value["factors"],
            "context_hash": _stable_hash(context),
        }
        results.append(public)
    receipt = {
        "contract": PRECEDENT_RANKING_CONTRACT,
        "corpus_version": PRECEDENT_CORPUS_VERSION,
        "context": context,
        "context_hash": _stable_hash(context),
        "candidate_scores": [
            {
                "claim_id": item["claim_id"],
                "score_basis_points": item["score_basis_points"],
                "factors": item["factors"],
            }
            for item in scored
        ],
        "selected_claim_ids": [item["claim_id"] for item in selected],
    }
    receipt["result_hash"] = _stable_hash(results)
    return {"results": results, "receipt": receipt}


def validate_precedent_ranking_bundle(
    *,
    current_claim_id: str,
    understanding: dict[str, Any],
    process: dict[str, Any],
    checklist: dict[str, Any],
    memories: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    results: list[dict[str, Any]],
    receipt: dict[str, Any],
) -> None:
    """Recompute and exactly bind the public ranking results and receipt.

    A hash inside a provider-facing DTO is not an authority boundary by itself.
    Acceptance therefore reruns the deterministic ranker from the governed
    corpus and internal memory records, then compares the entire public bundle.
    """

    expected = rank_precedents(
        current_claim_id=current_claim_id,
        understanding=understanding,
        process=process,
        checklist=checklist,
        memories=memories,
        corpus=corpus,
    )
    if results != expected["results"]:
        raise ValueError("precedent_ranking_results")
    if receipt != expected["receipt"]:
        raise ValueError("precedent_ranking_receipt")


__all__ = [
    "PRECEDENT_CORPUS_VERSION",
    "PRECEDENT_RANKING_CONTRACT",
    "rank_precedents",
    "ranking_context",
    "validate_precedent_ranking_bundle",
]

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .common import digest_value
from .contracts import CanonicalCaseArtifact, ValidationReceipt


def _check(name: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {"check": name, "passed": passed, "evidence": evidence}


def _provenance_hashes(values: list[dict[str, Any]]) -> set[str]:
    return {digest_value(value) for value in values}


def validate_canonical_artifact(
    artifact: CanonicalCaseArtifact,
) -> ValidationReceipt:
    """Validate structural and traceability invariants without judging semantics.

    This validator proves that required links and source locators are present and
    internally consistent. It does not prove that the process or plan is correct.
    """

    process = artifact.process_artifact
    concepts = process.get("concepts", [])
    relations = process.get("relations", [])
    branches = process.get("branch_predicates", [])
    documents = list(artifact.evidence_document_plan)

    concept_ids = {
        value.get("concept_id")
        for value in concepts
        if isinstance(value, dict) and isinstance(value.get("concept_id"), str)
    }
    document_ids = {
        value.get("item_id")
        for value in documents
        if isinstance(value, dict) and isinstance(value.get("item_id"), str)
    }
    all_node_ids = concept_ids | document_ids

    relation_shapes_valid = all(
        isinstance(value, dict)
        and isinstance(value.get("source_id"), str)
        and isinstance(value.get("target_id"), str)
        and value["source_id"] in all_node_ids
        and value["target_id"] in all_node_ids
        for value in relations
    )

    relation_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    relation_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        source_id = relation.get("source_id")
        target_id = relation.get("target_id")
        if isinstance(source_id, str) and isinstance(target_id, str):
            relation_by_target[target_id].append(relation)
            relation_by_source[source_id].append(relation)

    kind_by_id = {
        value["concept_id"]: value.get("kind")
        for value in concepts
        if isinstance(value, dict) and isinstance(value.get("concept_id"), str)
    }
    required_kinds = {"decision", "fact", "evidence_capability"}
    observed_kinds = {str(value) for value in kind_by_id.values()}

    source_locator_hashes = {
        digest_value(value.model_dump(mode="json"))
        for value in artifact.source_locators
    }
    artifact_provenance_hashes = {
        digest_value(value.model_dump(mode="json")) for value in artifact.provenance
    }
    embedded_provenance: list[dict[str, Any]] = []
    provenance_holders = [*concepts, *branches, *documents]
    holders_have_provenance = True
    for holder in provenance_holders:
        if not isinstance(holder, dict):
            holders_have_provenance = False
            continue
        values = holder.get("provenance")
        if not isinstance(values, list) or not values:
            holders_have_provenance = False
            continue
        embedded_provenance.extend(value for value in values if isinstance(value, dict))
    embedded_hashes = _provenance_hashes(embedded_provenance)

    document_chains: dict[str, bool] = {}
    for document_id in sorted(
        value for value in document_ids if isinstance(value, str)
    ):
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(document_id, ())])
        visited: set[tuple[str, tuple[str, ...]]] = set()
        found = False
        while queue and not found:
            node_id, path_types = queue.popleft()
            state = (node_id, path_types)
            if state in visited:
                continue
            visited.add(state)
            if kind_by_id.get(node_id) == "decision" and {
                "satisfied_by",
                "supported_by",
                "requires_fact",
            }.issubset(path_types):
                found = True
                break
            for relation in relation_by_target.get(node_id, []):
                relation_type = relation.get("relation_type")
                source_id = relation.get("source_id")
                if isinstance(relation_type, str) and isinstance(source_id, str):
                    queue.append((source_id, (*path_types, relation_type)))
        document_chains[document_id] = found

    terminal_ids = process.get("terminal_outcome_ids", [])
    terminal_ids_valid = isinstance(terminal_ids, list) and all(
        isinstance(value, str) and value in concept_ids for value in terminal_ids
    )
    branch_predicates_valid = all(
        isinstance(branch, dict)
        and isinstance(branch.get("predicate_id"), str)
        and bool(branch["predicate_id"])
        and isinstance(branch.get("expression"), str)
        and bool(branch["expression"])
        for branch in branches
    ) and len(
        {
            branch["predicate_id"]
            for branch in branches
            if isinstance(branch, dict) and isinstance(branch.get("predicate_id"), str)
        }
    ) == len(branches)

    checks = (
        _check("process_has_concepts", bool(concepts), count=len(concepts)),
        _check("process_has_relations", bool(relations), count=len(relations)),
        _check(
            "required_process_kinds_present",
            required_kinds.issubset(observed_kinds),
            required=sorted(required_kinds),
            observed=sorted(observed_kinds),
        ),
        _check(
            "relation_endpoints_resolve",
            relation_shapes_valid,
            concept_count=len(concept_ids),
            document_count=len(document_ids),
        ),
        _check(
            "branch_predicates_are_explicit_and_unique",
            branch_predicates_valid,
            branch_count=len(branches),
        ),
        _check(
            "terminal_outcomes_resolve",
            terminal_ids_valid,
            terminal_count=len(terminal_ids) if isinstance(terminal_ids, list) else 0,
        ),
        _check(
            "provenance_present_on_outputs",
            holders_have_provenance,
            holder_count=len(provenance_holders),
        ),
        _check(
            "embedded_provenance_matches_canonical_provenance",
            embedded_hashes.issubset(artifact_provenance_hashes),
            embedded_locator_count=len(embedded_hashes),
            canonical_provenance_count=len(artifact_provenance_hashes),
        ),
        _check(
            "canonical_provenance_resolves_to_sources",
            artifact_provenance_hashes.issubset(source_locator_hashes),
            source_locator_count=len(source_locator_hashes),
            canonical_provenance_count=len(artifact_provenance_hashes),
        ),
        _check(
            "every_document_has_process_fact_evidence_chain",
            bool(document_chains) and all(document_chains.values()),
            document_chains=document_chains,
        ),
    )
    passed = all(value["passed"] is True for value in checks)
    payload = {
        "contract": "casepath.foundation-validation-receipt/1.0.0",
        "case_id": artifact.case_id,
        "passed": passed,
        "checks": list(checks),
        "canonical_sha256": artifact.canonical_sha256,
    }
    return ValidationReceipt.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )

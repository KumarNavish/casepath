"""Zero-model alias/rule baseline shipped with CasePath-Bench-v3."""

from __future__ import annotations

import re
from typing import Any

from contracts.schema import (
    CandidateArtifact,
    CandidateBranchPredicate,
    CandidateConcept,
    CandidateDocument,
    CandidateRelation,
    ConceptKind,
    DocumentState,
    RelationType,
    RequestMode,
    SourceLocator,
)


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß]{3,}", value.casefold()))


def _predicate_variable(value: str) -> str:
    """Convert a public rule phrase into a valid, deterministic Boolean name."""

    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not normalized:
        raise ValueError("a conditional transition lacks a usable predicate phrase")
    if normalized[0].isdigit():
        normalized = f"condition_{normalized}"
    return normalized


def _choose_template(claim: dict[str, Any], templates: list[dict[str, Any]]) -> dict[str, Any]:
    body = str(claim.get("customer_message", {}).get("body", ""))
    keywords = {
        "defect_mold_heating": {"mould", "mold", "moisture", "heating", "schimmel", "heizung"},
        "lease_termination_dispute": {
            "termination",
            "notice",
            "kündigung",
            "gekündigt",
            "lease",
        },
        "rent_increase_dispute": {
            "increase",
            "rent",
            "mietzinserhöhung",
            "mietzins",
            "reference",
        },
    }
    body_words = _words(body)
    ranked = sorted(
        templates,
        key=lambda item: (
            -len(body_words.intersection(keywords[item["domain"]])),
            item["domain"],
        ),
    )
    return ranked[0]


def _registry_index(registry: dict[str, Any]) -> tuple[dict[str, SourceLocator], SourceLocator]:
    rules: dict[str, SourceLocator] = {}
    attachment: SourceLocator | None = None
    for entry in registry["entries"]:
        locator = SourceLocator.model_validate(entry["locator"])
        if entry["source_kind"] == "case_invariant_rule":
            rules[str(entry["display_value"])] = locator
        elif entry["source_kind"] == "observable_attachment_inventory":
            attachment = locator
    if attachment is None:
        raise ValueError("source registry lacks the attachment inventory")
    return rules, attachment


def alias_rule_baseline_v3(
    *, claim: dict[str, Any], rules: dict[str, Any], registry: dict[str, Any]
) -> CandidateArtifact:
    """Build a deterministic, deliberately weak graph/evidence prediction."""

    case_id = str(claim["submission"]["claim_id"])
    template = _choose_template(claim, rules["templates"])
    catalog = template["process_catalog"]
    rule_locators, attachment_locator = _registry_index(registry)
    conditional_sources = {
        item["source_node_id"]
        for item in catalog["transitions"]
        if str(item["condition"]).strip().casefold() != "true"
    }
    concepts: list[CandidateConcept] = []
    for item in catalog["nodes"]:
        kind = (
            ConceptKind.OUTCOME
            if item["terminal"]
            else ConceptKind.DECISION
            if item["node_id"] in conditional_sources
            else ConceptKind.PROCESS_STEP
        )
        concepts.append(
            CandidateConcept(
                concept_id=f"baseline.node.{item['node_id']}",
                kind=kind,
                label=item["label"],
                provenance=(rule_locators[item["assertion"]],),
            )
        )
    node_ids = {item["node_id"]: f"baseline.node.{item['node_id']}" for item in catalog["nodes"]}
    relations: list[CandidateRelation] = []
    predicates: list[CandidateBranchPredicate] = []
    for item in catalog["transitions"]:
        condition = str(item["condition"])
        conditional = condition.strip().casefold() != "true"
        expression = _predicate_variable(condition) if conditional else "true"
        relations.append(
            CandidateRelation(
                relation_id=f"baseline.edge.{item['edge_id']}",
                relation_type=(RelationType.BRANCHES_TO if conditional else RelationType.PRECEDES),
                source_id=node_ids[item["source_node_id"]],
                target_id=node_ids[item["target_node_id"]],
                # The zero-model baseline cannot observe the hidden case assignment.  Keep
                # its proposed graph executable under every assignment and let the separately
                # emitted predicate be judged by the frozen truth-table probes.
                active_when="true",
            )
        )
        if conditional:
            predicates.append(
                CandidateBranchPredicate(
                    predicate_id=f"baseline.predicate.{item['edge_id']}",
                    expression=expression,
                    provenance=(rule_locators[item["assertion"]],),
                )
            )

    observed_text = str(claim.get("customer_message", {}).get("body", ""))
    observed_text += " " + " ".join(
        str(item.get("file_name", "")) for item in claim.get("attachments", [])
    )
    documents: list[CandidateDocument] = []
    first_decision = next(item.concept_id for item in concepts if item.kind is ConceptKind.DECISION)
    for index, item in enumerate(catalog["documents"]):
        suffix = f"{index:03d}"
        rule_locator = rule_locators[item["assertion"]]
        label = str(item["label"])
        provided = bool(_words(label).intersection(_words(observed_text)))
        decision_id = f"baseline.doc-decision.{suffix}"
        fact_id = f"baseline.fact.{suffix}"
        capability_id = f"baseline.capability.{suffix}"
        document_item_id = f"baseline.document-item.{suffix}"
        concepts.extend(
            (
                CandidateConcept(
                    concept_id=decision_id,
                    kind=ConceptKind.DECISION,
                    label=f"Decide whether {label} is needed",
                    provenance=(rule_locator,),
                ),
                CandidateConcept(
                    concept_id=fact_id,
                    kind=ConceptKind.FACT,
                    label=f"Evidence state for {label}",
                    provenance=(rule_locator, attachment_locator),
                ),
                CandidateConcept(
                    concept_id=capability_id,
                    kind=ConceptKind.EVIDENCE_CAPABILITY,
                    label=f"Evidence capable of resolving {label}",
                    provenance=(rule_locator,),
                ),
            )
        )
        relations.extend(
            (
                CandidateRelation(
                    relation_id=f"baseline.requires.{suffix}",
                    relation_type=RelationType.REQUIRES_FACT,
                    source_id=decision_id,
                    target_id=fact_id,
                ),
                CandidateRelation(
                    relation_id=f"baseline.supported.{suffix}",
                    relation_type=RelationType.SUPPORTED_BY,
                    source_id=fact_id,
                    target_id=capability_id,
                ),
                CandidateRelation(
                    relation_id=f"baseline.satisfied.{suffix}",
                    relation_type=RelationType.SATISFIED_BY,
                    source_id=capability_id,
                    target_id=document_item_id,
                ),
                CandidateRelation(
                    relation_id=f"baseline.doc-control.{suffix}",
                    relation_type=RelationType.PRECEDES,
                    source_id=first_decision,
                    target_id=decision_id,
                ),
            )
        )
        documents.append(
            CandidateDocument(
                item_id=document_item_id,
                document_id=f"baseline.document.{suffix}",
                label=label,
                state=(DocumentState.PROVIDED_SUFFICIENT if provided else DocumentState.MISSING),
                request_mode=RequestMode.NONE if provided else RequestMode.NOW,
                provenance=(rule_locator, attachment_locator),
            )
        )
    return CandidateArtifact(
        artifact_version="casepath.candidate-artifact/0.1.0",
        case_id=case_id,
        concepts=tuple(concepts),
        relations=tuple(relations),
        branch_predicates=tuple(predicates),
        documents=tuple(documents),
        terminal_outcome_ids=tuple(
            item.concept_id for item in concepts if item.kind is ConceptKind.OUTCOME
        ),
    )

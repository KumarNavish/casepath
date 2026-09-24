"""Zero-call anti-circular floor for the internal custom diagnostic.

This is intentionally simple.  It is not a competitor dressed up as an agent:
it matches ontology labels/aliases in observable and generic-policy text, then
builds only the minimal chains supported by those matches.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from typing import Any

from contracts.closed_vocabulary import ClosedVocabularyOntology
from contracts.schema import (
    CandidateArtifact,
    CandidateConcept,
    CandidateDocument,
    CandidateRelation,
    ConceptKind,
    DocumentState,
    RelationType,
    RequestMode,
)

HEURISTIC_VERSION_V3 = "casepath.ontology-rule-heuristic/3.0.0"


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text(item) for key, item in value.items() if key != "sha256")
    if isinstance(value, list | tuple):
        return " ".join(_text(item) for item in value)
    return ""


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " " + re.sub(r"[^a-z0-9]+", " ", value).strip() + " "


def _matched(label: str, aliases: tuple[str, ...], haystack: str) -> bool:
    for value in (label, *aliases):
        needle = _normalized(value).strip()
        if len(needle) >= 4 and f" {needle} " in haystack:
            return True
    return False


def _identifier(prefix: str, kind: str, label: str) -> str:
    digest = hashlib.sha256(f"{kind}\0{label}".encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def ontology_rule_heuristic_v3(model_payload: dict[str, Any]) -> CandidateArtifact:
    """Produce one deterministic candidate using model-visible fields only."""

    case_id = str(model_payload["case_id"])
    ontology = ClosedVocabularyOntology.model_validate(model_payload["closed_vocabulary_ontology"])
    observable_text = _normalized(_text(model_payload["observable_claim"]))
    policy_text = _normalized(" ".join(source.content for source in ontology.policy_sources))
    evidence_text = observable_text + policy_text
    matches: dict[ConceptKind, list[str]] = defaultdict(list)
    for entry in ontology.vocabulary:
        if _matched(entry.label, entry.aliases, evidence_text):
            matches[entry.kind].append(entry.label)

    concepts: list[CandidateConcept] = []
    concept_ids: dict[tuple[ConceptKind, str], str] = {}
    for kind in (
        ConceptKind.PROCESS_STEP,
        ConceptKind.DECISION,
        ConceptKind.OUTCOME,
        ConceptKind.FACT,
        ConceptKind.EVIDENCE_CAPABILITY,
    ):
        for label in sorted(set(matches[kind])):
            concept_id = _identifier("h", kind.value, label)
            concept_ids[(kind, label)] = concept_id
            concepts.append(
                CandidateConcept(
                    concept_id=concept_id,
                    kind=kind,
                    label=label,
                    active_when="true",
                    confidence=1.0,
                )
            )

    # A document is requested only when the same observable/policy text also
    # supports one matched decision, fact, and evidence-capability label.
    decisions = sorted(set(matches[ConceptKind.DECISION]))
    facts = sorted(set(matches[ConceptKind.FACT]))
    capabilities = sorted(set(matches[ConceptKind.EVIDENCE_CAPABILITY]))
    documents = sorted(set(matches[ConceptKind.DOCUMENT]))
    can_chain = bool(decisions and facts and capabilities)
    candidate_documents: list[CandidateDocument] = []
    relations: list[CandidateRelation] = []
    if can_chain:
        decision_id = concept_ids[(ConceptKind.DECISION, decisions[0])]
        fact_id = concept_ids[(ConceptKind.FACT, facts[0])]
        capability_id = concept_ids[(ConceptKind.EVIDENCE_CAPABILITY, capabilities[0])]
        relations.extend(
            (
                CandidateRelation(
                    relation_id="h_requires_fact",
                    relation_type=RelationType.REQUIRES_FACT,
                    source_id=decision_id,
                    target_id=fact_id,
                ),
                CandidateRelation(
                    relation_id="h_supported_by",
                    relation_type=RelationType.SUPPORTED_BY,
                    source_id=fact_id,
                    target_id=capability_id,
                ),
            )
        )
        for label in documents:
            item_id = _identifier("hd", "document", label)
            candidate_documents.append(
                CandidateDocument(
                    item_id=item_id,
                    document_id=_identifier("doc", "document", label),
                    label=label,
                    state=DocumentState.UNKNOWN,
                    request_mode=RequestMode.NOW,
                    active_when="true",
                    confidence=1.0,
                )
            )
            relations.append(
                CandidateRelation(
                    relation_id=_identifier("hr", "satisfied_by", label),
                    relation_type=RelationType.SATISFIED_BY,
                    source_id=capability_id,
                    target_id=item_id,
                )
            )

    terminal_ids = tuple(
        concept_ids[(ConceptKind.OUTCOME, label)]
        for label in sorted(set(matches[ConceptKind.OUTCOME]))
    )
    return CandidateArtifact(
        artifact_version="casepath.candidate-artifact/0.1.0",
        case_id=case_id,
        concepts=tuple(concepts),
        relations=tuple(relations),
        documents=tuple(candidate_documents),
        terminal_outcome_ids=terminal_ids,
    )


def heuristic_input_sha256(model_payload: dict[str, Any]) -> str:
    """Bind the exact zero-call heuristic input for a run receipt."""

    return hashlib.sha256(
        json.dumps(
            model_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

"""Static union ontology for the closed-vocabulary custom task."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .autonomous import GenericPolicySource
from .schema import ConceptKind, StrictModel


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


class VocabularyEntry(StrictModel):
    kind: ConceptKind
    label: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()


class ClosedVocabularyOntology(StrictModel):
    ontology_version: Literal["casepath.closed-vocabulary-ontology/1.0.0"]
    task_definition: Literal[
        "closed-vocabulary domain routing, structure and activation recovery, "
        "and process-derived evidence selection"
    ]
    source_compilation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_evaluator_file_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_sources: tuple[GenericPolicySource, ...] = Field(min_length=3, max_length=3)
    vocabulary: tuple[VocabularyEntry, ...] = Field(min_length=1)
    predicate_names: tuple[str, ...] = Field(min_length=1)
    chain_label_templates: tuple[str, ...] = Field(min_length=3)
    output_contract_rules: tuple[str, ...] = Field(min_length=3)
    contains_active_values: Literal[False]
    contains_paths: Literal[False]
    contains_requirements: Literal[False]
    contains_document_states: Literal[False]
    ontology_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_union(self) -> ClosedVocabularyOntology:
        if tuple(source.subtype for source in self.policy_sources) != tuple(
            sorted(source.subtype for source in self.policy_sources)
        ):
            raise ValueError("union ontology policies must be sorted by subtype")
        if len({source.subtype for source in self.policy_sources}) != 3:
            raise ValueError("union ontology requires all three domain policies")
        keys: dict[tuple[ConceptKind, str], str] = {}
        for entry in self.vocabulary:
            for label in (entry.label, *entry.aliases):
                key = (entry.kind, normalized_label(label))
                previous = keys.setdefault(key, entry.label)
                if previous != entry.label:
                    raise ValueError("normalized ontology label collision")
        if self.predicate_names != tuple(sorted(set(self.predicate_names))):
            raise ValueError("predicate vocabulary must be sorted and unique")
        if self.ontology_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"ontology_sha256"})
        ):
            raise ValueError("closed-vocabulary ontology has a stale hash")
        return self

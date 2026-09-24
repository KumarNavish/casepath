"""Intermediate schemas make each generation intervention executable."""

from __future__ import annotations

import re
from collections import Counter
from typing import Annotated, Literal

from pydantic import Field, model_validator

from contracts.schema import StrictModel

BoundedRuleText = Annotated[str, Field(min_length=1, max_length=500)]


class DirectDraft(StrictModel):
    artifact_version: Literal["casepath.direct-draft/0.1.0"]
    observations: tuple[str, ...]
    decisions: tuple[str, ...]
    required_facts: tuple[str, ...]
    evidence_capabilities: tuple[str, ...]
    documents: tuple[str, ...]


class DocumentHypothesis(StrictModel):
    label: str
    observed_state: Literal[
        "provided_sufficient",
        "provided_insufficient",
        "missing",
        "conditional",
        "irrelevant",
        "unknown",
    ]
    possible_use: str


class DocumentFirstDraft(StrictModel):
    artifact_version: Literal["casepath.document-first-draft/0.1.0"]
    documents: tuple[DocumentHypothesis, ...] = Field(min_length=1)


class ProcessFirstDraft(StrictModel):
    artifact_version: Literal["casepath.process-first-draft/0.1.0"]
    decisions: tuple[str, ...] = Field(min_length=1)
    required_facts: tuple[str, ...] = Field(min_length=1)
    branch_predicates: tuple[str, ...]
    terminal_outcomes: tuple[str, ...] = Field(min_length=1)


class ExecutableRule(StrictModel):
    rule_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    conditions: tuple[BoundedRuleText, ...] = Field(min_length=1, max_length=16)
    action: BoundedRuleText


class ExIdeP5Draft(StrictModel):
    """Paper-inspired executable grounding without CasePath typed structures."""

    artifact_version: Literal["casepath.exide-p5-adapted-draft/0.1.0"]
    pseudo_code: tuple[BoundedRuleText, ...] = Field(min_length=1, max_length=64)
    rules: tuple[ExecutableRule, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> ExIdeP5Draft:
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("executable rule IDs must be unique")
        return self


DraftArtifact = DirectDraft | DocumentFirstDraft | ProcessFirstDraft | ExIdeP5Draft


# Publication-v3 intermediate contracts.  These live beside the retired v1
# contracts only so historical fixtures remain readable; new execution uses
# only the v3 entry points below.
PlanningKindV3 = Literal[
    "decision",
    "required_fact",
    "branch_condition",
    "terminal_outcome",
    "evidence_capability",
    "document",
    "uncertainty",
]
PROCESS_KINDS_V3 = {
    "decision",
    "required_fact",
    "branch_condition",
    "terminal_outcome",
}
EVIDENCE_KINDS_V3 = {"evidence_capability", "document"}


class TypedPlanningItemV3(StrictModel):
    item_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    kind: PlanningKindV3
    content: BoundedRuleText
    depends_on_item_ids: tuple[str, ...] = Field(default=(), max_length=16)


class TypedPlanningIntermediateV3(StrictModel):
    artifact_version: Literal["casepath.factorial-typed-intermediate/3.0.0"]
    items: tuple[TypedPlanningItemV3, ...] = Field(min_length=7, max_length=96)

    @model_validator(mode="after")
    def validate_items(self) -> TypedPlanningIntermediateV3:
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("typed intermediate item IDs must be unique")
        known = set(ids)
        for item in self.items:
            dependencies = set(item.depends_on_item_ids)
            if item.item_id in dependencies:
                raise ValueError("typed intermediate items cannot depend on themselves")
            if not dependencies.issubset(known):
                raise ValueError("typed dependencies must reference declared items")
        counts = Counter(item.kind for item in self.items)
        required = {
            "decision",
            "required_fact",
            "branch_condition",
            "terminal_outcome",
            "evidence_capability",
            "document",
            "uncertainty",
        }
        if set(counts) != required:
            raise ValueError("typed intermediate must cover every shared information kind")
        return self


PLAIN_HEADINGS_V3: tuple[str, ...] = (
    "DECISIONS",
    "REQUIRED_FACTS",
    "BRANCH_CONDITIONS",
    "TERMINAL_OUTCOMES",
    "EVIDENCE_CAPABILITIES",
    "DOCUMENTS",
    "UNCERTAINTIES",
)
_PLAIN_HEADING_V3 = re.compile(r"^\[([A-Z_]+)\]$")


def parse_plain_intermediate_v3(text: str) -> dict[str, tuple[str, ...]]:
    """Parse the strict sectioned-text arm without inventing typed links."""

    if not text or len(text) > 24_000 or "\x00" in text:
        raise ValueError("plain intermediate is empty or exceeds its frozen bound")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = _PLAIN_HEADING_V3.fullmatch(line)
        if heading:
            current = heading.group(1)
            if current not in PLAIN_HEADINGS_V3 or current in sections:
                raise ValueError("plain intermediate has an unknown or duplicate heading")
            sections[current] = []
            continue
        if current is None or not line.startswith("- ") or len(line) <= 2:
            raise ValueError("plain intermediate lines must be bullets under declared headings")
        sections[current].append(line[2:].strip())
    if set(sections) != set(PLAIN_HEADINGS_V3) or any(not values for values in sections.values()):
        raise ValueError("plain intermediate must cover every shared information heading")
    return {heading: tuple(sections[heading]) for heading in PLAIN_HEADINGS_V3}


class PlainPlanningIntermediateV3(StrictModel):
    artifact_version: Literal["casepath.factorial-plain-intermediate/3.0.0"]
    analysis: str = Field(min_length=1, max_length=24_000)

    @model_validator(mode="after")
    def validate_grammar(self) -> PlainPlanningIntermediateV3:
        parse_plain_intermediate_v3(self.analysis)
        return self


FactorialIntermediateV3 = TypedPlanningIntermediateV3 | PlainPlanningIntermediateV3


class ExIdeP5DraftV3(StrictModel):
    artifact_version: Literal["casepath.exide-p5-adapted-draft/3.0.0"]
    pseudo_code: tuple[BoundedRuleText, ...] = Field(min_length=1, max_length=64)
    rules: tuple[ExecutableRule, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> ExIdeP5DraftV3:
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("executable rule IDs must be unique")
        return self


class DocumentHypothesisV3(StrictModel):
    label: BoundedRuleText
    observed_state: Literal[
        "provided_sufficient",
        "provided_insufficient",
        "missing",
        "conditional",
        "irrelevant",
        "unknown",
    ]
    evidence_use: BoundedRuleText
    source_artifact_ids: tuple[str, ...] = Field(default=(), max_length=16)


class DocumentFirstDraftV3(StrictModel):
    artifact_version: Literal["casepath.document-first-draft/3.0.0"]
    documents: tuple[DocumentHypothesisV3, ...] = Field(min_length=1, max_length=96)
    uncertainties: tuple[BoundedRuleText, ...] = Field(min_length=1, max_length=32)


def validate_factorial_intermediate_v3(*, condition_id: str, payload: object) -> dict[str, object]:
    """Strictly parse the declared representation and enforce only order."""

    from .custom_factorial_v3 import CONDITIONS_V3

    try:
        condition = CONDITIONS_V3[condition_id]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError("unknown publication-v3 condition") from exc
    if condition.condition_id == "EXIDE_V3":
        return ExIdeP5DraftV3.model_validate(payload).model_dump(mode="json")
    if condition.condition_id == "DOCUMENT_FIRST_V3":
        return DocumentFirstDraftV3.model_validate(payload).model_dump(mode="json")
    schema = (
        TypedPlanningIntermediateV3
        if condition.representation_factor == "typed"
        else PlainPlanningIntermediateV3
    )
    parsed = schema.model_validate(payload)
    if condition.order_factor == "process_first":
        if isinstance(parsed, TypedPlanningIntermediateV3):
            process_positions = [
                index for index, item in enumerate(parsed.items) if item.kind in PROCESS_KINDS_V3
            ]
            evidence_positions = [
                index for index, item in enumerate(parsed.items) if item.kind in EVIDENCE_KINDS_V3
            ]
            if max(process_positions) >= min(evidence_positions):
                raise ValueError("process-first typed output placed evidence before process")
        else:
            observed = [
                line[1:-1]
                for line in parsed.analysis.splitlines()
                if _PLAIN_HEADING_V3.fullmatch(line.strip())
            ]
            process_last = max(observed.index(name) for name in PLAIN_HEADINGS_V3[:4])
            evidence_first = min(observed.index(name) for name in PLAIN_HEADINGS_V3[4:6])
            if process_last >= evidence_first:
                raise ValueError("process-first plain output placed evidence before process")
    return parsed.model_dump(mode="json")


def draft_schema_for_stage(stage: str) -> type[DraftArtifact] | None:
    schemas: dict[str, type[DraftArtifact]] = {
        "direct_draft": DirectDraft,
        "document_draft": DocumentFirstDraft,
        "process_draft": ProcessFirstDraft,
        "exide_rule_draft": ExIdeP5Draft,
    }
    return schemas.get(stage)


def validate_draft(stage: str, payload: object) -> dict[str, object]:
    schema = draft_schema_for_stage(stage)
    if schema is None:
        raise ValueError(f"stage {stage!r} is not an intermediate draft stage")
    return schema.model_validate(payload).model_dump(mode="json")

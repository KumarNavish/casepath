"""Predeclared causal conditions for the first CasePath experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConditionId = Literal["B3", "B6", "B7", "B8", "B9"]
GenerationConditionId = Literal["B3", "B6", "B7", "B9"]
CONDITION_ORDER: tuple[ConditionId, ...] = ("B3", "B6", "B7", "B9", "B8")
# Frozen four-treatment Williams design. Across this block, every treatment
# appears once in every position and every ordered adjacent pair appears once.
GENERATION_ORDERS: tuple[tuple[GenerationConditionId, ...], ...] = (
    ("B3", "B6", "B9", "B7"),
    ("B6", "B7", "B3", "B9"),
    ("B7", "B9", "B6", "B3"),
    ("B9", "B3", "B7", "B6"),
)


@dataclass(frozen=True)
class ConditionDefinition:
    condition_id: ConditionId
    label: str
    stages: tuple[str, ...]
    process_first: bool
    deterministic_verifier: bool
    causal_question: str


CONDITIONS: dict[ConditionId, ConditionDefinition] = {
    "B3": ConditionDefinition(
        condition_id="B3",
        label="Direct end-to-end",
        stages=("direct_draft", "direct_finalize"),
        process_first=False,
        deterministic_verifier=False,
        causal_question="Can a strong direct system match the factorized method?",
    ),
    "B6": ConditionDefinition(
        condition_id="B6",
        label="Document-first",
        stages=("document_draft", "document_first_finalize"),
        process_first=False,
        deterministic_verifier=False,
        causal_question=(
            "Does choosing documents before process obligations create avoidable burden?"
        ),
    ),
    "B7": ConditionDefinition(
        condition_id="B7",
        label="Process-first without verifier",
        stages=("process_draft", "evidence_from_process"),
        process_first=True,
        deterministic_verifier=False,
        causal_question="Does process-first factorization itself improve evidence planning?",
    ),
    "B9": ConditionDefinition(
        condition_id="B9",
        label="Adapted ExIde-P5 executable-rule baseline",
        stages=("exide_rule_draft", "exide_finalize"),
        process_first=False,
        deterministic_verifier=False,
        causal_question=(
            "Does generic executable-rule grounding match process-first evidence planning?"
        ),
    ),
    "B8": ConditionDefinition(
        condition_id="B8",
        label="Process-first with structural-chain filter",
        stages=(),
        process_first=True,
        deterministic_verifier=True,
        causal_question=("What is the incremental value of contract-free structural filtering?"),
    ),
}

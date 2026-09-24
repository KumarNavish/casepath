"""Preregistered custom-study conditions for the causal factorial experiment.

The identifiers in this module deliberately do not overlap with the retired
``B3/B6/B7/B8/B9`` study.  Reusing those identifiers would make an old lock
look compatible with a materially different causal design.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

FactorialConditionId = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
]
GenerativeConditionIdV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
]
ConditionIdV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
    "VERIFY_PF_TYPED_V3",
    "ONTOLOGY_RULE_HEURISTIC_V3",
]
OrderFactor = Literal["process_first", "direct_neutral"]
RepresentationFactor = Literal["typed", "plain_text"]
SequenceIdV3 = Literal["F01", "F02", "F03", "F04", "F05", "F06"]


@dataclass(frozen=True)
class ConditionDefinitionV3:
    condition_id: GenerativeConditionIdV3
    label: str
    stages: tuple[str, str]
    order_factor: OrderFactor | None
    representation_factor: RepresentationFactor | None
    role: Literal["factorial", "falsification"]


FACTORIAL_CONDITIONS: tuple[FactorialConditionId, ...] = (
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
)
GENERATION_CONDITIONS_V3: tuple[GenerativeConditionIdV3, ...] = (
    *FACTORIAL_CONDITIONS,
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
)
PRIMARY_CONDITION_V3: Literal["PF_TYPED_V3"] = "PF_TYPED_V3"
VERIFIED_CONDITION_V3: Literal["VERIFY_PF_TYPED_V3"] = "VERIFY_PF_TYPED_V3"
HEURISTIC_CONDITION_V3: Literal["ONTOLOGY_RULE_HEURISTIC_V3"] = "ONTOLOGY_RULE_HEURISTIC_V3"

CONDITIONS_V3: dict[GenerativeConditionIdV3, ConditionDefinitionV3] = {
    "PF_TYPED_V3": ConditionDefinitionV3(
        condition_id="PF_TYPED_V3",
        label="process-first x typed intermediate",
        stages=("factorial_intermediate", "factorial_finalize"),
        order_factor="process_first",
        representation_factor="typed",
        role="factorial",
    ),
    "PF_PLAIN_V3": ConditionDefinitionV3(
        condition_id="PF_PLAIN_V3",
        label="process-first x plain-text intermediate",
        stages=("factorial_intermediate", "factorial_finalize"),
        order_factor="process_first",
        representation_factor="plain_text",
        role="factorial",
    ),
    "DIRECT_TYPED_V3": ConditionDefinitionV3(
        condition_id="DIRECT_TYPED_V3",
        label="direct-neutral x typed intermediate",
        stages=("factorial_intermediate", "factorial_finalize"),
        order_factor="direct_neutral",
        representation_factor="typed",
        role="factorial",
    ),
    "DIRECT_PLAIN_V3": ConditionDefinitionV3(
        condition_id="DIRECT_PLAIN_V3",
        label="direct-neutral x plain-text intermediate",
        stages=("factorial_intermediate", "factorial_finalize"),
        order_factor="direct_neutral",
        representation_factor="plain_text",
        role="factorial",
    ),
    "EXIDE_V3": ConditionDefinitionV3(
        condition_id="EXIDE_V3",
        label="independent ExIde-inspired rule-first falsification",
        stages=("exide_v3_intermediate", "exide_v3_finalize"),
        order_factor=None,
        representation_factor=None,
        role="falsification",
    ),
    "DOCUMENT_FIRST_V3": ConditionDefinitionV3(
        condition_id="DOCUMENT_FIRST_V3",
        label="document-first checklist falsification",
        stages=("document_first_v3_intermediate", "document_first_v3_finalize"),
        order_factor=None,
        representation_factor=None,
        role="falsification",
    ),
}

# Six-sequence Williams design for six generative conditions. Every condition
# occurs once per period and every directed first-order carryover occurs once
# per block. Twenty-five blocks cover exactly 150 cases.
GENERATION_ORDERS_V3: tuple[tuple[GenerativeConditionIdV3, ...], ...] = (
    (
        "PF_TYPED_V3",
        "PF_PLAIN_V3",
        "DOCUMENT_FIRST_V3",
        "DIRECT_TYPED_V3",
        "EXIDE_V3",
        "DIRECT_PLAIN_V3",
    ),
    (
        "PF_PLAIN_V3",
        "DIRECT_TYPED_V3",
        "PF_TYPED_V3",
        "DIRECT_PLAIN_V3",
        "DOCUMENT_FIRST_V3",
        "EXIDE_V3",
    ),
    (
        "DIRECT_TYPED_V3",
        "DIRECT_PLAIN_V3",
        "PF_PLAIN_V3",
        "EXIDE_V3",
        "PF_TYPED_V3",
        "DOCUMENT_FIRST_V3",
    ),
    (
        "DIRECT_PLAIN_V3",
        "EXIDE_V3",
        "DIRECT_TYPED_V3",
        "DOCUMENT_FIRST_V3",
        "PF_PLAIN_V3",
        "PF_TYPED_V3",
    ),
    (
        "EXIDE_V3",
        "DOCUMENT_FIRST_V3",
        "DIRECT_PLAIN_V3",
        "PF_TYPED_V3",
        "DIRECT_TYPED_V3",
        "PF_PLAIN_V3",
    ),
    (
        "DOCUMENT_FIRST_V3",
        "PF_TYPED_V3",
        "EXIDE_V3",
        "PF_PLAIN_V3",
        "DIRECT_PLAIN_V3",
        "DIRECT_TYPED_V3",
    ),
)
SEQUENCE_IDS_V3: tuple[SequenceIdV3, ...] = (
    "F01",
    "F02",
    "F03",
    "F04",
    "F05",
    "F06",
)
SEQUENCE_TO_ORDER_V3 = dict(zip(SEQUENCE_IDS_V3, GENERATION_ORDERS_V3, strict=True))


def validate_williams_design_v3() -> None:
    """Fail if the frozen schedule loses period or carryover balance."""

    expected = set(GENERATION_CONDITIONS_V3)
    if len(GENERATION_ORDERS_V3) != 6:
        raise ValueError("factorial v3 requires six Williams sequences")
    if any(len(order) != 6 or set(order) != expected for order in GENERATION_ORDERS_V3):
        raise ValueError("every factorial v3 sequence must contain all six conditions once")
    for period in range(6):
        counts = Counter(order[period] for order in GENERATION_ORDERS_V3)
        if counts != Counter({condition: 1 for condition in GENERATION_CONDITIONS_V3}):
            raise ValueError("factorial v3 is not balanced by period")
    carryover = Counter(pair for order in GENERATION_ORDERS_V3 for pair in pairwise(order))
    expected_pairs = {
        (left, right)
        for left in GENERATION_CONDITIONS_V3
        for right in GENERATION_CONDITIONS_V3
        if left != right
    }
    if set(carryover) != expected_pairs or set(carryover.values()) != {1}:
        raise ValueError("factorial v3 is not balanced for first-order carryover")


validate_williams_design_v3()

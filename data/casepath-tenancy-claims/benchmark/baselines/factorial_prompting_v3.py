"""Byte-auditable prompts for the custom 2x2 factorial study."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from baselines.base import StageRequest
from contracts.schema import CandidateArtifact
from manifests.digests import digest_json

from .custom_factorial_v3 import CONDITIONS_V3
from .stage_schema import (
    DocumentFirstDraftV3,
    ExIdeP5DraftV3,
    PlainPlanningIntermediateV3,
    TypedPlanningIntermediateV3,
)

PROMPT_BUNDLE_V3_PATH = Path(__file__).resolve().parent / "prompts" / "v3.json"


@dataclass(frozen=True)
class FactorialPromptRequestV3:
    messages: tuple[dict[str, str], ...]
    response_schema: dict[str, Any]
    prompt_bundle_sha256: str
    matched_template_sha256: str


class FrozenFactorialPromptBundleV3:
    """Render prompts whose only primary-arm changes are the two factor slots."""

    def __init__(self, path: Path = PROMPT_BUNDLE_V3_PATH) -> None:
        self.path = path.resolve()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("bundle_version") != (
            "casepath.custom-factorial-prompt-bundle/3.0.0"
        ):
            raise ValueError("unexpected custom-factorial prompt bundle")
        self.payload = payload
        self.digest = digest_json(payload)
        self.matched_template_digest = digest_json(
            {
                "bundle_version": payload["bundle_version"],
                "shared_rules": payload["shared_rules"],
                "shared_information_requirements": payload["shared_information_requirements"],
                "intermediate": payload["factorial_intermediate"],
                "finalize": payload["factorial_finalize"],
                "factor_slot_names": ["order", "representation"],
            }
        )

    def render(self, request: StageRequest) -> FactorialPromptRequestV3:
        try:
            condition = CONDITIONS_V3[request.condition_id]  # type: ignore[index]
        except KeyError as exc:
            raise ValueError("prompt bundle received a non-v3 condition") from exc
        rules = "\n".join(f"- {rule}" for rule in self.payload["shared_rules"])
        requirements = "\n".join(
            f"- {item}" for item in self.payload["shared_information_requirements"]
        )
        requirements += "\n(The list is alphabetical and does not prescribe reasoning order.)"
        if request.stage == "factorial_intermediate":
            if condition.role != "factorial":
                raise ValueError("only factorial arms may use the factorial intermediate")
            order = self.payload["factor_slots"]["order"][condition.order_factor]
            representation = self.payload["factor_slots"]["representation"][
                condition.representation_factor
            ]
            system = (
                "You are a bounded evidence-planning component.\n"
                f"Objective: {self.payload['factorial_intermediate']['objective']}\n"
                f"Shared information requirements:\n{requirements}\n"
                f"[ORDER_FACTOR] {order}\n"
                f"[REPRESENTATION_FACTOR] {representation}\n"
                f"Rules:\n{rules}"
            )
            if condition.representation_factor == "typed":
                system += "\nRepresentation format: follow the supplied typed response schema."
                response_schema = TypedPlanningIntermediateV3.model_json_schema()
            else:
                system += (
                    "\nRepresentation format: use each of these headings exactly once: "
                    + ", ".join(self.payload["plain_text_format"])
                    + ". Heading order is free unless the order factor explicitly constrains it."
                )
                response_schema = PlainPlanningIntermediateV3.model_json_schema()
        elif request.stage == "factorial_finalize":
            if condition.role != "factorial":
                raise ValueError("only factorial arms may use factorial finalization")
            stage = self.payload["factorial_finalize"]
            system = (
                "You are a bounded evidence-planning component.\n"
                f"Objective: {stage['objective']}\n"
                f"Ordering constraint: {stage['ordering_constraint']}\n"
                f"Shared information requirements:\n{requirements}\n"
                f"Rules:\n{rules}"
            )
            response_schema = CandidateArtifact.model_json_schema()
        elif request.stage in {"exide_v3_intermediate", "exide_v3_finalize"}:
            if condition.condition_id != "EXIDE_V3":
                raise ValueError("only EXIDE_V3 may use ExIde stages")
            stage = self.payload[request.stage]
            system = (
                "You are a bounded evidence-planning component.\n"
                f"Objective: {stage['objective']}\n"
                f"Ordering constraint: {stage['ordering_constraint']}\n"
                f"Rules:\n{rules}"
            )
            response_schema = (
                ExIdeP5DraftV3.model_json_schema()
                if request.stage == "exide_v3_intermediate"
                else CandidateArtifact.model_json_schema()
            )
        elif request.stage in {
            "document_first_v3_intermediate",
            "document_first_v3_finalize",
        }:
            if condition.condition_id != "DOCUMENT_FIRST_V3":
                raise ValueError("only DOCUMENT_FIRST_V3 may use document-first stages")
            stage = self.payload[request.stage]
            system = (
                "You are a bounded evidence-planning component.\n"
                f"Objective: {stage['objective']}\n"
                f"Ordering constraint: {stage['ordering_constraint']}\n"
                f"Rules:\n{rules}"
            )
            response_schema = (
                DocumentFirstDraftV3.model_json_schema()
                if request.stage == "document_first_v3_intermediate"
                else CandidateArtifact.model_json_schema()
            )
        else:
            raise ValueError(f"prompt bundle has no stage {request.stage!r}")

        # Condition IDs are intentionally absent from model-visible bytes.  The
        # runner retains them in its journal, but the model sees only the two
        # declared interventions.
        user_payload = {
            "observable_packet": request.packet,
            "prior_stage_outputs": request.prior_stage_outputs,
            "stage": request.stage,
        }
        return FactorialPromptRequestV3(
            messages=(
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        user_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ),
            response_schema=response_schema,
            prompt_bundle_sha256=self.digest,
            matched_template_sha256=self.matched_template_digest,
        )


def normalized_factorial_prompt_bytes(request: FactorialPromptRequestV3) -> bytes:
    """Remove only the declared treatment slots for byte-matching audits."""

    messages = [dict(message) for message in request.messages]
    system_lines = []
    for line in messages[0]["content"].splitlines():
        if line.startswith("[ORDER_FACTOR] "):
            system_lines.append("[ORDER_FACTOR] <ORDER>")
        elif line.startswith("[REPRESENTATION_FACTOR] "):
            system_lines.append("[REPRESENTATION_FACTOR] <REPRESENTATION>")
        elif line.startswith("Representation format: "):
            # The strict textual response grammar is part of the representation
            # intervention, not an undeclared semantic instruction.
            system_lines.append("<REPRESENTATION_SCHEMA_HELP>")
        else:
            system_lines.append(line)
    messages[0]["content"] = "\n".join(system_lines)
    payload = {
        "messages": messages,
        "response_schema": "<REPRESENTATION_SCHEMA>",
        "matched_template_sha256": request.matched_template_sha256,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

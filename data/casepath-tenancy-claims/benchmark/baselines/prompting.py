"""Frozen, condition-specific prompts with one shared observable boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.schema import CandidateArtifact
from manifests.digests import digest_json

from .base import StageRequest
from .stage_schema import draft_schema_for_stage

PROMPT_BUNDLE_PATH = Path(__file__).resolve().parent / "prompts" / "v1.json"


@dataclass(frozen=True)
class PromptRequest:
    messages: tuple[dict[str, str], ...]
    response_schema: dict[str, Any] | None
    prompt_bundle_sha256: str


class FrozenPromptBundle:
    def __init__(self, path: Path = PROMPT_BUNDLE_PATH) -> None:
        self.path = path.resolve()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("prompt bundle must be a JSON object")
        if payload.get("bundle_version") != "casepath.prompt-bundle/0.1.0":
            raise ValueError("unexpected prompt-bundle version")
        stages = payload.get("stages")
        shared_rules = payload.get("shared_rules")
        if not isinstance(stages, dict) or not isinstance(shared_rules, list):
            raise ValueError("prompt bundle is missing stages or shared rules")
        self.payload = payload
        self.digest = digest_json(payload)

    def render(self, request: StageRequest) -> PromptRequest:
        stages = self.payload["stages"]
        if request.stage not in stages:
            raise ValueError(f"prompt bundle has no stage {request.stage!r}")
        stage = stages[request.stage]
        rules = "\n".join(f"- {rule}" for rule in self.payload["shared_rules"])
        system = (
            "You are a bounded evidence-planning component.\n"
            f"Objective: {stage['objective']}\n"
            f"Ordering constraint: {stage['ordering_constraint']}\n"
            f"Rules:\n{rules}"
        )
        user_payload = {
            "condition_id": request.condition_id,
            "stage": request.stage,
            "observable_packet": request.packet,
            "prior_stage_outputs": request.prior_stage_outputs,
        }
        final_stage = request.stage in {
            "direct_finalize",
            "document_first_finalize",
            "evidence_from_process",
            "exide_finalize",
        }
        draft_schema = draft_schema_for_stage(request.stage)
        response_schema = (
            CandidateArtifact.model_json_schema()
            if final_stage
            else draft_schema.model_json_schema()
            if draft_schema is not None
            else None
        )
        return PromptRequest(
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
        )

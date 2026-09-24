"""Reviewed condition memories are suggestions derived from handler journal events."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from .workspace_corpus import digest_value

CONTRACT = "casepath.reviewed-condition-memory/1.0.0"


def statement_pattern(quote: str) -> str:
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError("a source quotation is required")
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", quote).casefold()))


def compile_reviewed_memory(
    claim_id: str, assessment: Mapping[str, Any], observation: Mapping[str, Any],
    handler: str,
) -> dict[str, Any]:
    if observation.get("kind") != "condition" or observation.get("withdrawn"):
        raise ValueError("an active handler condition assessment is required")
    flag = observation.get("target")
    condition = assessment.get("conditions", {}).get(flag)
    if not isinstance(condition, Mapping):
        raise ValueError("the reviewed condition is outside this claim")
    quote = condition.get("quote")
    if not isinstance(quote, str) or not quote:
        raise ValueError("the reviewed condition lacks an exact source quotation")
    note = observation.get("note")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("a handler note is required before keeping a memory")
    if not isinstance(handler, str) or not handler.strip() or len(handler) > 80:
        raise ValueError("the reviewing handler is required")
    material = {
        "contract": CONTRACT,
        "source_claim_id": claim_id,
        "source_handler_event_sha256": observation["event_sha256"],
        "family": assessment["claim_type"],
        "condition": flag,
        "statement_pattern": statement_pattern(quote),
        "source_quote": quote,
        "verdict": observation["verdict"],
        "note": note.strip(),
        "handler": handler.strip(),
        "status": "unverified",
    }
    return {**material, "memory_sha256": digest_value(material)}


def matches(memory: Mapping[str, Any], claim_id: str, assessment: Mapping[str, Any]) -> bool:
    condition = assessment.get("conditions", {}).get(memory.get("condition"))
    return bool(
        memory.get("source_claim_id") != claim_id
        and memory.get("family") == assessment.get("claim_type")
        and memory.get("status") == "unverified"
        and isinstance(condition, Mapping)
        and isinstance(condition.get("quote"), str)
        and statement_pattern(condition["quote"]) == memory.get("statement_pattern")
    )

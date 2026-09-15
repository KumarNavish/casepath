"""Channel-typed evidential state for the six-role agent workflow.

A span's epistemic channel is fixed by where its bytes came from, never by its content and never by
the model's judgement. The customer's own message is a *party report*: it can say that a record exists,
that the customer holds it, or what the customer remembers it saying, but it cannot make the record
received. An attached or later returned document is an *artifact*: it is in the workspace and can.

The product already carries the signal — ``SourceSpan.extraction`` is ``message_body`` exactly for the
customer message projection and a document extraction (``pdf_text``, ``office_text``, ``utf8``,
``image_metadata``) for every admitted artifact — so no new model output and no new schema is needed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

CONTRACT = "casepath.agent-work-evidential-channel/1.0.0"
PARTY_EXTRACTIONS = frozenset({"message_body"})
ARTIFACT_EXTRACTIONS = frozenset({"utf8", "pdf_text", "office_text", "image_metadata"})
#: Classes that assert the requested record is actually in hand.
RECEIPT_CLASSES = frozenset({"received"})
#: What an unsupported receipt is lowered to: the need is still live and still requested.
LOWERED_CLASS = "insufficient"


def channel_of_extraction(extraction: str | None) -> str:
    if extraction in PARTY_EXTRACTIONS:
        return "party_report"
    if extraction in ARTIFACT_EXTRACTIONS:
        return "artifact"
    return "party_report"


def span_channels(spans: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({channel_of_extraction(span.get("extraction")) for span in spans})


def supports_receipt(spans: Iterable[Mapping[str, Any]]) -> bool:
    """True only when at least one supporting span comes from an artifact in the workspace."""
    return any(channel_of_extraction(span.get("extraction")) == "artifact" for span in spans)


def gate_evidence_class(proposed_class: str, spans: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Cap a proposed evidence class by the channel of the evidence supporting it.

    Returns the decision; the caller records it as a gate result and uses ``final_class``.
    """
    spans = list(spans)
    channels = span_channels(spans)
    if proposed_class not in RECEIPT_CLASSES:
        return {"contract": CONTRACT, "proposed_class": proposed_class, "final_class": proposed_class,
                "capped": False, "support_channels": channels,
                "reason": "The class does not assert that the record is in hand."}
    if supports_receipt(spans):
        return {"contract": CONTRACT, "proposed_class": proposed_class, "final_class": proposed_class,
                "capped": False, "support_channels": channels,
                "reason": "An admitted artifact in this claim supports the receipt."}
    return {"contract": CONTRACT, "proposed_class": proposed_class, "final_class": LOWERED_CLASS,
            "capped": True, "support_channels": channels,
            "reason": ("Only the customer's own message supports this receipt. A party's account that a record "
                       "exists, is held, or says something does not put the record in the workspace.")
            if channels else "No source span supports this receipt."}

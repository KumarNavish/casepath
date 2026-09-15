from __future__ import annotations

from casepath_api.agent_work import evidential_channel as ch


def _span(extraction: str, quote: str = "x") -> dict:
    return {"extraction": extraction, "quote": quote}


def test_channel_is_fixed_by_extraction_not_by_content() -> None:
    assert ch.channel_of_extraction("message_body") == "party_report"
    for artifact in ("pdf_text", "office_text", "utf8", "image_metadata"):
        assert ch.channel_of_extraction(artifact) == "artifact"
    assert ch.channel_of_extraction(None) == "party_report"          # unknown is conservative
    assert ch.channel_of_extraction("something_new") == "party_report"


def test_identical_content_from_two_channels_yields_different_support() -> None:
    quote = "The termination notice is dated 3 March 2025."
    assert ch.supports_receipt([_span("message_body", quote)]) is False
    assert ch.supports_receipt([_span("pdf_text", quote)]) is True


def test_receipt_supported_only_by_the_customer_message_is_lowered() -> None:
    d = ch.gate_evidence_class("received", [_span("message_body", "I found the notice at home.")])
    assert d["capped"] is True and d["final_class"] == "insufficient"
    assert d["support_channels"] == ["party_report"]
    assert "does not put the record in the workspace" in d["reason"]


def test_receipt_supported_by_an_attachment_is_kept() -> None:
    d = ch.gate_evidence_class("received", [_span("message_body"), _span("pdf_text")])
    assert d["capped"] is False and d["final_class"] == "received"
    assert d["support_channels"] == ["artifact", "party_report"]


def test_non_receipt_classes_are_never_capped() -> None:
    for state in ("missing", "insufficient", "conditional", "irrelevant", "unknown"):
        d = ch.gate_evidence_class(state, [_span("message_body")])
        assert d["capped"] is False and d["final_class"] == state


def test_receipt_with_no_supporting_span_is_lowered() -> None:
    d = ch.gate_evidence_class("received", [])
    assert d["capped"] is True and d["final_class"] == "insufficient" and d["support_channels"] == []

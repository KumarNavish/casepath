"""The product gate must be per requirement, not per run.

Before this was fixed, the runtime offered every span the run had selected as support for any requirement,
so a single returned artifact anywhere in a claim lifted the cap on every requirement in it. The research
method never had that shortcut. These tests pin the corrected semantics.
"""
from __future__ import annotations

from casepath_api.agent_work import evidential_channel as ec

MESSAGE = {"source_id": "com_customer", "extraction": "message_body", "quote": "the report says the boiler failed"}
ARTIFACT_B = {"source_id": "doc_contractor", "extraction": "pdf_text", "quote": "diagnosis: seized motor"}
ARTIFACT_UNRELATED = {"source_id": "doc_photos", "extraction": "image_metadata", "quote": "IMG_0041"}


def test_a_requirement_supported_only_by_a_party_report_is_capped():
    decision = ec.gate_evidence_class("received", [MESSAGE])
    assert decision["capped"] is True
    assert decision["final_class"] == "insufficient"


def test_a_requirement_supported_by_its_own_returned_artifact_is_admitted():
    decision = ec.gate_evidence_class("received", [ARTIFACT_B])
    assert decision["capped"] is False
    assert decision["final_class"] == "received"


def test_an_unrelated_artifact_elsewhere_in_the_claim_does_not_admit_a_party_report():
    """The mandate's case: artifact for B present, requirement A rests on a message only.

    A's span set contains only its own message. Passing the run's whole span set instead — the old
    behaviour — is what the second assertion shows would have wrongly admitted it.
    """
    spans_for_a = [MESSAGE]
    assert ec.gate_evidence_class("received", spans_for_a)["capped"] is True

    whole_run = [MESSAGE, ARTIFACT_B, ARTIFACT_UNRELATED]
    assert ec.gate_evidence_class("received", whole_run)["capped"] is False, (
        "this documents the defect: with run-level spans the cap lifts for a requirement that has no "
        "artifact of its own, which is exactly why the runtime now scopes spans per requirement")


def test_two_requirements_in_one_claim_get_independent_answers():
    a = ec.gate_evidence_class("received", [MESSAGE])
    b = ec.gate_evidence_class("received", [ARTIFACT_B])
    assert (a["final_class"], b["final_class"]) == ("insufficient", "received")


def test_a_requirement_with_no_spans_at_all_is_capped():
    assert ec.gate_evidence_class("received", [])["capped"] is True


def test_a_class_that_was_never_a_receipt_is_untouched():
    for proposed in ("insufficient", "conditional", "missing"):
        assert ec.gate_evidence_class(proposed, [MESSAGE])["capped"] is False

"""Tests for B6, the minimal artifact gate used as the obvious-fix comparator.

The gate must be per document. A baseline that is right about one document must not have another document
credited for it, and an unrelated artifact elsewhere in the run must never license a credit.
"""
from __future__ import annotations

import pytest

from casepath_api import artifact_gate_v1 as gate


def actor(*returned, catalog=("A1", "A2", "A3")):
    sources = [{"id": "src-1", "paragraphs": [{"id": "p1", "text": "x"}]}]
    sources += [{"id": f"ret-{d}", "document_id": d, "paragraphs": [{"id": "p1", "text": "y"}]} for d in returned]
    return {"sources": sources, "document_catalog": [{"id": d, "description": d} for d in catalog]}


def plan(states, *, ready=False, action=None, pending=()):
    return {"document_states": [{"document_id": d, "state": s, "source_refs": []} for d, s in states],
            "checklist_document_ids": [], "requested_document_ids": [],
            "next_action": action or {"kind": "wait", "document_ids": []},
            "ready": ready, "justifications": [],
            "pending_deliveries": [{"document_id": d, "source_refs": [], "expected_at": None} for d in pending]}


def state_of(result, doc):
    return next(r["state"] for r in result["document_states"] if r["document_id"] == doc)


def test_a_credit_without_its_own_artifact_is_reset():
    out = gate.apply(actor(), plan([("A1", "received")]))
    assert state_of(out, "A1") == "missing"
    assert out["artifact_gate"]["downgraded"] == [{"document_id": "A1", "from": "received", "to": "missing"}]


def test_a_credit_with_its_own_artifact_is_untouched():
    out = gate.apply(actor("A1"), plan([("A1", "received")]))
    assert state_of(out, "A1") == "received"
    assert out["artifact_gate"]["downgraded"] == []


def test_the_gate_is_per_document_not_per_run():
    """An artifact for A2 must not license a credit for A1. This is the defect the product gate had."""
    out = gate.apply(actor("A2"), plan([("A1", "received"), ("A2", "received")]))
    assert state_of(out, "A1") == "missing", "A1 was credited on the strength of an unrelated artifact"
    assert state_of(out, "A2") == "received"


def test_insufficient_is_also_a_credit_and_is_reset():
    out = gate.apply(actor(), plan([("A1", "insufficient")]))
    assert state_of(out, "A1") == "missing"


@pytest.mark.parametrize("state", ["missing", "pending", "not_required"])
def test_uncredited_states_are_never_touched(state):
    out = gate.apply(actor(), plan([("A1", state)]))
    assert state_of(out, "A1") == state
    assert out["artifact_gate"]["downgraded"] == []


def test_a_promised_delivery_downgrades_to_pending_not_missing():
    out = gate.apply(actor(), plan([("A1", "received")], pending=("A1",)))
    assert state_of(out, "A1") == "pending"


def test_readiness_is_withdrawn_only_when_a_credit_was_reset():
    withdrawn = gate.apply(actor(), plan([("A1", "received")], ready=True,
                                         action={"kind": "proceed", "document_ids": []}))
    assert withdrawn["ready"] is False
    assert withdrawn["artifact_gate"]["withdrew_readiness"] is True

    kept = gate.apply(actor("A1"), plan([("A1", "received")], ready=True,
                                        action={"kind": "proceed", "document_ids": []}))
    assert kept["ready"] is True
    assert kept["artifact_gate"]["withdrew_readiness"] is False


def test_a_withdrawal_repoints_a_proceed_at_the_reopened_documents():
    out = gate.apply(actor(), plan([("A1", "received"), ("A2", "received")], ready=True,
                                   action={"kind": "proceed", "document_ids": []}))
    assert out["next_action"]["kind"] == "request"
    assert out["next_action"]["document_ids"] == out["requested_document_ids"] == ["A1", "A2"]


def test_a_repair_never_requests_more_than_the_turn_budget():
    out = gate.apply(actor(), plan([("A1", "received"), ("A2", "received"), ("A3", "received")], ready=True,
                                   action={"kind": "proceed", "document_ids": []}))
    assert len(out["requested_document_ids"]) == gate.MAX_REQUESTS == 2


def test_a_request_action_is_left_alone_when_readiness_was_never_claimed():
    original = {"kind": "request", "document_ids": ["A3"]}
    out = gate.apply(actor(), plan([("A1", "received")], ready=False, action=original))
    assert out["next_action"] == original
    assert out["artifact_gate"]["repaired_next_action"] is False


def test_the_gate_uses_only_identities_already_in_the_actor():
    a = actor("A1")
    out = gate.apply(a, plan([("A1", "received")]))
    assert out["artifact_gate"]["returned_document_ids"] == ["A1"]

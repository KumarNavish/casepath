from __future__ import annotations

from casepath_api import evidential_channel_v1 as ctes


def _actor(returned: bool = False, readable: str = "full"):
    sources = [
        {"id": "src-1", "paragraphs": [{"id": "p1", "text": "I found the signed notice at home; it shows the date 3 March."}]},
        {"id": "gov-1", "paragraphs": [{"id": "h1", "text": "Establish the signed notice date from the notice itself."}]},
    ]
    if returned:
        sources.append({"id": "ret-1", "document_id": "D1", "paragraphs": [{"id": "p1", "text": "Signed notice dated 3 March 2025."}]})
    return {"aware_at": "2025-03-03T09:00:00+01:00", "turn": 0, "sources": sources,
            "document_catalog": [{"id": "D1", "description": "Signed notice"}, {"id": "D2", "description": "Photos"}], "static_checklist_ids": ["D1"]}


def _raw(returned: bool):
    atts = [{"unit_ref": "src-1#p1", "requirement_id": "r1", "coverage": "full"}]
    if returned:
        atts.append({"unit_ref": "ret-1#p1", "requirement_id": "r1", "coverage": "full"})
    return {"requirements": [{"id": "r1", "description": "notice date", "satisfying_document_sets": [["D1"]], "critical": True, "standard": "observed", "active": True, "source_refs": ["gov-1#h1"]}],
            "attestations": atts,
            "mentions": [{"unit_ref": "src-1#p1", "document_id": "D1", "status": "possessed_by_customer", "holder": "customer"}],
            "readability": ([{"document_id": "D1", "value": "full"}] if returned else [])}


def test_party_report_cannot_satisfy_requirement_but_steers_request() -> None:
    actor = _actor(returned=False)
    reqs, atts, mentions, readability = ctes.parse_extraction(_raw(False), actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["ready"] is False
    assert state["document_states"]["D1"] == "missing"
    assert state["next_action"] == {"kind": "request", "document_ids": ["D1"]}
    assert state["availability"]["D1"] == "possessed_by_customer"
    assert state["document_states"]["D2"] == "not_required"


def test_ablation_without_channel_cap_declares_hearsay_readiness() -> None:
    actor = _actor(returned=False)
    reqs, atts, mentions, readability = ctes.parse_extraction(_raw(False), actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=False)
    assert state["ready"] is True
    assert state["next_action"]["kind"] == "proceed"


def test_returned_readable_artifact_satisfies_requirement() -> None:
    actor = _actor(returned=True)
    reqs, atts, mentions, readability = ctes.parse_extraction(_raw(True), actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["ready"] is True
    assert state["document_states"]["D1"] == "received"
    plan = ctes.plan_from_state(actor, state, reqs, atts, mentions, "ctes")
    assert plan["next_action"] == {"kind": "proceed", "document_ids": []}
    assert {row["document_id"] for row in plan["document_states"]} == {"D1", "D2"}


def test_unreadable_return_is_insufficient_and_rerequested() -> None:
    actor = _actor(returned=True)
    raw = _raw(True)
    raw["readability"] = [{"document_id": "D1", "value": "unreadable"}]
    raw["attestations"] = [a for a in raw["attestations"] if not a["unit_ref"].startswith("ret-")]
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["document_states"]["D1"] == "insufficient"
    assert state["ready"] is False
    assert state["next_action"]["kind"] == "request"


def test_promise_in_returned_partial_waits_but_hearsay_promise_does_not() -> None:
    actor = _actor(returned=True)
    raw = _raw(True)
    raw["readability"] = [{"document_id": "D1", "value": "partial"}]
    raw["attestations"] = [{"unit_ref": "ret-1#p1", "requirement_id": "r1", "coverage": "partial"}]
    raw["mentions"] = [{"unit_ref": "ret-1#p1", "document_id": "D1", "status": "automatic", "holder": "manager"}]
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True, prior_requests=["D1"])
    assert state["document_states"]["D1"] == "insufficient"
    assert state["next_action"]["kind"] == "wait"
    hearsay = _actor(returned=False)
    raw2 = _raw(False)
    raw2["mentions"] = [{"unit_ref": "src-1#p1", "document_id": "D1", "status": "automatic", "holder": "manager"}]
    reqs, atts, mentions, readability = ctes.parse_extraction(raw2, hearsay)
    state2 = ctes.compute_state(hearsay, reqs, atts, mentions, readability, channel_cap=True)
    assert state2["next_action"] == {"kind": "request", "document_ids": ["D1"]}
    assert state2["availability"]["D1"] == "exists"


def test_unknown_refs_are_dropped_and_never_grant_support() -> None:
    """An atom naming a unit outside the actor is discarded, not repaired and not honoured."""
    actor = _actor(returned=False)
    raw = _raw(False)
    raw["attestations"][0]["unit_ref"] = "src-9#p1"
    notes: dict = {}
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor, notes)
    assert atts == [] and notes["dropped_atoms"] == ["attestation:src-9#p1|r1|full"]
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["ready"] is False
    assert state["attained_levels"]["r1"] == 0


def test_unknown_document_ids_make_a_requirement_unsatisfiable_not_fatal() -> None:
    actor = _actor(returned=True)
    raw = _raw(True)
    raw["requirements"].append({"id": "r2", "description": "invented record", "satisfying_document_sets": [["GHOST"]],
                                "critical": True, "standard": "observed", "active": True, "source_refs": ["gov-1#h1"]})
    notes: dict = {}
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor, notes)
    assert notes["dropped_document_ids"] == ["GHOST"]
    assert reqs[1].satisfying_document_sets == []
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["satisfied"]["r2"] is False          # never satisfiable
    assert state["ready"] is False                    # blocks readiness
    assert "GHOST" not in state["next_action"]["document_ids"]   # and contributes no request


def test_single_document_cover_is_hedged_with_a_disjoint_alternative_route() -> None:
    """A lone authenticated export satisfying every open requirement must not consume the whole turn."""
    actor = {"aware_at": "2025-03-03T09:00:00+01:00", "turn": 0,
             "sources": [{"id": "src-1", "paragraphs": [{"id": "p1", "text": "The form is at home."}]},
                         {"id": "gov-1", "paragraphs": [{"id": "h1", "text": "Establish the form date and the basis."}]}],
             "document_catalog": [{"id": "C1", "description": "Signed form"}, {"id": "C4", "description": "Worksheet"}, {"id": "C5", "description": "Authenticated export"}],
             "static_checklist_ids": ["C1"]}
    raw = {"requirements": [
        {"id": "seq", "description": "form date", "satisfying_document_sets": [["C1"], ["C5"]], "critical": True, "standard": "observed", "active": True, "source_refs": ["gov-1#h1"]},
        {"id": "basis", "description": "starting basis", "satisfying_document_sets": [["C4"], ["C5"]], "critical": True, "standard": "observed", "active": True, "source_refs": ["gov-1#h1"]}],
        "attestations": [], "mentions": [{"unit_ref": "src-1#p1", "document_id": "C1", "status": "possessed_by_customer", "holder": "customer"}], "readability": []}
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True, hedge_spare_slot=True)
    ids = state["next_action"]["document_ids"]
    assert ids[0] == "C5"                 # the cover still leads
    assert len(ids) == 2 and ids[1] in {"C1", "C4"}   # and the spare slot hedges on a disjoint route


def test_invalid_atoms_are_dropped_conservatively_not_fatal() -> None:
    actor = _actor(returned=True)
    raw = _raw(True)
    raw["attestations"].append({"unit_ref": "ghost#p9", "requirement_id": "r1", "coverage": "full"})
    raw["mentions"].append({"unit_ref": "src-1#p1", "document_id": "NOPE", "status": "promised"})
    raw["readability"].append({"document_id": "D1", "value": "who-knows"})
    notes: dict = {}
    reqs, atts, mentions, readability = ctes.parse_extraction(raw, actor, notes)
    assert len(notes["dropped_atoms"]) == 3
    assert all(a.unit_ref in {"src-1#p1", "ret-1#p1"} for a in atts)
    state = ctes.compute_state(actor, reqs, atts, mentions, readability, channel_cap=True)
    assert state["ready"] is True          # the valid returned-artifact attestation still stands

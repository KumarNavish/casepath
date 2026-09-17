from casepath_api import evidence_overlay_v1 as base
from casepath_api import evidence_overlay_v3 as overlay


def prepared():
    refinement = {"refinement": {"rules": [{
        "rule_id": "r1", "parent_node_id": "n1", "requirement_kind": "obligation",
        "condition": "special branch applies", "condition_supported_by": ["p-cond"],
        "requirement": "establish branch-specific loss", "supported_by": ["p-req"],
        "facts": [{"fact_id": "f1", "statement": "branch loss amount",
                   "from_propositions": ["p-req"],
                   "capabilities": [{"capability_id": "c1", "must_show": "loss amount",
                                     "from_propositions": ["p-req"]}]}],
    }], "non_evidentiary": []}, "verification": {"ok": True}}
    materialized = base.materialize(refinement)
    cap = materialized["compiled"][0]["facts"][0]["capabilities"][0]["capability_id"]
    return {"contract": "test", "overlay": materialized,
            "catalogue": ["branch proof", "branch result"],
            "resolvers": [{"capability_id": "resolver.overlay_rule_001"}],
            "requirements": [
                {"capability_id": cap, "routes": [{"route_id": "req", "document_types": ["branch result"]}]},
                {"capability_id": "resolver.overlay_rule_001",
                 "routes": [{"route_id": "confirm", "document_types": ["branch proof"]}]},
            ], "problems": []}


def decision(verdict):
    return {"verdicts": {"overlay_guard_001": {"verdict": verdict,
             "quote": "q" if verdict != "unresolved" else None,
             "source_ref": "customer_message" if verdict != "unresolved" else None,
             "what_would_settle_it": "state whether the branch applies"}},
            "ungrounded": [], "exclusive_groups": {}}


def test_unresolved_branch_is_question_not_document_request():
    plan = overlay.plan_case(case={"customer_message": "unknown"}, prepared=prepared(), held=[],
                             decided=decision("unresolved"))
    assert plan["documents"] == []
    assert plan["counts"]["state_questions"] == 1
    assert plan["next_action"]["type"] == "resolve_process_state"
    assert plan["next_action"]["guard_id"] == "overlay_guard_001"


def test_true_unconfirmed_branch_requests_confirmation_and_active_evidence():
    plan = overlay.plan_case(case={"customer_message": "q"}, prepared=prepared(), held=[],
                             decided=decision("true"))
    assert set(plan["documents"]) == {"branch proof", "branch result"}
    assert plan["counts"]["confirmation_chains"] == 1
    assert plan["counts"]["active_requirement_chains"] == 1


def test_true_confirmed_branch_does_not_re_request_confirmation():
    plan = overlay.plan_case(case={"customer_message": "q"}, prepared=prepared(), held=[],
                             decided=decision("true"),
                             confirmed_guard_ids=["overlay_guard_001"])
    assert plan["documents"] == ["branch result"]
    assert plan["counts"]["confirmation_chains"] == 0


def test_false_branch_requests_nothing():
    plan = overlay.plan_case(case={"customer_message": "q"}, prepared=prepared(), held=[],
                             decided=decision("false"))
    assert plan["documents"] == []
    assert not plan["active_requirement_chains"]
    assert not plan["confirmation_chains"]

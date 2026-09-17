import json

from casepath_api import evidence_overlay_v1 as eo


def refinement():
    raw = {
        "rules": [{
            "rule_id": "r1",
            "parent_node_id": "macro_parent",
            "requirement_kind": "obligation",
            "condition": "a bicycle is claimed",
            "condition_supported_by": ["p1"],
            "requirement": "provide bicycle value evidence",
            "supported_by": ["p1"],
            "facts": [{
                "fact_id": "f1",
                "statement": "the bicycle's value",
                "from_propositions": ["p1"],
                "capabilities": [{"capability_id": "c1", "must_show": "the bicycle purchase value", "from_propositions": ["p1"]}],
            }],
        }],
        "non_evidentiary": [],
    }
    return {"refinement": raw, "verification": {"ok": True}}
def prepared():
    overlay = eo.materialize(refinement())
    return {
        "contract": eo.CONTRACT,
        "overlay": overlay,
        "catalogue": ["bicycle receipt", "claim form"],
        "resolvers": [{"capability_id": "resolver.overlay_rule_001"}],
        "requirements": [
            {"capability_id": "overlay_rule_001.f01.c01", "routes": [{"route_id": "r1", "document_types": ["bicycle receipt"]}]},
            {"capability_id": "resolver.overlay_rule_001", "routes": [{"route_id": "r2", "document_types": ["claim form"]}]},
        ],
        "problems": [],
    }


def call_with(verdict, quote=None):
    def call(system, user):
        return json.dumps({"verdicts": [{
            "guard_id": "overlay_guard_001",
            "verdict": verdict,
            "quote": quote,
            "source_ref": "customer_message" if quote else None,
            "what_would_settle_it": None if verdict != "unresolved" else "state whether a bicycle is claimed",
        }]})
    return call
def test_active_rule_requests_requirement_without_macro_parent_gating():
    text = "A bicycle is claimed."
    plan = eo.plan_case(case={"customer_message": text}, prepared=prepared(), held=[],
                        call=call_with("true", text))
    assert plan["documents"] == ["bicycle receipt"]
    assert plan["next_action"]["type"] == "satisfy_active_requirement"
    assert plan["requests"][0]["justified_by"][0]["process_node"] == "macro_parent"


def test_false_rule_requests_nothing():
    text = "No bicycle is claimed."
    plan = eo.plan_case(case={"customer_message": text}, prepared=prepared(), held=[],
                        call=call_with("false", text))
    assert plan["documents"] == []
    assert plan["next_action"] is None


def test_unresolved_rule_requests_only_state_resolver():
    plan = eo.plan_case(case={"customer_message": "The loss is described."}, prepared=prepared(), held=[],
                        call=call_with("unresolved"))
    assert plan["documents"] == ["claim form"]
    assert plan["next_action"]["type"] == "resolve_process_state"
    assert not plan["active_requirement_chains"]
    assert plan["resolver_chains"]


def test_precomputed_guard_decision_requires_no_model_call():
    decision = {"verdicts": {"overlay_guard_001": {
        "verdict": "true", "quote": "A bicycle is claimed.",
        "source_ref": "customer_message", "what_would_settle_it": None,
    }}, "ungrounded": [], "exclusive_groups": {}}
    plan = eo.plan_case(case={"customer_message": "A bicycle is claimed."}, prepared=prepared(),
                        held=[], decided=decision)
    assert plan["documents"] == ["bicycle receipt"]

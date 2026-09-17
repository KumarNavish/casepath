import json

import pytest

from casepath_api import casepath_process_service_v2 as service


PROPOSITIONS = [{
    "proposition_id": "p1", "source_id": "src", "quote": "receipt",
}]
PASSAGES = [{
    "authority_id": "src", "article": "A.1",
    "exact_text": "For a bicycle claim, provide the receipt.",
    "source_url": "https://example.test/policy", "text_sha256": "abc",
}]


def prepared():
    overlay = {
        "guards": [{
            "guard_id": "overlay_guard_001", "statement": "a bicycle is claimed",
            "supported_by": ["p1"], "support": "supported", "exclusive_group": None,
        }],
        "rules": [{
            "rule_id": "overlay_rule_001", "parent_node_id": "macro_bicycle",
            "requirement_kind": "obligation", "requirement": "provide bicycle evidence",
            "guard_id": "overlay_guard_001", "condition": "a bicycle is claimed",
            "supported_by": ["p1"], "condition_supported_by": ["p1"],
        }],
        "compiled": [{"node_id": "overlay_rule_001", "facts": [{
            "fact_id": "overlay_rule_001.f01", "node_id": "macro_bicycle",
            "guard_id": "overlay_guard_001", "statement": "the bicycle purchase",
            "from_propositions": ["p1"],
            "capabilities": [{"capability_id": "overlay_rule_001.f01.c01",
                              "must_show": "the bicycle purchase value",
                              "from_propositions": ["p1"]}],
        }], "problems": []}],
    }
    return {
        "contract": "casepath.evidence-overlay-rich-map/1.0.0",
        "overlay": overlay,
        "catalogue": ["bicycle receipt", "claim form"],
        "resolvers": [{"capability_id": "resolver.overlay_rule_001",
                       "rule_id": "overlay_rule_001", "guard_id": "overlay_guard_001"}],
        "requirements": [
            {"capability_id": "overlay_rule_001.f01.c01",
             "routes": [{"route_id": "r1", "document_types": ["bicycle receipt"]}]},
            {"capability_id": "resolver.overlay_rule_001",
             "routes": [{"route_id": "r2", "document_types": ["claim form"]}]},
        ],
        "problems": [],
    }


def call_with(verdict: str, quote: str | None):
    def call(_, user):
        guard_id = json.loads(user)["guard"]["guard_id"]
        return json.dumps({
            "guard_id": guard_id, "verdict": verdict, "quote": quote,
            "source_ref": "customer_message" if quote else None,
            "what_would_settle_it": None if verdict != "unresolved" else "state whether a bicycle is claimed",
        })
    return call


def test_product_exposes_complete_chain():
    text = "A bicycle is claimed."
    plan = service.plan_claim(
        prepared=prepared(),
        propositions=PROPOSITIONS,
        passages=PASSAGES,
        case={"customer_message": text},
        already_held=[],
        call=call_with("true", text),
        workers=1,
    )
    assert plan["documents"] == ["bicycle receipt"]
    justification = plan["requests"][0]["justified_by"][0]
    assert justification["process_node"] == "macro_bicycle"
    assert justification["guard_id"] == "overlay_guard_001"
    assert justification["fact"] == "the bicycle purchase"
    assert justification["must_show"] == "the bicycle purchase value"
    assert justification["authorities"] == ["p1"]


def test_product_requests_state_resolver_when_guard_is_open():
    plan = service.plan_claim(
        prepared=prepared(),
        propositions=PROPOSITIONS,
        passages=PASSAGES,
        case={"customer_message": "A theft is reported."},
        already_held=[],
        call=call_with("unresolved", None),
        workers=1,
    )
    assert plan["documents"] == ["claim form"]
    assert plan["next_action"]["type"] == "resolve_process_state"
    assert plan["requests"][0]["justified_by"][0]["purpose"] == "resolve_process_state"


def test_product_diff_attributes_change_to_guard():
    false_text = "No bicycle is claimed."
    true_text = "A bicycle is claimed."
    before = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES, case={"customer_message": false_text}, already_held=[],
        call=call_with("false", false_text), workers=1)
    after = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES, case={"customer_message": true_text}, already_held=[],
        call=call_with("true", true_text), workers=1)
    diff = service.diff_plans(before, after)
    assert diff["changed_guards"] == [{"guard_id": "overlay_guard_001", "from": "false", "to": "true"}]
    assert diff["added"][0]["document"] == "bicycle receipt"
    assert diff["added"][0]["attributed_to_changed_guard"]


def test_product_rejects_orphan_request():
    with pytest.raises(ValueError, match="orphan"):
        service._validate_requests([{"still_missing": ["x"], "justified_by": []}])

import json

import pytest

from casepath_api import casepath_process_service_v3 as service

PROPOSITIONS = [{"proposition_id": "p1", "source_id": "src", "quote": "receipt"}]
PASSAGES = [{
    "authority_id": "src", "article": "A.1",
    "exact_text": "For a bicycle claim, provide the receipt.",
    "source_url": "https://example.test/policy", "text_sha256": "abc",
}]


def prepared():
    overlay = {
        "guards": [{"guard_id": "overlay_guard_001", "statement": "a bicycle is claimed",
                    "supported_by": ["p1"], "support": "supported", "exclusive_group": None}],
        "rules": [{"rule_id": "overlay_rule_001", "parent_node_id": "macro_bicycle",
                   "requirement_kind": "obligation", "requirement": "provide bicycle evidence",
                   "guard_id": "overlay_guard_001", "condition": "a bicycle is claimed",
                   "supported_by": ["p1"], "condition_supported_by": ["p1"]}],
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
        "contract": "casepath.evidence-overlay/3.0.0", "overlay": overlay,
        "catalogue": ["bicycle receipt", "claim form"],
        "resolvers": [{"capability_id": "resolver.overlay_rule_001",
                       "rule_id": "overlay_rule_001", "guard_id": "overlay_guard_001"}],
        "requirements": [
            {"capability_id": "overlay_rule_001.f01.c01",
             "routes": [{"route_id": "r1", "document_types": ["bicycle receipt"]}]},
            {"capability_id": "resolver.overlay_rule_001",
             "routes": [{"route_id": "r2", "document_types": ["claim form"]}]},
        ], "problems": [],
    }


def call_with(verdict: str, quote: str | None):
    def call(_, user):
        payload = json.loads(user)
        rows = []
        for case in payload["cases"]:
            rows.append({
                "unit_id": case["unit_id"], "verdict": verdict, "quote": quote,
                "source_ref": "customer_message" if quote else None,
                "what_would_settle_it": None if verdict != "unresolved" else "state whether a bicycle is claimed",
            })
        return json.dumps({"results": rows})
    return call


def request_for(plan, document):
    return next(request for request in plan["requests"] if document in request["still_missing"])


def test_true_branch_uses_v4_interpreter_and_v3_planner():
    text = "A bicycle is claimed."
    plan = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES,
        case={"customer_message": text}, already_held=[],
        call=call_with("true", text), workers=1)
    assert "bicycle receipt" in plan["documents"]
    req = request_for(plan, "bicycle receipt")
    justification = next(j for j in req["justified_by"] if j["purpose"] == "satisfy_active_requirement")
    assert justification["process_node"] == "macro_bicycle"
    assert justification["guard_id"] == "overlay_guard_001"


def test_unresolved_branch_is_question_not_document_leak():
    plan = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES,
        case={"customer_message": "A theft is reported."}, already_held=[],
        call=call_with("unresolved", None), workers=1)
    assert plan["documents"] == []
    assert plan["requests"] == []
    assert plan["next_action"]["type"] == "resolve_process_state"
    assert plan["next_action"]["guard_id"] == "overlay_guard_001"
    assert len(plan["state_questions"]) == 1


def test_diff_attributes_active_branch_documents():
    false_text, true_text = "No bicycle is claimed.", "A bicycle is claimed."
    before = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES,
        case={"customer_message": false_text}, already_held=[], call=call_with("false", false_text), workers=1)
    after = service.plan_claim(
        prepared=prepared(), propositions=PROPOSITIONS, passages=PASSAGES,
        case={"customer_message": true_text}, already_held=[], call=call_with("true", true_text), workers=1)
    diff = service.diff_plans(before, after)
    added = {row["document"]: row for row in diff["added"]}
    assert added["bicycle receipt"]["attributed_to_changed_guard"]
    assert diff["changed_guards"] == [{"guard_id": "overlay_guard_001", "from": "false", "to": "true"}]


def test_product_rejects_orphan_request():
    with pytest.raises(ValueError, match="orphan"):
        service._validate_requests([{"still_missing": ["x"], "justified_by": []}])

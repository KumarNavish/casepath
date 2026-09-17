import json

from casepath_api import two_tier_planner_v1 as tp


def fixture():
    graph = {
        "nodes": [
            {"node_id": "root", "label": "review", "kind": "decision"},
            {"node_id": "repair", "label": "prior repair consent", "kind": "decision", "supported_by": ["p1"]},
        ],
        "transitions": [{"edge_id": "e1", "source_node_id": "root", "target_node_id": "repair",
                         "condition": "repair cost exceeds CHF 500", "supported_by": ["p1"]}],
        "obligations": [],
    }
    props = {"p1": {"proposition_id": "p1", "source_id": "s1", "kind": "condition", "statement": "consent required"}}
    prepared = {
        "compiled": [{"node_id": "repair", "facts": [{"fact_id": "repair.f1", "statement": "prior consent exists",
            "only_if": "repair cost exceeds CHF 500", "from_propositions": ["p1"],
            "capabilities": [{"capability_id": "repair.c1", "must_show": "prior insurer consent", "from_propositions": ["p1"]}]}]}],
        "resolvers": [{"capability_id": "resolver.e1", "edge_id": "e1", "source_node_id": "root", "target_node_id": "repair",
            "must_show": "whether repair cost exceeds CHF 500", "condition": "repair cost exceeds CHF 500", "from_propositions": ["p1"]}],
        "requirements": [
            {"capability_id": "repair.c1", "routes": [{"route_id": "r1", "document_types": ["insurer_consent"]}]},
            {"capability_id": "resolver.e1", "routes": [{"route_id": "r2", "document_types": ["repair_estimate"]}]},
        ],
    }
    return graph, props, prepared
def fake_call(system, user):
    payload = json.loads(user)
    text = " ".join(payload.get("case_materials", {}).values())
    if "over" in text:
        verdict, quote = "true", "over"
    elif "under" in text:
        verdict, quote = "false", "under"
    else:
        verdict, quote = "unresolved", None
    return json.dumps({"verdicts": [{"predicate_id": "e1", "verdict": verdict, "quote": quote,
                                      "source_ref": "case", "what_would_settle_it": "repair estimate"}]})


def test_unresolved_requests_branch_resolver_only():
    graph, props, prepared = fixture()
    out = tp.plan_case(graph=graph, propositions=props, case={"message": "repair cost unknown"},
                       prepared=prepared, held=[], call=fake_call)
    assert out["documents"] == ["repair_estimate"]
    assert out["next_action"]["type"] == "resolve_process_state"


def test_true_requests_active_requirement_not_resolver():
    graph, props, prepared = fixture()
    out = tp.plan_case(graph=graph, propositions=props, case={"message": "repair cost over CHF 500"},
                       prepared=prepared, held=[], call=fake_call)
    assert out["documents"] == ["insurer_consent"]
    assert out["next_action"]["type"] == "satisfy_active_requirement"
def test_false_requests_neither_branch_resolver_nor_requirement():
    graph, props, prepared = fixture()
    out = tp.plan_case(graph=graph, propositions=props, case={"message": "repair cost under CHF 500"},
                       prepared=prepared, held=[], call=fake_call)
    assert out["documents"] == []
    assert out["next_action"] is None

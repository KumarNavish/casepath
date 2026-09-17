from casepath_api import state_refinement_v1 as sr


def fixture():
    graph = {"nodes": [{"node_id": "n1", "label": "review", "kind": "decision"}], "transitions": [], "obligations": []}
    props = [
        {"proposition_id": "p1", "kind": "condition", "statement": "consent is required if repair cost exceeds 500"},
        {"proposition_id": "p2", "kind": "deadline", "statement": "notification must occur within 24 hours"},
        {"proposition_id": "p3", "kind": "obligation", "statement": "notify insurer"},
    ]
    return graph, props


def test_verify_requires_all_target_propositions():
    graph, props = fixture()
    raw = {"rules": [{"rule_id": "s1", "parent_node_id": "n1", "source_supported_by": ["p1"],
                       "kind": "state_test", "case_condition": "repair cost exceeds 500",
                       "required_fact": "insurer consent exists", "must_show": "prior insurer consent",
                       "effect": "repair may proceed"}], "non_evidentiary": []}
    out = sr.verify(raw, graph, props)
    assert not out["ok"]
    assert out["missing"] == ["p2"]
def test_verified_state_rule_augments_graph_and_compiled_fact():
    graph, props = fixture()
    raw = {"rules": [
        {"rule_id": "s1", "parent_node_id": "n1", "source_supported_by": ["p1"],
         "kind": "state_test", "case_condition": "repair cost exceeds 500",
         "required_fact": "insurer consent exists", "must_show": "prior insurer consent",
         "effect": "repair consent becomes required"},
        {"rule_id": "s2", "parent_node_id": "n1", "source_supported_by": ["p2"],
         "kind": "deadline", "case_condition": "a SIM-card theft is claimed",
         "required_fact": "notification occurred within 24 hours", "must_show": "the theft and notification timestamps",
         "effect": "coverage depends on timely notification"},
    ], "non_evidentiary": []}
    verification = sr.verify(raw, graph, props)
    assert verification["ok"]
    out = sr.augment_graph(graph, {"refinement": raw, "verification": verification})
    assert len(out["nodes"]) == 3
    assert len(sr.compiled_rules(out)) == 2
    assert out["transitions"][-1]["condition"] == "a SIM-card theft is claimed"

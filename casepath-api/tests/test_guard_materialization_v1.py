from casepath_api import guard_materialization_v1 as gm
from casepath_api import case_interpreter_v2 as ci


def test_materializes_macro_and_evidence_conditions_as_guards():
    macro = {
        "nodes": [{"node_id": "a", "label": "A", "kind": "step"},
                  {"node_id": "b", "label": "B", "kind": "step"}],
        "transitions": [{"edge_id": "e1", "source_node_id": "a", "target_node_id": "b",
                         "condition": "a bicycle is claimed", "supported_by": ["p1"]}],
        "obligations": [], "deadlines": []}
    refinement = {"verification": {"ok": True}, "refinement": {"rules": [{
        "rule_id": "r1", "parent_node_id": "b", "condition": "repair exceeds threshold",
        "condition_supported_by": ["p2"], "requirement": "establish insurer consent",
        "supported_by": ["p2"], "requirement_kind": "coverage_condition",
        "facts": [{"statement": "consent exists", "from_propositions": ["p2"],
                   "capabilities": [{"must_show": "consent", "from_propositions": ["p2"]}]}]}],
        "non_evidentiary": []}}
    graph = gm.materialize(macro, refinement)
    assert graph["grounding_problems"] == []
    assert len(graph["guards"]) == 2
    assert graph["transitions"][0]["guard_id"]
    compiled = gm.compiled_rules(graph)
    assert compiled[0]["facts"][0]["guard_ids"]


def test_materialized_guard_controls_reachability():
    macro = {"nodes": [{"node_id": "a", "label": "A", "kind": "step"},
                       {"node_id": "b", "label": "B", "kind": "step"}],
             "transitions": [{"edge_id": "e1", "source_node_id": "a", "target_node_id": "b",
                              "condition": "special branch", "supported_by": ["p1"]}],
             "obligations": [], "deadlines": []}
    refinement = {"verification": {"ok": True}, "refinement": {"rules": [], "non_evidentiary": []}}
    graph = gm.materialize(macro, refinement)
    gid = graph["transitions"][0]["guard_id"]
    state_false = ci.activate(graph, {gid: {"verdict": "false"}})
    state_unresolved = ci.activate(graph, {gid: {"verdict": "unresolved"}})
    assert state_false["b"] == "inactive"
    assert state_unresolved["b"] == "unresolved"


def test_capability_ids_are_unique_across_multiple_facts_in_one_rule():
    macro = {"nodes": [{"node_id": "a", "label": "A", "kind": "step"}],
             "transitions": [], "obligations": [], "deadlines": []}
    refinement = {"verification": {"ok": True}, "refinement": {"rules": [{
        "rule_id": "r", "parent_node_id": "a", "condition": None,
        "condition_supported_by": [], "requirement": "R", "supported_by": ["p"],
        "requirement_kind": "obligation", "facts": [
            {"statement": "f1", "from_propositions": ["p"], "capabilities": [{"must_show": "x", "from_propositions": ["p"]}]},
            {"statement": "f2", "from_propositions": ["p"], "capabilities": [{"must_show": "y", "from_propositions": ["p"]}]},
        ]}], "non_evidentiary": []}}
    graph = gm.materialize(macro, refinement)
    ids = [c["capability_id"] for item in gm.compiled_rules(graph) for f in item["facts"] for c in f["capabilities"]]
    assert len(ids) == len(set(ids)) == 2
    assert graph["grounding_problems"] == []

import json

from casepath_api import case_interpreter_v2 as ci
from casepath_api import obligation_compiler_v2 as oc
from casepath_api import process_induction_v2 as pi

GRAPH = {
    "guards": [{"guard_id": "g_bike", "statement": "a bicycle is among the stolen items",
                "supported_by": ["p1"], "support": "supported", "exclusive_group": None}],
    "nodes": [
        {"node_id": "root", "label": "receive claim", "kind": "step", "guard_ids": [],
         "supported_by": ["p1"], "support": "supported"},
        {"node_id": "bike", "label": "determine bicycle particulars", "kind": "decision", "guard_ids": [],
         "supported_by": ["p1"], "support": "supported"},
    ],
    "transitions": [{"edge_id": "e1", "source_node_id": "root", "target_node_id": "bike",
                     "guard_id": "g_bike", "supported_by": ["p1"], "support": "supported"}],
    "deadlines": [],
    "obligations": [{"obligation_id": "o1", "node_id": "bike", "party": "claimant",
                     "statement": "establish bicycle particulars", "guard_ids": ["g_bike"],
                     "supported_by": ["p1"], "support": "supported"}],
    "unsupported_gaps": [],
}
PROPS = {"p1": {"proposition_id": "p1", "source_id": "s1", "kind": "obligation",
                "statement": "Bicycle particulars are required when a bicycle is claimed."}}
COMPILED = [{"node_id": "bike", "facts": [{"fact_id": "bike.f1", "node_id": "bike",
    "statement": "the bicycle identity", "guard_ids": ["g_bike"], "from_propositions": ["p1"],
    "capabilities": [{"capability_id": "bike.c1", "must_show": "shows bicycle identity",
                      "from_propositions": ["p1"]}]}]}]
REQS = [{"capability_id": "bike.c1", "routes": [{"route_id": "r1", "document_types": ["bicycle_receipt"]}]}]


def verdict(value):
    return {"g_bike": {"verdict": value, "quote": None}}


def test_true_guard_activates_document_chain():
    state = ci.activate(GRAPH, verdict("true"))
    assert state == {"root": "active", "bike": "active"}
    chains = oc.build_chains(GRAPH, state, verdict("true"), COMPILED, REQS, PROPS)
    assert chains["counts"]["clean"] == 1
    assert oc.checklist(chains)["requests"][0]["document_types"] == ["bicycle_receipt"]


def test_false_guard_retracts_document_chain():
    state = ci.activate(GRAPH, verdict("false"))
    assert state["bike"] == "inactive"
    chains = oc.build_chains(GRAPH, state, verdict("false"), COMPILED, REQS, PROPS)
    assert chains["counts"]["wrong_branch"] == 1
    assert oc.checklist(chains)["requests"] == []
def test_unresolved_guard_is_premature_not_requestable():
    state = ci.activate(GRAPH, verdict("unresolved"))
    assert state["bike"] == "unresolved"
    chains = oc.build_chains(GRAPH, state, verdict("unresolved"), COMPILED, REQS, PROPS)
    assert chains["counts"]["premature"] == 1
    assert oc.checklist(chains)["requests"] == []


def test_unquoted_decision_reverts_to_unresolved():
    def call(system, user):
        return json.dumps({"verdicts": [{"guard_id": "g_bike", "verdict": "true", "quote": "not present"}]})
    out = ci.decide(GRAPH, {"customer_message": "No bicycle is mentioned."}, call)
    assert out["verdicts"]["g_bike"]["verdict"] == "unresolved"
    assert out["ungrounded"]


def test_graph_validator_rejects_unknown_guard_reference():
    bad = json.loads(json.dumps(GRAPH))
    bad["obligations"][0]["guard_ids"] = ["g_missing"]
    validated = pi.validate_graph(bad, list(PROPS.values()), "test")
    assert any("unknown guards" in problem for problem in validated["grounding_problems"])


def test_graph_validator_reports_unused_guard():
    bad = json.loads(json.dumps(GRAPH))
    bad["guards"].append({"guard_id": "g_unused", "statement": "unused", "supported_by": ["p1"],
                          "support": "supported", "exclusive_group": None})
    validated = pi.validate_graph(bad, list(PROPS.values()), "test")
    assert any("unused guards" in problem for problem in validated["grounding_problems"])

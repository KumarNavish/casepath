from casepath_api import evidence_refinement_v1 as er


def test_verifier_rejects_silent_omission():
    graph = {"nodes": [{"node_id": "n", "label": "N", "kind": "step"}]}
    props = [{"proposition_id": "p1", "kind": "obligation", "statement": "show X"}]
    report = er.verify({"rules": [], "non_evidentiary": []}, graph, props)
    assert not report["ok"]
    assert report["missing"] == ["p1"]


def test_verifier_accepts_guarded_rule_and_augment():
    graph = {"nodes": [{"node_id": "n", "label": "N", "kind": "step"}], "transitions": [], "obligations": []}
    props = [
        {"proposition_id": "p1", "kind": "obligation", "statement": "show X"},
        {"proposition_id": "p2", "kind": "condition", "statement": "if Y"},
    ]
    raw = {"rules": [{"rule_id": "r", "parent_node_id": "n", "condition": "Y",
        "condition_supported_by": ["p2"], "obligation": "show X", "obligation_supported_by": ["p1"],
        "facts": [{"statement": "X", "from_propositions": ["p1"],
                   "capabilities": [{"must_show": "X", "from_propositions": ["p1"]}]}]}],
        "non_evidentiary": []}
    report = er.verify(raw, graph, props)
    assert report["ok"] and report["covered_once"] == 1
    refined = er.augment_graph(graph, {"refinement": raw, "verification": report})
    assert refined["transitions"][0]["condition"] == "Y"
    assert refined["evidence_refinement"]["compiled"][0]["facts"][0]["only_if"] == "Y"

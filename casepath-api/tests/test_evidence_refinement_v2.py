from casepath_api import evidence_refinement_v2 as er


def test_v2_requires_every_proposition_accounted():
    graph = {"nodes": [{"node_id": "n", "label": "N", "kind": "step"}]}
    props = [{"proposition_id": "p1", "kind": "condition", "statement": "if X"}]
    report = er.verify({"rules": [], "non_evidentiary": []}, graph, props)
    assert not report["ok"] and report["missing"] == ["p1"]


def test_v2_accepts_condition_as_evidence_requirement():
    graph = {"nodes": [{"node_id": "n", "label": "N", "kind": "step"}], "transitions": [], "obligations": []}
    props = [{"proposition_id": "p1", "kind": "condition", "statement": "cover only if X"}]
    raw = {"rules": [{"rule_id": "r1", "parent_node_id": "n", "requirement_kind": "coverage_condition",
        "condition": "X is at issue", "condition_supported_by": ["p1"], "requirement": "establish X",
        "supported_by": ["p1"], "facts": [{"statement": "X", "from_propositions": ["p1"],
        "capabilities": [{"must_show": "X", "from_propositions": ["p1"]}]}]}], "non_evidentiary": []}
    report = er.verify(raw, graph, props)
    assert report["ok"] and report["accounted"] == 1
    refined = er.augment_graph(graph, {"refinement": raw, "verification": report})
    assert refined["transitions"][0]["condition"] == "X is at issue"


def test_v2_repair_closes_missing_propositions_without_cases():
    graph = {"nodes": [{"node_id": "n", "label": "Notify insurer", "kind": "step"}], "transitions": [], "obligations": []}
    props = [
        {"proposition_id": "p1", "source_id": "s1", "kind": "allowed_action", "statement": "Insurer may set a deadline.", "quote": "may set a deadline", "party": "insurer", "governs": "deadline", "citation": "c1"},
        {"proposition_id": "p2", "source_id": "s2", "kind": "condition", "statement": "Costs are covered if ordered by insurer.", "quote": "covered if ordered", "party": "insurer", "governs": "costs", "citation": "c2"},
    ]
    current = {"rules": [], "non_evidentiary": []}
    def call(_system, user):
        payload = __import__("json").loads(user)
        assert {p["proposition_id"] for p in payload["missing_propositions"]} == {"p1", "p2"}
        return __import__("json").dumps({"new_rules": [
            {"rule_id": "repair_r1", "parent_node_id": "n", "requirement_kind": "deadline_condition",
             "condition": "the insurer set a deadline", "condition_supported_by": ["p1"],
             "requirement": "establish the applicable deadline", "supported_by": ["p1"],
             "facts": [{"statement": "deadline set", "from_propositions": ["p1"],
                        "capabilities": [{"must_show": "the deadline", "from_propositions": ["p1"]}]}]},
            {"rule_id": "repair_r2", "parent_node_id": "n", "requirement_kind": "coverage_condition",
             "condition": "the insurer ordered the measure", "condition_supported_by": ["p2"],
             "requirement": "establish insurer order", "supported_by": ["p2"],
             "facts": [{"statement": "order existed", "from_propositions": ["p2"],
                        "capabilities": [{"must_show": "the insurer order", "from_propositions": ["p2"]}]}]},
        ], "non_evidentiary": []})
    result = er.repair_missing(current, graph, props, call)
    assert result["verification"]["ok"]
    assert result["verification"]["missing"] == []
    assert result["verification"]["accounted"] == 2


def test_v2_repair_fails_closed_if_repair_omits_any_missing_proposition():
    graph = {"nodes": [{"node_id": "n", "label": "N", "kind": "step"}]}
    props = [{"proposition_id": "p1", "kind": "condition", "statement": "if X"}]
    result = er.repair_missing({"rules": [], "non_evidentiary": []}, graph, props,
                               lambda _s, _u: '{"new_rules":[],"non_evidentiary":[]}')
    assert not result["verification"]["ok"]
    assert result["verification"]["missing"] == ["p1"]


def test_non_evidentiary_audit_converts_material_item_to_rule():
    graph = {"nodes": [{"node_id": "n", "label": "Evidence", "kind": "step"}]}
    props = [{"proposition_id": "p1", "kind": "condition", "statement": "receipt cannot be produced"}]
    current = {"rules": [], "non_evidentiary": [{"proposition_id": "p1", "reason": "initially excluded"}]}
    def call(_s, _u):
        return '{"decisions":[{"proposition_id":"p1","decision":"material","covered_by_rule_id":null,"reason":"changes proof route","new_rule":{"rule_id":"a1","parent_node_id":"n","requirement_kind":"coverage_condition","condition":"receipt unavailable","condition_supported_by":["p1"],"requirement":"establish alternative proof need","supported_by":["p1"],"facts":[{"statement":"receipt unavailable","from_propositions":["p1"],"capabilities":[{"must_show":"receipt cannot be produced","from_propositions":["p1"]}]}]}}]}'
    result = er.audit_non_evidentiary(current, graph, props, call)
    assert result["verification"]["ok"]
    assert result["refinement"]["non_evidentiary"] == []
    assert result["refinement"]["rules"][0]["rule_id"] == "a1"


def test_non_evidentiary_audit_rejects_unknown_subsuming_rule():
    graph = {"nodes": [{"node_id": "n", "label": "Evidence", "kind": "step"}]}
    props = [{"proposition_id": "p1", "kind": "condition", "statement": "x"}]
    current = {"rules": [], "non_evidentiary": [{"proposition_id": "p1", "reason": "x"}]}
    call = lambda _s, _u: '{"decisions":[{"proposition_id":"p1","decision":"subsumed","covered_by_rule_id":"missing","reason":"covered","new_rule":null}]}'
    result = er.audit_non_evidentiary(current, graph, props, call)
    assert not result["verification"]["ok"]
    assert any("unknown rule" in p for p in result["verification"]["problems"])

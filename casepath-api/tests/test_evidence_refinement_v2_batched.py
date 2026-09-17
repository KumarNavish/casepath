import json

from casepath_api import evidence_refinement_v2 as er


def fixtures():
    graph = {"nodes": [{"node_id": "n", "label": "node", "kind": "decision"}]}
    propositions = [
        {"proposition_id": "p1", "source_id": "s", "kind": "obligation",
         "statement": "base", "quote": "base", "party": None, "governs": None, "citation": None},
        {"proposition_id": "p2", "source_id": "s", "kind": "condition",
         "statement": "same condition", "quote": "same", "party": None, "governs": None, "citation": None},
        {"proposition_id": "p3", "source_id": "s", "kind": "obligation",
         "statement": "new evidence", "quote": "new", "party": None, "governs": None, "citation": None},
    ]
    current = {
        "rules": [{
            "rule_id": "r1", "parent_node_id": "n", "requirement_kind": "obligation",
            "condition": None, "condition_supported_by": [], "requirement": "base",
            "supported_by": ["p1"],
            "facts": [{"fact_id": "f1", "statement": "base fact", "from_propositions": ["p1"],
                       "capabilities": [{"capability_id": "c1", "must_show": "base evidence",
                                         "from_propositions": ["p1"]}]}],
        }],
        "non_evidentiary": [
            {"proposition_id": "p2", "reason": "claimed duplicate"},
            {"proposition_id": "p3", "reason": "claimed irrelevant"},
        ],
    }
    return graph, propositions, current
def test_batched_audit_merges_exact_rosters_and_new_rule():
    graph, propositions, current = fixtures()

    def call(_, user):
        challenged = json.loads(user)["challenged"]
        proposition_id = challenged[0]["classification"]["proposition_id"]
        if proposition_id == "p2":
            return json.dumps({"decisions": [{
                "proposition_id": "p2", "decision": "subsumed",
                "covered_by_rule_id": "r1", "reason": "r1 preserves it", "new_rule": None,
            }]})
        return json.dumps({"decisions": [{
            "proposition_id": "p3", "decision": "material", "covered_by_rule_id": None,
            "reason": "needs distinct evidence",
            "new_rule": {
                "rule_id": "r2", "parent_node_id": "n", "requirement_kind": "obligation",
                "condition": None, "condition_supported_by": [], "requirement": "new evidence",
                "supported_by": ["p3"],
                "facts": [{"fact_id": "f2", "statement": "new fact", "from_propositions": ["p3"],
                           "capabilities": [{"capability_id": "c2", "must_show": "new evidence",
                                             "from_propositions": ["p3"]}]}],
            },
        }]})

    result = er.audit_non_evidentiary_batched(current, graph, propositions, call, batch_size=1)
    assert result["verification"]["ok"]
    assert len(result["audit"]["batches"]) == 2
    assert {r["rule_id"] for r in result["refinement"]["rules"]} == {"r1", "r2"}
    assert result["refinement"]["non_evidentiary"][0]["proposition_id"] == "p2"


def test_malformed_audit_fails_closed_without_exception():
    graph, propositions, current = fixtures()
    result = er.audit_non_evidentiary(
        current, graph, propositions,
        lambda *_: json.dumps({"decisions": [{"proposition_id": "p2", "decision": "irrelevant",
                                               "covered_by_rule_id": None, "reason": "x",
                                               "new_rule": None}, "stray"]}),
    )
    assert not result["verification"]["ok"]
    assert any("non-object" in problem for problem in result["verification"]["problems"])


def test_batched_roster_mismatch_fails_closed():
    graph, propositions, current = fixtures()
    result = er.audit_non_evidentiary_batched(
        current, graph, propositions,
        lambda *_: json.dumps({"decisions": []}),
        batch_size=1,
    )
    assert not result["verification"]["ok"]
    assert any("batch must decide" in problem for problem in result["verification"]["problems"])


def test_apply_audit_assigns_stable_unique_rule_id():
    graph, propositions, current = fixtures()
    decisions = [
        {"proposition_id": "p2", "decision": "subsumed", "covered_by_rule_id": "r1",
         "reason": "covered", "new_rule": None},
        {"proposition_id": "p3", "decision": "material", "covered_by_rule_id": None,
         "reason": "material", "new_rule": {
             "rule_id": "r1", "parent_node_id": "n", "requirement_kind": "obligation",
             "condition": None, "condition_supported_by": [], "requirement": "new evidence",
             "supported_by": ["p3"],
             "facts": [{"fact_id": "f", "statement": "new", "from_propositions": ["p3"],
                        "capabilities": [{"capability_id": "c", "must_show": "new",
                                          "from_propositions": ["p3"]}]}],
         }},
    ]
    result = er.apply_audit_decisions(current, decisions, graph, propositions)
    assert result["verification"]["ok"]
    rule = next(r for r in result["refinement"]["rules"] if r["rule_id"].startswith("audit_p3"))
    assert rule["audit_original_rule_id"] == "r1"

from casepath_api import evidence_refinement_v2 as er


def test_remove_unbacked_condition_preserves_requirement_and_records_repair():
    refinement = {
        "rules": [{
            "rule_id": "r1",
            "parent_node_id": "n1",
            "condition": "invented applicability",
            "condition_supported_by": [],
            "requirement_kind": "obligation",
            "requirement": "establish payment account",
            "supported_by": ["p1"],
            "facts": [{
                "fact_id": "f1", "statement": "account details",
                "from_propositions": ["p1"],
                "capabilities": [{"capability_id": "c1", "must_show": "IBAN", "from_propositions": ["p1"]}],
            }],
        }],
        "non_evidentiary": [],
    }
    normalized = er.remove_unbacked_conditions(refinement)
    assert normalized["refinement"]["rules"][0]["condition"] is None
    assert normalized["refinement"]["rules"][0]["requirement"] == "establish payment account"
    assert normalized["repairs"] == [{"rule_id": "r1", "removed_condition": "invented applicability",
                                       "reason": "condition had no source proposition support"}]

from casepath_api import refinement_repairs_v1 as repairs


def fixtures():
    propositions = [
        {"proposition_id": "p_condition", "source_id": "s1", "kind": "condition",
         "statement": "the threshold applies"},
        {"proposition_id": "p_consequence", "source_id": "s1", "kind": "exception",
         "statement": "evidence is required"},
        {"proposition_id": "p_trigger", "source_id": "s2", "kind": "condition",
         "statement": "a written demand exists"},
        {"proposition_id": "p_outcome", "source_id": "s2", "kind": "condition",
         "statement": "the demand was not met"},
    ]
    refinement = {
        "rules": [
            {"rule_id": "value_rule", "parent_node_id": "n", "requirement_kind": "exception",
             "condition": "ordinary evidence is assessed", "condition_supported_by": ["p_consequence"],
             "requirement": "establish value evidence", "supported_by": ["p_consequence"],
             "facts": [{"fact_id": "f_value", "statement": "value evidence exists",
                        "from_propositions": ["p_consequence"],
                        "capabilities": [{"capability_id": "c_value", "must_show": "receipt or valuation",
                                          "from_propositions": ["p_consequence"]}]}]},
            {"rule_id": "deadline_rule", "parent_node_id": "n", "requirement_kind": "condition",
             "condition": "a demand exists and was not met",
             "condition_supported_by": ["p_trigger", "p_outcome"],
             "requirement": "determine compliance", "supported_by": ["p_trigger", "p_outcome"],
             "facts": [
                 {"fact_id": "f_request", "statement": "written request details",
                  "from_propositions": ["p_trigger"],
                  "capabilities": [{"capability_id": "c_request", "must_show": "request and warning",
                                    "from_propositions": ["p_trigger"]}]},
                 {"fact_id": "f_compliance", "statement": "whether complied",
                  "from_propositions": ["p_outcome"],
                  "capabilities": [{"capability_id": "c_compliance", "must_show": "compliance outcome",
                                    "from_propositions": ["p_outcome"]}]},
             ]},
        ],
        "non_evidentiary": [{"proposition_id": "p_condition", "reason": "incorrectly ignored"}],
    }
    return propositions, refinement


def test_bind_source_condition_requires_same_source_and_removes_non_evidentiary():
    propositions, refinement = fixtures()
    result = repairs.bind_source_condition(
        refinement, propositions, condition_proposition_id="p_condition", rule_id="value_rule")
    rule = next(rule for rule in result["refinement"]["rules"] if rule["rule_id"] == "value_rule")
    assert rule["condition"] == "the threshold applies"
    assert "p_condition" in rule["condition_supported_by"]
    assert result["refinement"]["non_evidentiary"] == []


def test_extract_fact_as_rule_preserves_other_outcome_fact():
    propositions, refinement = fixtures()
    result = repairs.extract_fact_as_rule(
        refinement, propositions,
        source_rule_id="deadline_rule", fact_id="f_request", new_rule_id="request_rule",
        condition="a written demand exists", condition_supported_by=["p_trigger"],
        requirement="establish the written demand", supported_by=["p_trigger"])
    source = next(rule for rule in result["refinement"]["rules"] if rule["rule_id"] == "deadline_rule")
    added = next(rule for rule in result["refinement"]["rules"] if rule["rule_id"] == "request_rule")
    assert [fact["fact_id"] for fact in source["facts"]] == ["f_compliance"]
    assert [fact["fact_id"] for fact in added["facts"]] == ["f_request"]
    assert added["condition_supported_by"] == ["p_trigger"]

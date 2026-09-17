import json

from casepath_api import case_interpreter_v4 as ci


def test_one_call_per_guard_and_exact_unit_quotes():
    graph = {"guards": [
        {"guard_id": "bike", "statement": "a bicycle is claimed", "exclusive_group": None},
        {"guard_id": "sim", "statement": "a SIM card is claimed", "exclusive_group": None},
    ]}
    cases = {
        "u1": {"customer_message": "A bicycle is claimed. No SIM card is claimed."},
        "u2": {"customer_message": "No bicycle is claimed. A SIM card is claimed."},
    }
    calls = []

    def call(system, user):
        payload = json.loads(user)
        guard_id = payload["guard"]["guard_id"]
        calls.append(guard_id)
        rows = []
        for case in payload["cases"]:
            text = case["materials"]["customer_message"]
            positive = (guard_id == "bike" and text.startswith("A bicycle")) or (
                guard_id == "sim" and "A SIM card" in text)
            quote = ("A bicycle is claimed." if guard_id == "bike" and positive else
                     "No bicycle is claimed." if guard_id == "bike" else
                     "A SIM card is claimed." if positive else "No SIM card is claimed.")
            rows.append({"unit_id": case["unit_id"], "verdict": "true" if positive else "false",
                         "quote": quote, "source_ref": "customer_message", "what_would_settle_it": None})
        return json.dumps({"results": rows})

    result = ci.decide_many(graph, cases, call, workers=2)
    assert sorted(calls) == ["bike", "sim"]
    assert result["u1"]["verdicts"]["bike"]["verdict"] == "true"
    assert result["u1"]["verdicts"]["sim"]["verdict"] == "false"
    assert result["u2"]["verdicts"]["bike"]["verdict"] == "false"
    assert result["u2"]["verdicts"]["sim"]["verdict"] == "true"
def test_missing_or_nonverbatim_rows_fail_closed_per_unit():
    graph = {"guards": [{"guard_id": "g", "statement": "condition", "exclusive_group": None}]}
    cases = {
        "u1": {"customer_message": "Known text."},
        "u2": {"customer_message": "Other text."},
    }

    def call(*_):
        return json.dumps({"results": [{"unit_id": "u1", "verdict": "true", "quote": "invented",
                                        "source_ref": "customer_message", "what_would_settle_it": None}]})

    result = ci.decide_many(graph, cases, call, workers=1)
    assert result["u1"]["verdicts"]["g"]["verdict"] == "unresolved"
    assert result["u2"]["verdicts"]["g"]["verdict"] == "unresolved"
    assert result["u1"]["ungrounded"]
    assert result["u2"]["ungrounded"]


def test_exclusive_group_is_enforced_per_unit():
    graph = {"guards": [
        {"guard_id": "a", "statement": "A", "exclusive_group": "x"},
        {"guard_id": "b", "statement": "B", "exclusive_group": "x"},
    ]}
    cases = {"u": {"customer_message": "A and B."}}

    def call(_, user):
        guard_id = json.loads(user)["guard"]["guard_id"]
        return json.dumps({"results": [{"unit_id": "u", "verdict": "true", "quote": "A and B.",
                                        "source_ref": "customer_message", "what_would_settle_it": None}]})

    result = ci.decide_many(graph, cases, call, workers=2)["u"]
    assert {v["verdict"] for v in result["verdicts"].values()} == {"unresolved"}
    assert "exclusive_group_contradictions" in result["ungrounded"][-1]

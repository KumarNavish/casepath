import json

from casepath_api import case_interpreter_v3 as ci


def graph():
    return {
        "guards": [
            {"guard_id": "bike", "statement": "a bicycle is claimed", "exclusive_group": None},
            {"guard_id": "sim", "statement": "a SIM card is claimed", "exclusive_group": None},
        ],
        "nodes": [{"node_id": "root", "guard_ids": []}],
        "transitions": [],
    }


def test_each_guard_is_sent_in_an_independent_prompt():
    calls = []
    text = "A bicycle is claimed. No SIM card is claimed."

    def call(system, user):
        payload = json.loads(user)
        calls.append(payload)
        guard_id = payload["guard"]["guard_id"]
        if guard_id == "bike":
            return json.dumps({"guard_id": guard_id, "verdict": "true",
                               "quote": "A bicycle is claimed.", "source_ref": "customer_message",
                               "what_would_settle_it": None})
        return json.dumps({"guard_id": guard_id, "verdict": "false",
                           "quote": "No SIM card is claimed.", "source_ref": "customer_message",
                           "what_would_settle_it": None})

    result = ci.decide(graph(), {"customer_message": text}, call, workers=2)
    assert {payload["guard"]["guard_id"] for payload in calls} == {"bike", "sim"}
    assert all("guards" not in payload for payload in calls)
    assert result["verdicts"]["bike"]["verdict"] == "true"
    assert result["verdicts"]["sim"]["verdict"] == "false"
def test_non_verbatim_decision_reverts_to_unresolved():
    single = {"guards": [{"guard_id": "g", "statement": "condition", "exclusive_group": None}]}
    result = ci.decide(single, {"customer_message": "No relevant statement."},
                       lambda *_: json.dumps({"guard_id": "g", "verdict": "true",
                                             "quote": "invented", "source_ref": "customer_message",
                                             "what_would_settle_it": None}), workers=1)
    assert result["verdicts"]["g"]["verdict"] == "unresolved"
    assert result["ungrounded"]


def test_exclusive_true_guards_revert_as_a_group():
    exclusive = {"guards": [
        {"guard_id": "a", "statement": "A", "exclusive_group": "branch"},
        {"guard_id": "b", "statement": "B", "exclusive_group": "branch"},
    ]}
    text = "A and B were both asserted."

    def call(_, user):
        guard_id = json.loads(user)["guard"]["guard_id"]
        return json.dumps({"guard_id": guard_id, "verdict": "true",
                           "quote": text, "source_ref": "customer_message",
                           "what_would_settle_it": None})

    result = ci.decide(exclusive, {"customer_message": text}, call, workers=2)
    assert {value["verdict"] for value in result["verdicts"].values()} == {"unresolved"}
    assert "exclusive_group_contradictions" in result["ungrounded"][-1]

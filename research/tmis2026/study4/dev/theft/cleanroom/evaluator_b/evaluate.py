#!/usr/bin/env python3
"""Evaluator B, theft regime: derive document states from rule_text.md.

Usage: python3 -I evaluate.py catalogue.json designs.json [reference.json]

The rule text is encoded below as data (stops, steps in order, documents with
their step, condition and mandatory flag).  The engine is generic:

* every fact gets True / False / None (unresolved) from the file, using the
  benchmark convention for facts the file does not mention;
* every unresolved fact is completed both ways; under each completion the steps
  are walked in order and a stop ends the process at its step;
* under each completion a document gets a definite state; if all completions
  agree, that is the state, otherwise the document is on hold, waiting for the
  unresolved facts that can change it (pivotal facts).
"""
import itertools
import json
import sys

ALWAYS = lambda v: True  # noqa: E731


def _h_go(v):
    # theft_at_home = true and household_perpetrator = false
    return v["theft_at_home"] and not v["household_perpetrator"]


def _a_go(v):
    # theft_away = true and away_cover_missing = false
    return v["theft_away"] and not v["away_cover_missing"]


TYPES = {
    "theft_at_home": {
        "defining": "theft_at_home",
        "stops": [
            ("h_event", lambda v: not v["theft_at_home"]),
            ("h_exclusion", lambda v: v["theft_at_home"] and v["household_perpetrator"]),
        ],
        "steps": [
            ("h_event", ALWAYS),
            ("h_exclusion", lambda v: v["theft_at_home"]),
            ("h_notify", _h_go),
            ("h_police", _h_go),
            ("h_traces", lambda v: _h_go(v) and v["traces_changed"]),
            ("h_instruction_check", _h_go),
            ("h_instruction", lambda v: _h_go(v) and v["measures_pending"] and not v["imminent_danger"]),
            ("h_loss", _h_go),
        ],
        # document -> (step, needed-when, mandatory)
        "documents": {
            "notification_record": ("h_notify", _h_go, True),
            "insurance_policy": ("h_notify", _h_go, True),
            "police_report": ("h_police", _h_go, False),
            "police_consent": ("h_traces", lambda v: _h_go(v) and v["traces_changed"], True),
            "stolen_items_list": ("h_loss", _h_go, True),
            "original_vouchers": ("h_loss", lambda v: _h_go(v) and not v["vouchers_unobtainable"], True),
            "bicycle_voucher": ("h_loss", lambda v: _h_go(v) and v["bicycle"] and not v["vouchers_unobtainable"], True),
            "lock_change_invoice": ("h_loss", lambda v: _h_go(v) and v["lock_change"] and v["burglary_or_robbery"], True),
        },
    },
    "simple_theft_away": {
        "defining": "theft_away",
        "stops": [
            ("a_event", lambda v: not v["theft_away"]),
            ("a_cover", lambda v: v["theft_away"] and v["away_cover_missing"]),
        ],
        "steps": [
            ("a_event", ALWAYS),
            ("a_cover", lambda v: v["theft_away"]),
            ("a_notify", _a_go),
            ("a_police", _a_go),
            ("a_traces", lambda v: _a_go(v) and v["traces_changed"]),
            ("a_instruction_check", _a_go),
            ("a_instruction", lambda v: _a_go(v) and v["measures_pending"] and not v["imminent_danger"]),
            ("a_loss", _a_go),
        ],
        "documents": {
            "notification_record": ("a_notify", _a_go, True),
            "insurance_policy": ("a_cover", lambda v: v["theft_away"], True),
            "police_report": ("a_police", _a_go, False),
            "police_consent": ("a_traces", lambda v: _a_go(v) and v["traces_changed"], True),
            "stolen_items_list": ("a_loss", _a_go, True),
            "original_vouchers": ("a_loss", lambda v: _a_go(v) and not v["vouchers_unobtainable"], True),
            "bicycle_voucher": ("a_loss", lambda v: _a_go(v) and v["bicycle"] and not v["vouchers_unobtainable"], True),
        },
    },
}


def _assignments(facts):
    for bits in itertools.product((False, True), repeat=len(facts)):
        yield dict(zip(facts, bits))


def absence_would_end(rule, fact, fact_ids):
    """Convention: 'where a fact's absence would end it [the process]'.
    True if, for some answer to the other facts, a stop applies with the fact
    absent (false) and none applies with it present."""
    others = [f for f in fact_ids if f != fact]
    for a in _assignments(others):
        no, yes = dict(a, **{fact: False}), dict(a, **{fact: True})
        if any(c(no) for _, c in rule["stops"]) and not any(c(yes) for _, c in rule["stops"]):
            return True
    return False


def resolve(rule, fact, state, fact_ids):
    if state == "stated_true":
        return True
    if state == "denied":
        return False
    if state == "raised_and_left_open":
        return None  # "A fact that the file raises and leaves unsettled is open."
    if state != "not_mentioned":
        raise ValueError(state)
    if fact == rule["defining"]:
        return None  # "The defining event is never presumed"
    # "taken as not alleged ... as if it were absent", unless absence would end the process
    return None if absence_would_end(rule, fact, fact_ids) else False


def reached_steps(rule, v):
    reached = set()
    for name, cond in rule["steps"]:
        if cond(v):
            reached.add(name)
        if any(at == name and c(v) for at, c in rule["stops"]):
            break  # a stop ends the process at its step: no later step is reached
    return reached


def doc_state(rule, doc, v, supplied):
    step, cond, mandatory = rule["documents"][doc]
    needed = step in reached_steps(rule, v) and bool(cond(v))
    if not needed:
        return "not_needed"
    if doc in supplied:
        return "present_sufficient" if supplied[doc] == "sufficient" else "present_insufficient"
    if not mandatory:
        # optional: "not requested at intake"; "marks it 'not needed' unless the file contains it"
        return "not_needed"
    return "request"


def evaluate_file(rule, f, doc_ids, fact_ids):
    values = {k: resolve(rule, k, f["facts"][k], fact_ids) for k in fact_ids}
    unknown = [k for k in fact_ids if values[k] is None]
    supplied = {a["document"]: a["as_designed"] for a in f["attachments"]}
    out = {}
    for doc in doc_ids:
        results = {}
        for a in _assignments(unknown):
            v = dict(values)
            v.update(a)
            results[tuple(sorted(a.items()))] = doc_state(rule, doc, v, supplied)
        states = set(results.values())
        if len(states) == 1:
            out[doc] = {"state": states.pop()}
            continue
        pivotal = []
        for k in unknown:
            for key, r in results.items():
                flipped = tuple((f2, (not b) if f2 == k else b) for f2, b in key)
                if results[flipped] != r:
                    pivotal.append(k)
                    break
        out[doc] = {"state": "hold", "waits_for": pivotal}
    return out


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: evaluate.py catalogue.json designs.json [reference.json]")
    with open(argv[1], encoding="utf-8") as fh:
        catalogue = json.load(fh)
    with open(argv[2], encoding="utf-8") as fh:
        designs = json.load(fh)
    out_path = argv[3] if len(argv) > 3 else "reference.json"
    cat = {t["type"]: t for t in catalogue["types"]}
    for tname, rule in TYPES.items():
        assert sorted(d["document"] for d in cat[tname]["documents"]) == sorted(rule["documents"]), tname
    result = {}
    for f in designs["files"]:
        t = cat[f["type"]]
        fact_ids = [x["fact"] for x in t["facts"]]
        doc_ids = [x["document"] for x in t["documents"]]
        assert sorted(f["facts"]) == sorted(fact_ids), f["file_id"]
        result[f["file_id"]] = evaluate_file(TYPES[f["type"]], f, doc_ids, fact_ids)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv)

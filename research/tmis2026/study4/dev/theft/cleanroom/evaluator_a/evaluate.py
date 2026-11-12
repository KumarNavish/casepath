#!/usr/bin/env python3
"""Evaluator A, theft: derive document states from rule_text.md.

Usage: python3 -I evaluate.py catalogue.json designs.json reference.json

The rule text is encoded below as step and document conditions (Y(f) = "fact f
is true", N(f) = "fact f is false").  Conditions are evaluated in three-valued
(Kleene) logic: an answer that is unresolved or open makes a condition that
depends on it wait for that answer.
"""
import json
import sys

# ---------------------------------------------------------------- engine
T, F, U = "T", "F", "U"


def Y(fact):
    return ("is", fact, "yes")


def N(fact):
    return ("is", fact, "no")


def AND(*xs):
    return ("and",) + xs


def OR(*xs):
    return ("or",) + xs


def NOT(x):
    return ("not", x)


ALWAYS = ("and",)


def ev(expr, answers):
    """Return (value, waits) with value in T/F/U and waits the set of
    unresolved facts the value U depends on."""
    op = expr[0]
    if op == "is":
        a = answers[expr[1]]
        if a == "unresolved":
            return U, {expr[1]}
        return (T if a == expr[2] else F), set()
    if op == "not":
        v, w = ev(expr[1], answers)
        return {T: F, F: T, U: U}[v], w
    vals = [ev(x, answers) for x in expr[1:]]
    if op == "and":
        if any(v == F for v, _ in vals):
            return F, set()
        unk = [w for v, w in vals if v == U]
        return (U, set().union(*unk)) if unk else (T, set())
    if op == "or":
        if any(v == T for v, _ in vals):
            return T, set()
        unk = [w for v, w in vals if v == U]
        return (U, set().union(*unk)) if unk else (F, set())
    raise ValueError(op)


def answer(fact, state, presumption):
    """Map a designed fact state to yes / no / unresolved."""
    if state == "stated_true":
        return "yes"
    if state == "denied":
        return "no"
    if state == "raised_and_left_open":
        return "unresolved"  # "A fact that the file raises and leaves unsettled is open."
    if state == "not_mentioned":
        return presumption[fact]  # the question's own "If not mentioned" line
    raise ValueError(state)


def evaluate(rules, catalogue, designs):
    types = {t["type"]: t for t in catalogue["types"]}
    out = {}
    for f in designs["files"]:
        typ = types[f["type"]]
        rule = rules[f["type"]]
        order = [x["fact"] for x in typ["facts"]]
        assert set(order) == set(f["facts"]) == set(rule["presumption"]), f["file_id"]
        answers = {k: answer(k, v, rule["presumption"]) for k, v in f["facts"].items()}
        supplied = {}
        for a in f["attachments"]:
            assert a["document"] not in supplied
            supplied[a["document"]] = a["as_designed"]
        docs = {}
        for step in rule["steps"]:
            for doc, cond in step["documents"]:
                docs[doc] = AND(step["when"], cond)
        catalogue_docs = [d["document"] for d in typ["documents"]]
        assert set(docs) == set(catalogue_docs), f["type"]
        assert set(supplied) <= set(docs), f["file_id"]
        res = {}
        for doc in catalogue_docs:
            v, w = ev(docs[doc], answers)
            optional = doc in rule.get("optional", ())
            if v == T:
                if doc in supplied:
                    res[doc] = {"state": "present_" + supplied[doc]}
                elif optional:
                    res[doc] = {"state": "not_needed"}
                else:
                    res[doc] = {"state": "request"}
            elif v == U:
                if optional and doc not in supplied:
                    res[doc] = {"state": "not_needed"}
                else:
                    res[doc] = {"state": "hold", "waits_for": [x for x in order if x in w]}
            else:
                res[doc] = {"state": "not_needed"}
        out[f["file_id"]] = res
    return out


# ---------------------------------------------------------------- rule text
NO, UNRES = "no", "unresolved"
# "A fact is answered true, false, open ... or not stated."  true -> yes, false -> no.
# Not stated: "taken as not alleged, and the rules are applied as if it were absent"
# -> no, except the defining event ("never presumed") and the facts the rule text
# marks "always stated or open in a file; no presumption" -> unresolved.

_HOME_OK = AND(Y("theft_at_home"), N("household_perpetrator"))
_AWAY_OK = AND(Y("theft_away"), N("away_cover_missing"))

RULES = {
    # Type 1: Theft at the insured location (Ziff. 23.3)
    "theft_at_home": {
        "presumption": {
            "theft_at_home": UNRES,          # defining event: never presumed
            "household_perpetrator": NO,
            "burglary_or_robbery": UNRES,    # "always stated or open in a file; no presumption"
            "lock_change": NO,
            "traces_changed": NO,
            "bicycle": NO,
            "vouchers_unobtainable": NO,
            "measures_pending": NO,
            "imminent_danger": NO,
        },
        # Stops: theft_at_home = false; theft_at_home = true and household_perpetrator = true.
        # Every later step's condition, as written, already excludes both.
        "optional": ("police_report",),
        "steps": [
            {"name": "h_event", "when": ALWAYS, "documents": []},
            {"name": "h_exclusion", "when": Y("theft_at_home"), "documents": []},
            {"name": "h_notify", "when": _HOME_OK,
             "documents": [("notification_record", _HOME_OK), ("insurance_policy", _HOME_OK)]},
            {"name": "h_police", "when": _HOME_OK,
             "documents": [("police_report", _HOME_OK)]},
            {"name": "h_traces", "when": AND(_HOME_OK, Y("traces_changed")),
             "documents": [("police_consent", AND(_HOME_OK, Y("traces_changed")))]},
            {"name": "h_instruction_check", "when": _HOME_OK, "documents": []},
            {"name": "h_instruction",
             "when": AND(_HOME_OK, Y("measures_pending"), N("imminent_danger")),
             "documents": []},
            {"name": "h_loss", "when": _HOME_OK,
             "documents": [
                 ("stolen_items_list", _HOME_OK),
                 ("original_vouchers", AND(_HOME_OK, N("vouchers_unobtainable"))),
                 ("bicycle_voucher", AND(_HOME_OK, Y("bicycle"), N("vouchers_unobtainable"))),
                 ("lock_change_invoice", AND(_HOME_OK, Y("lock_change"), Y("burglary_or_robbery"))),
             ]},
        ],
    },
    # Type 2: Simple theft away from the insured location (Ziff. 24.2)
    "simple_theft_away": {
        "presumption": {
            "theft_away": UNRES,             # defining event: never presumed
            "away_cover_missing": UNRES,     # "always stated or open in a file; no presumption"
            "traces_changed": NO,
            "bicycle": NO,
            "vouchers_unobtainable": NO,
            "measures_pending": NO,
            "imminent_danger": NO,
        },
        # Stops: theft_away = false; theft_away = true and away_cover_missing = true.
        "optional": ("police_report",),
        "steps": [
            {"name": "a_event", "when": ALWAYS, "documents": []},
            {"name": "a_cover", "when": Y("theft_away"),
             "documents": [("insurance_policy", Y("theft_away"))]},
            {"name": "a_notify", "when": _AWAY_OK,
             "documents": [("notification_record", _AWAY_OK)]},
            {"name": "a_police", "when": _AWAY_OK,
             "documents": [("police_report", _AWAY_OK)]},
            {"name": "a_traces", "when": AND(_AWAY_OK, Y("traces_changed")),
             "documents": [("police_consent", AND(_AWAY_OK, Y("traces_changed")))]},
            {"name": "a_instruction_check", "when": _AWAY_OK, "documents": []},
            {"name": "a_instruction",
             "when": AND(_AWAY_OK, Y("measures_pending"), N("imminent_danger")),
             "documents": []},
            {"name": "a_loss", "when": _AWAY_OK,
             "documents": [
                 ("stolen_items_list", _AWAY_OK),
                 ("original_vouchers", AND(_AWAY_OK, N("vouchers_unobtainable"))),
                 ("bicycle_voucher", AND(_AWAY_OK, Y("bicycle"), N("vouchers_unobtainable"))),
             ]},
        ],
    },
}


def main(argv):
    cat_path, des_path, out_path = argv[1], argv[2], argv[3]
    with open(cat_path, encoding="utf-8") as fh:
        catalogue = json.load(fh)
    with open(des_path, encoding="utf-8") as fh:
        designs = json.load(fh)
    out = evaluate(RULES, catalogue, designs)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv)

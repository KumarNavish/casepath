#!/usr/bin/env python3
"""Evaluator A, dismissal: derive document states from rule_text.md.

Usage: python3 -I evaluate.py catalogue.json designs.json reference.json

The rule text is encoded below as step and document conditions (Y(f) = "question f
is yes", N(f) = "question f is no").  Conditions are evaluated in three-valued
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
# Presumptions are taken from each type's "Presumptions" list.

# Type 1 shorthand
_P_AFTER_PROBATION = AND(Y("employer_gave_notice"), N("notice_during_probation"))
_P_ANY_PERIOD = OR(Y("incapacity_illness_accident"), Y("compulsory_service"), Y("pregnancy_or_birth"))

# Type 2 shorthand: the conditions exactly as the steps write them
_W_NO_LAPSE = AND(Y("employer_gave_notice"),
                  NOT(AND(Y("notice_period_ended"), N("objection_submitted"))))
_W_NOT_CONTINUED = AND(_W_NO_LAPSE, N("agreed_to_continue"))
_W_IN_TIME = AND(_W_NOT_CONTINUED, NOT(AND(Y("more_than_180_days"), N("action_in_time"))))

RULES = {
    # Type 1: Notice during a protected period (CO art. 336c)
    "protected_period_notice": {
        "presumption": {
            "employer_gave_notice": UNRES,          # never presumed
            "notice_during_probation": NO,
            "probation_varied": NO,
            "incapacity_illness_accident": NO,
            "compulsory_service": NO,
            "pregnancy_or_birth": NO,
            "notice_before_protected_period": UNRES,  # "No presumption; always stated in the file"
            "notice_period_varied": NO,
        },
        # Stops: employer_gave_notice no; employer_gave_notice yes and notice_during_probation yes
        # (both are written into the conditions of steps 3-8).
        "steps": [
            {"name": "1 Establish whether the employer gave notice", "when": ALWAYS, "documents": []},
            {"name": "2 Record the notice, start of employment, probation",
             "when": Y("employer_gave_notice"),
             "documents": [("termination_letter", ALWAYS), ("employment_contract", ALWAYS),
                           ("probation_terms", Y("probation_varied"))]},
            {"name": "3 Illness or accident", "when": AND(_P_AFTER_PROBATION, Y("incapacity_illness_accident")),
             "documents": [("incapacity_proof", ALWAYS)]},
            {"name": "4 Compulsory service", "when": AND(_P_AFTER_PROBATION, Y("compulsory_service")),
             "documents": [("service_confirmation", ALWAYS)]},
            {"name": "5 Pregnancy and maternity", "when": AND(_P_AFTER_PROBATION, Y("pregnancy_or_birth")),
             "documents": [("pregnancy_certificate", ALWAYS)]},
            {"name": "6 Suspended and extended notice period",
             "when": AND(_P_AFTER_PROBATION, _P_ANY_PERIOD, Y("notice_before_protected_period")),
             "documents": [("notice_period_terms", Y("notice_period_varied"))]},
            {"name": "7 Notice inside a protected period",
             "when": AND(_P_AFTER_PROBATION, _P_ANY_PERIOD, N("notice_before_protected_period")),
             "documents": []},
            {"name": "8 Assess the effect", "when": _P_AFTER_PROBATION, "documents": []},
        ],
    },
    # Type 2: Wrongful (abusive) notice (CO arts. 336-336b)
    "wrongful_termination": {
        "presumption": {
            "employer_gave_notice": UNRES,     # never presumed
            "notice_period_ended": UNRES,      # no presumption; always stated
            "objection_submitted": UNRES,      # absence would end the process
            "agreed_to_continue": NO,
            "more_than_180_days": UNRES,       # no presumption; always stated
            "action_in_time": UNRES,           # absence would end the process
            "reasons_requested": NO,
            "retaliation_for_claims": NO,
            "employee_representative": NO,
        },
        "steps": [
            {"name": "1 Establish whether the employer gave notice", "when": ALWAYS, "documents": []},
            {"name": "2 Record the notice and the notice period, check the objection",
             "when": Y("employer_gave_notice"),
             "documents": [("termination_letter", ALWAYS), ("employment_contract", ALWAYS),
                           ("written_objection", Y("objection_submitted"))]},
            {"name": "3 Agreement to continue", "when": _W_NO_LAPSE, "documents": []},
            {"name": "4 180-day time limit", "when": _W_NOT_CONTINUED,
             "documents": [("court_filing", Y("action_in_time"))]},
            {"name": "5 Reason given for the notice", "when": _W_IN_TIME,
             "documents": [("written_reasons", Y("reasons_requested"))]},
            {"name": "6 Retaliation", "when": AND(_W_IN_TIME, Y("retaliation_for_claims")),
             "documents": [("claims_correspondence", ALWAYS)]},
            {"name": "7 Employee representative", "when": AND(_W_IN_TIME, Y("employee_representative")),
             "documents": [("representative_mandate", ALWAYS)]},
            {"name": "8 Assess the compensation claim", "when": _W_IN_TIME,
             "documents": [("salary_evidence", ALWAYS)]},
        ],
    },
    # Type 3: Dismissal with immediate effect (CO arts. 337, 337c)
    "immediate_dismissal": {
        "presumption": {
            "dismissed_immediately": UNRES,   # never presumed
            "reasons_requested": NO,
            "incapacity_cause": NO,
            "fixed_term": UNRES,              # no presumption; always stated
            "notice_period_varied": NO,
            "other_earnings": NO,
        },
        "steps": [
            {"name": "1 Establish the immediate dismissal", "when": ALWAYS, "documents": []},
            {"name": "2 Record the dismissal, the contract and the salary",
             "when": Y("dismissed_immediately"),
             "documents": [("termination_letter", ALWAYS), ("employment_contract", ALWAYS),
                           ("salary_evidence", ALWAYS)]},
            {"name": "3 Establish the cause", "when": Y("dismissed_immediately"),
             "documents": [("written_reasons", Y("reasons_requested")),
                           ("incapacity_proof", Y("incapacity_cause"))]},
            {"name": "4 Damages to end of fixed term",
             "when": AND(Y("dismissed_immediately"), Y("fixed_term")), "documents": []},
            {"name": "5 Damages to end of notice period",
             "when": AND(Y("dismissed_immediately"), N("fixed_term")),
             "documents": [("notice_period_terms", Y("notice_period_varied"))]},
            {"name": "6 Assess damages and compensation", "when": Y("dismissed_immediately"),
             "documents": [("other_earnings_evidence", Y("other_earnings"))]},
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

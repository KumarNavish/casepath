#!/usr/bin/env python3
"""Evaluator A, tenancy: derive document states from rule_text.md.

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

RULES = {
    # 1. Defect of the rented dwelling
    "defect_mold_heating": {
        "presumption": {
            "defect_present": UNRES,   # defining event: never presumed
            "landlord_unaware": NO,
            "notice_oral_only": NO,
            "damages_claimed": NO,
            "deposit_intended": NO,
            "rent_deposited": NO,
        },
        # Stop: question 1 is no -> every step below requires Y(defect_present).
        "steps": [
            {"name": "Establish the defect and the agreed use of the dwelling",
             "when": Y("defect_present"),
             "documents": [("lease_contract", ALWAYS), ("defect_record", ALWAYS)]},
            {"name": "Establish how and when the landlord learned of the defect",
             "when": AND(Y("defect_present"), N("landlord_unaware")),
             "documents": [("knowledge_proof", N("notice_oral_only"))]},
            {"name": "Establish the damage claimed",
             "when": AND(Y("defect_present"), Y("damages_claimed")),
             "documents": [("damage_evidence", ALWAYS)]},
            {"name": "Check the preconditions and the time limit of the rent deposit",
             "when": AND(Y("defect_present"), Y("deposit_intended")),
             "documents": [("deposit_deadline_notice", ALWAYS),
                           ("deposit_receipt", Y("rent_deposited"))]},
        ],
    },
    # 2. Termination of the lease by the landlord
    "lease_termination_dispute": {
        "presumption": {
            "notice_received": UNRES,  # defining event: never presumed
            "family_residence": NO,
            "arrears_termination": NO,
            "asserted_claims": NO,
            "extension_requested": NO,
        },
        "steps": [
            {"name": "Check the form of the notice, the notice period and the challenge deadline",
             "when": Y("notice_received"),
             "documents": [("lease_contract", ALWAYS), ("termination_notice", ALWAYS),
                           ("proof_of_receipt", ALWAYS)]},
            {"name": "Check separate service on the spouse or registered partner",
             "when": AND(Y("notice_received"), Y("family_residence")),
             "documents": [("spouse_service", ALWAYS)]},
            {"name": "Check the payment time limit that preceded the notice",
             "when": AND(Y("notice_received"), Y("arrears_termination")),
             "documents": [("payment_demand", ALWAYS)]},
            {"name": "Check whether the notice can be challenged as contrary to good faith",
             "when": Y("notice_received"),
             "documents": [("claims_and_reasons", Y("asserted_claims"))]},
            {"name": "Assess an extension of the lease",
             "when": AND(Y("notice_received"), N("arrears_termination")),
             "documents": [("hardship_evidence", Y("extension_requested"))]},
        ],
    },
    # 3. Rent increase
    "rent_increase_dispute": {
        "presumption": {
            "increase_applied": UNRES,         # defining event: never presumed
            "graduated_rent": NO,
            "index_clause": NO,
            "cost_or_services_reason": UNRES,  # "unresolved (this fact has no ordinary default)"
            "termination_with_increase": NO,
        },
        "steps": [
            {"name": "Check the form, reasons and timing of the increase",
             "when": Y("increase_applied"),
             "documents": [("lease_contract", ALWAYS), ("rent_increase_notice", ALWAYS),
                           ("proof_of_receipt", ALWAYS)]},
            {"name": "Check the graduated-rent agreement",
             "when": AND(Y("increase_applied"), Y("graduated_rent")),
             "documents": []},
            {"name": "Check the index clause",
             "when": AND(Y("increase_applied"), N("graduated_rent"), Y("index_clause")),
             "documents": []},
            {"name": "Check whether the increase is justified by its stated reasons",
             "when": AND(Y("increase_applied"), N("graduated_rent"), N("index_clause")),
             "documents": [("cost_breakdown", Y("cost_or_services_reason"))]},
            {"name": "Check the notice of termination given with the increase",
             "when": AND(Y("increase_applied"), Y("termination_with_increase")),
             "documents": [("termination_notice", ALWAYS)]},
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

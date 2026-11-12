#!/usr/bin/env python3
"""Evaluator B, tenancy regime: derive document states from rule_text.md.

Usage: python3 -I evaluate.py catalogue.json designs.json [reference.json]

The rule text is encoded below as data: per type, each deciding question's
"If not mentioned" rule, the stop, the steps in order with their "reached when"
conditions, and each document with its step and own condition.  The engine is
generic: unresolved facts (open, or unmentioned where the text says
"unresolved") are completed both ways; under each completion the steps are
walked in order (a stop ends the process at its step) and each document gets a
state; if all completions agree that is the state, otherwise the document waits
("hold") for the unresolved facts that can change it.
"""
import itertools
import json
import sys

ALWAYS = lambda v: True  # noqa: E731
NO, UNRESOLVED = "no", "unresolved"

TYPES = {
    "defect_mold_heating": {
        "defining": "defect_present",
        # "If not mentioned" per question
        "if_not_mentioned": {
            "defect_present": UNRESOLVED,
            "landlord_unaware": NO,
            "notice_oral_only": NO,
            "damages_claimed": NO,
            "deposit_intended": NO,
            "rent_deposited": NO,
        },
        # stop: "if question 1 is no, the process ends" -- at the first step
        "stops": [("establish_defect", lambda v: not v["defect_present"])],
        "steps": [
            ("establish_defect", lambda v: v["defect_present"]),
            ("landlord_knowledge", lambda v: v["defect_present"] and not v["landlord_unaware"]),
            ("damage", lambda v: v["defect_present"] and v["damages_claimed"]),
            ("deposit", lambda v: v["defect_present"] and v["deposit_intended"]),
        ],
        # document -> (step, own condition)
        "documents": {
            "lease_contract": ("establish_defect", ALWAYS),
            "defect_record": ("establish_defect", ALWAYS),
            "knowledge_proof": ("landlord_knowledge", lambda v: not v["notice_oral_only"]),
            "damage_evidence": ("damage", ALWAYS),
            "deposit_deadline_notice": ("deposit", ALWAYS),
            "deposit_receipt": ("deposit", lambda v: v["rent_deposited"]),
        },
    },
    "lease_termination_dispute": {
        "defining": "notice_received",
        "if_not_mentioned": {
            "notice_received": UNRESOLVED,
            "family_residence": NO,
            "arrears_termination": NO,
            "asserted_claims": NO,
            "extension_requested": NO,
        },
        "stops": [("form_and_deadline", lambda v: not v["notice_received"])],
        "steps": [
            ("form_and_deadline", lambda v: v["notice_received"]),
            ("spouse_service", lambda v: v["notice_received"] and v["family_residence"]),
            ("payment_time_limit", lambda v: v["notice_received"] and v["arrears_termination"]),
            ("good_faith", lambda v: v["notice_received"]),
            ("extension", lambda v: v["notice_received"] and not v["arrears_termination"]),
        ],
        "documents": {
            "lease_contract": ("form_and_deadline", ALWAYS),
            "termination_notice": ("form_and_deadline", ALWAYS),
            "proof_of_receipt": ("form_and_deadline", ALWAYS),
            "spouse_service": ("spouse_service", ALWAYS),
            "payment_demand": ("payment_time_limit", ALWAYS),
            "claims_and_reasons": ("good_faith", lambda v: v["asserted_claims"]),
            "hardship_evidence": ("extension", lambda v: v["extension_requested"]),
        },
    },
    "rent_increase_dispute": {
        "defining": "increase_applied",
        "if_not_mentioned": {
            "increase_applied": UNRESOLVED,
            "graduated_rent": NO,
            "index_clause": NO,
            "cost_or_services_reason": UNRESOLVED,  # "unresolved (this fact has no ordinary default)"
            "termination_with_increase": NO,
        },
        "stops": [("form_reasons_timing", lambda v: not v["increase_applied"])],
        "steps": [
            ("form_reasons_timing", lambda v: v["increase_applied"]),
            ("graduated", lambda v: v["increase_applied"] and v["graduated_rent"]),
            ("index", lambda v: v["increase_applied"] and not v["graduated_rent"] and v["index_clause"]),
            ("justified", lambda v: v["increase_applied"] and not v["graduated_rent"] and not v["index_clause"]),
            ("termination", lambda v: v["increase_applied"] and v["termination_with_increase"]),
        ],
        "documents": {
            "lease_contract": ("form_reasons_timing", ALWAYS),
            "rent_increase_notice": ("form_reasons_timing", ALWAYS),
            "proof_of_receipt": ("form_reasons_timing", ALWAYS),
            "cost_breakdown": ("justified", lambda v: v["cost_or_services_reason"]),
            "termination_notice": ("termination", ALWAYS),
        },
    },
}


def _assignments(facts):
    for bits in itertools.product((False, True), repeat=len(facts)):
        yield dict(zip(facts, bits))


def resolve(rule, fact, state):
    if state == "stated_true":
        return True
    if state == "denied":
        return False
    if state == "raised_and_left_open":
        return None  # open: "waits for that answer"
    if state != "not_mentioned":
        raise ValueError(state)
    return None if rule["if_not_mentioned"][fact] == UNRESOLVED else False


def reached_steps(rule, v):
    reached = set()
    for name, cond in rule["steps"]:
        if cond(v):
            reached.add(name)
        if any(at == name and c(v) for at, c in rule["stops"]):
            break  # "no later step is reached"
    return reached


def doc_state(rule, doc, v, supplied):
    step, cond = rule["documents"][doc]
    if not (step in reached_steps(rule, v) and cond(v)):
        return "not_needed"
    if doc in supplied:
        return "present_sufficient" if supplied[doc] == "sufficient" else "present_insufficient"
    return "request"


def evaluate_file(rule, f, doc_ids, fact_ids):
    values = {k: resolve(rule, k, f["facts"][k]) for k in fact_ids}
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
        assert sorted(x["fact"] for x in cat[tname]["facts"]) == sorted(rule["if_not_mentioned"]), tname
    result = {}
    for f in designs["files"]:
        t = cat[f["type"]]
        fact_ids = [x["fact"] for x in t["facts"]]
        doc_ids = [x["document"] for x in t["documents"]]
        result[f["file_id"]] = evaluate_file(TYPES[f["type"]], f, doc_ids, fact_ids)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv)

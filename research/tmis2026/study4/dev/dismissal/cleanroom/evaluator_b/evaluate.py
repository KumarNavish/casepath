#!/usr/bin/env python3
"""Evaluator B, dismissal regime: derive document states from rule_text.md.

Usage: python3 -I evaluate.py catalogue.json designs.json [reference.json]

The rule text is encoded below as data (facts, presumptions, stops, steps,
documents).  The engine is generic:

* every fact gets a value True / False / None (unresolved) from the file and the
  presumptions;
* every unresolved fact is completed both ways; for each completion the steps are
  walked in order, a stop ends the process at its step (no later step reached);
* a document is needed under a completion when its step is reached and its own
  condition holds.  Needed under all completions -> request / present_*;
  under none -> not_needed; under some -> hold, waiting for the unresolved facts
  on which the answer actually turns (pivotal facts).
"""
import itertools
import json
import sys

# ---------------------------------------------------------------------------
# Rule text, encoded.  Conditions are functions of v (fact -> bool).
# ---------------------------------------------------------------------------


def _protected(v):
    return v["incapacity_illness_accident"] or v["compulsory_service"] or v["pregnancy_or_birth"]


def _t1_base(v):
    # (employer_gave_notice is yes and notice_during_probation is no)
    return v["employer_gave_notice"] and not v["notice_during_probation"]


def _t2_no_lapse(v):
    # employer_gave_notice is yes and not (notice_period_ended is yes and objection_submitted is no)
    return v["employer_gave_notice"] and not (v["notice_period_ended"] and not v["objection_submitted"])


def _t2_s3(v):
    return _t2_no_lapse(v) and not v["agreed_to_continue"]


def _t2_s5(v):
    return _t2_s3(v) and not (v["more_than_180_days"] and not v["action_in_time"])


ALWAYS = lambda v: True  # noqa: E731

TYPES = {
    "protected_period_notice": {
        "defining": "employer_gave_notice",
        "presumed_no": ["notice_during_probation", "probation_varied", "incapacity_illness_accident",
                        "compulsory_service", "pregnancy_or_birth", "notice_period_varied"],
        "unresolved_if_unmentioned": [],
        "always_stated": ["notice_before_protected_period"],
        # stops: (step at which the stop ends the process, condition)
        "stops": [
            (1, lambda v: not v["employer_gave_notice"]),
            (2, lambda v: v["employer_gave_notice"] and v["notice_during_probation"]),
        ],
        # steps: number -> condition under which the step is taken
        "steps": {
            1: ALWAYS,
            2: lambda v: v["employer_gave_notice"],
            3: lambda v: _t1_base(v) and v["incapacity_illness_accident"],
            4: lambda v: _t1_base(v) and v["compulsory_service"],
            5: lambda v: _t1_base(v) and v["pregnancy_or_birth"],
            6: lambda v: _t1_base(v) and _protected(v) and v["notice_before_protected_period"],
            7: lambda v: _t1_base(v) and _protected(v) and not v["notice_before_protected_period"],
            8: lambda v: _t1_base(v),
        },
        # documents: id -> (step, own condition)
        "documents": {
            "termination_letter": (2, ALWAYS),
            "employment_contract": (2, ALWAYS),
            "probation_terms": (2, lambda v: v["probation_varied"]),
            "incapacity_proof": (3, ALWAYS),
            "service_confirmation": (4, ALWAYS),
            "pregnancy_certificate": (5, ALWAYS),
            "notice_period_terms": (6, lambda v: v["notice_period_varied"]),
        },
    },
    "wrongful_termination": {
        "defining": "employer_gave_notice",
        "presumed_no": ["agreed_to_continue", "reasons_requested", "retaliation_for_claims",
                        "employee_representative"],
        "unresolved_if_unmentioned": ["action_in_time", "objection_submitted"],
        "always_stated": ["notice_period_ended", "more_than_180_days"],
        "stops": [
            (1, lambda v: not v["employer_gave_notice"]),
            (2, lambda v: v["employer_gave_notice"] and (v["notice_period_ended"] and not v["objection_submitted"])),
            (3, lambda v: _t2_no_lapse(v) and v["agreed_to_continue"]),
            (4, lambda v: _t2_s3(v) and (v["more_than_180_days"] and not v["action_in_time"])),
        ],
        "steps": {
            1: ALWAYS,
            2: lambda v: v["employer_gave_notice"],
            3: _t2_no_lapse,
            4: _t2_s3,
            5: _t2_s5,
            6: lambda v: _t2_s5(v) and v["retaliation_for_claims"],
            7: lambda v: _t2_s5(v) and v["employee_representative"],
            8: _t2_s5,
        },
        "documents": {
            "termination_letter": (2, ALWAYS),
            "employment_contract": (2, ALWAYS),
            "written_objection": (2, lambda v: v["objection_submitted"]),
            "court_filing": (4, lambda v: v["action_in_time"]),
            "written_reasons": (5, lambda v: v["reasons_requested"]),
            "claims_correspondence": (6, ALWAYS),
            "representative_mandate": (7, ALWAYS),
            "salary_evidence": (8, ALWAYS),
        },
    },
    "immediate_dismissal": {
        "defining": "dismissed_immediately",
        "presumed_no": ["reasons_requested", "incapacity_cause", "notice_period_varied", "other_earnings"],
        "unresolved_if_unmentioned": [],
        "always_stated": ["fixed_term"],
        "stops": [
            (1, lambda v: not v["dismissed_immediately"]),
        ],
        "steps": {
            1: ALWAYS,
            2: lambda v: v["dismissed_immediately"],
            3: lambda v: v["dismissed_immediately"],
            4: lambda v: v["dismissed_immediately"] and v["fixed_term"],
            5: lambda v: v["dismissed_immediately"] and not v["fixed_term"],
            6: lambda v: v["dismissed_immediately"],
        },
        "documents": {
            "termination_letter": (2, ALWAYS),
            "employment_contract": (2, ALWAYS),
            "salary_evidence": (2, ALWAYS),
            "written_reasons": (3, lambda v: v["reasons_requested"]),
            "incapacity_proof": (3, lambda v: v["incapacity_cause"]),
            "notice_period_terms": (5, lambda v: v["notice_period_varied"]),
            "other_earnings_evidence": (6, lambda v: v["other_earnings"]),
        },
    },
}

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _all_assignments(facts):
    for bits in itertools.product((False, True), repeat=len(facts)):
        yield dict(zip(facts, bits))


def absence_would_end(rule, fact, fact_ids):
    """General convention: does taking `fact` as absent (no) end the process
    under some answer to the other facts, where its presence would not?"""
    others = [f for f in fact_ids if f != fact]
    for a in _all_assignments(others):
        no = dict(a, **{fact: False})
        yes = dict(a, **{fact: True})
        if any(c(no) for _, c in rule["stops"]) and not any(c(yes) for _, c in rule["stops"]):
            return True
    return False


def resolve(rule, fact, state, fact_ids):
    """Value of a fact for the engine: True, False, or None (unresolved)."""
    if state == "stated_true":
        return True
    if state == "denied":
        return False
    if state == "raised_and_left_open":
        return None
    if state != "not_mentioned":
        raise ValueError(state)
    if fact == rule["defining"]:
        return None  # the defining event is never presumed
    if fact in rule["unresolved_if_unmentioned"]:
        return None
    if fact in rule["presumed_no"]:
        return False
    if fact in rule["always_stated"]:
        # No presumption is stated; the general convention applies:
        # taken as absent unless its absence would end the process.
        return None if absence_would_end(rule, fact, fact_ids) else False
    raise ValueError("fact without a presumption: " + fact)


def reached_steps(rule, v):
    """Walk the steps in order; a stop ends the process at its step."""
    reached = set()
    stopped_at = None
    for n in sorted(rule["steps"]):
        if stopped_at is not None and n > stopped_at:
            break
        if rule["steps"][n](v):
            reached.add(n)
        for at, cond in rule["stops"]:
            if at == n and cond(v):
                stopped_at = n if stopped_at is None else min(stopped_at, n)
    return reached


def needed(rule, doc, v):
    step, cond = rule["documents"][doc]
    return step in reached_steps(rule, v) and bool(cond(v))


def evaluate_file(rule, f, doc_ids, fact_ids):
    values = {k: resolve(rule, k, f["facts"][k], fact_ids) for k in fact_ids}
    unknown = [k for k in fact_ids if values[k] is None]
    supplied = {a["document"]: a["as_designed"] for a in f["attachments"]}
    completions = []
    for a in _all_assignments(unknown):
        v = dict(values)
        v.update(a)
        completions.append((a, v))
    out = {}
    for doc in doc_ids:
        results = {tuple(sorted(a.items())): needed(rule, doc, v) for a, v in completions}
        vals = set(results.values())
        if vals == {True}:
            if doc in supplied:
                state = "present_sufficient" if supplied[doc] == "sufficient" else "present_insufficient"
            else:
                state = "request"
            out[doc] = {"state": state}
        elif vals == {False}:
            out[doc] = {"state": "not_needed"}
        else:
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
    # consistency checks between the encoded rule text and the catalogue
    for tname, rule in TYPES.items():
        fact_ids = [x["fact"] for x in cat[tname]["facts"]]
        doc_ids = [x["document"] for x in cat[tname]["documents"]]
        assert sorted(doc_ids) == sorted(rule["documents"]), tname
        listed = [rule["defining"]] + rule["presumed_no"] + rule["unresolved_if_unmentioned"] + rule["always_stated"]
        assert sorted(listed) == sorted(fact_ids), tname
        for fct in rule["presumed_no"]:
            assert not absence_would_end(rule, fct, fact_ids), (tname, fct)
        for fct in rule["unresolved_if_unmentioned"]:
            assert absence_would_end(rule, fct, fact_ids), (tname, fct)
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

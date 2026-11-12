#!/usr/bin/env python3
"""Evaluator B: derive document states from the rule text alone.

Usage: python3 evaluate.py [rules.json] [claims.json] [reference.json]
Defaults: ../bundle/rules.json ../bundle/claims.json ./reference.json
(relative to the current directory). Standard library only; deterministic.
Also writes reference_alt_A1/A2/A3/A4/all.json next to reference.json (the
rejected readings of ambiguities A1-A4, see SEMANTICS.md).

See SEMANTICS.md for the reading of the rule text that this program applies.
"""
import itertools
import json
import os
import re
import sys

# --- Matching of the rule text to fact names (see SEMANTICS.md, case 8) ---------

# Defining events named by the silence-policy clause:
#   "for a termination dispute, that a termination notice was received;
#    for a rent dispute, that a rent-increase notification was received"
DEFINING_EVENT = {
    "lease_termination_dispute": "termination_received",
    "rent_increase_dispute": "claim_received",
}

# Transition conditions that name a claim fact. Each maps to a list of
# (fact, required_value) literals that must all hold.
FACT_GUARDS = {
    # defect_mold_heating
    "health effects alleged": [("health_effects", True)],
    "technical inspection needed": [("specialist_needed", True)],
    "deposit route considered without specialist": [("deposit_considered", True),
                                                    ("specialist_needed", False)],
    "deposit route remains relevant": [("deposit_considered", True)],
    # lease_termination_dispute
    "termination received": [("termination_received", True)],
    "arrears termination": [("arrears", True)],
    "family-home ordinary termination": [("family_home", True)],
    "extension relevant": [("extension_relevant", True)],
    # rent_increase_dispute
    "claim received": [("claim_received", True)],
    "reference-rate reason selected": [("reference_rate", True)],
    "renovation reason selected": [("renovation", True)],
}

# "No <branch>" conditions: the default branch, taken exactly when no sibling
# edge (same source) with a fact guard is taken.
ELSE_GUARDS = {
    "no immediate health escalation",
    "no further specialist or deposit branch",
    "no special precondition branch",
    "no extension branch",
    "no specialist calculation branch",
}

# Every other transition condition names completion of the handler's own work
# at the source step (e.g. "timeline drafted", "outcome recorded"); it is not a
# claim fact and is treated as satisfied.
PROCEDURAL = {
    "safety advice recorded", "timeline drafted", "notice position recorded",
    "causation status recorded", "evidence gaps identified",
    "deposit safeguards assessed", "outcome recorded", "inspection result available",
    "deadline position recorded", "formal review complete",
    "arrears preconditions assessed", "family service assessed",
    "hardship factors recorded", "evidence collection closed",
    "baseline reconstructed", "cost evidence screened", "assessment recorded",
    "resolution recorded",
}

DOC_COND_RE = re.compile(r"^scenario flag '([a-z_]+)' is active$")


# Alternative readings of the ambiguities in SEMANTICS.md. The main reference
# uses none of them; each alternative file switches on the named ones.
ALT_NONE = frozenset()
ALTERNATIVES = [
    ("reference_alt_A1.json", frozenset({"A1"})),
    ("reference_alt_A2.json", frozenset({"A2"})),
    ("reference_alt_A3.json", frozenset({"A3"})),
    ("reference_alt_A4.json", frozenset({"A4"})),
    ("reference_alt_all.json", frozenset({"A1", "A2", "A3", "A4"})),
]


def guards_for(alts):
    guards = dict(FACT_GUARDS)
    if "A4" in alts:
        # A4: "ordinary" excludes an arrears termination.
        guards["family-home ordinary termination"] = [("family_home", True),
                                                      ("arrears", False)]
    return guards


def fact_truth(dispute_type, fact, state, alts=ALT_NONE):
    """Return True/False for a decided fact, None for an open one."""
    is_defining = DEFINING_EVENT.get(dispute_type) == fact
    if state == "stated_true":
        return True
    if state == "denied":
        # A1: a denied defining event does not stop the process.
        return is_defining and "A1" in alts
    if state == "raised_and_left_open" and is_defining and "A2" in alts:
        # A2: an open defining event is presumed to have occurred.
        return True
    if state == "not_mentioned":
        # "a branch fact that the claim never mentions is presumed absent;
        #  the dispute's defining event ... is presumed to have occurred"
        return DEFINING_EVENT.get(dispute_type) == fact
    if state == "raised_and_left_open":
        return None
    raise ValueError("unknown fact state %r" % state)


def guard_holds(literals, assignment):
    return all(assignment[f] == v for f, v in literals)


def reachable_nodes(proc, assignment, guards=FACT_GUARDS):
    nodes = proc["nodes"]
    targets = {t["target_node_id"] for t in proc["transitions"]}
    starts = [n["node_id"] for n in nodes if n["node_id"] not in targets]
    if len(starts) != 1:
        raise ValueError("expected exactly one start node, got %r" % starts)
    by_source = {}
    for t in proc["transitions"]:
        by_source.setdefault(t["source_node_id"], []).append(t)
    seen = {starts[0]}
    stack = [starts[0]]
    while stack:
        src = stack.pop()
        edges = sorted(by_source.get(src, []), key=lambda e: e["edge_id"])
        guarded_taken = any(
            guard_holds(guards[e["condition"]], assignment)
            for e in edges if e["condition"] in guards)
        for e in edges:
            c = e["condition"]
            if c in guards:
                take = guard_holds(guards[c], assignment)
            elif c in ELSE_GUARDS:
                take = not guarded_taken
            elif c in PROCEDURAL:
                take = True
            else:
                raise ValueError("unmatched transition condition %r" % c)
            if take and e["target_node_id"] not in seen:
                seen.add(e["target_node_id"])
                stack.append(e["target_node_id"])
    return seen


def doc_needed(doc, reach, assignment, alts=ALT_NONE):
    """Is the document needed (to be requested) under one complete assignment?"""
    if doc["requirement_class"] == "optional" and "A3" not in alts:
        # Optional documents are never requested (SEMANTICS.md case 6).
        return False
    if not any(n in reach for n in doc["required_at_node_ids"]):
        return False
    if doc["requirement_class"] == "optional":
        # A3: requested like a mandatory document when its step is reached.
        return True
    if doc["requirement_class"] == "mandatory":
        return True
    m = DOC_COND_RE.match(doc["condition"] or "")
    if not m:
        raise ValueError("unmatched document condition %r" % doc["condition"])
    return assignment[m.group(1)] is True


def evaluate_claim(dt, claim, alts=ALT_NONE):
    proc = dt["process_catalog"]
    catalog = dt["condition_catalog"]
    guards = guards_for(alts)
    if sorted(claim["facts"]) != sorted(catalog):
        raise ValueError("facts of %s do not match catalogue" % claim["claim_id"])
    base = {f: fact_truth(dt["dispute_type"], f, claim["facts"][f], alts) for f in catalog}
    open_facts = sorted(f for f in catalog if base[f] is None)
    # Enumerate every answer to every open question.
    outcomes = {d["document_type"]: set() for d in proc["documents"]}
    for values in itertools.product([False, True], repeat=len(open_facts)):
        assignment = dict(base)
        assignment.update(zip(open_facts, values))
        reach = reachable_nodes(proc, assignment, guards)
        for d in proc["documents"]:
            outcomes[d["document_type"]].add(doc_needed(d, reach, assignment, alts))
    supplied = {}
    for a in claim["attachments"]:
        if a["document_type"] not in outcomes:
            raise ValueError("unknown attachment %r" % a["document_type"])
        supplied[a["document_type"]] = a["as_designed"]
    result = {}
    for doc_type, needs in outcomes.items():
        if needs == {True}:
            if doc_type in supplied:
                result[doc_type] = "supplied_" + supplied[doc_type]
            else:
                result[doc_type] = "required_now"
        elif needs == {False}:
            result[doc_type] = "not_needed"
        else:
            result[doc_type] = "held"
    return result


def main(argv):
    here = os.getcwd()
    rules_path = argv[1] if len(argv) > 1 else os.path.join("..", "bundle", "rules.json")
    claims_path = argv[2] if len(argv) > 2 else os.path.join("..", "bundle", "claims.json")
    out_path = argv[3] if len(argv) > 3 else os.path.join(here, "reference.json")
    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)
    with open(claims_path, encoding="utf-8") as f:
        claims = json.load(f)
    by_type = {d["dispute_type"]: d for d in rules["dispute_types"]}
    out_dir = os.path.dirname(os.path.abspath(out_path))
    runs = [(out_path, ALT_NONE)] + [(os.path.join(out_dir, name), alts)
                                     for name, alts in ALTERNATIVES]
    for path, alts in runs:
        out = {}
        for claim in claims["claims"]:
            out[claim["claim_id"]] = evaluate_claim(by_type[claim["dispute_type"]], claim, alts)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
            f.write("\n")


if __name__ == "__main__":
    main(sys.argv)

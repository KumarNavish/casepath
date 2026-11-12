#!/usr/bin/env python3
"""Clean-room evaluator A: derive document states from the rule text.

Usage: python3 evaluate.py [rules.json] [claims.json] [reference.json]
Defaults: ../bundle/rules.json ../bundle/claims.json reference.json
Standard library only; deterministic. See SEMANTICS.md for the reading applied.
"""
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Defining event per dispute type (silence policy: "the dispute's defining event (for a
# termination dispute, that a termination notice was received; for a rent dispute, that a
# rent-increase notification was received) is presumed to have occurred").
# Matched to the fact whose name is the condition of the first, non-optional transition out of
# intake ("termination received", "claim received"). The defect workflow names none.
DEFINING_EVENT = {
    "lease_termination_dispute": "termination_received",
    "rent_increase_dispute": "claim_received",
}

# Transition conditions as boolean expressions over facts. Conditions that name a fact or the
# absence of a branch are gates; conditions not listed here are completion labels of the step
# ("timeline drafted", "outcome recorded", ...) and are treated as satisfied.
# Each entry: function of a fact-value dict (True/False) -> bool.
EDGE_CONDITIONS = {
    # defect_mold_heating
    "health effects alleged": lambda f: f["health_effects"],
    "no immediate health escalation": lambda f: not f["health_effects"],
    "technical inspection needed": lambda f: f["specialist_needed"],
    "deposit route considered without specialist":
        lambda f: f["deposit_considered"] and not f["specialist_needed"],
    "no further specialist or deposit branch":
        lambda f: not f["specialist_needed"] and not f["deposit_considered"],
    "deposit route remains relevant": lambda f: f["deposit_considered"],
    # lease_termination_dispute
    "termination received": lambda f: f["termination_received"],
    "arrears termination": lambda f: f["arrears"],
    "family-home ordinary termination": lambda f: f["family_home"],
    "no special precondition branch": lambda f: not f["arrears"] and not f["family_home"],
    "extension relevant": lambda f: f["extension_relevant"],
    "no extension branch": lambda f: not f["extension_relevant"],
    # rent_increase_dispute
    "claim received": lambda f: f["claim_received"],
    "reference-rate reason selected": lambda f: f["reference_rate"],
    "renovation reason selected": lambda f: f["renovation"],
    "no specialist calculation branch": lambda f: not f["reference_rate"] and not f["renovation"],
}

FLAG_RE = re.compile(r"^scenario flag '([a-z_]+)' is active$")
FACT_STATES = ("stated_true", "denied", "not_mentioned", "raised_and_left_open")


def edge_holds(cond, facts):
    fn = EDGE_CONDITIONS.get(cond)
    return True if fn is None else bool(fn(facts))


def reached_nodes(proc, facts):
    """Fork semantics: a step is reached if any incoming transition from a reached step holds."""
    nodes = [n["node_id"] for n in proc["nodes"]]
    incoming = {n: [] for n in nodes}
    for e in proc["transitions"]:
        incoming[e["target_node_id"]].append(e)
    starts = [n for n in nodes if not incoming[n]]
    reached = set(starts)
    changed = True
    while changed:  # fixpoint (graphs are acyclic; loop is order-independent)
        changed = False
        for n in nodes:
            if n in reached:
                continue
            for e in incoming[n]:
                if e["source_node_id"] in reached and edge_holds(e["condition"], facts):
                    reached.add(n)
                    changed = True
                    break
    return reached


def doc_needed(doc, reached, facts):
    if doc["requirement_class"] == "optional":
        return False
    if not any(n in reached for n in doc["required_at_node_ids"]):
        return False
    if doc["requirement_class"] == "conditional":
        m = FLAG_RE.match(doc["condition"] or "")
        if not m:
            raise ValueError("unparsed document condition: %r" % doc["condition"])
        return bool(facts[m.group(1)])
    return True  # mandatory on a reached step


def fact_value(name, state, defining):
    """Two-valued value of a decided fact; None for an open one."""
    if state == "stated_true":
        return True
    if state == "denied":
        return False
    if state == "not_mentioned":
        # silence policy: branch fact presumed absent; defining event presumed to have occurred
        return name == defining
    if state == "raised_and_left_open":
        return None
    raise ValueError("unknown fact state %r" % state)


def evaluate_claim(dt, claim):
    proc = dt["process_catalog"]
    defining = DEFINING_EVENT.get(dt["dispute_type"])
    fixed, open_facts = {}, []
    for name in dt["condition_catalog"]:
        state = claim["facts"][name]
        v = fact_value(name, state, defining)
        if v is None:
            open_facts.append(name)
        else:
            fixed[name] = v
    open_facts.sort()
    # Enumerate every answer to the open questions; a document needed under every answer is
    # required now, under none is not needed, under some only is held behind the question.
    needed_counts = {d["document_type"]: 0 for d in proc["documents"]}
    worlds = list(itertools.product((True, False), repeat=len(open_facts)))
    for combo in worlds:
        facts = dict(fixed)
        facts.update(zip(open_facts, combo))
        reached = reached_nodes(proc, facts)
        for d in proc["documents"]:
            if doc_needed(d, reached, facts):
                needed_counts[d["document_type"]] += 1
    supplied = {}
    for a in claim["attachments"]:
        # if the same type were supplied twice, a sufficient copy wins
        prev = supplied.get(a["document_type"])
        supplied[a["document_type"]] = "sufficient" if "sufficient" in (prev, a["as_designed"]) else "insufficient"
    out = {}
    for d in proc["documents"]:
        dtyp = d["document_type"]
        c = needed_counts[dtyp]
        if c == len(worlds):
            state = "required_now"
        elif c == 0:
            state = "not_needed"
        else:
            state = "held"
        if state == "required_now" and dtyp in supplied:
            state = "supplied_" + supplied[dtyp]
        # a supplied copy of a held or not-needed document keeps that state (see SEMANTICS.md)
        out[dtyp] = state
    return out


def main(argv):
    rules_path = argv[1] if len(argv) > 1 else os.path.join(HERE, "..", "bundle", "rules.json")
    claims_path = argv[2] if len(argv) > 2 else os.path.join(HERE, "..", "bundle", "claims.json")
    out_path = argv[3] if len(argv) > 3 else os.path.join(HERE, "reference.json")
    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)
    with open(claims_path, encoding="utf-8") as f:
        claims = json.load(f)
    types = {dt["dispute_type"]: dt for dt in rules["dispute_types"]}
    # sanity: every gate fact used by a mapped condition must exist in the catalogue
    result = {}
    for claim in claims["claims"]:
        dt = types[claim["dispute_type"]]
        if set(claim["facts"]) != set(dt["condition_catalog"]):
            raise ValueError("fact set mismatch for %s" % claim["claim_id"])
        for s in claim["facts"].values():
            if s not in FACT_STATES:
                raise ValueError("bad fact state in %s" % claim["claim_id"])
        result[claim["claim_id"]] = evaluate_claim(dt, claim)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv)

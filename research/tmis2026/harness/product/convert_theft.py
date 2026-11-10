"""Convert the reviewed theft rule base into ONE casepath-internal workflow (`casepath.workflow/1`). Deterministic.

    python3 convert_theft.py [--rules rule_review/final/reviewed_rules.json] [--out workflows/theft-reviewed]

Mapping
- workflow        -> one intake step `intake` (all needs attached to it), outcome `closed`; `applies_when` the routing
                     fact `claim_type` is "household_theft" (enum household_theft / other), read by the product's routing
                     as for tenancy. (`fallback: true` was tried first: the product's run does not prepare a case routed
                     to a fallback workflow, it returns at routing.)
- rule condition  -> boolean fact per distinct guard (guard ids as harness/v2/load_reviewed, so rules sharing a
                     condition share the fact: overlay_guard_042 -> g042), question = the condition text; source_refs =
                     the rules and their cited passages. Only conditions some need depends on become facts.
- evidence item   -> for each evidence item (rule.facts[].evidence[] and the rule's confirming_evidence) the CHEAPEST
  (capability)       route is chosen at conversion with the harness's route order (fewest documents, then route id;
                     nothing on file), exactly as the paper engine chooses with nothing on file (theft_methods._route_key).
- document        -> one need per catalogue document that some chosen route contains; id = the harness id in lower
                     case (D07 -> d07); title = the catalogue entry; required_when = the OR (`any`) of the conditions
                     of the evidence items whose chosen route contains it (True if one of them is unconditional);
                     must_show = the must_show texts of those evidence items; `why` = the rules it serves and, for
                     each, the alternative routes that were not chosen.
- confirming evidence (resolver) -> as an evidence item under the rule's condition.
- presumptions    -> none (the theft pack has no silence policy; see harness/v2/presume.py).

What the conversion loses (stated in the workflow's `conversion.loses` too)
1. Alternative routes: the product requests the route fixed at conversion; it cannot switch to another route when the
   files already hold part of it (the paper engine re-chooses with documents on file). Alternatives survive only as
   text in `why`. Evidence items with no route produce no need at all.
2. Rule structure: rule -> fact -> evidence item -> route collapses to document needs with a disjunctive condition;
   which evidence item (and which must_show) a document serves is only text; the facts each rule establishes and its
   requirement kind (obligation, ...) are not represented as data, and the process-node order (n01..) becomes one step.
3. Source passages: the rules' cited passages are kept as source_refs (identifiers), but their text (law, policy terms,
   claim form; given to the Rules-in-context arm) is not in the workflow, so the product's agents cannot read it.
4. Conditions are opaque facts: a rule condition's internal structure (e.g. "A and B") is one boolean fact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "harness" / "v2"))
from theft_data import catalogue, doc_ids  # noqa: E402
from load_reviewed import _guard_id  # noqa: E402  (the guard ids CP4 and Rules in context use for this rule base)

RULES = TMIS / "rule_review" / "final" / "reviewed_rules.json"
VERSION = "2026-11-10"


def route_key(route):  # theft_methods._route_key with nothing on file
    return (len(route["documents"]), len(route["documents"]), sorted(route["documents"]), route["route_id"])


def fact_id(guard_id):
    """overlay_guard_042 -> g042; overlay_guard_068.rev-1a2b3c4d -> g068_rev_1a2b3c4d (guard ids as harness/v2/load_reviewed)."""
    m = re.match(r"overlay_guard_(\d+)(.*)$", guard_id)
    return "g" + m.group(1) + re.sub(r"[^a-z0-9]+", "_", m.group(2).lower()).rstrip("_")


def convert(rules_path=RULES):
    data = json.loads(Path(rules_path).read_text())
    ids = doc_ids()
    cat = catalogue()
    src = "theft-reviewed-rules"
    facts, need = {}, {}
    stats = {"rules": 0, "conditional_rules": 0, "evidence_items": 0, "items_without_route": 0, "items_with_alternatives": 0}

    def item(rule_id, fid, cap, why_prefix):
        stats["evidence_items"] += 1
        routes = cap.get("routes") or []
        if not routes:
            stats["items_without_route"] += 1
            return
        chosen = min(routes, key=route_key)
        others = [r for r in routes if r is not chosen]
        stats["items_with_alternatives"] += bool(others)
        for doc in chosen["documents"]:
            if doc not in ids:
                raise ValueError(f"{rule_id}: document not in the catalogue: {doc[:60]}")
            row = need.setdefault(doc, {"conditions": [], "must_show": [], "why": [], "refs": []})
            row["conditions"].append(fid)
            if cap.get("must_show") and cap["must_show"] not in row["must_show"]:
                row["must_show"].append(cap["must_show"])
            alt = "; ".join(" + ".join(ids[d] for d in r["documents"]) for r in others)
            row["why"].append(f"{why_prefix} ({cap['capability_id']}, route {chosen['route_id']})"
                              + (f"; alternatives not chosen: {alt}" if alt else ""))
            row["refs"].append(f"{src}#{cap['capability_id']}")

    for rule in sorted(data["rules"], key=lambda r: r["rule_id"]):
        rid = rule["rule_id"]
        stats["rules"] += 1
        cond = rule.get("condition")
        fid = None
        if cond:
            stats["conditional_rules"] += 1
            fid = fact_id(_guard_id(rid, cond))
            row = facts.setdefault(fid, {"id": fid, "type": "boolean", "question": f"Does this hold for the claim: {cond['text'].strip()}",
                                         "source_refs": []})
            row["source_refs"] = sorted(set(row["source_refs"]) | {f"{src}#{rid}"} | {f"{src}#{c}" for c in cond.get("cited", [])})
        for f in rule["facts"]:
            for cap in f["evidence"]:
                item(rid, fid, cap, f"{rid}: {rule.get('title', '').strip()}")
        ce = rule.get("confirming_evidence")
        if ce and fid:
            item(rid, fid, ce, f"{rid} (confirms its condition)")

    documents = []
    for doc in cat:
        if doc not in need:
            continue
        row = need[doc]
        conds = row["conditions"]
        if None in conds:
            when = True
        else:
            uniq = sorted(set(conds))
            when = {"fact": uniq[0], "is": True} if len(uniq) == 1 else {"any": [{"fact": c, "is": True} for c in uniq]}
        d = {"id": ids[doc].lower(), "title": doc, "why": " | ".join(row["why"])[:4000],
             "source_refs": sorted(set(row["refs"]))}
        if when is not True:
            d["required_when"] = when
        if row["must_show"]:
            d["must_show"] = row["must_show"]
        documents.append(d)
    used = {c["fact"] for d in documents for c in ([d["required_when"]] if "fact" in d.get("required_when", {}) else
                                                     d.get("required_when", {}).get("any", []))}
    stats["conditions_without_any_need"] = len(set(facts) - used)
    facts = [facts[f] for f in sorted(used)]  # a condition no need depends on cannot change the checklist
    sha = hashlib.sha256(Path(rules_path).read_bytes()).hexdigest()
    cited = sorted({r for d in documents for r in d["source_refs"]} | {r for f in facts for r in f["source_refs"]})
    workflow = {
        "format": "casepath.workflow/1", "id": "household_theft", "version": VERSION,
        "title": "Household insurance: theft claim intake", "status": "reviewed", "example": False,
        "applies_when": {"fact": "claim_type", "is": "household_theft"},
        "sources": [{"id": src, "kind": "expert_review",
                     "title": f"Reviewed theft evidence rules (four-eyes reconciliation), rule_review/final/reviewed_rules.json sha256 {sha[:16]}"}],
        "facts": [{"id": "claim_type", "type": "enum", "values": ["household_theft", "other"],
                   "question": "Is this a household-insurance claim for a theft (household_theft), or something else (other)?",
                   "source_refs": [f"{src}#scope"]}] + facts, "start": "intake",
        "steps": [{"id": "intake", "title": "Theft claim intake: request the evidence the rules require", "role": "claim_handler",
                   "documents": [d["id"] for d in documents], "outcome": "closed", "source_refs": [f"{src}#intake"]}],
        "documents": documents,
        "outcomes": [{"id": "closed", "title": "Intake complete", "source_refs": [f"{src}#intake"]}],
        "notes": [{"text": "Each document need comes from one or more reviewed evidence rules; where a rule allows several routes, the "
                           "cheapest route (fewest documents) was fixed at conversion and the alternatives are named in the need's text.",
                   "source_refs": [f"{src}#conversion"]}],
        "open_questions": [],
        "conversion": {"from": "rule_review/final/reviewed_rules.json", "sha256": sha, "route_choice": "cheapest (fewest documents, then route id), nothing on file",
                       **stats, "documents": len(documents), "condition_facts": len(facts),
                       "loses": ["alternative routes (fixed at conversion; alternatives only as text)",
                                 "rule -> fact -> evidence-item structure and requirement kinds; process-node order",
                                 "text of the cited source passages", "internal structure of a rule condition"]},
    }
    assert cited
    return workflow


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(RULES))
    ap.add_argument("--out", default=str(HERE / "workflows" / "theft-reviewed"))
    a = ap.parse_args()
    import os
    product = Path(os.environ.get("CASEPATH_PRODUCT", "/home/user/work/casepath-product-7ff7af64"))
    sys.path.insert(0, str(product / "casepath-internal"))
    from casepath.process.workflows import validate_workflow
    wf = convert(a.rules)
    validate_workflow(wf)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "household_theft.json"
    path.write_text(json.dumps(wf, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(path, hashlib.sha256(path.read_bytes()).hexdigest()[:16], json.dumps({k: v for k, v in wf["conversion"].items() if k != "loses"}))

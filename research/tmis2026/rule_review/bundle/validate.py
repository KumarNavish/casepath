"""Check a reviewed rules file against the schema, the catalogue and the passages; print a diff summary.

Usage: python3 validate.py rules_reviewed.json [--original rules.json] [--passages passages.json] [--catalogue catalogue.json]
Exit code 0 if valid, 1 otherwise. Standard library only; no network.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("reviewed")
ap.add_argument("--original", default=str(HERE / "rules.json"))
ap.add_argument("--passages", default=str(HERE / "passages.json"))
ap.add_argument("--catalogue", default=str(HERE / "catalogue.json"))
a = ap.parse_args()
orig = {r["rule_id"]: r for r in json.loads(Path(a.original).read_text())["rules"]}
rev_doc = json.loads(Path(a.reviewed).read_text())
passages = {p["id"] for p in json.loads(Path(a.passages).read_text())["passages"]}
docs = {d["name"] for d in json.loads(Path(a.catalogue).read_text())["documents"]}
errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def check_cited(where, cited):
    if not isinstance(cited, list) or not all(isinstance(c, str) for c in cited):
        return err(where, "cited must be a list of strings")
    for c in cited:
        if c.split("#")[0] not in passages:
            err(where, f"citation {c!r} does not resolve to a passage")
        if "#" in c and not re.fullmatch(r"[^#]+#p\d+", c):
            err(where, f"citation {c!r} has a malformed statement part")


def check_evidence(where, ev, prefix):
    if not isinstance(ev, dict) or set(ev) != {"capability_id", "must_show", "cited", "routes"}:
        return err(where, "evidence item needs exactly capability_id, must_show, cited, routes")
    check_cited(where, ev["cited"])
    rids = set()
    for rt in ev["routes"]:
        if not isinstance(rt, dict) or not {"route_id", "documents"} <= set(rt) or set(rt) - {"route_id", "documents", "why"}:
            err(where, "route needs route_id, documents (and optional why)")
            continue
        if rt["route_id"] in rids:
            err(where, f"duplicate route_id {rt['route_id']}")
        rids.add(rt["route_id"])
        if not rt["documents"]:
            err(where, f"route {rt['route_id']} has no document")
        for d in rt["documents"]:
            if d not in docs:
                err(where, f"unknown document {d!r}")
        if len(set(rt["documents"])) != len(rt["documents"]):
            err(where, f"route {rt['route_id']} repeats a document")


rules = rev_doc.get("rules") if isinstance(rev_doc, dict) else None
if not isinstance(rules, list):
    print("INVALID: top level must be {\"pack\": ..., \"rules\": [...]}")
    sys.exit(1)
seen, caps = set(), set()
for r in rules:
    rid = r.get("rule_id")
    where = str(rid)
    if rid in seen:
        err(where, "duplicate rule_id")
    seen.add(rid)
    base = rid.split(".")[0] if isinstance(rid, str) else None
    if rid not in orig and not (base in orig and re.fullmatch(re.escape(base) + r"\.[A-Za-z0-9_-]+", rid)):
        err(where, "unknown rule id (new rules must be <existing rule id>.<suffix>)")
    need = {"rule_id", "title", "process_node", "requirement_kind", "condition", "facts", "confirming_evidence"}
    if set(r) != need:
        err(where, f"fields must be exactly {sorted(need)}")
        continue
    c = r["condition"]
    if c is not None:
        if not isinstance(c, dict) or set(c) != {"guard_id", "text", "cited"} or not str(c.get("text", "")).strip():
            err(where, "condition must be null or {guard_id, text, cited} with non-empty text")
        else:
            check_cited(where + " condition", c["cited"])
    if not r["facts"]:
        err(where, "a rule needs at least one fact")
    for f in r["facts"]:
        fw = f"{where} {f.get('fact_id')}"
        if set(f) != {"fact_id", "statement", "cited", "evidence"}:
            err(fw, "fact needs exactly fact_id, statement, cited, evidence")
            continue
        check_cited(fw, f["cited"])
        if not f["evidence"]:
            err(fw, "a fact needs at least one evidence item")
        for ev in f["evidence"]:
            check_evidence(f"{fw} {ev.get('capability_id')}", ev, f["fact_id"])
            if ev.get("capability_id") in caps:
                err(fw, f"duplicate capability_id {ev.get('capability_id')}")
            caps.add(ev.get("capability_id"))
    if r["confirming_evidence"] is not None:
        check_evidence(where + " confirming_evidence", r["confirming_evidence"], rid)
for rid in orig:
    if rid not in seen:
        err(rid, "original rule missing")

# ---------------------------------------------------------------- diff summary
def routes_of(ev):
    return sorted(tuple(sorted(rt["documents"])) for rt in ev["routes"])


changes = []
for r in rules:
    rid = r.get("rule_id")
    o = orig.get(rid)
    if o is None:
        changes.append(f"{rid}: NEW rule (split)")
        continue
    if (o["condition"] or {}).get("text") != (r.get("condition") or {}).get("text"):
        changes.append(f"{rid}: condition {'added' if not o['condition'] else 'removed' if not r.get('condition') else 'changed'}")
    oe = {e["capability_id"]: e for f in o["facts"] for e in f["evidence"]}
    re_ = {e["capability_id"]: e for f in r.get("facts", []) for e in f.get("evidence", []) if isinstance(e, dict)}
    for cap in sorted(oe.keys() | re_.keys()):
        if cap not in re_:
            changes.append(f"{rid}: evidence {cap} removed")
        elif cap not in oe:
            changes.append(f"{rid}: evidence {cap} added")
        elif routes_of(oe[cap]) != routes_of(re_[cap]):
            changes.append(f"{rid}: routes of {cap}: {routes_of(oe[cap])} -> {routes_of(re_[cap])}")
    if [f["fact_id"] for f in o["facts"]] != [f.get("fact_id") for f in r.get("facts", [])]:
        changes.append(f"{rid}: facts changed")
    oc, rc = o["confirming_evidence"], r.get("confirming_evidence")
    if (oc and routes_of(oc)) != (rc and isinstance(rc, dict) and routes_of(rc)):
        changes.append(f"{rid}: confirming evidence changed")
print(f"{len(rules)} rules; {len(changes)} changes")
for c in changes:
    print("  " + c)
if errors:
    print(f"INVALID: {len(errors)} problems")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("VALID")

"""Offline consolidation of CPv3 knowledge candidates into revised rules (no model calls, no reference answers).

A candidate is an applied result-checker correction attached to a rule (rule, type, document, alternative, quotations,
case). A candidate that recurs for the same rule, type and document(s) in at least two distinct cases is promoted:
  drop                      the document is removed from the rule's routes (a single-document route is removed when
                            the item has another route; an only route leaves the item with no route)
  replace_with_alternative  a route requiring both documents jointly becomes two alternative routes; if they are in
                            different evidence items, the dropped document is removed as for drop
  add                       a new evidence item with a one-document route is added to the rule's first fact
  hold / release            concern the reading of a case, not the rule: recorded, never promoted
Usage (library): promote(pack, candidates, min_cases=2) -> (revised pack, promotions)
"""
from __future__ import annotations

import copy
from collections import defaultdict


def _rule_ids(pack):
    return {b["node_id"] for b in pack["overlay"]["compiled"]}


def _caps(pack, rule_id):
    block = next(b for b in pack["overlay"]["compiled"] if b["node_id"] == rule_id)
    return [c["capability_id"] for f in block["facts"] for c in f["capabilities"]]


def _resolve_rule(pack, cand):
    if cand["rule"] in _rule_ids(pack):
        return cand["rule"]
    req = {r["capability_id"]: r["routes"] for r in pack["requirements"]}
    for b in sorted(pack["overlay"]["compiled"], key=lambda b: b["node_id"]):
        for cap in _caps(pack, b["node_id"]):
            if any(cand["document"] in rt["document_types"] for rt in req.get(cap, [])):
                return b["node_id"]
    return None


def promote(pack, candidates, min_cases=2):
    pack = copy.deepcopy(pack)
    groups = defaultdict(set)
    for c in candidates:
        if c["type"] in {"hold", "release"}:
            continue
        rule = _resolve_rule(pack, c)
        if rule:
            groups[(rule, c["type"], c["document"], c.get("alternative") or "")].add(c["case"])
    req = {r["capability_id"]: r for r in pack["requirements"]}
    promotions = []
    for (rule, kind, doc, alt), cases in sorted(groups.items()):
        if len(cases) < min_cases:
            continue
        changed = False
        caps = _caps(pack, rule)
        if kind in {"drop", "replace_with_alternative"}:
            for cap in caps:
                routes = req.get(cap, {}).get("routes", [])
                for i, rt in enumerate(list(routes)):
                    if doc not in rt["document_types"]:
                        continue
                    if kind == "replace_with_alternative" and alt in rt["document_types"]:
                        rest = [d for d in rt["document_types"] if d not in (doc, alt)]
                        routes[i:i + 1] = [{**rt, "route_id": rt["route_id"] + ".a", "document_types": rest + [alt]},
                                           {**rt, "route_id": rt["route_id"] + ".b", "document_types": rest + [doc]}]
                    elif len(rt["document_types"]) > 1:
                        rt["document_types"] = [d for d in rt["document_types"] if d != doc]
                    else:
                        routes.remove(rt)
                    changed = True
                    break
        elif kind == "add":
            block = next(b for b in pack["overlay"]["compiled"] if b["node_id"] == rule)
            cap_id = f"{rule}.f01.cadd{len(promotions) + 1:02d}"
            block["facts"][0]["capabilities"].append({"capability_id": cap_id, "must_show": f"{doc} (promoted correction)",
                                                      "from_propositions": []})
            new = {"capability_id": cap_id, "routes": [{"route_id": "r1", "document_types": [doc], "why": "promoted"}]}
            pack["requirements"].append(new)
            req[cap_id] = new
            changed = True
        if changed:
            promotions.append({"rule": rule, "type": kind, "document": doc, "alternative": alt, "cases": sorted(cases)})
    return pack, promotions

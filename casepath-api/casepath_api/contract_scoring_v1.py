"""Scoring an arm's document request against a source-built reference contract.

The reference contract says which decisions a case leaves open and which documents each open decision needs. An
arm's checklist is scored against the union of those documents. Two choices here decide what the numbers mean.

**An unknown decision is open.** If the adjudicators could not tell from the narrative whether a decision is
settled, its documents stay in the reference set. The alternative — treating "cannot tell" as "not needed" —
would reward a system for ignoring everything the case does not spell out, which is the opposite of the behaviour
a handler needs.

**Held documents leave the reference set, not the score.** A document the file already holds is not a request,
so it cannot be a hit or a miss. Scoring it either way lets an arm inflate recall by listing what is already there.
"""
from __future__ import annotations

import collections
from typing import Any, Mapping, Sequence

CONTRACT = "casepath.contract-scoring/1.0.0"
OPEN = ("live", "unknown")


def adjudicate(votes: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Majority status per decision across adjudicators. Ties fall open, for the reason above."""
    per: dict[str, list[str]] = collections.defaultdict(list)
    for v in votes:
        for d in v.get("decisions") or []:
            if d.get("decision_id") and d.get("status"):
                per[d["decision_id"]].append(d["status"])
    out = {}
    for k, ss in per.items():
        c = collections.Counter(ss)
        top, n = c.most_common(1)[0]
        tied = [s for s, m in c.items() if m == n]
        status = top if len(tied) == 1 else ("live" if "live" in tied else "unknown")
        out[k] = {"status": status, "votes": dict(c), "unanimous": n == len(ss), "n": len(ss)}
    return out


def reference_set(contract: Mapping[str, Any], statuses: Mapping[str, Mapping[str, Any]],
                  held: Sequence[str] = ()) -> dict[str, Any]:
    """Documents the contract requires for this case: union over decisions that are not settled."""
    held = set(held)
    need: dict[str, list[str]] = collections.defaultdict(list)
    for d in contract["decisions"]:
        st = statuses.get(d["decision_id"], {}).get("status", "unknown")
        if st in OPEN:
            for doc in d.get("required_documents") or []:
                need[doc].append(d["decision_id"])
    return {"documents": sorted(set(need) - held),
            "because": {k: v for k, v in need.items() if k not in held},
            "open_decisions": sorted(k for k, v in statuses.items() if v["status"] in OPEN),
            "settled_decisions": sorted(k for k, v in statuses.items() if v["status"] == "dead"),
            "excluded_as_held": sorted(set(need) & held)}


def score(requested: Sequence[str], reference: Mapping[str, Any], held: Sequence[str] = ()) -> dict[str, Any]:
    """Precision, recall and F1 on the document set, with the two fault types named separately."""
    ref = set(reference["documents"])
    req = set(requested) - set(held)
    hit, over, miss = req & ref, req - ref, ref - req
    p = len(hit) / len(req) if req else (1.0 if not ref else 0.0)
    r = len(hit) / len(ref) if ref else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f1,
            "hit": sorted(hit), "over_requested": sorted(over), "missed": sorted(miss),
            "n_requested": len(req), "n_reference": len(ref),
            "burden": len(req), "unjustified_burden": len(over)}


def score_justification(chains: Sequence[Mapping[str, Any]], reference: Mapping[str, Any],
                        contract: Mapping[str, Any]) -> dict[str, Any]:
    """Whether a request that was right was right *for a reason the contract also holds*.

    An arm can name the correct document from a wrong node. Document-set F1 cannot see that; this can. Arms that
    emit no chains score zero here by construction, which is the honest reading: they offered no justification to
    check, not a justification that failed.
    """
    valid = {d["decision_id"] for d in contract["decisions"]}
    by_doc: dict[str, set[str]] = collections.defaultdict(set)
    for ch in chains or []:
        for doc in ch.get("document_types") or ([ch["document_type"]] if ch.get("document_type") else []):
            src = ch.get("decision_id") or ch.get("node_id")
            if src:
                by_doc[doc].add(src)
    ref_because = reference.get("because") or {}
    grounded = sum(1 for doc in ref_because
                   if by_doc.get(doc) and (by_doc[doc] & set(ref_because[doc]) or by_doc[doc] & valid))
    aligned = sum(1 for doc in ref_because if by_doc.get(doc) and (by_doc[doc] & set(ref_because[doc])))
    n = len(ref_because)
    return {"documents_with_a_chain": sum(1 for d in ref_because if by_doc.get(d)),
            "chain_reaches_a_contract_decision": grounded,
            "chain_reaches_the_right_decision": aligned,
            "justified_rate": grounded / n if n else 0.0,
            "correctly_justified_rate": aligned / n if n else 0.0,
            "n_reference_documents": n}

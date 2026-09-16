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
                        contract: Mapping[str, Any], graph: Mapping[str, Any] | None = None,
                        propositions: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Whether a request that was right was right *for a reason the contract also holds*.

    Node identifiers cannot be compared directly. The induced graph and the reference contract are built
    independently and partition the same law differently — on this scope the graph runs downstream into the
    conciliation and court stages while the contract stays upstream on form, timing and substance. Neither is
    wrong; they are different cuts. Requiring their names to match would measure agreement on vocabulary and call
    it agreement on law.

    They do share one vocabulary: the authorities. Both cite Fedlex passages by identifier, and those identifiers
    are fixed by the corpus rather than chosen by either author. So a chain counts as justified when the authority
    it rests on is an authority the contract also relies on for a decision that requires that same document.

    Arms that emit no chains score zero, which is the honest reading — no justification was offered to check,
    rather than one offered and found wanting.
    """
    # document -> authorities the contract relies on for it
    want: dict[str, set[str]] = collections.defaultdict(set)
    for d in contract["decisions"]:
        auth = {e["authority_id"] for e in d.get("evidence") or []}
        for doc in d.get("required_documents") or []:
            want[doc] |= auth

    node_auth: dict[str, set[str]] = collections.defaultdict(set)
    if graph and propositions:
        for n in graph.get("nodes") or []:
            for pid in n.get("supported_by") or []:
                pr = propositions.get(pid) or {}
                for a in ([pr.get("authority_id")] if pr.get("authority_id") else pr.get("authorities") or []):
                    if a:
                        node_auth[n["node_id"]].add(a)

    got: dict[str, set[str]] = collections.defaultdict(set)
    for ch in chains or []:
        docs = ch.get("document_types") or ([ch["document_type"]] if ch.get("document_type") else [])
        auths = set(ch.get("authorities") or [])
        src = ch.get("decision_id") or ch.get("node_id")
        if src:
            auths |= node_auth.get(src, set())
        for doc in docs:
            got[doc] |= auths

    ref_because = reference.get("because") or {}
    n = len(ref_because)
    with_chain = [d for d in ref_because if got.get(d)]
    shared = [d for d in with_chain if got[d] & want.get(d, set())]
    return {"n_reference_documents": n,
            "documents_with_a_chain": len(with_chain),
            "chain_shares_an_authority_with_the_contract": len(shared),
            "chain_rate": len(with_chain) / n if n else 0.0,
            "grounded_rate": len(shared) / n if n else 0.0,
            "ungrounded": sorted(set(with_chain) - set(shared))}

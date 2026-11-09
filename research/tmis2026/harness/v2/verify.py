"""V3 Evidence-bearing verification.

The verifier must quote, for every rejection, the exact case text that contradicts the proposition. A
rejection of a condition verdict counts only if it carries at least one contradicting quotation that is an
exact span of the named source; otherwise the verdict stands. The family is admitted whenever the verifier
affirms family_supported (the separate category check no longer decides it). Document assessments keep the
Study 1 rule (a rejected sufficiency claim makes the document insufficient, i.e. it is requested): rejecting
sufficiency can only add a request, and insufficiency is typically shown by absence, which cannot be quoted.
"""
from __future__ import annotations

import copy

import match

ID = {"type": "string", "maxLength": 120}


def obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(items, n):
    return {"type": "array", "items": items, "maxItems": n}


CONTRA = arr(obj({"artifact_id": ID, "quote": {"type": "string", "maxLength": 800}}), 4)
TENANCY_SCHEMA = obj({"family_supported": {"type": "boolean"},
                      "checks": arr(obj({"item_id": ID, "accepted": {"type": "boolean"}, "reason": {"type": "string", "maxLength": 1200},
                                         "contradicting_citations": CONTRA}), 60),
                      "issues": arr({"type": "string", "maxLength": 1200}, 20)})
THEFT_SCHEMA = obj({"checks": arr(obj({"item_id": {"type": "string", "maxLength": 80}, "accepted": {"type": "boolean"},
                                       "reason": {"type": "string", "maxLength": 200},
                                       "contradicting_quote": {"type": "string", "maxLength": 400}}), 90),
                    "issues": arr({"type": "string", "maxLength": 400}, 10)})
RULE = """EVIDENCE RULE FOR REJECTIONS: Reject a condition verdict only when the case text contradicts it, and quote that
contradicting text exactly (verbatim, contiguous, from the named source) in the contradicting quotation field. A rejection
without an exact contradicting quotation is ignored and the verdict stands. Do not reject merely for imperfect
wording of the proposer's quotation; quotation exactness is checked by code."""


def effective_tenancy(verifier: dict, proposal_rows: dict, sources: list[dict]) -> tuple[dict, dict]:
    """Return (verifier output for validate_interpretation, diagnostics). V3 + V6: quotations are located with the
    robust matcher; the family is refuted only by family_supported=false WITH a locatable contradicting quotation."""
    texts = {s["artifact_id"]: s["text"] for s in sources}
    out = copy.deepcopy(verifier)
    diag = {"rejections": 0, "counted": 0, "ignored_no_quote": 0, "ignored_inexact": 0, "same_as_own_citation": 0,
            "category_overridden": False, "family_refuted": False}

    def located(quotes):
        return [q for q in quotes if q.get("quote") and match.contains(texts.get(q["artifact_id"], ""), q["quote"])]

    cat = next((c for c in out["checks"] if c["item_id"] == "category"), None)
    refuted = (not verifier["family_supported"]) and bool(located((cat or {}).get("contradicting_citations") or []))
    diag["family_refuted"] = refuted
    if not refuted and (not verifier["family_supported"] or (cat and not cat["accepted"])):
        diag["category_overridden"] = True
    out["family_supported"] = not refuted
    for chk in out["checks"]:
        item = chk["item_id"]
        if item == "category":
            chk["accepted"] = not refuted
            continue
        if not item.startswith("condition:") or chk["accepted"]:
            continue
        diag["rejections"] += 1
        quotes = chk.get("contradicting_citations") or []
        exact = located(quotes)
        if not quotes:
            diag["ignored_no_quote"] += 1
            chk["accepted"] = True
        elif not exact:
            diag["ignored_inexact"] += 1
            chk["accepted"] = True
        else:
            diag["counted"] += 1
            own = {match.normalise(c["quote"]) for c in proposal_rows.get(item, {}).get("citations", [])}
            diag["same_as_own_citation"] += int(all(match.normalise(q["quote"]) in own for q in exact))
    for chk in out["checks"]:
        chk.pop("contradicting_citations", None)
    return out, diag


def effective_theft(checks: list[dict], text: str) -> tuple[dict, dict]:
    accepted, diag = {}, {"rejections": 0, "counted": 0, "ignored": 0}
    for chk in checks:
        ok = chk["accepted"]
        if not ok:
            diag["rejections"] += 1
            q = chk.get("contradicting_quote") or ""
            if q and match.contains(text, q):
                diag["counted"] += 1
            else:
                diag["ignored"] += 1
                ok = True
        accepted[chk["item_id"]] = ok
    return accepted, diag

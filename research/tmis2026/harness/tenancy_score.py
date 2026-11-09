"""Score evidence plans against tenancy references."""
from __future__ import annotations

from tenancy_data import intake, reference


def unscored(claim_id: str) -> set[str]:
    """Documents no text-only method can judge: a supplied photo the reference counts as provided."""
    has_image = any(a["media_type"].startswith("image/") for a in intake(claim_id)["attachments"])
    ref = reference(claim_id)
    return {"dated_photos"} if has_image and "dated_photos" not in ref["document_states"] and ref["family"] == "defect_mold_heating" else set()


def score(claim_id: str, plan: dict | None) -> dict:
    ref = reference(claim_id)
    skip = unscored(claim_id)
    R = set(ref["request_set"]) - skip
    if plan is None:  # failed output: no plan at all
        return {"claim_id": claim_id, "available": False, "tp": 0, "fp": 0, "fn": len(R), "n_ref": len(R),
                "holds": 0, "held_required": 0, "family_ok": False, "deferred": False}
    P = set(plan.get("requests", [])) - skip
    H = set(plan.get("holds", [])) - skip
    return {"claim_id": claim_id, "available": True, "tp": len(P & R), "fp": len(P - R), "fn": len(R - P),
            "n_ref": len(R), "holds": len(H), "held_required": len(H & R),
            "family_ok": plan.get("family") == ref["family"], "deferred": bool(plan.get("deferred"))}

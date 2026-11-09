"""Score theft checklists: signed changes for off->on pairs (frozen scorer) and
premature requests / holds for off->unresolved pairs."""
from __future__ import annotations

from theft_data import best_realization


def delta(before: set, after: set) -> list[str]:
    return sorted({f"+{d}" for d in after - before} | {f"-{d}" for d in before - after})


def score_pair(pair: dict, off_plan: dict | None, var_plan: dict | None) -> dict:
    ref = pair["reference"]
    if off_plan is None or var_plan is None:
        return {"pair_id": pair["pair_id"], "kind": pair["kind"], "available": False}
    pred = delta(set(off_plan["requests"]), set(var_plan["requests"]))
    if pair["kind"] == "on":
        selected, m = best_realization(pred, ref)
        wrong = sorted(set(pred) - set(selected))
        return {"pair_id": pair["pair_id"], "kind": "on", "available": True, "condition": pair["condition"],
                "story": pair["story"], "correct": m["tp"],
                "wrong": len(wrong), "wrong_add": sum(w.startswith("+") for w in wrong),
                "wrong_withdraw": sum(w.startswith("-") for w in wrong),
                "missed": len(set(selected) - set(pred)), "exact": set(pred) == set(selected)}
    # unresolved variant: no request should change; the condition's documents should be held
    on_docs = {d.lstrip("+") for option in ref["acceptable_signed_deltas"] for d in option}
    held_ok = any(all(d.lstrip("+") in set(var_plan["holds"]) for d in option) for option in ref["acceptable_signed_deltas"])
    premature = sorted(d for d in set(var_plan["requests"]) - set(off_plan["requests"]) if d in on_docs)
    return {"pair_id": pair["pair_id"], "kind": "unresolved", "available": True, "condition": pair["condition"],
            "story": pair["story"], "changes": len(pred), "premature": len(premature) > 0,
            "other_changes": len([p for p in pred if p.lstrip("+-") not in on_docs]), "held": held_ok,
            "stable": len(pred) == 0}


def pooled(rows: list[dict]) -> dict:
    on = [r for r in rows if r["kind"] == "on" and r["available"]]
    c, w, m = (sum(r[k] for r in on) for k in ("correct", "wrong", "missed"))
    p = c / (c + w) if c + w else 0.0
    rec = c / (c + m) if c + m else 0.0
    return {"pairs": len(on), "correct": c, "wrong": w, "wrong_add": sum(r["wrong_add"] for r in on),
            "wrong_withdraw": sum(r["wrong_withdraw"] for r in on), "missed": m,
            "precision": p, "recall": rec, "f1": 2 * p * rec / (p + rec) if p + rec else 0.0,
            "exact": sum(r["exact"] for r in on)}

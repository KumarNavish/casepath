"""Extract Figure 1's input data from stored files (read-only, no model call) into f1_data.json.

Pair: fresh2 theft story 13 (a social worker's e-mail), condition PR_third_party_causer.
  claim A = s13-on-PR_third_party_causer   (the sentence states the fact)
  claim B = s13-unres-PR_third_party_causer (the sentence leaves it open)
The two texts differ in exactly one sentence (fresh2/theft_fresh2.py builds both from the same off text by one
replacement). Checklists: the full product, run index 0 of each (runs/study3/confirm/plans_theft_casepath.json).
"""
import json, re, sys
from pathlib import Path

T = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(T / "fresh2"))
import theft_fresh2  # noqa: E402

A, B, RUN = "s13-on-PR_third_party_causer", "s13-unres-PR_third_party_causer", 0
texts = theft_fresh2.texts()
plans = json.loads((T / "runs/study3/confirm/plans_theft_casepath.json").read_text())
wf = json.loads((T / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())


def cond_facts(rw):
    if rw is None:
        return []
    if "any" in rw:
        return [c["fact"] for c in rw["any"]]
    return [rw["fact"]]


def paragraphs(text):
    """Sentences per paragraph, with character lengths (for the measured page miniature)."""
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        sents = [s for s in re.split(r"(?<=[.!?])\s+|\n", para) if s.strip()]
        out.append([s.strip() for s in sents])
    return out


def side(tid):
    r = plans[f"PRODUCT|{tid}|{RUN}"]
    p = r["plan_ids"]
    rows = []
    for d in wf["documents"]:
        st = "request" if d["id"] in p["requests"] else "hold" if d["id"] in p["holds"] else "not_needed"
        qs = [f for f in cond_facts(d.get("required_when")) if f in p["questions"]] if st == "hold" else []
        rows.append({"doc": d["id"], "state": st, "questions": qs})
    return {"text_id": tid, "run": RUN, "paragraphs": paragraphs(texts[tid]["text"]), "rows": rows,
            "questions": p["questions"], "added_requests": p["added_requests"], "added_holds": p["added_holds"],
            "suggested_by_model": [{"title": n["title"], "required": n["required"]}
                                   for n in r["product_extra"].get("agent_added_needs", [])],
            "fact_g042": r["product_extra"]["facts"]["g042_rev_92ab8925"]}


a, b = side(A), side(B)
pa = [s for p in a["paragraphs"] for s in p]
pb = [s for p in b["paragraphs"] for s in p]
changed = [i for i, (x, y) in enumerate(zip(pa, pb)) if x != y]
assert len(pa) == len(pb) and len(changed) == 1, (len(pa), len(pb), changed)
diff_lines = [r["doc"] for r, s in zip(a["rows"], b["rows"]) if r["state"] != s["state"]]
diff_q = sorted(set(a["questions"]) ^ set(b["questions"]))
out = {"source": {"texts": "research/tmis2026/fresh2/theft/BENCHMARK_FRESH2.json via fresh2/theft_fresh2.py",
                  "checklists": "research/tmis2026/runs/study3/confirm/plans_theft_casepath.json",
                  "workflow": "research/tmis2026/harness/product/workflows/theft-reviewed/household_theft.json"},
       "a": a, "b": b, "changed_sentence_index": changed[0], "sentence_a": pa[changed[0]], "sentence_b": pb[changed[0]],
       "checklist_lines_changed": diff_lines, "questions_changed": diff_q}
(Path(__file__).parent / "f1_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print("changed sentence", changed, "lines", diff_lines, "questions", diff_q)
print("suggested A", a["suggested_by_model"]); print("suggested B", b["suggested_by_model"])

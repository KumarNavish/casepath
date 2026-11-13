"""Extract Figure 2's input data from stored files (read-only, no model call) into f2_data.json.

Same case as Figure 1: fresh2 theft story 13, condition PR_third_party_causer, full product, run index 0.
For each of the two claims: the changed sentence; the three stored readings of fact g042_rev_92ab8925 (verdict and
quotation, from the product's response cache, runs/product/cache/<key>.json, in call order); whether each quotation
occurs word for word in the file; the fact as the product stored it; the workflow rule that names the fact; the
checklist line; the model-suggested extra line the record holds.
"""
import json, sys
from pathlib import Path

T = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(T / "fresh2"))
import theft_fresh2  # noqa: E402

FACT, DOC, RUN = "g042_rev_92ab8925", "d15", 0
CLAIMS = {"a": "s13-on-PR_third_party_causer", "b": "s13-unres-PR_third_party_causer"}
texts = theft_fresh2.texts()
plans = json.loads((T / "runs/study3/confirm/plans_theft_casepath.json").read_text())
wf = json.loads((T / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
f1 = json.loads((T / "rebuild/figures/f1/f1_data.json").read_text())
cache = T / "runs/product/cache"

out = {"fact": FACT, "fact_question": next(f["question"] for f in wf["facts"] if f["id"] == FACT),
       "doc": DOC, "doc_title": next(d["title"] for d in wf["documents"] if d["id"] == DOC),
       "rule": next(d["required_when"] for d in wf["documents"] if d["id"] == DOC),
       "source": {"records": "research/tmis2026/runs/study3/confirm/plans_theft_casepath.json",
                  "readings": "research/tmis2026/runs/product/cache/<key>.json (keys listed in each record)",
                  "workflow": "research/tmis2026/harness/product/workflows/theft-reviewed/household_theft.json"}}
for side, tid in CLAIMS.items():
    rec = plans[f"PRODUCT|{tid}|{RUN}"]
    text = texts[tid]["text"]
    readings = []
    for k in dict.fromkeys(rec["keys"]):
        body = json.loads(json.loads((cache / f"{k}.json").read_text())["body"])
        content = body["choices"][0]["message"].get("content")
        try:
            v = json.loads(content) if content else None
        except ValueError:
            v = None
        if isinstance(v, dict) and "conditions" in v and len(v["conditions"]) > 2:   # a full reading, not a requote
            row = next(x for x in v["conditions"] if x["id"] == FACT)
            readings.append({"key": k, "verdict": row["verdict"], "quote": row["quote"],
                             "found_in_file": bool(row["quote"]) and row["quote"] in text})
    assert len(readings) == 3, (side, len(readings))
    p = rec["plan_ids"]
    out[side] = {"text_id": tid, "sentence": f1["sentence_" + side], "readings": readings,
                 "fact_stored": rec["product_extra"]["facts"][FACT],
                 "line": "request" if DOC in p["requests"] else "hold" if DOC in p["holds"] else "not_needed",
                 "question": FACT in p["questions"],
                 "reached": rec["product_extra"]["reached"],
                 "document_judgment": rec["product_extra"]["document_judgments"].get(DOC),
                 "suggested_by_model": [n["title"] for n in rec["product_extra"]["agent_added_needs"]],
                 "agents": rec["agents"]}
(Path(__file__).parent / "f2_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
for s in "ab":
    print(s, [(r["verdict"], r["quote"], r["found_in_file"]) for r in out[s]["readings"]], out[s]["fact_stored"],
          out[s]["line"], out[s]["question"], out[s]["document_judgment"])

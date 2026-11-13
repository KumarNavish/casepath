"""Figure 3: the checklist of one real file under three readings of its one open fact. No model call.

    <lintvenv>/bin/python -I -B compute.py      # writes f3_data.json

Instance: study4/dev/theft/final/the_12ee892d56f4 (public-rule benchmark, development), type simple_theft_away,
workflow study4/rules/theft/workflow/simple_theft_away.json (revision 3). Its design leaves traces_changed open; the
stored revision-3 run (study4/lint/runs, clean_rev3) has all three readings answer open, quoting the same sentence.

Facts: the file's designed facts as generator/reference.py builds them (lint/diagnose.designed_inputs). The fact
traces_changed is then set three ways and the product's own evaluator (workflows.evaluate, worktree read-only) runs:
  true   : two-valued reading forced to true
  false  : two-valued reading forced to false
  open   : left unresolved (the product's three-valued evaluation, exact deferral over the completions)
Documents: none on file (checked=True), so every needed document is a request; this isolates the branch logic
from the file's attachments. The fragment drawn is a_police -> {a_traces | direct} -> a_instruction_check -> ... -> a_loss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[2]
S4 = TMIS / "study4"
sys.path[:0] = [str(S4 / "lint"), str(S4 / "generator")]
import analyse as A  # noqa: E402
import diagnose as DG  # noqa: E402
import genlib as G  # noqa: E402

W = DG.W
FID = "the_12ee892d56f4"


def main():
    regime = G.Regime("theft")
    x = A.files("theft")[FID]
    design = x["design"]
    wf = regime.workflows[design["type"]]
    Df, _ = DG.designed_inputs(regime, design)
    assert "traces_changed" not in Df
    out = {"file": f"study4/dev/theft/final/{FID}", "workflow": "study4/rules/theft/workflow/simple_theft_away.json",
           "facts_given": Df, "readings": {}}
    for label, val in (("true", True), ("false", False), ("open", None)):
        facts = dict(Df)
        if val is not None:
            facts["traces_changed"] = val
        ev = W.evaluate(wf, facts, {}, checked=True)
        docs = {}
        for r in ev["documents"]:
            st = "hold" if r["required"] == "depends" else "optional" if r["required"] in ("optional", "suggested") else "request"
            docs[r["document"]] = {"state": st, "questions": [q["fact"] for q in r.get("questions") or []]}
        for d in wf["documents"]:
            docs.setdefault(d["id"], {"state": "not_on_list", "questions": []})
        out["readings"][label] = {"documents": docs, "waiting_for": [w["fact"] for w in ev.get("waiting_for", [])],
                                  "reached": ev.get("reached"), "deferral": ev.get("deferral")}
    # stored run: what the three readings said about traces_changed (data, for the contract)
    e = A.results("clean_rev3", "theft")[FID]
    res = A.record(e)["case"]["run"]["result"]
    row = next(r for r in res["facts"] if r["fact"] == "traces_changed")
    out["stored_run_traces_changed"] = {"status": row["status"], "open_readings": row.get("open_readings"),
                                        "quotes": [c.get("quote") for c in row.get("citations") or []]}
    # reference.json agrees with the open evaluation?
    ref = x["reference"]["documents"]
    out["reference_police_consent"] = ref["police_consent"]
    out["reference_stolen_items_list"] = ref["stolen_items_list"]
    (HERE / "f3_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in out["readings"].items():
        print(k, {d: s["state"] + ("?" + ",".join(s["questions"]) if s["questions"] else "") for d, s in v["documents"].items()},
              "waiting", v["waiting_for"])
    print(out["stored_run_traces_changed"])


if __name__ == "__main__":
    main()

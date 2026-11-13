"""Figure 6, left: recompute every stored theft checklist (Study 4 lint, revision 3, clean arm) after one rule edit.
No model call: the script imports no client, reads only stored run records and runs the product's own evaluator.

    <lintvenv>/bin/python -I -B compute.py      # writes f6_data.json

Edit (one line, a copy in this folder; nothing under study4/ is changed):
    simple_theft_away.before.json  = study4/rules/theft/workflow/simple_theft_away.json (revision 3, the rules the runs read)
    simple_theft_away.after.json   = the same with police_report "optional": true -> false (the police report becomes
                                     a required document of a simple theft away; AVB Ziff. 8 lit. f lets the insurer call for it)

For every one of the 56 files:
  stored    : the product's stored facts and accepted document findings (diagnose.product_inputs) through
              workflows.evaluate(before) -> checklist A; must reproduce the stored plan (checked);
              the same inputs through workflows.evaluate(after)      -> checklist B.
  reference : the file's design (diagnose.designed_inputs, as generator/reference.py) through evaluate(before) -> R_A
              (must equal reference.json, checked) and evaluate(after) -> R_B.
A checklist line is one catalogue document of the file's type, in one of: request, hold, on_file, optional (listed,
not asked), not_needed. Files the product handed over unrouted have no checklist; their lines are 'unrouted'.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[2]
S4 = TMIS / "study4"
sys.path[:0] = [str(S4 / "lint"), str(S4 / "generator")]
import analyse as A  # noqa: E402
import diagnose as DG  # noqa: E402  (imports the product's evaluator read-only from the worktree)
import genlib as G  # noqa: E402

W = DG.W
REGIME = "theft"
TYPE = "simple_theft_away"
EDITED_DOC = "police_report"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def line_states(wf, facts, findings):
    ev = W.evaluate(wf, facts, findings, checked=True)
    rows = {r["document"]: r for r in ev["documents"]}
    out = {}
    for d in wf["documents"]:
        r = rows.get(d["id"])
        if r is None:
            out[d["id"]] = "not_needed"
        elif r["required"] in ("optional", "suggested"):
            out[d["id"]] = "on_file" if r["status"] == "present" else "optional"
        elif r["required"] == "depends":
            out[d["id"]] = "hold"
        else:
            out[d["id"]] = "on_file" if r["status"] == "present" else "request"
    return out, ev


def plan(states):
    return ({d for d, s in states.items() if s == "request"}, {d for d, s in states.items() if s == "hold"})


def main():
    before = load(HERE / "simple_theft_away.before.json")
    after = load(HERE / "simple_theft_away.after.json")
    assert before == load(S4 / "rules" / REGIME / "workflow" / f"{TYPE}.json"), "before copy differs from the rules the runs read"
    W.validate_workflow(after)
    regime = G.Regime(REGIME)  # rules/theft/ = revision 3, as analyse.workflows('clean_rev3')
    wf_before = dict(regime.workflows)
    wf_after = {**wf_before, TYPE: after}
    F = A.files(REGIME)
    R = A.results("clean_rev3", REGIME)
    files, checks = [], Counter()
    calls_stored = 0
    for fid, x in F.items():
        design, ref = x["design"], x["reference"]
        tid = design["type"]
        e = R[fid]
        calls_stored += int(e.get("calls") or 0)
        # reference, before and after
        Df, Dd = DG.designed_inputs(regime, design)
        RA, _ = line_states(wf_before[tid], Df, Dd)
        RB, _ = line_states(wf_after[tid], Df, Dd)
        for d, s in RA.items():
            rs = ref["documents"][d]["state"]
            want = {"present_sufficient": "on_file", "present_insufficient": "request"}.get(rs, rs)
            if ref["documents"][d].get("optional") and not ref["documents"][d].get("request") and s == "optional":
                want = "optional"  # an optional document, absent or unusable: listed, not asked
            checks["reference_replay_equal" if s == want else "reference_replay_differs"] += 1
        # stored readings, before and after
        p = e.get("plan") or {}
        routed = p.get("family") if p and not p.get("deferred") else None
        if routed is None:
            SA = {d: "unrouted" for d in RA}
            SB = dict(SA)
        else:
            rec = A.record(e)
            res = rec["case"]["run"]["result"]
            Pf, Pd = DG.product_inputs(res)
            SA, _ = line_states(wf_before[routed], Pf, Pd)
            SB, _ = line_states(wf_after[routed], Pf, Pd)
            req, hold = plan(SA)
            same = req == set(p.get("requests") or []) and hold == set(p.get("holds") or [])
            checks["stored_replay_reproduces_plan" if same else "stored_replay_differs_from_plan"] += 1
            # stored replay never sees the reference: lines are compared on the routed type's catalogue
            if routed != tid:
                checks["routed_to_other_type"] += 1
        lines = []
        for d in sorted(set(RA) | set(SA)):
            lines.append({"document": d, "ref_before": RA.get(d), "ref_after": RB.get(d),
                          "stored_before": SA.get(d), "stored_after": SB.get(d)})
        files.append({"file": fid, "type": tid, "routed": routed, "calls_stored_run": e.get("calls"), "lines": lines})

    # measures
    m = Counter()
    per_file_changed = []
    for f in files:
        ch_s = [l for l in f["lines"] if l["stored_before"] != l["stored_after"]]
        ch_r = [l for l in f["lines"] if l["ref_before"] != l["ref_after"]]
        m["lines_total"] += len(f["lines"])
        m["files"] += 1
        m["files_checklist_changed"] += bool(ch_s)
        m["files_reference_changed"] += bool(ch_r)
        m["lines_changed"] += len(ch_s)
        m["lines_reference_changed"] += len(ch_r)
        for l in f["lines"]:
            cs = l["stored_before"] != l["stored_after"]
            cr = l["ref_before"] != l["ref_after"]
            if cs and cr:
                m["changed_and_should" + ("_same_new_state" if l["stored_after"] == l["ref_after"] else "_other_new_state")] += 1
            elif cs:
                m["collateral_changed_should_not"] += 1
                m["collateral_on_other_document" if l["document"] != EDITED_DOC else "collateral_on_edited_document"] += 1
            elif cr:
                m["missed_should_change_did_not"] += 1
            if cs:
                m[f"transition {l['stored_before']} -> {l['stored_after']}"] += 1
            if cr:
                m[f"ref transition {l['ref_before']} -> {l['ref_after']}"] += 1
        per_file_changed.append({"file": f["file"], "type": f["type"], "routed": f["routed"],
                                 "changed": [(l["document"], l["stored_before"], l["stored_after"]) for l in ch_s],
                                 "reference_changed": [(l["document"], l["ref_before"], l["ref_after"]) for l in ch_r]})
    out = {"label": "Figure 6 left: DEVELOPMENT data (Study 4 public-rule benchmark, theft, clean arm revision 3); replay, no model call",
           "edit": {"workflow": f"rules/{REGIME}/workflow/{TYPE}.json (copied)", "line": 379,
                    "before": '"optional": true', "after": '"optional": false', "document": EDITED_DOC},
           "model_calls_in_this_recomputation": 0,
           "model_calls_how_known": "this script imports no model client and opens no network connection; it reads stored records and runs workflows.evaluate (pure function)",
           "model_calls_of_the_stored_runs_being_reused": calls_stored,
           "checks": dict(checks), "measures": dict(sorted(m.items())), "files": per_file_changed, "detail": files}
    (HERE / "f6_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"checks": out["checks"], "measures": out["measures"], "calls_stored": calls_stored}, indent=1))


if __name__ == "__main__":
    main()

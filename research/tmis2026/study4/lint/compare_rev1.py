"""Part C: the clean arm before (rules rev0) and after (rules revised after first use) on the files re-run with the
revised rules. DEVELOPMENT, post hoc, in-sample, not a result: the fixes were designed on these same files.

    python3 -I -B study4/lint/compare_rev1.py      # writes lint/COMPARE_REV1.json and lint/COMPARE_REV1.md

Reads only stored material: runs/results_clean_<regime>_gpt-6-luna.json (before), runs/results_clean_rev1_<regime>_
gpt-6-luna.json (after), the run records, the cached readings, each file's design and reference, REV1_PLAN.json and the
ledgers. Scoring is lint/analyse.py's part (d) rule, unchanged. Both columns are computed on the same files: those the
re-run stored.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyse as A  # noqa: E402

KINDS = A.KINDS
SHORT = {"unneeded_request": "UR", "missed_request": "MR", "unwarranted_hold": "UH", "missed_hold": "MH"}
FACTS = {"tenancy": [("lease_termination_dispute", "asserted_claims")],
         "dismissal": [("wrongful_termination", "retaliation_for_claims")],
         "theft": [("theft_at_home", "household_perpetrator"), ("theft_at_home", "measures_pending"),
                   ("simple_theft_away", "measures_pending")]}


def summarise(rows):
    n = len(rows)
    if not n:
        return {"files": 0}
    out = {"files": n, **{k: round(sum(r["errors"][k] for r in rows) / n, 3) for k in KINDS}}
    out["errors_per_file"] = round(sum(r["total"] for r in rows) / n, 3)
    out["errors"] = sum(r["total"] for r in rows)
    out["files_without_error"] = sum(r["total"] == 0 for r in rows)
    out["routing_failures_denied"] = sum(r["routing_failure"] and r["denied_event"] for r in rows)
    out["routing_failures_not_denied"] = sum(r["routing_failure"] and not r["denied_event"] for r in rows)
    out["failed_runs"] = sum(r["failed"] for r in rows)
    return out


def fact_admission(regime, F, R, arm, ids):
    wfs = A.workflows(regime, arm)
    out = {}
    for t, fact in FACTS[regime]:
        c = Counter()
        for fid in ids:
            x = F[fid]
            if x["design"]["type"] != t:
                continue
            st = x["design"]["facts"].get(fact)
            v = A.run_view(R[fid], wfs[t])
            if not v or v.get("facts") is None:
                c[(st, "not read")] += 1
                continue
            fv = v["facts"][fact]
            c[(st, "established true" if fv["admitted_true"] else f"{fv['status']} {fv['value']}")] += 1
        out[f"{t}.{fact}"] = {f"{a} -> {b}": n for (a, b), n in sorted(c.items())}
    return out


def spend():
    by = defaultdict(float)
    n = Counter()
    for p in sorted((HERE / "runs").glob("ledger_dev_*.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "rev1" in (r.get("arm") or ""):
                    by[r["arm"]] += float(r.get("usd") or 0)
                    n[r["arm"]] += 1
    return {"by_arm_label": {k: round(v, 6) for k, v in sorted(by.items())}, "paid_calls": dict(n), "total_usd": round(sum(by.values()), 6)}


NOTES = """## Reading the comparison

- Coverage: 95 of 176 files were re-run (tenancy 31 of 59, theft 42 of 59, dismissal 22 of 58), in the order fixed in
  REV1_PLAN.json: P1 the 16 non-denied routing failures owed to wording, P2 all 24 denied-event files, P3 the files of
  the changed fact wordings, P4 five seeded error-free control files per regime, P5 the remaining files with errors
  until the stop line (tenancy 9 of 9, theft 5 of 8, dismissal 0 of 16). The selection is weighted to the files the
  fixes target, so the after-figures are not regime estimates.
- Each "after" is a new single run: every reading and routing request changed text, so it is a fresh draw. Changes in
  files the fixes do not touch (for example ten_270f84d8acff from 4 holds to 0, ten_eec676341229 from 1 to 3 errors,
  the_fefc066e8269 from 0 to 1) show the run-to-run variation of the product; differences of one or two errors are
  within it.
- Routing failures, denied-event files: the count rises from 19 to 20 because ten_8572ddc89110 (denied) is now left
  unrouted, which is the empty plan the rule text gives (0 errors before and after). dis_ff1e9056d2c3 (an immediate
  dismissal denied by stating an ordinary notice) is now unrouted too, which removes its 5 errors against the stop
  reference; under the rule text it belongs to type 1 or 2 (benchmark design, DIAGNOSIS.md). The 6 theft denied files
  routed to the other type stay so (24 errors, benchmark design).
- the_248aa95805a8 (flatmate theft at home, household_perpetrator stated true) is now routed to theft_at_home, but two
  readings of three still answer that whether the flatmate did it is open, so the product holds the exclusion's four
  documents (4 holds; before, the unrouted empty plan coincided with the stop reference: 0 errors). The routing fix
  exposes the household reading of the_656f9aad39e5's kind (DIAGNOSIS.md, cause 6), not a new defect.
- Non-denied routing failures left after the revision: the_32a656cb56cf and the_d76f5df60f83, whose defining event is
  designed open and is itself the routing question (benchmark design).
"""


def main():
    plan = json.loads((HERE / "REV1_PLAN.json").read_text())
    rep = {"label": "DEVELOPMENT, post hoc, in-sample: the wording fixes were designed on these same files. Not a result.",
           "regimes": {}, "spend": spend(), "plan_stop_usd": plan["stop_usd"], "ledger_total_before_usd": plan["ledger_total_before_usd"]}
    allb, alla = [], []
    for r in A.REGIMES:
        F = A.files(r)
        R0, R1 = A.results("clean", r), A.results("clean_rev1", r)
        if not R1:
            continue
        ids = sorted(R1)
        groups = {fid: o["group"] for o in plan["order"] if o["regime"] == r for fid in o["files"]}
        before, after, changed = [], [], []
        for fid in ids:
            m = F[fid]["meta"]
            b = A.score_file(F[fid], R0.get(fid), None)
            a = A.score_file(F[fid], R1.get(fid), None)
            for s in (b, a):
                s.update(level=m["level"], denied_event=m["denied_event"], open_fact=bool(m["open_facts"]), file=fid, group=groups.get(fid))
            before.append(b)
            after.append(a)
            if (b["total"], b["routed"]) != (a["total"], a["routed"]) or b["errors"] != a["errors"]:
                changed.append({"file": fid, "group": groups.get(fid), "denied_event": m["denied_event"], "level": m["level"],
                                "type": F[fid]["design"]["type"],
                                "before": {"routed": b["routed"], "errors": b["total"], "kinds": {SHORT[k]: v for k, v in b["errors"].items() if v}},
                                "after": {"routed": a["routed"], "errors": a["total"], "kinds": {SHORT[k]: v for k, v in a["errors"].items() if v},
                                          "detail": a["detail"]}})
        tab = {}
        for name, sel in [("all re-run", lambda s: True)] + [(f"level_{lv}", (lambda lv: lambda s: s["level"] == lv)(lv)) for lv in A.LEVELS] + \
                         [("denied_event", lambda s: s["denied_event"]), ("not denied", lambda s: not s["denied_event"])] + \
                         [(f"group {g}", (lambda g: lambda s: s["group"] == g)(g)) for g in ("P1", "P2", "P3", "P4", "P5")]:
            tb, ta = summarise([s for s in before if sel(s)]), summarise([s for s in after if sel(s)])
            if tb.get("files"):
                tab[name] = {"before": tb, "after": ta}
        rep["regimes"][r] = {"files_rerun": len(ids), "files_in_regime": len(F), "table": tab, "changed_files": changed,
                             "fact_admission_before": fact_admission(r, F, R0, "clean", ids),
                             "fact_admission_after": fact_admission(r, F, R1, "clean_rev1", ids)}
        allb += before
        alla += after
    rep["all_regimes"] = {"before": summarise(allb), "after": summarise(alla)}
    rep["notes_text"] = NOTES
    (HERE / "COMPARE_REV1.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (HERE / "COMPARE_REV1.md").write_text(markdown(rep), encoding="utf-8")
    print(json.dumps({r: x["table"].get("all re-run") for r, x in rep["regimes"].items()}, indent=1))
    print(json.dumps(rep["spend"], indent=1))


def markdown(rep):
    L = ["# Part C: the clean arm with the revised rule wording (Study 4, step 2d follow-up)", "",
         "**DEVELOPMENT material, post hoc, in-sample: the wording fixes were designed on these same files, so the change "
         "measures how well the fixes fit the files they were made from, not how they generalise. Not a result.** "
         "Cost-efficient model gpt-6-luna, one run per file (run index 0), product at the tested commit, caching transport "
         "and ledger under `lint/runs/` (arm label `LINT-clean_rev1-<regime>`). Before = the stored clean arm (rules in "
         "`rules/<regime>/rev0/`); after = `results_clean_rev1_<regime>_gpt-6-luna.json` (rules as revised). Both on the "
         "same files: those the re-run stored (selection and order fixed in `REV1_PLAN.json` before the first rev1 call). "
         "Scoring is `lint/analyse.py` part (d), unchanged.", ""]
    L += ["UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, "
          "MH = holds missed, E = errors per file; RF = routing failures, denied-event / other.", ""]
    head = ["Regime", "Split", "Files", "E before", "E after", "UR b/a", "MR b/a", "UH b/a", "MH b/a", "RF denied b/a", "RF other b/a", "No error b/a"]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r, x in rep["regimes"].items():
        for split, t in x["table"].items():
            b, a = t["before"], t["after"]
            L.append(f"| {r} | {split} | {b['files']} | {b['errors_per_file']} | {a['errors_per_file']} | "
                     + " | ".join(f"{b[k]} / {a[k]}" for k in KINDS)
                     + f" | {b['routing_failures_denied']} / {a['routing_failures_denied']} | {b['routing_failures_not_denied']} / {a['routing_failures_not_denied']}"
                     + f" | {b['files_without_error']} / {a['files_without_error']} |")
    b, a = rep["all_regimes"]["before"], rep["all_regimes"]["after"]
    L.append(f"| all | all re-run | {b['files']} | {b['errors_per_file']} | {a['errors_per_file']} | "
             + " | ".join(f"{b[k]} / {a[k]}" for k in KINDS)
             + f" | {b['routing_failures_denied']} / {a['routing_failures_denied']} | {b['routing_failures_not_denied']} / {a['routing_failures_not_denied']} | {b['files_without_error']} / {a['files_without_error']} |")
    L += ["", "## Files whose score or routing changed", ""]
    for r, x in rep["regimes"].items():
        for c in x["changed_files"]:
            L.append(f"- {r} {c['file']} ({c['group']}, {'denied' if c['denied_event'] else 'not denied'}, level {c['level']}, type {c['type']}): "
                     f"before routed {c['before']['routed']}, {c['before']['errors']} errors {c['before']['kinds']}; "
                     f"after routed {c['after']['routed']}, {c['after']['errors']} errors {c['after']['kinds']}"
                     + (": " + "; ".join(f"{d['document']} {d['error']}" for d in c["after"]["detail"]) if c["after"]["detail"] else "") + ".")
    L += ["", "## The changed facts: product state by designed state, on the re-run files", ""]
    for r, x in rep["regimes"].items():
        for k in x["fact_admission_before"]:
            L.append(f"- {r} {k}: before {x['fact_admission_before'][k]}; after {x['fact_admission_after'][k]}")
    sp = rep["spend"]
    L += ["", "## Spend (ledger rows of the rev1 arm labels)", "",
          f"USD {sp['total_usd']} in {sum(sp['paid_calls'].values())} paid calls: "
          + "; ".join(f"{k} USD {v} ({sp['paid_calls'][k]} calls)" for k, v in sp["by_arm_label"].items())
          + f". Ledger total before part C: USD {rep['ledger_total_before_usd']}; launch stop at USD {rep['plan_stop_usd']}.", ""]
    L += [rep.get("notes_text") or ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

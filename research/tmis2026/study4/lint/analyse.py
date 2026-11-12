"""Analysis of the planted-defect test (study4 step 2d). DEVELOPMENT, post hoc, not a result. No model calls.

    python3 -I -B study4/lint/analyse.py                 # writes REPORT.json and REPORT.md
    python3 -I -B study4/lint/analyse.py --review-material   # writes runs/review_material.json for part (c)

Reads only: DESIGN.json (sealed), the stored runs (runs/results_*.json, the run records under runs/records/, the reading
responses in runs/cache/), the ledgers under runs/, and per file dev/<regime>/final/<id>/design.json (recorded states,
type, level, flags) and reference.json (scoring of the clean arm only). The judgments of part (c) are read from
false_alarm_review.json (written by reading the files; see the report).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
RUNS = HERE / "runs"
CACHE = RUNS / "cache"
REGIMES = ["tenancy", "theft", "dismissal"]
ARMS = ["clean", "blunt", "subtle"]
MODEL = "gpt-6-luna"
LEVELS = [0, 10, 25, 50]
KINDS = ["unneeded_request", "missed_request", "unwarranted_hold", "missed_hold"]
KIND_LABEL = {"unneeded_request": "requests that should not be made", "missed_request": "requests missed",
              "unwarranted_hold": "holds where the file settles the fact", "missed_hold": "holds missed"}


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


DESIGN = jl(HERE / "DESIGN.json")


def files(regime):
    man = jl(S4 / "dev" / regime / "final" / "MANIFEST.json")
    out = {}
    for f in man["files"]:
        d = S4 / "dev" / regime / "final" / f["file_id"]
        out[f["file_id"]] = {"meta": f, "design": jl(d / "design.json"), "reference": jl(d / "reference.json")}
    return out


def workflows(regime, arm):
    # the clean arm read the rule sets kept in rules/<regime>/rev0/ (revision after first use, 2026-11-12)
    d = (S4 / "rules" / regime / "rev0" / "workflow" if arm == "clean" else S4 / "rules" / regime / "rev1" / "workflow" if arm == "clean_rev1"
         else S4 / "rules" / regime / "workflow" if arm == "clean_rev3" else HERE / "widened" / regime / arm)
    return {p.stem: jl(p) for p in sorted(d.glob("*.json"))}


def results(arm, regime, model=None):
    p = RUNS / f"results_{arm}_{regime}_{model or MODEL}.json"
    return jl(p) if p.exists() else None


def record(entry):
    if not entry or not entry.get("record"):
        return None
    p = HERE / entry["record"]
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def readings(entry, fact_ids):
    """[(keys, {fact: (verdict, quote)})] for the reading calls of a run, from the cached responses (as
    analysis/lint_followup.py): a conditions answer covering most of the workflow's facts starts a reading; a short one
    right after it is its requote retry and replaces those answers."""
    out, seen = [], set()
    for k in (entry or {}).get("keys") or []:
        if k in seen:
            continue
        seen.add(k)
        p = CACHE / f"{k}.json"
        if not p.exists():
            continue
        try:
            content = json.loads(json.loads(json.loads(p.read_text())["body"])["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001  (tool-call turns carry no JSON content)
            continue
        rows = content.get("conditions") if isinstance(content, dict) else None
        if not rows or not all(r.get("id") in fact_ids for r in rows):
            continue
        ans = {}
        for r in rows:
            ans.setdefault(r["id"], (r.get("verdict"), r.get("quote") or ""))
        if len(ans) >= 0.8 * len(fact_ids) or not out:
            out.append([k, ans])
        else:
            out[-1][0] += "+" + k
            out[-1][1].update(ans)
    return [(k, a) for k, a in out]


def run_view(entry, wf):
    """What one run says about each fact of workflow wf: admitted (product), readings' verdicts, located quotes."""
    rec = record(entry)
    if rec is None:
        return None
    run = rec["case"]["run"]
    res = run.get("result") or {}
    routed = (run.get("workflow_id") or (res.get("workflow") or {}).get("id"))
    if routed != wf["id"]:
        return {"routed": routed, "facts": None}
    ids = {f["id"] for f in wf["facts"]}
    rows = {f["fact"]: f for f in res.get("facts", [])}
    rds = readings(entry, ids)
    out = {}
    for f in wf["facts"]:
        r = rows.get(f["id"]) or {}
        verdicts = [a.get(f["id"], (None, ""))[0] for _, a in rds]
        out[f["id"]] = {"admitted_true": r.get("status") == "established" and r.get("value") is True and r.get("verdict") != "rejected",
                        "status": r.get("status"), "value": r.get("value"),
                        "some_reading_true": any(v == "true" for v in verdicts), "verdicts": verdicts,
                        "quotes": [c.get("quote") for c in (r.get("citations") or []) if c.get("quote")],
                        "reading_true_quotes": [a[f["id"]][1] for _, a in rds if a.get(f["id"], (None,))[0] == "true" and a[f["id"]][1]]}
    return {"routed": routed, "facts": out, "n_readings": len(rds)}


# --------------------------------------------------------------------------------------------------- the lint
def planted_in(regime, arm):
    dr = DESIGN["regimes"][regime]["draw"]
    if arm == "blunt":
        return {(t, f): "blunt" for t, fs in dr["drawn"].items() for f in fs}
    if arm == "subtle":
        return {(t, f): "subtle" for t, f in dr["subtle"]}
    return {}


def lint(regime, arm, F):
    R = results(arm, regime)
    if R is None:
        return None
    wfs = workflows(regime, arm)
    dr = DESIGN["regimes"][regime]["draw"]
    planted = planted_in(regime, arm)
    conds, excluded = {}, []
    views = {}
    for fid, x in F.items():
        t = x["design"]["type"]
        e = R.get(fid)
        if e is None:
            excluded.append({"file": fid, "why": "not run"})
            continue
        v = run_view(e, wfs[t])
        if v is None or v.get("facts") is None:
            excluded.append({"file": fid, "why": "failed run" if v is None or (e.get("plan") is None) else f"routed to {v and v.get('routed')}"})
            continue
        views[fid] = v
    for t, wf in wfs.items():
        tfiles = [fid for fid, x in F.items() if x["design"]["type"] == t]
        for f in wf["facts"]:
            fid_ = f["id"]
            if f.get("type") != "boolean":
                continue
            st = {"type": t, "fact": fid_, "question": f["question"], "defining_event": fid_ == dr["defining"][t],
                  "planted": planted.get((t, fid_)), "files_of_type": len(tfiles)}
            by_state = defaultdict(lambda: {"n": 0, "admitted_true": 0, "some_reading_true": 0, "files_admitted": [], "files": []})
            unread = 0
            for fid in tfiles:
                v = views.get(fid)
                state = F[fid]["design"]["facts"].get(fid_)
                if v is None:
                    unread += 1
                    continue
                g = "false_or_not_mentioned" if state in ("stated_false", "not_mentioned") else state
                b = by_state[g]
                b["n"] += 1
                b["files"].append(fid)
                fv = v["facts"][fid_]
                if fv["admitted_true"]:
                    b["admitted_true"] += 1
                    b["files_admitted"].append(fid)
                b["some_reading_true"] += fv["some_reading_true"]
            fnm = by_state["false_or_not_mentioned"]
            n = fnm["n"]
            st.update(files_assessed=n, files_not_read=unread,
                      admitted_true_share=round(fnm["admitted_true"] / n, 3) if n else None,
                      some_reading_true_share=round(fnm["some_reading_true"] / n, 3) if n else None,
                      admitted_true=fnm["admitted_true"], some_reading_true=fnm["some_reading_true"],
                      assessable=n >= 5, flagged=(n >= 5 and fnm["admitted_true"] >= n / 2),
                      files_admitted_true=fnm["files_admitted"],
                      calibration={g: {"n": by_state[g]["n"], "admitted_true": by_state[g]["admitted_true"],
                                       "share": round(by_state[g]["admitted_true"] / by_state[g]["n"], 3) if by_state[g]["n"] else None}
                                   for g in ("stated_true", "open")})
            st["state_split"] = {g: by_state[g]["n"] for g in by_state}
            n_all = sum(b["n"] for b in by_state.values())
            st["admitted_true_all_files"] = {"n": n_all, "admitted_true": sum(b["admitted_true"] for b in by_state.values()),
                                             "share": round(sum(b["admitted_true"] for b in by_state.values()) / n_all, 3) if n_all else None}
            q = []
            for fid in fnm["files_admitted"]:
                qs = views[fid]["facts"][fid_]["quotes"]
                if qs and len(q) < 2:
                    q.append({"file": fid, "recorded_state": F[fid]["design"]["facts"].get(fid_), "quote": qs[0]})
            st["quotations"] = q
            conds[f"{t}.{fid_}"] = st
    return {"conditions": conds, "excluded": excluded, "files_run": len(R)}


def detection(L):
    out = {}
    for regime, arms in L.items():
        clean = (arms.get("clean") or {}).get("conditions") or {}
        for arm in ("blunt", "subtle"):
            A = arms.get(arm)
            if not A:
                continue
            c = A["conditions"]
            planted = [k for k, v in c.items() if v["planted"]]
            untouched = [k for k, v in c.items() if not v["planted"] and not v["defining_event"]]
            out.setdefault(arm, {})[regime] = {
                "planted": len(planted),
                "planted_detected": sorted(k for k in planted if c[k]["flagged"] and not clean.get(k, {}).get("flagged")),
                "planted_flagged_but_also_in_clean": sorted(k for k in planted if c[k]["flagged"] and clean.get(k, {}).get("flagged")),
                "planted_not_flagged": sorted(k for k in planted if not c[k]["flagged"]),
                "planted_not_assessable": sorted(k for k in planted if not c[k]["assessable"]),
                "untouched": len(untouched),
                "untouched_flagged": sorted(k for k in untouched if c[k]["flagged"]),
                "untouched_not_assessable": sorted(k for k in untouched if not c[k]["assessable"]),
                "defining_events_flagged": sorted(k for k, v in c.items() if v["defining_event"] and v["flagged"]),
            }
        if clean:
            br = [k for k, v in clean.items() if not v["defining_event"]]
            out.setdefault("clean", {})[regime] = {
                "branch": len(br), "flagged": sorted(k for k in br if clean[k]["flagged"]),
                "not_assessable": sorted(k for k in br if not clean[k]["assessable"]),
                "defining_events_flagged": sorted(k for k, v in clean.items() if v["defining_event"] and v["flagged"])}
    return out


# --------------------------------------------------------------------------------------------------- scoring (clean arm)
def score_file(x, entry, catalogue_types):
    ref = x["reference"]["documents"]
    t = x["design"]["type"]
    plan = (entry or {}).get("plan") or {}
    failed = entry is None or entry.get("plan") is None or entry.get("status") in {"failed", "adapter_error"}
    req, hold = set(plan.get("requests") or []), set(plan.get("holds") or [])
    errs = Counter()
    detail = []
    for d, r in ref.items():
        st = r["state"]
        if st == "hold":
            k = None if d in hold else "missed_hold"
        elif r.get("request"):
            k = None if d in req else ("unwarranted_hold" if d in hold else "missed_request")
        else:
            k = "unneeded_request" if d in req else ("unwarranted_hold" if d in hold else None)
        if k:
            errs[k] += 1
            detail.append({"document": d, "reference": st, "error": k})
    for d in sorted((req | hold) - set(ref)):
        k = "unneeded_request" if d in req else "unwarranted_hold"
        errs[k] += 1
        detail.append({"document": d, "reference": "not in the type's catalogue (other type or process-builder addition)", "error": k})
    routed = plan.get("family")
    routing_failure = (not failed) and (plan.get("deferred") or routed != t)
    return {"errors": {k: errs[k] for k in KINDS}, "total": sum(errs.values()), "detail": detail, "failed": failed,
            "routing_failure": bool(routing_failure), "routed": routed, "type": t}


def scoring(regime, F):
    R = results("clean", regime)
    if R is None:
        return None
    per = {}
    for fid, x in F.items():
        s = score_file(x, R.get(fid), None)
        m = x["meta"]
        s.update(level=m["level"], denied_event=m["denied_event"], open_fact=bool(m["open_facts"]), scan_noise=m["scan_noise"],
                 kept=m["kept"])
        per[fid] = s
    return per


def summarise(rows):
    n = len(rows)
    if not n:
        return {"files": 0}
    out = {"files": n}
    for k in KINDS:
        out[k] = round(sum(r["errors"][k] for r in rows) / n, 3)
    out["errors_per_file"] = round(sum(r["total"] for r in rows) / n, 3)
    out["files_without_error"] = sum(r["total"] == 0 for r in rows)
    return out


def score_tables(S):
    out = {}
    allrows = []
    for regime, per in S.items():
        rows = list(per.values())
        allrows += rows
        tab = {"overall": summarise(rows)}
        for lv in LEVELS:
            tab[f"level_{lv}"] = summarise([r for r in rows if r["level"] == lv])
        tab["denied_event"] = summarise([r for r in rows if r["denied_event"]])
        tab["open_fact"] = summarise([r for r in rows if r["open_fact"]])
        tab["others"] = summarise([r for r in rows if not r["denied_event"] and not r["open_fact"]])
        tab["routed_correctly_only"] = summarise([r for r in rows if not r["routing_failure"] and not r["failed"]])
        out[regime] = tab
    tab = {"overall": summarise(allrows)}
    for lv in LEVELS:
        tab[f"level_{lv}"] = summarise([r for r in allrows if r["level"] == lv])
    tab["denied_event"] = summarise([r for r in allrows if r["denied_event"]])
    tab["open_fact"] = summarise([r for r in allrows if r["open_fact"]])
    tab["others"] = summarise([r for r in allrows if not r["denied_event"] and not r["open_fact"]])
    tab["routed_correctly_only"] = summarise([r for r in allrows if not r["routing_failure"] and not r["failed"]])
    out["all_regimes"] = tab
    return out


# --------------------------------------------------------------------------------------------------- spend
def spend():
    rows = []
    for p in sorted(RUNS.glob("ledger_dev_*.jsonl")):
        rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    by = defaultdict(float)
    calls = Counter()
    for r in rows:
        by[r.get("arm") or "?"] += float(r.get("usd") or 0)
        calls[r.get("arm") or "?"] += 1
    est = jl(RUNS / "ESTIMATE.json") if (RUNS / "ESTIMATE.json").exists() else None
    files_paid = defaultdict(set)
    for r in rows:
        files_paid[r.get("arm")].add(r["case"])
    return {"total_usd": round(sum(by.values()), 4), "by_arm_label": {k: round(v, 4) for k, v in sorted(by.items())},
            "paid_calls_by_arm_label": dict(calls), "files_with_paid_calls_by_arm_label": {k: len(v) for k, v in files_paid.items()},
            "estimate": est}


def failed_outputs():
    out = []
    for p in sorted(RUNS.glob("results_*.json")):
        for fid, e in jl(p).items():
            if e.get("plan") is None or e.get("status") in {"failed", "adapter_error"}:
                out.append({"store": p.name, "file": fid, "status": e.get("status"), "error": str(e.get("error"))[:300]})
    return out


# --------------------------------------------------------------------------------------------------- part (c) material
def review_material(L, FF):
    """For each untouched condition flagged in the clean arm: five files (admitted true where the recorded state is false
    or not mentioned), with the product's located quotations and the recorded state."""
    out = {}
    for regime, arms in L.items():
        c = (arms.get("clean") or {}).get("conditions") or {}
        R = results("clean", regime)
        wfs = workflows(regime, "clean")
        for k, v in c.items():
            if not v["flagged"] or v["defining_event"]:
                continue
            rows = []
            for fid in v["files_admitted_true"][:5]:
                vw = run_view(R[fid], wfs[v["type"]])["facts"][v["fact"]]
                d = FF[regime][fid]["design"]
                rows.append({"file": fid, "recorded_state": d["facts"].get(v["fact"]),
                             "designed_state": (d.get("facts_designed") or {}).get(v["fact"]), "kept": FF[regime][fid]["meta"]["kept"],
                             "quotes": vw["quotes"], "verdicts": vw["verdicts"]})
            out[f"{regime}/{k}"] = {"question": v["question"], "files": rows}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--review-material", action="store_true")
    a = ap.parse_args()
    FF = {r: files(r) for r in REGIMES}
    L = {r: {arm: lint(r, arm, FF[r]) for arm in ARMS} for r in REGIMES}
    L = {r: {arm: v for arm, v in arms.items() if v is not None} for r, arms in L.items()}
    if a.review_material:
        (RUNS / "review_material.json").write_text(json.dumps(review_material(L, FF), indent=1, ensure_ascii=False) + "\n")
        print("written runs/review_material.json")
        return
    S = {r: scoring(r, FF[r]) for r in REGIMES}
    S = {r: v for r, v in S.items() if v is not None}
    review = jl(HERE / "false_alarm_review.json") if (HERE / "false_alarm_review.json").exists() else None
    frontier = {}
    for r in REGIMES:
        R = results("clean", r, "gpt-6.1-terra")
        if R is not None:
            frontier[r] = {"files": len(R), "lint": lint_frontier(r, FF[r])}
    rep = {"label": "DEVELOPMENT, post hoc, not a result", "design_sha256": (HERE / "DESIGN.sha256").read_text().split()[0],
           "design_written_utc": DESIGN["written_utc"], "lint_rule": DESIGN["lint_rule"], "detection_rule": DESIGN["detection"],
           "scoring_rule": DESIGN["scoring_clean_arm"],
           "arms_run": {r: sorted(L[r]) for r in REGIMES},
           "planted": {r: DESIGN["regimes"][r]["planted"] for r in REGIMES},
           "lint": L, "detection": detection(L), "false_alarm_review": review,
           "clean_arm_scoring": {"tables": score_tables(S), "per_file": S,
                                 "routing_failures": sorted(f"{r}/{fid}" for r, per in S.items() for fid, s in per.items() if s["routing_failure"]),
                                 "failed_runs": sorted(f"{r}/{fid}" for r, per in S.items() for fid, s in per.items() if s["failed"])},
           "spend": spend(), "failed_outputs": failed_outputs(), "frontier": frontier or None}
    notes = HERE / "notes.json"
    rep["notes"] = jl(notes) if notes.exists() else []
    (HERE / "REPORT.md").write_text(markdown(rep), encoding="utf-8")
    (HERE / "REPORT.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({"detection": rep["detection"], "spend": rep["spend"]["total_usd"]}, indent=1))


def pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def markdown(rep):
    L = ["# Planted-defect test of the rule lint (Study 4, step 2d)", "",
         "**DEVELOPMENT material, post hoc, not a result.** Product at the tested commit 6a72159c (worktree read-only), "
         "checklist-only run scope, reasoning on, gpt-6-luna, one run per file (run index 0), through the caching transport "
         "with the ledger under `study4/lint/runs/`. Design sealed before any call on the development files: "
         f"`DESIGN.json` SHA-256 `{rep['design_sha256']}`, written {rep['design_written_utc']}. "
         "The widened wordings were written by the same session that knows the lint and wrote this analysis.", "",
         "## Rules", "", "**Lint.** " + rep["lint_rule"], "", "**Detection and false alarms.** " + rep["detection_rule"], "",
         "**Arms run.** " + "; ".join(f"{r}: {', '.join(a)}" for r, a in rep["arms_run"].items()) + ". "
         "The estimate exceeded the stop line, so the sealed fallback applied: clean and blunt everywhere, subtle on tenancy only.", ""]
    L += ["## Planted defects", "", "| Regime | Condition | Original | Blunt | Subtle (dropped qualifier) |", "|---|---|---|---|---|"]
    for r, pl in rep["planted"].items():
        for k, v in pl.items():
            sub = f"{v['subtle']} ({v['subtle_dropped_qualifier']})" if v.get("subtle") else "-"
            L.append(f"| {r} | {k} | {v['original']} | {v['blunt']} | {sub} |")
    L += ["", "## (b) Detection and false alarms", ""]
    det = rep["detection"]
    for arm in ("blunt", "subtle"):
        for r, d in (det.get(arm) or {}).items():
            L.append(f"- **{arm}, {r}:** planted {d['planted']}; detected (flagged here, not in clean) {len(d['planted_detected'])} "
                     f"{d['planted_detected']}; flagged but also flagged in clean {d['planted_flagged_but_also_in_clean']}; not flagged "
                     f"{d['planted_not_flagged']}; not assessable {d['planted_not_assessable']}. Untouched branch conditions {d['untouched']}: "
                     f"flagged {len(d['untouched_flagged'])} {d['untouched_flagged']}; not assessable {d['untouched_not_assessable']}. "
                     f"Defining events flagged: {d['defining_events_flagged'] or 'none'}.")
    for r, d in (det.get("clean") or {}).items():
        L.append(f"- **clean, {r}:** branch conditions {d['branch']}; flagged {len(d['flagged'])} {d['flagged']}; not assessable "
                 f"{d['not_assessable']}; defining events flagged: {d['defining_events_flagged'] or 'none'}.")
    L += ["", "## (a) Per condition", "",
          "Assessed = files of the type whose recorded state is stated false or not mentioned and whose run read the type's facts. "
          "Admitted = product established true. Calibration: admitted-true share where the recorded state is stated true (T) and open (O).", ""]
    for r, arms in rep["lint"].items():
        for arm, A in arms.items():
            L += [f"### {r}, {arm} arm", "", "| Condition | Planted | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) | All files of type (n) |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for k, c in A["conditions"].items():
                fl = "yes" if c["flagged"] else ("not assessable" if not c["assessable"] else "no")
                cal = c["calibration"]
                L.append(f"| {k}{' (defining event)' if c['defining_event'] else ''} | {c['planted'] or '-'} | {c['files_assessed']} | "
                         f"{c['admitted_true']} ({pct(c['admitted_true_share'])}) | {c['some_reading_true']} ({pct(c['some_reading_true_share'])}) | {fl} | "
                         f"{pct(cal['stated_true']['share'])} ({cal['stated_true']['n']}) | {pct(cal['open']['share'])} ({cal['open']['n']}) | "
                         f"{pct(c['admitted_true_all_files']['share'])} ({c['admitted_true_all_files']['n']}) |")
            fl = [(k, c) for k, c in A["conditions"].items() if c["flagged"]]
            if fl:
                L += ["", "Quotations the readings relied on, flagged conditions:", ""]
                for k, c in fl:
                    for q in c["quotations"]:
                        L.append(f"- {k} ({q['file']}, recorded {q['recorded_state']}): \"{q['quote']}\"")
            if A["excluded"]:
                L += ["", "Files not counted: " + "; ".join(f"{e['file']} ({e['why']})" for e in A["excluded"])]
            L.append("")
    L += ["## (c) What the clean-arm false alarms are", ""]
    rv = rep.get("false_alarm_review") or {}
    if rv.get("statement"):
        L += [rv["statement"], ""]
    for k, v in (rv.get("conditions") or {}).items():
        L += [f"### {k}", "", f"**Verdict:** {v['verdict']}", "", v["summary"], ""]
        for f in v["files"]:
            L.append(f"- {f['file']} (recorded {f['recorded_state']}): {f['judgment']} Quote: \"{f['quote']}\"")
        L.append("")
    sc = rep["clean_arm_scoring"]
    L += ["## (d) The clean arm scored (a first look at the tested core; no baseline, no comparison)", "", rep["scoring_rule"], "",
          "Means per file. UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, "
          "MH = holds missed, E = errors per file (sum).", "",
          "| Regime | Split | Files | UR | MR | UH | MH | E | Files without error |", "|---|---|---|---|---|---|---|---|---|"]
    for r, tab in sc["tables"].items():
        for split, t in tab.items():
            if not t.get("files"):
                L.append(f"| {r} | {split} | 0 | | | | | | |")
                continue
            L.append(f"| {r} | {split} | {t['files']} | {t['unneeded_request']} | {t['missed_request']} | {t['unwarranted_hold']} | "
                     f"{t['missed_hold']} | {t['errors_per_file']} | {t['files_without_error']} |")
    L += ["", f"Routing failures: {sc['routing_failures'] or 'none'}. Failed runs: {sc['failed_runs'] or 'none'}.", ""]
    sp = rep["spend"]
    L += ["## (e) Spend (from the ledgers under study4/lint/runs/)", "", f"Total USD {sp['total_usd']}.", "",
          "| Ledger arm label | USD | Paid calls | Files with paid calls |", "|---|---|---|---|"]
    for k, v in sp["by_arm_label"].items():
        L.append(f"| {k} | {v} | {sp['paid_calls_by_arm_label'].get(k)} | {sp['files_with_paid_calls_by_arm_label'].get(k)} |")
    est = sp.get("estimate") or {}
    if est:
        L += ["", f"Estimate (first five files): USD {est['usd_per_file_first_five']} per file; clean+blunt on all regimes "
                  f"USD {est['estimate_usd']['clean_all'] + est['estimate_usd']['blunt_all']:.2f}, three arms USD {est['estimate_usd']['three_arms_total']}. "
                  + est["decision"]]
    L += ["", f"Failed outputs: {rep['failed_outputs'] or 'none'}.", ""]
    fr = rep.get("frontier") or {}
    for r, v in fr.items():
        A = v["lint"]
        L += [f"## Frontier arm (gpt-6.1-terra, clean, {r}): partial", "",
              f"{v['files']} of the regime's files were run (manifest order, stopped at the launch threshold); files not counted: "
              + ("; ".join(f"{e['file']} ({e['why']})" for e in A["excluded"]) or "none") + ".", "",
              "| Condition | Assessed | Admitted true | Some reading true | Flagged | T (n) | O (n) |", "|---|---|---|---|---|---|---|"]
        for k, c in A["conditions"].items():
            fl = "yes" if c["flagged"] else ("not assessable" if not c["assessable"] else "no")
            cal = c["calibration"]
            L.append(f"| {k} | {c['files_assessed']} | {c['admitted_true']} | {c['some_reading_true']} | {fl} | "
                     f"{pct(cal['stated_true']['share'])} ({cal['stated_true']['n']}) | {pct(cal['open']['share'])} ({cal['open']['n']}) |")
        L.append("")
    if rep.get("notes"):
        L += ["## Notes and limits", ""] + [f"- {n}" for n in rep["notes"]] + [""]
    return "\n".join(L) + "\n"


def lint_frontier(regime, F):
    """The lint on the frontier model's clean-arm run, if one was made (same rule)."""
    global MODEL
    old = MODEL
    MODEL = "gpt-6.1-terra"
    try:
        return lint(regime, "clean", F)
    finally:
        MODEL = old


if __name__ == "__main__":
    main()

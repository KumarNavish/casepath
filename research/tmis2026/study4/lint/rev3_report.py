"""Score and attribute the clean arm on revision 3 (study4 step 2, last paid run). DEVELOPMENT, post hoc, in-sample, not
a result: wording and files were repaired on these same files; no baseline, no comparison between designs.

    python3 -I -B study4/lint/rev3_report.py      # writes lint/REV3.json and lint/REV3.md

Scoring: lint/analyse.py part (d), unchanged. Attribution: lint/diagnose.py's rule (replays through the product's
evaluator with the current rule sets). Cause 6 (text against recorded state) uses diagnose.py's rule (a) and the fact
judgments of diagnosis_review.json where the file's text is unchanged; the document judgments of that review are not
carried over, because revision 2 rewrote the must_show items they rest on. rev0 figures: the stored clean arm
(runs/results_clean_<regime>_gpt-6-luna.json, rules rev0) on the same files, with DIAGNOSIS.json's attribution.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
sys.path.insert(0, str(HERE))
import analyse as A  # noqa: E402
import diagnose as DG  # noqa: E402

KINDS = A.KINDS
SH = {"unneeded_request": "UR", "missed_request": "MR", "unwarranted_hold": "UH", "missed_hold": "MH"}
CAUSE = {"routing_denied": "routing, denied-event file", "routing_not_denied": "routing, other file", "fact_reading": "fact reading",
         "document_judgment": "document judgment", "text_state_disagree": "text against recorded state",
         "workflow_vs_reference": "workflow differs from reference", "scoring_convention": "scoring convention", "failed_run": "failed run"}
SPLITS = ["overall", "level_0", "level_10", "level_25", "level_50", "denied_event", "open_fact", "other"]


def rewritten_ids():
    out = set()
    for name in ("REPAIR_R3_LIST.json", "REPAIR_R4_LIST.json"):
        p = S4 / "dev" / name
        if p.exists():
            txt = p.read_text()
            for reg in A.REGIMES:
                for fid in A.files(reg):
                    if fid in txt:
                        out.add((reg, fid))
    return out


def summarise(rows):
    n = len(rows)
    if not n:
        return None
    out = {"files": n, **{SH[k]: round(sum(r["errors"][k] for r in rows) / n, 3) for k in KINDS}}
    out["E"] = round(sum(r["total"] for r in rows) / n, 3)
    out["errors"] = sum(r["total"] for r in rows)
    out["RF_denied"] = sum(r["routing_failure"] and r["denied_event"] for r in rows)
    out["RF_other"] = sum(r["routing_failure"] and not r["denied_event"] for r in rows)
    out["failed_runs"] = sum(r["failed"] for r in rows)
    return out


def split_rows(rows, s):
    if s == "overall":
        return rows
    if s.startswith("level_"):
        return [r for r in rows if r["level"] == int(s[6:])]
    if s == "denied_event":
        return [r for r in rows if r["denied_event"]]
    if s == "open_fact":
        return [r for r in rows if r["open_fact"]]
    return [r for r in rows if not r["denied_event"] and not r["open_fact"]]


def label(r):
    c = CAUSE.get(r["cause"], r["cause"])
    if r["cause"] in ("fact_reading", "text_state_disagree") and (r.get("fact") or r.get("sub") == "several_facts"):
        return c + ": " + DG.SUB_LABEL.get(r.get("sub"), r.get("sub") or "")
    if r["cause"] == "document_judgment":
        return c + ": " + (r.get("sub") or "")
    return c


CLOSING = ("Product behaviour that remains, by size, in errors per file over the two complete regimes (theft and dismissal, "
           "114 files; tenancy ran 28 of 59 files and is not a regime figure): (1) supplied-document judgments, 24 errors, "
           "0.21 per file: sufficient documents judged insufficient (9), findings the second judgment or the source checker "
           "did not confirm (8), present documents judged missing (4), and three the other way; not re-reviewed against the "
           "rewritten must_show items, so some may be text against recorded state; (2) stated facts held because one "
           "reading's quotation was not found word for word (a capital letter, scan noise corrected), 14 errors, 0.12 per "
           "file, most of them on defining events that hold a whole type; (3) stated facts held because one reading of three "
           "answered otherwise (household member, vouchers, incapacity, probation, order of notice and protected period), "
           "about 12 errors, 0.11 per file, of which the_248aa95805a8's household reading (4) is the open reading also seen "
           "in rev0 and 5 more are carried over as text against recorded state; (4) routing, 12 errors, 0.11 per file: 5 in "
           "two theft files whose defining event is designed open (benchmark design) and 7 in three dismissal "
           "wrongful_termination files routed to protected_period_notice or left unrouted under the revised routing "
           "question, which the next design cycle should read before any further wording change. No run failed.")


def main():
    review = A.jl(HERE / "diagnosis_review.json")
    changed_text = rewritten_ids()
    facts_review = {k: v for k, v in (review.get("facts") or {}).items() if tuple(k.split("/")[:2]) not in changed_text}
    rev0diag = A.jl(HERE / "DIAGNOSIS.json")
    rev0_err = defaultdict(list)
    for e in rev0diag["errors"]:
        rev0_err[(e["regime"], e["file"])].append(e)
    plan = A.jl(HERE / "REV3_PLAN.json")
    rep = {"label": "DEVELOPMENT, post hoc, in-sample: rule wording and files were repaired on these same files. No baseline, "
                    "no comparison between designs. Not a result.", "regimes": {}, "plan": plan}
    all3, all0, allerr3 = [], [], []
    for reg in A.REGIMES:
        F = A.files(reg)
        R3 = A.results("clean_rev3", reg) or {}
        R0 = A.results("clean", reg) or {}
        ids = [f for f in F if f in R3]
        if not ids:
            continue
        complete = len(ids) == len(F)
        rows3, errs3, fo, checks = [], [], {}, {}
        # attribution with diagnose.py's rule, on the files run
        all_rows, files_out, checks = DG.diagnose_regime(reg, "clean_rev3", ".", review=facts_review, review_docs={})
        errs3 = [r for r in all_rows if r["file"] in R3]
        for fid in ids:
            x, m = F[fid], F[fid]["meta"]
            s = A.score_file(x, R3[fid], None)
            s.update(file=fid, level=m["level"], denied_event=m["denied_event"], open_fact=bool(m["open_facts"]))
            rows3.append(s)
        ids0 = [f for f in ids if f in R0]
        rows0 = []
        for fid in ids0:
            x, m = F[fid], F[fid]["meta"]
            s = A.score_file(x, R0[fid], None)
            s.update(file=fid, level=m["level"], denied_event=m["denied_event"], open_fact=bool(m["open_facts"]))
            rows0.append(s)
        tab = {}
        for sp in SPLITS:
            a, b = summarise(split_rows(rows3, sp)), summarise(split_rows([r for r in rows3 if r["file"] in R0], sp))
            z = summarise(split_rows(rows0, sp))
            if a:
                tab[sp] = {"rev3": a, "rev3_on_files_with_rev0": b, "rev0_same_files": z}
        c3 = Counter(label(r) for r in errs3)
        c0 = Counter(label(r) for r in sum((rev0_err[(reg, f)] for f in ids0), []))
        routing = [{k: x.get(k) for k in ("file", "type", "denied_event", "routing_status", "routed_to", "routing_answer", "errors")}
                   for x in DG.routing_detail(reg, "clean_rev3") if x.get("file") in R3]
        rep["regimes"][reg] = {"files_in_final": len(F), "files_run": len(ids), "complete": complete,
                               "files_with_rev0_run": len(ids0), "rewritten_texts_in_set": sorted(f for r_, f in changed_text if r_ == reg and f in R3),
                               "table": tab, "causes_rev3": dict(c3.most_common()), "causes_rev0_same_files": dict(c0.most_common()),
                               "replay_checks": checks, "routing_failures": routing, "errors": errs3}
        if complete:
            all3 += rows3
            all0 += rows0
            allerr3 += errs3
    rep["overall_complete_regimes"] = {"regimes": [r for r, x in rep["regimes"].items() if x["complete"]],
                                       "rev3": summarise(all3), "rev0_same_files": summarise(all0),
                                       "causes_rev3": dict(Counter(label(r) for r in allerr3).most_common())}
    rep["quotations"] = quotations(allerr3 or sum((x["errors"] for x in rep["regimes"].values()), []))
    rep["spend"] = spend(plan)
    rep["closing"] = CLOSING
    (HERE / "REV3.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    (HERE / "REV3.md").write_text(markdown(rep), encoding="utf-8")
    print(json.dumps({r: {"complete": x["complete"], "files": x["files_run"], "overall": x["table"]["overall"], "causes": x["causes_rev3"]}
                      for r, x in rep["regimes"].items()}, indent=1))
    print(json.dumps(rep["overall_complete_regimes"], indent=1), json.dumps(rep["spend"], indent=1))


def quotations(errs):
    """The two largest causes (by errors), each with two quotations from the stored material."""
    c = Counter(label(r) for r in errs)
    out = []
    for lab, n in c.most_common(2):
        rs = [r for r in errs if label(r) == lab]
        qs, seen = [], set()
        for r in rs:
            if r["file"] in seen:
                continue
            q = None
            if r.get("reading_quotes"):
                want = {"stated_true": "true", "stated_false": "false", "open": "open"}.get(r.get("designed_state"))
                q = next((f"{x['verdict']}: \"{x['quote']}\"" for x in r["reading_quotes"] if x["quote"] and x["verdict"] != want), None) \
                    or next((f"{x['verdict']}: \"{x['quote']}\"" for x in r["reading_quotes"] if x["quote"]), None)
                q = q and (q + (f" [{r['pattern']}]" if r.get("pattern") else ""))
                q = q and f"{r['fact']} (designed {r.get('designed_state')}), a reading answered {q}"
            elif r.get("product_document"):
                rec = A.record(A.results("clean_rev3", r["regime"])[r["file"]])
                row = next((d for d in rec["case"]["run"]["result"]["documents"] if d["document"] == r["document"]), {})
                q = f"{r['document']} (supplied {r.get('supplied')}), product note: \"{DG.short(row.get('note'), 240)}\""
            elif r["cause"].startswith("routing"):
                rt = next((x for x in DG.routing_detail(r["regime"], "clean_rev3") if x["file"] == r["file"]), {})
                ans = (rt.get("routing_answer") or [{}])[0]
                q = f"routing answer {ans.get('value')}: \"{(ans.get('quotes') or ['(no quotation)'])[0]}\""
            if q:
                qs.append({"regime": r["regime"], "file": r["file"], "quote": q})
                seen.add(r["file"])
            if len(qs) == 2:
                break
        out.append({"cause": lab, "errors": n, "quotations": qs})
    return out


def spend(plan):
    usd, n = defaultdict(float), Counter()
    tot = 0.0
    for p in (HERE / "runs").glob("ledger_dev_*.jsonl"):
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                tot += float(r.get("usd") or 0)
                if "rev3" in (r.get("arm") or ""):
                    usd[r["arm"]] += float(r["usd"])
                    n[r["arm"]] += 1
    return {"rev3_usd": round(sum(usd.values()), 6), "by_arm_label": {k: round(v, 6) for k, v in sorted(usd.items())},
            "paid_calls": dict(n), "ledger_total_usd": round(tot, 6), "ledger_total_before_usd": plan["ledger_total_before_usd"]}


def fmt(t, k):
    return "-" if not t else t[k]


def markdown(rep):
    L = ["# Clean arm on revision 3 (Study 4, step 2: last paid run)", "",
         "**DEVELOPMENT material, post hoc, in-sample: the rule wording and the files were repaired on these same files. "
         "No baseline is run and no comparison between designs is made. Not a result.** Product at the tested commit "
         "(worktree read-only), gpt-6-luna, readings 3, open rule any, checklist scope, reasoning on, one run per file, "
         "current rule sets (revision 3), caching transport and ledger under `lint/runs/` (arm label "
         "`LINT-clean_rev3-<regime>`, stores `results_clean_rev3_<regime>_gpt-6-luna.json`). Plan, estimate and stop line "
         "written before the first call: `REV3_PLAN.json`. Scoring: `analyse.py` part (d), unchanged; attribution: "
         "`diagnose.py`'s rule.", "",
         "rev0 = the stored first clean arm (rules `rev0/`) on the same files. The eight denied-event texts rewritten in "
         "repair round 3 were read in their old form by rev0 (listed per regime); references are unchanged for every kept "
         "file. UR = requests that should not be made, MR = requests missed, UH = holds where the file settles the fact, "
         "MH = holds missed, E = errors per file; RF = routing failures (denied-event / other).", ""]
    for reg, x in rep["regimes"].items():
        L += [f"## {reg}: {x['files_run']} of {x['files_in_final']} files run ({'complete' if x['complete'] else 'INCOMPLETE: stopped at the budget line; not a regime figure'}); "
              f"stored rev0 run for {x['files_with_rev0_run']} of them", ""]
        if x["rewritten_texts_in_set"]:
            L += [f"Files named in the repair lists since rev0 (rewritten or re-checked in repair rounds 3 and 4; where a text was rewritten, rev0 read the old text): {', '.join(x['rewritten_texts_in_set'])}.", ""]
        L += ["| Split | Files | E rev3 (rev0) | UR | MR | UH | MH | RF denied | RF other |", "|---|---|---|---|---|---|---|---|---|"]
        for sp, t in x["table"].items():
            a, z = t["rev3"], t["rev0_same_files"]
            L.append(f"| {sp} | {a['files']} | {a['E']} ({fmt(z, 'E')}) | " + " | ".join(f"{a[k]} ({fmt(z, k)})" for k in ("UR", "MR", "UH", "MH"))
                     + f" | {a['RF_denied']} ({fmt(z, 'RF_denied')}) | {a['RF_other']} ({fmt(z, 'RF_other')}) |")
        L += ["", "Errors by cause, rev3 (rev0 on the same files):", ""]
        keys = list(dict.fromkeys(list(x["causes_rev3"]) + list(x["causes_rev0_same_files"])))
        L += ["| Cause | rev3 | rev0 |", "|---|---|---|"] + [f"| {k} | {x['causes_rev3'].get(k, 0)} | {x['causes_rev0_same_files'].get(k, 0)} |" for k in keys]
        if x["routing_failures"]:
            L += ["", "Routing failures: " + "; ".join(
                f"{r['file']} ({'denied' if r['denied_event'] else 'not denied'}, {r['type']} -> {r['routed_to']}, answer "
                f"{', '.join(str(a.get('value')) for a in r['routing_answer'] or []) or '-'}, {r['errors']} errors)" for r in x["routing_failures"]) + "."]
        L.append("")
    o = rep["overall_complete_regimes"]
    if o["rev3"]:
        a, z = o["rev3"], o["rev0_same_files"]
        L += [f"## Overall, complete regimes only ({', '.join(o['regimes'])})", "",
              f"{a['files']} files: E {a['E']} (rev0 {z['E']}); UR {a['UR']} ({z['UR']}), MR {a['MR']} ({z['MR']}), UH {a['UH']} ({z['UH']}), "
              f"MH {a['MH']} ({z['MH']}); routing failures denied {a['RF_denied']} ({z['RF_denied']}), other {a['RF_other']} ({z['RF_other']}); "
              f"failed runs {a['failed_runs']}.", "", "Causes: " + "; ".join(f"{k} {v}" for k, v in o["causes_rev3"].items()) + ".", ""]
    L += ["## The two largest causes, with two quotations each", ""]
    for q in rep["quotations"]:
        L.append(f"- **{q['cause']}** ({q['errors']} errors)")
        for y in q["quotations"]:
            L.append(f"  - {y['regime']} {y['file']}: {y['quote']}")
    sp = rep["spend"]
    L += ["", "## Spend", "", f"This run: USD {sp['rev3_usd']} ({sum(sp['paid_calls'].values())} paid calls; "
          + "; ".join(f"{k} USD {v}" for k, v in sp["by_arm_label"].items()) + f"). Step total from the ledgers: USD {sp['ledger_total_usd']} "
          f"(before this run USD {sp['ledger_total_before_usd']}).", ""]
    L += ["## What remains that is the product's behaviour", "", rep.get("closing") or "(written after the run)", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

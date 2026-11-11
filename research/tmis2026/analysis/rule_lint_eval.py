"""Model-free evaluation of the lint-reviewed theft rule files. No model calls.

    python3 rule_lint_eval.py      # writes rule_lint_eval.json and rule_lint_eval.md; writes two workflow folders

Rule files: before = rule_review/final/reviewed_rules.json; final = rule_review/lint/final/reviewed_rules.json;
pending = rule_review/lint/pending_jurist/reviewed_rules_with_042.json (final + editor A's rule-042 narrowing, NOT adopted).
Each is converted with harness/product/convert_theft.convert (final and pending written to new folders
harness/product/workflows/theft-lint-final and theft-lint-pending042), validated with the product's validate_workflow at
6a72159c, and checked against TheftPack.plan_exact as harness/product/compare_theft.py does.

This is post hoc analysis with the reference: the floor uses the designed truth of theft_diagnosis.py, extended to the
changed and new conditions (EXTRA below; uncertain assignments marked and varied).
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import theft_diagnosis as D  # noqa: E402

ct, load_reviewed, theft_v2 = D.ct, D.load_reviewed, D.theft_v2
FILES = {"before": TMIS / "rule_review/final/reviewed_rules.json",
         "final": TMIS / "rule_review/lint/final/reviewed_rules.json",
         "pending": TMIS / "rule_review/lint/pending_jurist/reviewed_rules_with_042.json"}
OUTDIR = {"final": TMIS / "harness/product/workflows/theft-lint-final", "pending": TMIS / "harness/product/workflows/theft-lint-pending042"}

# Designed truth for the changed and new conditions (keyed by the fact id up to '_rev'), in addition to theft_diagnosis's
# BACKGROUND and CHANGED, which still apply to the facts whose condition text is unchanged.
EXTRA = {
    "g003_rev": ("repair", "UNCERTAIN: narrowed 'traces removed or altered, or the loss location or damaged items altered, "
                           "repaired or disposed of ... or such a change is planned'. True in the repair on text ('A repair to a "
                           "damaged insured item is contemplated'), open in the repair unresolved text, false elsewhere (no text "
                           "states a change to traces or items); varied: false everywhere"),
    "g004_a": ("false", "UNCERTAIN: narrowed 'measures were to be taken to reduce the loss or to preserve or rescue insured items "
                        "... or the insurer gave instructions'. No text states either; varied: true in every text (a forced entry "
                        "calls for securing the premises)"),
    "g014_rev": ("false", "UNCERTAIN: 'the insurer has asked the claimant to produce original purchase vouchers ... or through the "
                          "insurer's claim form used for this claim'. No text states it (some texts are claim forms); varied: true in "
                          "every text. Its document D05 is due unconditionally through another rule, so it cannot change a checklist"),
    "g073_rev": ("false", "no document depends on it"),
    "g042_rev_03390de5": ("third", "pending file only: A's narrowing ('someone other than the policyholder who is identified ... "
                                   "an unidentified thief does not count'); true in the third-party on text, open in its unresolved "
                                   "text, false elsewhere (near-certain)"),
}
VARIANTS = {"primary": {}, "g003_rev false": {"g003_rev": "false"}, "g004_a true": {"g004_a": "true"},
            "g014_rev true": {"g014_rev": "true"}, "g020 F (expert)": {"expert": {"g022": True, "g020": False}},
            "literal g042 (before/final only)": {"literal042": True}}


def key(fid):
    if fid.startswith("g042_rev_03390de5"):
        return "g042_rev_03390de5"
    for k in ("g003_rev", "g004_a", "g014_rev", "g073_rev"):
        if fid.startswith(k):
            return k
    return None


def designed(meta, fu, variant=None):
    v = variant or {}
    expert = v.get("expert", D.EXPERT_VARIANTS[D.PRIMARY])
    always = ("g042",) if v.get("literal042") else ()
    plain = [f for f in fu if key(f) is None]
    out = D.designed(meta, plain, expert, always)
    for f in fu:
        k = key(f)
        if k is None:
            continue
        rule = v.get(k, EXTRA[k][0])
        if rule == "true":
            out[f] = True
        elif rule == "false":
            out[f] = False
        elif rule in ("repair", "third"):
            target = "PR_repair_over_500" if rule == "repair" else "PR_third_party_causer"
            out[f] = (True if meta["kind"] == "on" else None) if meta["condition"] == target else False
    return out


def engine_check(path, wf, W):
    """compare_theft.py's check: product evaluator vs TheftPack.plan_exact over 3,000 random assignments; and every document
    the rules can demand has a need."""
    pack = theft_v2.TheftPack(load_reviewed.load(path), judge_all=True)
    g2f = {g: ct.fact_id(g) for g in pack.guards}
    used = {f["id"] for f in wf["facts"]}
    ids = D.IDS
    rng = random.Random(7)
    n = agree = docs = 0
    first_diff = None
    for i in range(3000):
        nu = {g: rng.choice(["true"] + ["false"] * 2 + ["unresolved"] * (3 if i % 2 else 0)) for g in pack.guards}
        ref = pack.plan_exact(nu)
        facts = {g2f[g]: (v == "true") for g, v in nu.items() if v != "unresolved" and g2f[g] in used}
        ev = W.evaluate(wf, facts, {}, checked=True)
        req = {r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] == "missing"}
        hold = {r["document"] for r in ev["documents"] if r["required"] == "depends"}
        rq = {ids[d].lower() for d in ref["requests"]}
        rh = {ids[d].lower() for d in ref["holds"]}
        n += 1
        for d in {x["id"] for x in wf["documents"]}:
            docs += 1
            agree += ((d in req) == (d in rq)) and ((d in hold) == (d in rh))
        if (req != rq or hold != rh) and first_diff is None:
            first_diff = {"requests": sorted(req ^ rq), "holds": sorted(hold ^ rh)}
    demandable = set()
    for g in pack.guards:
        nu = {x: "false" for x in pack.guards}
        nu[g] = "true"
        p = pack.plan_exact(nu)
        demandable |= set(p["requests"]) | set(p["holds"])
    needs = {d["id"] for d in wf["documents"]}
    lacking = sorted(ids[d] for d in demandable if ids[d].lower() not in needs)
    return {"assignments": n, "document_decisions": docs, "agree": agree, "first_difference": first_diff,
            "demandable_without_need": lacking}


def run(W, wf, facts):
    return D.run_wf(W, wf, facts)


def main():
    W = D.evaluator()
    texts, pairs = D.load_data()
    wfs = {}
    out = {"note": __doc__, "files": {k: str(v.relative_to(TMIS)) for k, v in FILES.items()}, "mapping_extra": {k: v[1] for k, v in EXTRA.items()}}
    for name, path in FILES.items():
        wf = ct.convert(path)
        W.validate_workflow(wf)
        wfs[name] = wf
        if name in OUTDIR:
            OUTDIR[name].mkdir(parents=True, exist_ok=True)
            (OUTDIR[name] / "household_theft.json").write_text(json.dumps(wf, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    out["workflows"] = {n: {"facts": len(w["facts"]), "documents": len(w["documents"]), "conversion": {k: v for k, v in w["conversion"].items() if k != "loses"}}
                        for n, w in wfs.items()}
    out["engine_check"] = {n: engine_check(FILES[n], wfs[n], W) for n in wfs}
    # document conditions that changed
    bd = {d["id"]: d.get("required_when") for d in wfs["before"]["documents"]}
    out["document_condition_changes"] = {n: {d["id"].upper(): {"before": bd.get(d["id"]), "after": d.get("required_when")}
                                             for d in wfs[n]["documents"] if bd.get(d["id"], "absent") != d.get("required_when")}
                                         for n in ("final", "pending")}
    # floors and off-text checklists
    floors, offlists, everylists = {}, {}, {}
    for vname, var in VARIANTS.items():
        for n, wf in wfs.items():
            if var.get("literal042") and n == "pending":
                continue
            fu = D.used_facts(wf)
            plans = {t: [run(W, wf, designed(m, fu, var))] for t, m in texts.items()}
            on, un = D.score(pairs, plans)
            floors[f"{n} | {vname}"] = {"summary": {k: D.r3(v) for k, v in D.summ(on, un).items()},
                                       "by_fact": {k: D.r3(v) for k, v in D.by_fact(on).items()},
                                       "atoms": {c: {f"{a[0]}{a[1]}": k for a, k in v.items()} for c, v in D.atoms_by_fact(on).items()}}
            offs = {t: plans[t][0] for t in texts if texts[t]["kind"] == "off"}
            offlists[f"{n} | {vname}"] = {"requests_in_every_off_text": sorted(D.IDS[d] for d in set.intersection(*[set(p["requests"]) for p in offs.values()])),
                                          "holds_in_every_off_text": sorted(D.IDS[d] for d in set.intersection(*[set(p["holds"]) for p in offs.values()]))}
            everylists[f"{n} | {vname}"] = sorted(D.IDS[d] for d in set.intersection(*[set(p[0]["requests"]) for p in plans.values()]))
    out["floors"] = floors
    out["off_checklists"] = offlists
    out["requested_in_every_text"] = everylists
    changes = {}
    for vname in VARIANTS:
        b = offlists.get(f"before | {vname}")
        for n in ("final", "pending"):
            a = offlists.get(f"{n} | {vname}")
            if not a or not b:
                continue
            changes[f"{n} | {vname}"] = {"requests_leave": sorted(set(b["requests_in_every_off_text"]) - set(a["requests_in_every_off_text"])),
                                        "requests_enter": sorted(set(a["requests_in_every_off_text"]) - set(b["requests_in_every_off_text"])),
                                        "holds_leave": sorted(set(b["holds_in_every_off_text"]) - set(a["holds_in_every_off_text"])),
                                        "holds_enter": sorted(set(a["holds_in_every_off_text"]) - set(b["holds_in_every_off_text"]))}
    out["off_checklist_changes"] = changes
    # original rule base (bundle) for 'made due in every case by the original rule base'
    wo = ct.convert(TMIS / "rule_review/bundle/rules.json")
    fu = D.used_facts(wo)
    offs = [run(W, wo, D.designed(m, fu, D.EXPERT_VARIANTS[D.PRIMARY])) for t, m in texts.items() if m["kind"] == "off"]
    out["original_rule_base_requests_in_every_off_text"] = sorted(D.IDS[d] for d in set.intersection(*[set(p["requests"]) for p in offs]))
    # prediction for the frontier product from its stored readings (stories 8-15)
    st = json.loads((D.CONFIRM / "plans_theft_casepath_checklist_frontier.json").read_text())
    t2 = {t: m for t, m in texts.items() if m["story"] >= 8}
    p2 = [p for p in pairs if p["story"] >= 8]
    pred = {}
    for n, wf in wfs.items():
        fu = D.used_facts(wf)
        for assume in ("new facts never admitted true", "new facts at their designed value (primary)"):
            plans = {}
            carried = set()
            for t, m in t2.items():
                e = st[f"PRODUCT|{t}|0"]
                stored = D.admitted(e, [f for f in fu if key(f) is None])
                d = designed(m, fu)
                facts = {}
                for f in fu:
                    if key(f) is None:
                        facts[f] = stored[f]
                        carried.add(f)
                    else:
                        facts[f] = d[f] if assume.startswith("new facts at") else None
                plans[t] = [run(W, wf, facts)]
            on, un = D.score(p2, plans)
            pred[f"{n} | {assume}"] = {"summary": {k: D.r3(v) for k, v in D.summ(on, un).items()},
                                       "by_fact": {k: D.r3(v) for k, v in D.by_fact(on).items()},
                                       "new_or_changed_facts": sorted(f for f in fu if key(f) is not None),
                                       "requests_in_every_off_text": sorted(D.IDS[x] for x in set.intersection(*[set(plans[t][0]["requests"]) for t in t2 if t2[t]["kind"] == "off"]))}
    out["frontier_prediction"] = pred
    (HERE / "rule_lint_eval.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    (HERE / "rule_lint_eval.md").write_text(markdown(out))
    return out


def markdown(o):
    f3 = D.f3
    L = ["# Lint-reviewed theft rules: model-free evaluation", "", "Generated by `analysis/rule_lint_eval.py`. No model calls. Post hoc, uses the reference.", "",
         "## Conversion and engine check", ""]
    L.append(D.tbl(["Rule file", "Facts", "Documents", "Engine check (document decisions agreeing)", "Documents the rules can demand without a need"],
                   [[n, o["workflows"][n]["facts"], o["workflows"][n]["documents"], f"{e['agree']} of {e['document_decisions']} ({e['assignments']} assignments)",
                     ", ".join(e["demandable_without_need"]) or "none"] for n, e in o["engine_check"].items()]))
    L += ["", "Document conditions that changed (workflow `required_when`):", ""]
    for n, ch in o["document_condition_changes"].items():
        for d, v in ch.items():
            L.append(f"- {n}: {d}: {json.dumps(v['before'])} -> {json.dumps(v['after'])}")
    L += ["", "## Floor (designed facts, stories 0-15, 144 changed-fact pairs)", "", "Extended mapping:"]
    L += [f"- `{k}`: {v}" for k, v in o["mapping_extra"].items()]
    L.append("")
    L.append(D.tbl(["Rule file, mapping", "Wrong", "Missed", "Wrong + missed", "Unresolved unchanged"] + [D.SHORT[c] for c in D.COND],
                   [[k, f3(v["summary"]["wrong"]), f3(v["summary"]["missed"]), f3(v["summary"]["errors"]), f3(v["summary"]["unres_unchanged"])]
                    + [f3(v["by_fact"].get(c)) for c in D.COND] for k, v in o["floors"].items()]))
    L += ["", "## Documents requested in every off text (designed facts)", "",
          "Original rule base (bundle), primary mapping: " + ", ".join(o["original_rule_base_requests_in_every_off_text"]), ""]
    L.append(D.tbl(["Rule file, mapping", "Requested in every off text", "Held in every off text"],
                   [[k, ", ".join(v["requests_in_every_off_text"]), ", ".join(v["holds_in_every_off_text"]) or "–"] for k, v in o["off_checklists"].items()]))
    L += ["", "Changes against `before` (same mapping):", ""]
    L.append(D.tbl(["Rule file, mapping", "Requests leaving", "Requests entering", "Holds leaving", "Holds entering"],
                   [[k, ", ".join(v["requests_leave"]) or "–", ", ".join(v["requests_enter"]) or "–", ", ".join(v["holds_leave"]) or "–", ", ".join(v["holds_enter"]) or "–"]
                    for k, v in o["off_checklist_changes"].items()]))
    L += ["", "## Prediction for the frontier product from its stored readings (stories 8-15, one run)", "",
          "Facts whose condition text is unchanged keep the stored admitted value; removed conditions no longer exist. The new or changed "
          "facts cannot be carried over and are set as named. Changing any condition changes every reading request (all conditions are read "
          "together), so carrying the other values over is itself an assumption.", ""]
    L.append(D.tbl(["Rule file, assumption", "Wrong + missed", "Unresolved unchanged", "Requested in every off text"] + [D.SHORT[c] for c in D.COND],
                   [[k, f3(v["summary"]["errors"]), f3(v["summary"]["unres_unchanged"]), ", ".join(v["requests_in_every_off_text"])] + [f3(v["by_fact"].get(c)) for c in D.COND]
                    for k, v in o["frontier_prediction"].items()]))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: v["summary"]["errors"] for k, v in o["floors"].items()}, indent=0))
    print(json.dumps(o["off_checklist_changes"], indent=0))
    print(json.dumps({k: (e["agree"], e["document_decisions"], e["demandable_without_need"]) for k, e in o["engine_check"].items()}))
    print(json.dumps({k: (v["summary"]["errors"], v["summary"]["unres_unchanged"], v["requests_in_every_off_text"]) for k, v in o["frontier_prediction"].items()}, indent=0))

"""POST HOC. Error decomposition of the finished Study 3 runs (data fresh2, label confirm), every model x regime cell.
No model calls. Not part of ANALYSIS_PLAN_STUDY3.md.

    python3 decomposition.py [--tenancy-reference module.path:function]   # writes decomposition.json and .md

Product designs (stored runs, the product's evaluator at 6a72159c on the stored facts and findings):
  casepath                     gpt-6-luna, full product, 3 runs
  casepath_frontier_checklist  gpt-6.1-terra, checklist only, 1 run

Method (path method). For one claim-run (tenancy) or one changed-fact pair-run (theft), the stored state of the run is
replaced, stage by stage in a fixed order, by its designed value; the error that disappears at a stage is that stage's
part; what remains when every stage carries its designed value is the rule error. The parts add up exactly to the error
recomputed from the stored facts and findings; 'product steps' is the stored error minus that recomputed error (needs
the product's agents added, and the like). Order: routing, document judgment, reading, hold (theft: reading, hold).
Interaction remainder = (recomputed - rule error) - sum of each stage's effect when it alone is replaced; it says how much
the attribution depends on the order (0 = additive).

Families:
- rule error: errors left with every stage at its designed value (theft: the converted rules executed on designed facts;
  tenancy: zero by construction, because the reference comes from the engine the workflows were converted from; a
  non-zero value would be a mismatch between that engine and the product's evaluator).
- routing (tenancy): the claim handed over, or routed to another workflow.
- document judgment (tenancy): a supplied document judged present though insufficient, or judged absent / unusable
  though sufficient (designed finding: present if the reference marks the attachment sufficient, unusable if not).
- reading: a fact admitted with a value other than its designed value (tenancy: including a denied defining event
  admitted as received, and a stated fact presumed with the wrong value); theft also: the changed fact not admitted.
- hold: a fact left without a value although it has a designed value (a stated fact left unresolved; an unstated fact
  raised instead of presumed), or a fact given a value although it is open by design (an open fact given a value or
  presumed).
Designed values: tenancy, the reference's policy verdicts under the silence policy (true / false / unresolved) and the
reference family; theft, the mapping of analysis/theft_diagnosis.py (primary), which is post hoc and partly uncertain.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import theft_diagnosis as TD  # noqa: E402

s3, s2, common = TD.s3, TD.s2, TD.common
SPEC = json.loads((HERE / "study3_spec.json").read_text())
PRODUCT = {"casepath": "CasePath, gpt-6-luna (full, 3 runs)", "casepath_frontier_checklist": "CasePath, gpt-6.1-terra (checklist only, 1 run)"}
SINGLE = {"ric": "Rules in context, gpt-6-luna", "ric_frontier": "Rules in context, gpt-6.1-terra",
          "self_consistency": "Self-consistency, gpt-6-luna", "model_executes_rules": "Model executes rules, gpt-6-luna",
          "react": "ReAct, gpt-6-luna", "ric_original": "Rules in context, original rules, gpt-6-luna",
          "ric_original_frontier": "Rules in context, original rules, gpt-6.1-terra"}
SUBSETS = ("ordinary", "denied_event", "open_event")
MEAS = ("strict_unsafe", "all_dev")


def study():
    D = {"tenancy": common.data("tenancy", "fresh2"), "theft": common.data("theft", "fresh2")}
    return s3.Study(SPEC, "fresh2", "confirm", D), D


def measures(ref, plan):
    r = s2.ten_row(ref, plan)
    return {"strict_unsafe": r["strict_unsafe"], "all_dev": r["strict_unsafe"] + r["held_req"] + r["spurious_hold"], "row": r}


# ------------------------------------------------------------------------------------------------ tenancy
def tenancy_state(entry, ref):
    """The stored state of a claim-run and its designed counterpart."""
    plan = entry.get("plan") if entry else None
    extra = (entry or {}).get("product_extra") or {}
    fam = None if plan is None or plan.get("deferred") else plan.get("family")
    facts = {}
    for k, f in (extra.get("facts") or {}).items():
        if (f["status"] == "established" and f.get("verdict") == "accepted") or f["status"] == "presumed":
            facts[k] = f["value"]
    findings = {d: j["status"] for d, j in (extra.get("document_judgments") or {}).items()
                if j["status"] in {"present", "unusable"} and j.get("verdict") == "accepted"}
    dfacts = {k: {"true": True, "false": False}.get(v) for k, v in ref["policy_verdicts"].items()}
    dfind = {a["document_type"]: "present" if a["sufficient"] else "unusable" for a in ref.get("attachments") or []}
    return {"family": fam, "facts": facts, "findings": findings, "read": fam is not None}, \
           {"family": ref["family"], "facts": dfacts, "findings": dfind}


def tenancy_eval(W, cat, ref, family, facts, findings):
    wf = cat.get(family)
    fx = {f["id"]: facts.get(f["id"]) for f in wf["facts"] if f["type"] == "boolean"}
    fx["dispute_family"] = family
    ev = W.evaluate(wf, fx, {d: {"status": s, "verdict": "accepted"} for d, s in findings.items()}, checked=True)
    plan = {"family": family, "deferred": False,
            "requests": sorted(r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] in {"missing", "unusable"}),
            "holds": sorted(r["document"] for r in ev["documents"] if r["required"] == "depends")}
    return measures(ref, plan)


def tenancy_classes(stored, designed):
    """Facts and documents by the stage whose error they are."""
    reading, hold = set(), set()
    if stored["read"] and stored["family"] == designed["family"]:
        for f, d in designed["facts"].items():
            a = stored["facts"].get(f)
            if a is not None and d is not None and a != d:
                reading.add(f)
            elif (a is None) != (d is None):
                hold.add(f)
    docs = {d for d in set(stored["findings"]) | set(designed["findings"]) if stored["findings"].get(d) != designed["findings"].get(d)}
    return reading, hold, docs


def tenancy_apply(stored, designed, fix):
    """The state with the stages in `fix` replaced by their designed values."""
    routed_ok = stored["read"] and stored["family"] == designed["family"]
    reading, hold, docs = tenancy_classes(stored, designed)
    if not routed_ok and "routing" not in fix:
        return None  # still handed over / misrouted: the stored outcome stands
    if routed_ok:
        facts = dict(stored["facts"])
        findings = dict(stored["findings"])
    else:  # routing fixed: what the run never read is taken at its designed value
        facts = dict(designed["facts"])
        findings = dict(designed["findings"])
    for f in designed["facts"]:
        if (f in reading and "reading" in fix) or (f in hold and "hold" in fix):
            facts[f] = designed["facts"][f]
    if "document" in fix:
        findings = dict(designed["findings"])
    return facts, findings


ORDER_T = ("routing", "document", "reading", "hold")


def decompose_tenancy(st, design, W, cat, reference):
    st.load(design, "tenancy")
    ent = st.entries[(design, "tenancy")]
    rows = []
    for cid, runs in ent.items():
        ref = reference(cid)
        for r, e in enumerate(runs):
            stored, designed = tenancy_state(e, ref)
            meas = measures(ref, (e or {}).get("plan"))

            def E(fix):
                x = tenancy_apply(stored, designed, fix)
                if x is None:
                    return measures(ref, (e or {}).get("plan"))
                return tenancy_eval(W, cat, ref, designed["family"], x[0], x[1])
            rec = E(()) if stored["read"] else meas
            path, prev = {}, rec
            fixed = ()
            for stage in ORDER_T:
                fixed = fixed + (stage,)
                cur = E(fixed)
                path[stage] = {m: prev[m] - cur[m] for m in MEAS}
                prev = cur
            floor = prev
            alone = {stage: {m: rec[m] - E((stage,))[m] for m in MEAS} for stage in ORDER_T}
            row = {"claim": cid, "run": r, "subset": next(s for s in SUBSETS if st.in_subset(cid, s))}
            for m in MEAS:
                row[m] = {"measured": meas[m], "product_steps": meas[m] - rec[m], "rule": floor[m],
                          **{s: path[s][m] for s in ORDER_T},
                          "interaction": (rec[m] - floor[m]) - sum(alone[s][m] for s in ORDER_T)}
            row["kinds"] = meas["row"]
            rows.append(row)
    return rows


def summarise(rows, measure, subset=None):
    rs = [r for r in rows if subset is None or r["subset"] == subset]
    n = len(rs)
    keys = ("measured", "rule", "routing", "document", "reading", "hold", "product_steps", "interaction")
    return {"claim_runs": n, **{k: sum(r[measure][k] for r in rs) / n for k in keys}} if n else {"claim_runs": 0}


KINDS = ("unnecessary", "missed", "handed", "premature", "silent_skip", "held_req", "spurious_hold")


def single_tenancy(st, design):
    rows = st.tenancy_rows(design)
    out = {}
    for sub in (None,) + SUBSETS:
        rs = [r for r in rows if sub is None or st.in_subset(r["case"], sub)]
        n = len(rs)
        out[sub or "all"] = {"claim_runs": n, **{k: sum(r[k] for r in rs) / n for k in KINDS},
                             "strict_unsafe": sum(r["strict_unsafe"] for r in rs) / n, "all_dev": sum(r["all_dev"] for r in rs) / n}
    return out


# ------------------------------------------------------------------------------------------------ theft
def decompose_theft(st, design, W):
    st.load(design, "theft")
    ent = st.entries[(design, "theft")]
    T = st.D["theft"].texts()
    wf = json.loads((TMIS / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
    fu = TD.used_facts(wf)
    ex = TD.Exec(W, wf)
    runs = st.runs(design, "theft")
    rows = []
    for p in [p for p in st.pairs if p["kind"] == "on"]:
        Po, Pv = TD.designed(T[p["off"]], fu), TD.designed(T[p["variant"]], fu)
        Gc = set(TD.gset(p["condition"], fu))
        for r in range(runs):
            eo, evv = ent[p["off"]][r], ent[p["variant"]][r]
            Ao, Av = TD.admitted(eo, fu), TD.admitted(evv, fu)

            def cls(A, P, changed):
                rd, hd = set(), set()
                for f in fu:
                    a, d = A[f], P[f]
                    if a is not None and d is not None and a != d:
                        rd.add(f)
                    elif changed and f in Gc and d is True and a is None:
                        rd.add(f)  # the changed fact not admitted
                    elif (a is None) != (d is None):
                        hd.add(f)
                return rd, hd
            ro, ho = cls(Ao, Po, False)
            rv, hv = cls(Av, Pv, True)

            def state(fix):
                o, v = dict(Ao), dict(Av)
                for fam, (sb, sv) in (("reading", (ro, rv)), ("hold", (ho, hv))):
                    shared = {f for f in sb & sv if Ao[f] == Av[f]}
                    for f in fu:
                        if f in shared and f"{fam}_shared" in fix:
                            o[f], v[f] = Po[f], Pv[f]
                        if f in sb - shared and f"{fam}_base" in fix:
                            o[f] = Po[f]
                        if f in sv - shared and f"{fam}_variant" in fix:
                            v[f] = Pv[f]
                return TD.pair_err(ex, p, o, v)[0]
            stored_err = s2.theft_row(p, s3.to_names((eo or {}).get("plan"), st.inv), s3.to_names((evv or {}).get("plan"), st.inv))["errors"]
            rec = state(())
            steps = ("reading_shared", "reading_base", "reading_variant", "hold_shared", "hold_base", "hold_variant")
            part, prev, fixed = {}, rec, ()
            for s_ in steps:
                fixed = fixed + (s_,)
                cur = state(fixed)
                part[s_] = prev - cur
                prev = cur
            floor = prev
            alone_r = rec - state(("reading_shared", "reading_base", "reading_variant"))
            alone_h = rec - state(("hold_shared", "hold_base", "hold_variant"))
            rows.append({"pair": p["pair_id"], "condition": p["condition"], "run": r, "measured": stored_err,
                         "product_steps": stored_err - rec, "rule": floor,
                         "reading": part["reading_shared"] + part["reading_base"] + part["reading_variant"],
                         "hold": part["hold_shared"] + part["hold_base"] + part["hold_variant"],
                         **part, "interaction": (rec - floor) - alone_r - alone_h})
    return rows


def theft_single(st, design, floor_atoms):
    on, _ = st.theft_rows(design)
    n = len(on)
    same = other = 0
    for r in on:
        fa = floor_atoms.get(r["pair_id"] if "pair_id" in r else None, set())
        for a in r["atoms"]:
            if (a[0], a[1]) in fa:
                same += 1
            else:
                other += 1
    return {"pair_runs": n, "errors": (same + other) / n, "same_as_rule_floor": same / n, "other": other / n}


def floor_atoms(rules_path, W, texts, pairs):
    wf = TD.ct.convert(rules_path)
    plans, on, un = TD.floor(W, wf, texts, pairs, TD.EXPERT_VARIANTS[TD.PRIMARY])
    return {r["pair_id"]: {(a[0], a[1]) for a in r["atoms"]} for r in on}


# ------------------------------------------------------------------------------------------------ main
def main(reference_spec=None):
    st, Dm = study()
    W = TD.evaluator()
    cat = W.Catalogue.load(TMIS / "harness/product/workflows/fresh-serial-sync")
    reference = Dm["tenancy"].reference
    if reference_spec:
        mod, fn = reference_spec.split(":")
        reference = getattr(importlib.import_module(mod), fn)
    out = {"label": "POST HOC: not part of ANALYSIS_PLAN_STUDY3.md", "method": __doc__,
           "tenancy_reference": reference_spec or "fresh2 reference (the engine the workflows were converted from)"}
    # tenancy
    ten = {}
    for d in PRODUCT:
        rows = decompose_tenancy(st, d, W, cat, reference)
        ten[d] = {m: {sub or "all": summarise(rows, m, sub) for sub in (None,) + SUBSETS} for m in MEAS}
        ten[d]["kinds"] = {sub or "all": {k: sum(r["kinds"][k] for r in rows if sub is None or r["subset"] == sub) /
                                         max(1, sum(1 for r in rows if sub is None or r["subset"] == sub)) for k in KINDS}
                           for sub in (None,) + SUBSETS}
    out["tenancy_product"] = ten
    out["tenancy_single"] = {d: single_tenancy(st, d) for d in ("ric", "ric_frontier", "self_consistency", "model_executes_rules", "react")}
    # theft
    texts, pairs = st.D["theft"].texts(), [p for p in st.pairs]
    allt = {t: {"story": v["story"], "kind": v["kind"], "condition": v["condition"], "text": v["text"]} for t, v in texts.items()}
    th = {}
    for d in PRODUCT:
        rows = decompose_theft(st, d, W)
        keys = ("measured", "rule", "reading", "hold", "product_steps", "interaction", "reading_shared", "reading_base", "reading_variant",
                "hold_shared", "hold_base", "hold_variant")
        th[d] = {"all": {"pair_runs": len(rows), **{k: sum(r[k] for r in rows) / len(rows) for k in keys}},
                 "by_fact": {c: {k: sum(r[k] for r in rows if r["condition"] == c) / sum(1 for r in rows if r["condition"] == c) for k in keys}
                             for c in TD.COND}}
    out["theft_product"] = th
    fa = {"reviewed": floor_atoms(TD.REVIEWED, W, allt, pairs), "original": floor_atoms(TD.ORIGINAL, W, allt, pairs)}
    out["theft_single"] = {d: theft_single(st, d, fa["original" if "original" in d else "reviewed"])
                           for d in ("ric", "ric_frontier", "ric_original", "ric_original_frontier", "self_consistency", "model_executes_rules", "react")}
    (HERE / "decomposition.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    (HERE / "decomposition.md").write_text(markdown(out))
    return out


def f3(x):
    return "–" if x is None else f"{x:.3f}"


def markdown(o):
    L = ["# Error decomposition by stage (POST HOC)", "",
         "**Post hoc analysis, not part of the pre-registered plan.** Generated by `analysis/decomposition.py` from the stored runs of "
         "Study 3 (data fresh2, label confirm). No model calls.", "",
         "Each scored error is attributed to the stage that caused it: the run's stored state is replaced stage by stage, in a fixed "
         "order, by its designed value, and the error that disappears at a stage is that stage's part. Order: routing, document "
         "judgment, reading, hold; what remains with every stage at its designed value is the **rule error**. The parts add up "
         "exactly to the measured value ('product steps' = stored error minus the error recomputed from the stored facts and "
         "findings). The **interaction remainder** (not part of the sum) is the difference between the path attribution and the sum "
         "of each stage's effect alone; 0 means the attribution does not depend on the order.", "",
         "- **Rule error:** errors that remain with perfect facts. Tenancy: zero by construction, because the reference comes from the "
         "engine the workflows were converted from (reference used: " + o["tenancy_reference"] + "; an independent reference will be "
         "substituted later).",
         "- **Routing:** the claim handed over or routed to another workflow (tenancy).",
         "- **Document judgment:** a supplied document judged present though insufficient (missed request), or judged absent or "
         "unusable though sufficient (unnecessary request) (tenancy).",
         "- **Reading error:** a fact admitted with a wrong value (including a denied defining event admitted as received); theft also: "
         "the changed fact not admitted.",
         "- **Hold error:** a stated fact left unresolved (documents held), an unstated fact raised instead of presumed (unneeded "
         "holds), or an open fact given a value or presumed (premature requests or silent skips).", ""]
    L += ["## Tenancy (per claim-run, all 96 claims)", ""]
    for m, name in (("strict_unsafe", "strict unsafe errors per claim"), ("all_dev", "all deviations per claim")):
        L += [f"**{name}**", "", "| Design | Claim-runs | Rule | Routing | Document judgment | Reading | Hold | Product steps | = Measured | Interaction remainder |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for d, lab in PRODUCT.items():
            s = o["tenancy_product"][d][m]["all"]
            L.append(f"| {lab} | {s['claim_runs']} | {f3(s['rule'])} | {f3(s['routing'])} | {f3(s['document'])} | {f3(s['reading'])} | "
                     f"{f3(s['hold'])} | {f3(s['product_steps'])} | {f3(s['measured'])} | {f3(s['interaction'])} |")
        L.append("")
    L += ["Per subset (ordinary: request set not empty; denied event: empty request and held sets; open event: empty request set, "
          "documents held):", "", "| Design | Measure | Subset | Claim-runs | Rule | Routing | Document judgment | Reading | Hold | Product steps | = Measured | Interaction |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, lab in PRODUCT.items():
        for m in MEAS:
            for sub in SUBSETS:
                s = o["tenancy_product"][d][m][sub]
                L.append(f"| {lab} | {m} | {sub} | {s['claim_runs']} | {f3(s['rule'])} | {f3(s['routing'])} | {f3(s['document'])} | "
                         f"{f3(s['reading'])} | {f3(s['hold'])} | {f3(s['product_steps'])} | {f3(s['measured'])} | {f3(s['interaction'])} |")
    L += ["", "Single-prompt designs: no stage is observable, so only the kind of each error is reported (per claim-run).", "",
          "| Design | Subset | Unnecessary | Missed | Handed over | Premature | Silent skips | Held required-now | Spurious holds | Strict unsafe | All deviations |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, v in o["tenancy_single"].items():
        for sub, s in v.items():
            L.append(f"| {SINGLE[d]} | {sub} | " + " | ".join(f3(s[k]) for k in KINDS) + f" | {f3(s['strict_unsafe'])} | {f3(s['all_dev'])} |")
    L += ["", "The product's errors by kind (same layout):", "", "| Design | Subset | " + " | ".join(KINDS) + " |", "|---|---|" + "---|" * len(KINDS)]
    for d, lab in PRODUCT.items():
        for sub, s in o["tenancy_product"][d]["kinds"].items():
            L.append(f"| {lab} | {sub} | " + " | ".join(f3(s[k]) for k in KINDS) + " |")
    L += ["", "## Theft (wrong + missed changes per changed-fact pair-run)", "",
          "Designed facts: the mapping of `analysis/theft_diagnosis.py` (primary; partly uncertain, see there). Order: reading, hold.", "",
          "| Design | Pair-runs | Rule | Reading | Hold | Product steps | = Measured | Interaction remainder |", "|---|---|---|---|---|---|---|---|"]
    for d, lab in PRODUCT.items():
        s = o["theft_product"][d]["all"]
        L.append(f"| {lab} | {s['pair_runs']} | {f3(s['rule'])} | {f3(s['reading'])} | {f3(s['hold'])} | {f3(s['product_steps'])} | {f3(s['measured'])} | {f3(s['interaction'])} |")
    L += ["", "Single-prompt designs (no stage observable): errors that coincide with the rule floor's errors on the same pair (same "
          "document, same direction, same kind) and the rest.", "", "| Design | Pair-runs | Same as rule floor | Other | = Errors |", "|---|---|---|---|---|"]
    for d, s in o["theft_single"].items():
        L.append(f"| {SINGLE[d]} | {s['pair_runs']} | {f3(s['same_as_rule_floor'])} | {f3(s['other'])} | {f3(s['errors'])} |")
    L += ["", "## Appendix: theft sub-split (base text vs variant) and by changed fact", "",
          "Within each family: first the facts both texts got wrong in the same way (shared), then those only the base text got wrong, "
          "then those only the variant got wrong.", "",
          "| Design | Changed fact | Rule | Reading, shared | Reading, base text | Reading, variant | Hold, shared | Hold, base text | Hold, variant | Product steps | = Measured |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, lab in PRODUCT.items():
        rows = [("all", o["theft_product"][d]["all"])] + list(o["theft_product"][d]["by_fact"].items())
        for c, s in rows:
            L.append(f"| {lab} | {TD.SHORT.get(c, c)} | {f3(s['rule'])} | {f3(s['reading_shared'])} | {f3(s['reading_base'])} | {f3(s['reading_variant'])} | "
                     f"{f3(s['hold_shared'])} | {f3(s['hold_base'])} | {f3(s['hold_variant'])} | {f3(s['product_steps'])} | {f3(s['measured'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenancy-reference", default=None, help="module:function returning the reference of a claim id")
    a = ap.parse_args()
    o = main(a.tenancy_reference)
    for d in PRODUCT:
        print(d, "tenancy strict", {k: round(v, 3) for k, v in o["tenancy_product"][d]["strict_unsafe"]["all"].items()})
        print(d, "tenancy all_dev", {k: round(v, 3) for k, v in o["tenancy_product"][d]["all_dev"]["all"].items()})
        print(d, "theft", {k: round(v, 3) for k, v in o["theft_product"][d]["all"].items()})
    print({d: {k: round(v, 3) for k, v in s.items()} for d, s in o["theft_single"].items()})

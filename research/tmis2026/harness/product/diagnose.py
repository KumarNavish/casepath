"""Attribute each of the product's remaining errors to its cause in the pipeline. No model calls.

    python3 diagnose.py [--label p7ff]      -> results/diagnose_<label>.json, printed summary

Tenancy (conservative view, every claim-run). For each error document -- missed (required now, neither requested nor
held), unnecessary request, premature request (of a reference-held document), silent skip (a reference-held document
neither held nor requested), and held-required-now (not unsafe, but not requested) -- the cause is found by replay
through the product's own evaluator (casepath.process.workflows.evaluate) on the routed workflow:
  1. failed run / routing (handed over, wrong family);
  2. process-builder addition (an added need the product marked required, or held);
  3. facts: replace the product's effective facts (accepted established facts + applied presumptions) by the
     reference's policy verdicts one fact at a time; the first fact whose correction fixes the document is the cause,
     classified by how the product recorded it: left unknown by the claim reader (with a quote / without), rejected by
     the source checker, conflicting second reading, established but not checked, presumption (no quotation found, the
     silence presumption filled it), or judged with the wrong value by the claim reader;
  4. document finder: with the reference's facts, replacing the product's document findings by the reference's
     (supplied sufficient -> present) fixes it; split by whether the need has must_show items;
  5. walk changed by process-builder steps/questions (the case graph's evaluation differs from the workflow's);
  6. evaluator: still wrong with the reference's facts and findings (expected none: 5,076 of 5,076 in compare.py).
Theft (stories 4-5, k=1): each wrong / missed change of a pair is attributed by the same replay on the converted
workflow, per text, against the reference realisation chosen by best_realization.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
for p in (HERE, TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh", TMIS / "analysis"):
    sys.path.insert(0, str(p))
PRODUCT = Path(os.environ.get("CASEPATH_PRODUCT", "/home/user/work/casepath-product-7ff7af64"))
sys.path.insert(0, str(PRODUCT / "casepath-internal"))
from casepath.process import workflows as W  # noqa: E402

RUNS = TMIS / "runs"


def effective(extra):
    facts, how = {}, {}
    for k, f in (extra.get("facts") or {}).items():
        if f["status"] == "established" and f.get("verdict") == "accepted":
            facts[k] = f["value"]
        elif f["status"] == "presumed":
            facts[k] = f["value"]
        how[k] = f
    return facts, how


def fact_cause(fid, how):
    f = how.get(fid)
    if f is None:
        return "fact not recorded (no presumption)"
    if f["status"] == "presumed":
        return "presumption (no quotation found; silence presumption applied)"
    if f["status"] == "conflicting":
        return "second-reading conflict"
    if f.get("verdict") == "rejected":
        return "source-checker rejection"
    if f["status"] == "established" and f.get("verdict") != "accepted":
        return f"established, not accepted (verdict {f.get('verdict')})"
    if f["status"] == "unknown":
        return "left unknown by the claim reader" + (" (quoted)" if f.get("cited") else "")
    return "claim reader judged the wrong value"


def state(ev, d):
    row = next((r for r in ev["documents"] if r["document"] == d), None)
    if row is None:
        return "absent"
    if row["required"] == "depends":
        return "hold"
    if row["required"] == "yes" and row["status"] in {"missing", "unusable"}:
        return "request"
    return "absent"


def findings_from(extra):
    return {d: {"status": j["status"], "verdict": "accepted"} for d, j in (extra.get("document_judgments") or {}).items()
            if j["status"] in {"present", "unusable"} and j.get("verdict") == "accepted"}


def attribute_doc(wf, d, want, facts, how, findings, ref_facts, ref_findings, wf_state):
    """want: 'request' | 'hold' | 'absent'. Returns the cause."""
    if wf_state == want:
        return "walk changed by process-builder steps/questions (workflow alone gives the right state)"
    flags = [f["id"] for f in wf["facts"] if f["id"] in ref_facts or f["id"] in facts]
    for fid in flags:
        if facts.get(fid) == ref_facts.get(fid):
            continue
        trial = dict(facts)
        if ref_facts.get(fid) is None:
            trial.pop(fid, None)
        else:
            trial[fid] = ref_facts[fid]
        if state(W.evaluate(wf, trial, findings, checked=True), d) == want:
            return f"fact {fid}: " + fact_cause(fid, how)
    fixed = {**{k: v for k, v in facts.items() if k not in ref_facts}, **{k: v for k, v in ref_facts.items() if v is not None}}
    if state(W.evaluate(wf, fixed, findings, checked=True), d) == want:
        return "several facts together: " + ", ".join(sorted(fact_cause(f, how) for f in flags if facts.get(f) != ref_facts.get(f)))
    if state(W.evaluate(wf, fixed, ref_findings, checked=True), d) == want:
        doc = next(x for x in wf["documents"] if x["id"] == d)
        judged = findings.get(d, {}).get("status", "missing")
        return f"document finder ({'with' if doc.get('must_show') else 'without'} must_show): judged {judged}"
    return "evaluator / workflow data"


def tenancy(label):
    import tenancy_fresh as F
    prod = json.loads((RUNS / "product" / f"plans_tenancy_gpt-6-luna_fresh_{label}.json").read_text())
    cat = W.Catalogue.load(HERE / "workflows" / "fresh-serial-sync")
    causes = defaultdict(Counter)
    blocking = Counter()
    for key, entry in sorted(prod.items()):
        _, cid, run = key.split("|")
        ref = F.reference(cid)
        st = ref["document_states"]
        req_now = {d for d, s in st.items() if s in {"required_now", "supplied_insufficient"}}
        held = {d for d, s in st.items() if s == "held"}
        plan, extra = entry.get("plan"), entry.get("product_extra") or {}
        if plan is None:
            causes["missed"]["failed run (" + str(entry.get("error"))[:60] + ")"] += len(req_now)
            causes["silent_skip"]["failed run"] += len(held)
            continue
        P, H = set(plan["requests"]), set(plan["holds"]) - set(plan["requests"])
        if plan.get("deferred"):
            causes["handed"]["routing: whole claim handed over"] += len(req_now - P)
            continue
        if plan["family"] != ref["family"]:
            for d in req_now - P - H:
                causes["missed"]["routing: wrong family"] += 1
            for d in P - req_now - held:
                causes["unnecessary"]["routing: wrong family"] += 1
            continue
        wf = cat.get(plan["family"])
        facts, how = effective(extra)
        findings = findings_from(extra)
        ref_facts = {"dispute_family": ref["family"],
                     **{f: (None if v == "unresolved" else v == "true") for f, v in ref["policy_verdicts"].items()}}
        ref_findings = {d: {"status": "present", "verdict": "accepted"} for d, s in st.items() if s == "supplied_sufficient"}
        ref_findings.update({d: {"status": "unusable", "verdict": "accepted"} for d, s in st.items() if s == "supplied_insufficient"})
        ev = W.evaluate(wf, facts, findings, checked=True)
        for f in extra.get("waiting_for") or []:
            blocking[fact_cause(f, how)] += 1
        added = set(plan.get("added_requests", [])) | set(plan.get("added_holds", []))
        errors = [("missed", d, "request") for d in req_now - P - H] + \
                 [("held_required_now", d, "request") for d in req_now & H] + \
                 [("unnecessary", d, "absent") for d in P - req_now - held] + \
                 [("premature", d, "hold") for d in P & held] + \
                 [("silent_skip", d, "hold") for d in held - P - H] + \
                 [("spurious_hold", d, "absent") for d in H - req_now - held]
        for kind, d, want in errors:
            if d in added:
                b = "process-builder addition marked required" if kind == "unnecessary" else "process-builder addition held"
                causes[kind][b] += 1
                continue
            causes[kind][attribute_doc(wf, d, want, facts, how, findings, ref_facts, ref_findings, state(ev, d))] += 1
    return {k: dict(v.most_common()) for k, v in causes.items()}, dict(blocking.most_common())


def theft(stories=(4, 5)):
    import common
    from theft_data import best_realization, doc_ids
    from theft_score import delta
    D = common.data("theft", "fresh")
    ids = doc_ids()
    prod = json.loads((RUNS / "product" / "plans_theft_gpt-6-luna_fresh_reviewed.json").read_text())
    wf = W.Catalogue.load(HERE / "workflows" / "theft-reviewed").get("household_theft")
    causes = Counter()
    per_text = {}
    for p in [p for p in D.pairs() if p["story"] in stories and p["kind"] == "on"]:
        eo, ev_ = prod.get(f"PRODUCT|{p['off']}|0"), prod.get(f"PRODUCT|{p['variant']}|0")
        if not eo or not ev_:
            continue
        off, var = eo.get("plan") or {"requests": [], "holds": []}, ev_.get("plan") or {"requests": [], "holds": []}
        handed = off.get("deferred") or var.get("deferred")
        pred = delta(set(off["requests"]), set(var["requests"]))
        sel, _ = best_realization(pred, p["reference"])
        wrong, missed = set(pred) - set(sel), set(sel) - set(pred)
        for atom in sorted(wrong | missed):
            kind = "wrong" if atom in wrong else "missed"
            doc = atom[1:]
            did = ids.get(doc, doc).lower()
            if handed:
                causes[f"{kind}: routing handed one text of the pair over (claim_type not established)"] += 1
                continue
            if did.startswith("e-") or doc not in ids:
                causes[f"{kind}: process-builder addition differs between the two texts"] += 1
                continue
            # which text's state is off: the text whose request set must change to remove the error
            sides = []
            for name, entry in (("off", eo), ("variant", ev_)):
                extra = entry.get("product_extra") or {}
                facts, how = effective(extra)
                cond = next((x.get("required_when") for x in wf["documents"] if x["id"] == did), True)
                used = sorted(W.condition_facts(cond)) if cond is not True else []
                states = {f: (facts.get(f), fact_cause(f, how) if f in how else "not recorded") for f in used}
                judged = (extra.get("document_judgments") or {}).get(did, {}).get("status")
                sides.append((name, states, judged))
            for name, states, judged in sides:
                if judged == "present":
                    causes[f"{kind}: document finder judged present ({name} text)"] += 1
                    break
            else:
                vo, vv = sides[0][1], sides[1][1]
                diff = [f for f in vo if vo[f][0] != vv[f][0]]
                if kind == "wrong" and diff:
                    causes[f"{kind}: a condition's value differs between the texts (unchanged in the story): "
                           + "; ".join(sorted({vo[f][1] if vo[f][0] is not True else vv[f][1] for f in diff}))] += 1
                elif kind == "missed":
                    states = vv if atom[0] == "+" else vo
                    causes[f"{kind}: the changed condition not established: "
                           + "; ".join(sorted({s[1] for s in states.values()}) or ["need unconditional after conversion (cheapest route / OR of conditions)"])] += 1
                else:
                    causes[f"{kind}: other (" + ", ".join(f"{f}={vo[f][0]}/{vv[f][0]}" for f in vo) + ")"] += 1
    return dict(causes.most_common())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="p7ff")
    a = ap.parse_args()
    ten, blocking = tenancy(a.label)
    th = theft() if (RUNS / "product" / "plans_theft_gpt-6-luna_fresh_reviewed.json").exists() else {}
    out = {"tenancy": ten, "tenancy_waiting_for_causes": blocking, "theft": th}
    (HERE / "results" / f"diagnose_{a.label}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

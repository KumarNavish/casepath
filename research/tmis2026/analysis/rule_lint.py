"""Reference-free lint of the theft rule base from readings of ordinary cases. No model calls.

    python3 rule_lint.py        # writes rule_lint.json and rule_lint.md next to this file

Idea. A branch condition is meant to distinguish a case from the ordinary case of its type. If the readings admit it true
in most ordinary cases, it does not distinguish cases: either it belongs to the case type (its documents are due in every
case) or it is broader than its source. Stand-in for ordinary cases: the baseline ("off") case documents of the theft
stories. Variants of a story differ from its baseline document in one sentence.

Inputs, and only these: the case texts (texts() of the data loaders; no reference field is read), the stored product runs
at the tested commit 6a72159c (study3 confirm runs, stories 8-15; development runs on stories 4-7 whose manifest shows
the same source tree and workflow file) with their readings from the response cache, the rule base the workflow was
converted from (rule_review/final/reviewed_rules.json) and the passage file of the rule review (rule_review/bundle/).
No reference answer, pair score, designed truth or earlier diagnosis is used to decide a flag.

Definitions (per condition, per model; a "run" of a text is one product run, i.e. its three readings):
- admitted true: every reading of the run answers true with a quotation found verbatim (whitespace and case normalised)
  in the text (the product's admission rule for a value; it is computed from the readings so that it applies equally to
  every condition and to runs that stored no facts);
- some reading true: at least one reading answers true;
- distinct runs: identical reading responses (the same cache keys, e.g. shared by two stored arms) count once;
- instability: over variant documents, the run's value (true / false when all readings agree with quotations found,
  otherwise open) differs from the value in the same story's baseline document in the same stored run, although no
  reading's quotation for the condition lies in the variant's differing sentence (the sentence found by comparing the two
  texts word by word);
- flagged: admitted true in at least half of the baseline-document runs of the model, or some reading true in at least
  three quarters of them.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path[:0] = [str(TMIS / "harness"), str(TMIS / "harness" / "v2"), str(TMIS / "harness" / "product")]
import common  # noqa: E402
import convert_theft as ct  # noqa: E402
import load_reviewed  # noqa: E402
from theft_data import doc_ids  # noqa: E402

TESTED_TREE = "030480203f7d10b364e4ecc34e0c0b544c4038e107f489bc2080aba6b349ab4d"  # 6a72159c, analysis/study3_spec.json
WORKFLOW_SHA = "a0c53a812920f4c7be60029c620a8c112857bfc9c9656bc92a745170357a2ded"
RULES = TMIS / "rule_review" / "final" / "reviewed_rules.json"
PASSAGES = TMIS / "rule_review" / "bundle" / "passages.json"
WORKFLOW = TMIS / "harness" / "product" / "workflows" / "theft-reviewed" / "household_theft.json"
CACHE = TMIS / "runs" / "product" / "cache"
SOURCES = [  # (model, label, stored runs file, runs, manifest or None for the study3 confirm runs)
    ("gpt-6.1-terra", "study3 confirm, checklist only", "runs/study3/confirm/plans_theft_casepath_checklist_frontier.json", 1, None),
    ("gpt-6-luna", "study3 confirm, full", "runs/study3/confirm/plans_theft_casepath.json", 3, None),
    ("gpt-6-luna", "study3 confirm, checklist only", "runs/study3/confirm/plans_theft_casepath_checklist.json", 3, None),
    ("gpt-6-luna", "development e-check", "runs/product/plans_theft_gpt-6-luna_fresh_e-check.json", 3, "runs/product/manifest_theft_gpt-6-luna_fresh_e-check.json"),
    ("gpt-6-luna", "development e-full-s4", "runs/product/plans_theft_gpt-6-luna_fresh_e-full-s4.json", 1, "runs/product/manifest_theft_gpt-6-luna_fresh_e-full-s4.json"),
    ("gpt-6-luna", "development e67-check", "runs/product/plans_theft_gpt-6-luna_fresh_e67-check.json", 3, "runs/product/manifest_theft_gpt-6-luna_fresh_e67-check.json"),
]
EXCLUDED = ["runs/product/plans_theft_gpt-6.1-terra_fresh_t1-check.json (frontier, stories 4-7: another product commit)",
            "every other runs/product/plans_theft_gpt-6-luna_fresh_*.json (other product commits)"]


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def texts():
    out = {}
    for which in ("fresh", "fresh2"):
        for t, v in common.data("theft", which).texts().items():
            out[t] = {"story": v["story"], "kind": v["kind"], "text": v["text"]}
    return out


def readings(entry, n_facts):
    """[(cache key of the reading, {condition: (verdict, quote)})] in call order; a short conditions answer right after a
    reading is its requote retry and replaces those answers."""
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
        except Exception:  # noqa: BLE001
            continue
        rows = content.get("conditions") if isinstance(content, dict) else None
        if not rows or not any(str(r.get("id", "")).startswith("g") for r in rows):
            continue
        ans = {}
        for r in rows:
            ans.setdefault(r["id"], (r.get("verdict"), r.get("quote") or ""))
        if len(ans) >= 0.8 * n_facts or not out:
            out.append([k, ans])
        else:
            out[-1][0] += "+" + k
            out[-1][1].update(ans)
    return [(k, a) for k, a in out]


def value(rds, cid, text):
    """true / false when every reading gives it with a quotation found in the text; otherwise open."""
    vs = [a.get(cid) for _, a in rds]
    if len(vs) < 3 or not vs:
        return "open"
    t = norm(text)
    for v in ("true", "false"):
        if all(x and x[0] == v and x[1] and norm(x[1]) in t for x in vs):
            return v
    return "open"


def changed_span(off, var):
    """The words of the variant that differ from the baseline document (normalised text)."""
    a, b = norm(off).split(), norm(var).split()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    words = [w for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal" for w in b[j1:j2]]
    return " ".join(words)


def about(quote, span):
    """A quotation lies in the differing sentence when they share a run of four words (or the quotation is inside it)."""
    q, s = norm(quote).split(), span.split()
    if not q or not s:
        return False
    if " ".join(q) in " ".join(s):
        return True
    grams = {tuple(s[i:i + 4]) for i in range(len(s) - 3)}
    return any(tuple(q[i:i + 4]) in grams for i in range(len(q) - 3))


def rule_index():
    """condition fact id -> rules using it, with their evidence (routes, the route fixed in the workflow) and cited passages."""
    rules = json.loads(RULES.read_text())["rules"]
    P = {p["id"]: p for p in json.loads(PASSAGES.read_text())["passages"]}
    ids = doc_ids()
    out = defaultdict(list)
    for r in sorted(rules, key=lambda x: x["rule_id"]):
        cond = r.get("condition")
        if not cond:
            continue
        fid = ct.fact_id(load_reviewed._guard_id(r["rule_id"], cond))
        caps = [("fact " + f["fact_id"], e) for f in r["facts"] for e in f["evidence"]]
        if r.get("confirming_evidence"):
            caps.append(("confirming evidence", r["confirming_evidence"]))
        evidence = []
        for where, e in caps:
            routes = e.get("routes") or []
            fixed = min(routes, key=ct.route_key) if routes else None
            evidence.append({"item": where, "must_show": e.get("must_show"),
                             "routes": [[f"{ids[d]}: {d}" for d in rt["documents"]] for rt in routes],
                             "route_fixed_in_workflow": [f"{ids[d]}: {d}" for d in fixed["documents"]] if fixed else None})
        cited = list(dict.fromkeys(list(cond.get("cited", [])) + [c for f in r["facts"] for c in f.get("cited", [])]
                                   + [c for _, e in caps for c in e.get("cited", [])]))
        pas = []
        for c in cited:
            base = c.split("#")[0]
            p = P.get(base)
            pas.append({"id": c, "source": "; ".join(p.get("source", [])) if p else None, "text": p["text"] if p else None})
        out[fid].append({"rule_id": r["rule_id"], "title": r.get("title"), "requirement_kind": r.get("requirement_kind"),
                         "condition": cond["text"], "evidence": evidence, "cited_passages": pas})
    return out


def main():
    T = texts()
    wf = json.loads(WORKFLOW.read_text())
    facts = [f for f in wf["facts"] if f["id"] != "claim_type"]
    nf = len(wf["facts"])
    deciding = set()
    for d in wf["documents"]:
        rw = d.get("required_when")
        if rw:
            deciding |= {c["fact"] for c in ([rw] if "fact" in rw else rw["any"])}
    src_info, units = [], []  # units: (model, source, story, run, {text: (reading keys, readings, stored facts)})
    for model, label, path, runs, manifest in SOURCES:
        info = {"model": model, "source": label, "file": path}
        if manifest:
            m = json.loads((TMIS / manifest).read_text())
            info["source_tree_sha256"] = m.get("source_tree_sha256")
            info["workflow_sha256"] = (m.get("workflows") or {}).get("household_theft.json")
            if info["source_tree_sha256"] != TESTED_TREE or info["workflow_sha256"] != WORKFLOW_SHA:
                info["used"] = False
                src_info.append(info)
                continue
        stored = json.loads((TMIS / path).read_text())
        by = defaultdict(dict)
        missing = 0
        for key, e in stored.items():
            _, t, r = key.split("|")
            rds = readings(e, nf)
            if len(rds) != 3:
                missing += 1
                continue
            by[(T[t]["story"], int(r))][t] = (tuple(k for k, _ in rds), rds, ((e.get("product_extra") or {}).get("facts") or {}))
        for (story, r), tx in sorted(by.items()):
            units.append((model, label, story, r, tx))
        info.update(used=True, entries=len(stored), entries_without_three_readings=missing,
                    stories=sorted({s for s, _ in by}), runs=runs)
        src_info.append(info)
    res = {}
    for model in sorted({u[0] for u in units}):
        mu = [u for u in units if u[0] == model]
        seen_off, seen_var = set(), set()
        stat = {f["id"]: {"off_runs": 0, "admitted_true": 0, "some_reading_true": 0, "stored_admitted_true": 0, "quotes": [],
                          "variant_observations": 0, "unstable": 0} for f in facts}
        for _, label, story, r, tx in mu:
            off = f"s{story}-off"
            if off not in tx:
                continue
            okeys, ords, ofacts = tx[off]
            new_off = okeys not in seen_off
            seen_off.add(okeys)
            for f in facts:
                cid = f["id"]
                s = stat[cid]
                if new_off:
                    s["off_runs"] += 1
                    vals = [a.get(cid) for _, a in ords]
                    if value(ords, cid, T[off]["text"]) == "true":
                        s["admitted_true"] += 1
                    if any(v and v[0] == "true" for v in vals):
                        s["some_reading_true"] += 1
                        for v in vals:
                            if v and v[0] == "true" and v[1] and v[1] not in s["quotes"] and len(s["quotes"]) < 3:
                                s["quotes"].append(v[1])
                    x = ofacts.get(cid) or {}
                    s["stored_admitted_true"] += bool(x.get("status") == "established" and x.get("value") is True)
            ov = {f["id"]: value(ords, f["id"], T[off]["text"]) for f in facts}
            for t, (vkeys, vrds, _) in tx.items():
                if t == off or (okeys, vkeys) in seen_var:
                    continue
                seen_var.add((okeys, vkeys))
                span = changed_span(T[off]["text"], T[t]["text"])
                for f in facts:
                    cid = f["id"]
                    if any(a.get(cid) and about(a[cid][1], span) for _, a in vrds):
                        continue  # the variant's differing sentence is what this condition was read from
                    stat[cid]["variant_observations"] += 1
                    stat[cid]["unstable"] += value(vrds, cid, T[t]["text"]) != ov[cid]
        for cid, s in stat.items():
            n = s["off_runs"]
            s["flagged"] = bool(n) and (s["admitted_true"] >= n / 2 or s["some_reading_true"] >= 0.75 * n)
            s["decides_a_document"] = cid in deciding
        res[model] = stat
    ri = rule_index()
    qtext = {f["id"]: f["question"].replace("Does this hold for the claim: ", "") for f in facts}
    out = {"definitions": __doc__, "sources": src_info, "excluded": EXCLUDED, "results": res,
           "flagged": {m: sorted(c for c, s in v.items() if s["flagged"]) for m, v in res.items()},
           "conditions": {c: {"text": qtext[c], "rules": ri.get(c, [])} for c in qtext}}
    (HERE / "rule_lint.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    (HERE / "rule_lint.md").write_text(markdown(out))
    return out


def markdown(o):
    models = list(o["results"])
    L = ["# Theft rule base: conditions that do not distinguish ordinary cases", "",
         "Generated by `analysis/rule_lint.py` from case texts, stored readings and the rule base; no model calls. A branch "
         "condition should mark what distinguishes a case from the ordinary case of its type. The conditions below are read as "
         "true in most of a set of ordinary theft case documents. For each, decide whether it belongs to every theft case (its "
         "documents would then be due in every case) or whether it is broader than its source and needs narrowing.", "",
         "**Counts** (per model; a run is one product run of a document, with three independent readings):", "",
         "- *ordinary runs*: runs of ordinary case documents (identical reading responses counted once);",
         "- *admitted true*: runs in which every reading answered true with a quotation found in the document;",
         "- *some reading true*: runs in which at least one reading answered true;",
         "- *product admitted*: runs in which the product recorded the condition as established true;",
         "- *unstable*: variant documents of the same cases (which differ from the ordinary document in one sentence that "
         "the condition was not read from) in which the condition's value differs from its value in the ordinary document, "
         "out of all such observations.", "",
         "A condition is listed when it is admitted true in at least half of the ordinary runs of a model, or some reading "
         "answers true in at least three quarters of them.", "",
         "Models: " + ", ".join(models) + ". Sources: " + "; ".join(f"{s['model']} {s['source']}" + ("" if s.get("used") else " (not used)")
                                                                    for s in o["sources"]) + ".", ""]
    flagged = sorted(set().union(*[set(v) for v in o["flagged"].values()]))
    for c in flagged:
        cond = o["conditions"][c]
        L += [f"## {c}", "", f"**Condition:** {cond['text']}", ""]
        rows = []
        for m in models:
            s = o["results"][m][c]
            rows.append([m, "yes" if s["flagged"] else "no", s["off_runs"], s["admitted_true"], s["some_reading_true"], s["stored_admitted_true"],
                         f"{s['unstable']} of {s['variant_observations']}"])
        L.append("| Model | Listed | Ordinary runs | Admitted true | Some reading true | Product admitted | Unstable |")
        L.append("|---|---|---|---|---|---|---|")
        L += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
        L += ["", "**Quotations given for 'true' in ordinary documents:**", ""]
        for m in models:
            for q in o["results"][m][c]["quotes"]:
                L.append(f"- ({m}) \"{q}\"")
        L += [""]
        for r in cond["rules"]:
            L += [f"**Rule {r['rule_id']}** ({r.get('requirement_kind') or 'kind not stated'}): {r.get('title') or ''}", ""]
            for e in r["evidence"]:
                if e["routes"]:
                    alt = " | ".join(" + ".join(rt) for rt in e["routes"])
                    L.append(f"- {e['item']}: must show \"{e['must_show']}\"; routes: {alt}; route used by the workflow: "
                             + " + ".join(e["route_fixed_in_workflow"]))
                else:
                    L.append(f"- {e['item']}: must show \"{e['must_show']}\"; no document route")
            L += ["", "Cited passages:", ""]
            for p in r["cited_passages"]:
                L.append(f"- `{p['id']}` ({p['source'] or 'source not in the passage file'}): \"{p['text'] or 'text not in the passage file'}\"")
            L.append("")
    L += ["## Appendix: conditions not listed", "",
          "| Condition | " + " | ".join(f"{m}: ordinary runs / admitted true / some reading true / unstable" for m in models) + " |",
          "|---|" + "---|" * len(models)]
    for c in sorted(o["conditions"]):
        if c in flagged:
            continue
        L.append(f"| {c} | " + " | ".join(f"{o['results'][m][c]['off_runs']} / {o['results'][m][c]['admitted_true']} / "
                                         f"{o['results'][m][c]['some_reading_true']} / {o['results'][m][c]['unstable']} of "
                                         f"{o['results'][m][c]['variant_observations']}" for m in models) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    o = main()
    print({m: len(v) for m, v in o["flagged"].items()})

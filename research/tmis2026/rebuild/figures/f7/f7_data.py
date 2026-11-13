"""Figure 7 data: error against cost per file, and the same file run again. No model calls.

    python3 -I f7_data.py      # writes f7_data.json

Regime: Study 3's 96 sealed tenancy claims (fresh2, confirm). Error = all deviations per claim-run
(study3 tenancy_rows all_dev; needless holds count).
Cost per file (USD per case-run), from ledgers:
- Study 3 designs: the registered cost_per_case_run in analysis/study3_results_fresh2_confirm.json (study3.py: the
  product's stored call keys joined to the ledger whoever paid them, so a cached call costs what the ledger recorded
  when it was first paid; other designs: matching ledger rows of the cases, each distinct key once, times the spec's
  multiplier, over cases x runs).
- Fair-prompt designs: study4/baseline_check/runs/ledger_<model>.jsonl, rows tagged data fresh2, method A or B and a
  tenancy claim id; each distinct key once; over 96 claims x runs.
Budget curves (post hoc, analysis/study3_feedback.json F4): Self-consistency with m = 1..15 samples (stored samples
regrouped, cost = m x cost per sample) and CasePath checklist-only with k = 1..3 readings (stored readings recombined).
Repeat runs: designs with three stored runs per claim. A checklist = one line per document (union of the reference's
documents and those the plan names): request / hold / neither; a handed-over claim adds one line "handed over".
Identical in all three runs = every line equal in runs 0, 1, 2. Lines that differ = mean over claims of the mean over
the three run pairs of the number of differing lines.
"""
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f4"))
import f4_data as F4  # noqa: E402

TMIS = F4.TMIS
RES = "analysis/study3_results_fresh2_confirm.json"
FB = "analysis/study3_feedback.json"
LEDGER = {"cost-efficient": "study4/baseline_check/runs/ledger_gpt-6-luna.jsonl",
          "frontier": "study4/baseline_check/runs/ledger_gpt-6.1-terra.jsonl"}
FAIR = {"hold_prompt": ("A", "cost-efficient"), "hold_prompt_frontier": ("A", "frontier"),
        "mer_hold_frontier": ("B", "frontier")}
# Figure 4's order, then the product's full scope (registered design)
DESIGNS = F4.DESIGNS + [("casepath", "CasePath, full", "cost-efficient", "the product, full scope")]


def sha(rel):
    return hashlib.sha256((TMIS / rel).read_bytes()).hexdigest()


def lines(plan, docs):
    plan = plan or {"requests": [], "holds": []}
    P, H = set(plan.get("requests", [])), set(plan.get("holds", [])) - set(plan.get("requests", []))
    u = sorted(set(docs) | P | H)
    out = {d: ("request" if d in P else "hold" if d in H else "neither") for d in u}
    out["__handed_over__"] = bool(plan.get("deferred"))
    return out


def diff(a, b):
    keys = set(a) | set(b)
    da = {k: a.get(k, "neither") for k in keys}
    db = {k: b.get(k, "neither") for k in keys}
    da["__handed_over__"], db["__handed_over__"] = a["__handed_over__"], b["__handed_over__"]
    return sum(da[k] != db[k] for k in keys)


def main():
    study = F4.load()
    D = study.D["tenancy"]
    cids = list(study.cases["tenancy"])
    res = json.loads((TMIS / RES).read_text())
    fb = json.loads((TMIS / FB).read_text())
    led = {m: [json.loads(l) for l in (TMIS / p).read_text().splitlines() if l.strip()] for m, p in LEDGER.items()}
    out = {"figure": "f7", "regime": "tenancy (Study 3 sealed claims)", "error": "all deviations per claim-run",
           "cost": "USD per case-run from ledgers", "designs": []}
    for key, name, model, role in DESIGNS:
        assert study.load(key, "tenancy"), key
        rows = study.tenancy_rows(key)
        runs = study.runs(key, "tenancy")
        err = sum(r["all_dev"] for r in rows) / len(rows)
        if key in FAIR:
            method, m = FAIR[key]
            seen, usd = set(), 0.0
            for x in led[m]:
                t = x["tag"]
                if t.get("data") == "fresh2" and t.get("method") == method and t.get("case") in set(cids) and x["key"] not in seen:
                    seen.add(x["key"])
                    usd += float(x.get("cost") or 0)
            cost = usd / (len(cids) * runs)
            src = f"{LEDGER[m]} (method {method}, {len(seen)} distinct calls)"
        else:
            rec = res["designs"][key]["regimes"]["tenancy"]
            cost = rec["cost"]["cost_per_case_run"]
            src = f"{RES} designs.{key}.regimes.tenancy.cost (method {rec['cost'].get('method')})"
            assert abs(rec["measures"]["all_deviations_per_claim"] - err) < 1e-9, key
        d = {"key": key, "name": name, "model": model, "role": role, "runs": runs, "claim_runs": len(rows),
             "all_dev_per_file": err, "usd_per_file": cost, "cost_source": src}
        if runs == 3:
            same, dl, flags = 0, [], []
            for c in sorted(cids):
                docs = list(D.reference(c)["document_states"])
                L = [lines(p, docs) for p in study.plans[(key, "tenancy")][c]]
                pair = [diff(a, b) for a, b in combinations(L, 2)]
                same += all(x == 0 for x in pair)
                flags.append(all(x == 0 for x in pair))
                dl.append(sum(pair) / len(pair))
            d["repeat"] = {"runs": 3, "claims": len(cids), "identical_all_runs": same,
                           "identical_share": same / len(cids), "mean_lines_differing_per_pair": sum(dl) / len(dl),
                           "checklist_lines_per_claim": sum(len(D.reference(c)["document_states"]) for c in cids) / len(cids) + 1}
            d["repeat"]["identical_by_claim_id_order"] = flags
            d["repeat"]["share_lines_differing_per_pair"] = d["repeat"]["mean_lines_differing_per_pair"] / d["repeat"]["checklist_lines_per_claim"]
        out["designs"].append(d)
    # strips construction: per design, the claim at the design's median number of differing lines (mean over the three
    # run pairs; ties: first claim id), with its three stored checklists in the reference's document order.
    out["strips"] = {}
    for key in ("casepath_checklist", "hold_prompt"):
        per = []
        for c in sorted(cids):
            docs = list(D.reference(c)["document_states"])
            L = [lines(p, docs) for p in study.plans[(key, "tenancy")][c]]
            per.append((sum(diff(a, b) for a, b in combinations(L, 2)) / 3, c, L, docs))
        vals = sorted(v for v, *_ in per)
        med = (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        v, c, L, docs = min(per, key=lambda t: (abs(t[0] - med), t[1]))
        ref = D.reference(c)["document_states"]
        out["strips"][key] = {"rule": "claim whose mean differing lines over the three run pairs is closest to the design's "
                                      "median (ties: first claim id)", "median": med, "claim": c, "mean_differing": v,
                              "documents": docs, "reference": [ref[d] for d in docs],
                              "runs": [[L[r][d] for d in docs] for r in range(3)],
                              "handed_over": [L[r]["__handed_over__"] for r in range(3)],
                              "distribution": dict(sorted({str(x): vals.count(x) for x in set(vals)}.items()))}
    sc = fb["F4"]["self_consistency"]["tenancy"]["by_m"]
    rd = fb["F4"]["readings"]["tenancy"]["by_k"]
    out["budget_self_consistency"] = [{"m": int(m), "usd_per_file": v["cost_per_case_run"], "all_dev_per_file": v["all_deviations_per_claim"],
                                       "votes_per_case": v["votes_per_case"]} for m, v in sorted(sc.items(), key=lambda kv: int(kv[0]))]
    out["readings_casepath_checklist"] = [{"k": int(k), "usd_per_file": v["cost_per_case_run"], "all_dev_per_file": v["all_deviations_per_claim"]}
                                          for k, v in sorted(rd.items(), key=lambda kv: int(kv[0]))]
    out["not_yet_measured"] = "ten runs of the same file (Study 4); here three"
    out["inputs"] = dict(sorted(study.inputs.hashes.items()))
    for rel in [RES, FB, *LEDGER.values()]:
        out["inputs"][rel] = sha(rel)
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (HERE / "f7_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for d in out["designs"]:
        r = d.get("repeat")
        print(f"{d['name'][:26]:26s} {d['model'][:5]} err {d['all_dev_per_file']:.3f} usd {d['usd_per_file']:.5f}"
              + (f" | identical {r['identical_all_runs']}/96 ({r['identical_share']:.2f}) lines diff {r['mean_lines_differing_per_pair']:.3f}" if r else ""))
    print([(x["m"], round(x["usd_per_file"], 5), round(x["all_dev_per_file"], 3)) for x in out["budget_self_consistency"]])
    print(out["readings_casepath_checklist"])


if __name__ == "__main__":
    main()

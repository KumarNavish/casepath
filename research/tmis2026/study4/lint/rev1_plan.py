"""Write REV1_PLAN.json: which files the part-C re-run reads, in priority order, fixed before any rev1 call.
DEVELOPMENT, not a result. No model calls. python3 -I -B study4/lint/rev1_plan.py"""
import json, random, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyse as A  # noqa: E402

D = json.loads((HERE / "DIAGNOSIS.json").read_text())
SEED = 20261112
plan, seen = {}, set()


def add(group, regime, ids, why):
    ids = [i for i in ids if (regime, i) not in seen]
    for i in ids:
        seen.add((regime, i))
    plan.setdefault(regime, []).append({"group": group, "why": why, "files": ids})


spent = 0.0
for p in (HERE / "runs").glob("ledger_dev_*.jsonl"):
    spent += sum(float(json.loads(l).get("usd") or 0) for l in p.read_text().splitlines() if l.strip())
per_file = {}
for r in A.REGIMES:
    rows = [json.loads(l) for l in (HERE / "runs" / "ledger_dev_gpt-6-luna.jsonl").read_text().splitlines() if l.strip()]
    usd = sum(float(x["usd"]) for x in rows if x.get("arm") == f"LINT-clean-{r}")
    per_file[r] = usd / len({x["case"] for x in rows if x.get("arm") == f"LINT-clean-{r}"})
for r in A.REGIMES:
    F = A.files(r)
    rt = D["routing"][r]
    add("P1", r, [x["file"] for x in rt if not x.get("denied_event") and (x.get("judgment") or {}).get("owner") == "rule wording"],
        "non-denied routing failures attributed to routing wording (the fix's target)")
    add("P2", r, [f for f, x in F.items() if x["meta"]["denied_event"]], "every denied-event file (the routing fix must not route a denied file into a plan, and should keep the other-type denials where the rule text puts them)")
    facts = {"tenancy": [("lease_termination_dispute", "asserted_claims")], "dismissal": [("wrongful_termination", "retaliation_for_claims")],
             "theft": [("theft_at_home", "household_perpetrator"), ("theft_at_home", "measures_pending"), ("simple_theft_away", "measures_pending")]}[r]
    ids = []
    for f, x in F.items():
        for t, fact in facts:
            st = x["design"]["facts"].get(fact)
            if x["design"]["type"] != t:
                continue
            if st == "stated_true":
                ids.append(f)
            elif fact == "household_perpetrator" and st == "not_mentioned":
                # only where a clean-arm reading answered open (the case the not_this addition is about)
                e = A.results("clean", r)[f]
                wf = A.workflows(r, "clean")[t]
                if any(a.get(fact, (None,))[0] == "open" for _, a in A.readings(e, {q["id"] for q in wf["facts"]})):
                    ids.append(f)
    add("P3", r, ids, "files of the changed fact wordings: motive facts stated true; theft household_perpetrator stated true, or not mentioned with an open reading in the clean arm; measures_pending stated true")
    rnd = random.Random(f"{SEED}-{r}")
    ok = sorted(f for f, x in F.items() if not x["meta"]["denied_event"] and D and f not in {y for _, y in seen})
    errfree = [f for f in ok if not any(e["file"] == f for e in D["errors"])]
    add("P4", r, rnd.sample(errfree, 5), "seeded control sample (seed 20261112-<regime>) of five error-free non-denied files: regressions")
    add("P5", r, sorted(f for f in ok if any(e["file"] == f for e in D["errors"])), "remaining files with clean-arm errors (product-owned causes), if the budget allows")
est = {r: round(per_file[r], 5) for r in A.REGIMES}
order = []
for g in ("P1", "P2", "P3", "P4", "P5"):
    for r in A.REGIMES:
        for b in plan[r]:
            if b["group"] == g:
                order.append({"group": g, "regime": r, "files": b["files"], "n": len(b["files"]),
                              "estimate_usd_all_calls_new": round(len(b["files"]) * per_file[r], 4)})
cum = 0
for o in order:
    cum += o["estimate_usd_all_calls_new"]
    o["cumulative_estimate"] = round(cum, 4)
out = {"label": "DEVELOPMENT, post hoc, not a result. Written before any rev1 call.", "ledger_total_before_usd": round(spent, 6),
       "budget": "USD 0.50 for part C; no file is launched once the ledger total reaches before + 0.40",
       "stop_usd": round(spent + 0.40, 6), "usd_per_file_clean_arm_all_calls_new": est,
       "cache_note": "Every reading request and the routing request carry the routing question and, for the changed types, the changed fact wording, so they are new; document-finder conversations open with the workflow reference (id, version, title) and continue on tool results, so only some of their turns can be answered from the cache. The estimate counts every call as new (upper bound); the pilot below measures the real share.",
       "plan": plan, "order": order}
(HERE / "REV1_PLAN.json").write_text(json.dumps(out, indent=1) + "\n")
for o in order:
    print(o["group"], o["regime"], o["n"], o["estimate_usd_all_calls_new"], o["cumulative_estimate"])
print("stop_usd", out["stop_usd"])

"""Pre-specified primary contrasts H1-H5 per model, with Holm correction."""
import itertools, json, sys
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from analyze import signflip_p, jaccard
from tenancy_data import claim_ids, reference
from theft_data import texts

def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [0.0] * len(ps); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i])); adj[i] = run
    return adj

def retest_by_cluster(P, method, field, cases, cluster):
    by = defaultdict(list)
    for c in cases:
        plans = [(P.get(f"{method}|{c}|{r}") or {}).get(field) for r in range(3)]
        plans = [p for p in plans if p]
        if len(plans) >= 2:
            by[cluster(c)].append(sum(jaccard(a["requests"], b["requests"]) for a, b in itertools.combinations(plans, 2)) / 3)
    return {k: sum(v) / len(v) for k, v in by.items()}

out = {}
for tag in ("gpt-6.1-terra", "gpt-6-luna"):
    res = json.loads((HERE / f"results_{tag}.json").read_text())
    ten, th = res["tenancy"]["_contrasts"], res["theft"]["_contrasts"]
    pick = lambda lst, a, b, key, val: next(c for c in lst if c["a"] == a and c["b"] == b and c.get(key) == val)
    tests = [("H1 unsafe errors, CP-exact vs B1", pick(ten, "CP-exact", "B1", "metric", "unsafe")["p_signflip"]),
             ("H2 deferrals, CP vs B1", pick(ten, "CP-kleene", "B1", "metric", "deferred")["p_signflip"]),
             ("H3 wrong changes, CP vs R", pick(th, "CP", "R", "kind", "on")["p_signflip"]),
             ("H4 premature or changed, CP vs R", pick(th, "CP", "R", "kind", "unresolved")["p_signflip"])]
    PT = json.loads((HERE.parent / "runs" / f"plans_tenancy_{tag}.json").read_text())
    fam = {c: reference(c)["family_id"] for c in claim_ids("test")}
    a = retest_by_cluster(PT, "CP", "plan_exact", claim_ids("test"), fam.get)
    b = retest_by_cluster(PT, "B1", "plan", claim_ids("test"), fam.get)
    diffs = [a[k] - b[k] for k in sorted(set(a) & set(b))]
    tests.append(("H5 test-retest, CP-exact vs B1", signflip_p(diffs)))
    adj = holm([p for _, p in tests])
    out[tag] = [{"test": n, "p": p, "p_holm": q, **({"retest_diff": sum(diffs) / len(diffs)} if n.startswith("H5") else {})}
                for (n, p), q in zip(tests, adj)]
(HERE / "primary_tests.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

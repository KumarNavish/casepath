"""Tests of analysis/study2.py on oracle, perturbed and synthetic plans (no design output, no model calls).

python3 test_study2.py   -> prints each check and exits non-zero on failure.
"""
import random
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study2 as s2  # noqa: E402
import tenancy_fresh as D  # noqa: E402  (study2 puts fresh/ on the path)
import theft_fresh as TH  # noqa: E402

fails = 0


def check(name, cond, detail=""):
    global fails
    fails += not cond
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


# ----------------------------------------------------------------- oracle plans
def oracle_ten(ref):
    st = ref["document_states"]
    return {"requests": sorted(d for d, s in st.items() if s in s2.REQ_NOW),
            "holds": sorted(d for d, s in st.items() if s == "held"), "deferred": False}


ten = {c: [oracle_ten(D.reference(c))] * 3 for c in D.claim_ids("test")}
rows = s2.tenancy_rows(D, ten)
summ = s2.ten_summary(rows)
check("tenancy oracle: zero strict unsafe errors", sum(r["strict_unsafe"] for r in rows) == 0, f"{summ['strict_unsafe_per_claim']}")
check("tenancy oracle: requested share 1", summ["requested_share"] == 1.0)
check("tenancy oracle: correct-hold share 1 (18 open-fact claims)", summ["correct_hold_share"] == 1.0, f"held docs {summ['ref_held']}")
check("tenancy oracle: no spurious holds, no handoffs", summ["spurious_hold"] == 0 and summ["handoffs"] == 0)

pairs = TH.pairs()
T = TH.texts()


def oracle_theft():
    plans = {t: [{"requests": [], "holds": []}] * 3 for t in T}
    for p in pairs:
        opts = p["reference"]["acceptable_signed_deltas"]
        if p["kind"] == "on":
            plans[p["variant"]] = [{"requests": sorted(d.lstrip("+") for d in opts[0]), "holds": []}] * 3
        else:
            plans[p["variant"]] = [{"requests": [], "holds": sorted({d.lstrip("+") for o in opts for d in o})}] * 3
    return plans


th = oracle_theft()
on = s2.theft_rows(T, [p for p in pairs if p["kind"] == "on"], th)
un = s2.theft_rows(T, [p for p in pairs if p["kind"] == "unresolved"], th)
ts = s2.theft_summary(on, un)
check("theft oracle: zero wrong and missed changes", ts["wrong"] == 0 and ts["missed"] == 0, f"pair runs {ts['pair_runs']}")
check("theft oracle: F1 = 1", ts["f1"] == 1.0)
check("theft oracle: no premature request, no change on open facts",
      ts["unresolved"]["premature_rate"] == 0 and ts["unresolved"]["other_changes_per_pair"] == 0, f"{ts['unresolved']}")

# ----------------------------------------------------------------- perturbations (one claim with an open fact and an attachment)
cid = next(c for c in D.claim_ids("test") if D.reference(c)["held_set"] and
           any(s == "supplied_sufficient" for s in D.reference(c)["document_states"].values())) \
    if any(D.reference(c)["held_set"] and "supplied_sufficient" in D.reference(c)["document_states"].values() for c in D.claim_ids("test")) \
    else next(c for c in D.claim_ids("test") if D.reference(c)["held_set"])
ref = D.reference(cid)
base = s2.ten_row(ref, oracle_ten(ref))
UNSAFE = ("unnecessary", "missed", "handed", "premature", "silent_skip")


def delta(plan):
    r = s2.ten_row(ref, plan)
    return {k: r[k] - base[k] for k in s2.TEN_COUNTS + ("strict_unsafe",) if r[k] != base[k]}


not_needed = next(d for d, s in ref["document_states"].items() if s == "not_needed")
required = next(d for d, s in ref["document_states"].items() if s == "required_now")
held = ref["held_set"][0]
p = oracle_ten(ref); p["requests"] = p["requests"] + [not_needed]
d = delta(p); check("request one not-needed document -> unnecessary +1 only", d == {"unnecessary": 1, "strict_unsafe": 1}, d)
p = oracle_ten(ref); p["requests"] = [x for x in p["requests"] if x != required]
d = delta(p); check("skip one required document -> missed +1 (requested -1)", d == {"missed": 1, "requested": -1, "strict_unsafe": 1}, d)
p = oracle_ten(ref); p["requests"] = p["requests"] + [held]; p["holds"] = [x for x in p["holds"] if x != held]
d = delta(p); check("request a reference-held document -> premature +1 (correct hold -1)",
                    d == {"premature": 1, "correct_hold": -1, "strict_unsafe": 1}, d)
p = oracle_ten(ref); p["holds"] = [x for x in p["holds"] if x != held]
d = delta(p); check("drop a reference-held document -> silent skip +1 (correct hold -1)",
                    d == {"silent_skip": 1, "correct_hold": -1, "strict_unsafe": 1}, d)
n_req = len([x for x, s in ref["document_states"].items() if s in s2.REQ_NOW])
d = delta({"requests": [], "holds": [], "deferred": True})
check("hand over the claim -> handed = required-now documents; held documents handed, not skipped",
      d.get("handed") == n_req and d.get("handed_held") == len(ref["held_set"]) and "missed" not in d and "silent_skip" not in d
      and d.get("strict_unsafe") == n_req, d)
d = delta(None)
check("empty (failed) plan -> missed = required-now, silent skips = held",
      d.get("missed") == n_req and d.get("silent_skip") == len(ref["held_set"]) and d.get("strict_unsafe") == n_req + len(ref["held_set"])
      and "unnecessary" not in d and "handed" not in d, d)
p = oracle_ten(ref); p["holds"] = p["holds"] + [not_needed]
d = delta(p); check("hold a not-needed document -> spurious hold +1, not unsafe", d == {"spurious_hold": 1}, d)
p = oracle_ten(ref); p["requests"] = p["requests"] + ["not_a_family_document"]
d = delta(p); check("request a document outside the reference set -> unnecessary +1", d == {"unnecessary": 1, "strict_unsafe": 1}, d)

# theft perturbation: a wrong addition in one on-pair and a missed change in another
p_on = [p for p in pairs if p["kind"] == "on"]
th2 = deepcopy(th)
th2[p_on[0]["variant"]] = [{"requests": th[p_on[0]["variant"]][0]["requests"] + ["Extra document"], "holds": []}] * 3
th2[p_on[1]["variant"]] = [{"requests": [], "holds": []}] * 3
on2 = s2.theft_rows(T, p_on, th2)
check("theft: one added document -> wrong +1 per run; one omitted change -> missed per run",
      sum(r["wrong"] for r in on2) == 3 and sum(r["missed"] for r in on2) == 3 * len(p_on[1]["reference"]["acceptable_signed_deltas"][0]),
      f"wrong {sum(r['wrong'] for r in on2)} missed {sum(r['missed'] for r in on2)}")
# repeated off-case error: an extra document in one story's off plan becomes a wrong withdrawal in all 9 pairs
th3 = deepcopy(th)
off4 = next(t for t in T if t == "s4-off")
th3[off4] = [{"requests": ["Extra off document"], "holds": []}] * 3
on3 = s2.theft_rows(T, p_on, th3)
s2.dedup_errors(on3)
check("dedup sensitivity: one off-plan error repeated over 9 pairs counts 9 times raw, once per run deduplicated",
      sum(r["errors"] for r in on3) == 27 and abs(sum(r["errors_dedup"] for r in on3) - 3) < 1e-9)

# ----------------------------------------------------------------- contrast machinery
rng = random.Random(1)
b = {f"c{i}": rng.uniform(0.5, 1.5) for i in range(18)}
a = {k: v + 0.30 + rng.uniform(-0.05, 0.05) for k, v in b.items()}
c = s2.contrast(a, b, "test|shift")
check("known positive difference recovered", c["diff"] > 0.25 and c["diff_ci"][0] > 0 and c["favours"] == "b"
      and abs(c["p_signflip"] - 2 / 2 ** 18) < 1e-12, f"diff {c['diff']:.3f} ci {c['diff_ci']} p {c['p_signflip']}")
c = s2.contrast(b, a, "test|shift-neg")
check("sign flips when the sides are swapped", c["diff"] < -0.25 and c["favours"] == "a")
nine = {f"f{i}": 1.0 for i in range(9)}
check("smallest attainable p with 9 clusters = 2/512", abs(s2.contrast({k: 2.0 for k in nine}, nine, "t")["min_p_signflip"] - 2 / 512) < 1e-12)
for gap, want in ((0.0, "1.0"), (-0.06, "0"), (0.06, "1.0")):
    a2 = {k: v + 0.25 + gap for k, v in nine.items()}
    c = s2.contrast(a2, nine, f"test|ni{gap}", margin=0.25)
    ok = c["p_noninferiority"] == float(want)
    check(f"non-inferiority p at difference = margin {gap:+.2f}: p = {want}", ok, f"p {c['p_noninferiority']}")
noisy = {k: v + 0.25 + (0.2 if i % 2 else -0.2) for i, (k, v) in enumerate(sorted(b.items()))}
c = s2.contrast(noisy, b, "test|ni-noisy", margin=0.25)
check("non-inferiority p near 0.5 when the mean difference sits on the margin", 0.3 < c["p_noninferiority"] < 0.7, f"p {c['p_noninferiority']}")
a3 = {k: v - 0.10 for k, v in b.items()}
c = s2.contrast(a3, b, "test|ni-higher", higher_is_better=True, margin=0.05)
check("higher-is-better non-inferiority: 10 points worse than a 5-point margin -> p = 1", c["p_noninferiority"] == 1.0)
check("Holm adjustment", [round(x, 6) for x in s2.holm([0.01, 0.04, 0.03, 0.5])] == [0.04, 0.09, 0.09, 0.5])

# ----------------------------------------------------------------- end to end on synthetic systems
ten_bad = {cid_: [dict(p_, requests=p_["requests"] + ["not_a_family_document"]) for p_ in v] for cid_, v in ten.items()}
plans = {("tenancy", "gpt-6-luna"): {"CPv2p": ten, "B1v2p": ten_bad}, ("tenancy", "gpt-6.1-terra"): {"B1v2p": ten_bad},
         ("theft", "gpt-6-luna"): {"CPv2p": th, "Rv2p": th2}, ("theft", "gpt-6.1-terra"): {"R": th2}}
res = s2.analyse(plans, D, TH, {}, [], {})
pc = res["contrasts"]
check("end to end: four primary contrasts with Holm", set(pc) == {"A", "B", "C", "D"} and all("p_holm" in v for v in pc.values()))
check("end to end: B difference = -1 strict unsafe error per claim", abs(pc["B"]["diff"] + 1) < 1e-12 and pc["B"]["clusters"] == 18,
      f"{pc['B']['diff']}")
check("end to end: D non-inferiority p = 0 (v2 better by 1 per claim)", pc["D"]["p_noninferiority"] == 0.0)
check("end to end: A favours CasePath, C non-inferior", pc["A"]["favours"] == "a" and pc["C"]["p_noninferiority"] == 0.0,
      f"A diff {pc['A']['diff']:.3f}")
print("ALL STUDY2 TESTS PASSED" if not fails else f"{fails} FAILED")
if __name__ == "__main__":
    sys.exit(1 if fails else 0)

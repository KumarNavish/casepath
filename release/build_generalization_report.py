"""Emit MODEL_GENERALIZATION_RESULT.md and FINAL_PARETO_ANALYSIS.md from whichever actor runs are complete."""
import sys, json, random, collections
sys.path.insert(0, ".")
from pathlib import Path
from statistics import fmean
from casepath_api.arena_v1.analyze import load, family_means, paired

R = Path("/Users/kumar0002/Documents/ChatGPT/CasePath Agentic Acceptance 20260915d/casepath/research/ctes")
ACTORS = [("economical", "openai/gpt-5.4-mini", "arena_v1_data_submission/run_mini"),
          ("strong, same provider", "openai/gpt-5.6-terra", "arena_v1_data_submission/run_terra"),
          ("strong, different provider", "anthropic/claude-sonnet-5", "arena_v1_data_submission/run_sonnet")]
ARMS = ["ctes", "ctes-abl-satisfaction", "full-artifact-gate", "full", "direct-end-to-end", "constant"]


def bp(a, b, seed=20260914, n=5000):
    f = sorted(set(a) & set(b)); d = [a[x] - b[x] for x in f]
    if not d: return 1.0
    rng = random.Random(seed)
    bs = [fmean([d[rng.randrange(len(d))] for _ in d]) for _ in range(n)]
    below = sum(x <= 0 for x in bs) / n
    return round(min(1.0, 2 * min(below, 1 - below)), 4)


def turn_table(res, arms):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in res["records"]:
        by[r["arm"]][r["turn"]].append(r["metrics"].get("state_accuracy") or 0.0)
    return {a: [round(fmean(by[a][t]), 3) if t in by[a] else None for t in (0, 1, 2)] for a in arms if a in by}


rows, pareto_rows, missing = [], [], []
for label, model, path in ACTORS:
    p = Path(path) / "RESULT.json"
    if not p.exists():
        missing.append(f"{label} ({model})"); continue
    L = load(Path(path)); pe, fam = L["per_episode"], L["family"]
    res = json.loads(p.read_text())
    a = family_means(pe["ctes"], fam, "state_acc"); b = family_means(pe["full-artifact-gate"], fam, "state_acc")
    r = paired(a, b)
    ra = family_means(pe["ctes"], fam, "readiness_acc"); rb = family_means(pe["full-artifact-gate"], fam, "readiness_acc")
    rr = paired(ra, rb)
    tt = turn_table(res, ARMS)
    rows.append({"label": label, "model": model,
                 "s1": {"mean": round(r["mean_diff"], 4), "ci": [round(x, 4) for x in r["ci95"]],
                        "w": r["wins"], "l": r["losses"], "p": bp(a, b)},
                 "readiness": {"mean": round(rr["mean_diff"], 4), "ci": [round(x, 4) for x in rr["ci95"]],
                               "w": rr["wins"], "l": rr["losses"], "p": bp(ra, rb)},
                 "hearsay": {"full": int(sum(m["hearsay"] for m in pe["full"].values())),
                             "gated": int(sum(m["hearsay"] for m in pe["full-artifact-gate"].values()))},
                 "premature": {"ctes": int(sum(m["P"] for m in pe["ctes"].values())),
                               "abl": int(sum(m["P"] for m in pe.get("ctes-abl-satisfaction", {}).values()))},
                 "turns": tt,
                 "arms": {arm: {"state": round(fmean(family_means(pe[arm], fam, "state_acc").values()), 3),
                                "final_turn_state": tt.get(arm, [None, None, None])[2],
                                "premature": int(sum(m["P"] for m in pe[arm].values())),
                                "requests": int(sum(m["requests"] for m in pe[arm].values()))}
                          for arm in ARMS if arm in pe}})
json.dump({"actors": rows, "missing": missing}, open("/tmp/generalization.json", "w"), indent=1)
print(json.dumps({"complete": [r["model"] for r in rows], "missing": missing}, indent=1))
for r in rows:
    print(f"\n{r['model']}  S1 state acc {r['s1']['mean']:+.4f} {r['s1']['ci']} {r['s1']['w']}/{r['s1']['l']} p={r['s1']['p']}")
    print(f"   readiness {r['readiness']['mean']:+.4f} {r['readiness']['ci']}   hearsay full={r['hearsay']['full']} gated={r['hearsay']['gated']}")
    print(f"   final-turn state: " + ", ".join(f"{a}={v[2]}" for a, v in r["turns"].items() if v[2] is not None))

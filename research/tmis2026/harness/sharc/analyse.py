"""Score the ShARC pilot (train-split sample): micro / macro accuracy, confusion matrices, paired differences
CasePath core minus each baseline with a 95% cluster bootstrap over rule snippets, calls and USD per utterance.
Run with python3 -I. Usage: python3 -I analyse.py <sharc_train.json>  -> runs/sharc/summary.json (+ printed tables)"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "runs" / "sharc"
CLASSES = ["Yes", "No", "Irrelevant", "Inquire"]
CP = "cp-v3"
B = 10000


def micro(pairs):
    return sum(g == p for g, p in pairs) / len(pairs)


def macro(pairs):
    per = []
    for c in CLASSES:
        sub = [p for g, p in pairs if g == c]
        if sub:
            per.append(sum(p == c for p in sub) / len(sub))
    return sum(per) / len(per)


def main(path):
    assert Path(path).name == "sharc_train.json"
    sample = json.loads((OUT / "sample_ids.json").read_text())
    ids = sample["order"]
    want = set(ids)
    data = {r["utterance_id"]: r for r in json.loads(Path(path).read_text()) if r["utterance_id"] in want}
    cluster = {u: hashlib.sha256(data[u]["snippet"].encode()).hexdigest()[:12] for u in ids}
    res = {d: json.loads((OUT / f"results_{d}.json").read_text()) for d in [CP, "direct", "steps", "sc3"]}
    gold = {u: res[CP][u]["gold"] for u in ids}
    preds = {"direct": {u: res["direct"][u]["decision"] for u in ids},
             "steps": {u: res["steps"][u]["decision"] for u in ids},
             "sc3": {u: res["sc3"][u]["decision"] for u in ids},
             "cp_core": {u: res[CP][u]["decision"] for u in ids},
             "cp_kleene": {u: res[CP][u]["kleene"] for u in ids},
             "cp_single": {u: res[CP][u]["single"] for u in ids}}
    dev60 = set(sample["dev60"])
    summary = {"n": len(ids), "clusters": len(set(cluster.values())), "trees": len({data[u]["tree_id"] for u in ids}),
               "designs": {}, "paired": {}}
    for d, p in preds.items():
        pairs = [(gold[u], p[u]) for u in ids]
        rest = [(gold[u], p[u]) for u in ids if u not in dev60]
        conf = {g: {c: sum(1 for gg, pp in pairs if gg == g and pp == c) for c in CLASSES + [None]} for g in CLASSES}
        summary["designs"][d] = {"micro": micro(pairs), "macro": macro(pairs), "micro_excl_dev60": micro(rest),
                                 "macro_excl_dev60": macro(rest), "missing": sum(p[u] is None for u in ids),
                                 "confusion_gold_rows": conf}
    # cluster bootstrap of paired differences
    by = defaultdict(list)
    for u in ids:
        by[cluster[u]].append(u)
    keys = sorted(by)
    rng = random.Random(20261110)
    for base in ["direct", "steps", "sc3"]:
        for meas, f in (("micro", micro), ("macro", macro)):
            obs = f([(gold[u], preds["cp_core"][u]) for u in ids]) - f([(gold[u], preds[base][u]) for u in ids])
            boots = []
            for _ in range(B):
                draw = [u for k in (rng.choice(keys) for _ in keys) for u in by[k]]
                boots.append(f([(gold[u], preds["cp_core"][u]) for u in draw]) - f([(gold[u], preds[base][u]) for u in draw]))
            boots.sort()
            summary["paired"][f"cp_core-{base}|{meas}"] = {"diff": obs, "ci95": [boots[int(0.025 * B)], boots[int(0.975 * B) - 1]]}
    # cost: ledger rows tagged exp=sharc-pilot of the final 320-utterance designs
    rows = [json.loads(l) for l in (OUT / "ledger_pilot_gpt-6-luna.jsonl").read_text().splitlines()]
    cost = Counter()
    calls = Counter()
    for r in rows:
        m = r["tag"].get("method", "")
        key = {"direct": "direct", "steps": "steps", "sc3": "sc3_extra"}.get(m)
        if m.startswith("cp-v3-A"):
            key = "cp_A"
        elif m.startswith("cp-v3-B"):
            key = "cp_B"
        elif m.startswith("cp-v"):
            key = "cp_dev_revisions"
        if key:
            cost[key] += r["cost"] or 0
            calls[key] += 1
    n = len(ids)
    summary["cost"] = {
        "total_ledger_usd": sum((r["cost"] or 0) for r in rows), "ledger_rows": len(rows),
        "by_component": {k: {"usd": cost[k], "calls": calls[k]} for k in cost},
        "per_utterance": {
            "direct": {"calls": calls["direct"] / n, "usd": cost["direct"] / n},
            "steps": {"calls": calls["steps"] / n, "usd": cost["steps"] / n},
            "sc3": {"calls": (calls["steps"] + calls["sc3_extra"]) / n, "usd": (cost["steps"] + cost["sc3_extra"]) / n},
            "cp_core": {"calls": (calls["cp_A"] + calls["cp_B"]) / n, "usd": (cost["cp_A"] + cost["cp_B"]) / n,
                        "note": "call A paid once per (snippet, question); calls B1/B2 per utterance"}}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"n={n} snippet clusters={summary['clusters']} trees={summary['trees']}")
    for d, s in summary["designs"].items():
        print(f"{d:10s} micro {s['micro']:.3f} macro {s['macro']:.3f} | excl dev60 micro {s['micro_excl_dev60']:.3f} "
              f"macro {s['macro_excl_dev60']:.3f} missing {s['missing']}")
        for g in CLASSES:
            print("   ", g.ljust(10), [s["confusion_gold_rows"][g][c] for c in CLASSES + [None]])
    for k, v in summary["paired"].items():
        print(f"{k:24s} {v['diff']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
    print(json.dumps(summary["cost"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

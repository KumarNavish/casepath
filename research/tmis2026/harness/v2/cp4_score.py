"""Development comparison for CP4 (no model calls). Usage: python3 cp4_score.py
Writes runs/v2/cp4/scores.json."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import common
import theft_v2
import v3

sys.argv = [sys.argv[0], "gpt-6-luna"]
from theft_data import best_realization  # noqa: E402
from theft_score import delta  # noqa: E402

K = 3
OUT = common.OUT / "cp4"
REV = str(Path(__file__).resolve().parents[2] / "rule_review" / "final" / "reviewed_rules.json")  # was an absolute path
STORIES = {"gpt-6-luna": [0, 1, 2, 4, 5, 6, 7], "gpt-6.1-terra": [4, 5]}
EMPTY = {"requests": [], "holds": []}


def load(p):
    return json.loads(p.read_text()) if p.exists() else {}


def arms(model, data):
    cp4 = load(OUT / f"plans_theft_{model}_{data}_reviewed.json")
    v3p = load(common.OUT / "v3" / f"plans_theft_{model}_{data}_original.json")
    base = load(common.OUT / (f"plans_theft_{model}_original_dev.json" if data == "original" else f"plans_theft_{model}_fresh_heldout.json"))
    return {"CP4-reviewed": lambda t, r: (cp4.get(f"CP4|{t}|{r}") or {}).get("plan"),
            "R-reviewed": lambda t, r: (cp4.get(f"Rpack|{t}|{r}") or {}).get("plan"),
            "CP4-original": lambda t, r: (v3p.get(f"CPv3|{t}|{r}") or {}).get("draft"),
            "R-original": lambda t, r: (base.get(f"R|{t}|{r}") or {}).get("plan")}, cp4, v3p


def errors(pair, off, var):
    pred = delta(set(off["requests"]), set(var["requests"]))
    sel, _ = best_realization(pred, pair["reference"])
    return sorted(set(pred) - set(sel)), sorted(set(sel) - set(pred))


def main():
    res = {}
    for model, stories in STORIES.items():
        res[model] = {}
        rows, holds = defaultdict(list), defaultdict(list)
        for data in ("original", "fresh"):
            D = common.data("theft", data)
            T = D.texts()
            A, _, _ = arms(model, data)
            pairs = [p for p in D.pairs() if p["story"] in stories]
            if not pairs:
                continue
            for name, get in A.items():
                for t in T:
                    if T[t]["story"] in stories:
                        for r in range(K):
                            p = get(t, r)
                            if p is not None:
                                holds[name].append(len(p.get("holds", [])))
                for p in pairs:
                    for r in range(K):
                        off, var = get(p["off"], r), get(p["variant"], r)
                        if off is None and var is None:
                            continue
                        off, var = off or EMPTY, var or EMPTY
                        w, m = errors(p, off, var)
                        on_docs = {d.lstrip("+") for o in p["reference"]["acceptable_signed_deltas"] for d in o}
                        rows[name].append({"kind": p["kind"], "story": p["story"], "run": r, "wrong": w, "missed": m,
                                           "missed_held": [x for x in m if x[1:] in set(var.get("holds", []))],
                                           "stable": not delta(set(off["requests"]), set(var["requests"])),
                                           "premature": bool((set(var["requests"]) - set(off["requests"])) & on_docs)})
        for name, rs in rows.items():
            on = [x for x in rs if x["kind"] == "on"]
            un = [x for x in rs if x["kind"] == "unresolved"]
            once = defaultdict(set)
            for x in on:
                for w in x["wrong"]:
                    once[(x["story"], x["run"])].add(w)
            w, m = sum(len(x["wrong"]) for x in on), sum(len(x["missed"]) for x in on)
            res[model][name] = {"pair_runs": len(on), "wrong": w, "missed": m,
                                "missed_because_held": sum(len(x["missed_held"]) for x in on),
                                "wm_per_pair": round((w + m) / len(on), 3),
                                "wm_per_pair_once": round((sum(len(v) for v in once.values()) + m) / len(on), 3),
                                "unchanged_when_open": round(sum(x["stable"] for x in un) / len(un), 3),
                                "premature_when_open": round(sum(x["premature"] for x in un) / len(un), 3),
                                "held_per_text": round(sum(holds[name]) / max(1, len(holds[name])), 2)}
    res["costs"] = costs()
    res["terra_vs_luna"] = terra_vs_luna()
    res["reviewed_rules_effect"] = reviewed_effect()
    common.dump(OUT / "scores.json", res)
    print(json.dumps(res, indent=1))


def costs():
    out = {}
    for model in STORIES:
        rows = [json.loads(l) for l in (common.OUT / f"ledger_{model}.jsonl").read_text().splitlines()]
        agg = defaultdict(lambda: [0, 0.0])
        for r in rows:
            m = r["tag"].get("method")
            if m in ("CPv3-read", "R", "Rv2p") and r.get("cost") is not None:
                agg[m][0] += 1
                agg[m][1] += float(r["cost"])
        out[model] = {"CP4 per text-run (2 readings)": round(2 * agg["CPv3-read"][1] / max(1, agg["CPv3-read"][0]), 5),
                      "R per text-run": round(agg["R"][1] / max(1, agg["R"][0]), 5),
                      "R-reviewed per text-run": round(agg["Rv2p"][1] / max(1, agg["Rv2p"][0]), 5)}
    return out


def terra_vs_luna():
    """CP4 original pack, stories 4-5: which rules produce the wrong changes, and how the two models' verdicts differ."""
    pack = theft_v2.TheftPack(v3.theft_pack("original"), judge_all=True)
    D = common.data("theft", "fresh")
    pairs = [p for p in D.pairs() if p["story"] in (4, 5) and p["kind"] == "on"]
    out = {}
    judg = {}
    for model in STORIES:
        P = load(common.OUT / "v3" / f"plans_theft_{model}_fresh_original.json")
        judg[model] = {k: v.get("judgments") for k, v in P.items() if v and v.get("judgments")}
        by_rule = Counter()
        true_counts = []
        for p in pairs:
            for r in range(K):
                a, b = P.get(f"CPv3|{p['off']}|{r}"), P.get(f"CPv3|{p['variant']}|{r}")
                if not a or not b or "draft" not in a or "draft" not in b:
                    continue
                w, _ = errors(p, a["draft"], b["draft"])
                for atom in w:
                    doc = atom[1:]
                    src = pack.support(b["judgments"] if atom[0] == "+" else a["judgments"]).get(doc, [])
                    for c, o in src:
                        if c == "true":
                            by_rule[(o["rule"], o["guard"])] += 1
        for k, nu in judg[model].items():
            true_counts.append(sum(v == "true" for v in nu.values()))
        out[model] = {"wrong_change_sources(rule,guard)": [[f"{r}|{g}", n] for (r, g), n in by_rule.most_common(8)],
                      "guards_true_per_text_mean": round(sum(true_counts) / max(1, len(true_counts)), 2)}
    # verdict disagreements between models on the same text and run
    diff = Counter()
    for k in set(judg["gpt-6-luna"]) & set(judg["gpt-6.1-terra"]):
        a, b = judg["gpt-6-luna"][k], judg["gpt-6.1-terra"][k]
        for g in a:
            if a[g] != b.get(g):
                diff[(g, a[g], b.get(g))] += 1
    out["verdict_differences(guard,luna,terra)"] = [[f"{g}|{x}|{y}", n] for (g, x, y), n in diff.most_common(12)]
    out["guard_text"] = {g.split("|")[0]: pack.guards.get(g.split("|")[0]) for g, _ in out["verdict_differences(guard,luna,terra)"][:6]}
    return out


def reviewed_effect():
    """Per changed rule: pair-runs where CP4 reviewed and CP4 original differ in a document the rule routes, and whether
    the difference reduced (right) or increased (wrong) that pair's wrong + missed."""
    import load_reviewed
    orig = v3.theft_pack("original")
    rev = load_reviewed.load(REV)
    def rule_docs(pack):
        req = {r["capability_id"]: r["routes"] for r in pack["requirements"]}
        out = defaultdict(set)
        for b in pack["overlay"]["compiled"]:
            for f in b["facts"]:
                for c in f["capabilities"]:
                    for rt in req.get(c["capability_id"], []):
                        out[b["node_id"]] |= set(rt["document_types"])
        for res in pack["resolvers"]:
            for rt in req.get(res["capability_id"], []):
                out[res["rule_id"]] |= set(rt["document_types"])
        return out
    od, rd = rule_docs(orig), rule_docs(rev)
    g_o = {b["node_id"]: [f.get("guard_id") for f in b["facts"]] for b in orig["overlay"]["compiled"]}
    g_r = {b["node_id"]: [f.get("guard_id") for f in b["facts"]] for b in rev["overlay"]["compiled"]}
    changed = sorted(r for r in rd if r not in od or rd[r] != od[r] or g_r.get(r) != g_o.get(r)
                     or json.dumps([b for b in rev["requirements"] if b["capability_id"].startswith(r + ".")], sort_keys=True)
                     != json.dumps([b for b in orig["requirements"] if b["capability_id"].startswith(r + ".")], sort_keys=True))
    tally = {model: defaultdict(Counter) for model in STORIES}
    for model, stories in STORIES.items():
        for data in ("original", "fresh"):
            D = common.data("theft", data)
            A, _, _ = arms(model, data)
            for p in [p for p in D.pairs() if p["story"] in stories and p["kind"] == "on"]:
                for r in range(K):
                    o1, v1 = A["CP4-original"](p["off"], r), A["CP4-original"](p["variant"], r)
                    o2, v2 = A["CP4-reviewed"](p["off"], r), A["CP4-reviewed"](p["variant"], r)
                    if None in (o1, v1, o2, v2):
                        continue
                    e1, e2 = sum(map(len, errors(p, o1, v1))), sum(map(len, errors(p, o2, v2)))
                    d1 = set(delta(set(o1["requests"]), set(v1["requests"])))
                    d2 = set(delta(set(o2["requests"]), set(v2["requests"])))
                    diffdocs = {x[1:] for x in d1 ^ d2}
                    if not diffdocs:
                        continue
                    for rule in changed:
                        if diffdocs & (rd.get(rule, set()) | od.get(rule, set())):
                            tally[model][rule]["right" if e2 < e1 else "wrong" if e2 > e1 else "neutral"] += 1
    return {"changed_rules": changed, **{m: {r: dict(c) for r, c in t.items()} for m, t in tally.items()}}


if __name__ == "__main__":
    main()

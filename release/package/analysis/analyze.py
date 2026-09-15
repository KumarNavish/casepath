"""Analysis of an arena run: frozen primary utility, family-weighted means, paired family-level tests,
bootstrap intervals, mechanism metrics, and cost accounting from transport receipts."""
from __future__ import annotations

import argparse, collections, json, random
from pathlib import Path
from statistics import fmean

ARMS_ORDER = ["constant", "random", "static-checklist", "keyword-router", "domain-compiler", "direct-end-to-end", "process-only", "full", "ctes-ablation", "ctes"]


def episode_utility(recs: list[dict]) -> dict:
    final = next(r for r in recs if r["turn"] == 2)["metrics"]
    A = final.get("acquired_critical_evidence") or 0.0
    P = 1 if any((r["metrics"].get("premature_readiness") or 0) for r in recs) else 0
    B = min(4, sum((r["metrics"].get("unnecessary_unique_requests") or 0) + (r["metrics"].get("repeat_requests") or 0) for r in recs))
    H = sum(r["metrics"].get("hearsay_receipts") or 0 for r in recs)
    reqs = sum(r["metrics"].get("total_document_requests") or 0 for r in recs)
    fails = sum(1 for r in recs if r["metrics"].get("status") != "ok")
    return {"U": A - P - 0.25 * B, "A": A, "P": P, "B": B, "hearsay": H, "requests": reqs, "failures": fails,
            "state_acc": fmean([r["metrics"].get("state_accuracy") or 0.0 for r in recs]),
            "readiness_acc": fmean([r["metrics"].get("readiness_accuracy") or 0.0 for r in recs]),
            "action_acc": fmean([r["metrics"].get("next_action_accuracy") or 0.0 for r in recs])}


def load(run: Path, extra: list[Path] | None = None) -> dict:
    res = json.loads((run / "RESULT.json").read_text())
    records = list(res["records"])
    for other in (extra or []):
        o = json.loads((other / "RESULT.json").read_text())
        keep = {r["arm"] for r in o["records"]}
        records = [r for r in records if r["arm"] not in keep] + o["records"]
    res = {**res, "records": records}
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    fam = {}
    for r in res["records"]:
        by[r["arm"]][r["case_id"]].append(r); fam[r["case_id"]] = (r["domain"], r["family"])
    per_episode = {arm: {cid: episode_utility(recs) for cid, recs in cases.items()} for arm, cases in by.items()}
    return {"result": res, "per_episode": per_episode, "family": fam}


def family_means(per_arm: dict, fam: dict, key: str = "U") -> dict:
    out = collections.defaultdict(list)
    for cid, m in per_arm.items():
        out[fam[cid]].append(m[key])
    return {f: fmean(v) for f, v in out.items()}


def paired(a: dict, b: dict) -> dict:
    fams = sorted(set(a) & set(b)); d = [a[f] - b[f] for f in fams]
    wins = sum(x > 0 for x in d); losses = sum(x < 0 for x in d)
    rng = random.Random(20260914); boots = []
    for _ in range(5000):
        s = [d[rng.randrange(len(d))] for _ in d]; boots.append(fmean(s))
    boots.sort()
    return {"families": len(fams), "mean_diff": fmean(d), "ci95": [boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]],
            "wins": wins, "losses": losses, "ties": len(d) - wins - losses}


def costs(run: Path) -> dict:
    total = 0.0; calls = 0; tokens_in = 0; tokens_out = 0; by_arm = collections.defaultdict(lambda: {"calls": 0, "cost": 0.0, "out_tokens": 0})
    for rec in run.glob("pending/turn-*/*/*/receipt.json"):
        r = json.loads(rec.read_text())
        if not r.get("ok"):
            continue
        u = r.get("usage") or {}; c = r.get("cost_usd") or 0.0
        total += c; calls += 1; tokens_in += u.get("prompt_tokens", 0); tokens_out += u.get("completion_tokens", 0)
        for arm in r.get("arms", []):
            share = 1.0 / len(r["arms"])
            by_arm[arm]["calls"] += share; by_arm[arm]["cost"] += c * share; by_arm[arm]["out_tokens"] += u.get("completion_tokens", 0) * share
    return {"physical_calls": calls, "cost_usd": round(total, 4), "prompt_tokens": tokens_in, "completion_tokens": tokens_out,
            "by_arm": {a: {k: round(v, 4) for k, v in d.items()} for a, d in by_arm.items()}}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--run", required=True); ap.add_argument("--out", required=True); ap.add_argument("--latents", default=None); ap.add_argument("--extra-run", nargs="*", default=[])
    a = ap.parse_args(); run = Path(a.run); L = load(run, [Path(x) for x in a.extra_run]); fam = L["family"]
    report = {"run": str(run), "model": L["result"]["model_label"], "episodes": len(fam), "arms": {}, "paired_vs_ctes": {}, "cost": costs(run), "extra_runs": a.extra_run, "extra_cost": [costs(Path(x)) for x in a.extra_run]}
    fm = {arm: family_means(pe, fam) for arm, pe in L["per_episode"].items()}
    for arm in ARMS_ORDER:
        if arm not in L["per_episode"]:
            continue
        pe = L["per_episode"][arm]
        report["arms"][arm] = {"family_weighted_U": fmean(fm[arm].values()), "mean_U": fmean(m["U"] for m in pe.values()),
                               "A": fmean(m["A"] for m in pe.values()), "premature_episodes": sum(m["P"] for m in pe.values()),
                               "burden_total": sum(m["B"] for m in pe.values()), "hearsay_total": sum(m["hearsay"] for m in pe.values()),
                               "requests_total": sum(m["requests"] for m in pe.values()), "failed_records": sum(m["failures"] for m in pe.values()),
                               "state_acc": fmean(m["state_acc"] for m in pe.values()), "readiness_acc": fmean(m["readiness_acc"] for m in pe.values()),
                               "action_acc": fmean(m["action_acc"] for m in pe.values())}
    if "ctes" in fm:
        for arm in fm:
            if arm != "ctes":
                report["paired_vs_ctes"][arm] = paired(fm["ctes"], fm[arm])
    # mechanism signature: utility split by presence of report motifs (possession/quote/relay/existence) and intake attachments
    latents_path = Path(a.latents) if a.latents else None
    if latents_path and latents_path.exists():
        lat = {f"{l['domain']}.{l['family']}.e{l['episode']}": l for l in json.loads(latents_path.read_text())}
        hearsay_ids = {cid for cid, l in lat.items() if any(m["motif"] in {"possession_report", "content_quote", "third_party_relay", "existence_only"} for m in l["motifs"])}
        report["signature"] = {}
        for arm, pe in L["per_episode"].items():
            with_h = [m for cid, m in pe.items() if cid in hearsay_ids]; without = [m for cid, m in pe.items() if cid not in hearsay_ids]
            report["signature"][arm] = {"episodes_with_report_motif": len(with_h), "U_with": fmean(m["U"] for m in with_h) if with_h else None, "U_without": fmean(m["U"] for m in without) if without else None,
                                        "hearsay_with": sum(m["hearsay"] for m in with_h), "hearsay_without": sum(m["hearsay"] for m in without), "premature_with": sum(m["P"] for m in with_h), "premature_without": sum(m["P"] for m in without)}
    by_domain = collections.defaultdict(lambda: collections.defaultdict(list))
    for arm, pe in L["per_episode"].items():
        for cid, m in pe.items():
            by_domain[fam[cid][0]][arm].append(m["U"])
    report["by_domain_U"] = {d: {arm: fmean(v) for arm, v in arms.items()} for d, arms in by_domain.items()}
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in report["arms"].items()}, indent=1))
    print("paired vs ctes:", json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in report["paired_vs_ctes"].items()}, indent=1))
    print("cost:", json.dumps(report["cost"]))


if __name__ == "__main__":
    main()

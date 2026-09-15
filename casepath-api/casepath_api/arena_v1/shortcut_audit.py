"""Shortcut audit: run every zero-model control through the full action-conditioned episodes and a
family-mode leakage probe; report family-weighted primary utility and t0 state accuracy per control."""
from __future__ import annotations

import argparse, collections, copy, json
from pathlib import Path
from statistics import fmean

from casepath_api.arena_v1 import evaluation, runner
from casepath_api.arena_v1.generator import PACKS

CONTROLS = ("constant", "random", "static-checklist", "keyword-router", "domain-compiler")


def episode_utility(records: list[dict]) -> float:
    final = [r for r in records if r["turn"] == 2][0]["metrics"]
    A = final.get("acquired_critical_evidence") or 0.0
    P = 1 if any((r["metrics"].get("premature_readiness") or 0) for r in records) else 0
    B = min(4, sum((r["metrics"].get("unnecessary_unique_requests") or 0) + (r["metrics"].get("repeat_requests") or 0) for r in records))
    return A - P - 0.25 * B


def run_control(case: dict, arm: str) -> list[dict]:
    state = evaluation.initial_state(case); prior = None; prev_plan = None; prev_state = None; out = []
    for turn in range(3):
        public_actor = evaluation.actor_input(case, state, prior); actor = runner.adapt_actor_input(public_actor)
        prior_requests = list((actor.get("prior_plan") or {}).get("requested_document_ids") or [])
        plan = runner.control_plan(arm, actor, turn, prior_requests, pack=PACKS[case["domain"]], seed=runner.seed_for(1, case["case_id"], turn, arm))
        metrics = evaluation.score(case, state, plan, prev_plan, prev_state)
        out.append({"turn": turn, "metrics": metrics})
        if turn < 2:
            try:
                state2, _ = evaluation.advance(case, state, runner.action_requests(plan))
            except ValueError:
                state2, _ = evaluation.advance(case, state, [])
            prev_plan, prev_state, state = copy.deepcopy(plan), state, state2
            prior = runner.prior_for_next_turn(plan)
    return out


def family_mode_probe(cases: list[dict]) -> dict:
    """Leakage probe: predict each episode's t0 gold states/checklist by the modal gold of the OTHER episodes in its family."""
    by_fam = collections.defaultdict(list)
    for c in cases:
        by_fam[(c["domain"], c["family"])].append(c)
    accs, f1s = [], []
    for key, rows in by_fam.items():
        for c in rows:
            others = [o for o in rows if o["case_id"] != c["case_id"]]
            if not others:
                continue
            votes = collections.defaultdict(collections.Counter); check = collections.Counter()
            for o in others:
                ref = evaluation.reference(o, evaluation.initial_state(o))
                for row in ref["document_states"]:
                    votes[row["document_id"]][row["state"]] += 1
                for d in ref["checklist_document_ids"]:
                    check[d] += 1
            ref = evaluation.reference(c, evaluation.initial_state(c))
            gold = {r["document_id"]: r["state"] for r in ref["document_states"]}
            pred = {d: votes[d].most_common(1)[0][0] for d in gold}
            accs.append(sum(pred[d] == gold[d] for d in gold) / len(gold))
            pred_check = {d for d, n in check.items() if n * 2 >= len(others)}; truth = set(ref["checklist_document_ids"])
            ov = len(pred_check & truth); p = ov / len(pred_check) if pred_check else 0.0; r = ov / len(truth) if truth else 0.0
            f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return {"t0_state_accuracy": fmean(accs) if accs else None, "t0_checklist_f1": fmean(f1s) if f1s else None, "episodes": len(accs)}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--cases", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); cases = evaluation.load_cases(a.cases)
    report = {"contract": "casepath.arena-v1-shortcut-audit/1.0.0", "cases": len(cases), "controls": {}}
    for arm in CONTROLS:
        per_fam = collections.defaultdict(list); t0 = []
        for c in cases:
            recs = run_control(c, arm)
            per_fam[(c["domain"], c["family"])].append(episode_utility(recs)); t0.append(recs[0]["metrics"].get("state_accuracy") or 0.0)
        fam_means = [fmean(v) for v in per_fam.values()]
        report["controls"][arm] = {"family_weighted_U": fmean(fam_means), "t0_state_accuracy": fmean(t0), "families": len(fam_means)}
    report["controls"]["family-mode"] = family_mode_probe(cases)
    report["thresholds"] = {"max_control_U": 0.35, "max_control_t0_state_accuracy": 0.75}
    report["admitted"] = all((v.get("family_weighted_U") is None or v["family_weighted_U"] <= 0.35) and (v.get("t0_state_accuracy") is None or v["t0_state_accuracy"] <= 0.75) for v in report["controls"].values())
    Path(a.out).write_text(json.dumps(report, indent=1)); print(json.dumps(report["controls"], indent=1)); print("admitted:", report["admitted"])


if __name__ == "__main__":
    main()

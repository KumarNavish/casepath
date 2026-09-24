from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from casepath_api.paper_method_runtime_v3 import PaperMethodRuntimeV3

CONTRACT = "casepath.product-method-parity/5.0.0"
GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_verdicts(decision: dict) -> dict[str, str]:
    rows = decision.get("verdicts") or decision.get("guard_verdicts") or {}
    return {gid: row.get("verdict") for gid, row in rows.items()}


def norm_action(action: dict | None):
    if not action:
        return None
    out = {k: action.get(k) for k in ("type", "guard_id", "process_node", "condition", "why") if k in action}
    if action.get("request"):
        out["still_missing"] = action["request"].get("still_missing")
    return out


def load_plans(*paths: Path) -> dict[str, dict]:
    out = {}
    for path in paths:
        for row in json.loads(path.read_text()):
            out[row["unit_id"]] = row
    return out


def load_decisions(*paths: Path) -> dict[str, dict]:
    out = {}
    for path in paths:
        out.update(json.loads(path.read_text()))
    return out


def load_pair_rows(*paths: Path) -> dict[str, dict]:
    out = {}
    for path in paths:
        for row in json.loads(path.read_text()):
            out[row["pair_id"]] = row
    return out


def exact_source_chains(plan: dict) -> bool:
    for request in plan.get("requests") or []:
        justifications = request.get("justified_by") or []
        if not justifications:
            return False
        for item in justifications:
            if not item.get("process_node") or not item.get("fact") or not item.get("must_show"):
                return False
            sources = item.get("sources") or []
            if not sources:
                return False
            if any(not s.get("quote") or s["quote"] not in (s.get("exact_text") or "") for s in sources):
                return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--benchmark", type=Path, required=True)
    ap.add_argument("--dev-decisions", type=Path, required=True)
    ap.add_argument("--dev-plans", type=Path, required=True)
    ap.add_argument("--hidden-decisions", type=Path, required=True)
    ap.add_argument("--hidden-plans", type=Path, required=True)
    ap.add_argument("--dev-pairs", type=Path, required=True)
    ap.add_argument("--hidden-pairs", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    benchmark = json.loads(args.benchmark.read_text())
    decisions = load_decisions(args.dev_decisions, args.hidden_decisions)
    plans = load_plans(args.dev_plans, args.hidden_plans)
    pair_rows = load_pair_rows(args.dev_pairs, args.hidden_pairs)
    units = {u["unit_id"]: u for u in benchmark["units"]}

    text_ids: dict[str, list[str]] = defaultdict(list)
    for unit in benchmark["units"]:
        text_ids[unit["customer_message"]].append(unit["unit_id"])

    duplicate_semantic_ok = True
    for ids in text_ids.values():
        if len(ids) < 2:
            continue
        first = semantic_verdicts(decisions[ids[0]])
        duplicate_semantic_ok &= all(semantic_verdicts(decisions[uid]) == first for uid in ids[1:])

    canonical_uid = {text: sorted(ids)[0] for text, ids in text_ids.items()}

    def fake_call(_system: str, user: str) -> str:
        payload = json.loads(user)
        case = payload["cases"][0]
        text = case["materials"]["customer_message"]
        uid = canonical_uid[text]
        guard_id = payload["guard"]["guard_id"]
        verdict = decisions[uid]["verdicts"][guard_id]
        row = {
            "unit_id": case["unit_id"],
            "verdict": verdict.get("verdict"),
            "quote": verdict.get("quote"),
            "source_ref": verdict.get("source_ref"),
            "what_would_settle_it": verdict.get("what_would_settle_it"),
        }
        return json.dumps({"results": [row]})

    runtime = PaperMethodRuntimeV3(args.pack, call=fake_call)
    if not runtime.ready:
        raise RuntimeError(runtime.status())

    product_plans: dict[str, dict] = {}
    mismatches = []
    source_failures = []
    for uid, unit in units.items():
        got = runtime.plan({"customer_message": unit["customer_message"]}, [])
        expected = plans[uid]
        product_plans[uid] = got
        if got.get("documents") != expected.get("documents"):
            mismatches.append({"unit_id": uid, "field": "documents"})
        if semantic_verdicts(got) != semantic_verdicts(expected):
            mismatches.append({"unit_id": uid, "field": "guard_verdicts"})
        if norm_action(got.get("next_action")) != norm_action(expected.get("next_action")):
            mismatches.append({"unit_id": uid, "field": "next_action"})
        if not exact_source_chains(got):
            source_failures.append(uid)

    pair_mismatches = []
    for pair in benchmark["pairs"]:
        before = product_plans[pair["false_unit_id"]]
        after = product_plans[pair["true_unit_id"]]
        diff = runtime.diff(before, after)
        predicted = sorted(
            ["+" + row["document"] for row in diff.get("added") or []]
            + ["-" + row["document"] for row in diff.get("withdrawn") or []]
        )
        expected = sorted(pair_rows[pair["pair_id"]]["predicted_signed_delta"])
        if predicted != expected:
            pair_mismatches.append({"pair_id": pair["pair_id"],
                                    "product": predicted, "research": expected})

    status = runtime.status()
    result = {
        "contract": CONTRACT,
        "goal_contract_sha256": GOAL,
        "passed": bool(duplicate_semantic_ok and not mismatches and not pair_mismatches and not source_failures),
        "benchmark_units": len(units),
        "benchmark_pairs": len(benchmark["pairs"]),
        "duplicate_text_semantic_invariant": duplicate_semantic_ok,
        "unit_semantic_mismatches": mismatches,
        "pair_delta_mismatches": pair_mismatches,
        "source_chain_failures": source_failures,
        "all_unit_documents_match": not any(x["field"] == "documents" for x in mismatches),
        "all_unit_guard_states_match": not any(x["field"] == "guard_verdicts" for x in mismatches),
        "all_unit_next_actions_match": not any(x["field"] == "next_action" for x in mismatches),
        "all_pair_deltas_match": not pair_mismatches,
        "all_product_requests_have_exact_source_spans": not source_failures,
        "pack_manifest_sha256": status.get("pack_manifest_sha256"),
        "method_freeze_sha256": status.get("method_freeze_sha256"),
        "inputs": {
            "benchmark": sha(args.benchmark),
            "dev_decisions": sha(args.dev_decisions),
            "dev_plans": sha(args.dev_plans),
            "hidden_decisions": sha(args.hidden_decisions),
            "hidden_plans": sha(args.hidden_plans),
            "dev_pairs": sha(args.dev_pairs),
            "hidden_pairs": sha(args.hidden_pairs),
        },
        "verifier_sha256": sha(Path(__file__)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

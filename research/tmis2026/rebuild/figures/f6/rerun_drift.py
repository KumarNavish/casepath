"""Figure 6, right: how many checklist lines a prompt changes when it reads the same file again with unchanged rules.
POST HOC, Study 3's files (fresh2), stored runs only, no model call.

    python3 -I -B rerun_drift.py      # writes rerun_drift.json

Prompt = the prompt that may hold (study4/baseline_check, design 'hold_prompt', the cost-efficient model, 3 runs per
case). Beside it, for the same files, CasePath's stored Study 3 runs (design 'casepath', 3 runs per case): it also reads
again on a new run, so its run-to-run drift is reported, not hidden. Loading and the theft name mapping are Study 3's
own (analysis/study3.py via study4/baseline_check/analyse.py).

A line = one catalogue document of the case (tenancy: the reference's document_states of the claim's family; theft:
the 33-entry catalogue), state request / hold / neither. For each case and each pair of runs (0-1, 0-2, 1-2) count
lines whose state differs. Calls per case-run read from the ledger where present.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[2]
sys.path.insert(0, str(TMIS / "study4" / "baseline_check"))
import analyse as B  # noqa: E402


def state(plan, d):
    plan = plan or {}
    if d in set(plan.get("requests") or []):
        return "request"
    if d in set(plan.get("holds") or []):
        return "hold"
    return "neither"


def main():
    spec = B.spec_with_new()
    B.s3.configure(spec)
    st = B.s3.Study(spec, "fresh2", "confirm", B.s3.load_data("fresh2"))
    theft_cat = sorted(set(st.inv.values()))
    out = {"label": "POST HOC, Study 3 files (fresh2), stored runs; same file, same rules, no edit", "designs": {}}
    for design in ("hold_prompt", "casepath"):
        res = {}
        for reg in ("tenancy", "theft"):
            assert st.load(design, reg), st.status[(design, reg)]
            plans = st.plans[(design, reg)]
            pairs = lines_total = lines_diff = pairs_any = 0
            extra = set()
            for cid, runs in plans.items():
                if reg == "tenancy":
                    cat = sorted(st.D["tenancy"].reference(cid)["document_states"])
                else:
                    cat = theft_cat
                named = {d for p in runs for d in (p or {}).get("requests", []) + (p or {}).get("holds", [])}
                extra |= named - set(cat)
                lines = sorted(set(cat) | named)
                for a, b in combinations(range(len(runs)), 2):
                    diff = sum(state(runs[a], d) != state(runs[b], d) for d in lines)
                    pairs += 1
                    lines_total += len(lines)
                    lines_diff += diff
                    pairs_any += diff > 0
            res[reg] = {"cases": len(plans), "runs_per_case": len(next(iter(plans.values()))), "run_pairs": pairs,
                        "run_pairs_with_any_line_different": pairs_any, "lines_compared": lines_total,
                        "lines_different": lines_diff, "lines_different_per_pair": lines_diff / pairs,
                        "names_outside_catalogue": len(extra)}
        out["designs"][design] = res
    (HERE / "rerun_drift.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

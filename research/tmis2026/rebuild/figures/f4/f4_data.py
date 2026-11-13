"""Figure 4 data: the fate of requests per design on Study 3's sealed tenancy claims. No model calls.

    python3 -I f4_data.py      # writes f4_data.json beside this file

Unit: one document of one claim-run (a "request"). Reference state from fresh2's reference
(study2.REQ_NOW = request now; "held" = hold, waiting for an open fact; anything else = not needed).
Each document is assigned the fate the registered scorer study2.ten_row counts it under (mirrored per document
below and checked against ten_row's totals for every claim-run):
  reference "held"        -> held | requested too early (premature) | dropped (silent_skip) | handed to a person (handed_held)
  reference "request now" -> requested | held needlessly (held_req) | dropped (missed) | handed to a person (handed)
  reference "not needed"  -> requested needlessly (unnecessary) | held needlessly (spurious_hold) | left alone
Pooling: every document-run counts once (runs pooled; claims, families and runs are balanced, so this equals
the mean over runs). A failed output is an empty plan (registered rule): its documents are dropped.
Questions: only the product states its question as a fact id; for it, "names the open fact" = the reference's
open-fact flag is among plan.questions. Free-text questions of the other designs are not scored (no registered scorer).
Loading and scoring are imported from analysis/study3.py (frozen) and study4/baseline_check/analyse.py (the
fair-prompt designs as in-memory spec entries); nothing is edited.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[2]
sys.path.insert(0, str(TMIS / "analysis"))
sys.path.insert(0, str(TMIS / "harness" / "v2"))
sys.path.insert(0, str(TMIS / "study4" / "baseline_check"))
import analyse as BC  # noqa: E402  (fair-prompt check; spec_with_new only)

s3, s2 = BC.s3, BC.s2

# Order: the product; the strongest prompt; the others (same order in Figures 5 and 7).
DESIGNS = [
    ("casepath", "CasePath", "cost-efficient", "the product"),
    ("hold_prompt_frontier", "Prompt that may hold", "frontier", "strongest prompt"),
    ("hold_prompt", "Prompt that may hold", "cost-efficient", "prompt"),
    ("ric_frontier", "Rules in context", "frontier", "prompt"),
    ("ric", "Rules in context", "cost-efficient", "prompt"),
    ("self_consistency", "Self-consistency (5 votes)", "cost-efficient", "prompt"),
    ("mer_hold_frontier", "Model executes rules", "frontier", "agent"),
    ("model_executes_rules", "Model executes rules", "cost-efficient", "agent"),
    ("react", "ReAct", "cost-efficient", "agent"),
]


def fates(ref, plan):
    plan = plan or s3.EMPTY
    states = ref["document_states"]
    P = set(plan.get("requests", []))
    H = set(plan.get("holds", [])) - P
    deferred = bool(plan.get("deferred"))
    out = []
    for d, s in states.items():
        if s in s2.REQ_NOW:
            ref_state = "request_now"
            if d in P:
                f = "requested"
            elif deferred:
                f = "handed"
            elif d in H:
                f = "held_needlessly"
            else:
                f = "dropped"
        elif s == "held":
            ref_state = "hold"
            if d in P:
                f = "too_early"
            elif deferred:
                f = "handed"
            elif d in H:
                f = "held"
            else:
                f = "dropped"
        else:
            ref_state = "not_needed"
            f = "requested_needlessly" if d in P else ("held_needlessly" if (d in H and not deferred) else "left_alone")
        out.append((d, ref_state, f))
    # documents outside the reference's catalogue: the scorer counts them as unnecessary / spurious
    for d in sorted((P | H) - set(states)):
        if d in P:
            out.append((d, "not_needed", "requested_needlessly"))
        elif not deferred:
            out.append((d, "not_needed", "held_needlessly"))
    return out


def check(row, fs):
    c = Counter((r, f) for _, r, f in fs)
    assert c[("hold", "held")] == row["correct_hold"]
    assert c[("hold", "too_early")] == row["premature"]
    assert c[("hold", "dropped")] == row["silent_skip"]
    assert c[("hold", "handed")] == row["handed_held"]
    assert c[("request_now", "requested")] == row["requested"]
    assert c[("request_now", "held_needlessly")] == row["held_req"]
    assert c[("request_now", "dropped")] == row["missed"]
    assert c[("request_now", "handed")] == row["handed"]
    assert c[("not_needed", "requested_needlessly")] == row["unnecessary"]
    assert c[("not_needed", "held_needlessly")] == row["spurious_hold"]


def load():
    spec = BC.spec_with_new()
    s3.configure(spec)
    study = s3.Study(spec, "fresh2", "confirm", s3.load_data("fresh2"))
    return study


def main():
    study = load()
    D = study.D["tenancy"]
    out = {"figure": "f4", "label": "Study 3 sealed tenancy claims (fresh2, run label confirm); fair-prompt designs "
                                    "post hoc on the same claims (study4/baseline_check)",
           "unit": "one document of one claim-run", "pooling": "document-runs pooled over runs",
           "designs": []}
    for key, name, model, role in DESIGNS:
        ok = study.load(key, "tenancy")
        assert ok, key
        st = study.status[(key, "tenancy")]
        rows = {(r["case"], r["run"]): r for r in study.tenancy_rows(key)}
        cnt = Counter()
        by_sub = {"denied_event": Counter(), "other": Counter()}
        q_right = q_total = 0
        for cid in study.cases["tenancy"]:
            ref = D.reference(cid)
            denied = study.in_subset(cid, "denied_event")
            for r, plan in enumerate(study.plans[(key, "tenancy")][cid]):
                fs = fates(ref, plan)
                check(rows[(cid, r)], fs)
                for _, rs, f in fs:
                    cnt[(rs, f)] += 1
                    by_sub["denied_event" if denied else "other"][(rs, f)] += 1
                if key == "casepath" and plan and ref.get("open_fact"):
                    held = [d for d, rs, f in fs if rs == "hold" and f == "held"]
                    if held:
                        q_total += len(held)
                        if ref["open_fact"]["flag"] in (plan.get("questions") or []):
                            q_right += len(held)
        hold_n = sum(v for (rs, _), v in cnt.items() if rs == "hold")
        req_n = sum(v for (rs, _), v in cnt.items() if rs == "request_now")
        claim_runs = len(rows)
        per100 = lambda rs, n: {f: 100 * v / n for (r, f), v in sorted(cnt.items()) if r == rs}
        d = {"key": key, "name": name, "model": model, "role": role, "runs": st["runs"], "file": st.get("file"),
             "failed_outputs": st.get("failed_outputs"), "claim_runs": claim_runs,
             "open": {"denominator_document_runs": hold_n,
                      "counts": {f: v for (r, f), v in sorted(cnt.items()) if r == "hold"},
                      "per100": per100("hold", hold_n)},
             "settled": {"denominator_document_runs": req_n,
                         "counts": {f: v for (r, f), v in sorted(cnt.items()) if r == "request_now"},
                         "per100": per100("request_now", req_n)},
             "not_needed": {"counts": {f: v for (r, f), v in sorted(cnt.items()) if r == "not_needed"},
                            "needless_holds_per100_settled": 100 * cnt[("not_needed", "held_needlessly")] / req_n,
                            "needless_requests_per100_settled": 100 * cnt[("not_needed", "requested_needlessly")] / req_n,
                            "needless_holds_on_denied_event_claims": by_sub["denied_event"][("not_needed", "held_needlessly")],
                            "needless_requests_on_denied_event_claims": by_sub["denied_event"][("not_needed", "requested_needlessly")]}}
        if key == "casepath":
            d["question_names_open_fact"] = {"right": q_right, "of_held": q_total,
                                             "rule": "open-fact flag id in plan.questions (product states fact ids)"}
        else:
            d["question_names_open_fact"] = "not scored: free-text questions, no registered scorer"
        out["designs"].append(d)
    out["inputs"] = dict(sorted(study.inputs.hashes.items()))
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (HERE / "f4_data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for d in out["designs"]:
        o, s, n = d["open"], d["settled"], d["not_needed"]
        print(f"{d['name'][:26]:26s} {d['model'][:5]} runs {d['runs']} | open n={o['denominator_document_runs']:4d} "
              + " ".join(f"{k}={v:5.1f}" for k, v in o["per100"].items())
              + f" | settled n={s['denominator_document_runs']:5d} " + " ".join(f"{k}={v:5.1f}" for k, v in s["per100"].items())
              + f" | NN holds/100={n['needless_holds_per100_settled']:5.1f} (denied {n['needless_holds_on_denied_event_claims']})"
              + f" NN req/100={n['needless_requests_per100_settled']:5.1f} (denied {n['needless_requests_on_denied_event_claims']})")
    print(out["designs"][0]["question_names_open_fact"])


if __name__ == "__main__":
    main()

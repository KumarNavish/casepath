"""Offline ablations of CasePath v2 (frozen plan, section 6). NO model calls: everything is recomputed from the
recorded CPv2p interpretations in runs/v2/plans_<exp>_<model>_<data>_<split>.json.

Tenancy (from each run's admitted proposal, recorded as 'replay'):
  CPv2p-nopres   without the presumption clause (exact deferral, otherwise identical)
  CPv2p-kleene   strong Kleene evaluation instead of exact deferral
  CPv2p-2read    "two readings agree": a true/false condition verdict counts only if run r and run (r+1) mod 3
                 give the same verdict, each with a located quotation; otherwise unresolved (citations kept)
Theft (from each run's recorded raw judgments):
  CPv2p-kleene   identical to CPv2p by construction (flat rules: monotone OR of literals); recomputed anyway
  CPv2p-2read    as above, per guard
  CPv2p-origpack the original extracted pack (PREPARED.json) executed on the recorded judgments. Guards of the
                 original pack that the v2 pack does not contain were never judged: they are reported (count and
                 ids, and the number of extra judgments needed = texts x runs x missing guards) and treated as
                 unresolved, never filled by a model call.
Usage: python3 ablate.py --data fresh --model gpt-6-luna [--split heldout]
Writes runs/v2/ablations_<exp>_<model>_<data>_<split>.json in the plans format ("<design>|<case>|<run>": {"plan"}).
"""
import argparse
import copy
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="fresh")
ap.add_argument("--model", default="gpt-6-luna")
ap.add_argument("--split", default="heldout")
args = ap.parse_args()
os.environ["TMIS_MODEL"] = f"openai/{args.model}"
os.environ["TMIS_BUDGET_USD"] = "0"  # any model call would fail
import common  # noqa: E402
import llm  # noqa: E402


def _no_calls(**kw):
    raise RuntimeError("ablate.py makes no model calls")


llm.call = _no_calls
K = 3


def tenancy():
    import tenancy_v2 as tv
    from casepath_api.autonomous_policy_v1 import proposal_items, validate_interpretation
    path = common.OUT / f"plans_tenancy_{args.model}_{args.data}_{args.split}.json"
    if not path.exists():
        return None
    P = json.loads(path.read_text())
    D = common.data("tenancy", args.data)
    pack = tv.pack_for(D)
    out = {}
    for key, entry in P.items():
        design, c, r = key.split("|")
        if design != "CPv2p":
            continue
        r = int(r)
        rep = (entry or {}).get("replay")
        if rep is None:  # handoff or failed output: the ablations inherit the recorded plan
            for name in ("CPv2p-nopres", "CPv2p-kleene", "CPv2p-2read"):
                out[f"{name}|{c}|{r}"] = {"plan": (entry or {}).get("plan")}
            continue
        srcs = D.sources(c)
        verified, prop = rep["verified"], rep["proposal"]
        out[f"CPv2p-nopres|{c}|{r}"] = {"plan": tv.plan_v2(D, c, verified, prop, srcs, pack, presumptions=False)}
        out[f"CPv2p-kleene|{c}|{r}"] = {"plan": tv.plan_v2(D, c, verified, prop, srcs, pack, semantics="kleene")}
        other = ((P.get(f"CPv2p|{c}|{(r + 1) % K}") or {}).get("replay") or {}).get("proposal") or {}
        second = {row["flag"]: row for row in other.get("conditions", [])}
        p2 = copy.deepcopy(prop)
        for row in p2["conditions"]:
            if row["verdict"] in {"true", "false"}:
                s = second.get(row["flag"])
                if not (row["citations"] and s and s["verdict"] == row["verdict"] and s["citations"]):
                    row["verdict"] = "unresolved"
        allok = {"family_supported": True, "issues": [], "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in proposal_items(p2)]}
        try:
            out[f"CPv2p-2read|{c}|{r}"] = {"plan": tv.plan_v2(D, c, validate_interpretation(pack, srcs, p2, allok), p2, srcs, pack)}
        except ValueError as error:
            out[f"CPv2p-2read|{c}|{r}"] = {"plan": tv.handoff(str(error))}
    return out, {}


def theft():
    import theft_v2
    path = common.OUT / f"plans_theft_{args.model}_{args.data}_{args.split}.json"
    if not path.exists():
        return None
    P = json.loads(path.read_text())
    T = common.data("theft", args.data).texts()
    prep = json.loads((common.REPO / "data" / "casepath-theft-pairs" / "representation" / "PREPARED.json").read_text())
    orig = theft_v2.TheftPack({"overlay": prep["overlay"], "requirements": prep["requirements"],
                               "resolvers": prep["resolvers"], "quarantined_rules": []})
    v2 = theft_v2.DEFAULT
    missing = sorted(set(orig.guards) - set(v2.guards))
    out = {}
    texts_run = 0
    for key, entry in P.items():
        design, t, r = key.split("|")
        if design != "CPv2p" or not (entry or {}).get("raw_judgments"):
            continue
        texts_run += 1
        r = int(r)
        nu = entry["judgments_no_verifier"]
        out[f"CPv2p-kleene|{t}|{r}"] = {"plan": v2.plan_kleene(nu)}
        other = (P.get(f"CPv2p|{t}|{(r + 1) % K}") or {}).get("judgments_no_verifier") or {}
        agreed = {g: (v if v in {"true", "false"} and other.get(g) == v else "unresolved") for g, v in nu.items()}
        out[f"CPv2p-2read|{t}|{r}"] = {"plan": v2.plan_exact(agreed)}
        out[f"CPv2p-origpack|{t}|{r}"] = {"plan": orig.plan_exact({g: nu.get(g, "unresolved") for g in orig.guards})}
    note = {"original_pack_guards": len(orig.guards), "v2_pack_guards_judged": len(v2.guards),
            "original_guards_not_judged": missing, "extra_judgments_needed": len(missing) * texts_run,
            "recorded_text_runs": texts_run}
    return out, note


if __name__ == "__main__":
    for exp, fn in (("tenancy", tenancy), ("theft", theft)):
        res = fn()
        if res is None:
            print(exp, "no recorded plans for", args.model, args.data, args.split)
            continue
        plans, note = res
        common.dump(common.OUT / f"ablations_{exp}_{args.model}_{args.data}_{args.split}.json", {"_note": note, **plans})
        print(exp, len(plans), "ablation plans", json.dumps(note))

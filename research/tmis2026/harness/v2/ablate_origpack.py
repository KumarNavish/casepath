"""Original-pack ablation with the eight extra judgments (judge_extra.py) filled in; no model calls.
Writes runs/v2/ablations_theft_origpack_<model>_<data>_<split>.json in the plans format (design CPv2p-origpack-full)."""
import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="fresh")
ap.add_argument("--model", default="gpt-6-luna")
ap.add_argument("--split", default="heldout")
args = ap.parse_args()
os.environ["TMIS_MODEL"] = f"openai/{args.model}"
os.environ["TMIS_BUDGET_USD"] = "0"
import common  # noqa: E402
import theft_v2  # noqa: E402

P = json.loads((common.OUT / f"plans_theft_{args.model}_{args.data}_{args.split}.json").read_text())
X = json.loads((common.OUT / f"extra_judgments_theft_gpt-6-luna_{args.data}.json").read_text())
prep = json.loads((common.REPO / "data" / "casepath-theft-pairs" / "representation" / "PREPARED.json").read_text())
orig = theft_v2.TheftPack({"overlay": prep["overlay"], "requirements": prep["requirements"],
                           "resolvers": prep["resolvers"], "quarantined_rules": []})
out, filled = {}, 0
for key, entry in P.items():
    design, t, r = key.split("|")
    if design != "CPv2p" or not (entry or {}).get("judgments_no_verifier"):
        continue
    nu = dict(entry["judgments_no_verifier"])
    extra = (X.get(t) or {}).get("judgments") or {}
    filled += bool(extra)
    nu.update(extra)
    out[f"CPv2p-origpack-full|{t}|{r}"] = {"plan": orig.plan_exact({g: nu.get(g, "unresolved") for g in orig.guards})}
common.dump(common.OUT / f"ablations_theft_origpack_{args.model}_{args.data}_{args.split}.json",
            {"_note": {"extra_judgments_from": "judge_extra.py, one gpt-6-luna call per text (run 0), used for all three runs",
                       "text_runs_with_extra": filled}, **out})
print(len(out), "plans;", filled, "with extra judgments")

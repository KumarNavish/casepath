"""Empirical judgment errors of CasePath's interpreter and the effect of the verifier."""
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference
TAG = sys.argv[1] if len(sys.argv) > 1 else "gpt-6.1-terra"
P = json.loads((HERE.parent / "runs" / f"plans_tenancy_{TAG}.json").read_text())
c = Counter()
for cid in claim_ids("test"):
    ref = reference(cid)
    truth = {**ref["implicit_flags"], **ref["scenario"]}
    for r in range(3):
        j = (P.get(f"CP|{cid}|{r}") or {}).get("judgments")
        if not j:
            continue
        if j["family"] != ref["family"]:
            c["family_wrong"] += 1
            continue
        for flag, t in truth.items():
            v = j["conditions"].get(flag, "unresolved")
            acc = j["verifier"].get(f"condition:{flag}", True)
            tv = "true" if t else "false"
            kind = "correct" if v == tv else "unresolved" if v == "unresolved" else "flipped"
            c[("interp", kind)] += 1
            c[("interp", kind, "truth_" + tv)] += 1
            if v != "unresolved" and not acc:
                c[("verifier_rejected", "was_" + kind)] += 1
            after = v if (acc or v == "unresolved") else "unresolved"
            kind2 = "correct" if after == tv else "unresolved" if after == "unresolved" else "flipped"
            c[("admitted", kind2)] += 1
            routing = flag in ref["implicit_flags"]
            c[("interp", kind, "routing" if routing else "scenario")] += 1
out = {" | ".join(k) if isinstance(k, tuple) else k: v for k, v in sorted(c.items(), key=str)}
(HERE / f"judgment_accuracy_{TAG}.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

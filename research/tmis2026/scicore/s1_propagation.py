"""S1b: exact expected request errors under a judgment-error model.

Each flag is judged correctly with probability 1-eps; an error is 'unresolved'
with probability rho and a confident flip otherwise. Expectations are exact
sums over all partial assignments (no sampling). Usage: s1_propagation.py TABLEDIR OUT
"""
import json
import sys
from itertools import product
from pathlib import Path

tables = {}
for p in sorted(Path(sys.argv[1]).glob("s1_tables_*.json")):
    tables.update(json.loads(p.read_text()))
EPS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4]
RHO = [0.0, 0.25, 0.5, 0.75, 1.0]
SEM = ["kleene", "exact", "closed", "eager"]
skip_photo = {"clm_e262801f9368bc12", "clm_731b214dde882f89", "clm_7ac806bd30792cfb"}
out = []
for eps, rho in product(EPS, RHO):
    agg = {s: {"unnecessary": 0.0, "missed": 0.0, "deferred": 0.0, "requested": 0.0} for s in SEM}
    n_req = 0
    for cid, t in tables.items():
        R = set(t["reference_requests"]) - ({"dated_photos"} if cid in skip_photo else set())
        n_req += len(R)
        for key, row in t["table"].items():
            p = 1.0
            for judged, true in zip(key, t["truth"]):
                if judged == true:
                    p *= 1 - eps
                elif judged == "U":
                    p *= eps * rho
                else:
                    p *= eps * (1 - rho)
            if p == 0.0:
                continue
            for s in SEM:
                req, held = set(row[s][0]), set(row[s][1])
                agg[s]["unnecessary"] += p * len(req - R)
                agg[s]["missed"] += p * len(R - req - held)
                agg[s]["deferred"] += p * len(R & held)
                agg[s]["requested"] += p * len(req)
    out.append({"eps": eps, "rho": rho, "required_total": n_req, "claims": len(tables),
                **{f"{s}_{k}": v for s in SEM for k, v in agg[s].items()}})
Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
print("wrote", len(out), "grid points over", len(tables), "claims")

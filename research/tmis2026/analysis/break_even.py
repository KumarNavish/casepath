"""Break-even cost of deferral (POST HOC; not in ANALYSIS_PLAN.md).

Per claim, a design incurs unsafe errors u (unnecessary requests + silent misses), held
documents h (behind a question) and handed-over documents o (whole-claim handoff). With an
unsafe error costing c_u and every deferred document (held or handed) costing c_d, CasePath
is preferred over Rules in context iff c_u / c_d exceeds
    ratio = ((h + o)_CP - (h + o)_B1) / (u_B1 - u_CP),
defined only when CasePath makes fewer unsafe errors (otherwise it is never preferred).
The strict variant counts handed-over documents as unsafe instead of deferred.
Writes break_even.json."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent


def ratio(u_cp, d_cp, u_b, d_b):
    if u_b - u_cp <= 1e-12:
        return None  # CasePath makes at least as many unsafe errors: never preferred
    return max(0.0, (d_cp - d_b) / (u_b - u_cp))


out = {"post_hoc": True}
for tag in ("gpt-6.1-terra", "gpt-6-luna"):
    t = json.loads((HERE / f"results_{tag}.json").read_text())["tenancy"]
    x = json.loads((HERE / f"tenancy_extra_{tag}.json").read_text())["routing_presumption_all"]
    n = x["runs"]
    designs = {name: {"unsafe": t[name]["unsafe_per_claim"], "held": t[name]["held_per_claim"],
                      "handed": t[name]["handed_per_claim"]} for name in ("B1", "CP-exact")}
    designs["CP-exact-routing"] = {"unsafe": (x["fp"] + x["miss"]) / n, "held": x["held"] / n, "handed": x["handed"] / n}
    b = designs["B1"]
    res = {"designs": designs}
    for name in ("CP-exact", "CP-exact-routing"):
        c = designs[name]
        res[name] = {"ratio": ratio(c["unsafe"], c["held"] + c["handed"], b["unsafe"], b["held"] + b["handed"]),
                     "ratio_strict": ratio(c["unsafe"] + c["handed"], c["held"], b["unsafe"] + b["handed"], b["held"])}
    out[tag] = res
(HERE / "break_even.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

"""Parity: the harness planner (all-routes mode) on the ORIGINAL ICLR condition
answers must reproduce the original CasePath checklists of Study A."""
import json, sys, zipfile
from pathlib import Path
import theft_methods as tm

ZIP = Path("/home/user/work/repro/study-a-v5/original-v5.zip")
PRED = tm.PREP and Path(__file__).resolve().parents[3] / "data/casepath-theft-pairs/benchmark/predictions"


def original_judgments(split_dir: str) -> dict:
    z = zipfile.ZipFile(ZIP)
    out = {}
    for n in z.namelist():
        if f"/{split_dir}/" in n and n.endswith(".receipt.json"):
            guard = json.loads(z.read(n))["guard_id"]
            ans = json.loads(z.read(n.replace(".receipt.json", ".answer.json")))
            for row in ans["results"]:
                out.setdefault(row["unit_id"], {})[guard] = row["verdict"]
    return out


if __name__ == "__main__":
    nu = original_judgments("v11-b5-hidden-v5")
    preds = json.loads((PRED / "heldout" / "casepath.json").read_text())
    agree = total = 0
    for p in preds:
        for side, unit in (("before_documents", p["before_unit_id"]), ("after_documents", p["after_unit_id"])):
            mine = set(tm.plan({g: nu[unit].get(g, "unresolved") for g in tm.GUARDS}, all_routes=True)["requests"])
            orig = set(p[side])
            total += 1
            agree += mine == orig
            if mine != orig and total < 6:
                print(unit, "extra", sorted(mine - orig)[:3], "missing", sorted(orig - mine)[:3])
    print(f"exact checklist agreement: {agree}/{total}")

"""Blind re-derivation of the theft references from the sources alone.

For each condition, the model sees the source passages, the catalogue and the
two versions of the condition sentence, and lists which documents the true
version adds or removes (alternatives grouped). It never sees the reference,
CasePath's rules or any method output. Three independent runs per condition.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import llm
import theft_methods as tm
from theft_data import benchmark

SCHEMA = tm.obj({"added_requirements": tm.arr(tm.obj({"alternatives": tm.arr(tm.arr(tm.DOC_ENUM, 4), 4),
                                                        "why": {"type": "string", "maxLength": 300}}), 6),
                 "withdrawn": tm.arr(tm.DOC_ENUM, 6)})
SYSTEM = (tm.sources_block() + "\n\n" + tm.catalogue_block() + """

TASK: A household-theft claim is identical in two versions except for one statement. Using ONLY the source
passages, decide which catalogue documents the second version newly requires (added) and which documents it makes
unnecessary (withdrawn), compared with the first version. Group documents that are alternatives for the same
requirement (any one suffices) as separate alternatives of one requirement; documents that are needed together form
one alternative. List only changes caused by the changed statement.""")


def run(cond_pair, r):
    user = f"FIRST VERSION STATEMENT: {cond_pair['changed_statement_false']}\nSECOND VERSION STATEMENT: {cond_pair['changed_statement_true']}"
    res = llm.call(system=SYSTEM, user=user, schema=SCHEMA, schema_name="reference", run=r, max_tokens=2000,
                   tag={"exp": "reference_rederive", "method": "blind", "case": cond_pair["scenario"]})
    return cond_pair["scenario"], r, res["result"]


if __name__ == "__main__":
    seen, conds = set(), []
    for p in benchmark()["pairs"]:
        if p["scenario"] not in seen:
            seen.add(p["scenario"]); conds.append(p)
    with ThreadPoolExecutor(9) as ex:
        out = list(ex.map(lambda a: run(*a), [(c, r) for c in conds for r in range(3)]))
    rows = {}
    for scen, r, res in out:
        rows.setdefault(scen, {})[r] = {"added": [[sorted(tm.INV[i] for i in alt) for alt in req["alternatives"]] for req in res["added_requirements"]],
                                        "withdrawn": sorted(tm.INV[i] for i in res["withdrawn"])} if res else None
    ref = {c["scenario"]: c["acceptable_signed_deltas"] for c in conds}
    json.dump({"rederived": rows, "reference": ref}, open("../analysis/reference_rederivation.json", "w"), indent=1, ensure_ascii=False)
    for scen in ref:
        ref_docs = {d.lstrip("+") for opt in ref[scen] for d in opt}
        for r in range(3):
            v = rows[scen][r]
            got = {d for req in v["added"] for alt in req for d in alt} if v else set()
            print(scen[:28].ljust(28), r, "ref", len(ref_docs), "got", len(got), "overlap", len(ref_docs & got),
                  "withdrawn", len(v["withdrawn"]) if v else None)

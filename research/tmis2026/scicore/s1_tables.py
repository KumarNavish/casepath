"""S1 (sciCORE): exact decision tables for every tenancy claim.

For each claim and EVERY partial assignment of its family's condition flags
(true/false/unresolved), evaluate the product engine and record which
documents are requested and held under four semantics:
  kleene  - the product engine unchanged (strong Kleene);
  exact   - supervaluation over the open flags (our fix);
  closed  - two-valued, unresolved read as false (closed world);
  eager   - two-valued, unresolved read as true.
Usage: python3 s1_tables.py SHARD NSHARDS OUTDIR
"""
import json
import sys
import time
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference, templates  # noqa: E402
from casepath_tenancy import compile_process, evaluate  # noqa: E402
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402

REQ = {"needed_now", "needed_later"}


def states(graph, override):
    view = evaluate(graph, conditions=override)
    return {d["document_type"]: d["route_state"] for d in view["documents"]}


def table_for(cid):
    ref = reference(cid)
    fam = ref["family"]
    flags = list(FAMILY_FLAGS[fam])
    verified = {"category": {"family": fam, "summary": "", "citations": []},
                "conditions": [{"flag": f, "verdict": "unresolved", "summary": "", "citations": []} for f in flags],
                "documents": [], "steps": [], "item_rejections": []}
    graph, _, _ = compile_process(templates(), cid, verified)
    docs = sorted(d["document_type"] for d in graph["document_catalog"])
    complete = {}
    for bits in product("TF", repeat=len(flags)):
        ov = {f: ("true" if b == "T" else "false") for f, b in zip(flags, bits)}
        complete["".join(bits)] = {d for d, s in states(graph, ov).items() if s in REQ}
    rows = {}
    for vals in product("TFU", repeat=len(flags)):
        key = "".join(vals)
        ov = {f: {"T": "true", "F": "false", "U": "unresolved"}[v] for f, v in zip(flags, vals)}
        kl = states(graph, ov)
        comps = [complete["".join(c)] for c in product(*[("T", "F") if v == "U" else (v,) for v in vals])]
        always = set.intersection(*comps)
        sometimes = set.union(*comps)
        closed = complete["".join("F" if v == "U" else v for v in vals)]
        eager = complete["".join("T" if v == "U" else v for v in vals)]
        rows[key] = {"kleene": [sorted(d for d, s in kl.items() if s in REQ), sorted(d for d, s in kl.items() if s == "held_behind_question")],
                     "exact": [sorted(always), sorted(sometimes - always)],
                     "closed": [sorted(closed), []], "eager": [sorted(eager), []]}
    truth = {**ref["implicit_flags"], **ref["scenario"]}
    return {"family": fam, "flags": flags, "truth": "".join("T" if truth[f] else "F" for f in flags),
            "reference_requests": ref["request_set"], "documents": docs, "table": rows}


if __name__ == "__main__":
    shard, nshards, outdir = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    ids = sorted(claim_ids("dev") + claim_ids("test"))[shard::nshards]
    t0, out = time.time(), {}
    for cid in ids:
        out[cid] = table_for(cid)
    (outdir / f"s1_tables_{shard:02d}.json").write_text(json.dumps(out))
    print(f"shard {shard}: {len(ids)} claims, {sum(len(v['table']) for v in out.values())} assignments, {time.time()-t0:.1f}s")

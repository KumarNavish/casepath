"""Exact semantic comparison, no model: the product's `workflows.evaluate` against the paper engine.

For every family and every assignment of its flags to true / false / unknown (3^n), each non-optional document gets
one state per semantics:

  product (casepath-internal 55b8030, converted workflow, nothing on file, checked=True)
    R  in the checklist, required "yes", missing          (a request)
    H  in the checklist, required "depends"               (a hold: its own condition is open)
    W  not in the checklist while the walk waits at a question (`waiting_for` non-empty): the step that needs it lies
       beyond the stop. The product names the blocking question, but not for this document.
    S  not in the checklist and the walk is not waiting (skipped)
  paper strong Kleene (casepath-api causal_process_v1.evaluate):  R needed_now/needed_later, H held_behind_question, S other
  paper exact deferral (harness casepath_tenancy.supervaluate):    same mapping

    python3 compare.py [--layout serial|direct] [--product <worktree>] [--label x]
        -> prints counts, writes results/semantic_<layout>[_<label>].json (default product: the as-built worktree)
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert  # noqa: E402  (sets the import paths for casepath-api and the harness)

_PRODUCT = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--product"), "/home/user/work/casepath-ui3")
sys.path.insert(0, f"{_PRODUCT}/casepath-internal")
try:  # the product's package layout since 2821bf3, then the earlier one
    from casepath.process import workflows as product  # noqa: E402
except ImportError:
    from casepath_internal import workflows as product  # noqa: E402
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402
from casepath_api.causal_process_v1 import evaluate as paper_evaluate  # noqa: E402
from casepath_tenancy import supervaluate  # noqa: E402

REQ = {"needed_now", "needed_later"}


def paper_states(graph, assignment, exact):
    g = deepcopy(graph)
    for flag, v in assignment.items():
        g["conditions"][flag] = {**g["conditions"][flag], "verdict": v}
    if exact:
        states = supervaluate(g)["states"]
    else:
        states = {d["document_type"]: d["route_state"] for d in paper_evaluate(g)["documents"]}
    return {d: "R" if s in REQ else "H" if s == "held_behind_question" else "S" for d, s in states.items()}


def product_states(wf, family, assignment):
    facts = {"dispute_family": family}
    facts.update({f: (v == "true") for f, v in assignment.items() if v != "unresolved"})
    ev = product.evaluate(wf, facts, {}, checked=True)
    listed = {c["document"]: c for c in ev["documents"]}
    waiting = bool(ev["waiting_for"])
    out = {}
    for d in wf["documents"]:
        c = listed.get(d["id"])
        if c is None:
            out[d["id"]] = "W" if waiting else "S"
        elif c["required"] == "depends":
            out[d["id"]] = "H"
        elif c["required"] == "yes" and c["status"] == "missing":
            out[d["id"]] = "R"
        else:
            out[d["id"]] = "S"
    return out, [w["fact"] for w in ev["waiting_for"]]


def main(layout, label=None):
    templates = convert.load_templates("original")
    summary, rows = {}, []
    for family in convert.FAMILIES:
        wf = convert.convert(templates, family, layout)
        product.validate_workflow(wf)
        graph = convert.compiled(templates, family)
        optional = {d["id"] for d in wf["documents"] if d.get("optional")}
        flags = list(FAMILY_FLAGS[family])
        c = {"assignments": 0, "doc_decisions": 0, "agree_exact": 0, "agree_kleene": 0,
             "two_valued_assignments": 0, "two_valued_disagreements": 0,
             "product_holds_or_drops_required_by_every_completion": 0,
             "product_requires_doc_some_completion_makes_unnecessary": 0,
             "product_absent_where_exact_holds": 0, "product_absent_where_exact_holds_while_waiting": 0,
             "product_holds_where_exact_skips": 0, "product_skips_where_exact_requests": 0,
             "assignments_all_docs_agree_exact": 0, "pairs": {}}
        for bits in itertools.product(("true", "false", "unresolved"), repeat=len(flags)):
            a = dict(zip(flags, bits))
            p, waiting = product_states(wf, family, a)
            k = paper_states(graph, a, exact=False)
            x = paper_states(graph, a, exact=True)
            c["assignments"] += 1
            two = "unresolved" not in bits
            c["two_valued_assignments"] += two
            all_agree = True
            for d in sorted(p):
                if d in optional:
                    continue
                c["doc_decisions"] += 1
                pp = "H" if p[d] == "H" else "R" if p[d] == "R" else "W" if p[d] == "W" else "S"
                pc = pp if pp in {"R", "H"} else "S"  # product collapsed to request / hold / not listed
                c["agree_exact"] += pc == x[d]
                c["agree_kleene"] += pc == k[d]
                if pc != x[d]:
                    all_agree = False
                if two and pc != x[d]:
                    c["two_valued_disagreements"] += 1
                if x[d] == "R" and pc != "R":
                    c["product_holds_or_drops_required_by_every_completion"] += 1
                if pc == "R" and x[d] != "R":
                    c["product_requires_doc_some_completion_makes_unnecessary"] += 1
                if x[d] == "H" and pc == "S":
                    c["product_absent_where_exact_holds"] += 1
                    c["product_absent_where_exact_holds_while_waiting"] += pp == "W"
                if pc == "H" and x[d] == "S":
                    c["product_holds_where_exact_skips"] += 1
                key = f"product {pp} / exact {x[d]} / kleene {k[d]}"
                c["pairs"][key] = c["pairs"].get(key, 0) + 1
                rows.append({"family": family, "assignment": a, "document": d, "product": pp, "kleene": k[d],
                             "exact": x[d], "waiting_for": waiting})
            c["assignments_all_docs_agree_exact"] += all_agree
        summary[family] = c
    tot = {k: sum(summary[f][k] for f in summary) for k in summary[convert.FAMILIES[0]] if k != "pairs"}
    summary["total"] = tot
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    name = f"semantic_{layout}{'_' + label if label else ''}.json"
    (out / name).write_text(json.dumps({"layout": layout, "product": _PRODUCT, "summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default="serial", choices=["serial", "direct"])
    ap.add_argument("--product", default=None)
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    main(a.layout, a.label)

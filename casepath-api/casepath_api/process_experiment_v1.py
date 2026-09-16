"""Run every arm on one case under matched conditions, and score them against the reference contract.

Matching is enforced here rather than promised in a table: every arm receives the same authority passages,
the same case materials, the same document catalogue, the same already-held set, and the same model at the
same temperature. The only difference between arms is what sits between the sources and the checklist.

The two pipeline arms are assembled from the modules rather than prompted:
  B4  reference graph -> activation -> compiler   (ceiling)
  B5  induced graph   -> activation -> compiler   (the method)
Both use the identical compiler, so B4 minus B5 is graph quality and nothing else.
"""
from __future__ import annotations

import json, time
from typing import Any, Callable, Mapping, Sequence

from . import case_interpreter_v1 as ci
from . import checklist_baselines_v1 as bl
from . import obligation_compiler_v1 as oc
from . import process_evaluation_v1 as ev
from . import process_induction_v1 as pi

CONTRACT = "casepath.process-experiment/1.0.0"
ARMS = ("b1_direct", "b2_retrieval", "b3_graph_then_list", "b3t_summary_then_list",
        "b6_prior_composition", "b4_reference_graph", "b5_induced_graph")


def keyword_retriever(sources: Sequence[Mapping[str, Any]], case: Mapping[str, str], k: int):
    """A deliberately plain lexical retriever, so B2 and B6 are not advantaged or handicapped by a clever one."""
    import re
    text = " ".join(case.values()).lower()
    terms = set(re.findall(r"[a-zäöüß]{5,}", text))
    scored = []
    for s in sources:
        body = set(re.findall(r"[a-zäöüß]{5,}", s.get("exact_text", "").lower()))
        scored.append((len(body & terms), s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]


def _compile_all(graph, propositions, catalogue, call, workers=6):
    import concurrent.futures
    obl: dict[str, list] = {}
    for o in graph.get("obligations") or []:
        obl.setdefault(o.get("node_id"), []).append(o)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        compiled = list(pool.map(
            lambda n: oc.compile_node(n, obl.get(n["node_id"], []), propositions, call), graph["nodes"]))
    caps = [c for f in (x for c in compiled for x in c["facts"]) for c in f.get("capabilities") or []]
    batches = [caps[i:i + 12] for i in range(0, len(caps), 12)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        mapped = list(pool.map(lambda b: oc.map_documents(b, catalogue, call), batches))
    return compiled, [r for m in mapped for r in m["requirements"]]


def pipeline_arm(graph, propositions, case, catalogue, held, call, compiled=None, requirements=None):
    """B4 and B5 differ only in which graph comes in."""
    if compiled is None:
        compiled, requirements = _compile_all(graph, propositions, catalogue, call)
    decided = ci.decide(graph, case, call)
    state = ci.activate(graph, decided["verdicts"])
    chains = oc.build_chains(graph, state, compiled, requirements, propositions)
    cl = oc.checklist(chains, already_held=held)
    return {"requests": cl["requests"], "count": cl["count"],
            "documents": sorted({d for r in cl["requests"] for d in r["document_types"]}),
            "chains": chains["chains"], "activation": state,
            "verdicts": {k: v["verdict"] for k, v in decided["verdicts"].items()},
            "counts": chains["counts"], "compiled": compiled, "requirements": requirements}


def run_case(*, sources, propositions, case, catalogue, held, scope,
             induced_graph, reference_graph, call, arms: Sequence[str] = ARMS,
             cached: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cached = dict(cached or {})
    out: dict[str, Any] = {"contract": CONTRACT, "scope": scope, "arms": {}, "timing": {}}
    for arm in arms:
        t0 = time.time()
        try:
            if arm == "b1_direct":
                r = bl.b1_direct(sources, case, catalogue, held, call)
            elif arm == "b2_retrieval":
                r = bl.b2_retrieval(sources, case, catalogue, held, call, keyword_retriever)
            elif arm == "b3_graph_then_list":
                r = bl.b3_graph_then_list(sources, case, induced_graph, catalogue, held, call)
            elif arm == "b3t_summary_then_list":
                r = bl.b3t_summary_then_list(sources, case, scope, catalogue, held, call)
            elif arm == "b6_prior_composition":
                r = bl.b6_prior_composition(sources, case, catalogue, held, call, keyword_retriever)
            elif arm == "b4_reference_graph":
                c = cached.get("b4") or {}
                r = pipeline_arm(reference_graph, propositions, case, catalogue, held, call,
                                 c.get("compiled"), c.get("requirements"))
                cached["b4"] = {"compiled": r["compiled"], "requirements": r["requirements"]}
            elif arm == "b5_induced_graph":
                c = cached.get("b5") or {}
                r = pipeline_arm(induced_graph, propositions, case, catalogue, held, call,
                                 c.get("compiled"), c.get("requirements"))
                cached["b5"] = {"compiled": r["compiled"], "requirements": r["requirements"]}
            else:
                continue
            out["arms"][arm] = {k: v for k, v in r.items() if k not in ("compiled", "requirements")}
        except Exception as exc:
            out["arms"][arm] = {"error": f"{type(exc).__name__}: {exc}"[:300], "requests": [],
                                "documents": [], "chains": []}
        out["timing"][arm] = round(time.time() - t0, 1)
    out["_cached"] = cached
    return out


def score_case(run: Mapping[str, Any], reference: Mapping[str, Any],
               critical: Sequence[str] = ()) -> dict[str, Any]:
    return {arm: ev.checklist_quality(reference, a.get("documents") or [], a.get("chains") or [], critical)
            for arm, a in run["arms"].items()}


def score_intervention(before: Mapping[str, Any], after: Mapping[str, Any],
                       expected_withdrawn: Sequence[str], expected_added: Sequence[str] = ()) -> dict[str, Any]:
    out = {}
    for arm in before["arms"]:
        if arm not in after["arms"]:
            continue
        b, a = before["arms"][arm], after["arms"][arm]
        out[arm] = ev.causal_consistency(
            {"requested": b.get("documents") or [], "chains": b.get("chains") or []},
            {"requested": a.get("documents") or [], "chains": a.get("chains") or []},
            expected_withdrawn, expected_added)
    return out

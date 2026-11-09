"""S2 (sciCORE): engine runtime on synthetic process graphs within the product's
bounds (<=100 nodes, <=300 relationships, <=100 documents), and the cost of
exact deferral as the number of open flags grows. Usage: s2_scalability.py OUT"""
import json
import random
import statistics
import sys
import time
from copy import deepcopy
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference, templates  # noqa: E402
from casepath_tenancy import compile_process, evaluate, seal_graph  # noqa: E402
from casepath_api.causal_process_v1 import TRUE  # noqa: E402

rng = random.Random(20261109)
base_id = claim_ids("dev")[0]
ref = reference(base_id)
verified = {"category": {"family": ref["family"], "summary": "", "citations": []},
            "conditions": [{"flag": f, "verdict": "true", "summary": "", "citations": []} for f in ref["scenario"]],
            "documents": [], "steps": [], "item_rejections": []}
BASE, _, _ = compile_process(templates(), base_id, verified)
NODE, EDGE, DOC = BASE["nodes"][1], BASE["edges"][1], BASE["document_catalog"][0]


def cond(flags):
    """Random condition in the engine's closed grammar."""
    k = rng.random()
    if k < 0.4:
        return {"flag": rng.choice(flags)}
    if k < 0.6:
        return {"not": {"flag": rng.choice(flags)}}
    if k < 0.8:
        return {"all": [{"flag": rng.choice(flags)}, {"not": {"flag": rng.choice(flags)}}]}
    return {"any": [{"flag": rng.choice(flags)}, {"flag": rng.choice(flags)}]}


def make_graph(n, n_flags):
    flags = [f"f{i}" for i in range(n_flags)]
    g = deepcopy(BASE)
    g["conditions"] = {f: {"flag": f, "verdict": "true", "summary": "", "citations": [], "worker": "synthetic"} for f in flags}
    nodes, edges = [], []
    for i in range(n):
        node = deepcopy(NODE)
        node.update(node_id=f"n{i}", label=f"Step {i}", meaning=f"Step {i}", entry=(i == 0), completed=False,
                    condition=cond(flags) if i and rng.random() < 0.4 else deepcopy(TRUE),
                    document_types=[f"d{i}"])
        nodes.append(node)
        if i:
            for j in rng.sample(range(i), min(i, rng.choice([1, 1, 2, 3]))):
                if len(edges) >= 300:
                    break
                e = deepcopy(EDGE)
                e.update(edge_id=f"e{len(edges)}", source_node_id=f"n{j}", target_node_id=f"n{i}", label=f"e{len(edges)}",
                         relation="branches_to", condition=cond(flags) if rng.random() < 0.5 else deepcopy(TRUE))
                edges.append(e)
    docs = []
    for i in range(n):
        d = deepcopy(DOC)
        d.update(document_type=f"d{i}", label=f"Document {i}", condition_flag=None, held_files=[],
                 condition=cond(flags) if rng.random() < 0.3 else deepcopy(TRUE),
                 requirement_class="mandatory")
        docs.append(d)
    g.update(nodes=nodes, edges=edges, document_catalog=docs)
    return seal_graph(g), flags


def timeit(fn, reps):
    vals = []
    for _ in range(reps):
        t = time.perf_counter(); fn(); vals.append(time.perf_counter() - t)
    return statistics.median(vals)


if __name__ == "__main__":
    out = {"evaluate": [], "exact": []}
    for n in (10, 25, 50, 100):
        for rep in range(5):
            g, flags = make_graph(n, 20)
            out["evaluate"].append({"nodes": n, "edges": len(g["edges"]), "documents": len(g["document_catalog"]),
                                    "seconds": timeit(lambda: evaluate(g), 15)})
    g, flags = make_graph(100, 20)
    for u in range(0, 11, 2):
        open_flags = flags[:u]

        def exact():
            for bits in product(("true", "false"), repeat=u):
                evaluate(g, conditions=dict(zip(open_flags, bits)) or None)
        out["exact"].append({"open_flags": u, "evaluations": 2 ** u, "seconds": timeit(exact, 3 if u < 8 else 1)})
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
    print(json.dumps({"evaluate_100_nodes_ms": 1000 * statistics.median(r["seconds"] for r in out["evaluate"] if r["nodes"] == 100),
                      "exact_10_open_s": out["exact"][-1]["seconds"]}))

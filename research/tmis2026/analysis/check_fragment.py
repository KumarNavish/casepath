"""Check the claims of the paper's Appendix A ("The tested workflows are flow workflows", "The plain walk on theft")
against the product's own evaluator at the tested commit. No model calls, no network; deterministic.

    python3 analysis/check_fragment.py

The product's `casepath/process/workflows.py` is taken from commit 6a72159c of this repository exactly as
analysis/study3.py takes it (study3.load_evaluator: `git archive` of the commit into a temporary folder), so the
commit must be in the clone (`git fetch origin claude/casepath-internal-paper-sync-20261110d`). The workflows are the
four of Study 3: the three tenancy workflows of harness/product/workflows/fresh-serial-sync and the theft workflow of
harness/product/workflows/theft-reviewed (the catalogues named in analysis/study3_spec.json).

Checks, for each tenancy workflow:
  1. Structure: the step graph is acyclic; wherever two transitions of one step can hold together under a complete
     assignment, every target that holds is reachable from the first one (the product's walk follows the first
     transition that holds), so both lead to the same later steps.
  2. Every complete two-valued assignment of the facts its conditions use: the documents the product's walk lists
     (workflows._walk) equal those of Equations (1)-(2) (activation over all transitions, strong Kleene).
  3. Every three-valued assignment of those facts: the product's evaluate() requests, holds and leaves out exactly what
     Equation (4) gives (exact deferral over the two-valued completions of Equations (1)-(2)).
  Optional documents are left out of 2 and 3: the product lists them but never requests or holds them.
For the theft workflow:
  4. Structure: one step, no transitions.
  5. 5,000 random three-valued assignments (random.Random(1); each fact true, false, open, open with equal chance):
     the product's evaluate() requests and holds exactly what Equation (4) gives, document by document. The number
     of assignments evaluated by the plain walk (more than eight open facts) is printed.

The counts the appendix states are written below (APPENDIX). The exit status is 1 if any comparison disagrees or any
count differs from the appendix. Written for the release; the same checks were first run by scratch scripts whose
paths were fixed to one container.
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import study3 as s3  # noqa: E402  (load_evaluator: the product's evaluator from a commit, via git archive)

SPEC = json.loads((HERE / "study3_spec.json").read_text())
APPENDIX = {"complete": [32, 32, 8], "three_valued": [243, 243, 27], "theft_random": 5000}
THEFT_SEED = 1


def kor(x, y):
    return True if (x is True or y is True) else (None if (x is None or y is None) else False)


def kand(x, y):
    return False if (x is False or y is False) else (None if (x is None or y is None) else True)


def topological(w):
    steps = {s["id"]: s for s in w["steps"]}
    order, seen = [], set()

    def visit(u):
        if u in seen:
            return
        seen.add(u)
        for e in steps[u].get("next", []):
            visit(e["to"])
        order.append(u)
    for s in steps:
        visit(s)
    return steps, order[::-1]


def acyclic(w):
    steps = {s["id"]: s for s in w["steps"]}
    state = {}

    def dfs(u):
        state[u] = 1
        for e in steps[u].get("next", []):
            v = e["to"]
            if state.get(v) == 1 or (state.get(v) is None and not dfs(v)):
                return False
        state[u] = 2
        return True
    return all(state.get(s) == 2 or dfs(s) for s in steps)


def eq12(W, w, a):
    """Equations (1)-(2): a step is active if it is the start or some transition into it from an active step holds
    (strong Kleene over all transitions); a document is needed if a step that lists it is active and its own
    condition holds."""
    steps, order = topological(w)
    K = lambda c: W.evaluate_condition(c if c is not None else True, a)  # noqa: E731
    act = {}
    for u in order:
        v = u == w["start"]
        for p in order:
            if p not in act:
                continue
            for e in steps[p].get("next", []):
                if e["to"] == u:
                    v = kor(v, kand(act[p], K(e.get("when", True))))
        act[u] = v
    req = {}
    for d in w["documents"]:
        r = False
        for s in steps:
            if d["id"] in steps[s].get("documents", []):
                r = kor(r, act[s])
        req[d["id"]] = kand(r, K(d.get("required_when")))
    return req


def reachable(w, u):
    steps = {s["id"]: s for s in w["steps"]}
    seen, todo = set(), [u]
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo += [e["to"] for e in steps[x].get("next", [])]
    return seen


def overlapping_transitions(W, w):
    """Steps where two transitions can hold together under a complete assignment, with whether the product's walk
    (first transition that holds) still reaches every other target that holds, so that both lead to the same later
    steps: (step, True/False)."""
    out = []
    for s in w["steps"]:
        edges = s.get("next", [])
        if len(edges) < 2:
            continue
        fs = sorted(set().union(*[W.condition_facts(e.get("when", True)) for e in edges]))
        overlap, converge = False, True
        for vals in itertools.product([True, False], repeat=len(fs)):
            a = dict(zip(fs, vals))
            hold = [e["to"] for e in edges if W.evaluate_condition(e.get("when", True), a) is True]
            if len(hold) > 1:
                overlap = True
                converge &= set(hold) <= reachable(w, hold[0])
        if overlap:
            out.append((s["id"], converge))
    return out


def check_tenancy(W, path):
    w = json.loads(path.read_text())
    used = sorted(W._used_facts(w))
    opt = {x["id"]: bool(x.get("optional")) for x in w["documents"]}
    complete = walk_bad = 0
    for vals in itertools.product([True, False], repeat=len(used)):
        a = dict(zip(used, vals))
        prod = {c["document"] for c in W._walk(w, a, {}, checked=True)["documents"] if c["required"] != "optional"}
        mine = {d for d, r in eq12(W, w, a).items() if r is True and not opt[d]}
        complete += 1
        walk_bad += prod != mine
    three = eval_bad = 0
    for vals in itertools.product([True, False, None], repeat=len(used)):
        a = {f: v for f, v in zip(used, vals) if v is not None}
        ev = W.evaluate(w, a, {}, checked=True)
        prod = {c["document"]: ("H" if c["required"] == "depends" else "R") for c in ev["documents"]
                if c["required"] != "optional"}
        openf = [f for f in used if f not in a]
        comps = [eq12(W, w, {**a, **dict(zip(openf, cv))}) for cv in itertools.product([True, False], repeat=len(openf))]
        mine = {}
        for d in (x["id"] for x in w["documents"] if not opt[x["id"]]):
            vs = {c[d] for c in comps}
            if vs == {True}:
                mine[d] = "R"
            elif vs != {False}:
                mine[d] = "H"
        three += 1
        eval_bad += prod != mine
    return {"workflow": path.name, "facts": len(used), "acyclic": acyclic(w),
            "overlapping_transitions": overlapping_transitions(W, w),
            "complete": complete, "walk_disagrees": walk_bad, "three_valued": three, "evaluate_disagrees": eval_bad}


def check_theft(W, path):
    w = json.loads(path.read_text())
    used = sorted(W._used_facts(w))
    one_step = len(w["steps"]) == 1 and not w["steps"][0].get("next")
    rnd = random.Random(THEFT_SEED)
    bad = n = plain = 0
    for _ in range(APPENDIX["theft_random"]):
        a = {}
        for f in used:
            v = rnd.choice([True, False, None, None])
            if v is not None:
                a[f] = v
        ev = W.evaluate(w, a, {}, checked=True)
        plain += (ev.get("deferral") or {}).get("mode") != "exact"
        prod = {c["document"]: ("H" if c["required"] == "depends" else "R") for c in ev["documents"]}
        mine = {}
        for d in w["documents"]:
            cond = d.get("required_when", True)
            openf = [f for f in sorted(W.condition_facts(cond)) if f not in a]
            vs = {W.evaluate_condition(cond, {**a, **dict(zip(openf, cv))})
                  for cv in itertools.product([True, False], repeat=len(openf))}
            if vs == {True}:
                mine[d["id"]] = "R"
            elif vs != {False}:
                mine[d["id"]] = "H"
        n += 1
        bad += prod != mine
    return {"workflow": path.name, "facts": len(used), "one_step_no_transitions": one_step, "random": n,
            "not_exact_mode": plain, "evaluate_disagrees": bad}


def main():
    ok = True
    ev = SPEC["product_evaluator"]
    W = s3.load_evaluator(ev["tenancy"]["package"])
    print(f"product evaluator: casepath/process/workflows.py at {ev['tenancy']['package']['commit'][:12]}")
    rows = [check_tenancy(W, p) for p in sorted((TMIS / ev["tenancy"]["catalogue"]).glob("*.json"))]
    for r in rows:
        good = r["acyclic"] and all(same for _, same in r["overlapping_transitions"]) and not r["walk_disagrees"] \
            and not r["evaluate_disagrees"]
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {r['workflow']}: {r['facts']} facts; acyclic {r['acyclic']}; steps with "
              f"transitions that can hold together {r['overlapping_transitions'] or 'none'}; complete assignments "
              f"{r['complete']}, walk differs from Eq. (1)-(2) in {r['walk_disagrees']}; three-valued assignments "
              f"{r['three_valued']}, evaluate differs from Eq. (4) in {r['evaluate_disagrees']}")
    got = {"complete": [r["complete"] for r in rows], "three_valued": [r["three_valued"] for r in rows]}
    for k in ("complete", "three_valued"):
        same = sorted(got[k]) == sorted(APPENDIX[k])
        ok &= same
        print(f"{'PASS' if same else 'FAIL'} counts of {k} assignments {got[k]}; Appendix A says {APPENDIX[k]}")
    W = s3.load_evaluator(ev["theft"]["package"])
    for p in sorted((TMIS / ev["theft"]["catalogue"]).glob("*.json")):
        t = check_theft(W, p)
        good = t["one_step_no_transitions"] and not t["evaluate_disagrees"] and t["random"] == APPENDIX["theft_random"]
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {t['workflow']}: {t['facts']} facts; one step without transitions "
              f"{t['one_step_no_transitions']}; random three-valued assignments {t['random']} (seed {THEFT_SEED}; "
              f"Appendix A says {APPENDIX['theft_random']}), of which {t['not_exact_mode']} evaluated by the plain walk; "
              f"evaluate differs from Eq. (4) in {t['evaluate_disagrees']}")
    print("ALL FRAGMENT CHECKS PASSED" if ok else "SOME FRAGMENT CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

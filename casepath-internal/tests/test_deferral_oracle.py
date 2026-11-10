"""Brute-force oracle for exact deferral, independent of the code under test.

The reference is the plain walk frozen at commit 55b8030 (tests/oracle_walk.py). For each case the oracle enumerates
every completion of the open facts itself (yes/no, an enum's values, the named values of a text fact plus another value,
and "stays unknown" for a fact a condition asks to be known), walks each completion with the frozen walk, and derives
the expected checklist, path, steps beyond, and waiting questions. Random workflows cover branches, rejoins, loops,
gates over known/unknown, conditional documents and enum and text facts."""
import copy
import itertools
import random
import time
import unittest

from casepath.process import workflows
from tests import oracle_walk as ref

UNSET = "<stays unknown>"


def used(wf):
    out = set()
    for s in wf["steps"]:
        for e in s.get("next", []):
            out |= ref.condition_facts(e.get("when", True))
    for d in wf["documents"]:
        out |= ref.condition_facts(d.get("required_when", True))
    return out


def visit_all(wf, fn):
    def visit(c):
        if not isinstance(c, dict):
            return
        for k in ("all", "any"):
            for ch in c.get(k, ()):
                visit(ch)
        if "not" in c:
            visit(c["not"])
        fn(c)
    for s in wf["steps"]:
        for e in s.get("next", []):
            visit(e.get("when"))
    for d in wf["documents"]:
        visit(d.get("required_when"))


def domain(wf, fid):
    fact = next(f for f in wf["facts"] if f["id"] == fid)
    if fact["type"] == "boolean":
        out = [True, False]
    elif fact["type"] == "enum":
        out = list(fact["values"])
    else:
        named = []
        visit_all(wf, lambda c: named.extend(v for v in c.get("in", [c["is"]] if "is" in c else [])
                                             if c.get("fact") == fid and v not in named))
        out = named + ["<another value>"]
    asked = []
    visit_all(wf, lambda c: asked.append(c.get("fact")) if "known" in c else None)
    return out + ([UNSET] if fid in asked else [])


def expected(wf, facts, findings, checked):
    open_ = sorted(f for f in used(wf) if facts.get(f) is None)
    base = ref.evaluate(wf, facts, findings, checked=checked)
    if not open_:
        return {"plain": base}
    doms = [domain(wf, f) for f in open_]
    comps = []
    for vals in itertools.product(*doms):
        answer = {f: v for f, v in zip(open_, vals) if v != UNSET}
        run = ref.evaluate(wf, {**facts, **answer}, findings, checked=checked)
        comps.append((vals, [p["step"] for p in run["path"]], {d["document"] for d in run["documents"]}))
    n = len(comps)

    def deciders(member):
        out = []
        for i, f in enumerate(open_):
            groups = {}
            for vals, steps, docs in comps:
                groups.setdefault(vals[:i] + vals[i + 1:], set()).add(member(steps, docs))
            if any(len(g) > 1 for g in groups.values()):
                out.append(f)
        return out

    path = []
    for p in base["path"]:
        if not all(p["step"] in steps for _v, steps, _d in comps):
            break
        path.append(p["step"])
    beyond = {}
    for _v, steps, _d in comps:
        for s in steps:
            if s not in path and s not in beyond:
                c = sum(s in st for _v2, st, _d2 in comps)
                beyond[s] = ("reached", []) if c == n else ("pending", deciders(lambda st, ds, s=s: s in st))
    docs = {}
    for d in wf["documents"]:
        c = sum(d["id"] in ds for _v, _s, ds in comps)
        if c:
            docs[d["id"]] = ("fixed", []) if c == n else ("depends", deciders(lambda st, ds, i=d["id"]: i in ds))
    waiting = sorted(set().union(*[set(q) for _k, q in list(beyond.values()) + list(docs.values())]))
    return {"path": path, "beyond": beyond, "docs": docs, "waiting": waiting, "completions": n}


def rand_cond(rng, facts, depth=0):
    r = rng.random()
    if depth < 2 and r < 0.25:
        return {rng.choice(["all", "any"]): [rand_cond(rng, facts, depth + 1) for _ in range(rng.randint(1, 3))]}
    if depth < 2 and r < 0.35:
        return {"not": rand_cond(rng, facts, depth + 1)}
    f = rng.choice(facts)
    if f["type"] == "boolean":
        return {"fact": f["id"], "is": rng.choice([True, False])}
    if f["type"] == "enum":
        if rng.random() < 0.5:
            return {"fact": f["id"], "is": rng.choice(f["values"])}
        return {"fact": f["id"], "in": rng.sample(f["values"], rng.randint(1, len(f["values"])))}
    if rng.random() < 0.3:
        return {"fact": f["id"], "known": rng.choice([True, False])}
    return {"fact": f["id"], "is": rng.choice(["a", "b"])}


def rand_wf(rng):
    facts = []
    for i in range(rng.randint(1, 5)):
        t = rng.choice(["boolean", "boolean", "boolean", "enum", "text"])
        f = {"id": f"f{i}", "type": t, "question": f"Q{i}?", "source_refs": ["s#f"]}
        if t == "enum":
            f["values"] = ["x", "y", "z"][: rng.randint(2, 3)]
        facts.append(f)
    ns = rng.randint(3, 9)
    steps = [{"id": f"s{i}", "title": f"S{i}", "source_refs": ["s#s"]} for i in range(ns)]
    docs = []
    for j in range(rng.randint(1, 6)):
        d = {"id": f"d{j}", "title": f"D{j}", "why": "w", "source_refs": ["s#d"]}
        if rng.random() < 0.4:
            d["required_when"] = rand_cond(rng, facts)
        docs.append(d)
    for i, s in enumerate(steps):
        if i == ns - 1 or (i > 1 and rng.random() < 0.15):
            s["outcome"] = rng.choice(["o1", "o2"])
            continue
        later = list(range(i + 1, ns))
        edges = [{"to": f"s{t}", "when": rand_cond(rng, facts)} for t in rng.sample(later, rng.randint(1, min(3, len(later))))]
        if rng.random() < 0.6:
            edges[-1]["when"] = True
        if rng.random() < 0.08 and i > 0:
            edges.insert(0, {"to": f"s{rng.randint(0, i)}", "when": rand_cond(rng, facts)})
        if rng.random() < 0.3:  # a rejoin: two plain branch steps meeting one step later
            pass
        s["next"] = edges
        if rng.random() < 0.5:
            s["documents"] = rng.sample([d["id"] for d in docs], rng.randint(1, min(2, len(docs))))
    for i, s in enumerate(steps[:-1]):
        if "next" in s and not any(e["to"] == f"s{i + 1}" for e in s["next"]) and rng.random() < 0.5:
            s["next"].append({"to": f"s{i + 1}", "when": True})
    wf = {"format": "casepath.workflow/1", "id": "r", "version": "1", "title": "R", "status": "draft",
          "sources": [{"id": "s", "kind": "process_guidance", "title": "s"}], "facts": facts, "start": "s0",
          "steps": steps, "documents": docs,
          "outcomes": [{"id": "o1", "title": "O1", "source_refs": ["s#o"]}, {"id": "o2", "title": "O2", "source_refs": ["s#o"]}]}
    try:
        ref.validate_workflow(copy.deepcopy(wf))
    except ref.CatalogueError:
        return None
    return wf


def check(test, wf, facts, findings, checked):
    got = workflows.evaluate(wf, facts, findings, checked=checked)
    exp = expected(wf, facts, findings, checked)
    if "plain" in exp:
        test.assertEqual(got, exp["plain"])
        return "plain"
    if got.get("deferral", {}).get("mode") == "first_open_branch":
        test.assertGreater(exp["completions"], 2 ** workflows.MAX_OPEN_FACTS)
        return "cap"
    test.assertEqual([p["step"] for p in got["path"]], exp["path"])
    test.assertEqual({b["step"]: (b["state"], b.get("depends_on", [])) for b in got["beyond"]}, exp["beyond"])
    gd = {d["document"]: d for d in got["documents"]}
    test.assertEqual(set(gd), set(exp["docs"]))
    for doc, (kind, q) in exp["docs"].items():
        if kind == "depends":
            test.assertEqual((gd[doc]["required"], [x["fact"] for x in gd[doc]["questions"]]), ("depends", q))
        else:
            test.assertNotEqual(gd[doc]["required"], "depends")
    test.assertEqual([w["fact"] for w in got["waiting_for"]], exp["waiting"])
    for p in got["path"]:  # every step on the path is reached under every answer
        test.assertNotIn(p["step"], {b["step"] for b in got["beyond"]})
    return "exact"


class OracleTests(unittest.TestCase):
    def test_random_workflows_match_the_brute_force_oracle(self):
        rng, counts, made = random.Random(20261110), {"plain": 0, "exact": 0, "cap": 0}, 0
        while made < 250:
            wf = rand_wf(rng)
            if wf is None:
                continue
            made += 1
            for _ in range(8):
                facts = {f["id"]: rng.choice([v for v in domain(wf, f["id"]) if v != UNSET])
                         for f in wf["facts"] if rng.random() < 0.5}
                with self.subTest(workflow=made, facts=facts):
                    counts[check(self, wf, facts, {}, rng.random() < 0.5)] += 1
        self.assertGreater(counts["exact"], 500)

    def test_a_rejoin_over_branches_that_miss_an_answer_does_not_pass_the_join(self):
        wf = {"format": "casepath.workflow/1", "id": "j", "version": "1", "title": "J", "status": "draft",
              "sources": [{"id": "s", "kind": "process_guidance", "title": "s"}],
              "facts": [{"id": "kind", "type": "text", "question": "Which kind?", "source_refs": ["s#k"]}], "start": "a",
              "steps": [{"id": "a", "title": "A", "source_refs": ["s#a"],
                         "next": [{"to": "b1", "when": {"fact": "kind", "is": "x"}}, {"to": "b2", "when": {"fact": "kind", "is": "y"}}]},
                        {"id": "b1", "title": "B1", "source_refs": ["s#b"], "next": [{"to": "join", "when": True}]},
                        {"id": "b2", "title": "B2", "source_refs": ["s#b"], "next": [{"to": "join", "when": True}]},
                        {"id": "join", "title": "Join", "source_refs": ["s#j"], "documents": ["form"], "outcome": "o"}],
              "documents": [{"id": "form", "title": "Form", "why": "w", "source_refs": ["s#f"]}],
              "outcomes": [{"id": "o", "title": "O", "source_refs": ["s#o"]}]}
        workflows.validate_workflow(wf)
        self.assertEqual([p["step"] for p in ref.evaluate(wf, {})["path"]], ["a", "join"])  # the old shortcut
        got = workflows.evaluate(wf, {}, {}, checked=True)
        self.assertEqual([(p["step"], p["state"]) for p in got["path"]], [("a", "current")])
        self.assertEqual(got["current"]["step"], "a")
        self.assertIsNone(got["outcome"])
        self.assertEqual({d["document"]: d["required"] for d in got["documents"]}, {"form": "depends"})
        self.assertEqual({b["step"]: b["state"] for b in got["beyond"]}, {"b1": "pending", "b2": "pending", "join": "pending"})
        check(self, wf, {}, {}, True)

    def test_a_fact_asked_to_be_known_can_also_stay_unknown(self):
        data = copy.deepcopy(ref_fixture())
        data["facts"].append({"id": "party", "type": "text", "question": "Who is the other party?", "source_refs": ["fixture#p"]})
        assess = next(s for s in data["steps"] if s["id"] == "assess")
        assess.pop("outcome")
        assess["next"] = [{"to": "done", "when": {"all": [{"fact": "party", "known": True}]}},
                          {"to": "assess", "when": {"any": [{"fact": "party", "known": False}]}}]
        data["documents"].append({"id": "report_form", "title": "Report form", "why": "w", "source_refs": ["fixture#d9"]})
        data["steps"].append({"id": "done", "title": "Report", "source_refs": ["fixture#d"], "outcome": "reported", "documents": ["report_form"]})
        workflows.validate_workflow(data)
        got = workflows.evaluate(data, {"landlord_notified": True}, {}, checked=True)
        rows = {d["document"]: d["required"] for d in got["documents"]}
        self.assertEqual(rows["report_form"], "depends")
        self.assertEqual([w["fact"] for w in got["waiting_for"]], ["party"])
        check(self, data, {"landlord_notified": True}, {}, True)


class TimingTests(unittest.TestCase):
    def test_a_long_workflow_at_the_cap_evaluates_quickly(self):
        n = workflows.MAX_OPEN_FACTS
        facts = [{"id": f"f{i}", "type": "boolean", "question": "q", "source_refs": ["s#x"]} for i in range(n)]
        steps = []
        for i in range(150):
            s = {"id": f"s{i}", "title": "t", "source_refs": ["s#x"]}
            if i == 149:
                s["outcome"] = "o"
            else:
                s["next"] = [{"to": f"s{i + 1}", "when": {"fact": f"f{i % n}", "is": True}}, {"to": f"s{min(i + 2, 149)}", "when": True}]
                s["documents"] = [f"d{i % 60}"]
            steps.append(s)
        docs = [{"id": f"d{j}", "title": "d", "why": "w", "source_refs": ["s#x"], "required_when": {"fact": f"f{j % n}", "is": True}}
                for j in range(60)]
        wf = workflows.validate_workflow({"format": "casepath.workflow/1", "id": "p", "version": "1", "title": "p", "status": "draft",
                                          "sources": [{"id": "s", "kind": "process_guidance", "title": "s"}], "facts": facts,
                                          "start": "s0", "steps": steps, "documents": docs,
                                          "outcomes": [{"id": "o", "title": "o", "source_refs": ["s#x"]}]})
        best = min(self._time(wf) for _ in range(3))
        self.assertLess(best, 0.1)
        wider = copy.deepcopy(wf)
        wider["facts"].append({"id": "extra", "type": "boolean", "question": "q", "source_refs": ["s#x"]})
        wider["documents"][0]["required_when"] = {"all": [{"fact": "f0", "is": True}, {"fact": "extra", "is": True}]}
        self.assertEqual(workflows.evaluate(wider, {}, {}, checked=True)["deferral"]["mode"], "first_open_branch")

    @staticmethod
    def _time(wf):
        start = time.perf_counter()
        result = workflows.evaluate(wf, {}, {}, checked=True)
        assert result["deferral"]["mode"] == "exact"
        return time.perf_counter() - start


def ref_fixture():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())


if __name__ == "__main__":
    unittest.main()

"""Check the theft rule set. Run with `python3 -I tools/check.py`; exit status 1 on any failure.

1. every passage (and context passage) of every rule occurs character for character in its stored snapshot, has at
   most 60 words, and the snapshot's SHA-256 is the one in sources/SOURCES.json;
2. every rule has a known basis; 'follows' and 'evidence' carry an inference;
3. every fact and document referenced in a condition, step, document, presumption or stop exists; the defining event
   is a fact of its type; the convention rule is present with basis 'convention';
4. the workflows pass the product's own validate_workflow (frozen worktree, loaded read-only) and carry the same facts,
   steps, documents and stops as rules.json;
5. under every assignment of true/false to a type's facts, the product's evaluator reaches exactly the steps whose
   reached_when holds, ends in exactly the stop whose condition holds, and requires exactly the documents whose step is
   reached and whose needed_when holds (mandatory -> 'yes', not mandatory -> 'optional');
6. SPEC.md 6a/6b: each branch fact carries exactly one 'unstated' presumption (value false) pointing to the convention
   source, except the defining event, a fact whose value false triggers a stop, and an always_stated fact, which carry
   none; walking every assignment in which each branch fact is true, false or unmentioned (defining event stated true):
   no stop is reached through an unmentioned fact, and no document need is created by a fact being unmentioned;
7. size per SPEC.md item 5;
8. the paragraph 'How to read steps and stops' is the fixed words and identical in rules.json and rule_text.md.
Prints counts of types, facts, steps, documents, presumptions, stops and rules by basis.
"""
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = Path("/home/user/work/casepath-sync-e/casepath-internal/casepath/process/workflows.py")
BASES = {"states", "follows", "evidence"}
FAIL = []


def fail(msg):
    FAIL.append(msg)
    print("FAIL", msg)


def load_product():
    sys.dont_write_bytecode = True  # never leave a cache file in the read-only product worktree
    spec = importlib.util.spec_from_file_location("product_workflows", PRODUCT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def all_rules(t):
    for kind in ("facts", "steps", "documents", "presumptions", "stops"):
        for item in t[kind]:
            yield kind, item.get("id", item.get("fact")), item["rule"]


def stop_on_false(t):
    found = set()

    def visit(c):
        if isinstance(c, dict):
            for k in ("all", "any"):
                for x in c.get(k, ()):
                    visit(x)
            if c.get("is") is False:
                found.add(c["fact"])
    for s in t["stops"]:
        visit(s["when"])
    return found


# The general paragraph on reading steps and stops: the same words in all three regimes (tenancy, theft, dismissal).
STOPS_READING = ("Steps are taken in the order given. A document belongs to a step and is decided when that step is "
                 "reached. A stop ends the process at its step: no later step is reached, and no document of a later "
                 "step is requested or left waiting. Documents of steps reached before the stop keep the state they had; "
                 "a document requested there remains requested.")


def check_stops_reading(rules, rule_text, report):
    """The paragraph 'How to read steps and stops': fixed words, present and identical in rules.json and rule_text.md,
    once, in the general part (before the convention section)."""
    if rules.get("reading_of_stops") != STOPS_READING:
        report("rules.json: reading_of_stops missing or not the fixed words")
    block = "## How to read steps and stops\n\n" + STOPS_READING + "\n\n"
    conv = rule_text.find("## Convention of this benchmark (not law)")
    if rule_text.count("## How to read steps and stops") != 1 or block not in rule_text \
            or not 0 <= rule_text.find(block) < conv:
        report("rule_text.md: 'How to read steps and stops' missing, repeated, not the fixed words, or not in the "
               "general part")
    if rules.get("reading_of_stops", "") not in rule_text:
        report("rule_text.md and rules.json: reading_of_stops differs")


def main():
    product = load_product()
    data = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
    check_stops_reading(data, (ROOT / "rule_text.md").read_text(encoding="utf-8"), fail)
    sources = json.loads((ROOT / "sources" / "SOURCES.json").read_text(encoding="utf-8"))
    snaps = {}
    for s in sources["sources"]:
        path = ROOT / "sources" / s["snapshot"]
        snaps[s["id"]] = path.read_text(encoding="utf-8")
        if hashlib.sha256(path.read_bytes()).hexdigest() != s["snapshot_sha256"]:
            fail(f"snapshot {s['snapshot']}: SHA-256 differs from SOURCES.json")

    # 1-3: passages, bases, references
    conv = data.get("convention")
    if not conv or conv["rule"].get("basis") != "convention":
        fail("convention rule missing or without basis 'convention'")
    by_basis = {}
    catalogue = set()
    routing = data.get("routing")
    if not routing:
        fail("routing fact missing from rules.json")
    else:
        for c in [routing["rule"]] + routing["rule"].get("context", []):
            if c["source_id"] not in snaps or c["passage"] not in snaps[c["source_id"]]:
                fail(f"routing: passage not verbatim in {c['source_id']} snapshot: {c['passage'][:60]}")
            if len(c["passage"].split()) > 60:
                fail("routing: passage over 60 words")
        if set(routing["values"]) != {t["id"] for t in data["types"]} | {"other"}:
            fail("routing values differ from the types plus 'other'")
    for t in data["types"]:
        facts = {f["id"] for f in t["facts"]}
        steps = {s["id"] for s in t["steps"]}
        docs = {d["id"] for d in t["documents"]}
        catalogue |= docs
        if t["defining_event"] not in facts:
            fail(f"{t['id']}: defining event is not a fact")
        for kind, ident, r in all_rules(t):
            by_basis[r["basis"]] = by_basis.get(r["basis"], 0) + 1
            if r["basis"] not in BASES:
                fail(f"{t['id']} {kind} {ident}: basis {r['basis']}")
            if r["basis"] in ("follows", "evidence") and not r.get("inference"):
                fail(f"{t['id']} {kind} {ident}: {r['basis']} without inference")
            for c in [r] + r.get("context", []):
                if c["source_id"] not in snaps or c["passage"] not in snaps[c["source_id"]]:
                    fail(f"{t['id']} {kind} {ident}: passage not verbatim in {c['source_id']} snapshot: {c['passage'][:60]}")
                if len(c["passage"].split()) > 60:
                    fail(f"{t['id']} {kind} {ident}: passage over 60 words")
        conds = [s["reached_when"] for s in t["steps"]] + [d["needed_when"] for d in t["documents"]] + [s["when"] for s in t["stops"]]
        for c in conds:
            unknown = product.condition_facts(c) - facts
            if unknown:
                fail(f"{t['id']}: condition names unknown facts {unknown}")
        for d in t["documents"]:
            if d["step"] not in steps:
                fail(f"{t['id']} document {d['id']}: unknown step {d['step']}")
        for p in t["presumptions"]:
            if p["fact"] not in facts:
                fail(f"{t['id']} presumption: unknown fact {p['fact']}")

    # 4-6: workflows
    counts = {"convention_presumptions": 0}
    for t in data["types"]:
        path = ROOT / "workflow" / f"{t['id']}.json"
        wf = json.loads(path.read_text(encoding="utf-8"))
        try:
            product.validate_workflow(wf)
        except product.CatalogueError as e:
            fail(f"{path.name}: product validator: {e}")
            continue
        variant = json.loads(json.dumps(wf))
        for s in variant["sources"]:
            if s.get("intended_kind"):
                s["kind"] = s["intended_kind"]
        try:
            product.validate_workflow(variant)
            print(f"note: the validator also accepts kind benchmark_convention ({path.name})")
        except product.CatalogueError as e:
            print(f"note: {path.name} validates with kind process_guidance; with benchmark_convention the frozen validator says: {e}")
        fact_ids = [f["id"] for f in t["facts"]]
        used = product._used_facts(wf)
        if len(used) > product.MAX_OPEN_FACTS:
            print(f"note: {t['id']} uses {len(used)} facts; the product defers exactly only while at most {product.MAX_OPEN_FACTS} are open")
        wf_route = next((f for f in wf["facts"] if f["id"] == "claim_type"), None)
        if not wf_route or routing and wf_route["values"] != routing["values"]:
            fail(f"{path.name}: routing fact differs from rules.json")
        wf_facts = {f["id"] for f in wf["facts"]} - {"claim_type"}
        if wf_facts != set(fact_ids):
            fail(f"{path.name}: facts differ from rules.json")
        stop_ids = {s["id"] for s in t["stops"]}
        if {s["id"] for s in wf["steps"]} != {s["id"] for s in t["steps"]} | stop_ids:
            fail(f"{path.name}: steps differ from rules.json")
        if {d["id"] for d in wf["documents"]} != {d["id"] for d in t["documents"]}:
            fail(f"{path.name}: documents differ from rules.json")
        # 5. reachability and needs under every true/false assignment, through the product's evaluator
        for values in itertools.product([True, False], repeat=len(fact_ids)):
            facts = dict(zip(fact_ids, values))
            ev = product.evaluate(wf, {**facts, "claim_type": t["id"]})
            reached = {row["step"] for row in ev["path"]}
            want = {s["id"] for s in t["steps"] if product.evaluate_condition(s["reached_when"], facts)}
            stops = {s["id"] for s in t["stops"] if product.evaluate_condition(s["when"], facts)}
            if reached - stop_ids != want:
                fail(f"{t['id']}: reached {sorted(reached - stop_ids)} but reached_when gives {sorted(want)} under {facts}")
                break
            got_stop = {ev["outcome"]["id"]} & stop_ids if ev["outcome"] else set()
            if got_stop != stops:
                fail(f"{t['id']}: stop {got_stop} but stop conditions give {stops} under {facts}")
                break
            need = {d["document"]: d["required"] for d in ev["documents"]}
            want_need = {d["id"]: ("yes" if d["mandatory"] else "optional") for d in t["documents"]
                         if d["step"] in want and product.evaluate_condition(d["needed_when"], facts)}
            if need != want_need:
                fail(f"{t['id']}: documents {need} but rules give {want_need} under {facts}")
                break
        # 6. convention presumptions
        no_pres = {t["defining_event"]} | stop_on_false(t) | {f["id"] for f in t["facts"] if f.get("always_stated")}
        conv_src = next(s["id"] for s in wf["sources"] if s.get("intended_kind") == "benchmark_convention")
        pres = {}
        for p in wf.get("presumptions", []):
            pres.setdefault(p["fact"], []).append(p)
        for f in fact_ids:
            got = pres.get(f, [])
            if f in no_pres:
                if got:
                    fail(f"{t['id']}: {f} carries a presumption (defining event, always_stated, or false ends the process)")
            elif len(got) != 1 or got[0]["applies"] != "unstated" or got[0]["value"] is not False \
                    or not got[0]["source_ref"].startswith(conv_src + "#"):
                fail(f"{t['id']}: branch fact {f} needs exactly one unstated presumption (false) from the convention")
        counts["convention_presumptions"] += sum(len(v) for v in pres.values())
        # 6b walk: each branch fact true, false or unmentioned; defining event stated true
        UNM = object()
        branch = [f for f in fact_ids if f != t["defining_event"]]
        n = 0
        for values in itertools.product([True, False, UNM], repeat=len(branch)):
            n += 1
            stated = {f: v for f, v in zip(branch, values) if v is not UNM}
            stated[t["defining_event"]] = True
            unmentioned = [f for f, v in zip(branch, values) if v is UNM]
            recorded = {f: {"status": "established", "readings": [v]} for f, v in stated.items()}
            applied = product.presumed(wf, recorded)
            facts = dict(stated, claim_type=t["id"])
            for f in unmentioned:
                if f in applied:
                    facts[f] = applied[f]["value"]
            ev = product.evaluate(wf, facts)
            if ev["outcome"] and ev["outcome"]["id"] in stop_ids:
                stop = next(s for s in t["stops"] if s["id"] == ev["outcome"]["id"])
                if product.evaluate_condition(stop["when"], stated) is not True:
                    fail(f"{t['id']}: stop {stop['id']} reached through unmentioned facts {unmentioned} under {stated}")
                    break
            yes = {d["document"] for d in ev["documents"] if d["required"] == "yes"}
            ordinary = dict(stated, claim_type=t["id"])
            for f in unmentioned:
                ordinary[f] = False
            yes_ordinary = {d["document"] for d in product.evaluate(wf, ordinary)["documents"] if d["required"] == "yes"}
            if not yes <= yes_ordinary:
                fail(f"{t['id']}: unmentioned {unmentioned} create needs {sorted(yes - yes_ordinary)} under {stated}")
                break
        print(f"{t['id']}: 6b walk over {n} assignments")
        # 7. size
        if not 5 <= len(fact_ids) <= 10:
            fail(f"{t['id']}: {len(fact_ids)} deciding conditions (want 5-10)")
        changing = set().union(*(product.condition_facts(d["needed_when"]) for d in t["documents"]))
        changing |= set().union(*(product.condition_facts(s["reached_when"]) for s in t["steps"]
                                  if any(d["step"] == s["id"] for d in t["documents"]) and s["reached_when"] is not True))
        changing -= {t["defining_event"]} | {f for f in fact_ids if any(f in product.condition_facts(s["when"]) for s in t["stops"])}
        if len(changing) < 2:
            fail(f"{t['id']}: fewer than two conditions change the documents needed ({changing})")
        if not t["stops"]:
            fail(f"{t['id']}: no stop")
        incoming = {}
        for s in wf["steps"]:
            for e in s.get("next", []):
                incoming[e["to"]] = incoming.get(e["to"], 0) + 1
        if not any(v >= 2 for v in incoming.values()):
            fail(f"{t['id']}: no place where branches reconverge")
        print(f"{t['id']}: facts {len(fact_ids)}, steps {len(t['steps'])}, documents {len(t['documents'])}, "
              f"presumptions {len(t['presumptions'])}, convention presumptions {sum(len(v) for v in pres.values())}, "
              f"stops {len(t['stops'])}; facts that change documents: {sorted(changing)}")
    if not 8 <= len(catalogue) <= 14:
        fail(f"catalogue has {len(catalogue)} documents (want 8-14)")
    if not 2 <= len(data["types"]) <= 3:
        fail("want 2 or 3 claim types")
    T = data["types"]
    print(f"\ncounts: types {len(T)}; facts {sum(len(t['facts']) for t in T)}; steps {sum(len(t['steps']) for t in T)}; "
          f"documents {sum(len(t['documents']) for t in T)} per type, {len(catalogue)} in the catalogue; "
          f"presumptions {sum(len(t['presumptions']) for t in T)} (plus {counts['convention_presumptions']} convention presumptions in the workflows); "
          f"stops {sum(len(t['stops']) for t in T)}; convention rules 1")
    print("rules by basis: " + ", ".join(f"{k} {v}" for k, v in sorted(by_basis.items())) + f" (total {sum(by_basis.values())}), plus convention 1")
    print("FAILED: %d" % len(FAIL) if FAIL else "ALL CHECKS PASSED")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

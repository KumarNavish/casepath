"""Self-check of the dismissal rule set. Run: `python3 -I tools/check.py`.

1. every passage (English and German) occurs character for character in its snapshot,
   inside the cited article and, where the locator names one, the cited paragraph and letter;
   at most 60 words;
2. every locator names an article present in the snapshot; every stored article is cited;
3. every fact and document referenced in a condition, step, presumption or stop exists;
4. SOURCES.json hashes match the stored snapshots and raw downloads;
5. every workflow passes the product's own validate_workflow (tested worktree, read-only);
6. each workflow, walked with the product's own walk under every complete assignment of the
   type's facts, reaches exactly the steps, documents and stops rules.json states;
7. the intake convention and polarity (SPEC.md items 6a, 6b): exact wording in rules.json, rule_text.md and
   SPEC.md; in each workflow exactly one unstated presumption per branch fact (statutory where the rule set has
   one, otherwise the convention with value false), none on the defining event, on a fact whose false ends the
   process, or on an always_stated fact; over every assignment with each branch fact true, false or unmentioned
   (defining event true): no stop is reached through an unmentioned fact and no document need is created by
   one; with one fact raised and left open no presumption fills it;
8. size limits of SPEC.md step 2a item 5; prints the counts.
Exit status 1 on any failure.
"""
import hashlib
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path

REGIME = Path(__file__).resolve().parent.parent
PRODUCT = Path("/home/user/work/casepath-sync-e/casepath-internal/casepath/process/workflows.py")
FAIL = []


def fail(msg):
    FAIL.append(msg)
    print("FAIL", msg)


def load_product():
    sys.dont_write_bytecode = True  # the product worktree is read-only: never leave a cache file there
    spec = importlib.util.spec_from_file_location("product_workflows", PRODUCT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def articles(text):
    """Map 'Art. 336c' -> list of lines of that article."""
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^Art\. (\d+[a-z]*)$", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line)
    return out


def paragraph_text(lines, para, letter):
    """Text of paragraph `para` (and letter) of an article's lines; None when absent."""
    block, inside = [], False
    for line in lines:
        if line.startswith("[Marginal"):
            continue
        m = re.match(r"^(\d+) ", line)
        if m:
            inside = m.group(1) == para
        if inside:
            block.append(line)
    if para is None:
        block = [l for l in lines if not l.startswith("[Marginal")]
    if not block:
        return None
    if letter:
        hits = [l for l in block if re.match(rf"^(\d+ )?{re.escape(letter)}\. ", l)]
        return "\n".join(hits) if hits else None
    return "\n".join(block)


def parse_locator(loc):
    m = re.match(r"^CO art\. (\d+[a-z]*)(?: para\. (\d+))?(?: let\. ([a-z]+))?(?: \(introduction\))?$", loc)
    if not m:
        return None
    return m.groups()


def stop_on_false(product, t):
    """Facts whose value false can end the process: some complete assignment reaches a stop with the fact false
    and no stop with only that fact turned true."""
    ids = [f["id"] for f in t["facts"]]
    out = set()
    for values in itertools.product([True, False], repeat=len(ids)):
        facts = dict(zip(ids, values))
        hit = any(product.evaluate_condition(s["when"], facts) is True for s in t["stops"])
        if not hit:
            continue
        for f in ids:
            if facts[f] is False and not any(product.evaluate_condition(s["when"], {**facts, f: True}) is True for s in t["stops"]):
                out.add(f)
    return out


def all_rules(data):
    for t in data["types"]:
        for kind in ("facts", "steps", "documents", "presumptions", "stops"):
            for item in t[kind]:
                yield t["id"], kind, item.get("id") or item.get("fact"), item["rule"]


def main():
    data = json.loads((REGIME / "rules.json").read_text(encoding="utf-8"))
    snaps = {sid: (REGIME / "sources" / f"{sid}.txt").read_text(encoding="utf-8") for sid in ("co-sr220-en", "co-sr220-de")}
    arts = {sid: articles(txt) for sid, txt in snaps.items()}
    cited = {sid: set() for sid in snaps}
    by_basis = {}
    n_rules = 0
    for tid, kind, iid, rule in all_rules(data):
        n_rules += 1
        by_basis[rule["basis"]] = by_basis.get(rule["basis"], 0) + 1
        where = f"{tid}/{kind}/{iid}"
        if rule["basis"] not in {"states", "follows", "evidence"}:
            fail(f"{where}: basis {rule['basis']}")
        if rule["basis"] in {"follows", "evidence"} and not rule.get("inference"):
            fail(f"{where}: {rule['basis']} without inference")
        loc = parse_locator(rule["locator"])
        if loc is None:
            fail(f"{where}: locator not parsed: {rule['locator']}")
            continue
        art, para, letter = loc
        passages = [(rule["source_id"], rule["passage"])]
        if "passage_de" in rule:
            passages.append((rule["passage_de"]["source_id"], rule["passage_de"]["passage"]))
        for sid, passage in passages:
            if passage not in snaps[sid]:
                fail(f"{where}: passage not verbatim in {sid}: {passage[:60]}")
            if len(passage.split()) > 60:
                fail(f"{where}: passage over 60 words")
            if art not in arts[sid]:
                fail(f"{where}: article {art} not in {sid}")
                continue
            cited[sid].add(art)
            scope = paragraph_text(arts[sid][art], para, letter)
            if scope is None:
                fail(f"{where}: {rule['locator']} not found in {sid}")
            elif passage not in scope:
                fail(f"{where}: passage not inside {rule['locator']} in {sid}")
    for sid in snaps:
        unused = set(arts[sid]) - cited[sid]
        if unused:
            fail(f"{sid}: stored but not cited: {sorted(unused)}")

    # references
    product = load_product()
    for t in data["types"]:
        facts = {f["id"] for f in t["facts"]}
        steps = {s["id"] for s in t["steps"]}
        docs = {d["id"] for d in t["documents"]}
        if t["defining_event"] not in facts:
            fail(f"{t['id']}: defining event not a fact")
        conds = [("step " + s["id"], s["reached_when"]) for s in t["steps"]] + \
                [("doc " + d["id"], d["needed_when"]) for d in t["documents"]] + \
                [("stop " + s["id"], s["when"]) for s in t["stops"]]
        for where, c in conds:
            missing = product.condition_facts(c) - facts
            if missing:
                fail(f"{t['id']} {where}: unknown facts {missing}")
        for d in t["documents"]:
            if d["step"] not in steps:
                fail(f"{t['id']} doc {d['id']}: unknown step {d['step']}")
        for p in t["presumptions"]:
            if p["fact"] not in facts:
                fail(f"{t['id']} presumption: unknown fact {p['fact']}")
        for f in t["facts"]:
            if not f.get("question") or not f.get("not_this"):
                fail(f"{t['id']} fact {f['id']}: question or not_this missing")
        used = set().union(*(product.condition_facts(c) for _w, c in conds))
        if facts - used:
            fail(f"{t['id']}: facts that decide nothing: {sorted(facts - used)}")

    # the intake convention (SPEC.md item 6a)
    conv = data.get("convention") or {}
    spec_raw = (REGIME.parent.parent / "SPEC.md").read_text(encoding="utf-8")
    spec = re.sub(r"\s+", " ", re.sub(r"(?m)^\s*> ?", "", spec_raw))
    rule_text = (REGIME / "rule_text.md").read_text(encoding="utf-8")
    if conv.get("rule", {}).get("basis") != "convention":
        fail("rules.json: convention entry missing or basis is not 'convention'")
    if not conv.get("text") or conv["text"] not in spec:
        fail("convention text is not the exact wording of SPEC.md item 6a")
    if "## Convention of this benchmark (not law)" not in rule_text or conv.get("text", "") not in rule_text:
        fail("rule_text.md: convention section or exact wording missing")
    conv_src = conv.get("rule", {}).get("source_id")
    if not any(x["id"] == conv_src and x.get("kind") == "benchmark_convention" for x in data["sources"]):
        fail("rules.json: convention source entry of kind benchmark_convention missing")
    for tid, kind, iid, rule in all_rules(data):
        if rule["basis"] == "convention":
            fail(f"{tid}/{kind}/{iid}: convention basis outside the top-level convention entry")

    # sources
    meta = json.loads((REGIME / "sources" / "SOURCES.json").read_text(encoding="utf-8"))
    for s in meta["sources"]:
        path = REGIME / "sources" / s["snapshot"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != s["sha256"]:
            fail(f"SOURCES.json: snapshot hash mismatch for {s['id']}")
        raw = REGIME / "sources" / "raw" / s["raw_file"]
        if hashlib.sha256(raw.read_bytes()).hexdigest() != s["raw_sha256"]:
            fail(f"SOURCES.json: raw hash mismatch for {s['id']}")

    # workflows: product validator and exhaustive equivalence with rules.json
    counts = {"types": 0, "facts": 0, "steps": 0, "documents": 0, "presumptions": 0, "convention_presumptions": 0, "stops": 0}
    catalogue = set()
    for t in data["types"]:
        path = REGIME / "workflow" / f"{t['id']}.json"
        wf = json.loads(path.read_text(encoding="utf-8"))
        try:
            product.validate_workflow(wf)
            print(f"validate_workflow OK: {path.name}")
        except product.CatalogueError as e:
            fail(f"{path.name}: {e}")
            continue
        rule_steps = {s["id"]: s for s in t["steps"]}
        stop_ids = {s["id"] for s in t["stops"]}
        fact_ids = [f["id"] for f in t["facts"]]
        reach = product._Reach(wf)
        for values in itertools.product([True, False], repeat=len(fact_ids)):
            facts = dict(zip(fact_ids, values))
            facts["dispute_family"] = t["id"]
            path_, needs = reach.reach(facts)
            got_steps = {s for s in path_ if s in rule_steps}
            want_steps = {s for s, st in rule_steps.items() if product.evaluate_condition(st["reached_when"], facts) is True}
            got_stop = {s for s in path_ if s in stop_ids}
            want_stop = {s["id"] for s in t["stops"] if product.evaluate_condition(s["when"], facts) is True}
            want_docs = {d["id"] for d in t["documents"] if d["step"] in want_steps
                         and product.evaluate_condition(d["needed_when"], facts) is True}
            if got_steps != want_steps or got_stop != want_stop or set(needs) != want_docs:
                fail(f"{t['id']}: walk differs from rules.json under {facts}: steps {got_steps ^ want_steps}, "
                     f"stops {got_stop ^ want_stop}, docs {set(needs) ^ want_docs}")
                break
            if len(want_stop) > 1:
                fail(f"{t['id']}: two stops at once under {facts}")
            if not want_stop and not path_[-1].endswith("_close"):
                fail(f"{t['id']}: walk ends neither at a stop nor at close under {facts}")
        # one open fact at a time: the product's deferral must hold exactly the documents whose need it changes
        for f in fact_ids:
            base = {x: True for x in fact_ids}
            base["dispute_family"] = t["id"]
            base[f] = None
            ev = product.evaluate(wf, base)
            held = {d["document"] for d in ev["documents"] if d["required"] == "depends"}
            yes = {d["id"] for d in t["documents"] if d["step"] in {s for s, st in rule_steps.items()
                   if product.evaluate_condition(st["reached_when"], {**base, f: True}) is True}
                   and product.evaluate_condition(d["needed_when"], {**base, f: True}) is True}
            no = {d["id"] for d in t["documents"] if d["step"] in {s for s, st in rule_steps.items()
                  if product.evaluate_condition(st["reached_when"], {**base, f: False}) is True}
                  and product.evaluate_condition(d["needed_when"], {**base, f: False}) is True}
            if held != yes ^ no:
                fail(f"{t['id']}: open {f}: product holds {sorted(held)}, rules imply {sorted(yes ^ no)}")
        # the convention in the workflow (SPEC.md 6a, 6b): which facts carry which presumption
        pres = {}
        for p in wf.get("presumptions", []):
            pres.setdefault(p["fact"], []).append(p)
        statutory = {p["fact"]: p for p in t["presumptions"]}
        wf_src = {x["id"]: x for x in wf["sources"]}
        always = {f["id"] for f in t["facts"] if f.get("always_stated")}
        false_stops = stop_on_false(product, t)
        for f in fact_ids:
            got = pres.get(f, [])
            if f == t["defining_event"] or f in always or (f in false_stops and f not in statutory):
                if got:
                    fail(f"{t['id']}: {f} carries a presumption (defining event, always_stated, or false ends the process)")
                continue
            if len(got) != 1 or got[0]["applies"] != "unstated":
                fail(f"{t['id']}: branch fact {f} has {len(got)} presumptions (want exactly one, unstated)")
                continue
            src = got[0]["source_ref"].split("#")[0]
            if f in statutory:
                if src != "co-sr220" or got[0]["value"] != statutory[f]["value"]:
                    fail(f"{t['id']}: {f} should carry its statutory presumption")
            elif src != conv_src or got[0]["value"] is not False or wf_src.get(src, {}).get("intended_kind") != "benchmark_convention" \
                    or wf_src.get(src, {}).get("kind") != "process_guidance":
                fail(f"{t['id']}: {f} should carry the convention (value no, source {conv_src}, process_guidance/intended_kind)")
        for f in always:
            if f in statutory or pres.get(f):
                fail(f"{t['id']}: always_stated fact {f} has a presumption")
        variant = json.loads(json.dumps(wf))
        for x in variant["sources"]:
            if x["id"] == conv_src:
                x["kind"] = "benchmark_convention"
        try:
            product.validate_workflow(variant)
            print(f"note: the validator accepts kind benchmark_convention ({path.name})")
        except product.CatalogueError as e:
            print(f"note: with kind benchmark_convention the product validator rejects {path.name}: {e}")
        # SPEC.md 6b: every assignment in which each branch fact is stated true, stated false or unmentioned, with the
        # defining event stated true. Unmentioned facts get only the presumptions the product applies (presumed()).
        # (a) no stop is reached through an unmentioned fact: a stop reached must hold with the unmentioned facts unknown;
        # (b) no document need is created by a fact being unmentioned: every document the product requires ("yes") is
        #     also required when each unmentioned fact is instead stated with the value of its cited presumption, or
        #     false where it has none (the ordinary case).
        UNM = object()
        branch = [f for f in fact_ids if f != t["defining_event"]]
        n_assign = 0
        for values in itertools.product([True, False, UNM], repeat=len(branch)):
            n_assign += 1
            stated = {f: v for f, v in zip(branch, values) if v is not UNM}
            stated[t["defining_event"]] = True
            unmentioned = [f for f, v in zip(branch, values) if v is UNM]
            recorded = {f: {"status": "established", "readings": [v]} for f, v in stated.items()}
            applied = product.presumed(wf, recorded)
            facts = {**stated, "dispute_family": t["id"]}
            for f in unmentioned:
                if f in applied:
                    facts[f] = applied[f]["value"]
            ev = product.evaluate(wf, facts)
            if ev["outcome"] and ev["outcome"]["id"] in stop_ids:
                stop = next(x for x in t["stops"] if x["id"] == ev["outcome"]["id"])
                if product.evaluate_condition(stop["when"], {**stated}) is not True:
                    fail(f"{t['id']}: stop {stop['id']} reached through unmentioned facts {unmentioned} under {stated}")
                    break
            yes = {d["document"] for d in ev["documents"] if d["required"] == "yes"}
            ordinary = {**stated, "dispute_family": t["id"]}
            for f in unmentioned:
                ordinary[f] = statutory[f]["value"] if f in statutory else False
            yes_ordinary = {d["document"] for d in product.evaluate(wf, ordinary)["documents"] if d["required"] == "yes"}
            if not yes <= yes_ordinary:
                fail(f"{t['id']}: unmentioned {unmentioned} create needs {sorted(yes - yes_ordinary)} under {stated}")
                break
        print(f"{t['id']}: 6b walk over {n_assign} assignments (each branch fact true, false or unmentioned)")

        # one fact raised and left open: no presumption applies to it
        for f in fact_ids:
            recorded = {x: {"status": "established", "readings": [True]} for x in fact_ids if x != f}
            recorded[f] = {"status": "unknown", "readings": [None], "open_readings": [True], "citations": ["quoted doubt"]}
            if f in product.presumed(wf, recorded):
                fail(f"{t['id']}: a presumption fills {f} although the file raises it and leaves it open")
        # size limits per type
        n_facts = len(t["facts"])
        if not 5 <= n_facts <= 10:
            fail(f"{t['id']}: {n_facts} deciding conditions (5-10)")
        changing = set()
        for d in t["documents"]:
            changing |= product.condition_facts(d["needed_when"])
        for s in t["steps"]:
            if any(d["step"] == s["id"] for d in t["documents"]):
                changing |= product.condition_facts(s["reached_when"])
        changing -= {t["defining_event"]}
        if len(changing) < 2:
            fail(f"{t['id']}: fewer than two conditions change the documents")
        if not t["stops"]:
            print(f"note: {t['id']} has no stop")
        targets = {}
        for st in wf["steps"]:
            for e in st.get("next", []):
                targets.setdefault(e["to"], set()).add(st["id"])
        rejoin = sorted(k for k, v in targets.items() if len(v) > 1)
        if not rejoin:
            fail(f"{t['id']}: no reconvergence")
        print(f"{t['id']}: facts {n_facts}, steps {len(t['steps'])} (+{len(wf['steps']) - len(t['steps'])} gate/stop/close in workflow), "
              f"documents {len(t['documents'])}, presumptions {len(t['presumptions'])}, stops {len(t['stops'])}, "
              f"document-changing conditions {sorted(changing)}, reconvergence at {rejoin}")
        counts["types"] += 1
        counts["facts"] += n_facts
        counts["steps"] += len(t["steps"])
        counts["documents"] += len(t["documents"])
        counts["presumptions"] += len(t["presumptions"])
        counts["convention_presumptions"] += sum(1 for p in wf["presumptions"] if p["source_ref"].startswith(conv_src + "#"))
        counts["stops"] += len(t["stops"])
        catalogue |= {d["id"] for d in t["documents"]}
    if not 8 <= len(catalogue) <= 14:
        fail(f"catalogue has {len(catalogue)} documents (8-14)")
    print("counts:", json.dumps(counts), "catalogue:", len(catalogue), "rules:", n_rules, "by basis:", json.dumps(by_basis, sort_keys=True))
    print("catalogue documents:", sorted(catalogue))
    if FAIL:
        print(f"{len(FAIL)} FAILURE(S)")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

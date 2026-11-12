"""Self-check of the tenancy rule set.

Run: python3 -I -B tools/check.py
Checks: every passage (EN and DE) occurs character for character in its
snapshot, inside the article (and paragraph / letter) its locator names; every
locator names an article present in both snapshots; passages are at most 60
words; every fact, step and document a condition or a document references
exists; SOURCES.json hashes match the snapshots; each workflow passes the
product's own `validate_workflow` (read-only import from the tested worktree)
and reaches exactly the steps, documents and stops that rules.json states,
under every assignment of the type's facts; rule_text.md carries every
question and document title. Prints the counts.
"""
import hashlib
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PRODUCT = Path("/home/user/work/casepath-sync-e/casepath-internal")
sys.path.insert(0, str(PRODUCT))
from casepath.process import workflows as W  # noqa: E402  (product code, read-only)

errors = []


def err(msg):
    errors.append(msg)


def blocks(path):
    """Article label -> list of (paragraph, line) for a snapshot."""
    out, cur, para = {}, None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^=== (Art\. \S+) ===$", line)
        if m:
            cur, para = m.group(1), None
            out[cur] = []
            continue
        if cur is None or line.startswith("[marginal heading") or not line.strip():
            continue
        p = re.match(r"^(\d+) ", line)
        if p:
            para = p.group(1)
        out[cur].append((para, line))
    return out


SNAP = {sid: HERE / "sources" / f"{sid}.txt" for sid in ("sr220-en", "sr220-de")}
BLOCKS = {sid: blocks(p) for sid, p in SNAP.items()}
TEXT = {sid: p.read_text(encoding="utf-8") for sid, p in SNAP.items()}


def parse_locator(loc):
    m = re.match(r"^Art\. (\d+[a-z]?)(?: para\. (\d+))?(?: let\. ([a-z])(?:–([a-z]))?)?$", loc)
    if not m:
        return None
    return {"art": "Art. " + m.group(1), "para": m.group(2), "let": m.group(3)}


def check_passage(where, sid, loc, passage):
    if passage not in TEXT[sid]:
        err(f"{where}: passage not found verbatim in {sid}: {passage[:60]!r}")
        return
    words = len(passage.split())
    if words > 60:
        err(f"{where}: passage has {words} words (> 60)")
    L = parse_locator(loc)
    if L is None:
        err(f"{where}: unreadable locator {loc!r}")
        return
    if L["art"] not in BLOCKS[sid]:
        err(f"{where}: {L['art']} not in snapshot {sid}")
        return
    rows = BLOCKS[sid][L["art"]]
    body = "\n".join(line for _, line in rows)
    pos = body.find(passage)
    if pos < 0:
        err(f"{where}: passage not inside {L['art']} of {sid}")
        return
    start_line = body[:pos].count("\n")
    end_line = body[:pos + len(passage)].count("\n")
    span = rows[start_line:end_line + 1]
    if L["para"] and any(p != L["para"] for p, _ in span):
        err(f"{where}: passage lies outside para. {L['para']} of {L['art']} in {sid}")
    if L["let"] and not any(line.startswith(L["let"] + ". ") for _, line in span):
        err(f"{where}: passage does not contain let. {L['let']} of {L['art']} in {sid}")


def check_rule(where, rule, counts):
    if rule.get("source_id") != "sr220-en":
        err(f"{where}: unknown source_id {rule.get('source_id')!r}")
        return
    if rule.get("basis") not in {"states", "follows", "evidence"}:
        err(f"{where}: basis {rule.get('basis')!r}")
    if rule.get("basis") in {"follows", "evidence"} and not rule.get("inference"):
        err(f"{where}: basis {rule['basis']} needs an inference")
    counts[rule.get("basis")] += 1
    check_passage(where, "sr220-en", rule["locator"], rule["passage"])
    if "passage_de" in rule:
        if rule["passage_de"].get("source_id") != "sr220-de":
            err(f"{where}: passage_de source must be sr220-de")
        check_passage(where + " [de]", "sr220-de", rule["locator"], rule["passage_de"]["passage"])


def facts_in(c):
    return W.condition_facts(c) if c is not True else set()


def main():
    rules = json.loads((HERE / "rules.json").read_text(encoding="utf-8"))
    basis = Counter()
    n_facts = n_steps = n_pres = n_stops = 0
    catalogue = set()
    per_type = []
    rule_text = (HERE / "rule_text.md").read_text(encoding="utf-8")

    # sources
    meta = json.loads((HERE / "sources" / "SOURCES.json").read_text(encoding="utf-8"))
    listed = {s["id"]: s for s in meta["sources"]}
    for sid, path in SNAP.items():
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if sid not in listed:
            err(f"SOURCES.json lacks {sid}")
        elif listed[sid].get("sha256") != h:
            err(f"SOURCES.json sha256 for {sid} does not match the snapshot")

    for t in rules["types"]:
        tid = t["id"]
        facts = {f["id"] for f in t["facts"]}
        steps = {s["id"] for s in t["steps"]}
        docs = {d["id"] for d in t["documents"]}
        if t["defining_event"] not in facts:
            err(f"{tid}: defining event is not a fact")
        for f in t["facts"]:
            for k in ("question", "not_this"):
                if not f.get(k):
                    err(f"{tid}.{f['id']}: missing {k}")
            if f["question"] not in rule_text:
                err(f"{tid}.{f['id']}: question missing from rule_text.md")
            check_rule(f"{tid} fact {f['id']}", f["rule"], basis)
        for s in t["steps"]:
            if facts_in(s["reached_when"]) - facts:
                err(f"{tid} step {s['id']}: unknown fact in reached_when")
            check_rule(f"{tid} step {s['id']}", s["rule"], basis)
        for d in t["documents"]:
            if d["step"] not in steps:
                err(f"{tid} document {d['id']}: unknown step {d['step']}")
            if facts_in(d["needed_when"]) - facts:
                err(f"{tid} document {d['id']}: unknown fact in needed_when")
            if d["title"] not in rule_text:
                err(f"{tid} document {d['id']}: title missing from rule_text.md")
            check_rule(f"{tid} document {d['id']}", d["rule"], basis)
            catalogue.add(d["id"])
        for p in t["presumptions"]:
            if p["fact"] not in facts:
                err(f"{tid} presumption: unknown fact {p['fact']}")
            check_rule(f"{tid} presumption {p['fact']}", p["rule"], basis)
        for s in t["stops"]:
            if facts_in(s["when"]) - facts:
                err(f"{tid} stop: unknown fact")
            check_rule(f"{tid} stop", s["rule"], basis)
        n_facts += len(facts)
        n_steps += len(steps)
        n_pres += len(t["presumptions"])
        n_stops += len(t["stops"])

        # workflow: product validator, then equivalence with rules.json under every assignment
        wf = json.loads((HERE / "workflow" / f"{tid}.json").read_text(encoding="utf-8"))
        try:
            W.validate_workflow(wf)
        except W.CatalogueError as e:
            err(f"workflow {tid}: validate_workflow failed: {e}")
            continue
        reach = W._Reach(wf)
        fact_ids = [f["id"] for f in t["facts"]]
        changes_docs = set()
        results = {}
        for values in itertools.product([True, False], repeat=len(fact_ids)):
            fv = dict(zip(fact_ids, values))
            fv["dispute_family"] = tid
            path, needs = reach.reach(fv)
            stopped = any(W.evaluate_condition(s["when"], fv) is True for s in t["stops"])
            exp_steps = set() if stopped else {s["id"] for s in t["steps"]
                                               if W.evaluate_condition(s["reached_when"], fv) is True}
            exp_docs = set() if stopped else {d["id"] for d in t["documents"] if d["step"] in exp_steps
                                              and W.evaluate_condition(d["needed_when"], fv) is True}
            got_steps = set(path) & steps
            got_docs = {d for d, need in needs.items() if need == "yes"}
            outcome = wf_outcome(wf, path)
            if got_steps != exp_steps or got_docs != exp_docs or (outcome == "stopped") != stopped:
                err(f"workflow {tid} differs from rules.json at {fv}: steps {sorted(got_steps ^ exp_steps)}, "
                    f"documents {sorted(got_docs ^ exp_docs)}, outcome {outcome}, stop {stopped}")
            results[values] = frozenset(got_docs)
        for i, f in enumerate(fact_ids):
            for values, got in results.items():
                flipped = values[:i] + (not values[i],) + values[i + 1:]
                if results[flipped] != got and f != t["defining_event"]:
                    changes_docs.add(f)
        incoming = Counter(e["to"] for s in wf["steps"] for e in s.get("next", []))
        merges = sorted(s for s, n in incoming.items() if n >= 2)
        per_type.append((tid, len(fact_ids), len(steps), len(docs), len(t["stops"]), sorted(changes_docs), merges))
        if not 5 <= len(fact_ids) <= 10:
            err(f"{tid}: {len(fact_ids)} deciding conditions (want 5 to 10)")
        if len(changes_docs) < 2:
            err(f"{tid}: fewer than two conditions change the documents")
        if not merges:
            err(f"{tid}: no reconvergence")

    if not 8 <= len(catalogue) <= 14:
        err(f"catalogue has {len(catalogue)} documents (want 8 to 14)")

    print(f"types {len(rules['types'])}, facts {n_facts}, steps {n_steps}, documents {len(catalogue)} "
          f"(catalogue; {sum(r[3] for r in per_type)} type-document rows), presumptions {n_pres}, stops {n_stops}")
    print("rules by basis: " + ", ".join(f"{k} {v}" for k, v in sorted(basis.items())) + f" (total {sum(basis.values())})")
    for tid, nf, ns, nd, nst, ch, mg in per_type:
        print(f"  {tid}: deciding conditions {nf}, steps {ns}, documents {nd}, stops {nst}; "
              f"conditions changing documents {ch}; reconvergence at {mg}")
    print("workflows: validate_workflow passed" if not any("validate_workflow" in e for e in errors)
          else "workflows: validate_workflow FAILED")
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print("all checks passed")


def wf_outcome(wf, path):
    steps = {s["id"]: s for s in wf["steps"]}
    last = steps[path[-1]] if path else None
    return last.get("outcome") if last else None


if __name__ == "__main__":
    main()

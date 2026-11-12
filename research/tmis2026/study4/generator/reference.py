"""Engine reference for each design: the product's own evaluator at the tested commit, under the intake convention.

Run:  python3 -I -B study4/generator/reference.py --regime tenancy
Reads study4/dev/<regime>/designs/*.json, writes study4/dev/<regime>/references/<file_id>.json,
references/MANIFEST.json and MARGINALS_reference.json.

How a design becomes the evaluator's input (the intake convention, SPEC 6a):
- stated true / stated false: the fact is established with that value;
- not mentioned: the workflow's `unstated` presumption fills it, through the product's own `presumed()` (no row
  recorded); a fact without a presumption (defining event, stop-on-false fact) stays unresolved;
- open: recorded as raised and left open (every reading answered "open" with a quotation), so `presumed()` fills
  nothing and the fact stays unresolved;
- a denied defining event is a stated false, which the workflow routes to its stop.
Supplied attachments are findings: sufficient -> `present`, insufficient -> `unusable`; `checked=True`, so an
unsupplied needed document is `missing`.

Mapping of the evaluator's checklist to the five reference states (the product's own semantics, and the earlier
study's scorer: `supplied_insufficient` counted as a request, harness/product/diagnose.py and analysis/study2.py):
- not on the checklist -> not_needed (also when supplied);
- required "depends" -> hold, `waits_for` = the open facts the evaluator names (also when supplied);
- required "yes": missing -> request; present -> present_sufficient; unusable -> present_insufficient (request again);
- required "optional"/"suggested" (rules.json `mandatory: false`): not_needed unless supplied, then present_sufficient
  or present_insufficient, never a request (theft's `reading_of_optional`).
Each reference is also recomputed from rules.json alone (genlib.rules_outcome) and any difference is listed.
"""
import argparse
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import genlib as G  # noqa: E402

PRODUCT_DEFAULT = "/home/user/work/casepath-sync-e/casepath-internal"


def load_product(path):
    sys.path.insert(0, path)
    from casepath.process import workflows as W  # product code, read-only
    return W


def product_commit(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def stop_steps(regime, tid, wf):
    """Workflow terminal steps that are stops: their id or outcome id is a rules.json stop id, or outcome 'stopped'."""
    ids = {s["id"] for s in regime.stops(tid)}
    return {s["id"] for s in wf["steps"] if s.get("outcome") and (s["id"] in ids or s["outcome"] in ids
                                                                   or s["outcome"] == "stopped")}


def engine_reference(W, regime, design):
    tid = design["type"]
    wf = regime.workflows[tid]
    rf, rv = regime.routing_fact(tid)
    facts = {rf: rv} if rf else {}
    recorded = {}
    for f, s in design["facts"].items():
        if s in ("stated_true", "stated_false"):
            facts[f] = s == "stated_true"
            recorded[f] = {"status": "established", "value": facts[f]}
        elif s == "open":
            recorded[f] = {"status": "unknown", "readings": [None, None], "open_readings": [True, True],
                           "citations": [{"quote": "(designed: raised and left open)"}]}
    filled = W.presumed(wf, recorded)
    presumed = {}
    for f, s in design["facts"].items():
        if s == "not_mentioned" and f in filled:
            facts[f] = filled[f]["value"]
            presumed[f] = filled[f]["value"]
        elif s == "open" and f in filled:
            raise SystemExit(f"{design['file_id']}: the product presumed the open fact {f}")
    supplied = {a["document"]: a["sufficient"] for a in design["attachments"] if a["supplied"]}
    findings = {d: {"status": "present" if ok else "unusable", "verdict": "accepted"} for d, ok in supplied.items()}
    ev = W.evaluate(wf, facts, findings, checked=True)
    rows = {r["document"]: r for r in ev["documents"]}
    docs = {}
    for d in regime.documents(tid):
        did = d["id"]
        r = rows.get(did)
        entry = {}
        if did in supplied:
            entry["supplied"] = "sufficient" if supplied[did] else "insufficient"
        if r is None:
            entry.update(state="not_needed", request=False)
        elif r["required"] in ("optional", "suggested"):
            entry["optional"] = True
            st = {"present": "present_sufficient", "unusable": "present_insufficient"}.get(r["status"], "not_needed")
            entry.update(state=st, request=False)
        elif r["required"] == "depends":
            entry.update(state="hold", request=False, waits_for=sorted(r.get("condition_facts") or []))
        elif r["required"] == "yes":
            st = {"present": "present_sufficient", "unusable": "present_insufficient"}.get(r["status"], "request")
            entry.update(state=st, request=st != "present_sufficient")
        else:
            raise SystemExit(f"{design['file_id']}: unknown requirement {r['required']!r} for {did}")
        docs[did] = entry
    stops = stop_steps(regime, tid, wf)
    terminal = ev["path"][-1]["step"] if ev["path"] else None
    pending = [b["step"] for b in ev.get("beyond", []) if b["step"] in stops and b["state"] == "pending"]
    reached = [b["step"] for b in ev.get("beyond", []) if b["step"] in stops and b["state"] == "reached"]
    if ev.get("outcome") and terminal in stops:
        stop = {"state": "stopped", "step": terminal, "outcome": ev["outcome"]["id"]}
    elif reached:
        stop = {"state": "stopped", "step": reached[0]}
    elif pending:
        stop = {"state": "pending", "steps": sorted(pending)}
    else:
        stop = {"state": "none"}
    return {"facts_given": {k: v for k, v in sorted(facts.items())}, "presumed": presumed,
            "unresolved": sorted(f for f, s in design["facts"].items() if f not in facts),
            "documents": docs, "stop": stop,
            "waiting_for": [w["fact"] for w in ev.get("waiting_for", [])],
            "deferral": ev.get("deferral"), "outcome": (ev.get("outcome") or {}).get("id"),
            "path": [p["step"] for p in ev["path"]]}


def unreached_check(W, regime, design, ref):
    """An always_stated fact left unmentioned because no step using it can be reached: confirm with the product's
    evaluator that stating it as drawn changes no document's state and not the stop."""
    alt = dict(design, facts=dict(design["facts"]))
    for x in design["always_stated_not_mentioned"]:
        alt["facts"][x["fact"]] = x["drawn"]
    other = engine_reference(W, regime, alt)
    diffs = [{"document": k, "not_mentioned": v["state"], "as_drawn": other["documents"][k]["state"]}
             for k, v in ref["documents"].items()
             if (v["state"], v.get("waits_for")) != (other["documents"][k]["state"], other["documents"][k].get("waits_for"))]
    if ref["stop"] != other["stop"]:
        diffs.append({"stop": True, "not_mentioned": ref["stop"], "as_drawn": other["stop"]})
    return {"facts": design["always_stated_not_mentioned"], "same": not diffs, "differences": diffs}


def rules_check(regime, design, ref):
    tid = design["type"]
    supplied = {a["document"]: a["sufficient"] for a in design["attachments"] if a["supplied"]}
    o = G.rules_outcome(regime, tid, G.resolve(regime, tid, design["facts"]), supplied)
    diffs = []
    for did, e in ref["documents"].items():
        r = o["documents"][did]
        if r["state"] != e["state"] or (e["state"] == "hold" and r.get("waits_for") != e.get("waits_for")):
            diffs.append({"document": did, "engine": e["state"], "rules": r["state"],
                          "engine_waits_for": e.get("waits_for"), "rules_waits_for": r.get("waits_for")})
    if (o["stop"]["state"] != ref["stop"]["state"]):
        diffs.append({"stop": True, "engine": ref["stop"], "rules": o["stop"]})
    return {"agrees": not diffs, "differences": diffs, "rules_stops": o["stop"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir")
    ap.add_argument("--out", help="dev folder of the regime (default study4/dev/<regime>)")
    ap.add_argument("--product", default=PRODUCT_DEFAULT, help="path to the product's casepath-internal folder")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    W = load_product(a.product)
    regime = G.Regime(a.regime, a.rules_dir)
    for tid, wf in regime.workflows.items():
        W.validate_workflow(wf)
    out = Path(a.out) if a.out else G.DEV / a.regime
    designs = [G.read_json(p) for p in sorted((out / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
    rdir = out / "references"
    rdir.mkdir(parents=True, exist_ok=True)
    for old in rdir.glob("*.json"):
        old.unlink()
    wf_py = Path(a.product) / "casepath" / "process" / "workflows.py"
    evaluator = {"product_commit": product_commit(str(Path(a.product).parent)),
                 "workflows_py_sha256": G.sha256_file(wf_py),
                 "workflow_sha256": regime.workflow_sha256, "rules_sha256": regime.rules_sha256,
                 "convention": "intake (SPEC 6a): unmentioned branch fact -> its presumption; open -> unresolved; "
                               "denied defining event -> stop"}
    files, refs = [], []
    for d in designs:
        ref = engine_reference(W, regime, d)
        ref["rules_check"] = rules_check(regime, d, ref)
        if d.get("always_stated_not_mentioned"):
            ref["unreached_always_stated_check"] = unreached_check(W, regime, d, ref)
        rec = {"schema": "study4.reference/1", "file_id": d["file_id"], "regime": a.regime, "type": d["type"],
               "level": d["level"], "design_sha256": G.sha256_bytes(G.canon(d).encode("utf-8")),
               "evaluator": evaluator, **ref}
        h = G.write_json(rdir / f"{d['file_id']}.json", rec)
        files.append({"file_id": d["file_id"], "sha256": h})
        refs.append((d, rec))
    G.write_json(rdir / "MANIFEST.json", {"schema": "study4.reference-manifest/1", "regime": a.regime,
                                          "evaluator": evaluator,
                                          "reference_py_sha256": G.sha256_file(Path(__file__)),
                                          "files": files})
    m = marginals(regime, refs)
    G.write_json(out / "MARGINALS_reference.json", m)
    if not a.quiet:
        print_marginals(m)
    return m


def marginals(regime, refs):
    m = {"documents": defaultdict(Counter), "stops": Counter(), "rules_disagreements": [],
         "always_stated_not_mentioned": Counter(), "unreached_always_stated_changes": [],
         "files_without_request": Counter(),
         "requests_per_file": Counter(), "holds_per_file": Counter(), "denied": Counter(), "open_by_fact": Counter()}
    for d, r in refs:
        for did, e in r["documents"].items():
            m["documents"][f"{d['type']}.{did}"][e["state"]] += 1
        st = r["stop"]
        key = st["state"] if st["state"] == "none" else st["state"] + ":" + (st.get("step") or ",".join(st.get("steps", [])))
        m["stops"][f"{d['type']}.{key}"] += 1
        m["requests_per_file"][str(sum(e["request"] for e in r["documents"].values()))] += 1
        m["holds_per_file"][str(sum(e["state"] == "hold" for e in r["documents"].values()))] += 1
        m["denied"][str(d["denied_event"])] += 1
        for f in d["open_facts"]:
            m["open_by_fact"][f"{d['type']}.{f}"] += 1
        u = r.get("unreached_always_stated_check")
        if u:
            for x in u["facts"]:
                m["always_stated_not_mentioned"][f"{d['type']}.{x['fact']}"] += 1
            if not u["same"]:
                m["unreached_always_stated_changes"].append({"file_id": d["file_id"], **u})
        if not sum(e["request"] for e in r["documents"].values()):
            m["files_without_request"][d["type"]] += 1
        if not r["rules_check"]["agrees"]:
            m["rules_disagreements"].append({"file_id": d["file_id"], **r["rules_check"]})
    for tid in regime.type_ids:
        for doc in regime.documents(tid):
            m["documents"].setdefault(f"{tid}.{doc['id']}", Counter())
    return {k: (dict(sorted(v.items())) if isinstance(v, dict) else v) for k, v in m.items()}


def print_marginals(m):
    print("documents (engine reference; " + " / ".join(G.REF_STATES) + "):")
    for k, c in m["documents"].items():
        print(f"  {k:55s} " + " ".join(f"{c.get(s, 0):3d}" for s in G.REF_STATES))
    print("stops: " + ", ".join(f"{k} {v}" for k, v in m["stops"].items()))
    print("requests per file: " + str(dict(sorted(m["requests_per_file"].items(), key=lambda x: int(x[0])))))
    print("holds per file: " + str(dict(sorted(m["holds_per_file"].items(), key=lambda x: int(x[0])))))
    print("always_stated facts left unmentioned (step unreachable): " + str(m["always_stated_not_mentioned"])
          + f"; files where stating them as drawn would change a state: {len(m['unreached_always_stated_changes'])}")
    print("files without any request: " + str(m["files_without_request"]))
    print(f"engine vs rules.json disagreements: {len(m['rules_disagreements'])}")
    for x in m["rules_disagreements"][:20]:
        print("  ", x["file_id"], x["differences"])


if __name__ == "__main__":
    main()

"""Check that the wording revision after first use (rules/<regime>/ vs rules/<regime>/rev0/) touches no reference.
DEVELOPMENT material, not a result. No model calls; writes nothing outside lint/.

    python3 -I -B study4/lint/verify_rev1.py      # writes lint/VERIFY_REV1.json

1. Every stored final reference.json (and design.json) still has the SHA-256 that dev/<regime>/final/MANIFEST.json records.
2. The product's evaluator (generator/reference.py's engine_reference) recomputes every final file's reference with the
   revised workflows: document states, waited-for facts, stop, path, presumed facts must equal the stored reference.
3. The same on the round-1 designs (dev/<regime>/designs) against the two clean-room evaluators' stored outputs
   (dev/<regime>/cleanroom/evaluator_a|b/reference.json): the clean-room comparison, re-run on the revised workflows.
4. rules.json: documents (ids, steps, needed_when, mandatory, must_show), fact ids, steps, presumptions, stops and the
   convention are byte-equal (as JSON) between rev0 and the revision; workflow logic (steps, documents, presumptions,
   applies_when, fact ids and types) likewise.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
sys.path[:0] = [str(S4 / "generator")]
import genlib as G  # noqa: E402
import reference as REF  # noqa: E402

W = REF.load_product(REF.PRODUCT_DEFAULT)
REGIMES = ["tenancy", "theft", "dismissal"]


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_ref(a, b):
    keys = ("documents", "stop", "path", "presumed", "waiting_for", "unresolved", "outcome")
    return {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}


def logic_rules(doc):
    out = {"convention": doc.get("convention"), "types": []}
    for t in doc["types"]:
        out["types"].append({"id": t["id"], "defining_event": t["defining_event"],
                             "facts": [(f["id"], f.get("type"), f.get("always_stated")) for f in t["facts"]],
                             "steps": [(s["id"], s.get("reached_when")) for s in t["steps"]],
                             "documents": [{k: d.get(k) for k in ("id", "title", "step", "needed_when", "mandatory", "must_show")} for d in t["documents"]],
                             "presumptions": t.get("presumptions"), "stops": [s.get("when") for s in t["stops"]]})
    return out


def logic_wf(wf):
    return {"id": wf["id"], "applies_when": wf["applies_when"], "start": wf["start"], "steps": wf["steps"],
            "documents": wf["documents"], "presumptions": wf["presumptions"], "outcomes": wf["outcomes"],
            "facts": [(f["id"], f["type"], f.get("values"), f.get("always_stated")) for f in wf["facts"]]}


def main():
    rep = {"label": "DEVELOPMENT, not a result", "regimes": {}}
    ok_all = True
    for r in REGIMES:
        new, old = G.Regime(r), G.Regime(r, S4 / "rules" / r / "rev0")
        for wf in new.workflows.values():
            W.validate_workflow(wf)
        x = {}
        man = jl(S4 / "dev" / r / "final" / "MANIFEST.json")
        bad_hash = [f["file_id"] for f in man["files"] for n in ("reference.json", "design.json")
                    if sha(S4 / "dev" / r / "final" / f["file_id"] / n) != f["sha256"][n]]
        x["final_files"] = len(man["files"])
        x["hash_mismatch"] = bad_hash
        diffs = []
        for f in man["files"]:
            d = S4 / "dev" / r / "final" / f["file_id"]
            design, stored = jl(d / "design.json"), jl(d / "reference.json")
            dd = same_ref(REF.engine_reference(W, new, design), stored)
            if dd:
                diffs.append({"file": f["file_id"], "differences": dd})
        x["final_recomputed_differences"] = diffs
        cr = []
        designs = [jl(p) for p in sorted((S4 / "dev" / r / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
        for ev in ("evaluator_a", "evaluator_b"):
            out = jl(S4 / "dev" / r / "cleanroom" / ev / "reference.json")
            rows = out.get("files") or out
            if isinstance(rows, list):
                rows = {row["file_id"]: row for row in rows}
            n = same = 0
            for dsg in designs:
                eng = REF.engine_reference(W, new, dsg)
                other = rows.get(dsg["file_id"]) or {}
                docs = other.get("documents") or other  # the evaluators store {file: {document: {state}}}
                for did, e in eng["documents"].items():
                    n += 1
                    o = docs.get(did) or {}
                    same += (o.get("state") == e["state"])
            cr.append({"evaluator": ev, "documents": n, "same_state_as_engine_on_revised_workflows": same})
        x["cleanroom"] = cr
        x["rules_logic_equal"] = logic_rules(old.rules) == logic_rules(new.rules)
        x["workflow_logic_equal"] = {t: logic_wf(old.workflows[t]) == logic_wf(new.workflows[t]) for t in new.workflows}
        ok = (not bad_hash and not diffs and all(c["documents"] == c["same_state_as_engine_on_revised_workflows"] for c in cr)
              and x["rules_logic_equal"] and all(x["workflow_logic_equal"].values()))
        x["ok"] = ok
        ok_all &= ok
        x["sha256_revised"] = {"rules.json": sha(S4 / "rules" / r / "rules.json"), "rule_text.md": sha(S4 / "rules" / r / "rule_text.md"),
                               **{f"workflow/{t}.json": sha(S4 / "rules" / r / "workflow" / f"{t}.json") for t in new.workflows}}
        x["sha256_rev0"] = {"rules.json": sha(S4 / "rules" / r / "rev0" / "rules.json"), "rule_text.md": sha(S4 / "rules" / r / "rev0" / "rule_text.md"),
                            **{f"workflow/{t}.json": sha(S4 / "rules" / r / "rev0" / "workflow" / f"{t}.json") for t in old.workflows}}
        rep["regimes"][r] = x
    rep["ok"] = ok_all
    (HERE / "VERIFY_REV1.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({r: {k: v for k, v in x.items() if not k.startswith("sha256")} for r, x in rep["regimes"].items()}, indent=1))
    print("ALL REFERENCES UNCHANGED" if ok_all else "DIFFERENCES FOUND")


if __name__ == "__main__":
    main()

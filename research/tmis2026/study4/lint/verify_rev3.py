"""Check revision 3 of the rule sets (the second reader's wording, rules/<regime>/ vs rules/<regime>/rev2/) and list
the development files it touches. DEVELOPMENT material, not a result. No model calls; writes nothing outside lint/.

    python3 -I -B study4/lint/verify_rev3.py      # writes lint/VERIFY_REV3.json

1. Every final reference.json and design.json has the SHA-256 its manifest records; the product's evaluator recomputes
   every final reference with the revised workflows (for a file whose recorded states a repair round's keep rule
   changed: document states and stop; the stored reference is kept from before).
2. The clean-room comparison on the round-1 designs, on the revised workflows: 354 / 450 / 436 documents equal.
3. rules.json and every workflow equal rev2/ once must_show items are read through MUST_SHOW_WORDING.json, apart from
   the changes revision 3 makes outside must_show, each named here: document titles and the routing question.
4. Item notes (generator/items/<regime>.json against generator/items/rev2/<regime>.json): for every final file and
   every supplied attachment, each item's (conditional, applies, checkable_as) under both, read through the wording
   file. A difference marks an attachment whose designed state or text must be checked against the revised item; a
   designed missing item that no longer applies is listed separately (its designed state would change).
"""
from __future__ import annotations

import copy
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
EXPECTED_CLEANROOM = {"tenancy": 354, "theft": 450, "dismissal": 436}
CORE = ("documents", "stop", "outcome", "waiting_for")


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_ref(a, b, keys=("documents", "stop", "path", "presumed", "waiting_for", "unresolved", "outcome")):
    return {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}


def mapped(reg, tid, did, items):
    return [x for x in (reg.current_item(tid, did, i) for i in items) if x is not None]


def masked_rules(doc, reg, changes):
    d = copy.deepcopy(doc)
    for t in d["types"]:
        for x in t["documents"]:
            x["must_show"] = mapped(reg, t["id"], x["id"], x["must_show"]) if reg else x["must_show"]
            changes.setdefault(("title", t["id"], x["id"]), []).append(x.pop("title"))
    return d


def masked_wf(wf, reg, changes):
    w = copy.deepcopy(wf)
    for x in w["documents"]:
        if reg:
            x["must_show"] = mapped(reg, wf["id"], x["id"], x.get("must_show", []))
        changes.setdefault(("title", wf["id"], x["id"]), []).append(x.pop("title"))
    rf = (w.get("applies_when") or {}).get("fact")
    for f in w["facts"]:
        if f["id"] == rf:
            changes.setdefault(("routing question", wf["id"], rf), []).append(f.pop("question"))
    return w


def main():
    rep = {"label": "DEVELOPMENT, not a result", "regimes": {}}
    ok_all = True
    for r in REGIMES:
        new, old = G.Regime(r), G.Regime(r, S4 / "rules" / r / "rev2")
        for wf in new.workflows.values():
            W.validate_workflow(wf)
        x = {}
        man = jl(S4 / "dev" / r / "final" / "MANIFEST.json")
        x["final_files"] = len(man["files"])
        x["hash_mismatch"] = [f["file_id"] for f in man["files"] for n in ("reference.json", "design.json")
                              if sha(S4 / "dev" / r / "final" / f["file_id"] / n) != f["sha256"][n]]
        diffs = []
        for f in man["files"]:
            d = S4 / "dev" / r / "final" / f["file_id"]
            keep = bool((f.get("repair") or {}).get("changed_facts"))
            dd = same_ref(REF.engine_reference(W, new, jl(d / "design.json")), jl(d / "reference.json"),
                          CORE if keep else ("documents", "stop", "path", "presumed", "waiting_for", "unresolved", "outcome"))
            if dd:
                diffs.append({"file": f["file_id"], "differences": dd})
        x["final_recomputed_differences"] = diffs
        designs = [jl(p) for p in sorted((S4 / "dev" / r / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
        cr = []
        for ev in ("evaluator_a", "evaluator_b"):
            out = jl(S4 / "dev" / r / "cleanroom" / ev / "reference.json")
            rows = out.get("files") or out
            if isinstance(rows, list):
                rows = {row["file_id"]: row for row in rows}
            n = same = 0
            for dsg in designs:
                eng = REF.engine_reference(W, new, dsg)
                docs = (rows.get(dsg["file_id"]) or {}).get("documents") or rows.get(dsg["file_id"]) or {}
                for did, e in eng["documents"].items():
                    n += 1
                    same += ((docs.get(did) or {}).get("state") == e["state"])
            cr.append({"evaluator": ev, "documents": n, "same": same})
        x["cleanroom"] = cr
        ch_old, ch_new = {}, {}
        x["rules_equal_outside_named_changes"] = masked_rules(old.rules, new, ch_old) == masked_rules(new.rules, None, ch_new)
        wf_eq = {}
        for t in new.workflows:
            wf_eq[t] = masked_wf(old.workflows[t], new, ch_old) == masked_wf(new.workflows[t], None, ch_new)
        x["workflows_equal_outside_named_changes"] = wf_eq
        x["named_changes"] = sorted({f"{k[0]}: {k[1]}.{k[2]}" for k in ch_new if ch_old.get(k) != ch_new.get(k)})
        # item notes, per final file and supplied attachment
        n_old = G.ItemNotes(r, S4 / "generator" / "items" / "rev2" / f"{r}.json")
        n_new = G.ItemNotes(r)
        touched, stale = [], []
        for f in man["files"]:
            rec = jl(S4 / "dev" / r / "final" / f["file_id"] / "design.json")
            tid = rec["type"]
            for a in rec["attachments"]:
                if not a.get("supplied"):
                    continue
                did = a["document"]
                for i in old.doc(tid, did)["must_show"]:
                    now = new.current_item(tid, did, i)
                    if now is None:
                        continue
                    before = (n_old.conditional(tid, did, i), n_old.applies(tid, did, i, rec["facts"]), n_old.gloss(tid, did, i))
                    after = (n_new.conditional(tid, did, now), n_new.applies(tid, did, now, rec["facts"]), n_new.gloss(tid, did, now))
                    if before != after or now != i:
                        touched.append({"file": f["file_id"], "type": tid, "document": did, "round": f["round"],
                                        "designed": "sufficient" if a["sufficient"] else "missing: " + str(new.current_item(tid, did, a.get("missing"))),
                                        "item_now": now, "wording_changed": now != i,
                                        "applies_before": before[1], "applies_now": after[1],
                                        "checkable_as_changed": before[2] != after[2]})
                if a.get("missing"):
                    m_now = new.current_item(tid, did, a["missing"])
                    if m_now not in n_new.required_items(tid, did, new.doc(tid, did)["must_show"], rec["facts"]):
                        stale.append({"file": f["file_id"], "document": did, "designed_missing": m_now,
                                      "why": "the designed missing item no longer applies in this file: its designed "
                                             "state (insufficient) and the reference would change; not changed here"})
        x["attachments_touched_by_revised_items"] = touched
        x["designed_missing_item_no_longer_applies"] = stale
        ok = (not x["hash_mismatch"] and not diffs and all(c["documents"] == c["same"] == EXPECTED_CLEANROOM[r] for c in cr)
              and x["rules_equal_outside_named_changes"] and all(wf_eq.values()))
        x["ok"] = ok
        ok_all &= ok
        x["sha256_revised"] = {n: sha(S4 / "rules" / r / n) for n in ["rules.json", "rule_text.md", "MUST_SHOW_WORDING.json"]
                               + [f"workflow/{t}.json" for t in new.workflows]}
        rep["regimes"][r] = x
    rep["ok"] = ok_all
    (HERE / "VERIFY_REV3.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r, x in rep["regimes"].items():
        print(r, {k: v for k, v in x.items() if k in ("ok", "hash_mismatch", "final_recomputed_differences", "cleanroom",
                                                       "rules_equal_outside_named_changes", "named_changes")})
        print("  touched:", sorted({(t["file"], t["document"]) for t in x["attachments_touched_by_revised_items"]}))
        print("  stale missing:", x["designed_missing_item_no_longer_applies"])
    print("REFERENCES UNCHANGED; LOGIC EQUAL OUTSIDE THE NAMED CHANGES" if ok_all else "DIFFERENCES FOUND")


if __name__ == "__main__":
    main()

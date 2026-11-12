"""Check that revision 2 of the rule sets (must_show wording, SPEC.md item 6c; rules/<regime>/ vs rules/<regime>/rev1/)
touches no reference, no fact, no document need and no designed attachment state.
DEVELOPMENT material, not a result. No model calls; writes nothing outside lint/.

    python3 -I -B study4/lint/verify_rev2.py      # writes lint/VERIFY_REV2.json

1. Every stored final reference.json and design.json still has the SHA-256 that dev/<regime>/final/MANIFEST.json records.
   For files touched by a repair round (manifest `repair`), reference.json is byte-identical to before the repair; a
   design record differs from before only where the round's keep rule changed recorded states, exactly in those facts
   (and the kept_as_read flag dropped where the states are now the designed ones); the record before is rebuilt from
   the design and classify_round1.json and must hash to the recorded previous SHA-256.
2. The product's evaluator (generator/reference.py's engine_reference) recomputes every final file's reference with the
   revised workflows: document states, waited-for facts, stop, path, presumed facts equal the stored reference.
3. The clean-room comparison on the round-1 designs, re-run on the revised workflows: the engine's document states
   against both blind evaluators' stored outputs (354 / 450 / 436 documents, all equal, as for revision 1).
4. rules.json and the workflows: everything except must_show text is equal (as JSON) to rev1/; every must_show list of
   rev1/, read through rules/<regime>/MUST_SHOW_WORDING.json (removed items left out), equals the list now.
5. Item notes (generator/items/<regime>.json against generator/items/rev1/<regime>.json): for every design of
   dev/<regime>/designs and every item of every document of its type, the item is conditional, applies, and has the
   same checkable_as under both, read through the wording file; the designed missing item maps to an item the notes
   still require; the notes differ only in `item` keys (and the entry of a removed item).
6. Writer bundles: for every design, the bundle built from rev1/ and the rev1 notes equals the bundle built now once
   item texts are mapped and the fields added on 2026-11-12 (not_this, central_event_denied and its must_not_show
   line, the output's round) are set aside.
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
import writer_bundle as WB  # noqa: E402

W = REF.load_product(REF.PRODUCT_DEFAULT)
REGIMES = ["tenancy", "theft", "dismissal"]
EXPECTED_CLEANROOM = {"tenancy": 354, "theft": 450, "dismissal": 436}


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_ref(a, b):
    keys = ("documents", "stop", "path", "presumed", "waiting_for", "unresolved", "outcome")
    return {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}


def mapped(reg, tid, did, items):
    out = []
    for i in items:
        now = reg.current_item(tid, did, i)
        if now is not None:
            out.append(now)
    return out


def rules_without_must_show(doc, reg=None):
    d = copy.deepcopy(doc)
    for t in d["types"]:
        for x in t["documents"]:
            x["must_show"] = mapped(reg, t["id"], x["id"], x["must_show"]) if reg else x["must_show"]
    return d


def wf_mapped(wf, reg=None):
    w = copy.deepcopy(wf)
    for x in w["documents"]:
        if "must_show" in x and reg:
            x["must_show"] = mapped(reg, wf["id"], x["id"], x["must_show"])
    return w


def strip_new(bundle):
    b = copy.deepcopy(bundle)
    b.pop("central_event_denied", None)
    b["output"].pop("format", None)
    for q in b["questions"]:
        q.pop("not_this", None)
    for a in b["attachments"]:
        a["must_not_show"] = [x for x in a["must_not_show"] if "central_event_denied" not in x]
    return b


def map_bundle_items(bundle, reg, tid, amap):
    b = copy.deepcopy(bundle)
    for a in b["attachments"]:
        did = amap[a["label"]]
        for k in ("must_show", "show_only_if_it_applies", "does_not_apply_leave_out"):
            a[k] = mapped(reg, tid, did, a[k])
        a["checkable_as"] = [dict(g, item=reg.current_item(tid, did, g["item"])) for g in a["checkable_as"]]
        a["leave_out"] = reg.current_item(tid, did, a["leave_out"])
    return b


def main():
    rep = {"label": "DEVELOPMENT, not a result", "regimes": {}}
    ok_all = True
    for r in REGIMES:
        new, old = G.Regime(r), G.Regime(r, S4 / "rules" / r / "rev1")
        for wf in new.workflows.values():
            W.validate_workflow(wf)
        x = {}
        # 1-2 final references
        man = jl(S4 / "dev" / r / "final" / "MANIFEST.json")
        x["final_files"] = len(man["files"])
        x["hash_mismatch"] = [f["file_id"] for f in man["files"] for n in ("reference.json", "design.json")
                              if sha(S4 / "dev" / r / "final" / f["file_id"] / n) != f["sha256"][n]]
        # repair round 3 and later: every reference byte-identical to before the repair; a design record changes only
        # where the repair's keep rule changed recorded states, and then exactly in those facts (and, where the
        # states are now the designed ones, by dropping the kept_as_read flag and the facts_designed copy)
        cl_p = S4 / "dev" / r / "blindcheck" / "classify_round1.json"
        cl = jl(cl_p)["files"] if cl_p.exists() else {}
        ref_changed, design_changed, design_unexplained = [], [], []
        for f in man["files"]:
            rp = f.get("repair")
            if not rp:
                continue
            fdir = S4 / "dev" / r / "final" / f["file_id"]
            if sha(fdir / "reference.json") != rp["previous_sha256"]["reference.json"]:
                ref_changed.append(f["file_id"])
            if sha(fdir / "design.json") == rp["previous_sha256"]["design.json"]:
                if rp.get("changed_facts"):
                    design_unexplained.append(f["file_id"])
                continue
            # rebuild the record as it was before the repair and check it is the stored one
            dsg = jl(S4 / "dev" / r / "designs" / f"{f['file_id']}.json")
            prev = dict(dsg)
            if f["kept"] == "kept_as_read":
                prev.update(facts=cl[f["file_id"]]["facts_as_read"], facts_designed=dsg["facts"], kept_as_read=True)
            prev_ok = G.sha256_bytes(G.canon(prev).encode("utf-8")) == rp["previous_sha256"]["design.json"]
            now = jl(fdir / "design.json")
            expect = dict(prev, facts=dict(prev["facts"], **{k: v["now"] for k, v in (rp.get("changed_facts") or {}).items()}))
            if rp.get("states") == "as designed":
                expect.pop("kept_as_read", None)
                expect.pop("facts_designed", None)
            row = {"file": f["file_id"], "changed_facts": rp.get("changed_facts"), "states": rp.get("states"),
                   "previous_record_rebuilt": prev_ok, "record_is_previous_plus_changed_facts": now == expect,
                   "record_equals_design": now == dsg}
            (design_changed if prev_ok and now == expect and rp.get("changed_facts") else design_unexplained).append(row)
        x["repair_reference_changed"] = ref_changed
        x["repair_design_records_changed_by_keep_rule"] = design_changed
        x["repair_design_records_unexplained"] = design_unexplained
        keep_rule = {row["file"] for row in design_changed}
        diffs, keep_rule_ref = [], []
        for f in man["files"]:
            d = S4 / "dev" / r / "final" / f["file_id"]
            eng, stored = REF.engine_reference(W, new, jl(d / "design.json")), jl(d / "reference.json")
            dd = same_ref(eng, stored)
            if f["file_id"] in keep_rule:
                # the stored reference is kept from before the keep rule: document states and stop must still hold;
                # presumed / unresolved follow the fact moved between stated false and not mentioned
                core = {k: v for k, v in dd.items() if k in ("documents", "stop", "outcome", "waiting_for")}
                keep_rule_ref.append({"file": f["file_id"], "documents_and_stop_equal": not core,
                                      "other_fields_differing": sorted(set(dd) - set(core))})
                if core:
                    diffs.append({"file": f["file_id"], "differences": core})
            elif dd:
                diffs.append({"file": f["file_id"], "differences": dd})
        x["final_recomputed_differences"] = diffs
        x["keep_rule_files_recomputed"] = keep_rule_ref
        # 3 clean room
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
                other = rows.get(dsg["file_id"]) or {}
                docs = other.get("documents") or other
                for did, e in eng["documents"].items():
                    n += 1
                    same += ((docs.get(did) or {}).get("state") == e["state"])
            cr.append({"evaluator": ev, "documents": n, "same_state_as_engine_on_revised_workflows": same})
        x["cleanroom"] = cr
        x["cleanroom_documents_expected"] = EXPECTED_CLEANROOM[r]
        # 4 rules and workflows
        x["rules_equal_except_must_show_wording"] = rules_without_must_show(old.rules, new) == new.rules
        x["workflows_equal_except_must_show_wording"] = {t: wf_mapped(old.workflows[t], new) == new.workflows[t]
                                                        for t in new.workflows}
        wording = jl(S4 / "rules" / r / "MUST_SHOW_WORDING.json")["items"]
        x["must_show_rows"] = len(wording)
        x["must_show_instances"] = sum(len(w["types"]) for w in wording)
        x["must_show_removed"] = [w["rev1"] for w in wording if w["now"] is None]
        # 5 item notes
        n_old = G.ItemNotes(r, S4 / "generator" / "items" / "rev1" / f"{r}.json")
        n_new = G.ItemNotes(r)
        note_diffs, n_checked, removed_applied_unattached = [], 0, []
        for dsg in designs:
            tid = dsg["type"]
            for doc in old.documents(tid):
                did = doc["id"]
                for i in doc["must_show"]:
                    now = new.current_item(tid, did, i)
                    if now is None:
                        # a removed item may only ever have applied where its document is not attached (and so is
                        # never written or judged): there it changes nothing
                        if n_old.applies(tid, did, i, dsg["facts"]) is not False:
                            att = next((a for a in dsg["attachments"] if a["document"] == did), {})
                            ref = REF.engine_reference(W, new, dsg)["documents"].get(did, {}).get("state")
                            row = {"file": dsg["file_id"], "document": did, "item": i, "supplied": bool(att.get("supplied")),
                                   "document_state_in_reference": ref}
                            (note_diffs if att.get("supplied") else removed_applied_unattached).append(row)
                        continue
                    n_checked += 1
                    a = (n_old.conditional(tid, did, i), n_old.applies(tid, did, i, dsg["facts"]), n_old.gloss(tid, did, i))
                    b = (n_new.conditional(tid, did, now), n_new.applies(tid, did, now, dsg["facts"]), n_new.gloss(tid, did, now))
                    if a != b:
                        note_diffs.append({"file": dsg["file_id"], "document": did, "item": i, "rev1": a, "now": b})
        # entries are matched by (type or *, document): map through every type that has the document
        def key_entry(e, reg):
            tids = [e["type"]] if e.get("type") else [t for t in reg.type_ids if any(d["id"] == e["document"] for d in reg.documents(t))]
            nows = {reg.current_item(t, e["document"], e["item"]) for t in tids}
            return nows
        mapped_old = []
        for e in n_old.entries:
            nows = key_entry(e, new)
            assert len(nows) == 1, (r, e["item"])
            now = nows.pop()
            if now is not None:
                mapped_old.append(dict(e, item=now))
        x["item_notes_equal_after_renaming"] = mapped_old == n_new.entries
        x["item_notes_checked"] = n_checked
        x["item_notes_differences"] = note_diffs
        x["removed_item_applied_only_where_not_attached"] = removed_applied_unattached
        # 6 writer bundles
        style = (S4 / "generator" / "STYLE.md").read_text(encoding="utf-8")
        bdiff = []
        for dsg in designs:
            b_old, k_old = WB.build_one(old, dsg, style, n_old)
            b_new, k_new = WB.build_one(new, dsg, style, n_new)
            if k_old != k_new or map_bundle_items(strip_new(b_old), new, dsg["type"], k_old["attachments"]) != strip_new(b_new):
                bdiff.append(dsg["file_id"])
        x["writer_bundle_differences"] = bdiff
        ok = (not x["hash_mismatch"] and not diffs and not ref_changed and not design_unexplained
              and all(c["documents"] == c["same_state_as_engine_on_revised_workflows"] == EXPECTED_CLEANROOM[r] for c in cr)
              and x["rules_equal_except_must_show_wording"] and all(x["workflows_equal_except_must_show_wording"].values())
              and x["item_notes_equal_after_renaming"] and not note_diffs and not bdiff)
        x["ok"] = ok
        ok_all &= ok
        x["sha256_revised"] = {"rules.json": sha(S4 / "rules" / r / "rules.json"), "rule_text.md": sha(S4 / "rules" / r / "rule_text.md"),
                               "MUST_SHOW_WORDING.json": sha(S4 / "rules" / r / "MUST_SHOW_WORDING.json"),
                               **{f"workflow/{t}.json": sha(S4 / "rules" / r / "workflow" / f"{t}.json") for t in new.workflows}}
        x["sha256_rev1"] = {"rules.json": sha(S4 / "rules" / r / "rev1" / "rules.json"), "rule_text.md": sha(S4 / "rules" / r / "rev1" / "rule_text.md"),
                            **{f"workflow/{t}.json": sha(S4 / "rules" / r / "rev1" / "workflow" / f"{t}.json") for t in old.workflows}}
        rep["regimes"][r] = x
    rep["ok"] = ok_all
    (HERE / "VERIFY_REV2.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({r: {k: v for k, v in x.items() if not k.startswith("sha256")} for r, x in rep["regimes"].items()}, indent=1))
    print("ALL REFERENCES AND DESIGNED STATES UNCHANGED" if ok_all else "DIFFERENCES FOUND")


if __name__ == "__main__":
    main()

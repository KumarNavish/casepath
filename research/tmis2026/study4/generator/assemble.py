"""Assemble written files: blind-check inputs, comparison with the design, one rewrite, scan noise, final manifest.

Folders under study4/dev/<regime>/ (or --out):
  designs/, references/, writer_bundles/ (with KEYS.json)    from design.py, reference.py, writer_bundle.py
  written/<id>.json, written/<id>.r2.json                    from the writing session (WRITER_TASK.md)
  blindcheck/in/round<k>/<id>.json                           made here (`blind-in`), given to the blind checker
  blindcheck/out/round<k>/<id>.json                          from the blind-check session (BLIND_CHECK_TASK.md)
  blindcheck/compare_round<k>.json, rewrite/<id>.json        made here (`compare`)
  final/<id>/...  final/MANIFEST.json                        made here (`finalize`)

Steps:
  python3 -I -B assemble.py blind-in  --regime R --round 1
  (blind-check session writes blindcheck/out/round1/)
  python3 -I -B assemble.py compare   --regime R --round 1
  python3 -I -B assemble.py classify  --regime R             -> classify_round1.json, CLASSIFY.md, and
                                                                rewrite/<id>.json for the files to rewrite
  (writing session rewrites once from rewrite/<id>.json: written/<id>.r2.json)
  python3 -I -B assemble.py blind-in  --regime R --round 2   (only files with a rewrite request)
  python3 -I -B assemble.py compare   --regime R --round 2
  python3 -I -B assemble.py finalize  --regime R

Comparison rule: a file matches when every deciding fact's recovered state equals the designed state and every
attachment's recovered sufficiency equals the design (an insufficient attachment must be read as missing exactly
the designed item, and nothing else), and the message has the designed length.
Keep rule (from 2026-11-12): a file is kept without rewrite if it matches, or if every difference is a designed
"not mentioned" read as "stated false" and the engine reference from the states as read equals the design's
reference; such a file's recorded states become the states as read (designed states kept beside, flag
kept_as_read). Every other differing file gets one rewrite, against the designed states except where a
dependency rule makes a designed "not mentioned" impossible and an implied state leaves the reference unchanged
(target_round2). A file that still differs after round 2 is dropped and counted.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genlib as G  # noqa: E402
import noise as N  # noqa: E402


def paths(out):
    return {"designs": out / "designs", "refs": out / "references", "keys": out / "writer_bundles" / "KEYS.json",
            "written": out / "written", "bin": out / "blindcheck" / "in", "bout": out / "blindcheck" / "out",
            "bc": out / "blindcheck", "rewrite": out / "rewrite", "final": out / "final"}


def load_designs(p):
    return {d["file_id"]: d for d in (G.read_json(x) for x in sorted(p["designs"].glob("*.json"))
                                      if x.name != "MANIFEST.json")}


def written_path(p, fid, rnd):
    return p["written"] / (f"{fid}.json" if rnd == 1 else f"{fid}.r{rnd}.json")


def check_written(w, fid, key):
    errs = []
    if w.get("file_id") != fid:
        errs.append("file_id differs")
    labels = [a.get("label") for a in w.get("attachments", [])]
    if sorted(labels) != sorted(key["attachments"]):
        errs.append(f"attachment labels {labels} != {sorted(key['attachments'])}")
    if not isinstance(w.get("text"), str) or not w["text"].strip():
        errs.append("empty text")
    return errs


def blind_in(regime, out, rnd):
    p = paths(out)
    designs, keys = load_designs(p), G.read_json(p["keys"])["keys"]
    notes = G.ItemNotes(regime.name)
    todo = sorted(designs)
    if rnd > 1:
        cl = G.read_json(p["bc"] / "classify_round1.json")
        todo = sorted(fid for fid, c in cl["files"].items() if c["decision"] == "rewrite")
    dest = p["bin"] / f"round{rnd}"
    dest.mkdir(parents=True, exist_ok=True)
    made, missing = [], []
    for fid in todo:
        wp = written_path(p, fid, rnd)
        if not wp.exists():
            missing.append(fid)
            continue
        w, d, key = G.read_json(wp), designs[fid], keys[fid]
        errs = check_written(w, fid, key)
        if errs:
            raise SystemExit(f"{wp}: {errs}")
        texts = {a["label"]: a["text"] for a in w["attachments"]}
        item = {"file_id": fid, "text": w["text"],
                "attachments": [{"label": lab, "document_title": regime.doc(d["type"], did)["title"],
                                 "must_show": regime.doc(d["type"], did)["must_show"],
                                 "checkable_as": [{"item": i, "checkable_as": notes.gloss(d["type"], did, i)}
                                                  for i in regime.doc(d["type"], did)["must_show"]
                                                  if notes.gloss(d["type"], did, i)],
                                 "text": texts[lab]}
                                for lab, did in key["attachments"].items()],
                "questions": [{"label": lab, "question": regime.fact(d["type"], f)["question"]}
                              for lab, f in key["questions"].items()]}
        G.write_json(dest / f"{fid}.json", item)
        made.append(fid)
    print(f"round {rnd}: {len(made)} blind-check inputs written to {dest}; no written file for {len(missing)}")
    return made, missing


def compare_one(d, key, w, b, target=None):
    """Mismatches between design (or a round-2 target of fact states) and blind reading; empty when it matches."""
    mm = []
    facts = target or d["facts"]
    for lab, f in key["questions"].items():
        got = (b.get("facts", {}).get(lab) or {}).get("state")
        if got != facts[f]:
            mm.append({"label": lab, "kind": "question", "fact": f, "designed": facts[f], "read_as": got})
    att = {a["document"]: a for a in d["attachments"]}
    for lab, did in key["attachments"].items():
        a = att[did]
        got = b.get("attachments", {}).get(lab) or {}
        want = {"state": "sufficient"} if a["sufficient"] else {"state": "insufficient", "missing": [a["missing"]]}
        ok = got.get("state") == want["state"] and (want["state"] == "sufficient" or got.get("missing") == want["missing"])
        if not ok:
            mm.append({"label": lab, "kind": "attachment", "document": did, "designed": want, "read_as": got})
    words = len(w["text"].split())
    lo, hi = d["words"]
    if not lo <= words <= hi:
        mm.append({"label": "text", "kind": "length", "designed": [lo, hi], "read_as": words})
    return mm


def compare(regime, out, rnd):
    p = paths(out)
    designs, keys = load_designs(p), G.read_json(p["keys"])["keys"]
    targets = {}
    if rnd == 2:
        cl = G.read_json(p["bc"] / "classify_round1.json")["files"]
        targets = {fid: c["target_round2"] for fid, c in cl.items() if c.get("target_round2")}
    src = p["bout"] / f"round{rnd}"
    res = {}
    for bp in sorted(src.glob("*.json")):
        fid = bp.stem
        b = G.read_json(bp)
        w = G.read_json(written_path(p, fid, rnd))
        mm = compare_one(designs[fid], keys[fid], w, b, targets.get(fid))
        res[fid] = {"matches": not mm, "mismatches": mm, "blind_sha256": G.sha256_file(bp),
                    "written_sha256": G.sha256_file(written_path(p, fid, rnd))}
    G.write_json(p["bc"] / f"compare_round{rnd}.json", res)
    n_ok = sum(r["matches"] for r in res.values())
    print(f"round {rnd}: {len(res)} compared, {n_ok} match, {len(res) - n_ok} differ"
          + (" (next: classify --round 1)" if rnd == 1 else ""))
    return res


# ----------------------------------------------------------------- classification and the keep / rewrite rule
ANS = {"stated_true": "yes", "stated_false": "no", "open": "open", "not_mentioned": "not mentioned"}


def _ref_key(ref):
    return ({k: (v["state"], tuple(v.get("waits_for") or ())) for k, v in ref["documents"].items()},
            ref["stop"]["state"], ref["stop"].get("step"), tuple(ref["stop"].get("steps") or ()))


def _ref_diff(a, b):
    out = [{"document": k, "design": a["documents"][k]["state"], "as_read": b["documents"][k]["state"],
            "design_waits_for": a["documents"][k].get("waits_for"), "as_read_waits_for": b["documents"][k].get("waits_for")}
           for k in a["documents"] if (a["documents"][k]["state"], a["documents"][k].get("waits_for"))
           != (b["documents"][k]["state"], b["documents"][k].get("waits_for"))]
    if a["stop"] != b["stop"]:
        out.append({"stop": True, "design": a["stop"], "as_read": b["stop"]})
    return out


def implications(regime, d, fact, constraints, notes):
    """Dependency rules whose antecedent holds in the design and which answer `fact`: [(rule note, implying item,
    implied states, value the rule sets)]."""
    tid, states = d["type"], d["facts"]
    facts = set(states)
    drawn = {x["fact"]: x["drawn"] for x in d.get("always_stated_not_mentioned", [])}
    out = []
    for c in constraints:
        kind = c.get("kind")
        if kind is None and c["then"]["fact"] == fact and all(f in facts for f in G.state_facts(c["if"])) \
                and G.state_match(c["if"], states):
            out.append({"rule": c.get("note", ""), "implying": "designed answer(s): " + ", ".join(
                f"{f} {ANS[states[f]]}" for f in G.state_facts(c["if"])), "implied": c["then"]["in"],
                "sets": c["then"]["set"]})
        elif kind == "stated_if" and c["fact"] == fact and all(f in facts for f in G.state_facts(c["if"])) \
                and G.state_match(c["if"], states):
            out.append({"rule": c.get("note", ""), "implying": "designed answer(s): " + ", ".join(
                f"{f} {ANS[states[f]]}" for f in G.state_facts(c["if"]) if G.state_match({"fact": f, "in": ["stated_true", "open"]}, states)),
                "implied": ["stated_true", "stated_false"], "sets": drawn.get(fact, c.get("set_default", "stated_false"))})
        elif kind == "attachment_implies" and c["fact"] == fact:
            for a in d["attachments"]:
                if not a["supplied"] or a["document"] != c["document"]:
                    continue
                item = c.get("item")
                if item and (a.get("missing") == item or item not in regime.doc(tid, a["document"])["must_show"]):
                    continue
                sets = c.get("set", "drawn")
                if sets == "drawn":
                    sets = drawn.get(fact) if drawn.get(fact) in c["implies"] else c["implies"][0]
                out.append({"rule": c.get("note", ""), "implying": f"attachment {a['document']}"
                            + (f", item '{item}'" if item else " (the document itself)"),
                            "implied": c["implies"], "sets": sets})
    return out


def classify(regime, out, product=None):
    """Round 1 only. For each differing file: (a) the engine reference from the states as read, against the design's
    reference; (b) per question mismatch, the dependency rules that imply the read state; (c) per attachment mismatch,
    the must_show items at issue with their notes. Then the keep / rewrite rule, the round-2 targets and the rewrite
    requests. See README, "Blind check, classification and the keep rule"."""
    sys.dont_write_bytecode = True
    import reference as R
    W = R.load_product(product or R.PRODUCT_DEFAULT)
    p = paths(out)
    designs, keys = load_designs(p), G.read_json(p["keys"])["keys"]
    cmp1 = G.read_json(p["bc"] / "compare_round1.json")
    cpath = out / "constraints.json"
    constraints = G.read_json(cpath)["constraints"] if cpath.exists() else []
    notes = G.ItemNotes(regime.name)
    style = (G.GEN / "STYLE.md").read_text(encoding="utf-8")
    import writer_bundle as WB
    res, counts = {}, Counter()
    for fid, cmpr in sorted(cmp1.items()):
        counts["compared"] += 1
        if cmpr["matches"]:
            counts["exact"] += 1
            continue
        d, key = designs[fid], keys[fid]
        b = G.read_json(p["bout"] / "round1" / f"{fid}.json")
        ref = G.read_json(p["refs"] / f"{fid}.json")
        read_facts = dict(d["facts"])
        read_att = [dict(a) for a in d["attachments"]]
        qrows, arows, other = [], [], []
        for m in cmpr["mismatches"]:
            if m["kind"] == "question":
                f = m.get("fact") or key["questions"][m["label"]]
                read_facts[f] = m["read_as"]
                imp = implications(regime, d, f, constraints, notes)
                explains = [x for x in imp if m["read_as"] in x["implied"]]
                raised = [x for x in imp if m["read_as"] == "open" and "not_mentioned" not in x["implied"]]
                qrows.append({"label": m["label"], "fact": f, "designed": m["designed"], "read_as": m["read_as"],
                              "quote": (b["facts"].get(m["label"]) or {}).get("quote"),
                              "implied_by": imp,
                              "verdict": ("implied: the read state follows from " + "; ".join(x["implying"] for x in explains))
                              if explains else ("raised by " + "; ".join(x["implying"] for x in raised)
                                                + ", read open because the text leaves it unsettled") if raised
                              else "no implying answer or item found: writing or reading error"})
            elif m["kind"] == "attachment":
                did = m.get("document") or key["attachments"][m["label"]]
                got = m["read_as"] or {}
                for a in read_att:
                    if a["document"] == did:
                        a["sufficient"] = got.get("state") == "sufficient"
                want_missing = set(m["designed"].get("missing") or [])
                got_missing = set(got.get("missing") or [])
                items = []
                for i in sorted(want_missing ^ got_missing):
                    e = notes.get(d["type"], did, i)
                    items.append({"item": i, "designed": "missing" if i in want_missing else "shown",
                                  "read": "missing" if i in got_missing else "shown",
                                  "conditional": notes.conditional(d["type"], did, i),
                                  "applies_in_this_file": notes.applies(d["type"], did, i, d["facts"]),
                                  "checkable_as": e.get("checkable_as"),
                                  "rule_set_wording": e.get("rule_set_wording"),
                                  "checkable_from_document": not bool(e.get("rule_set_wording"))})
                arows.append({"label": m["label"], "document": did, "designed": m["designed"], "read_as": got,
                              "blind_reason": got.get("reason"), "items_at_issue": items})
            else:
                other.append(m)
        alt = dict(d, facts=read_facts, attachments=read_att)
        ref_read = R.engine_reference(W, regime, alt)
        diff = _ref_diff(ref, ref_read)
        equivalent = not diff
        only_nm_false = all(q["designed"] == "not_mentioned" and q["read_as"] == "stated_false" for q in qrows) \
            and not arows and not other
        decision = "kept_as_read" if (only_nm_false and equivalent) else "rewrite"
        counts["differing"] += 1
        counts["reference_equivalent"] += equivalent
        counts[decision] += 1
        row = {"decision": decision, "reference_equivalent": equivalent, "reference_changes": diff,
               "questions": qrows, "attachments": arows, "other": other}
        if decision == "kept_as_read":
            row["facts_as_read"] = read_facts
            row["reference_as_read"] = {k: ref_read[k] for k in ("documents", "stop", "facts_given", "presumed", "unresolved")}
        else:
            # round-2 target: the designed states, except where a dependency rule makes a designed "not mentioned"
            # impossible and an implied state keeps the reference unchanged
            target, revised = dict(d["facts"]), []
            for q in qrows:
                if q["designed"] != "not_mentioned" or not q["implied_by"]:
                    continue
                cands = []
                for x in q["implied_by"]:
                    if q["read_as"] in x["implied"]:
                        cands.append(q["read_as"])
                    if x["sets"] in ("stated_true", "stated_false"):
                        cands.append(x["sets"])
                for c in dict.fromkeys(cands):
                    trial = dict(target, **{q["fact"]: c})
                    if not _ref_diff(ref, R.engine_reference(W, regime, dict(d, facts=trial))):
                        target = trial
                        revised.append({"label": q["label"], "fact": q["fact"], "from": "not_mentioned", "to": c,
                                        "because": "; ".join(x["implying"] for x in q["implied_by"])})
                        break
                else:
                    revised.append({"label": q["label"], "fact": q["fact"], "from": "not_mentioned", "to": None,
                                    "because": "implied state would change the reference; designed state kept, the "
                                               "rewrite may not be able to meet it"})
            row["target_round2"] = target
            row["target_revisions"] = revised
            if any(r["to"] for r in revised):
                row["reference_target"] = {k: v for k, v in R.engine_reference(W, regime, dict(d, facts=target)).items()
                                           if k in ("documents", "stop", "facts_given", "presumed", "unresolved")}
        res[fid] = row
    # rewrite requests: only for the files to rewrite (stale ones from an earlier compare are removed)
    p["rewrite"].mkdir(parents=True, exist_ok=True)
    for old in p["rewrite"].glob("*.json"):
        if res.get(old.stem, {}).get("decision") != "rewrite":
            old.unlink()
    for fid, row in res.items():
        if row["decision"] != "rewrite":
            continue
        d = designs[fid]
        bundle, key2 = WB.build_one(regime, d, style, notes, facts=row["target_round2"])
        assert key2 == keys[fid], f"{fid}: labels changed"
        told = [{"label": q["label"], "kind": "question", "designed": ANS[q["designed"]], "read_as": ANS.get(q["read_as"], q["read_as"])}
                for q in row["questions"]]
        told += [{"label": a["label"], "kind": "attachment", "designed": a["designed"], "read_as": a["read_as"]}
                 for a in row["attachments"]] + row["other"]
        G.write_json(p["rewrite"] / f"{fid}.json", {
            "file_id": fid, "round": 2, "mismatches": told,
            "answers_changed": [{"label": r["label"], "now": ANS[r["to"]], "was": "not mentioned",
                                 "why": "another answer or an attachment of this file already answers it"}
                                for r in row["target_revisions"] if r["to"]],
            "bundle": bundle, "previous": f"written/{fid}.json"})
    summary = {k: counts[k] for k in ("compared", "exact", "differing", "kept_as_read", "rewrite", "reference_equivalent")}
    G.write_json(p["bc"] / "classify_round1.json", {
        "schema": "study4.classify/1", "regime": regime.name, "counts": summary,
        "rule": "kept without rewrite if exact, or if every difference is a designed 'not mentioned' read as 'stated "
                "false' and the engine reference from the states as read equals the design's reference; every other "
                "differing file gets one rewrite",
        "constraints_sha256": G.sha256_file(cpath) if cpath.exists() else None, "item_notes_sha256": notes.sha256,
        "files": res})
    write_classify_md(regime, p, summary, res)
    print(f"classify: {summary}")
    return summary, res


def write_classify_md(regime, p, summary, res):
    L = [f"# Round-1 blind check: classification ({regime.name})", "",
         "Generated by `assemble.py classify`; data in `classify_round1.json`. Development material.", "",
         f"Files {summary['compared']}: exact {summary['exact']}, differing {summary['differing']} "
         f"(reference-equivalent {summary['reference_equivalent']}); kept as read {summary['kept_as_read']}, "
         f"to rewrite {summary['rewrite']}.", "",
         "| file | decision | ref.-equivalent | question differences (designed -> read: verdict) | attachment differences (items at issue) |",
         "|---|---|---|---|---|"]
    for fid, r in sorted(res.items()):
        qs = "; ".join(f"{q['fact']} {ANS[q['designed']]} -> {ANS.get(q['read_as'], q['read_as'])}: {q['verdict']}"
                       for q in r["questions"]) or "-"
        at = "; ".join(f"{a['document']}: " + ", ".join(f"'{i['item']}' designed {i['designed']}, read {i['read']}"
                                                         for i in a["items_at_issue"]) for a in r["attachments"]) or "-"
        if r["other"]:
            at += "; " + "; ".join(f"{o['kind']} {o['read_as']}" for o in r["other"])
        ch = "yes" if r["reference_equivalent"] else "no: " + ", ".join(
            x.get("document", "stop") + f" {x.get('design')}->{x.get('as_read')}" for x in r["reference_changes"])
        rev = "".join(f" (round-2 target: {x['fact']} -> {ANS[x['to']] if x['to'] else 'kept'})"
                      for x in r.get("target_revisions", []))
        L.append(f"| {fid} | {r['decision']}{rev} | {ch} | {qs} | {at} |".replace("\n", " "))
    (p["bc"] / "CLASSIFY.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def finalize(regime, out):
    p = paths(out)
    designs = load_designs(p)
    c1 = G.read_json(p["bc"] / "compare_round1.json") if (p["bc"] / "compare_round1.json").exists() else {}
    c2 = G.read_json(p["bc"] / "compare_round2.json") if (p["bc"] / "compare_round2.json").exists() else {}
    keys = G.read_json(p["keys"])["keys"]
    clp = p["bc"] / "classify_round1.json"
    cl = G.read_json(clp)["files"] if clp.exists() else {}
    p["final"].mkdir(parents=True, exist_ok=True)
    entries, dropped = [], []
    for fid, d in sorted(designs.items()):
        c = cl.get(fid, {})
        how = None
        if c1.get(fid, {}).get("matches"):
            rnd, how = 1, "exact"
        elif c.get("decision") == "kept_as_read":
            rnd, how = 1, "kept_as_read"
        elif c2.get(fid, {}).get("matches"):
            rnd, how = 2, "rewritten"
        else:
            why = "not written" if fid not in c1 else "differs after rewrite" if fid in c2 else "no rewrite checked"
            dropped.append({"file_id": fid, "level": d["level"], "type": d["type"], "why": why})
            continue
        w = G.read_json(written_path(p, fid, rnd))
        b = p["bout"] / f"round{rnd}" / f"{fid}.json"
        fdir = p["final"] / fid
        fdir.mkdir(parents=True, exist_ok=True)
        rec = dict(d)
        ref = G.read_json(p["refs"] / f"{fid}.json") if (p["refs"] / f"{fid}.json").exists() else None
        if how == "kept_as_read":
            # the recorded states become the states as read; the designed ones are kept beside them
            rec.update(facts=c["facts_as_read"], facts_designed=d["facts"], kept_as_read=True)
            ref = dict(ref, **c["reference_as_read"], note="recomputed from the states as read; reference-"
                                                           "equivalent to the design's (classify_round1.json)")
        elif how == "rewritten" and any(r["to"] for r in c.get("target_revisions", [])):
            rec.update(facts=c["target_round2"], facts_designed=d["facts"], revised_by_implication=True,
                       target_revisions=c["target_revisions"])
            ref = dict(ref, **c["reference_target"], note="recomputed from the round-2 target states; "
                                                          "reference-equivalent to the design's")
        hashes = {"design.json": G.write_json(fdir / "design.json", rec)}
        if ref is not None:
            hashes["reference.json"] = G.write_json(fdir / "reference.json", ref)
        hashes["blind_check.json"] = G.write_json(fdir / "blind_check.json", G.read_json(b))
        texts = {"text": w["text"]}
        for a in w["attachments"]:
            texts["attachments/" + keys[fid]["attachments"][a["label"]]] = a["text"]
        noise_log = {}
        for name, clean in texts.items():
            (fdir / (name + ".clean.txt")).parent.mkdir(parents=True, exist_ok=True)
            (fdir / (name + ".clean.txt")).write_text(clean, encoding="utf-8")
            hashes[name + ".clean.txt"] = G.sha256_file(fdir / (name + ".clean.txt"))
            if d["scan_noise"]:
                deg, rec = N.degrade(clean, G.sub_seed(d["seed"], fid, name, "noise"))
                assert N.restore(deg, rec) == clean
                (fdir / (name + ".txt")).write_text(deg, encoding="utf-8")
                noise_log[name] = {**N.stats(rec, clean), "record": rec}
            else:
                (fdir / (name + ".txt")).write_text(clean, encoding="utf-8")
            hashes[name + ".txt"] = G.sha256_file(fdir / (name + ".txt"))
        if noise_log:
            hashes["noise.json"] = G.write_json(fdir / "noise.json", noise_log)
        entries.append({"file_id": fid, "level": d["level"], "type": d["type"], "round": rnd, "kept": how,
                        "scan_noise": d["scan_noise"], "denied_event": d["denied_event"],
                        "open_facts": d["open_facts"], "language": d["language"], "sha256": hashes})
    per_level = Counter(e["level"] for e in entries)
    open_lv = Counter(e["level"] for e in entries if e["open_facts"])
    G.write_json(p["final"] / "MANIFEST.json", {
        "schema": "study4.final-manifest/1", "regime": regime.name, "files": entries, "dropped": dropped,
        "counts": {"kept": len(entries), "dropped": len(dropped),
                   "kept_after_rewrite": sum(e["round"] == 2 for e in entries),
                   "kept_as_read": sum(e["kept"] == "kept_as_read" for e in entries),
                   "per_level": {str(k): v for k, v in sorted(per_level.items())},
                   "open_share_per_level": {str(k): round(open_lv[k] / v, 3) for k, v in sorted(per_level.items())}},
        "design_manifest_sha256": G.sha256_file(p["designs"] / "MANIFEST.json"),
        "assemble_sha256": G.sha256_file(Path(__file__)), "noise_sha256": G.sha256_file(G.GEN / "noise.py")})
    print(f"final: {len(entries)} kept, {len(dropped)} dropped")
    return entries, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["blind-in", "compare", "classify", "finalize"])
    ap.add_argument("--product", help="the product's casepath-internal folder (classify)")
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir")
    ap.add_argument("--out")
    ap.add_argument("--round", type=int, default=1, choices=[1, 2])
    a = ap.parse_args(argv)
    regime = G.Regime(a.regime, a.rules_dir)
    out = Path(a.out) if a.out else G.DEV / a.regime
    if a.step == "blind-in":
        blind_in(regime, out, a.round)
    elif a.step == "compare":
        compare(regime, out, a.round)
    elif a.step == "classify":
        classify(regime, out, a.product)
    else:
        finalize(regime, out)


if __name__ == "__main__":
    main()

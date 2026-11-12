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
  python3 -I -B assemble.py compare   --regime R --round 1   -> rewrite/<id>.json for every differing file
  (writing session rewrites once: written/<id>.r2.json)
  python3 -I -B assemble.py blind-in  --regime R --round 2   (only files with a rewrite request)
  python3 -I -B assemble.py compare   --regime R --round 2
  python3 -I -B assemble.py finalize  --regime R

Comparison rule: a file matches when every deciding fact's recovered state equals the designed state and every
attachment's recovered sufficiency equals the design (an insufficient attachment must be read as missing exactly
the designed item, and nothing else), and the message has the designed length. A file that differs after round 1
gets one rewrite; a file that still differs after round 2 (or has no rewrite) is dropped and counted.
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
    todo = sorted(designs)
    if rnd > 1:
        todo = sorted(x.stem for x in p["rewrite"].glob("*.json"))
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
                                 "must_show": regime.doc(d["type"], did)["must_show"], "text": texts[lab]}
                                for lab, did in key["attachments"].items()],
                "questions": [{"label": lab, "question": regime.fact(d["type"], f)["question"]}
                              for lab, f in key["questions"].items()]}
        G.write_json(dest / f"{fid}.json", item)
        made.append(fid)
    print(f"round {rnd}: {len(made)} blind-check inputs written to {dest}; no written file for {len(missing)}")
    return made, missing


def compare_one(d, key, w, b):
    """Mismatches between design and blind reading (list of dicts, empty when the file matches)."""
    mm = []
    for lab, f in key["questions"].items():
        got = (b.get("facts", {}).get(lab) or {}).get("state")
        if got != d["facts"][f]:
            mm.append({"label": lab, "kind": "question", "designed": d["facts"][f], "read_as": got})
    att = {a["document"]: a for a in d["attachments"]}
    for lab, did in key["attachments"].items():
        a = att[did]
        got = b.get("attachments", {}).get(lab) or {}
        want = {"state": "sufficient"} if a["sufficient"] else {"state": "insufficient", "missing": [a["missing"]]}
        ok = got.get("state") == want["state"] and (want["state"] == "sufficient" or got.get("missing") == want["missing"])
        if not ok:
            mm.append({"label": lab, "kind": "attachment", "designed": want, "read_as": got})
    words = len(w["text"].split())
    lo, hi = d["words"]
    if not lo <= words <= hi:
        mm.append({"label": "text", "kind": "length", "designed": [lo, hi], "read_as": words})
    return mm


def compare(regime, out, rnd):
    p = paths(out)
    designs, keys = load_designs(p), G.read_json(p["keys"])["keys"]
    src = p["bout"] / f"round{rnd}"
    res = {}
    for bp in sorted(src.glob("*.json")):
        fid = bp.stem
        b = G.read_json(bp)
        w = G.read_json(written_path(p, fid, rnd))
        mm = compare_one(designs[fid], keys[fid], w, b)
        res[fid] = {"matches": not mm, "mismatches": mm, "blind_sha256": G.sha256_file(bp),
                    "written_sha256": G.sha256_file(written_path(p, fid, rnd))}
        if rnd == 1 and mm:
            ans = {"stated_true": "yes", "stated_false": "no", "open": "open", "not_mentioned": "not mentioned"}
            told = [{**x, "designed": ans.get(x["designed"], x["designed"]), "read_as": ans.get(x["read_as"], x["read_as"])}
                    if x["kind"] == "question" else x for x in mm]
            G.write_json(p["rewrite"] / f"{fid}.json", {"file_id": fid, "round": 2, "mismatches": told,
                                                       "previous": f"written/{fid}.json"})
    G.write_json(p["bc"] / f"compare_round{rnd}.json", res)
    n_ok = sum(r["matches"] for r in res.values())
    print(f"round {rnd}: {len(res)} compared, {n_ok} match, {len(res) - n_ok} differ")
    return res


def finalize(regime, out):
    p = paths(out)
    designs = load_designs(p)
    c1 = G.read_json(p["bc"] / "compare_round1.json") if (p["bc"] / "compare_round1.json").exists() else {}
    c2 = G.read_json(p["bc"] / "compare_round2.json") if (p["bc"] / "compare_round2.json").exists() else {}
    keys = G.read_json(p["keys"])["keys"]
    p["final"].mkdir(parents=True, exist_ok=True)
    entries, dropped = [], []
    for fid, d in sorted(designs.items()):
        if c1.get(fid, {}).get("matches"):
            rnd = 1
        elif c2.get(fid, {}).get("matches"):
            rnd = 2
        else:
            why = "not written" if fid not in c1 else "differs after rewrite" if fid in c2 else "no rewrite checked"
            dropped.append({"file_id": fid, "level": d["level"], "type": d["type"], "why": why})
            continue
        w = G.read_json(written_path(p, fid, rnd))
        b = p["bout"] / f"round{rnd}" / f"{fid}.json"
        fdir = p["final"] / fid
        fdir.mkdir(parents=True, exist_ok=True)
        hashes = {"design.json": G.write_json(fdir / "design.json", d)}
        ref = p["refs"] / f"{fid}.json"
        if ref.exists():
            hashes["reference.json"] = G.write_json(fdir / "reference.json", G.read_json(ref))
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
        entries.append({"file_id": fid, "level": d["level"], "type": d["type"], "round": rnd,
                        "scan_noise": d["scan_noise"], "denied_event": d["denied_event"],
                        "open_facts": d["open_facts"], "language": d["language"], "sha256": hashes})
    per_level = Counter(e["level"] for e in entries)
    open_lv = Counter(e["level"] for e in entries if e["open_facts"])
    G.write_json(p["final"] / "MANIFEST.json", {
        "schema": "study4.final-manifest/1", "regime": regime.name, "files": entries, "dropped": dropped,
        "counts": {"kept": len(entries), "dropped": len(dropped),
                   "kept_after_rewrite": sum(e["round"] == 2 for e in entries),
                   "per_level": {str(k): v for k, v in sorted(per_level.items())},
                   "open_share_per_level": {str(k): round(open_lv[k] / v, 3) for k, v in sorted(per_level.items())}},
        "design_manifest_sha256": G.sha256_file(p["designs"] / "MANIFEST.json"),
        "assemble_sha256": G.sha256_file(Path(__file__)), "noise_sha256": G.sha256_file(G.GEN / "noise.py")})
    print(f"final: {len(entries)} kept, {len(dropped)} dropped")
    return entries, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["blind-in", "compare", "finalize"])
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
    else:
        finalize(regime, out)


if __name__ == "__main__":
    main()

"""Tests of the model-free generator. Run: python3 -I -B -m unittest study4/generator/test_generator.py
(from research/tmis2026) or python3 -I -B study4/generator/test_generator.py. Everything is written to temporary
folders; nothing under dev/ is touched. Regimes without rules are skipped."""
import random
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble as A  # noqa: E402
import cleanroom_bundle as C  # noqa: E402
import design as D  # noqa: E402
import genlib as G  # noqa: E402
import noise as N  # noqa: E402
import reference as R  # noqa: E402
import writer_bundle as WB  # noqa: E402

REGIMES = [r for r in ("tenancy", "theft", "dismissal") if (G.RULES / r / "rules.json").exists()]
PRODUCT = Path(R.PRODUCT_DEFAULT)


def run_design(regime, out, seed=20261112, extra=()):
    out.mkdir(parents=True, exist_ok=True)
    c = G.DEV / regime / "constraints.json"
    if c.exists():
        shutil.copyfile(c, out / "constraints.json")
    return D.main(["--regime", regime, "--out", str(out), "--seed", str(seed), "--quiet", *extra])


def designs(out):
    return [G.read_json(p) for p in sorted((out / "designs").glob("*.json")) if p.name != "MANIFEST.json"]


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="study4gen_"))
        cls.out = {}
        for r in REGIMES:
            cls.out[r] = cls.tmp / r
            run_design(r, cls.out[r])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_determinism(self):
        for r in REGIMES:
            m1 = G.read_json(self.out[r] / "designs" / "MANIFEST.json")
            m2 = run_design(r, self.tmp / f"{r}_again")
            self.assertEqual([f["sha256"] for f in m1["files"]], [f["sha256"] for f in m2["files"]], r)
            m3 = run_design(r, self.tmp / f"{r}_other", seed=7)
            self.assertNotEqual([f["sha256"] for f in m1["files"]], [f["sha256"] for f in m3["files"]], r)

    def test_share_levels_exact(self):
        for r in REGIMES:
            ds = designs(self.out[r])
            for level in D.DEFAULTS["levels"]:
                lv = [d for d in ds if d["level"] == level]
                self.assertEqual(len(lv), 15)
                self.assertEqual(sum(bool(d["open_facts"]) for d in lv), G.level_counts(15, level / 100), (r, level))
                self.assertTrue(all(len(d["open_facts"]) <= 1 for d in lv))
                self.assertEqual(sum(sum(s == "open" for s in d["facts"].values()) for d in lv),
                                 G.level_counts(15, level / 100))
            self.assertEqual([G.level_counts(15, x / 100) for x in (0, 10, 25, 50)], [0, 2, 4, 8])

    def test_always_stated_and_defining_event(self):
        for r in REGIMES:
            reg = G.Regime(r)
            for d in designs(self.out[r]):
                for f in reg.always_stated(d["type"]):
                    self.assertNotEqual(d["facts"][f], "not_mentioned", (r, d["file_id"], f))
                ev = d["facts"][reg.defining_event(d["type"])]
                if d["denied_event"]:
                    self.assertEqual(ev, "stated_false")
                elif reg.defining_event(d["type"]) in d["open_facts"]:
                    self.assertEqual(ev, "open")
                else:
                    self.assertEqual(ev, "stated_true")

    def test_denied_share(self):
        for r in REGIMES:
            ds = designs(self.out[r])
            for level in D.DEFAULTS["levels"]:
                lv = [d for d in ds if d["level"] == level]
                self.assertEqual(sum(d["denied_event"] for d in lv), G.level_counts(15, 0.10))
                self.assertFalse(any(d["denied_event"] and d["open_facts"] for d in lv))
            self.assertEqual(sum(d["language"] == "de" for d in ds), 4 * G.level_counts(15, 0.5))
            self.assertEqual(sum(d["scan_noise"] for d in ds), 4 * G.level_counts(15, 0.2))

    def test_attachments_only_where_needed(self):
        for r in REGIMES:
            reg = G.Regime(r)
            for d in designs(self.out[r]):
                o = G.rules_outcome(reg, d["type"], G.resolve(reg, d["type"], d["facts"]))
                for a in d["attachments"]:
                    if a["supplied"]:
                        self.assertTrue(o["documents"][a["document"]]["always"], (r, d["file_id"], a))
                        if not a["sufficient"]:
                            self.assertIn(a["missing"], reg.doc(d["type"], a["document"])["must_show"])

    @unittest.skipUnless(PRODUCT.exists(), "product worktree not available")
    def test_references_reproduce(self):
        for r in REGIMES:
            R.main(["--regime", r, "--out", str(self.out[r]), "--quiet"])
            m1 = G.read_json(self.out[r] / "references" / "MANIFEST.json")
            R.main(["--regime", r, "--out", str(self.out[r]), "--quiet"])
            m2 = G.read_json(self.out[r] / "references" / "MANIFEST.json")
            self.assertEqual(m1["files"], m2["files"], r)
            for p in (self.out[r] / "references").glob("*_*.json"):
                ref = G.read_json(p)
                self.assertTrue(set(e["state"] for e in ref["documents"].values()) <= set(G.REF_STATES))

    def test_writer_bundle_has_no_forbidden_content(self):
        for r in REGIMES:
            reg = G.Regime(r)
            WB.build(r, out=self.out[r])
            C.build(r, out=self.out[r])
            all_ids = {d["file_id"] for d in designs(self.out[r])}
            passages = []
            for t in reg.rules["types"]:
                for x in t["facts"] + t["steps"] + t["documents"] + t["presumptions"] + t["stops"]:
                    rule = x.get("rule") or {}
                    if rule.get("passage"):
                        passages.append(rule["passage"])
            for t in reg.rules["types"]:
                for f in t["facts"]:
                    if f.get("not_this"):
                        passages.append(f["not_this"])
            ids = set()
            for t in reg.rules["types"]:
                ids |= {s["id"] for s in t["steps"]} | {f["id"] for f in t["facts"]} | {d["id"] for d in t["documents"]}
                ids.add(t["id"])
            for wf in reg.workflows.values():
                ids |= {s["id"] for s in wf["steps"]}
            for p in (self.out[r] / "writer_bundles").glob("*.json"):
                if p.name in ("KEYS.json", "MANIFEST.json"):
                    continue
                b = G.read_json(p)
                t = reg.types[G.read_json(self.out[r] / "designs" / p.name)["type"]]
                allowed = [f["question"] for f in t["facts"]] + [f.get("generator_note", "") for f in t["facts"]]
                allowed += [d["title"] for d in t["documents"]] + [i for d in t["documents"] for i in d["must_show"]]
                allowed.append(b["style_sheet"])
                text = G.canon({k: v for k, v in b.items()})
                for s in sorted(allowed, key=len, reverse=True):
                    if s:
                        text = text.replace(G.canon(s)[1:-2], " ")
                for key in G.MACHINERY_KEYS:
                    self.assertNotIn(key, text, (r, p.name, key))
                for i in ids:
                    self.assertIsNone(re.search(r"(?<![A-Za-z0-9_])" + re.escape(i) + r"(?![A-Za-z0-9_])", text),
                                      (r, p.name, i))
                self.assertIsNone(re.search(r"\b(art|Art|Ziff|SR|para|Abs)\.?\s*\d", text), (r, p.name))
                for ps in passages:
                    self.assertNotIn(ps[:40], text, (r, p.name))
                for other in all_ids - {b["file_id"]}:
                    self.assertNotIn(other, text)
            # the clean-room bundle carries no reference, no workflow, no rules.json
            names = sorted(x.name for x in (self.out[r] / "cleanroom_bundle").iterdir())
            self.assertEqual(names, ["BUNDLE_MANIFEST.json", "SCHEMA.md", "TASK.md", "catalogue.json", "designs.json",
                                     "rule_text.md"])
            dj = (self.out[r] / "cleanroom_bundle" / "designs.json").read_text()
            for word in ("reference", "level", "story", "missing", "scan_noise", "needed_when", "reached_when"):
                self.assertNotIn(f'"{word}"', dj)

    def test_noise_reversible_and_bounded(self):
        rng = random.Random(1)
        words = ["Kündigung", "Vermieterin", "Wohnung", "Mietzinserhöhung", "Lohn", "formell", "Olten", "2026", "10",
                 "rn", "Zimmer", "Ärger", "geöffnet", "the", "landlord", "returned", "modern", "letter"]
        for k in range(30):
            clean = "\n\n".join(" ".join(rng.choice(words) for _ in range(rng.randrange(20, 120))) for _ in range(3))
            deg, rec = N.degrade(clean, k)
            self.assertEqual(N.restore(deg, rec), clean)
            st = N.stats(rec, clean)
            self.assertLess(st["dropped_share_of_characters"], 0.01)
        deg, rec = N.degrade("ä" * 50 + " " + "m" * 200 + " Olten 0 1 l rn " * 30, 3)
        self.assertNotEqual(deg, "ä" * 50)
        self.assertEqual(N.restore(deg, rec), "ä" * 50 + " " + "m" * 200 + " Olten 0 1 l rn " * 30)

    def test_assemble_noise_only_on_flagged_and_drop_rule(self):
        r = REGIMES[0]
        out = self.out[r]
        WB.build(r, out=out)
        reg = G.Regime(r)
        keys = G.read_json(out / "writer_bundles" / "KEYS.json")["keys"]
        ds = {d["file_id"]: d for d in designs(out)}
        fids = sorted(ds)
        bad_once, bad_twice = fids[0], fids[1]
        for fid, d in ds.items():
            key = keys[fid]
            text = ("Grüezi, ich schreibe wegen meiner Wohnung in Olten; der Brief kam am 10. Mai. " * 13).strip()
            w = {"file_id": fid, "round": 1, "language": d["language"], "text": text,
                 "attachments": [{"label": lab, "text": f"Dokument {lab} vom 1.1.2026, Verwaltung Müller."}
                                 for lab in key["attachments"]]}
            G.write_json(out / "written" / f"{fid}.json", w)
        A.blind_in(reg, out, 1)
        for fid, d in ds.items():
            key = keys[fid]
            att = {a["document"]: a for a in d["attachments"]}
            b = {"file_id": fid,
                 "facts": {lab: {"state": d["facts"][f], "quote": ""} for lab, f in key["questions"].items()},
                 "attachments": {lab: ({"state": "sufficient"} if att[did]["sufficient"] else
                                       {"state": "insufficient", "missing": [att[did]["missing"]]})
                                 for lab, did in key["attachments"].items()}}
            if fid in (bad_once, bad_twice):
                q = next(iter(key["questions"]))
                b["facts"][q]["state"] = "open" if d["facts"][key["questions"][q]] != "open" else "not_mentioned"
            G.write_json(out / "blindcheck" / "out" / "round1" / f"{fid}.json", b)
        res = A.compare(reg, out, 1)
        self.assertFalse(res[bad_once]["matches"])
        self.assertTrue((out / "rewrite" / f"{bad_once}.json").exists())
        for fid in (bad_once, bad_twice):
            w = G.read_json(out / "written" / f"{fid}.json")
            w["round"] = 2
            G.write_json(out / "written" / f"{fid}.r2.json", w)
        A.blind_in(reg, out, 2)
        for fid in (bad_once, bad_twice):
            b = G.read_json(out / "blindcheck" / "out" / "round1" / f"{fid}.json")
            if fid == bad_once:
                d, key = ds[fid], keys[fid]
                b["facts"] = {lab: {"state": d["facts"][f], "quote": ""} for lab, f in key["questions"].items()}
            G.write_json(out / "blindcheck" / "out" / "round2" / f"{fid}.json", b)
        A.compare(reg, out, 2)
        entries, dropped = A.finalize(reg, out)
        self.assertEqual([x["file_id"] for x in dropped], [bad_twice])
        self.assertIn(bad_once, {e["file_id"] for e in entries if e["round"] == 2})
        for e in entries:
            fdir = out / "final" / e["file_id"]
            clean = (fdir / "text.clean.txt").read_text(encoding="utf-8")
            shown = (fdir / "text.txt").read_text(encoding="utf-8")
            if e["scan_noise"]:
                self.assertNotEqual(clean, shown)
                rec = G.read_json(fdir / "noise.json")["text"]["record"]
                self.assertEqual(N.restore(shown, rec), clean)
            else:
                self.assertEqual(clean, shown)
                self.assertFalse((fdir / "noise.json").exists())
        man = G.read_json(out / "final" / "MANIFEST.json")
        for e in man["files"]:
            for name, h in e["sha256"].items():
                self.assertEqual(G.sha256_file(out / "final" / e["file_id"] / name), h)


if __name__ == "__main__":
    unittest.main()

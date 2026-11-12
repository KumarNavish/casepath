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
                listed = {x["fact"] for x in d["always_stated_not_mentioned"]}
                ruled = {x.get("changed") for x in d["constraint_adjustments"]}
                vals = G.resolve(reg, d["type"], d["facts"])
                for f in reg.always_stated(d["type"]):
                    if d["facts"][f] == "not_mentioned":
                        # only where no step that uses it can be reached
                        self.assertIn(f, listed, (r, d["file_id"], f))
                        self.assertFalse(G.fact_step_reachable(reg, d["type"], vals, f), (r, d["file_id"], f))
                    elif f not in d["open_facts"] and f not in ruled:
                        self.assertTrue(G.fact_step_reachable(reg, d["type"], vals, f), (r, d["file_id"], f))
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

    @unittest.skipUnless(PRODUCT.exists(), "product worktree not available")
    def test_rules_recomputation_follows_engine_walk(self):
        """reading_of_stops: steps in order, a stop ends the process at its step, documents of earlier steps keep
        their state. The rules-based recomputation must reach exactly the documents the product's in-order walk
        reaches, under every assignment of every type's facts."""
        import itertools
        W = R.load_product(str(PRODUCT))
        for r in REGIMES:
            reg = G.Regime(r)
            for tid in reg.type_ids:
                reach = W._Reach(reg.workflows[tid])
                rf, rv = reg.routing_fact(tid)
                fs = reg.facts(tid)
                for combo in itertools.product([True, False], repeat=len(fs)):
                    v = dict(zip(fs, combo))
                    o = G.rules_outcome(reg, tid, v)
                    _, needs = reach.reach({**v, rf: rv})
                    want = {d for d, n in needs.items() if n == "yes"}
                    got = {d for d, e in o["documents"].items() if e["state"] == "request"}
                    self.assertEqual(got, want, (r, tid, v))

    def test_writer_bundle_has_no_forbidden_content(self):
        for r in REGIMES:
            reg = G.Regime(r)
            WB.build(r, out=self.out[r], force=True)
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
                notes = G.ItemNotes(r)
                allowed += [e.get("checkable_as", "") for e in notes.entries]
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

    # ---------------------------------------------------------------- dependency rules and item notes
    def _rules(self, r):
        p = G.DEV / r / "constraints.json"
        return G.read_json(p)["constraints"] if p.exists() else []

    def test_rule_if_then_holds(self):
        for r in REGIMES:
            for d in designs(self.out[r]):
                prot = {G.Regime(r).defining_event(d["type"])} | set(d["open_facts"])
                for c in self._rules(r):
                    if c.get("kind") is None and c["then"]["fact"] in d["facts"] and \
                            all(f in d["facts"] for f in G.state_facts(c["if"])) and G.state_match(c["if"], d["facts"]):
                        if c["then"]["fact"] not in prot:
                            self.assertIn(d["facts"][c["then"]["fact"]], c["then"]["in"], (r, d["file_id"], c["note"]))

    def test_rule_stated_if_and_stated_only_if(self):
        n = 0
        for r in REGIMES:
            for d in designs(self.out[r]):
                for c in self._rules(r):
                    if c.get("kind") not in ("stated_if", "stated_only_if") or c["fact"] not in d["facts"] \
                            or c["fact"] in d["open_facts"]:
                        continue
                    if not all(f in d["facts"] for f in G.state_facts(c["if"])):
                        continue
                    holds = G.state_match(c["if"], d["facts"])
                    st = d["facts"][c["fact"]]
                    if c["kind"] == "stated_if" and holds:
                        self.assertNotEqual(st, "not_mentioned", (r, d["file_id"]))
                        n += 1
                    if c["kind"] == "stated_only_if" and not holds:
                        self.assertEqual(st, "not_mentioned", (r, d["file_id"]))
        if "dismissal" in REGIMES:
            self.assertGreater(n, 0)

    def test_rule_attachment_implies(self):
        for r in REGIMES:
            reg = G.Regime(r)
            for d in designs(self.out[r]):
                for c in self._rules(r):
                    if c.get("kind") != "attachment_implies" or c["fact"] not in d["facts"]:
                        continue
                    for a in d["attachments"]:
                        if a["supplied"] and a["document"] == c["document"] and a.get("missing") != c.get("item"):
                            self.assertIn(d["facts"][c["fact"]], c["implies"], (r, d["file_id"], c["note"]))
        # a protected (open) fact keeps its state and the attachment is withdrawn
        reg = G.Regime(REGIMES[0])
        tid = reg.type_ids[0]
        did = reg.documents(tid)[0]["id"]
        f = reg.facts(tid)[-1]
        states = {x: "not_mentioned" for x in reg.facts(tid)}
        states[f] = "open"
        att = [{"document": did, "supplied": True, "sufficient": True, "missing": None, "optional": False}]
        rule = {"kind": "attachment_implies", "document": did, "fact": f, "implies": ["stated_false"], "set": "stated_false"}
        log = []
        D.apply_attachment_rules(reg, tid, states, {f}, [rule], att, log, G.ItemNotes(reg.name), {})
        self.assertEqual(states[f], "open")
        self.assertFalse(att[0]["supplied"])
        self.assertTrue(att[0]["withdrawn"])
        # a not-mentioned fact takes the implied state
        states[f] = "not_mentioned"
        att = [{"document": did, "supplied": True, "sufficient": True, "missing": None, "optional": False}]
        D.apply_attachment_rules(reg, tid, states, set(), [rule], att, log, G.ItemNotes(reg.name), {})
        self.assertEqual(states[f], "stated_false")
        self.assertTrue(att[0]["supplied"])

    def test_rule_claimant_sex(self):
        import lexicon as LX
        n = 0
        for r in REGIMES:
            for d in designs(self.out[r]):
                for c in self._rules(r):
                    if c.get("kind") == "claimant_sex" and all(f in d["facts"] for f in G.state_facts(c["if"])) \
                            and G.state_match(c["if"], d["facts"]):
                        first = d["story"]["claimant"].split()[0]
                        self.assertEqual(d["story"]["claimant_sex"], c["sex"])
                        self.assertEqual(LX.SEX[first], c["sex"][0], (r, d["file_id"], first))
                        n += 1
        rng = random.Random(3)
        self.assertEqual(D.claimant_sex([{"kind": "claimant_sex", "if": {"fact": "x", "state": "stated_true"},
                                          "sex": "female"}], {"x": "stated_true"}, rng)[0], "female")

    def test_item_notes(self):
        self.assertFalse(G.conditional_item("where and when it was bought"))
        self.assertTrue(G.conditional_item("conciliation or court documents on those claims, if any"))
        self.assertTrue(G.conditional_item("for an index-linked increase: the old and new index values"))
        for r in REGIMES:
            reg, notes = G.Regime(r), G.ItemNotes(r)
            for d in designs(self.out[r]):
                for a in d["attachments"]:
                    if a.get("supplied") and a.get("missing"):
                        req = notes.required_items(d["type"], a["document"], reg.doc(d["type"], a["document"])["must_show"], d["facts"])
                        self.assertIn(a["missing"], req, (r, d["file_id"]))
            # every note names an existing item, and glosses reach the writer bundle
            items = {(t["id"], doc["id"], i) for t in reg.rules["types"] for doc in t["documents"] for i in doc["must_show"]}
            for e in notes.entries:
                self.assertTrue(any(x[1:] == (e["document"], e["item"]) and e.get("type", "*") in ("*", x[0])
                                    for x in items), (r, e["item"]))
            style = (G.GEN / "STYLE.md").read_text(encoding="utf-8")
            for d in designs(self.out[r]):
                b, _ = WB.build_one(reg, d, style, notes)
                for a, att in zip([x for x in d["attachments"] if x["supplied"]], b["attachments"]):
                    for i in reg.doc(d["type"], a["document"])["must_show"]:
                        g = notes.gloss(d["type"], a["document"], i)
                        if g and notes.applies(d["type"], a["document"], i, d["facts"]) is not False:
                            self.assertIn({"item": i, "checkable_as": g}, att["checkable_as"])
                        if notes.applies(d["type"], a["document"], i, d["facts"]) is False:
                            self.assertIn(i, att["does_not_apply_leave_out"])

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

    @unittest.skipUnless(PRODUCT.exists(), "product worktree not available")
    def test_assemble_noise_only_on_flagged_and_drop_rule(self):
        r = REGIMES[0]
        out = self.out[r]
        WB.build(r, out=out, force=True)
        R.main(["--regime", r, "--out", str(out), "--quiet"])
        reg = G.Regime(r)
        keys = G.read_json(out / "writer_bundles" / "KEYS.json")["keys"]
        ds = {d["file_id"]: d for d in designs(out)}
        fids = sorted(ds)
        bad_once, bad_twice = fids[0], fids[1]
        # a file whose only difference is a designed "not mentioned" (presumed false) read as "stated false"
        pres = {}
        as_read = None
        for fid in fids[2:]:
            d = ds[fid]
            pres = reg.presumptions(d["type"])
            cand = [f for f, st in d["facts"].items() if st == "not_mentioned" and pres.get(f) is False]
            if cand:
                as_read, as_read_fact = fid, cand[0]
                break
        self.assertIsNotNone(as_read)
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
            if fid == as_read:
                lab = next(l for l, f in key["questions"].items() if f == as_read_fact)
                b["facts"][lab]["state"] = "stated_false"
            G.write_json(out / "blindcheck" / "out" / "round1" / f"{fid}.json", b)
        res = A.compare(reg, out, 1)
        self.assertFalse(res[bad_once]["matches"])
        self.assertFalse(res[as_read]["matches"])
        summary, cl = A.classify(reg, out)
        self.assertEqual(cl[as_read]["decision"], "kept_as_read")
        self.assertTrue(cl[as_read]["reference_equivalent"])
        self.assertEqual(cl[bad_once]["decision"], "rewrite")
        self.assertTrue((out / "rewrite" / f"{bad_once}.json").exists())
        self.assertFalse((out / "rewrite" / f"{as_read}.json").exists())
        self.assertIn("bundle", G.read_json(out / "rewrite" / f"{bad_once}.json"))
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
        kept = G.read_json(out / "final" / as_read / "design.json")
        self.assertTrue(kept["kept_as_read"])
        self.assertEqual(kept["facts"][as_read_fact], "stated_false")
        self.assertEqual(kept["facts_designed"][as_read_fact], "not_mentioned")
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

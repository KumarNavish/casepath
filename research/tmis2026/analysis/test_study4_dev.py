"""Tests of analysis/make_numbers_study4_dev.py. No model calls.

    python3 -m unittest test_study4_dev      (from analysis/)   or   python3 test_study4_dev.py

1. paper/results/numbers_study4_dev.tex is what the writer produces now from the stored study4/ records.
2. The headline counts equal values recounted here independently from the raw records (manifests, comparisons,
   per-condition lint rows, per-error diagnosis rows) and the statements of the reports.
3. The rule shown in the article's Listing (s7_benchmark.tex) is stored in rules.json exactly as shown, and the
   convention quoted there is the convention of every regime, word for word.
4. Every \\sfourdev macro the paper uses is defined, and the benchmark section names no product's errors per file.
"""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_numbers_study4_dev as W  # noqa: E402

TEX = W.OUT.read_text()
MACROS = dict(re.findall(r"^\\newcommand\{\\([^}]*)\}\{(.*)\}$", TEX, re.M))
S4 = W.S4
PAPER = W.TMIS / "paper"
SECTION = (PAPER / "sections" / "s7_benchmark.tex").read_text()


def value(name):
    return float(MACROS[name].replace("{,}", "").replace("\\%", "").replace("\\ensuremath{-}", "-"))


def load(p):
    return json.loads(Path(p).read_text())


class Current(unittest.TestCase):
    def test_file_is_current(self):
        W.lines[:] = W.lines[:1]
        W.seen.clear()
        W.build(W.read_sources())
        self.assertEqual("\n".join(W.lines) + "\n", TEX)

    def test_macro_names(self):
        self.assertTrue(all(n.startswith("sfourdev") for n in MACROS))
        self.assertGreater(len(MACROS), 300)


class Recount(unittest.TestCase):
    def test_development_sets(self):
        kept = dropped = denied = 0
        for reg, R in W.REGIMES.items():
            man = load(S4 / "dev" / reg / "final" / "MANIFEST.json")
            folders = [p for p in (S4 / "dev" / reg / "final").iterdir() if p.is_dir()]
            self.assertEqual(len(folders), len(man["files"]), reg)
            self.assertEqual(value(f"sfourdev{R}Files"), len(man["files"]))
            kept += len(man["files"])
            dropped += len(man["dropped"])
            denied += sum(f["denied_event"] for f in man["files"])
        self.assertEqual(value("sfourdevAllFiles"), kept)
        self.assertEqual(value("sfourdevAllDropped"), dropped)
        self.assertEqual(value("sfourdevAllDesigned"), kept + dropped)
        self.assertEqual(value("sfourdevAllDeniedFiles"), denied)

    def test_cleanroom(self):
        cr = load(S4 / "dev" / "CLEANROOM_COMPARISON.json")
        self.assertEqual(value("sfourdevCleanroomDocuments"), sum(v["documents"] for v in cr.values()))
        self.assertEqual(value("sfourdevCleanroomSame"), value("sfourdevCleanroomDocuments"))
        self.assertTrue(all(v["a_equals_b"] and not v["differences"] for v in cr.values()))

    def test_lint_from_condition_rows(self):
        """Recount flags from the per-condition rows of every arm, not from the report's summary."""
        rep = load(S4 / "lint" / "REPORT.json")
        untouched = flagged = planted = detected = 0
        for reg, arms in rep["lint"].items():
            clean = arms["clean"]["conditions"]
            clean_flagged = {k for k, r in clean.items() if r["flagged"]}
            for k, r in clean.items():
                if not r["defining_event"]:
                    untouched += 1
                    flagged += r["flagged"]
            blunt = arms["blunt"]["conditions"]
            for k, r in blunt.items():
                if r.get("planted"):
                    planted += 1
                    detected += bool(r["flagged"] and k not in clean_flagged)
        self.assertEqual((untouched, flagged), (value("sfourdevLintUntouched"), value("sfourdevLintUntouchedFlagged")))
        self.assertEqual((planted, detected), (value("sfourdevLintBluntPlanted"), value("sfourdevLintBluntDetected")))
        stmt = rep["false_alarm_review"]["statement"]
        for reg, R in W.REGIMES.items():
            self.assertIn(f"0 of {int(value(f'sfourdevLint{R}Untouched'))} {reg}", stmt)

    def test_diagnosis_from_error_rows(self):
        diag = load(S4 / "lint" / "DIAGNOSIS.json")
        self.assertEqual(len(diag["errors"]), value("sfourdevDiagAllErrors"))
        self.assertEqual(sum(1 for e in diag["errors"] if e["cause"] == "workflow_differs"), 0)

    def test_first_use_and_repaired_run_labels(self):
        rep = load(S4 / "lint" / "REPORT.json")
        rev3 = load(S4 / "lint" / "REV3.json")
        self.assertIn("DEVELOPMENT", rep["label"])
        self.assertIn("in-sample", rev3["label"])
        self.assertEqual(MACROS["sfourdevRevThreeTenComplete"], "incomplete")
        self.assertAlmostEqual(value("sfourdevRevThreeThErrors"), rev3["regimes"]["theft"]["table"]["overall"]["rev3"]["E"],
                               delta=0.005 + 1e-9)

    def test_rules_have_passages(self):
        for reg, R in W.REGIMES.items():
            rules = load(S4 / "rules" / reg / "rules.json")
            cited = W.cited_rules(rules)
            self.assertEqual(value(f"sfourdev{R}Rules"), len(cited))
            snap = "".join(p.read_text() for p in (S4 / "rules" / reg / "sources").glob("*.txt"))
            flat = re.sub(r"\s+", " ", snap)
            missing = [r["passage"] for r in cited if re.sub(r"\s+", " ", r["passage"]) not in flat]
            self.assertEqual(missing, [], f"{reg}: passages not found in the stored snapshots")


class PaperText(unittest.TestCase):
    def test_listing_is_stored_as_shown(self):
        body = re.search(r"\\begin\{lstlisting\}.*?\]\n(.*?)\\end\{lstlisting\}", SECTION, re.S).group(1)
        pairs = dict(re.findall(r'"(\w+)": "([^"]*)"', body))
        rules = load(S4 / "rules" / "dismissal" / "rules.json")
        found = [f for t in rules["types"] for f in t["facts"] if f["id"] == pairs["id"]]
        self.assertTrue(found)
        f = found[[i for i, x in enumerate(found) if x["question"] == pairs["question"]][0]]
        for key in ("question", "not_this", "type"):
            self.assertEqual(f[key], pairs[key])
        for key in ("source_id", "locator", "passage", "basis"):
            self.assertEqual(f["rule"][key], pairs[key])

    def test_convention_quoted_word_for_word(self):
        quote = re.search(r"\\begin\{quote\}\\\w+\n(.*?)\n\\end\{quote\}", SECTION, re.S).group(1)
        for reg in W.REGIMES:
            conv = load(S4 / "rules" / reg / "rules.json")["convention"]["text"]
            self.assertEqual(quote.replace("'", "'"), conv, reg)

    def test_every_macro_used_is_defined(self):
        used = set()
        for f in list((PAPER / "sections").glob("*.tex")):
            used |= set(re.findall(r"\\(sfourdev[A-Za-z]+)", f.read_text()))
        self.assertTrue(used)
        self.assertEqual(sorted(used - set(MACROS)), [])

    def test_no_product_error_rate_in_the_main_section(self):
        text = re.sub(r"(?m)%.*$", "", SECTION)
        self.assertNotRegex(text, r"\\sfourdev(First|RevThree|RevOne)\w*Errors")
        self.assertIn("development material", text)

    def test_no_insurer_named(self):
        for f in (PAPER / "sections").glob("*.tex"):
            text = re.sub(r"(?m)%.*$", "", f.read_text())
            self.assertNotRegex(text, r"\bCSS\b", f.name)


if __name__ == "__main__":
    unittest.main()

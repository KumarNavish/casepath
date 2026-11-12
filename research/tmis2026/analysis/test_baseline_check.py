"""Tests of analysis/make_numbers_baseline_check.py. No model calls.

    python3 -m unittest test_baseline_check      (from analysis/)   or   python3 test_baseline_check.py

1. Every macro in paper/results/numbers_baseline_check.tex equals the REPORT.json value it names, rounded as the writer
   rounds, and the file is what the writer produces now.
2. The headline table of study4/baseline_check/REPORT.md can be rebuilt from the macros (every cell within half a unit
   of its last printed digit; REPORT.md was rounded by hand, so a value exactly on a half may print either way).
"""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_numbers_baseline_check as W  # noqa: E402

RES = json.loads(W.SRC.read_text())
TEX = W.OUT.read_text()
MACROS = dict(re.findall(r"^\\newcommand\{\\([^}]*)\}\{(.*)\}$", TEX, re.M))


def value(name):
    v = MACROS[name].replace("\\ensuremath{-}", "-").replace("\\%", "")
    return float(v)


class Macros(unittest.TestCase):
    def test_file_is_current(self):
        W.lines[:] = W.lines[:1]
        W.seen.clear()
        W.build(RES)
        self.assertEqual("\n".join(W.lines) + "\n", TEX)

    def test_every_design_value_equals_the_json(self):
        n = 0
        for d, dn in W.DESIGNS.items():
            for sub, sn in W.SUBSETS.items():
                for k, kn in W.TEN_MEASURES.items():
                    self.assertAlmostEqual(value(f"sbc{dn}{sn}{kn}"), RES["tenancy"][d][sub][k], delta=0.005 + 1e-9)
                    n += 1
            for k, (kn, kind) in W.TH_MEASURES.items():
                scale = 1 if kind == "num" else 100
                self.assertAlmostEqual(value(f"sbc{dn}Th{kn}"), scale * RES["theft"][d][k], delta=0.5 * (1 if kind == "pct" else 0.01) + 1e-9)
                n += 1
        self.assertGreater(n, 600)

    def test_every_contrast_equals_the_json(self):
        for reg, pre in (("tenancy", "sbcC"), ("theft", "sbcCTh")):
            for c in RES["contrasts"][reg]:
                sub = W.SUBSETS[c["subset"]] if reg == "tenancy" else ""
                base = f"{pre}{W.DESIGNS[c['a']]}Vs{W.DESIGNS[c['b']]}{sub}{W.CMEAS[c['measure']]}"
                self.assertAlmostEqual(value(base + "Diff"), c["diff_case_mean"], delta=0.005 + 1e-9)
                for key, suffix in (("p_cases", "PCases"), ("p_clusters", "PClusters")):
                    got = MACROS[base + suffix]
                    if got.startswith("<"):
                        self.assertLess(c[key], 0.0001)
                    else:
                        self.assertAlmostEqual(float(got), c[key], delta=0.00005 + 1e-12)

    def test_names_letters_only_and_unique(self):
        names = re.findall(r"\\newcommand\{\\([^}]*)\}", TEX)
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertRegex(n, r"^sbc[A-Za-z]+$")


class HeadlineTable(unittest.TestCase):
    ROWS = {"CasePath, cost-efficient": "CasePath", "CasePath, checklist only, cost-efficient": "Checklist",
            "CasePath, checklist only, frontier (one run)": "FrontierChecklist", "A, cost-efficient": "HoldPrompt",
            "A, frontier": "HoldPromptFrontier", "B, frontier": "MerHoldFrontier"}
    COLS = ["All", "S", "OpenBranch", "ODenied", "OOpenEvent"]

    def test_headline_table_rebuilds_from_the_macros(self):
        md = (W.SRC.parent / "REPORT.md").read_text()
        seen = 0
        for line in md.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or cells[0] not in self.ROWS:
                continue
            dn = self.ROWS[cells[0]]
            for col, cell in zip(self.COLS, cells[1:6]):
                strict, alldev = (float(x) for x in cell.split("/"))
                self.assertAlmostEqual(value(f"sbc{dn}{col}Strict"), strict, delta=0.01 + 1e-9, msg=(dn, col))
                self.assertAlmostEqual(value(f"sbc{dn}{col}AllDev"), alldev, delta=0.01 + 1e-9, msg=(dn, col))
            self.assertAlmostEqual(value(f"sbc{dn}ThErrors"), float(cells[6]), delta=0.01 + 1e-9)
            seen += 1
        self.assertEqual(seen, len(self.ROWS))


if __name__ == "__main__":
    unittest.main()

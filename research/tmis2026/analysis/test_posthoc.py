"""Checks of the POST HOC outputs decomposition.json, lint_followup.json and posthoc_numbers.tex. No model calls.

    python3 -m unittest test_posthoc        (run after decomposition.py and lint_followup.py)
"""
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DC = json.loads((HERE / "decomposition.json").read_text())
LF = json.loads((HERE / "lint_followup.json").read_text())
RES = json.loads((HERE / "study3_results_fresh2_confirm.json").read_text())
TEX = (HERE / "posthoc_numbers.tex").read_text()
TOL = 1e-9


def stored(design, regime, key):
    return RES["designs"][design]["regimes"][regime]["measures"][key]


class Decomposition(unittest.TestCase):
    def test_tenancy_parts_add_up_and_rule_error_is_zero(self):
        for d, v in DC["tenancy_product"].items():
            for m in ("strict_unsafe", "all_dev"):
                for sub, s in v[m].items():
                    parts = s["rule"] + s["routing"] + s["document"] + s["reading"] + s["hold"] + s["product_steps"]
                    self.assertAlmostEqual(parts, s["measured"], delta=TOL, msg=(d, m, sub))
                    self.assertAlmostEqual(s["rule"], 0.0, delta=TOL, msg=(d, m, sub))

    def test_tenancy_measured_equals_the_study3_analysis(self):
        for d in DC["tenancy_product"]:
            ms = RES["designs"][d]["regimes"]["tenancy"]["measures"]
            strict = next(v for k, v in ms.items() if k.startswith("strict_unsafe") and k.endswith("per_claim"))
            self.assertAlmostEqual(DC["tenancy_product"][d]["strict_unsafe"]["all"]["measured"], strict, delta=TOL)
            self.assertAlmostEqual(DC["tenancy_product"][d]["all_dev"]["all"]["measured"], ms["all_deviations_per_claim"], delta=TOL)

    def test_theft_parts_add_up_and_equal_the_study3_analysis(self):
        for d, v in DC["theft_product"].items():
            s = v["all"]
            self.assertAlmostEqual(s["rule"] + s["reading"] + s["hold"] + s["product_steps"], s["measured"], delta=TOL)
            self.assertAlmostEqual(s["reading_shared"] + s["reading_base"] + s["reading_variant"], s["reading"], delta=TOL)
            self.assertAlmostEqual(s["hold_shared"] + s["hold_base"] + s["hold_variant"], s["hold"], delta=TOL)
            self.assertAlmostEqual(s["measured"], stored(d, "theft", "errors_per_pair"), delta=TOL)

    def test_single_prompt_split_adds_up(self):
        for d, s in DC["theft_single"].items():
            self.assertAlmostEqual(s["same_as_rule_floor"] + s["other"], s["errors"], delta=TOL)
            self.assertAlmostEqual(s["errors"], stored(d, "theft", "errors_per_pair"), delta=TOL)


class LintFollowup(unittest.TestCase):
    def test_variant_decompositions_add_up(self):
        for m, v in LF["part2_theft"].items():
            for var, r in v.items():
                d = r["decomposition"]
                self.assertAlmostEqual(d["rule"] + d["reading"] + d["hold"], d["measured"], delta=2e-3, msg=(m, var))  # rounded values
                self.assertAlmostEqual(d["measured"], r["summary"]["errors"], delta=2e-3, msg=(m, var))

    def test_tested_frontier_configuration_reproduces_the_stored_contrast(self):
        self.assertAlmostEqual(LF["part2_theft"]["gpt-6.1-terra"]["tested"]["summary"]["errors"], 0.833, delta=1e-3)
        s7a = next(c for c in RES["secondary"]["contrasts"] if c["id"] == "S7a")["result"]
        mine = next(c for c in LF["paired_frontier"]["tested"] if c["single"] == "ric_frontier")
        self.assertAlmostEqual(mine["p_signflip"], s7a["p"], delta=1e-9)
        self.assertAlmostEqual(mine["mean_difference"], s7a["diff"], delta=1e-3)

    def test_development_flags_come_from_development_texts_only(self):
        for m in ("gpt-6-luna", "gpt-6.1-terra"):
            d = LF["development_flags"][m]
            self.assertTrue(d["off_texts"])
            self.assertTrue(all(int(t[1:].split("-")[0]) in (4, 5, 6, 7) for t in d["off_texts"]), d["off_texts"])
            self.assertTrue(all(src["workflow_sha256"] == "a0c53a812920f4c7be60029c620a8c112857bfc9c9656bc92a745170357a2ded" for src in d["sources"]))
        self.assertTrue(all(src["commit"].startswith("6a72159c") for src in LF["development_flags"]["gpt-6-luna"]["sources"]))

    def test_mutation_counts_are_consistent(self):
        t = LF["part3"]["totals"]
        self.assertEqual(t["planted_already_flagged_unmutated"] + t["planted_newly_flagged"], t["planted_flagged"])
        self.assertLessEqual(t["planted_flagged"], t["planted"])


class Macros(unittest.TestCase):
    def test_names_letters_only_unique_and_values_numeric(self):
        rows = re.findall(r"\\newcommand\{\\([^}]*)\}\{([^}]*)\}", TEX)
        names = [n for n, _ in rows]
        self.assertGreater(len(rows), 100)
        self.assertEqual(len(names), len(set(names)))
        for n, v in rows:
            self.assertRegex(n, r"^spost[A-Za-z]+$")
            self.assertRegex(v, r"^-?\d+(\.\d+)?$", n)


if __name__ == "__main__":
    unittest.main()

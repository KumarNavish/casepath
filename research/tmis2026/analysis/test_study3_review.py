"""Tests of the computations of analysis/study3_review.py on small constructed inputs. No model calls; fresh2/ is never
loaded (the engine tests build their own claim and call the reference engine of fresh2/tenancy/build.py directly).

    python3 -m unittest test_study3_review      (from analysis/)   or   python3 test_study3_review.py
"""
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study3_review as R  # noqa: E402

s2 = R.s2


def ref_of(req, held, other=()):
    st = {d: "required_now" for d in req}
    st.update({d: "held" for d in held})
    st.update({d: "not_needed" for d in other})
    return {"document_states": st}


class ClaimOutcome(unittest.TestCase):
    def test_exact(self):
        row = s2.ten_row(ref_of(["a", "b"], ["c"], ["d"]), {"requests": ["a", "b"], "holds": ["c"]})
        self.assertEqual(R.claim_outcome(row), {"exact": 1, "any_unsafe": 0, "any_wrong_hold": 0})

    def test_unsafe_and_wrong_hold(self):
        row = s2.ten_row(ref_of(["a", "b"], ["c"], ["d"]), {"requests": ["a", "d"], "holds": ["b", "c"]})
        self.assertEqual(R.claim_outcome(row), {"exact": 0, "any_unsafe": 1, "any_wrong_hold": 1})

    def test_spurious_hold_only(self):
        row = s2.ten_row(ref_of(["a"], [], ["d"]), {"requests": ["a"], "holds": ["d"]})
        self.assertEqual(R.claim_outcome(row), {"exact": 0, "any_unsafe": 0, "any_wrong_hold": 1})

    def test_handover_is_not_exact(self):
        row = s2.ten_row(ref_of([], [], ["d"]), {"requests": [], "holds": [], "deferred": True})
        self.assertEqual(R.claim_outcome(row)["exact"], 0)
        self.assertEqual(R.claim_outcome(row)["any_unsafe"], 0)

    def test_shares(self):
        rows = [s2.ten_row(ref_of(["a"], []), {"requests": ["a"], "holds": []}),
                s2.ten_row(ref_of(["a"], []), {"requests": [], "holds": []})]
        sh = R.claim_shares(rows)
        self.assertEqual((sh["exact_share"], sh["any_unsafe_share"], sh["any_wrong_hold_share"]), (0.5, 0.5, 0.0))


class Reweighting(unittest.TestCase):
    def test_reweighted(self):
        self.assertAlmostEqual(R.reweighted({"o": 1.0, "d": 5.0, "e": 3.0}, {"o": 0.8, "d": 0.1, "e": 0.1}), 1.6)
        self.assertAlmostEqual(R.reweighted({"o": 1.0}, {"o": 1.0, "d": 0.0}), 1.0)
        with self.assertRaises(KeyError):
            R.reweighted({"o": 1.0}, {"o": 0.5, "d": 0.5})

    def test_own_mix_reproduces_pooled_mean(self):
        rows = [("o", 1), ("o", 0), ("o", 2), ("d", 5), ("e", 3)]
        m = R.subset_means(rows, lambda r: r[0], lambda r: r[1])
        w = {"o": 3 / 5, "d": 1 / 5, "e": 1 / 5}
        self.assertAlmostEqual(R.reweighted(m, w), sum(v for _, v in rows) / len(rows))

    def test_bootstrap_constant_and_redraw(self):
        cells = {"f1": {"o": (2.0, 2)}, "f2": {"o": (3.0, 3), "d": (4.0, 2)}}
        vals, redraws = R.reweight_bootstrap(cells, {"o": 1.0}, 200, "t")
        self.assertTrue(all(abs(v - 1.0) < 1e-12 for v in vals))
        self.assertEqual(redraws, 0)
        vals, redraws = R.reweight_bootstrap(cells, {"o": 0.5, "d": 0.5}, 500, "t")
        self.assertEqual(len(vals), 500)
        self.assertGreater(redraws, 0)  # resamples with only f1 have no 'd' claim and are drawn again
        self.assertTrue(all(abs(v - (0.5 + 0.5 * 2.0)) < 1e-12 for v in vals))

    def test_bootstrap_deterministic(self):
        cells = {f"f{i}": {"o": (float(i), 1)} for i in range(6)}
        self.assertEqual(R.reweight_bootstrap(cells, {"o": 1}, 100, "s"), R.reweight_bootstrap(cells, {"o": 1}, 100, "s"))


class Facts(unittest.TestCase):
    def test_product_value(self):
        self.assertEqual(R.product_value({"status": "established", "verdict": "accepted", "value": True}), ("admitted", True))
        self.assertEqual(R.product_value({"status": "established", "verdict": None, "value": True}), ("not accepted", None))
        self.assertEqual(R.product_value({"status": "presumed", "verdict": "presumed", "value": False}), ("presumed", False))
        self.assertEqual(R.product_value({"status": "unknown", "value": None}), ("unresolved", None))
        self.assertEqual(R.product_value({"status": "conflicting", "value": None}), ("conflicting", None))
        self.assertEqual(R.product_value(None), ("absent", None))
        with self.assertRaises(ValueError):
            R.product_value({"status": "odd"})

    def test_category(self):
        self.assertEqual(R.fact_category("admitted", True, True, "stated_true"), "admitted right")
        self.assertEqual(R.fact_category("admitted", True, False, "absent"), "admitted wrong")
        self.assertEqual(R.fact_category("presumed", False, True, "stated_true"), "presumed wrong")
        self.assertEqual(R.fact_category("unresolved", None, True, "open"), "unresolved")

    def test_combine_readings_with_requote(self):
        full1 = [{"id": "a", "verdict": "true"}, {"id": "b", "verdict": "not_stated"}]
        requote = [{"id": "a", "verdict": "false"}]
        full2 = [{"id": "a", "verdict": "true"}, {"id": "b", "verdict": "open"}, {"id": "b", "verdict": "true"}]
        rd = R.combine_readings([full1, requote, full2], ["a", "b"])
        self.assertEqual(rd, [{"a": "false", "b": "not_stated"}, {"a": "true", "b": "open"}])

    def test_agreement(self):
        self.assertEqual(R.agreement(["true", "true", "true"], False), "all agree wrong")
        self.assertEqual(R.agreement(["false", "false", "false"], False), "all agree right")
        self.assertEqual(R.agreement(["true", "true", "open"], False), "not unanimous")
        self.assertEqual(R.agreement(["open", "open", "open"], False), "not unanimous")
        self.assertEqual(R.agreement([], True), "not unanimous")


class WrongPresumptions(unittest.TestCase):
    REF = {"claim_id": "test_claim", "family": "defect_mold_heating",
           "fact_states": {"health_effects": "stated_true", "mold": "absent", "heating": "stated_true",
                           "specialist_needed": "absent", "deposit_considered": "absent"},
           "open_fact": None, "attachments": []}

    def test_subsets(self):
        self.assertEqual(R.subsets_of(["b", "a"]), [(), ("a",), ("b",), ("a", "b")])
        self.assertEqual(R.subsets_of([]), [()])

    def test_draws(self):
        absent = {"c1": ["x", "y"], "c2": ["z"], "c3": []}
        self.assertEqual(R.draw_flips(absent, 0.0, random.Random(1)), {"c1": (), "c2": (), "c3": ()})
        self.assertEqual(R.draw_flips(absent, 1.0, random.Random(1)), {"c1": ("x", "y"), "c2": ("z",), "c3": ()})
        self.assertEqual(R.draw_flips(absent, 0.3, random.Random(7)), R.draw_flips(absent, 0.3, random.Random(7)))

    def test_flip_follows_engine_with_fact_true(self):
        base = R.engine_states(self.REF)
        flipped = R.engine_states(self.REF, ("mold",))
        direct = R.engine_states({**self.REF, "fact_states": {**self.REF["fact_states"], "mold": "stated_true"}})
        self.assertEqual(flipped, direct)
        self.assertNotEqual(flipped, base)  # a true mold fact requires more documents
        more = {d for d, s in flipped.items() if s in s2.REQ_NOW} - {d for d, s in base.items() if s in s2.REQ_NOW}
        self.assertTrue(more)

    def test_rescoring_counts_missed(self):
        base = R.engine_states(self.REF)
        flipped = R.engine_states(self.REF, ("mold",))
        plan = {"requests": sorted(d for d, s in base.items() if s in s2.REQ_NOW), "holds": []}
        self.assertEqual(s2.ten_row({"document_states": base}, plan)["strict_unsafe"], 0)
        extra = sum(s in s2.REQ_NOW for s in flipped.values()) - sum(s in s2.REQ_NOW for s in base.values())
        self.assertEqual(s2.ten_row({"document_states": flipped}, plan)["missed"], extra)


class TheftInference(unittest.TestCase):
    def test_twoway_constant_and_additive(self):
        cells = {(s, f): 0.5 for s in range(3) for f in range(4)}
        self.assertTrue(all(abs(v - 0.5) < 1e-12 for v in R.twoway_bootstrap(cells, 50, "x")))
        cells = {(s, f): s + 10 * f for s in range(3) for f in range(4)}
        vals = R.twoway_bootstrap(cells, 2000, "y")
        self.assertTrue(min(vals) >= 0 and max(vals) <= 2 + 30)
        self.assertAlmostEqual(sum(vals) / len(vals), 1 + 15, delta=1.0)

    def test_signflip_ci_ends(self):
        d = [-1.75, -1.67, -0.875, -0.75, -0.625, -0.583, -0.5, 0.125, 1.0]
        lo, hi, contiguous = R.signflip_ci(d)
        self.assertTrue(contiguous)
        self.assertLess(lo, sum(d) / len(d))
        self.assertGreater(hi, sum(d) / len(d))
        p = lambda x: R.s3.signflip_p([v - x for v in d])
        self.assertGreaterEqual(p(lo), 0.05)
        self.assertLess(p(lo - 1e-4), 0.05)
        self.assertGreaterEqual(p(hi), 0.05)
        self.assertLess(p(hi + 1e-4), 0.05)
        self.assertGreater(hi, 0.0)  # p = 0.0625 at zero: zero is inside

    def test_signflip_ci_excludes_zero_when_significant(self):
        lo, hi, _ = R.signflip_ci([-1.0, -2.0, -1.5, -0.5, -1.2, -0.8, -1.1, -0.9, -1.3])
        self.assertLess(hi, 0)

    def test_ni_onesided(self):
        self.assertAlmostEqual(R.signflip_onesided_ni([-1.0] * 6, 0.25), 1 / 64)
        self.assertEqual(R.signflip_onesided_ni([1.0] * 6, 0.25), 1.0)


class DeniedEvent(unittest.TestCase):
    def test_rule(self):
        self.assertTrue(R.acknowledges_event_open({"questions": ["Have you since received a written termination notice?"]}))
        self.assertTrue(R.acknowledges_event_open({"questions": ["Haben Sie die Kündigung inzwischen schriftlich erhalten?"]}))
        self.assertTrue(R.acknowledges_event_open({"questions": ["Has an official rent-increase form arrived?"]}))
        self.assertFalse(R.acknowledges_event_open({"questions": ["Was the rent previously adjusted?"]}))
        self.assertFalse(R.acknowledges_event_open({"questions": []}))
        self.assertFalse(R.acknowledges_event_open(None))


class ProductComparison(unittest.TestCase):
    def entry(self, fam="f", facts=None, docs=None, routing="selected", req=(), holds=(), added=()):
        return {"plan": {"family": fam, "requests": list(req), "holds": list(holds), "added_requests": list(added)},
                "product_extra": {"routing": {"status": routing}, "facts": facts or {}, "document_judgments": docs or {}}}

    def test_same_checklist(self):
        self.assertTrue(R.same_checklist({"requests": ["b", "a"], "holds": []}, {"requests": ["a", "b"]}))
        self.assertFalse(R.same_checklist({"requests": ["a"]}, {"requests": ["a"], "deferred": True}))
        self.assertTrue(R.same_checklist(None, {"requests": [], "holds": []}))

    def test_stages(self):
        acc = lambda v: {"status": "established", "verdict": "accepted", "value": v}
        a = self.entry(facts={"x": acc(True), "z": acc(True)}, docs={"d": {"status": "present", "verdict": "accepted"}})
        b = self.entry(facts={"x": acc(False), "z": acc(False)}, docs={"d": {"status": "unusable", "verdict": "accepted"}})
        self.assertEqual(R.stage_differences(a, b), ["fact value", "document status"])
        self.assertEqual(R.stage_differences(a, b, used={"q"}), ["document status"])
        self.assertEqual(R.stage_differences(a, self.entry(fam="g", facts={"x": acc(True), "z": acc(True)},
                                                           docs={"d": {"status": "present", "verdict": "accepted"}})), ["routing"])
        c = self.entry(facts={"x": {"status": "established", "verdict": None, "value": True}, "z": acc(True)},
                       docs={"d": {"status": "present", "verdict": "accepted"}}, added=["n1"])
        self.assertEqual(R.stage_differences(a, c), ["fact value", "needs added by an agent"])
        d = self.entry(facts={"x": acc(True), "z": acc(True)}, docs={"d": {"status": "present", "verdict": "not_checked"}})
        self.assertEqual(R.stage_differences(a, d), ["document status"])

    def test_product_fact_states(self):
        e = self.entry(facts={"a": {"status": "established", "verdict": "accepted", "value": True},
                              "b": {"status": "presumed", "verdict": "presumed", "value": False},
                              "c": {"status": "unknown", "value": None}})
        self.assertEqual(R.product_fact_states(e, ["a", "b", "c", "d"]),
                         {"a": "stated_true", "b": "stated_false", "c": "open", "d": "open"})


class CostSplit(unittest.TestCase):
    def test_classify(self):
        calls = [("router", False, 1.0), ("claim_reader", False, 2.0), ("claim_reader", False, 3.0),
                 ("process_builder", False, 4.0), ("claim_reader", True, 5.0), ("claim_reader", True, 0.5),
                 ("source_checker", True, 6.0), ("source_checker", True, 7.0), ("document_finder", False, 8.0),
                 ("source_checker", False, 9.0), ("claim_reader", False, 10.0), ("result_checker", False, 11.0)]
        out = R.classify_calls(calls)
        self.assertEqual(out["claim reader: brief"], (2, 5.0))
        self.assertEqual(out["claim reader: first reading"], (1, 5.0))
        self.assertEqual(out["claim reader: first reading (requote)"], (1, 0.5))
        self.assertEqual(out["claim reader: re-recording after the check"], (1, 10.0))
        self.assertEqual(out["source checker: confirming readings"], (2, 13.0))
        self.assertEqual(out["source checker: fact and document check"], (1, 9.0))
        self.assertEqual(out["router"], (1, 1.0))
        self.assertAlmostEqual(sum(v[1] for v in out.values()), sum(c[2] for c in calls))

    def test_checklist_run_has_no_brief(self):
        out = R.classify_calls([("router", False, 1.0), ("claim_reader", True, 2.0), ("source_checker", True, 3.0)])
        self.assertNotIn("claim reader: brief", out)


class Rules(unittest.TestCase):
    def test_rule_documents(self):
        rule = {"facts": [{"evidence": [{"routes": [{"documents": ["A", "B"]}, {"documents": ["C"]}]}, {"routes": []}]}],
                "confirming_evidence": {"routes": [{"documents": ["D"]}]}}
        self.assertEqual(R.rule_documents(rule), {"A", "B", "C", "D"})
        self.assertEqual(R.rule_documents({}), set())


class Helpers(unittest.TestCase):
    def test_need(self):
        self.assertEqual(R.need({"a": {"b": [1, 2]}}, "a", "b", 1), 2)
        with self.assertRaises(KeyError):
            R.need({"a": {}}, "a", "b")

    def test_pct_range(self):
        r = R.pct_range([1.0] * 10)
        self.assertEqual((r["mean"], r["p2_5"], r["p97_5"]), (1.0, 1.0, 1.0))


if __name__ == "__main__":
    unittest.main()

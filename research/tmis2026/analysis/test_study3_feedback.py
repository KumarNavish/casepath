"""Tests of analysis/study3_feedback.py. No model calls. Unit tests on small constructed inputs; one integration test
(F5Hook) loads the stored Study 3 outputs, as the hook is asked to reproduce the registered numbers with the
registered reference and to move them with a perturbed copy.

    python3 -m unittest test_study3_feedback      (from analysis/)   or   python3 test_study3_feedback.py
"""
import json
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study3_feedback as F  # noqa: E402

s2 = F.s2


def ref(states, implicit=None):
    return {"fact_states": states, "implicit_flags": implicit or {}}


class ClaimType(unittest.TestCase):
    def test_types(self):
        self.assertEqual(F.claim_type(ref({"a": "stated_true", "b": "absent", "c": "stated_false"})), "S")
        self.assertEqual(F.claim_type(ref({"a": "stated_true", "b": "open"})), "O")
        self.assertEqual(F.claim_type(ref({"termination_received": "stated_false", "a": "stated_true"},
                                          {"termination_received": False})), "O")
        self.assertEqual(F.claim_type(ref({"termination_received": "unmentioned"}, {"termination_received": True})), "S")
        self.assertEqual(F.claim_type(ref({"claim_received": "open"}, {"claim_received": True})), "O")

    def test_type_summary_family_and_claim_run_means(self):
        rows = []
        for fam, vals in (("f1", [0, 0, 3]), ("f2", [1])):
            for i, v in enumerate(vals):
                rows.append({"case": f"{fam}{i}", "cluster": fam, "strict_unsafe": v, "all_dev": v, "held_req": 0,
                             "spurious_hold": 0, "deferred": 0})
        s = F.type_summary(rows)
        self.assertAlmostEqual(s["strict_unsafe_claim_run_mean"], 1.0)
        self.assertAlmostEqual(s["strict_unsafe_family_mean"], (1.0 + 1.0) / 2)
        self.assertAlmostEqual(s["exact_share_claim_run"], 0.5)
        self.assertAlmostEqual(s["exact_share_family_mean"], (2 / 3 + 0) / 2)
        self.assertEqual(F.type_summary([]), {"claim_runs": 0})


class Lines(unittest.TestCase):
    def test_line_and_crossover(self):
        self.assertAlmostEqual(F.line(1.0, 3.0, 0.25), 1.5)
        self.assertAlmostEqual(F.crossover((1.0, 3.0), (2.0, 2.0)), 0.5)
        self.assertIsNone(F.crossover((1.0, 2.0), (2.0, 3.0)))  # parallel
        self.assertIsNone(F.crossover((0.0, 1.0), (2.0, 4.0)))  # would cross below 0
        q = F.crossover((0.2, 0.4), (0.2, 3.0))
        self.assertAlmostEqual(q, 0.0)

    def test_type_bootstrap(self):
        cells = {"f1": {"S": (1.0, 2), "O": (4.0, 2)}, "f2": {"S": (1.0, 2)}, "f3": {"O": (2.0, 1)}}
        lo, hi, redraws = F.type_bootstrap(cells, 300, "t", grid=[0.0, 1.0])
        self.assertEqual(len(lo), 2)
        self.assertAlmostEqual(lo[0], 0.5)
        self.assertAlmostEqual(hi[0], 0.5)  # every family with S claims has mean 0.5
        self.assertGreaterEqual(redraws, 0)
        self.assertLessEqual(lo[1], hi[1])
        self.assertEqual(F.type_bootstrap(cells, 50, "u", grid=[0.5]), F.type_bootstrap(cells, 50, "u", grid=[0.5]))


class Orders(unittest.TestCase):
    T = {"H1": (0.01, True), "H2": (0.001, True), "H3": (0.2, True), "H4": (0.01, True), "H5": (0.02, None)}

    def test_fixed_sequence(self):
        st = F.fixed_sequence_status(["H1", "H2", "H3", "H4", "H5"], self.T)
        self.assertEqual(st, {"H1": "confirmed", "H2": "confirmed", "H3": "not confirmed", "H4": "not tested", "H5": "not tested"})
        st = F.fixed_sequence_status(["H1", "H2", "H4", "H5", "H3"], self.T)
        self.assertEqual(st["H5"], "confirmed")
        self.assertEqual(st["H3"], "not confirmed")

    def test_direction_required(self):
        st = F.fixed_sequence_status(["H1"], {"H1": (0.001, False)})
        self.assertEqual(st["H1"], "not confirmed")

    def test_holm(self):
        st = F.holm_status(["H1", "H2", "H3", "H4", "H5"], self.T)
        self.assertAlmostEqual(st["H2"][1], 0.005)
        self.assertEqual(st["H2"][0], "confirmed")
        self.assertAlmostEqual(st["H1"][1], 0.04)  # 4 x 0.01; H4's 3 x 0.01 is lifted to the running maximum
        self.assertEqual(st["H3"][0], "not confirmed")


class Readings(unittest.TestCase):
    DEFS = {"a": {"id": "a", "type": "boolean"}, "b": {"id": "b", "type": "boolean"},
            "e": {"id": "e", "type": "enum", "values": ["x", "y"]}}

    def test_fact_value(self):
        self.assertIs(F.fact_value({"type": "boolean"}, "Ja"), True)
        self.assertIs(F.fact_value({"type": "boolean"}, "false"), False)
        self.assertIsNone(F.fact_value({"type": "boolean"}, "maybe"))
        self.assertEqual(F.fact_value({"type": "enum", "values": ["x"]}, "x"), "x")
        self.assertIsNone(F.fact_value({"type": "enum", "values": ["x"]}, "z"))

    def test_one_reading(self):
        found = lambda q: q.startswith("ok")
        conds = [{"id": "a", "verdict": "true", "quote": "ok a"}, {"id": "b", "verdict": "true", "quote": "nope"},
                 {"id": "e", "verdict": "true", "value": "y", "quote": "ok e"}]
        r = F.one_reading(conds, self.DEFS, found)
        self.assertEqual(r["a"], ("established", True, False))
        self.assertEqual(r["b"], ("unknown", None, False))  # quotation not found
        self.assertEqual(r["e"], ("established", "y", False))
        r = F.one_reading([{"id": "a", "verdict": "open", "quote": "ok open"}, {"id": "b", "verdict": "open", "quote": "x"}], self.DEFS, found)
        self.assertEqual(r["a"], ("unknown", None, True))
        self.assertEqual(r["b"], ("unknown", None, None))
        r = F.one_reading([{"id": "a", "verdict": "true", "quote": "ok"}, {"id": "a", "verdict": "false", "quote": "ok"}], self.DEFS, found)
        self.assertEqual(r["a"], ("unknown", None, False))  # answered twice differently

    def test_split_readings(self):
        full = [{"id": f, "verdict": "true"} for f in "abc"]
        rq = [{"id": "b", "verdict": "false"}]
        out = F.split_readings([full, rq, full, full], 3)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0][1], [0, 1])
        self.assertEqual({c["id"]: c["verdict"] for c in out[0][0]}["b"], "false")

    def test_combine_k(self):
        E = lambda v: ("established", v, False)
        U = ("unknown", None, False)
        rd = [{"a": E(True), "b": E(True), "c": U}, {"a": E(True), "b": E(False), "c": E(True)}, {"a": E(True), "b": E(True), "c": U}]
        self.assertEqual(F.combine_k(rd, 1, "a")["status"], "established")
        self.assertEqual(F.combine_k(rd, 3, "a")["status"], "established")
        self.assertTrue(F.combine_k(rd, 2, "a")["agreed"])
        self.assertEqual(F.combine_k(rd, 1, "b")["value"], True)
        self.assertEqual(F.combine_k(rd, 2, "b")["status"], "conflicting")
        self.assertEqual(F.combine_k(rd, 3, "b")["status"], "conflicting")
        c = F.combine_k(rd, 2, "c")
        self.assertEqual((c["status"], c["readings"]), ("unknown", [None, True]))  # one reading only: no value
        self.assertEqual(F.combine_k(rd, 1, "c")["status"], "unknown")
        rd2 = [{"a": E(True)}, {}, {"a": E(True)}]  # second reading did not answer
        self.assertEqual(F.combine_k(rd2, 3, "a")["status"], "unknown")


class Votes(unittest.TestCase):
    def test_disjoint_votes(self):
        P = lambda *r: {"requests": list(r), "holds": []}
        samples = [P("a"), P("a"), P(), P("b"), P("b"), P("b")]
        v = F.disjoint_votes(samples, 3)
        self.assertEqual([x["requests"] for x in v], [["a"], ["b"]])
        self.assertEqual(len(F.disjoint_votes(samples, 4)), 1)
        self.assertEqual(F.disjoint_votes([P("a"), P()], 2)[0]["requests"], [])  # a tie is not requested
        self.assertEqual(len(F.disjoint_votes([P()] * 15, 7)), 2)


class AltReference(unittest.TestCase):
    class Base:
        def reference(self, cid):
            return {"claim_id": cid, "document_states": {"d1": "required_now", "d2": "held"}, "request_set": ["d1"]}

        def claim_ids(self, split):
            return ["c1"]

    def test_replaces_states_only(self):
        A = F.AltTenancy(self.Base(), {"c1": {"d1": "not_needed", "d2": "held"}})
        r = A.reference("c1")
        self.assertEqual(r["document_states"], {"d1": "not_needed", "d2": "held"})
        self.assertEqual(r["request_set"], ["d1"])  # subsets stay the registered reference's
        self.assertEqual(A.claim_ids("test"), ["c1"])

    def test_validation(self):
        with self.assertRaises(KeyError):
            F.AltTenancy(self.Base(), {}).reference("c1")
        with self.assertRaises(KeyError):
            F.AltTenancy(self.Base(), {"c1": {"d1": "held"}}).reference("c1")
        with self.assertRaises(ValueError):
            F.AltTenancy(self.Base(), {"c1": {"d1": "optional", "d2": "held"}}).reference("c1")

    def test_load_alt_formats(self, tmp=None):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = Path(d) / "a.json", Path(d) / "b.json"
            p1.write_text(json.dumps({"c1": {"d1": "held"}}))
            p2.write_text(json.dumps({"c1": {"document_states": {"d1": "held"}, "other": 1}}))
            self.assertEqual(F.load_alt(p1), F.load_alt(p2))

    def test_verdict(self):
        reg = {"diff": -1.0, "p": 0.001}
        self.assertEqual(F.verdict(reg, {"diff": -0.95, "p": 0.01}), "holds")
        self.assertEqual(F.verdict(reg, {"diff": -0.5, "p": 0.01}), "holds, shrinks")
        self.assertEqual(F.verdict(reg, {"diff": -2.0, "p": 0.01}), "holds, grows")
        self.assertEqual(F.verdict(reg, {"diff": -0.5, "p": 0.2}), "same sign, not significant")
        self.assertEqual(F.verdict(reg, {"diff": 0.5, "p": 0.01}), "reverses (p < 0.05)")
        self.assertEqual(F.verdict(reg, {"diff": 0.5, "p": 0.3}), "reverses (not significant)")


class Amendments(unittest.TestCase):
    WF = Path(__file__).resolve().parent.parent / "harness" / "product" / "workflows" / "fresh-serial-sync"

    def wf(self, name):
        return json.loads((self.WF / f"{name}.json").read_text())

    def test_empty_amendment_is_a_copy(self):
        w = self.wf("lease_termination_dispute")
        a = F.amend_workflow(w, frozenset())
        self.assertEqual(a, w)
        self.assertIsNot(a, w)

    def test_a3_removes_optional(self):
        w = self.wf("defect_mold_heating")
        self.assertTrue(any(d.get("optional") for d in w["documents"]))
        a = F.amend_workflow(w, {"A3"})
        self.assertFalse(any(d.get("optional") for d in a["documents"]))
        self.assertTrue(any(d.get("optional") for d in w["documents"]))  # the original is untouched

    def test_a4_gate(self):
        a = F.amend_workflow(self.wf("lease_termination_dispute"), {"A4"})
        gate = next(st for st in a["steps"] if st["id"] == "lt_type__gate_family_home")
        when = {e["to"]: e["when"] for e in gate["next"]}
        self.assertEqual(when["lt_family"], {"all": [{"fact": "family_home", "is": True}, {"fact": "arrears", "is": False}]})
        self.assertEqual(F.amend_workflow(self.wf("rent_increase_dispute"), {"A4"}), self.wf("rent_increase_dispute"))

    def test_amend_facts(self):
        class W:
            @staticmethod
            def reading_gave_value(row, presumed=None):
                return any(v is not None and v != presumed for v in (row or {}).get("readings") or [])
        wf = {"id": "lease_termination_dispute"}
        ev = "termination_received"
        self.assertEqual(F.amend_facts({ev: False}, {}, wf, {"A1"}, W)[ev], True)
        self.assertIsNone(F.amend_facts({ev: None}, {ev: {"status": "unknown"}}, wf, {"A1"}, W)[ev])
        self.assertEqual(F.amend_facts({ev: None}, {ev: {"status": "unknown", "open_readings": [True]}}, wf, {"A2"}, W)[ev], True)
        self.assertIsNone(F.amend_facts({ev: None}, {ev: {"status": "conflicting"}}, wf, {"A2"}, W)[ev])
        self.assertIsNone(F.amend_facts({ev: None}, {ev: {"status": "unknown", "readings": [False, None]}}, wf, {"A2"}, W)[ev])
        self.assertEqual(F.amend_facts({ev: False}, {}, wf, {"A2"}, W)[ev], False)  # A2 alone leaves a denial
        self.assertEqual(F.amend_facts({"x": False}, {}, {"id": "defect_mold_heating"}, {"A1", "A2"}, W), {"x": False})


class F5Hook(unittest.TestCase):
    """Integration: the hook on the stored Study 3 outputs."""

    @classmethod
    def setUpClass(cls):
        F.s3.configure(F.SPEC)
        cls.study = F.s3.Study(F.SPEC, F.DATA, F.LABEL, F.s3.load_data(F.DATA))
        cls.res3 = json.loads((HERE / "study3_results_fresh2_confirm.json").read_text())

    def test_registered_reference_reproduces_stored_numbers(self):
        reg = {c: self.study.D["tenancy"].reference(c)["document_states"] for c in self.study.cases["tenancy"]}
        r = F.rescore(self.study, reg, "registered")
        self.assertTrue(r["identical_to_registered"])
        stored = {**{h["id"]: h["tests"][0] for h in self.res3["hypotheses"] if h["regime"] == "tenancy"},
                  **{c["id"]: c["result"] for c in self.res3["secondary"]["contrasts"]}}
        for c in r["contrasts"]:
            for k in ("a_value", "b_value", "diff", "p", "diff_ci"):
                self.assertEqual(c["alternative"][k], stored[c["id"]][k], (c["id"], k))
        self.assertAlmostEqual(r["by_design"]["casepath"]["strict_unsafe|all claims"],
                               self.res3["designs"]["casepath"]["regimes"]["tenancy"]["measures"]["strict_unsafe_per_claim"])

    def test_h4_self_consistency_cluster_counts(self):
        """The per-cluster counts of the H4 Self-consistency contrast agree with the registered result and with the stored
        post-hoc count by changed fact; their sign pattern reproduces the registered sign-flip p."""
        self.study.load("casepath", "theft")
        self.study.load("self_consistency", "theft")
        ca = self.study.clusters("casepath", "theft", "errors")
        cb = self.study.clusters("self_consistency", "theft", "errors")
        d = [ca[k] - cb[k] for k in sorted(ca)]
        sc = next(t for h in self.res3["hypotheses"] if h["id"] == "H4" for t in h["tests"] if t["b"] == "self_consistency")
        self.assertEqual(len(d), sc["clusters"])
        self.assertAlmostEqual(F.s3.signflip_p(d), sc["p"])
        fewer, more = sum(x < -1e-12 for x in d), sum(x > 1e-12 for x in d)
        stored = json.loads((HERE / "study3_feedback.json").read_text())["F3"]["h4_self_consistency"]
        self.assertEqual((fewer, more), (stored["clusters_fewer_casepath"], stored["clusters_more_casepath"]))
        post = json.loads((HERE / "study3_posthoc.json").read_text())
        h41 = post["h4_self_consistency_by_fact"]
        self.assertEqual((fewer, more), (h41["favouring_casepath"], h41["favouring_self_consistency"]))
        self.assertGreater(more, 0)  # so the claim "fewer in all nine clusters" is false

    def test_perturbed_copy_moves_the_numbers(self):
        alt = F.perturbed(self.study)
        self.assertEqual(alt, F.perturbed(self.study))  # seeded
        r = F.rescore(self.study, alt, "perturbed")
        self.assertFalse(r["identical_to_registered"])
        h2 = next(c for c in r["contrasts"] if c["id"] == "H2")
        self.assertNotAlmostEqual(h2["alternative"]["diff"], h2["registered"]["diff"])

    def test_unamended_replay_reproduces_stored_checklists(self):
        import study3_review as R
        for d in ("casepath", "casepath_checklist"):
            self.study.load(d, "tenancy")
            plans, cnt = F.replay_tenancy(self.study, d, R.Cache())
            self.assertEqual(cnt["replayed"], 286)
            self.assertGreaterEqual(cnt["replay reproduces the stored scored checklist"], 285)

    def test_one_document_changed_by_hand(self):
        cid = self.study.cases["tenancy"][0]
        alt = {c: dict(self.study.D["tenancy"].reference(c)["document_states"]) for c in self.study.cases["tenancy"]}
        d = next(k for k, v in alt[cid].items() if v == "not_needed")
        alt[cid][d] = "required_now"
        r = F.rescore(self.study, alt, "one")
        self.assertEqual(r["agreement_by_subset"]["all"]["documents"] - r["agreement_by_subset"]["all"]["same_state"], 1)
        # a run that neither requested nor held d gains a missed document; one that requested it loses an unnecessary
        # request; one that held it moves from a spurious hold to a held required document (no strict error either way)
        plans = [p or {} for p in self.study.plans[("ric", "tenancy")][cid]]
        miss = sum(d not in set(p.get("requests", [])) | set(p.get("holds", [])) for p in plans) - sum(d in p.get("requests", []) for p in plans)
        base = F.s3.Study(F.SPEC, F.DATA, F.LABEL, self.study.D, inputs=self.study.inputs)
        before = sum(row["strict_unsafe"] for row in base.tenancy_rows("ric"))
        alt_study = F.s3.Study(F.SPEC, F.DATA, F.LABEL, {"tenancy": F.AltTenancy(self.study.D["tenancy"], alt),
                                                        "theft": self.study.D["theft"]}, inputs=self.study.inputs)
        after = sum(row["strict_unsafe"] for row in alt_study.tenancy_rows("ric"))
        self.assertEqual(after - before, miss)


if __name__ == "__main__":
    unittest.main()

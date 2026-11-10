"""Tests of analysis/study3.py on oracle, perturbed and synthetic plans of the development data (fresh/) and on
constructed inputs. No model calls, and fresh2/ is never loaded.

    python3 -m unittest test_study3      (from analysis/)   or   python3 test_study3.py
"""
import copy
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study3 as s3  # noqa: E402
import study2 as s2  # noqa: E402

SPEC = json.loads((HERE / "study3_spec.json").read_text())
s3.configure(SPEC)
D = s3.load_data("fresh")  # development data only
TEN, THEFT = D["tenancy"], D["theft"]
REQ_NOW = s2.REQ_NOW


# ----------------------------------------------------------------- helpers
def oracle_ten(ref):
    st = ref["document_states"]
    return {"requests": sorted(d for d, s in st.items() if s in REQ_NOW),
            "holds": sorted(d for d, s in st.items() if s == "held"), "deferred": False}


def oracle_theft():
    plans = {t: {"requests": [], "holds": []} for t in THEFT.texts()}
    for p in THEFT.pairs():
        opts = p["reference"]["acceptable_signed_deltas"]
        if p["kind"] == "on":
            plans[p["variant"]] = {"requests": sorted(d.lstrip("+") for d in opts[0]), "holds": []}
        else:
            plans[p["variant"]] = {"requests": [], "holds": sorted({d.lstrip("+") for o in opts for d in o})}
    return plans


def base_spec(designs, hypotheses=(), contrasts=(), stats=None):
    spec = copy.deepcopy({k: SPEC[k] for k in ("regimes", "measures", "tenancy_subsets", "languages", "deciding_agents")})
    spec.update(statistics=dict(SPEC["statistics"], **(stats or {})), data={"fresh": {"theft_stories": None}},
                designs=designs, hypotheses=list(hypotheses),
                secondary={"contrasts": list(contrasts), "cost_baseline": {}, "product_designs": []})
    return spec


def design(key, regimes=("tenancy", "theft"), runs=3):
    return {"key": key, "label": key, "model": "m", "regimes": list(regimes), "runs": runs,
            "store": {r: {"path": f"{key}_{r}.json", "key": "X|{case}|{run}", "field": "plan"} for r in regimes},
            "cost": {"method": "none"}}


def write_plans(root, key, regime, by_case, runs=3):
    out = {f"X|{c}|{r}": {"plan": (p[r] if isinstance(p, list) else p)} for c, p in by_case.items() for r in range(runs)}
    (Path(root) / f"{key}_{regime}.json").write_text(json.dumps(out))


def study(root, spec, data=None):
    return s3.Study(spec, "fresh", "test", data or D, inputs=s3.Inputs(root))


TEN_ORACLE = {c: oracle_ten(TEN.reference(c)) for c in TEN.claim_ids("test")}
THEFT_ORACLE = oracle_theft()


# ----------------------------------------------------------------- oracle plans
class Oracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        write_plans(cls.tmp.name, "oracle", "tenancy", TEN_ORACLE)
        write_plans(cls.tmp.name, "oracle", "theft", THEFT_ORACLE)
        cls.st = study(cls.tmp.name, base_spec([design("oracle")]))
        cls.res = cls.st.analyse()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_tenancy_oracle_scores_zero(self):
        m = self.res["designs"]["oracle"]["regimes"]["tenancy"]["measures"]
        for k in ("strict_unsafe_per_claim", "all_deviations_per_claim", "unnecessary_per_claim", "missed_per_claim",
                  "handed_per_claim", "premature_per_claim", "silent_skip_per_claim", "held_required_now_per_claim",
                  "spurious_holds_per_claim"):
            self.assertEqual(m[k], 0, k)
        self.assertEqual(m["requested_share"], 1.0)
        self.assertEqual(m["correct_hold_share"], 1.0)
        self.assertEqual(m["claim_runs"], 3 * len(TEN_ORACLE))

    def test_theft_oracle_scores_zero(self):
        m = self.res["designs"]["oracle"]["regimes"]["theft"]["measures"]
        self.assertEqual((m["wrong"], m["missed"], m["errors_per_pair"], m["errors_dedup_per_pair"]), (0, 0, 0.0, 0.0))
        self.assertEqual(m["unresolved"]["premature_rate"], 0)
        self.assertEqual(m["unresolved"]["other_changes_per_pair"], 0)
        self.assertEqual(m["unresolved"]["stable_rate"], 1.0)

    def test_cluster_values_zero_and_run_agreement_one(self):
        for measure, regime in (("strict_unsafe", "tenancy"), ("all_deviations", "tenancy"), ("errors", "theft")):
            vals = self.st.clusters("oracle", regime, measure)
            self.assertEqual(set(vals.values()), {0.0}, measure)
        self.assertEqual(len(self.st.clusters("oracle", "tenancy", "strict_unsafe")), 18)
        self.assertEqual(len(self.st.clusters("oracle", "theft", "errors")), 9)
        self.assertEqual(self.res["secondary"]["run_to_run_jaccard"]["oracle, tenancy"], 1.0)


# ----------------------------------------------------------------- perturbations
CID = next(c for c in TEN.claim_ids("test") if TEN.reference(c)["held_set"]
           and any(s == "not_needed" for s in TEN.reference(c)["document_states"].values()))
REF = TEN.reference(CID)
REQUIRED = next(d for d, s in REF["document_states"].items() if s == "required_now")
NOT_NEEDED = next(d for d, s in REF["document_states"].items() if s == "not_needed")
HELD = REF["held_set"][0]
N_REQ = sum(s in REQ_NOW for s in REF["document_states"].values())
MEASURES = ("requested", "missed", "unnecessary", "held_req", "spurious_hold", "correct_hold", "premature",
            "silent_skip", "handed", "handed_held", "strict_unsafe", "all_dev")


class TenancyPerturbation(unittest.TestCase):
    """One claim-run of an oracle design is perturbed; only the expected measures move."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def delta(self, plan):
        plans = dict(TEN_ORACLE)
        plans[CID] = [plan, TEN_ORACLE[CID], TEN_ORACLE[CID]]
        write_plans(self.tmp.name, "p", "tenancy", plans)
        st = study(self.tmp.name, base_spec([design("p", ("tenancy",))]), {"tenancy": TEN})
        rows = st.tenancy_rows("p")
        self.assertTrue(all(r["all_dev"] == 0 and r["strict_unsafe"] == 0 for r in rows if not (r["case"] == CID and r["run"] == 0)))
        row = next(r for r in rows if r["case"] == CID and r["run"] == 0)
        base = s2.ten_row(REF, oracle_ten(REF))
        base["all_dev"] = 0
        return {k: row[k] - base[k] for k in MEASURES if row[k] != base[k]}

    def plan(self, **change):
        p = copy.deepcopy(oracle_ten(REF))
        p.update(change)
        return p

    def test_drop_required(self):
        p = self.plan(requests=[d for d in oracle_ten(REF)["requests"] if d != REQUIRED])
        self.assertEqual(self.delta(p), {"requested": -1, "missed": 1, "strict_unsafe": 1, "all_dev": 1})

    def test_add_unneeded(self):
        p = self.plan(requests=oracle_ten(REF)["requests"] + [NOT_NEEDED])
        self.assertEqual(self.delta(p), {"unnecessary": 1, "strict_unsafe": 1, "all_dev": 1})

    def test_hold_required(self):
        o = oracle_ten(REF)
        p = self.plan(requests=[d for d in o["requests"] if d != REQUIRED], holds=o["holds"] + [REQUIRED])
        self.assertEqual(self.delta(p), {"requested": -1, "held_req": 1, "all_dev": 1})

    def test_hold_unneeded(self):
        p = self.plan(holds=oracle_ten(REF)["holds"] + [NOT_NEEDED])
        self.assertEqual(self.delta(p), {"spurious_hold": 1, "all_dev": 1})

    def test_request_held(self):
        o = oracle_ten(REF)
        p = self.plan(requests=o["requests"] + [HELD], holds=[d for d in o["holds"] if d != HELD])
        self.assertEqual(self.delta(p), {"premature": 1, "correct_hold": -1, "strict_unsafe": 1, "all_dev": 1})

    def test_skip_held(self):
        p = self.plan(holds=[d for d in oracle_ten(REF)["holds"] if d != HELD])
        self.assertEqual(self.delta(p), {"silent_skip": 1, "correct_hold": -1, "strict_unsafe": 1, "all_dev": 1})

    def test_hand_over(self):
        p = {"requests": [], "holds": [], "deferred": True}
        n_held = len(REF["held_set"])
        self.assertEqual(self.delta(p), {"requested": -N_REQ, "handed": N_REQ, "correct_hold": -n_held, "handed_held": n_held,
                                         "strict_unsafe": N_REQ, "all_dev": N_REQ})

    def test_failed_output_is_empty_plan(self):
        n_held = len(REF["held_set"])
        self.assertEqual(self.delta(None), {"requested": -N_REQ, "missed": N_REQ, "correct_hold": -n_held, "silent_skip": n_held,
                                            "strict_unsafe": N_REQ + n_held, "all_dev": N_REQ + n_held})


class TheftPerturbation(unittest.TestCase):
    def run_plans(self, plans):
        with tempfile.TemporaryDirectory() as tmp:
            write_plans(tmp, "p", "theft", plans)
            st = study(tmp, base_spec([design("p", ("theft",))]), {"theft": THEFT})
            return st.theft_rows("p")

    def test_drop_and_add(self):
        on = [p for p in THEFT.pairs() if p["kind"] == "on"]
        a, b = on[0], on[1]
        plans = dict(THEFT_ORACLE)
        plans[a["variant"]] = {"requests": THEFT_ORACLE[a["variant"]]["requests"] + ["Not a catalogue document"], "holds": []}
        dropped = sorted(THEFT_ORACLE[b["variant"]]["requests"])
        self.assertTrue(dropped)
        plans[b["variant"]] = {"requests": dropped[1:], "holds": []}
        rows, un = self.run_plans(plans)
        by = {(r["story"], r["condition"]): r for r in rows if r["run"] == 0}
        ra, rb = by[(a["story"], a["condition"])], by[(b["story"], b["condition"])]
        self.assertEqual((ra["wrong"], ra["missed"]), (1, 0))
        self.assertEqual((rb["wrong"], rb["missed"]), (0, 1))
        self.assertEqual(sum(r["errors"] for r in rows), 3 * 2)
        self.assertEqual(sum(r["premature"] for r in un), 0)

    def test_need_ids_mapped_to_names(self):
        from theft_data import doc_ids
        ids = doc_ids()
        plans = {t: {"requests": [ids[d].lower() for d in p["requests"]], "holds": [ids[d] for d in p["holds"]]}
                 for t, p in THEFT_ORACLE.items()}
        rows, un = self.run_plans(plans)
        self.assertEqual(sum(r["errors"] for r in rows), 0)
        self.assertEqual(sum(r["premature"] for r in un), 0)

    def test_request_open_condition_documents_is_premature(self):
        u = next(p for p in THEFT.pairs() if p["kind"] == "unresolved")
        plans = dict(THEFT_ORACLE)
        plans[u["variant"]] = {"requests": THEFT_ORACLE[u["variant"]]["holds"], "holds": []}
        rows, un = self.run_plans(plans)
        self.assertEqual(sum(r["premature"] for r in un), 3)
        self.assertEqual(sum(r["errors"] for r in rows), 0)


# ----------------------------------------------------------------- statistics
class Statistics(unittest.TestCase):
    def test_signflip_hand_computed(self):
        # [1, 2, 3]: signed sums 6, 0, 2, -4, 4, -2, 0, -6 -> |sum| >= 6 in 2 of 8
        self.assertEqual(s3.signflip_p([1, 2, 3]), 0.25)
        # [1, 1]: sums 2, 0, 0, -2 -> 2 of 4
        self.assertEqual(s3.signflip_p([1, 1]), 0.5)
        # all zero: every sign vector is as extreme
        self.assertEqual(s3.signflip_p([0, 0, 0]), 1.0)
        # [1, -1, 3]: obs 3; signed sums 3, -3, 5, -1, 1, -5, 3, -3 -> |sum| >= 3 in 6 of 8
        self.assertEqual(s3.signflip_p([1, -1, 3]), 0.75)
        # nine clusters, all the same sign: 2 / 512, the smallest attainable p
        self.assertAlmostEqual(s3.signflip_p([0.5] * 9), 2 / 512)

    def test_fast_signflip_equals_enumeration(self):
        g = random.Random(7)
        for n in (17, 18):
            for _ in range(3):
                d = [g.choice([0, 1 / 3, -1 / 3, 2 / 3, -1, 0.25]) + (g.random() * 0.1 if g.random() < 0.3 else 0) for _ in range(n)]
                self.assertEqual(s3.signflip_p(d), s3._signflip_enumerate(d), d)
        d = [1 / 3] * 9 + [-1 / 3] * 8  # many ties
        self.assertEqual(s3.signflip_p(d), s3._signflip_enumerate(d))
        self.assertEqual(s3.signflip_p([0.0] * 20), 1.0)

    def test_noninferiority_hand_computed(self):
        c = s3.run_contrast({"a": 1.3, "b": 1.3}, {"a": 1.0, "b": 1.0}, "t1", False, "noninferiority", 0.25)
        self.assertEqual((c["p"], c["diff_ci"]), (1.0, [c["diff"]] * 2))
        c = s3.run_contrast({"a": 1.2, "b": 1.2}, {"a": 1.0, "b": 1.0}, "t2", False, "noninferiority", 0.25)
        self.assertEqual(c["p"], 0.0)
        # two clusters with differences 0.3 and 0: resampled means 0.3 (1/4), 0.15 (1/2), 0 (1/4) -> p = 1/4
        c = s3.run_contrast({"a": 1.3, "b": 1.0}, {"a": 1.0, "b": 1.0}, "t3", False, "noninferiority", 0.25)
        self.assertAlmostEqual(c["p"], 0.25, delta=0.02)
        self.assertEqual(c["min_p"], 1 / 10000)
        # higher is better (requested share): 3 points lower with a 5-point margin
        c = s3.run_contrast({"a": 0.92, "b": 0.92}, {"a": 0.95, "b": 0.95}, "t4", True, "noninferiority", 0.05)
        self.assertEqual(c["p"], 0.0)

    def test_bootstrap_deterministic(self):
        a = {f"c{i}": i * 0.1 for i in range(9)}
        b = {f"c{i}": i * 0.1 + (0.2 if i % 2 else -0.1) for i in range(9)}
        self.assertEqual(s3.run_contrast(a, b, "same", False, "signflip"), s3.run_contrast(a, b, "same", False, "signflip"))


def fake(p, favours="a", test="signflip"):
    return {"p": p, "favours": favours, "test": test}


class FixedSequence(unittest.TestCase):
    A = 0.05

    def test_all_confirmed(self):
        st = s3.fixed_sequence([("H1", [fake(0.01)]), ("H2", [fake(0.01)] * 3), ("H3", [fake(0.0, test="noninferiority")])], self.A)
        self.assertEqual(st, {"H1": "confirmed", "H2": "confirmed", "H3": "confirmed"})

    def test_first_fails_later_not_tested(self):
        st = s3.fixed_sequence([("H1", [fake(0.2)]), ("H2", [fake(0.001)]), ("H3", [fake(0.0, test="noninferiority")])], self.A)
        self.assertEqual(st, {"H1": "not confirmed", "H2": s3.NOT_TESTED, "H3": s3.NOT_TESTED})

    def test_all_must_hold_one_fails(self):
        st = s3.fixed_sequence([("H1", [fake(0.01)]), ("H2", [fake(0.004), fake(0.06), fake(0.004)]), ("H3", [fake(0.0)])], self.A)
        self.assertEqual(st, {"H1": "confirmed", "H2": "not confirmed", "H3": s3.NOT_TESTED})

    def test_wrong_direction_is_not_confirmed(self):
        st = s3.fixed_sequence([("H1", [fake(0.004, favours="b")]), ("H2", [fake(0.004)])], self.A)
        self.assertEqual(st, {"H1": "not confirmed", "H2": s3.NOT_TESTED})

    def test_boundary_p_equal_alpha_is_not_significant(self):
        self.assertEqual(s3.fixed_sequence([("H1", [fake(0.05)])], self.A), {"H1": "not confirmed"})

    def test_not_run_stops_the_sequence(self):
        st = s3.fixed_sequence([("H1", [fake(0.01)]), ("H2", [None, fake(0.01)]), ("H3", [fake(0.01)])], self.A)
        self.assertEqual(st, {"H1": "confirmed", "H2": "not run", "H3": s3.NOT_TESTED})


# ----------------------------------------------------------------- end to end on synthetic designs, missing files
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.tmp.name
        # "good" is the oracle; "bad" adds one unneeded tenancy request per claim and, in theft, an extra document
        # in every on-variant (one wrong change per pair)
        write_plans(root, "good", "tenancy", TEN_ORACLE)
        write_plans(root, "good", "theft", THEFT_ORACLE)
        bad_t = {c: dict(p, requests=p["requests"] + ["not_a_family_document"]) for c, p in TEN_ORACLE.items()}
        bad_th = {t: (dict(p, requests=p["requests"] + ["Extra document"]) if "-on-" in t else p) for t, p in THEFT_ORACLE.items()}
        write_plans(root, "bad", "tenancy", bad_t)
        write_plans(root, "bad", "theft", bad_th)
        designs = [design("good"), design("bad"), design("absent")]
        hyps = [{"id": "H1", "text": "t", "regime": "theft", "measure": "errors", "a": "good", "b": "bad", "test": "signflip"},
                {"id": "H2", "text": "t", "regime": "theft", "measure": "errors", "a": "good", "b": ["bad", "absent"], "test": "signflip"},
                {"id": "H3", "text": "t", "regime": "tenancy", "measure": "strict_unsafe", "a": "good", "b": "bad",
                 "test": "noninferiority", "margin": 0.1}]
        contrasts = [{"id": "S1", "section": "s", "regime": "tenancy", "measure": "all_deviations", "a": "good", "b": "absent", "test": "signflip"},
                     {"id": "S2", "section": "s", "regime": "tenancy", "measure": "requested_share", "a": "bad", "b": "good",
                      "test": "noninferiority", "margin": 0.05}]
        cls.spec = base_spec(designs, hyps, contrasts)
        cls.res = study(root, cls.spec).analyse()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_missing_design_is_not_run(self):
        st = self.res["designs"]["absent"]["regimes"]
        self.assertEqual(st["tenancy"]["status"], "not run")
        self.assertIn("file missing", st["theft"]["reason"])
        self.assertIn("absent_theft.json", self.res["inputs"]["files_missing"])

    def test_hypotheses(self):
        h = {x["id"]: x for x in self.res["hypotheses"]}
        self.assertEqual(h["H1"]["status"], "confirmed")
        t = h["H1"]["tests"][0]
        self.assertEqual((t["a_value"], t["b_value"], t["diff"], t["clusters"], t["nonzero_clusters"]), (0.0, 1.0, -1.0, 9, 9))
        self.assertAlmostEqual(t["p"], 2 / 512)
        self.assertEqual(h["H2"]["status"], "not run")
        self.assertIsNone(h["H2"]["tests"][1])
        self.assertTrue(h["H2"]["not_run"])
        self.assertEqual(h["H3"]["status"], s3.NOT_TESTED)
        self.assertFalse(h["H3"]["inside_procedure"])
        self.assertAlmostEqual(h["H3"]["tests"][0]["diff"], -1.0)  # raw result still reported

    def test_secondary(self):
        sec = {c["id"]: c for c in self.res["secondary"]["contrasts"]}
        self.assertIsNone(sec["S1"]["result"])
        self.assertTrue(sec["S1"]["not_run"])
        self.assertEqual(sec["S2"]["result"]["diff"], 0.0)  # extra requests do not lower the requested share
        self.assertEqual(sec["S2"]["result"]["p"], 0.0)

    def test_report_renders(self):
        md = s3.markdown(self.res, self.spec)
        self.assertIn("not run", md)
        self.assertIn("outside the procedure", md)
        self.assertNotIn("Design | regime", md)


# ----------------------------------------------------------------- tenancy subsets on a constructed reference
class FakeTenancy:
    """Three claims in one family: an empty reference (the defining event denied), an empty request set with held
    documents (the defining event left open), and an ordinary claim."""
    REFS = {
        "c_denied": {"family_id": "f1", "open_fact": None, "request_set": [], "held_set": [],
                     "document_states": {"a": "not_needed", "b": "not_needed"}},
        "c_open": {"family_id": "f1", "open_fact": {"flag": "termination_received", "true_value": False}, "request_set": [],
                   "held_set": ["a", "b"], "document_states": {"a": "held", "b": "held"}},
        "c_plain": {"family_id": "f1", "open_fact": None, "request_set": ["a"], "held_set": [],
                    "document_states": {"a": "required_now", "b": "not_needed"}},
    }
    LANG = {"c_denied": "en", "c_open": "de-CH", "c_plain": "en"}

    def claim_ids(self, split):
        return sorted(self.REFS)

    def reference(self, cid):
        return self.REFS[cid]

    def intake(self, cid):
        return {"submission": {"language": self.LANG[cid]}}


class Subsets(unittest.TestCase):
    def test_degenerate_selector(self):
        F = FakeTenancy()
        with tempfile.TemporaryDirectory() as tmp:
            plans = {c: {"requests": ["a"], "holds": [], "deferred": False} for c in F.REFS}
            write_plans(tmp, "d", "tenancy", plans)
            st = study(tmp, base_spec([design("d", ("tenancy",))]), {"tenancy": F})
            res = st.analyse()
        sub = res["secondary"]["tenancy_subsets"]
        self.assertEqual(sub["claims"], {"defining_event_false": 1, "without_defining_event_false": 2,
                                         "request_set_empty": 2, "open_fact": 1})
        by = sub["by_design"]["d"]
        # requesting "a" is unnecessary in c_denied, premature in c_open (and b silently skipped), right in c_plain
        self.assertEqual(by["defining_event_false"]["strict_unsafe_per_claim"], 1.0)
        self.assertEqual(by["without_defining_event_false"]["strict_unsafe_per_claim"], 1.0)
        self.assertEqual(by["open_fact"]["premature_per_claim"], 1.0)
        self.assertEqual(by["open_fact"]["silent_skip_per_claim"], 1.0)
        self.assertEqual(by["all claims"]["claims"], 3)
        self.assertEqual(res["secondary"]["tenancy_languages"]["claims"], {"English": 2, "German": 1})


# ----------------------------------------------------------------- derived designs
class Derived(unittest.TestCase):
    def test_majority(self):
        p = [{"requests": ["a", "b"], "holds": ["c"]}, {"requests": ["a"], "holds": ["b", "c"]}, None,
             {"requests": ["a"], "holds": [], "deferred": True}, {"requests": ["d"], "holds": ["a"]}]
        self.assertEqual(s3.majority(p), {"requests": ["a"], "holds": [], "deferred": False})
        self.assertEqual(s3.majority(p[:3]), {"requests": ["a"], "holds": ["b", "c"], "deferred": False})

    def test_self_consistency_matches_stored_development_arm(self):
        stored = s3.TMIS / "runs" / "product" / "baselines_tenancy_gpt-6-luna_fresh.json"
        b1 = s3.TMIS / "runs" / "v2" / "plans_tenancy_gpt-6-luna_fresh_heldout.json"
        if not (stored.exists() and b1.exists()):
            self.skipTest("development files absent")
        st = s3.Study(SPEC, "fresh", "r3", {"tenancy": TEN})
        self.assertTrue(st.load("self_consistency", "tenancy"))
        sc = json.loads(stored.read_text())
        for c, plans in st.plans[("self_consistency", "tenancy")].items():
            want = sc[f"SC|{c}|0"]["plan"]
            self.assertEqual((plans[0]["requests"], plans[0]["holds"], plans[0]["deferred"]),
                             (want["requests"], want["holds"], want["deferred"]), c)

    def test_two_valued_matches_stored_development_arms(self):
        """The stored TWO_F / TWO_T tenancy arms were derived from the product run p7ff (commit 7ff7af64)."""
        if not (s3.TMIS / "runs/product/plans_tenancy_gpt-6-luna_fresh_p7ff.json").exists():
            self.skipTest("development files absent")
        pkg = {"commit": "7ff7af648279e58765732ab2e1ed8f36d7f3b155", "subdir": "casepath-internal"}
        spec = copy.deepcopy(SPEC)
        dev = spec["development_runs"]["fresh/r3"]
        dev["designs"]["casepath"]["tenancy"]["path"] = "runs/product/plans_tenancy_gpt-6-luna_fresh_p7ff.json"
        dev["product_evaluator"]["tenancy"]["package"] = pkg
        st = s3.Study(spec, "fresh", "r3", {"tenancy": TEN})
        stored = json.loads((s3.TMIS / "runs/product/baselines_tenancy_gpt-6-luna_fresh.json").read_text())
        for key, arm in (("two_valued_false", "TWO_F"), ("two_valued_true", "TWO_T")):
            self.assertTrue(st.load(key, "tenancy"), st.status[(key, "tenancy")])
            for c, plans in st.plans[(key, "tenancy")].items():
                for r, p in enumerate(plans):
                    want = stored[f"{arm}|{c}|{r}"]["plan"]
                    if want is None:
                        self.assertIsNone(p)
                        continue
                    self.assertEqual((sorted(p["requests"]), sorted(p["holds"])), (want["requests"], want["holds"]), (key, c, r))

    def test_theft_two_valued_matches_stored_development_arm(self):
        """The stored theft TWO_F arm was derived from the product run r3-full (commit 9ca1207)."""
        st = s3.Study(SPEC, "fresh", "r3", {"theft": THEFT})
        if not st.load("two_valued_false", "theft"):
            self.skipTest(st.status[("two_valued_false", "theft")].get("reason"))
        stored = json.loads((s3.TMIS / "runs/product/baselines_theft_gpt-6-luna_fresh.json").read_text())
        for c, plans in st.plans[("two_valued_false", "theft")].items():
            for r, p in enumerate(plans):
                want = stored[f"TWO_F|{c}|{r}"]["plan"]
                self.assertEqual((p["requests"], p["holds"]), (want["requests"], want["holds"]), (c, r))

    def test_missing_evaluator_is_not_run(self):
        spec = copy.deepcopy(SPEC)
        spec["development_runs"]["fresh/r3"]["product_evaluator"]["theft"]["package"] = "/nonexistent"
        st = s3.Study(spec, "fresh", "r3", {"theft": THEFT})
        if not st.load("casepath", "theft"):
            self.skipTest("development files absent")
        self.assertFalse(st.load("two_valued_false", "theft"))
        self.assertIn("product evaluator not available", st.status[("two_valued_false", "theft")]["reason"])


# ----------------------------------------------------------------- development reproduction and determinism
TARGETS = {("casepath", "tenancy"): 0.157, ("casepath_checklist", "tenancy"): 0.132, ("ric", "tenancy"): 0.199,
           ("ric_frontier", "tenancy"): 0.157, ("self_consistency", "tenancy"): 0.194,
           ("casepath", "theft"): 0.796, ("casepath_checklist", "theft"): 0.926, ("core", "theft"): 0.333,
           ("ric", "theft"): 1.333, ("ric_original", "theft"): 1.611, ("ric_original_frontier", "theft"): 0.537,
           ("react", "theft"): 1.111, ("model_executes_rules", "theft"): 2.056}


class Development(unittest.TestCase):
    def test_round3_numbers_and_identical_bytes(self):
        if not (s3.TMIS / "runs/product/plans_tenancy_gpt-6-luna_fresh_r3b-full.json").exists():
            self.skipTest("development files absent")
        with tempfile.TemporaryDirectory() as tmp:
            res = s3.main(["--data", "fresh", "--label", "r3", "--out", f"{tmp}/a"])
            s3.main(["--data", "fresh", "--label", "r3", "--out", f"{tmp}/b"])
            self.assertEqual(Path(f"{tmp}/a.md").read_bytes(), Path(f"{tmp}/b.md").read_bytes())
            ja, jb = (json.loads(Path(f"{tmp}/{x}.json").read_text()) for x in "ab")
            # other sessions append to the shared ledgers while this runs; their hashes may differ, nothing else may
            for j in (ja, jb):
                j["inputs"]["files_read"] = {k: v for k, v in j["inputs"]["files_read"].items() if "ledger" not in k}
            self.assertEqual(json.dumps(ja, sort_keys=True), json.dumps(jb, sort_keys=True))
        for (d, reg), want in TARGETS.items():
            m = res["designs"][d]["regimes"][reg]["measures"]
            got = m["strict_unsafe_per_claim"] if reg == "tenancy" else m["errors_per_pair"]
            self.assertEqual(round(got, 3), want, (d, reg))


class Guard(unittest.TestCase):
    def test_fresh2_refused_without_committed_plan(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fresh2_guard_check", s3.TMIS / "fresh2" / "guard.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        if guard.plan_committed():
            self.skipTest("the Study 3 plan is committed; fresh2 may be loaded")
        with self.assertRaises(SystemExit):
            s3.load_data("fresh2")


if __name__ == "__main__":
    unittest.main(verbosity=2)

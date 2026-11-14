"""A deadline that exists for one sub-case of an area carries the condition of that sub-case, its trigger date is asked
only while the deadline can apply, and a key point holds only where its article says it does."""
import unittest

from casepath.agents import core
from casepath.process import area, keypoints
from casepath.process.items import build_items, open_customer_questions, trigger_question
from tests.test_handler_workflow import document, fact

# Deadlines reviewed as holding for every case of their area: any other deadline names the sub-case it exists for.
FOR_THE_WHOLE_AREA = {
    ("arbeit-kuendigung", "einsprache_kuendigung"), ("arbeit-kuendigung", "klage_entschaedigung"),
    ("arbeit-lohn", "verjaehrung_lohn"), ("betreibung-schuldner", "beschwerde_amt"),
    ("miete-kaution", "kaution_bank"), ("miete-kaution", "maengelmeldung"), ("miete-kuendigung", "anfechtung"),
    ("miete-mietzinserhoehung", "anfechtung_erhoehung"), ("privatversicherung", "faelligkeit"),
    ("privatversicherung", "klagefrist"), ("schaden-unfall", "verjaehrung_relativ"),
    ("vertrag-kauf", "maengelanzeige"), ("vertrag-kauf", "verjaehrung_gewaehrleistung"),
}
SUB_CASE = {  # deadline: the fact of the sub-case and the value it exists for
    ("sozialversicherung", "einwand_vorbescheid"): ("iv", True),
    ("sozialversicherung", "beschwerde_iv"): ("iv", True),
    ("sozialversicherung", "einsprache"): ("iv", False),
    ("sozialversicherung", "beschwerde"): ("iv", False),
    ("verkehr", "einsprache_strafbefehl"): ("strafbefehl", True),
    ("verkehr", "bedenkfrist"): ("ordnungsbusse", True),
    ("verkehr", "beschwerde_entzug"): ("entzug_verfahren", True),
    ("betreibung-schuldner", "aberkennungsklage"): ("provisorisch", True),
}


def listed(wid, facts, documents=()):
    result = {"facts": [fact(f, v) for f, v in facts], "documents": [document(d) for d in documents],
              "brief": {"request": "x", "parties": [], "timeline": []}}
    state = core.evaluate(area.workflow(wid), [], [], result, "c")
    return state, {i["item_id"]: i for i in build_items(state, result)}


class DeadlineConditionTests(unittest.TestCase):
    def test_every_deadline_names_its_sub_case_unless_reviewed_as_holding_for_the_whole_area(self):
        for w in area.shipped():
            for d in w.get("deadlines", []):
                with self.subTest(area=w["id"], deadline=d["id"]):
                    if (w["id"], d["id"]) in FOR_THE_WHOLE_AREA:
                        self.assertFalse(d.get("when"), "reviewed as unconditioned: review again before adding a condition")
                        continue
                    self.assertTrue(d.get("when"), "a deadline for one sub-case needs its condition (or a review as general)")
                    self.assertTrue(d.get("when_text"), "the condition is said in words on the card")

    def test_a_sub_case_deadline_does_not_apply_to_the_other_sub_case(self):
        rows = {w["id"]: w for w in area.shipped()}
        for (wid, did), (fid, value) in SUB_CASE.items():
            with self.subTest(area=wid, deadline=did):
                d = next(x for x in rows[wid]["deadlines"] if x["id"] == did)
                self.assertIsNone(area.compute_deadline(d, "2026-11-03", {fid: not value}))
                self.assertIsNotNone(area.compute_deadline(d, "2026-11-03", {fid: value}))


class TriggerQuestionTests(unittest.TestCase):
    def test_the_rule_asks_offers_or_leaves_out_by_the_deadlines_a_date_starts(self):
        graph = {"deadlines": [{"trigger": "a", "when": {"fact": "x", "is": True}}, {"trigger": "a", "when": {"fact": "y", "is": True}},
                               {"trigger": "b"}]}
        self.assertEqual(trigger_question(graph, "a", {"x": True, "y": False}), "ask")
        self.assertEqual(trigger_question(graph, "a", {"x": False}), "offer")
        self.assertIsNone(trigger_question(graph, "a", {"x": False, "y": False}))
        self.assertEqual(trigger_question(graph, "b", {}), "ask")
        self.assertEqual(trigger_question(graph, "other", {}), "ask")  # not a trigger date: the rule does not touch it

    def test_an_accident_insurance_case_is_not_asked_about_a_preliminary_decision_of_the_disability_insurance(self):
        base = [("rechtsgebiet", "Sozialversicherungsrecht / Verfügung, Einsprache, Beschwerde")]
        _, accident = listed("sozialversicherung", base + [("iv", False)])
        self.assertNotIn("letter_question:vorbescheid_erhalten", accident)
        self.assertIn("letter_question:verfuegung_erhalten", accident)
        _, unknown = listed("sozialversicherung", base)
        self.assertEqual(unknown["letter_question:vorbescheid_erhalten"]["ask"], "proposed")  # iv open: offered, not ticked
        _, disability = listed("sozialversicherung", base + [("iv", True)])
        self.assertIn("letter_question:vorbescheid_erhalten", disability)

    def test_a_penalty_order_case_is_not_asked_about_a_fixed_fine_or_a_licence_decision(self):
        base = [("rechtsgebiet", "Strafrecht, Ausweisentzug / Strassenverkehr"), ("strafbefehl", True), ("einsprache_erhoben", False)]
        _, order = listed("verkehr", base + [("ordnungsbusse", False), ("entzug_verfahren", False)])
        self.assertNotIn("letter_question:ordnungsbusse_erhalten", order)
        self.assertNotIn("letter_question:entzug_verfuegung", order)
        self.assertIn("letter_question:strafbefehl_erhalten", order)
        _, open_ = listed("verkehr", base)
        self.assertEqual(open_["letter_question:entzug_verfuegung"]["ask"], "proposed")
        _, fine = listed("verkehr", [("rechtsgebiet", "Strafrecht, Ausweisentzug / Strassenverkehr"), ("strafbefehl", False), ("ordnungsbusse", True)])
        self.assertNotIn("letter_question:strafbefehl_erhalten", fine)
        self.assertIn("letter_question:ordnungsbusse_erhalten", fine)

    def test_a_payment_order_case_is_not_asked_about_a_provisional_release_no_court_granted(self):
        routing = next(f for f in area.workflow("betreibung-schuldner")["facts"] if f["id"] == "rechtsgebiet")["values"][0]
        base = [("rechtsgebiet", routing), ("rechtsvorschlag_erhoben", False)]
        _, refused = listed("betreibung-schuldner", base + [("provisorisch", False)])
        self.assertNotIn("letter_question:rechtsoeffnung_eroeffnet", refused)
        self.assertIn("letter_question:zahlungsbefehl_zugestellt", refused)
        _, granted = listed("betreibung-schuldner", base + [("provisorisch", True)])
        self.assertIn("letter_question:rechtsoeffnung_eroeffnet", granted)

    def test_a_ticked_trigger_question_is_only_offered_while_its_condition_is_open(self):
        for w in area.shipped():
            graph = area.workflow(w["id"])
            for f in graph["facts"]:
                deadlines = [d for d in graph.get("deadlines", []) if d["trigger"] == f["id"]]
                if f.get("ask_customer") is not True or not deadlines or not all(d.get("when") for d in deadlines):
                    continue
                with self.subTest(area=w["id"], fact=f["id"]):  # nothing known: the conditions are open, nothing is ticked
                    self.assertNotIn(f["id"], [x["id"] for x in open_customer_questions(graph, {})])


class WarningKeyPointTests(unittest.TestCase):
    def points(self, facts):
        return {p["id"]: p["state"] for p in keypoints.evaluate(area.workflow("verkehr"), facts)}

    def test_a_warning_instead_of_a_withdrawal_holds_only_after_a_light_offence(self):
        self.assertEqual(self.points({"vorentzug": False, "leichte_widerhandlung": True}).get("verwarnung"), "applies")
        self.assertEqual(self.points({"vorentzug": False}).get("verwarnung"), "open")  # gravity not established: a question
        self.assertNotIn("verwarnung", self.points({"vorentzug": False, "leichte_widerhandlung": False}))  # medium or grave
        self.assertNotIn("verwarnung", self.points({"vorentzug": True, "leichte_widerhandlung": True}))

    def test_the_point_rests_on_the_articles_that_define_a_light_offence_and_its_warning(self):
        graph = area.workflow("verkehr")
        point = next(p for p in graph["key_points"] if p["id"] == "verwarnung")
        self.assertIn("law#svg-16a.1", point["law"])
        self.assertTrue(graph["law"]["svg-16a.1"]["passage"].startswith("Eine leichte Widerhandlung begeht"))
        self.assertTrue(all(graph["law"][r.split("#", 1)[1]]["verified"] for r in point["law"]))


if __name__ == "__main__":
    unittest.main()

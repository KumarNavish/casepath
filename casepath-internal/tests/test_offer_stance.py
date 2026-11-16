"""An offer of the other side, decision first (process/live.py): the customer is asked before anything is answered, the
answer is one question with what follows each choice, and the choice writes the letter to the other side.

Scripted and model-free: the update tests' synthetic offer (tests/test_update.py), held by the app."""
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import live
from casepath.web.app import create_app
from tests.test_update import OFFER_A, OFFER_B, SITUATIONS, WID, both_ways

USER = "N. Kumar"


class OfferStanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "catalogue").mkdir()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(root / "catalogue"),
                                                           "CASEPATH_DEV_USER": USER}), model_factory=lambda: None))
        store = self.store = self.client.app.state.store
        self.case = store.create_case("Heizung (synthetisch)", {"synthetic": True}, USER)["id"]
        ids = {f["id"]: store.add_file(self.case, f["name"], "application/pdf", "pdf", b"%PDF-1.4 synthetic " + f["id"].encode(), f["extraction"], USER)["id"]
               for f in (OFFER_A, OFFER_B)}
        text = json.dumps(both_ways("offer")[2])
        for old, new in ids.items():
            text = text.replace(f'"{old}"', f'"{new}"')
        run = store.create_run(self.case, USER)
        store.update_run(run["id"], status="completed", workflow_id=WID, finished_at="2026-11-15T10:00:00+00:00", result=json.loads(text))
        for e in SITUATIONS["offer"]["edits"]:
            self.post("edits", {"op": e["op"], "args": e["args"], "reason": "", "reason_code": "none", "recheck": False})

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def post(self, path, body, status=201):
        r = self.client.post(f"/api/cases/{self.case}/{path}", json=body)
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def view(self):
        v = self.client.get(f"/api/cases/{self.case}").json()
        return v, next(i for i in v["items"] if i["kind"] == "next_action")

    def asked(self):
        self.post("entries", {"kind": "telefon", "party": "kunde", "date": "2026-11-15", "said": "Kundin möchte das Angebot annehmen."})

    def test_the_customer_is_asked_first_and_no_answer_can_be_given_before(self):
        view, action = self.view()
        self.assertEqual((action["action"], action["value"]), ("A2", "Kundschaft zum Angebot befragen"))
        self.assertIsNone(view["screen"]["decision"])
        self.assertEqual(self.post("offer/stance", {"stance": "annehmen"}, 409)["detail"], "In diesem Fall wartet kein Angebot auf eine Antwort.")

    def test_after_the_call_the_offer_still_waits_and_the_card_asks_one_question_with_what_follows(self):
        self.asked()
        view, action = self.view()
        # talking to the customer does not answer the other side: the offer stays the open item (it was «Antwort abwarten»)
        self.assertEqual((action["action"], action["value"], action["incoming"]["kind"]), ("A9", "Antwort auf das Angebot der Gegenpartei", "angebot"))
        decision = view["screen"]["decision"]
        self.assertEqual((decision["key"], decision["chosen"], decision["offer"]), ("angebot", None, "2026-11-05"))
        self.assertEqual([(a["label"], a["stance"]) for a in decision["answers"]], [("annehmen", "annehmen"), ("ablehnen", "ablehnen"), ("Gegenangebot", "gegenangebot")])
        self.assertTrue(all(a["then"] for a in decision["answers"]))
        self.assertIsNone(view["draft"]["text"])  # no letter before the judgment

    def test_each_answer_writes_its_letter_to_the_other_side_and_can_be_changed_or_taken_back(self):
        self.asked()
        self.post("offer/stance", {"stance": "annehmen"})
        view, _ = self.view()
        draft = view["draft"]
        self.assertEqual((draft["form"], draft["title"], draft["to"], draft["live"]), ("A9", "Annahme des Angebots", "Gegenpartei, Kopie an die Kundschaft", "A9_annehmen"))
        self.assertIn("Wir beziehen uns auf Ihr Angebot vom 05.11.2026.\n\nUnsere Versicherte nimmt dieses Angebot an.", draft["text"])
        self.assertEqual(view["screen"]["decision"]["chosen"], "annehmen")
        self.assertEqual([r["to"] for r in draft["recipients"]], ["gegenpartei"])
        self.post("offer/stance", {"stance": "gegenangebot"})
        draft = self.view()[0]["draft"]
        self.assertEqual(draft["title"], "Gegenangebot")
        self.assertIn("[bitte ergänzen: Inhalt des Gegenangebots]", draft["text"])  # what is offered is the handler's to write
        self.assertIn("Unpräjudiziell und ohne Anerkennung einer Rechtspflicht", draft["text"])
        self.post("offer/stance", {"stance": None})
        view, _ = self.view()
        self.assertEqual((view["draft"]["text"], view["screen"]["decision"]["chosen"]), (None, None))
        log = json.dumps(view["verlauf"], ensure_ascii=False)  # each answer is in the case's log, attributed
        for line in ("Angebot der Gegenpartei: annehmen", "Angebot der Gegenpartei: Gegenangebot", "Antwort auf das Angebot zurückgenommen"):
            self.assertIn(line, log)

    def test_the_approved_answer_rests_on_its_own_parts_and_is_recorded_as_a_step_of_the_negotiation(self):
        from casepath.process import completion
        self.asked()
        self.post("offer/stance", {"stance": "ablehnen"})
        draft = self.view()[0]["draft"]
        self.assertEqual(completion.FORM_RECORD["A9"], ("gegenpartei", "schreiben_gegenpartei", "9"))
        self.assertEqual(live.element_ids(draft["live"]), ["backbone:live.A9_ablehnen.bezug", "backbone:live.A9_ablehnen.ablehnung", "backbone:live.A9_ablehnen.frist"])
        self.assertIn("Sie hält an ihrer Forderung fest.", draft["text"])
        self.assertNotIn("{frist}", draft["text"])
        r = self.post("actions/approve", {"form": draft["form"], "version": draft["version"], "op_id": "op-stance-1"}, 200)
        relies = r["approval"]["relies"]
        self.assertTrue(set(live.element_ids("A9_ablehnen")) <= set(relies), relies)


if __name__ == "__main__":
    unittest.main()

"""A refused cover is told as a refused cover (process/refusal.py): its own letter with the point that decides it,
never the demand before an end of benefits for missing cooperation; approved only on wording a jurist released."""
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import refusal
from casepath.read.extract import extract
from casepath.web.app import create_app
from tests.test_outbox import MAIL, TOLD, USER

GAP = re.compile(r"\[bitte ergänzen: [^\]]*\]")


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "catalogue").mkdir()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(root / "catalogue"),
                                                           "CASEPATH_DEV_USER": USER}), model_factory=lambda: None))
        store = self.store = self.client.app.state.store
        case = store.create_case("Schimmel im Bad (synthetisch)", {"synthetic": True}, USER)
        row = extract("Meldung Lea Brunner.eml", "message/rfc822", MAIL)
        mail = store.add_file(case["id"], "Meldung Lea Brunner.eml", row["media_type"], row["kind"], MAIL, row, USER)["id"]
        fact = lambda f, v, quote=None: {"fact": f, "status": "established", "verdict": "accepted", "value": v,
                                          "citations": [{"file": mail, "quote": quote}] if quote else []}
        run = store.create_run(case["id"], USER)
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja", TOLD)], "documents": [],
                                 "brief": {"request": "Lea Brunner möchte Hilfe, weil im Badezimmer immer wieder Schimmel auftritt.",
                                           "parties": [{"role": "Mieterin (VN)", "name": "Frau Lea Brunner"}], "timeline": []}})
        self.case = case["id"]

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def view(self):
        return self.client.get(f"/api/cases/{self.case}").json()

    def decide(self, fact, value):
        r = self.client.post(f"/api/cases/{self.case}/edits", json={"op": "set_fact", "args": {"fact": fact, "value": value}, "reason": "",
                                                                     "reason_code": "none", "recheck": False})
        self.assertEqual(r.status_code, 201, r.text)

    def approve(self, draft, op):
        return self.client.post(f"/api/cases/{self.case}/actions/approve", json={"form": draft["form"], "version": draft["version"], "op_id": op})

    def test_a_refused_cover_prepares_its_refusal_with_the_point_that_decides_it(self):
        self.decide("deckung", "abgelehnt")
        self.decide("deckung_grund", "wartefrist")
        view = self.view()
        draft = view["draft"]
        self.assertEqual((draft["form"], draft["title"], draft["kind"]), (refusal.FORM, "Deckungsablehnung mitteilen", "A12"))
        self.assertIn("weil folgende Voraussetzung der Deckung nicht erfüllt ist: «Ausserhalb der Wartefrist»", draft["text"])
        self.assertIn("der Allgemeinen Bedingungen)", draft["text"])  # the clause of the edition that applies
        self.assertNotIn("Säumnisfolgen", draft["text"])  # never the demand before an end of benefits for missing cooperation
        self.assertNotIn("Mitwirkung", draft["text"])
        self.assertEqual(len(GAP.findall(draft["text"])), 1)  # the explanation of the case is the handler's own
        action = next(i for i in view["items"] if i["kind"] == "next_action")
        self.assertEqual((action["action"], action["closing"]), ("A12", "Deckung abgelehnt"))
        row = next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == self.case)
        self.assertEqual(row["next_action"]["text"], "Dossier schliessen: Deckung abgelehnt")

    def test_without_a_named_point_the_point_is_a_gap_too(self):
        self.decide("deckung", "abgelehnt")
        self.assertEqual(len(GAP.findall(self.view()["draft"]["text"])), 2)

    def test_the_refusal_is_approved_only_on_wording_a_jurist_released(self):
        self.decide("deckung", "abgelehnt")
        self.decide("deckung_grund", "rechtsgebiet")
        view = self.view()
        held = view["completion"]["held_now"]
        self.assertEqual([(h["key"], h["mark"], h["blocks"]) for h in held], [(k, "noch nicht freigegeben", True) for k in refusal.element_ids()])
        draft = view["draft"]
        parts = [{"part": p["part"], "base_sha256": p["base_sha256"], "text": GAP.sub("Der Mietvertrag ist als Geschäftsmiete nicht versichert.", p["text"])}
                 for p in draft["parts"] if GAP.search(p["text"])]
        saved = self.client.put(f"/api/cases/{self.case}/drafts/{draft['form']}", json={"parts": parts, "parent_id": draft.get("draft_id"), "op_id": "op-fill-1"})
        self.assertEqual(saved.status_code, 200, saved.text)
        draft = self.view()["draft"]
        refused = self.approve(draft, "op-approve-1")
        self.assertEqual(refused.status_code, 422)
        self.assertIn("Deckungsablehnung: Eingang und Prüfung (noch nicht freigegeben)", refused.json()["detail"])
        for key in refusal.element_ids()[:-1]:
            self.assertEqual(self.client.post(f"/api/review/cover/{key.split(':', 1)[1]}", json={"mark": "geprueft"}).status_code, 201)
        self.assertEqual(self.approve(draft, "op-approve-2").status_code, 422)  # one part is still not released
        last = refusal.element_ids()[-1]
        self.assertEqual(self.client.post(f"/api/review/cover/{last.split(':', 1)[1]}", json={"mark": "geprueft"}).status_code, 201)
        self.assertEqual(self.view()["completion"]["held_now"], [])
        approved = self.approve(self.view()["draft"], "op-approve-3")
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertTrue(set(refusal.element_ids()) <= set(approved.json()["approval"]["relies"]))  # the approval names what it rests on

    def test_the_wording_is_a_review_element_with_its_open_question(self):
        detail = self.client.get("/api/review/deckung").json()
        group = next(g for g in detail["groups"] if g["id"] == "ablehnung")
        self.assertEqual([e["key"] for e in group["elements"]], refusal.element_ids())
        asked = next(e for e in group["elements"] if e["key"].endswith("ablehnung.erneut"))["questions"]
        self.assertTrue(any("Rechtsbehelfe" in q for q in asked))


if __name__ == "__main__":
    unittest.main()

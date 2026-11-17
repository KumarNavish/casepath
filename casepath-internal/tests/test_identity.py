"""A case's identity: its reference number (carried, proposed from its own files, or set by a person), its owner and the
deputy; the list's rows carry them so the handler finds a case by its number and sees «Meine». Synthetic, no model."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import letters
from casepath.read.extract import extract
from casepath.web.app import create_app

MAIL = ("From: Lea Brunner <lea.brunner@example.ch>\r\nTo: schaden@example-rechtsschutz.ch\r\nDate: Mon, 10 Feb 2025 09:14:00 +0100\r\n"
        "Subject: Ihr Fall 4321.7000.0042\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nGuten Tag\r\n\r\nIch melde einen Schimmelbefall.\r\n").encode()


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "catalogue").mkdir()
        self.apps = []
        self.a = self.client("A. Handler")

    def client(self, user):
        app = create_app(load_settings({"CASEPATH_DATA_DIR": str(self.root / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(self.root / "catalogue"),
                                        "CASEPATH_DEV_USER": user}), model_factory=lambda: None)
        self.apps.append(app)
        return TestClient(app)

    def tearDown(self):
        for app in self.apps:
            app.state.runs.shutdown()
            app.state.store.close()
        self.directory.cleanup()

    def case(self, title="Schimmel im Bad", mail=MAIL):
        created = self.a.post("/api/cases", json={"title": title, "intake": {"synthetic": True}}).json()
        if mail:
            store = self.apps[0].state.store
            row = extract("Meldung.eml", "message/rfc822", mail)
            store.add_file(created["id"], "Meldung.eml", row["media_type"], row["kind"], mail, row, "A. Handler")
        return created["id"]

    def test_a_reference_in_the_file_is_proposed_taken_over_and_used(self):
        cid = self.case()
        shown = self.a.get(f"/api/cases/{cid}").json()["case"]
        self.assertEqual((shown["reference"], shown["reference_set"], shown["reference_proposed"]["value"], shown["reference_proposed"]["name"]),
                         (None, False, "4321.7000.0042", "Meldung.eml"))
        self.assertEqual((shown["owner"], shown["deputy"], shown["mine"]), ("A. Handler", None, True))  # who created it is responsible
        r = self.a.put(f"/api/cases/{cid}/identity", json={"reference": " 4321.7000.0042 "})
        self.assertEqual((r.status_code, r.json()["case"]["reference"], r.json()["case"]["reference_set"]), (200, "4321.7000.0042", True))
        row = next(c for c in self.a.get("/api/cases").json()["cases"] if c["id"] == cid)
        self.assertEqual((row["reference"], row["owner"], row["mine"]), ("4321.7000.0042", "A. Handler", True))
        self.assertEqual(letters._reference(self.apps[0].state.store.get_case(cid)).group(0), "4321.7000.0042")  # the letter's «Unsere Referenz»
        events = [(e["kind"], e.get("text"), e["expert"]) for e in self.apps[0].state.store.list_case_events(cid)]
        self.assertEqual(events, [("case.reference", "4321.7000.0042", "A. Handler")])
        self.assertEqual(len(self.apps[0].state.store.list_case_events(cid)), 1)
        self.a.put(f"/api/cases/{cid}/identity", json={"reference": "4321.7000.0042"})  # the same again: nothing is logged
        self.assertEqual(len(self.apps[0].state.store.list_case_events(cid)), 1)

    def test_one_number_is_one_case(self):
        first, second = self.case(), self.case("Zweite Meldung", mail=None)
        self.a.put(f"/api/cases/{first}/identity", json={"reference": "4321.7000.0042"})
        r = self.a.put(f"/api/cases/{second}/identity", json={"reference": "4321.7000.0042"})
        self.assertEqual((r.status_code, r.json()["detail"]), (409, "Diese Referenz trägt bereits der Fall «Schimmel im Bad»."))
        self.assertIsNone(self.a.get(f"/api/cases/{second}").json()["case"]["reference"])

    def test_owner_and_deputy_decide_whose_case_it_is(self):
        cid = self.case()
        b = self.client("B. Kollegin")
        row = lambda client: next(c for c in client.get("/api/cases").json()["cases"] if c["id"] == cid)
        self.assertFalse(row(b)["mine"])
        r = self.a.put(f"/api/cases/{cid}/identity", json={"deputy": "B. Kollegin"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((row(b)["mine"], row(b)["deputy"], row(self.a)["mine"]), (True, "B. Kollegin", True))
        self.a.put(f"/api/cases/{cid}/identity", json={"owner": "B. Kollegin", "deputy": ""})
        self.assertEqual((row(self.a)["mine"], row(b)["owner"], row(b)["deputy"]), (False, "B. Kollegin", None))
        kinds = [e["kind"] for e in self.apps[0].state.store.list_case_events(cid)]
        self.assertEqual(kinds, ["case.assigned", "case.assigned"])

    def test_a_number_in_the_title_still_counts_and_a_set_one_stands_over_it(self):
        cid = self.case("Dossier 4321.5555.0001 Schimmel", mail=None)
        shown = self.a.get(f"/api/cases/{cid}").json()["case"]
        self.assertEqual((shown["reference"], shown["reference_set"], shown.get("reference_proposed")), ("4321.5555.0001", False, None))
        self.a.put(f"/api/cases/{cid}/identity", json={"reference": "S-2026-17"})
        self.assertEqual(self.a.get(f"/api/cases/{cid}").json()["case"]["reference"], "S-2026-17")


class OtherCaseTests(unittest.TestCase):
    """A file that names another case's reference number and not this case's is said on the page before it is relied on."""

    def test_a_mail_for_another_case_is_named_and_a_file_of_this_case_is_not(self):
        import tempfile
        from fastapi.testclient import TestClient
        from casepath.config import load_settings
        from casepath.web.app import create_app
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": folder, "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None))
            cid = client.post("/api/cases", json={"title": "Fall"}).json()["id"]
            client.put(f"/api/cases/{cid}/identity", json={"reference": "4321.7000.0042"})
            client.post(f"/api/cases/{cid}/files", files={"file": ("eigene.txt", "Betreff: Schadenfall 4321.7000.0042\nText".encode(), "text/plain")})
            client.post(f"/api/cases/{cid}/files", files={"file": ("ohne.txt", b"Ein Text ohne Referenz", "text/plain")})
            self.assertEqual(client.get(f"/api/cases/{cid}").json()["case"]["other_references"], [])
            other = client.post(f"/api/cases/{cid}/files", files={"file": ("fremd.txt", "Betreff: Schadenfall 4321.7000.0099\nText".encode(), "text/plain")}).json()
            rows = client.get(f"/api/cases/{cid}").json()["case"]["other_references"]
            self.assertEqual([(r["name"], r["reference"]) for r in rows], [("fremd.txt", "4321.7000.0099")])
            self.assertEqual(rows[0]["file"], other["id"])

    def test_the_page_says_it_on_the_file_and_above_the_step(self):
        from pathlib import Path
        script = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text(encoding="utf-8")
        self.assertIn("data-other-reference>", script)
        self.assertIn("function otherReferenceNote()", script)
        self.assertIn("const first = bar.decision ? T(`Decide first: ${bar.decision}`", script)  # a follow-up is not approved past an open decision


if __name__ == "__main__":
    unittest.main()

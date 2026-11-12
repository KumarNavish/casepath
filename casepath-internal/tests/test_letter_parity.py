"""The server's A1 letter is the browser's, text for text (one mechanism), apart from two deliberate lines: the greeting
("Sehr geehrte Damen und Herren" instead of an empty "…") and the closing sentence every Protekta letter carries."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import tests.test_app as app_tests
from tests.test_handler_workflow import intake

JS = Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js"
RUNNER = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (name) => { const i = src.indexOf(`function ${name}(`); let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; if (src[k] === "}" && --d === 0) return src.slice(i, k + 1); } };
const itemLine = src.split("\n").find((l) => l.startsWith("const item = "));
const T = (en, de) => de;
const S = { data: JSON.parse(fs.readFileSync(process.argv[2], "utf8")) };
eval(itemLine + "\n" + grab("askNow") + "\n" + grab("requestDraft") + "\nprocess.stdout.write(requestDraft(S.data.evaluation));");
"""


def deliberate(text):
    """The two lines that differ on purpose, brought to one wording."""
    closing = "Für Ihre Kenntnisnahme und Bemühungen danken wir Ihnen bestens. Bei Fragen stehen wir Ihnen gerne zur Verfügung."
    return text.replace("Sehr geehrte/r …", "Sehr geehrte Damen und Herren").replace(closing + "\n\n", "").strip()


@unittest.skipUnless(shutil.which("node"), "the browser's letter code runs in node")
class LetterParityTests(unittest.TestCase):
    def setUp(self):
        self.app = app_tests.AppTests()
        self.app.setUp()
        catalogue = Path(self.app.directory.name) / "catalogue"
        catalogue.mkdir()
        (catalogue / "osm-mold.json").write_text(json.dumps(intake()))
        self.client = self.app.client(CASEPATH_WORKFLOW_CATALOGUE=str(catalogue))

    def tearDown(self):
        self.app.tearDown()

    def browser(self, case_id):
        data = self.client.get(f"/api/cases/{case_id}").json()
        data["caseEvents"] = self.client.get(f"/api/cases/{case_id}/events").json()["events"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
        out = subprocess.run(["node", "-e", RUNNER, str(JS), f.name], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr[-600:])
        out = out.stdout
        return out, data["draft"]["text"]

    def case(self):
        case = self.client.post("/api/cases", json={"title": "Schimmel 1234.5678.9012"}).json()
        self.client.post(f"/api/cases/{case['id']}/files", files={"file": ("message.eml", app_tests.EMAIL, "message/rfc822")})
        store = self.client.app.state.store
        run = store.create_run(case["id"], "dev")
        fact = lambda f, v: {"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": []}
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"),
                                           fact("will_reduktion", True)],
                                 "documents": [], "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}})
        return case

    def test_the_server_letter_is_the_browsers_for_a_prepared_case(self):
        case = self.case()
        browser, server = self.browser(case["id"])
        self.assertEqual(deliberate(server), deliberate(browser))

    def test_and_after_the_handler_unticks_one_line_and_adds_one_document(self):
        case = self.case()
        shown = self.client.get(f"/api/cases/{case['id']}").json()
        first = next(i for i in shown["items"] if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present")
        self.client.post(f"/api/cases/{case['id']}/events", json={"kind": "letter.line", "item_id": first["item_id"], "fields": {"included": False, "reason": "3"}})
        self.client.post(f"/api/cases/{case['id']}/edits", json={"op": "add_document", "args": {"title": "Wohnungsabnahmeprotokoll", "why": "Steht nicht in den Akten",
                                                                                            "step": "klaeren"}, "reason": "", "reason_code": "2", "recheck": False})
        browser, server = self.browser(case["id"])
        self.assertEqual(deliberate(server), deliberate(browser))
        self.assertIn("Wohnungsabnahmeprotokoll", server)
        self.assertNotIn(f"– {first['label']['de']}\n", server)


if __name__ == "__main__":
    unittest.main()

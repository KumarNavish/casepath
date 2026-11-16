"""Review in the letter (docs/HANDLER_WORK.md): a letter says how much of the reviewed content it rests on is checked, a
jurist reviews those elements beside the real letter, and the elements approved letters carry are listed by use."""
from pathlib import Path
import unittest

from tests.test_knowledge_gate import Gate

SCRIPT = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()


class LetterReviewTests(Gate):
    def mark(self, key, mark="geprueft", comment=""):
        file, element = key.split(":", 1)
        r = self.client.post(f"/api/review/{file}/{element}", json={"mark": mark, "comment": comment})
        self.assertEqual(r.status_code, 201, r.text)

    def test_a_letter_counts_the_elements_it_rests_on_and_a_jurist_marks_them_beside_it(self):
        case = self.prepared("Fall A (synthetisch)")
        view = self.client.get(f"/api/cases/{case['id']}").json()
        reviewed = view["completion"]["reviewed"]
        self.assertGreater(reviewed["of"], 0)
        self.assertEqual((reviewed["checked"], reviewed["held"], reviewed["practice"]), (0, 0, 1))  # one need comes from «Wissen», released there
        page = self.client.get(f"/api/cases/{case['id']}/letter-review").json()
        self.assertEqual((page["kind"], page["case"], page["letter"], page["may_review"]), ("letter", case["id"], view["draft"]["text"], True))
        elements = [el for g in page["groups"] for el in g["elements"]]
        self.assertEqual((len(elements), page["status"]["counts"]["total"], page["status"]["label"]),
                         (reviewed["of"], reviewed["of"], f"0 von {reviewed['of']} Bausteinen geprüft"))
        self.assertTrue(all(el["title"] and el["sha256"] and el["state"] == "offen" for el in elements))  # each as the catalogue holds it, to read and mark
        self.assertTrue(any(el["lines"] for el in elements))
        self.mark(elements[0]["key"])
        self.mark(elements[1]["key"], "frage", "Gilt das auch bei Untermiete?")
        self.assertEqual(self.client.get(f"/api/cases/{case['id']}").json()["completion"]["reviewed"],
                         {"of": reviewed["of"], "checked": 1, "held": 1, "practice": 1})
        for el in elements[1:]:
            self.mark(el["key"])
        page = self.client.get(f"/api/cases/{case['id']}/letter-review").json()
        self.assertEqual((page["status"]["state"], page["status"]["label"]), ("freigegeben", f"{reviewed['of']} von {reviewed['of']} Bausteinen geprüft"))
        # another case of the area rests on the same elements: its letter is checked too, without a second review
        other = self.prepared("Fall B (synthetisch)")
        self.assertEqual(self.client.get(f"/api/cases/{other['id']}").json()["completion"]["reviewed"]["checked"], reviewed["of"])

    def test_the_elements_approved_letters_rest_on_are_listed_by_use_the_unchecked_first(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        self.assertEqual(self.client.get("/api/review/by-use").json(), {"rows": [], "elements": 0, "checked": 0})  # nothing approved yet
        first = self.approve(a["id"], "op-use-1")
        self.approve(b["id"], "op-use-2")
        use = self.client.get("/api/review/by-use").json()
        legal = [k for k in first["relies"] if ".k-" not in k]  # a need added by a Knowledge item is released under «Wissen», not here
        self.assertEqual((use["elements"], use["checked"], sorted(r["key"] for r in use["rows"])), (len(legal), 0, sorted(legal)))
        self.assertTrue(all((r["letters"], r["sent"], r["cases"]) == (2, 0, 2) and r["case"] in (a["id"], b["id"]) for r in use["rows"]))
        self.mark(use["rows"][0]["key"])
        after = self.client.get("/api/review/by-use").json()
        self.assertEqual((after["checked"], after["rows"][-1]["key"], after["rows"][-1]["state"]), (1, use["rows"][0]["key"], "geprueft"))

    def test_a_case_without_a_letter_and_a_study_copy_have_no_letter_review(self):
        case = self.store.create_case("Leer (synthetisch)", {"synthetic": True}, "dev")
        self.assertIn(self.client.get(f"/api/cases/{case['id']}/letter-review").status_code, (404, 409))

    def test_the_screen_links_the_letter_to_its_review_and_lists_by_use(self):
        self.assertIn("#/knowledge/brief/", SCRIPT)
        self.assertIn("Dieser Brief: ${r.checked} von ${r.of} Bausteinen geprüft", SCRIPT)
        self.assertIn("Zuerst prüfen: in freigegebenen Briefen verwendet", SCRIPT)
        self.assertIn('if (parts[0] === "knowledge" && parts[1] === "brief" && parts[2])', SCRIPT)


if __name__ == "__main__":
    unittest.main()

"""A jurist's review of the legal content (casepath/process/review.py): every element a handler or customer relies on with
a stable id and a content hash; marks stored and logged; an area released only once every element is «geprüft»; a mark
lapsing when its element changes; what a mark «Änderung nötig» changes in a case; the handler's line; the export; who may
mark (CASEPATH_REVIEWERS)."""
import copy
import json
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient

from casepath.agents import core
from casepath.config import load_settings
from casepath.parity import manifest
from casepath.process import area, cover, customer_letters, letters, review
from casepath.process.items import build_items
from casepath.process.workflows import CatalogueError
from casepath.quality.auswertung import _run_seconds
from casepath.web.app import create_app
from casepath.web.store import CaseStore
from tests.test_handler_workflow import fact

MODEL = review.Model.load(today=date(2026, 11, 15))


def mark(key, kind="geprueft", model=MODEL, at="2026-11-15T09:00:00+00:00", reviewer="Jurist A"):
    return {"file": key.split(":")[0], "element": key.split(":", 1)[1], "content_sha256": model.elements[key]["sha256"], "mark": kind,
            "comment": "" if kind == "geprueft" else "bitte prüfen", "suggestion": "", "reviewer": reviewer, "at": at}


def dismissal(review_marks=None):
    """A dismissal during sick leave at the first request: the hint on the blocking period holds, the deadline for the
    objection is computed, two templates for the customer's own letters apply."""
    wf = area.workflow("arbeit-kuendigung")
    result = {"facts": [fact("rechtsgebiet", "Arbeitsrecht / Kündigung"), fact("arbeitsunfaehig", True), fact("arbeitsende", "2026-12-31"),
                        fact("grund_genannt", False)], "documents": [], "brief": {"request": "Kündigung erhalten.", "parties": [], "timeline": []}}
    state = core.evaluate(wf, [], [], result, "c")
    return {i["item_id"]: i for i in build_items(state, result, [], None, review_marks)}


class ElementTests(unittest.TestCase):
    def test_every_element_has_an_id_from_the_data_and_a_hash_of_its_content(self):
        again = review.Model.load(today=date(2026, 11, 15))
        self.assertEqual({k: e["sha256"] for k, e in MODEL.elements.items()}, {k: e["sha256"] for k, e in again.elements.items()})
        for key in ("arbeit-kuendigung:frage.kuendigung_erhalten", "arbeit-kuendigung:unterlage.arztzeugnis", "arbeit-kuendigung:hinweis.sperrfrist",
                    "arbeit-kuendigung:kernpunkt.sperrfrist", "arbeit-kuendigung:frist.einsprache_kuendigung", "arbeit-kuendigung:rahmen.demand",
                    "arbeit-kuendigung:vorlage.einsprache", "backbone:zaehlung.or", "backbone:zaehlung.feiertage", "backbone:schreiben.A11_teilablehnung",
                    "cover:punkt.wartefrist", "cover:zuordnung.arbeit", "cover:ursache", "cover:frage.ursache_datum", "cover:regel.leistungseinstellung",
                    "cover:regel.erstkontakt", "cover:schreiben.A5_aussichtslos.begruendung", "cover:schreiben.A12_mitwirkung"):
            self.assertIn(key, MODEL.elements)
            self.assertRegex(MODEL.elements[key]["sha256"], r"^[0-9a-f]{64}$")
        rows = {r["id"]: r for r in MODEL.rows}
        self.assertEqual(len(rows), 21)  # 19 areas, the cover check, the letters with prescribed content
        self.assertEqual([g["id"] for g in rows["arbeit-kuendigung"]["groups"]],
                         ["fragen", "unterlagen", "hinweise", "kernpunkte", "fristen", "rahmen", "vorlagen", "berechnung"])
        self.assertEqual(rows["arbeit-kuendigung"]["groups"][-1]["keys"], ["backbone:zaehlung.or", "backbone:zaehlung.feiertage"])
        self.assertEqual(MODEL.status(rows["arbeit-zeugnis"], {})["counts"]["total"], 13)
        for row in MODEL.rows:  # every area has elements, and an id appears once in its row
            keys = [k for g in row["groups"] for k in g["keys"]]
            self.assertTrue(keys and len(keys) == len(set(keys)), row["id"])

    def test_each_element_shows_its_passage_and_the_official_source(self):
        deadline = MODEL.elements["arbeit-kuendigung:frist.einsprache_kuendigung"]
        self.assertEqual(deadline["law"][0]["cite"], "Art. 336b Abs. 1 OR")
        self.assertTrue(deadline["law"][0]["url"].startswith("https://fedlex.data.admin.ch/filestore/"))
        self.assertIn("längstens bis zum Ende der Kündigungsfrist", deadline["law"][0]["passage"])
        self.assertIn(("Letzter Tag", "wird nicht auf den nächsten Werktag verschoben"), [(l["label"], l["text"]) for l in deadline["lines"]])
        clause = MODEL.elements["cover:punkt.wartefrist"]["law"]
        self.assertTrue(any(r["url"] == "https://oiv.protekta.ch/de/avb/RSP-01-2026/" for r in clause))
        self.assertTrue(any("drei Monate Wartefrist" in r["passage"] for r in clause))  # the product page, named as such
        template = next(l for l in MODEL.elements["arbeit-kuendigung:vorlage.einsprache"]["lines"] if l["label"] == "Text")
        self.assertIn("Ich erachte diese Kündigung als missbräuchlich", template["text"])
        self.assertNotIn("[einsetzen: Ihre Adresse]", template["text"])  # the frame every template shares is left out

    def test_the_open_questions_stand_beside_the_element_they_are_about(self):
        questions = lambda key: " ".join(MODEL.elements[key]["questions"])
        self.assertIn("Schlusssatz", questions("cover:regel.leistungseinstellung"))
        self.assertIn("beauftragte Kanzlei", questions("cover:regel.leistungseinstellung"))
        self.assertIn("Produktseite", questions("cover:punkt.wartefrist"))
        self.assertIn("C Ziff. 1", questions("cover:zuordnung.arbeit"))
        self.assertIn("Art. 169 Abs. 2 AVO", questions("cover:schreiben.A5_aussichtslos.verfahren"))
        self.assertIn("Honorarnote", questions("backbone:schreiben.A11_teilablehnung"))
        self.assertIn("Art. 142 Abs. 2 ZPO", questions("backbone:zaehlung.zpo"))
        self.assertIn("Feiertage", questions("backbone:zaehlung.feiertage"))
        self.assertIn("missbräuchlich", questions("arbeit-kuendigung:vorlage.einsprache"))
        self.assertIn("Gesetzesartikel", questions("vertrag-kauf:vorlage.maengelanzeige"))
        self.assertIn("Hinterlegung", questions("mietmangel-handler:vorlage.maengelruege"))
        self.assertIn("Art. 367 Abs. 1bis OR", questions("werkvertrag-bau:frist.ruege_ablieferung"))
        self.assertIn("Wochenende", questions("werkvertrag-bau:frist.bauhandwerkerpfand"))
        self.assertIn("Art. 7 ZGB", questions("erbrecht:frist.ausschlagung_gesetzlich"))
        self.assertIn("Kenntnis", questions("schaden-unfall:frist.verjaehrung_relativ"))
        self.assertIn("Art. 57a IVG", questions("sozialversicherung:frist.einwand_vorbescheid"))
        self.assertIn("Betreibungsferien", questions("betreibung-schuldner:frist.rechtsvorschlag"))
        self.assertIn("Art. 336b Abs. 1 OR", questions("arbeit-kuendigung:frist.einsprache_kuendigung"))
        self.assertIn("nach Absprache", questions("vertrag-darlehen:frage.termin_vereinbart"))
        self.assertIn("Art. 318 OR", questions("vertrag-darlehen:frist.rueckzahlung"))
        self.assertIn("sieben abgeschlossenen Dossiers", " ".join(next(r for r in MODEL.rows if r["id"] == "mietmangel-handler")["questions"]))
        # the jurist's questions stay on the review screen: a case's process carries the area's own, as before
        self.assertEqual(area.workflow("mietmangel-handler")["open_questions"], [])
        self.assertEqual(len(area.workflow("erbrecht")["open_questions"]), 2)

    def test_an_open_question_about_an_unknown_element_is_refused(self):
        bb, module = area.load(area.AREAS / "backbone.json"), area.load(area.AREAS / "arbeit-zeugnis.json")
        area.compose(bb, module)
        for about in ("frist.nirgends", ["hinweis.jederzeit", "vorlage.keine"], ""):
            bad = copy.deepcopy(module)
            bad["open_questions"] = [{"text": "Stimmt das?", "about": about}]
            with self.subTest(about=about), self.assertRaises(CatalogueError):
                area.compose(bb, bad)
        data = copy.deepcopy(cover.data())
        data["open_questions"] = [{"text": "Stimmt das?", "about": "punkt.nirgends"}]
        with self.assertRaises(CatalogueError):
            cover.validate(data)


class MarkTests(unittest.TestCase):
    def test_marks_are_stored_and_each_is_an_event_in_the_log(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CaseStore(directory)
            first = store.add_review("arbeit-zeugnis", "hinweis.jederzeit", "a" * 64, "aenderung", "Wortlaut", "Neuer Wortlaut", "Jurist A")
            store.add_review("arbeit-zeugnis", "hinweis.jederzeit", "a" * 64, "geprueft", "", "", "Jurist B")
            latest = store.latest_reviews()["arbeit-zeugnis:hinweis.jederzeit"]
            self.assertEqual((latest["mark"], latest["reviewer"]), ("geprueft", "Jurist B"))  # the latest mark is the element's
            self.assertEqual(len(store.list_reviews("arbeit-zeugnis", "hinweis.jederzeit")), 2)  # never updated: each mark kept
            events = store.list_workspace_events("review.marked")
            self.assertEqual(len(events), 2)
            self.assertEqual({k: events[0][k] for k in ("file", "element", "mark", "comment", "suggestion", "reviewer", "content_sha256", "review_id")},
                             {"file": "arbeit-zeugnis", "element": "hinweis.jederzeit", "mark": "aenderung", "comment": "Wortlaut",
                              "suggestion": "Neuer Wortlaut", "reviewer": "Jurist A", "content_sha256": "a" * 64, "review_id": first["id"]})
            with self.assertRaises(ValueError):
                store.add_review("arbeit-zeugnis", "hinweis.jederzeit", "a" * 64, "egal", "", "", "Jurist A")
            store.close()

    def test_an_area_is_released_only_when_every_element_is_checked(self):
        row = MODEL.row("arbeit-zeugnis")
        keys = MODEL.keys(row)
        self.assertEqual(MODEL.status(row, {})["label"], "aus dem Gesetz abgeleitet, noch nicht freigegeben")
        marks = {k: mark(k) for k in keys[:-1]}
        status = MODEL.status(row, marks)
        self.assertEqual((status["state"], status["label"]), ("in_pruefung", f"in Prüfung ({len(keys) - 1} von {len(keys)} geprüft)"))
        marks[keys[-1]] = mark(keys[-1], "frage")  # a question open: not released
        self.assertEqual(MODEL.status(row, marks)["state"], "in_pruefung")
        self.assertEqual(MODEL.status(row, marks)["counts"]["frage"], 1)
        marks[keys[-1]] = mark(keys[-1], at="2026-11-16T08:30:00+00:00", reviewer="Jurist B")
        status = MODEL.status(row, marks)
        self.assertEqual((status["state"], status["label"]), ("freigegeben", "freigegeben am 16.11.2026 · Jurist B, Jurist A"))

    def test_a_mark_lapses_when_the_content_of_its_element_changes(self):
        modules = review.area_modules()
        changed = copy.deepcopy(modules)
        changed["arbeit-zeugnis"]["hints"][0]["text"] += " Bitte verlangen Sie es schriftlich."
        later = review.Model(changed, area.backbone(), cover.data(), date(2026, 11, 15))
        row = later.row("arbeit-zeugnis")
        marks = {k: mark(k) for k in MODEL.keys(MODEL.row("arbeit-zeugnis"))}  # every element checked on the earlier release
        self.assertEqual(MODEL.status(MODEL.row("arbeit-zeugnis"), marks)["state"], "freigegeben")
        key = "arbeit-zeugnis:hinweis.jederzeit"
        self.assertEqual(later.state(key, marks[key]), "geaendert")
        self.assertEqual(review.STATES["geaendert"], "geändert seit Prüfung")
        status = later.status(row, marks)
        self.assertEqual((status["state"], status["counts"]["offen"], status["counts"]["geaendert"]), ("in_pruefung", 1, 1))
        self.assertNotIn(key, later.current(marks))  # a lapsed mark changes nothing in a case
        self.assertNotEqual(later.elements[key]["sha256"], MODEL.elements[key]["sha256"])
        self.assertEqual(later.elements["arbeit-zeugnis:hinweis.jederzeit"]["key"], key)  # the id stays


class CaseTests(unittest.TestCase):
    def test_change_needed_offers_a_hint_point_or_template_unticked_and_a_deadline_still_shows(self):
        before = dismissal()
        self.assertEqual(before["hint:sperrfrist"]["stated_as"], "established")
        self.assertEqual(before["hint:kp-begruendung"]["stated_as"], "established")
        keys = ["arbeit-kuendigung:hinweis.sperrfrist", "arbeit-kuendigung:kernpunkt.begruendung", "arbeit-kuendigung:kernpunkt.sperrfrist",
                "arbeit-kuendigung:frist.einsprache_kuendigung", "arbeit-kuendigung:vorlage.begruendung"]
        after = dismissal(MODEL.current({k: mark(k, "aenderung") for k in keys}))
        for item_id in ("hint:sperrfrist", "hint:kp-begruendung"):  # offered, never ticked by default, with its quiet mark
            self.assertEqual((after[item_id]["stated_as"], after[item_id]["review"]), ("put_to_handler", "in Prüfung"))
        deadline = after["deadline:einsprache_kuendigung"]  # a deadline is never hidden or unticked by a mark
        self.assertEqual((deadline["value"], deadline["stated_as"], deadline["review"]), ("2026-12-31", "computed", "in Prüfung"))
        self.assertEqual(before["deadline:einsprache_kuendigung"]["value"], deadline["value"])
        self.assertEqual(after["key_point:sperrfrist"]["review"], "in Prüfung")
        self.assertEqual(after["customer_letter:begruendung"]["review"], "in Prüfung")
        hints = lambda items: letters.context({"id": "c", "title": "t"}, list(items.values()), [], {"due": "2026-12-01"})["hinweise"]
        self.assertIn("Sperrfrist", hints(before))
        self.assertNotIn("Sperrfrist, etwa bei Krankheit", hints(after))
        self.assertNotIn("schriftlich begründet (Art. 335 Abs. 2 OR)", hints(after))
        self.assertIn("Die Frist für die schriftliche Einsprache gegen eine missbräuchliche Kündigung endet am 31.12.2026 (Art. 336b Abs. 1 OR).", hints(after))
        in_case = lambda items: letters.context({"id": "c", "title": "t"}, list(items.values()), [], {"due": "2026-12-01"})["im_fall"]
        self.assertIn("Art. 336c Abs. 2 OR", in_case(before))  # the assessment states a point by itself only while no change is asked
        self.assertNotIn("Art. 336c Abs. 2 OR", in_case(after))
        refer = lambda items: customer_letters.referrals(list(items.values()), "A5")
        self.assertEqual((len(refer(before)), len(refer(after))), (2, 1))
        # «geprüft» or «Frage» changes nothing a case shows
        checked = dismissal(MODEL.current({k: mark(k, "frage") for k in keys}))
        self.assertEqual({k: (i.get("stated_as"), i.get("review")) for k, i in checked.items()}, {k: (i.get("stated_as"), i.get("review")) for k, i in before.items()})

    def test_a_counting_rule_marked_for_change_marks_every_deadline_counted_by_it(self):
        after = dismissal(MODEL.current({"backbone:zaehlung.or": mark("backbone:zaehlung.or", "aenderung")}))
        self.assertEqual([after[k].get("review") for k in ("deadline:einsprache_kuendigung", "deadline:klage_entschaedigung")], ["in Prüfung"] * 2)
        self.assertEqual(after["deadline:klage_entschaedigung"]["value"], "2027-06-29")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory, self.apps = tempfile.TemporaryDirectory(), []

    def tearDown(self):
        for app in self.apps:
            app.state.runs.shutdown()
            app.state.store.close()
        self.directory.cleanup()

    def client(self, **env):
        settings = load_settings({"CASEPATH_DATA_DIR": self.directory.name, "CASEPATH_DEV_USER": "Jurist A", **env})
        self.apps.append(create_app(settings, model_factory=lambda: None))
        return TestClient(self.apps[-1])

    def certificate_case(self, client):
        store = client.app.state.store
        case = store.create_case("Arbeitszeugnis Beispiel (synthetisch)", {"synthetic": True}, "Jurist A")
        run = store.create_run(case["id"], "Jurist A")
        store.update_run(run["id"], status="completed", workflow_id="arbeit-zeugnis", finished_at="2026-11-15T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Arbeitsrecht / Arbeitszeugnis")], "documents": [],
                                 "brief": {"request": "Ein Zeugnis ist zu berichtigen.", "parties": [], "timeline": []}})
        return case["id"]

    def mark(self, client, key, kind="geprueft", **body):
        file, element = key.split(":", 1)
        return client.post(f"/api/review/{file}/{element}", json={"mark": kind, **body})

    def test_the_handler_sees_the_area_not_released_in_review_or_released(self):
        client = self.client()
        case_id = self.certificate_case(client)
        label = lambda: client.get(f"/api/cases/{case_id}").json()["area_review"]
        self.assertEqual(label(), {"state": "offen", "label": "aus dem Gesetz abgeleitet, noch nicht freigegeben", "title": "Arbeitszeugnis"})
        row = client.get("/api/review/arbeit-zeugnis").json()
        keys = [e["key"] for g in row["groups"] for e in g["elements"]]
        self.assertEqual(self.mark(client, keys[0], sha256=row["groups"][0]["elements"][0]["sha256"]).status_code, 201)
        self.assertEqual(label()["label"], f"in Prüfung (1 von {len(keys)} geprüft)")
        for key in keys[1:]:
            last = self.mark(client, key)
            self.assertEqual(last.status_code, 201)
        today = review._day(last.json()["mark"]["at"])  # the release's day as the product states it: the Swiss day, at any hour
        self.assertEqual(label(), {"state": "freigegeben", "label": f"freigegeben am {today} · Jurist A", "title": "Arbeitszeugnis"})
        overview = {r["id"]: r for r in client.get("/api/review").json()["rows"]}
        self.assertEqual(overview["arbeit-zeugnis"]["status"]["state"], "freigegeben")
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", "aenderung", comment="Arbeitsbestätigung erwähnen").status_code, 201)
        self.assertEqual(label()["label"], f"in Prüfung ({len(keys) - 1} von {len(keys)} geprüft)")
        hint = next(i for i in client.get(f"/api/cases/{case_id}").json()["items"] if i["item_id"] == "hint:jederzeit")
        self.assertEqual((hint["stated_as"], hint["review"]), ("put_to_handler", "in Prüfung"))

    def test_a_mark_needs_a_known_element_its_content_as_seen_and_a_comment_for_a_change_or_a_question(self):
        client = self.client()
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.nirgends").status_code, 404)
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", sha256="0" * 64).status_code, 409)
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", "frage").status_code, 422)
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", "egal").status_code, 422)
        self.assertEqual(self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", "frage", comment="Auch für Lernende?").status_code, 201)

    def test_the_requested_changes_export_without_case_content(self):
        client = self.client()
        self.certificate_case(client)
        self.mark(client, "arbeit-zeugnis:hinweis.jederzeit", "aenderung", comment="Arbeitsbestätigung erwähnen", suggestion="Ein Zeugnis kann jederzeit …")
        self.mark(client, "cover:punkt.wartefrist", "frage", comment="Gilt die Produktseite?")
        self.mark(client, "arbeit-zeugnis:unterlage.zeugnis")
        items = client.get("/api/review/export").json()["items"]
        self.assertEqual([(i["element"], i["mark"], i["comment"], i["suggestion"]) for i in items],
                         [("arbeit-zeugnis:hinweis.jederzeit", "aenderung", "Arbeitsbestätigung erwähnen", "Ein Zeugnis kann jederzeit …"),
                          ("cover:punkt.wartefrist", "frage", "Gilt die Produktseite?", "")])
        text = client.get("/api/review/export", params={"format": "md"}).text
        for expected in ("`arbeit-zeugnis:hinweis.jederzeit`", "Kommentar: Arbeitsbestätigung erwähnen", "Vorschlag: Ein Zeugnis kann jederzeit …",
                         "## Frage", "`cover:punkt.wartefrist`"):
            self.assertIn(expected, text)
        pack = client.get("/api/review/arbeit-zeugnis/pruefpaket")
        self.assertEqual(pack.status_code, 200)
        self.assertIn("Amtliche Quellen", pack.text)
        self.assertIn("Art. 330a Abs. 1 OR", pack.text)
        for leaked in ("Arbeitszeugnis Beispiel", "Ein Zeugnis ist zu berichtigen"):  # no case content anywhere
            self.assertNotIn(leaked, text + json.dumps(items, ensure_ascii=False) + pack.text)

    def test_with_no_reviewers_named_every_signed_in_user_marks_with_some_only_they(self):
        open_ = self.client()
        self.assertEqual(open_.get("/api/me").json(), {"user": "Jurist A", "may_review": True})
        self.assertEqual(self.mark(open_, "arbeit-zeugnis:hinweis.jederzeit").status_code, 201)
        named = self.client(CASEPATH_DEV_USER="", CASEPATH_IDENTITY_HEADER="X-Forwarded-Email", CASEPATH_REVIEWERS="Anna.Muster@example.ch")
        anna, beat = {"X-Forwarded-Email": "anna.muster@example.ch"}, {"X-Forwarded-Email": "beat.beispiel@example.ch"}
        self.assertEqual(named.get("/api/me", headers=anna).json()["may_review"], True)
        self.assertEqual(named.get("/api/me", headers=beat).json()["may_review"], False)
        body = {"mark": "geprueft"}
        self.assertEqual(named.post("/api/review/arbeit-zeugnis/hinweis.jederzeit", json=body, headers=beat).status_code, 403)
        self.assertEqual(named.post("/api/review/arbeit-zeugnis/hinweis.jederzeit", json=body, headers=anna).status_code, 201)
        self.assertFalse(named.get("/api/review", headers=beat).json()["may_review"])
        self.assertEqual(named.get("/api/review/arbeit-zeugnis", headers=beat).status_code, 200)  # reading stays open
        settings = load_settings({"CASEPATH_REVIEWERS": " Anna.Muster@example.ch, ben@example.ch "})
        self.assertEqual(settings.reviewers, frozenset({"anna.muster@example.ch", "ben@example.ch"}))
        self.assertEqual(load_settings({}).reviewers, frozenset())
        self.assertEqual(manifest(settings)["settings_not_default"]["reviewers"], "2 named users")  # never the names


class AuswertungTests(unittest.TestCase):
    def test_a_run_whose_finish_lies_before_its_start_has_no_duration(self):
        self.assertIsNone(_run_seconds({"created_at": "2026-11-15T10:00:00+00:00", "finished_at": "2026-11-12T10:00:00+00:00"}))
        self.assertEqual(_run_seconds({"created_at": "2026-11-15T10:00:00+00:00", "finished_at": "2026-11-15T10:01:30+00:00"}), 90)
        self.assertIsNone(_run_seconds({"created_at": "2026-11-15T10:00:00+00:00"}))


if __name__ == "__main__":
    unittest.main()

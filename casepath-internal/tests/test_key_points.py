"""What a handler sees first: the legal key points of the area, the customer's own questions, the decisions of the stage,
dates others set, the wording of a partly present need, the case's title and where it stands in the list."""
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from casepath.agents import core, team
from casepath.process import area, keypoints, letters
from casepath.process.items import build_items, further
from casepath.process.workflows import CatalogueError
from casepath.web import listing
from tests.scripted import ScriptedModel, report
from tests.test_areas import catalogue, intakes
from tests.test_handler_workflow import fact

FIXTURES = Path(__file__).parent / "fixtures"
KEY_CASES = {k: v for k, v in json.loads((FIXTURES / "areas" / "key_cases.json").read_text()).items() if not k.startswith("_")}
CASE_ROW = {"id": "case_k", "title": "Kündigung (synthetisch)", "intake": {}}


def run(case):
    """One case of key_cases.json through the scripted team: the same turns as any case (ScriptedModel fails on a call it
    was not given), so the customer's questions come with the brief, not from a model call of their own."""
    cite = lambda quote: [{"file": "f1", "quote": quote}]
    model = ScriptedModel([
        [*[("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
         report("claim_reader", request=case["request"], parties=[{"role": r, "name": n} for r, n in case["parties"]],
                questions=[{"question": q, "citations": cite(quote)} for q, quote in case["questions"]])],
        [*[("record_document", {"document": d, "status": "present", "files": ["f1"], "citations": cite(q), "note": ""}) for d, q in case["documents"]],
         report("document_finder")],
        *[[report("result_checker", answer="Vorbereitet.")]] * 3,
    ], routing=[{"fact": "rechtsgebiet", "value": case["routing"][0], "citations": cite(case["routing"][1])}])
    job = {"format": core.JOB, "case": CASE_ROW, "files": [{"id": "f1", "name": "Schadenmeldung.txt", "kind": "text", "media_type": "text/plain",
                                                             "sha256": "abc", "extraction": {"text": case["text"], "pages": None, "readable": True, "note": ""}}],
           "workflows": list(catalogue(*intakes("osm-mold", "osm-loan", "osm-fallback")).workflows), "knowledge": [], "edits": [], "options": {}}
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    wf = area.workflow(case["workflow"])
    state = core.evaluate(wf, [], [], outcome["result"], CASE_ROW["id"])
    return outcome["result"], state, build_items(state, outcome["result"])


def by_id(items):
    return {i["item_id"]: i for i in items}


class KeyPointDataTests(unittest.TestCase):
    def test_every_area_has_two_to_five_key_points_each_on_an_article_with_its_passage(self):
        rows = area.shipped()
        self.assertEqual(len(rows), 19)
        for w in rows:
            with self.subTest(area=w["id"]):
                self.assertTrue(2 <= len(w["key_points"]) <= 5)
                for p in w["key_points"]:
                    for ref in p["law"]:
                        row = w["law"][ref.split("#", 1)[1]]
                        self.assertTrue(row["passage"].strip() and row["verified"] is True, ref)  # each checked against the official text

    def test_the_validator_refuses_a_key_point_without_condition_article_or_statement(self):
        bb, module = area.load(area.AREAS / "backbone.json"), area.load(area.AREAS / "arbeit-kuendigung.json")
        area.compose(bb, module)
        for broken in ({"when": None}, {"when": True}, {"law": []}, {"law": ["law#nowhere"]}, {"statement": ""},
                       {"when": {"fact": "kein_fakt", "is": True}}):
            with self.subTest(broken=broken):
                bad = copy.deepcopy(module)
                bad["key_points"][0].update(broken)
                with self.assertRaises(CatalogueError):
                    area.compose(bb, bad)

    def test_a_point_applies_on_the_facts_is_a_question_while_its_fact_is_open_and_is_gone_when_it_fails(self):
        wf = area.workflow("arbeit-kuendigung")
        state = lambda value: {p["id"]: p for p in keypoints.evaluate(wf, {"arbeitsunfaehig": value})}
        self.assertEqual((state(True)["sperrfrist"]["state"], state(True)["sperrfrist"]["text"]), ("applies", "Kündigung möglicherweise nichtig: Sperrfrist"))
        self.assertEqual((state(None)["sperrfrist"]["state"], state(None)["sperrfrist"]["text"]), ("open", "Arbeitsunfähigkeit bei Kündigung? Dann Sperrfrist prüfen"))
        self.assertNotIn("sperrfrist", state(False))
        self.assertEqual(state(True)["sperrfrist"]["cite"], "Art. 336c Abs. 2 OR")
        self.assertIn("nichtig", state(True)["sperrfrist"]["law"][0]["passage"])
        shown = keypoints.shown(keypoints.evaluate(wf, {"arbeitsunfaehig": None, "grund_genannt": False, "arbeitsende": "2027-01-31", "fristlos": None}))
        self.assertEqual([p["id"] for p in shown], ["begruendung", "einsprache"])  # what applies first, at most two


class NextStepTests(unittest.TestCase):
    """After a demand went unanswered, what comes next: debt enforcement or the conciliation request, from the verified
    text of the debt enforcement act and the civil procedure code, as advice the customer can act on."""

    def test_a_loan_not_repaid_after_the_period_leads_to_enforcement_or_the_conciliation_request_and_answers_what_now(self):
        wf = area.workflow("vertrag-darlehen")
        facts = {"rechtsgebiet": wf["applies_when"]["is"], "termin_vereinbart": False, "aufforderung": "2026-03-02", "zahlung_ausgeblieben": True}
        points = {p["id"]: p for p in keypoints.evaluate(wf, facts)}
        self.assertEqual((points["betreibung"]["state"], points["schlichtung"]["state"]), ("applies", "applies"))
        self.assertEqual([r["cite"] for r in points["betreibung"]["law"]], ["Art. 38 Abs. 1 SchKG", "Art. 67 Abs. 1 SchKG"])
        self.assertEqual([r["cite"] for r in points["schlichtung"]["law"]], ["Art. 197 ZPO", "Art. 202 Abs. 1 ZPO"])
        self.assertTrue(all(r["verified"] for p in ("betreibung", "schlichtung") for r in points[p]["law"]))  # checked against the official text
        self.assertIn("Das Betreibungsbegehren ist schriftlich oder mündlich an das Betreibungsamt zu richten.", points["betreibung"]["law"][1]["passage"])
        self.assertEqual(keypoints.advice_line(points["betreibung"]),
                         "Bezahlt der Borger nicht, können Sie beim Betreibungsamt schriftlich oder mündlich ein Betreibungsbegehren stellen (Art. 38 Abs. 1 SchKG).")
        for question in ("Was kann ich jetzt machen?", "Wie geht es weiter, er zahlt nicht?"):
            self.assertEqual(keypoints.answer_for(question, list(points.values()))["id"], "betreibung")
        self.assertEqual(keypoints.answer_for("Muss ich vor Gericht klagen?", list(points.values()))["id"], "schlichtung")
        open_ = {p["id"]: p["state"] for p in keypoints.evaluate(wf, {k: v for k, v in facts.items() if k != "zahlung_ausgeblieben"})}
        self.assertEqual((open_["betreibung"], open_["schlichtung"]), ("open", "open"))  # asked, never asserted
        paid = {p["id"] for p in keypoints.evaluate(wf, {**facts, "zahlung_ausgeblieben": False})}
        self.assertFalse({"betreibung", "schlichtung"} & paid)
        question = next(f for f in wf["facts"] if f["id"] == "zahlung_ausgeblieben")
        self.assertEqual(question["ask_customer"], "offered")

    def test_other_areas_name_the_next_step_their_demands_lead_to(self):
        cases = {"inkasso": ({"gemahnt": True}, "betreibung"), "arbeit-lohn": ({"lohn_faellig_seit": "2026-08-25"}, "schlichtung"),
                 "privatversicherung": ({"ablehnung": "Leistung abgelehnt am 2026-09-01"}, "schlichtung")}
        for wid, (facts, point) in cases.items():
            wf = area.workflow(wid)
            got = {p["id"]: p for p in keypoints.evaluate(wf, {"rechtsgebiet": wf["applies_when"]["is"], **facts})}
            self.assertEqual(got[point]["state"], "applies", wid)
            self.assertTrue(got[point]["advice"] and all(r["verified"] for r in got[point]["law"]), wid)
            self.assertEqual(keypoints.answer_for("Was kann ich jetzt machen?", [got[point]])["id"], point)


class DismissalTests(unittest.TestCase):
    """Sick leave from before the notice: the card's key point, the customer's questions, the assessment."""

    @classmethod
    def setUpClass(cls):
        cls.result, cls.state, cls.items = run(KEY_CASES["kuendigung-sperrfrist"])

    def test_the_key_point_is_on_the_card_with_its_article_and_the_facts_source(self):
        listed = by_id(self.items)
        point = listed["key_point:sperrfrist"]
        self.assertEqual((point["value"], point["shown"], point["legal_basis"]), ("applies", True, "Art. 336c Abs. 2 OR"))
        self.assertIn("arbeitsunfähig", point["evidence"][0]["quote"])
        self.assertEqual(sum(1 for i in self.items if i["kind"] == "key_point" and i["shown"]), 2)

    def test_the_customers_questions_are_in_the_brief_with_quotes_and_answered_by_the_matching_point(self):
        asked = self.result["brief"]["questions"]
        self.assertEqual([q["question"] for q in asked], ["Erhalte ich ab Dezember noch Lohn?", "Ist die Kündigung überhaupt gültig?"])
        self.assertTrue(all(q["citations"][0]["quote"] for q in asked))
        rows = [i for i in self.items if i["kind"] == "customer_question"]
        self.assertEqual([r.get("answered_by") for r in rows], ["lohn", "sperrfrist"])  # the salary question by the point on continued pay

    def test_the_assessment_starts_from_the_points_that_apply_and_answers_the_questions(self):
        wf = self.state["process"]
        text, none = letters.render("A5", wf["forms"], letters.context(CASE_ROW, self.items, [], {"due": "2026-12-12"}))
        self.assertIsNone(none)
        in_case = text.split("In Ihrem Fall: ", 1)[1]
        self.assertTrue(in_case.startswith("Eine Kündigung, die während einer Sperrfrist"))
        self.assertIn("(Art. 336c Abs. 2 OR).", in_case.split("\n")[0])
        self.assertIn("[bitte ergänzen: was in diesem Fall sonst vorliegt]", in_case)
        self.assertIn("Zu Ihren Fragen:\n– «Erhalte ich ab Dezember noch Lohn?» Während der Sperrfrist", text)
        self.assertIn("im ersten Dienstjahr für drei Wochen", text)
        self.assertIn("– «Ist die Kündigung überhaupt gültig?» Siehe oben (Art. 336c Abs. 2 OR).", text)
        self.assertTrue(text.startswith("Guten Tag Sandra Beispiel"))  # the name known, no salutation stated

    def test_a_question_no_point_answers_is_a_marked_gap(self):
        items = [dict(i) for i in self.items]
        for i in items:
            if i["kind"] == "customer_question":
                i.pop("answered_by", None), i.pop("answer", None)
        ctx = letters.context(CASE_ROW, items, [], {"due": "2026-12-12"})
        self.assertIn("– «Ist die Kündigung überhaupt gültig?» [bitte ergänzen: Antwort auf diese Frage]", ctx["zu_fragen"])

    def test_the_title_comes_from_the_area_and_the_parties(self):
        self.assertEqual(listing.display_title({"title": "Scan_01"}, self.items, "Kündigung Arbeit"),
                         "Kündigung Arbeit · Sandra Beispiel ./. Muster Transport AG")
        self.assertEqual(listing.display_title({"title": "Mein Titel"}, self.items, "Kündigung Arbeit", renamed=True), "Mein Titel")
        self.assertEqual(listing.display_title({"title": "Scan_01"}, [], "Kündigung Arbeit"), "Scan_01")  # before preparation
        one = [i for i in self.items if not (i["kind"] == "party" and i["key"] == "1")]
        self.assertEqual(listing.display_title({"title": "Scan_01"}, one, "Kündigung Arbeit"),
                         "Kündigung Arbeit · Sandra Beispiel")  # the other side unknown: the area and the customer


class HearingTests(unittest.TestCase):
    """A summons to a conciliation hearing: its own item, leading the card, mentioned in the first letter."""

    @classmethod
    def setUpClass(cls):
        cls.result, cls.state, cls.items = run(KEY_CASES["miete-schlichtung"])

    def test_a_date_set_by_others_is_read_as_its_own_item_with_what_who_and_source(self):
        row = by_id(self.items)["deadline:frist"]
        self.assertEqual((row["value"], row["what"], row["by"], row["source"], row["set_by_others"]),
                         ("2026-12-10", "Schlichtungsverhandlung", "Schlichtungsbehörde Beispielstadt", "Vorladung", True))
        self.assertIn("Schlichtungsverhandlung am 10. Dezember", row["evidence"][0]["quote"])
        self.assertEqual(self.result["deadlines"][0]["set"], {"what": "Schlichtungsverhandlung", "by": "Schlichtungsbehörde Beispielstadt", "source": "Vorladung"})

    def test_the_first_letter_mentions_an_open_date_and_not_a_past_one(self):
        wf = self.state["process"]
        ctx = letters.context(CASE_ROW, self.items, [], {"due": "2026-12-05"}, today=date(2026, 11, 14), evaluation=self.state["evaluation"], process=wf)
        text, _ = letters.render("A1", wf["forms"], ctx)
        self.assertIn("Wir haben vermerkt: Schlichtungsverhandlung am 10.12.2026, angesetzt von Schlichtungsbehörde Beispielstadt (Vorladung).", text)
        later = letters.context(CASE_ROW, self.items, [], {"due": "2026-12-05"}, today=date(2026, 12, 11), evaluation=self.state["evaluation"], process=wf)
        self.assertNotIn("Schlichtungsverhandlung am", letters.render("A1", wf["forms"], later)[0])

    def test_the_question_about_a_running_deadline_carries_dates_others_set_without_a_new_fact(self):
        for w in area.shipped():
            asked = [f for f in w["facts"] if f.get("deadline")]
            self.assertEqual(len(asked), 1, w["id"])
            self.assertIn("Datum als JJJJ-MM-TT, danach « · » was fällig ist", asked[0]["question"])
        read = [f for f in area.workflow("mietmangel-handler")["facts"] if not f.get("handler_only") and not f.get("derived")]
        self.assertEqual(len(read), 40)  # facts a tenancy-defect run reads: 40 before and after
        self.assertEqual(team._fact_value({"type": "date", "deadline": True}, "2025-04-23 · Schlichtungsverhandlung · Schlichtungsbehörde Bern"),
                         ("2025-04-23 · Schlichtungsverhandlung · Schlichtungsbehörde Bern", None))
        self.assertEqual(team._fact_value({"type": "date"}, "2025-04-23 · Schlichtungsverhandlung")[0], None)  # only the deadline question


class StageDecisionTests(unittest.TestCase):
    def test_each_handler_decision_names_its_stage_and_the_validator_holds_it_to_the_backbone(self):
        bb = area.backbone()
        stages = {f["id"]: f.get("stages") for f in bb["facts"]}
        self.assertEqual(stages["einigung"], ["gegenpartei", "mandat"])
        self.assertEqual(stages["zahlung_erhalten"], ["abwicklung"])
        self.assertNotIn("klaeren", stages["weiteres_vorgehen"] + stages["vorgehen"] + stages["einigung"] + stages["zahlung_erhalten"])
        items = build_items(core.evaluate(area.workflow("vertrag-darlehen"), [], [], {"facts": [fact("rechtsgebiet", "Vertragsrecht / Darlehen")]}, "c"),
                            {"facts": []})
        self.assertEqual(by_id(items)["fact:einigung"]["stages"], ["gegenpartei", "mandat"])
        bad = copy.deepcopy(bb)
        next(f for f in bad["facts"] if f["id"] == "einigung")["stages"] = ["nirgends"]
        with self.assertRaises(CatalogueError):
            area.validate_backbone(bad)


class WordingTests(unittest.TestCase):
    def test_a_partly_present_correspondence_asks_for_the_rest(self):
        self.assertEqual(further("Sämtliche Korrespondenz mit der Verwaltung"), "Weitere Korrespondenz mit der Verwaltung (über die vorliegenden Schreiben hinaus)")
        self.assertEqual(further("Bisherige Korrespondenz mit der Versicherung"), "Weitere Korrespondenz mit der Versicherung (über die vorliegenden Schreiben hinaus)")


def item(kind, key, value=None, **fields):
    return {"kind": kind, "key": key, "item_id": f"{kind}:{key}", "value": value, **fields}


class CaseListTests(unittest.TestCase):
    TODAY = date(2026, 11, 14)

    def stand(self, items=(), **kw):
        args = {"closed": False, "run_status": "completed", "new_files": 0, "items": list(items), "follow_up": "2026-12-05", "events": [],
                "completed_at": "2026-11-14T08:00:00", "files": [], "today": self.TODAY, **kw}
        return listing.stand(**args)

    def test_the_stand_says_what_the_handler_acts_on_and_ranks_it(self):
        frist = item("deadline", "anfechtung", "2026-12-03", origin="law", party="kunde")
        termin = item("deadline", "frist", "2026-11-20", set_by_others=True, what="Schlichtungsverhandlung")
        contact = item("contact", "erstkontakt", "2026-11-18")
        rows = {
            "frist": self.stand([frist]), "termin": self.stand([termin, frist]), "contact": self.stand([contact]),
            "prepared": self.stand([]), "arrived": self.stand([frist], new_files=2), "paused": self.stand(run_status="paused"),
            "working": self.stand(run_status="running"), "new": self.stand(run_status=None),
            "waiting": self.stand([item("next_action", "0", action="A1")], closed=True),
            "due": self.stand([item("next_action", "0", action="A1")], closed=True, follow_up="2026-11-10"),
            "copied": self.stand([item("next_action", "0", action="A8")], events=[{"kind": "letter.copied", "at": "2026-11-14T09:00:00"}]),
            "done": self.stand([item("next_action", "0", action="A12")], closed=True),
        }
        # the status in one word, the same on the card; the date it goes with is the list's «Fällig» (listing.due)
        self.assertEqual((rows["frist"]["text"], rows["frist"]["date"]), ("Frist läuft", "2026-12-03"))
        self.assertEqual((rows["termin"]["text"], rows["termin"]["date"]), ("Frist läuft", "2026-11-20"))
        self.assertEqual((rows["contact"]["text"], rows["contact"]["date"]), ("vorbereitet", "2026-11-18"))
        self.assertEqual(rows["prepared"]["text"], "vorbereitet")
        self.assertEqual(rows["arrived"]["text"], "neue Unterlagen")
        self.assertEqual((rows["waiting"]["text"], rows["waiting"]["date"]), ("wartet auf Kundschaft", "2026-12-05"))
        self.assertEqual(rows["copied"]["text"], "wartet auf Gegenpartei")
        self.assertEqual(rows["due"]["text"], "Wiedervorlage fällig")
        self.assertEqual(listing.due([termin, frist, contact], "2026-12-05", [], today=self.TODAY), {"date": "2026-11-18", "word": "Erstkontakt"})
        self.assertEqual(listing.due([termin, frist], "2026-12-05", [], today=self.TODAY), {"date": "2026-11-20", "word": "Termin"})
        self.assertEqual(rows["done"]["text"], "erledigt")
        order = sorted(rows, key=lambda k: rows[k]["rank"])
        self.assertEqual(order[0], "arrived")
        self.assertLess(rows["frist"]["rank"], rows["contact"]["rank"])
        self.assertLess(rows["contact"]["rank"], rows["prepared"]["rank"])
        self.assertLess(rows["prepared"]["rank"], rows["waiting"]["rank"])
        self.assertEqual(order[-1], "done")

    def test_a_historic_cut_is_looked_at_as_of_its_day_and_never_runs_a_live_deadline(self):
        files = [{"extraction": {"cut_of": {"as_of": "2025-02-07"}}}]
        self.assertEqual(listing.as_of(files), date(2025, 2, 7))
        old = item("deadline", "anfechtung", "2025-02-20", origin="law")
        row = self.stand([old, item("contact", "erstkontakt", "2026-11-18")], files=files)
        self.assertEqual((row["text"], row["date"]), ("Frist läuft", "2025-02-20"))  # running as of its own day, the first contact not counted

    def test_a_closing_row_names_its_reason_once(self):
        self.assertEqual(listing.next_step(item("next_action", "0", action="A12", label={"de": "Dossier schliessen"}, closing="keine Rückmeldung")),
                         "Dossier schliessen: keine Rückmeldung")
        self.assertEqual(listing.next_step(item("next_action", "0", action="close", label={"de": "Fall abschliessen: Abschluss: Beratung erfolgt"},
                                                closing="Beratung erfolgt")), "Dossier schliessen: Beratung erfolgt")
        wf = area.workflow("mietmangel-handler")
        facts = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("handlung_a1", "2024-02-01"), fact("handlung_a5", "2024-03-01"),
                 fact("weiteres_vorgehen", False), fact("deckung", "bestätigt")]
        items = build_items(core.evaluate(wf, [], [], {"facts": facts}, "c"), {"facts": facts})
        nxt = by_id(items)["next_action:0"]
        self.assertEqual(listing.next_step(nxt), "Dossier schliessen: Beratung erfolgt")


class FileNameTests(unittest.TestCase):
    def test_a_prepared_case_keeps_the_name_as_uploaded(self):
        from casepath.read import prepare
        with tempfile.TemporaryDirectory() as out:
            manifest = prepare.prepare_case("Brief_geschwärzt", [("Brief_geschwärzt.txt", "Die Verwaltung hat nicht reagiert.".encode())], out,
                                            source_name="Brief_geschwärzt.txt")
        self.assertEqual((manifest["source_name"], manifest["files"][0]["name"]), ("Brief_geschwärzt.txt", "Brief_geschwärzt.txt"))
        self.assertEqual(manifest["files"][0]["file"], "files/01-Brief_geschw-rzt.txt")  # only the stored copy's name is made safe


if __name__ == "__main__":
    unittest.main()


class CaseListAppTests(unittest.TestCase):
    def test_the_list_gives_the_title_from_the_case_and_the_stand_and_a_persons_title_stays(self):
        from fastapi.testclient import TestClient
        from casepath.config import load_settings
        from casepath.read.extract import extract
        from casepath.web.app import create_app
        with tempfile.TemporaryDirectory() as data:
            app = create_app(load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None)
            store, client = app.state.store, TestClient(app)
            case = store.create_case("Scan_01", {}, "dev")
            row = extract("Scan_01.txt", "text/plain", "Max Beispiel zahlt das Darlehen nicht zurück.".encode())
            store.add_file(case["id"], "Scan_01.txt", row["media_type"], row["kind"], b"x", row, "dev")
            run = store.create_run(case["id"], "dev")
            store.update_run(run["id"], status="completed", workflow_id="vertrag-darlehen", finished_at="2026-11-12T10:00:00+00:00",
                             result={"facts": [fact("rechtsgebiet", "Vertragsrecht / Darlehen")], "documents": [],
                                     "brief": {"request": "Anna Muster will ihr Darlehen zurück.", "timeline": [],
                                               "parties": [{"role": "Darleiherin (VN)", "name": "Anna Muster"}, {"role": "Borger", "name": "Max Beispiel"}]}})
            listed = client.get("/api/cases").json()["cases"][0]
            self.assertEqual(listed["display_title"], "Darlehen · Anna Muster ./. Max Beispiel")
            self.assertEqual(listed["title"], "Scan_01")  # the stored title, as before
            self.assertIn(listed["stand"]["kind"], {"contact", "prepared", "frist"})
            self.assertNotEqual(listed["stand"]["text"], "bereit")
            self.assertEqual(client.get(f"/api/cases/{case['id']}").json()["case"]["display_title"], "Darlehen · Anna Muster ./. Max Beispiel")
            client.put(f"/api/cases/{case['id']}/title", json={"title": "Darlehen Muster, Rückforderung"})
            self.assertEqual(client.get("/api/cases").json()["cases"][0]["display_title"], "Darlehen Muster, Rückforderung")
            app.state.runs.shutdown()
            store.close()

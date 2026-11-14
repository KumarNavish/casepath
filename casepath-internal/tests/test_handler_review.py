"""What a claim handler noticed on the deployed product, each as a general rule (process version 2026-11-14.6).

The first contact counted from the day the case came in, historic files apart and never overdue, the follow-up of a cut
from its «Stand am», titles from the area and the case, no placeholder on the list or the card, key points by stage
and the short facts of the mandate, the customer's advice in the first letter, continued pay in the dismissal area, and
a passed date that names what it was. Scripted and model-free."""
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

from casepath.agents import core
from casepath.process import area, keypoints, letters
from casepath.process.clock import follow_up, historic
from casepath.process.items import UNNAMED, SHOWN_KINDS, build_items, placeholder, plain
from casepath.web import listing
from tests.test_handler_workflow import fact
from tests.test_key_points import KEY_CASES, by_id, run

FIXTURES = Path(__file__).parent / "fixtures"
AREA_CASES = {k: v for k, v in json.loads((FIXTURES / "areas" / "cases.json").read_text()).items() if not k.startswith("_")}
YES = {"ja": True, "nein": False}


def items_of(wid, facts, files=None, events=None, created=None, deadlines=(), brief=None):
    result = {"facts": [fact(k, YES.get(v, v)) for k, v in facts], "documents": [], "deadlines": list(deadlines),
              "brief": brief or {"request": "", "parties": [], "timeline": []}}
    state = core.evaluate(area.workflow(wid), [], [], result, "c", files=files)
    state = {**state, "case": {"id": "c", "created_at": created or "2026-11-14T08:00:00", "intake": {}}}
    return state, build_items(state, result, files, events)


def routing(w):
    when = w.get("applies_when") or {}
    rows = when.get("any") or when.get("all") or [when]
    first = next((r for r in rows if r.get("fact") == "rechtsgebiet"), {})
    return first.get("is") or (first.get("in") or [None])[0]


class AppCase:
    """A case in a fresh app: created now, its files, a completed run with the given result."""

    def __init__(self):
        from fastapi.testclient import TestClient
        from casepath.config import load_settings
        from casepath.web.app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(load_settings({"CASEPATH_DATA_DIR": self.tmp.name, "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None)
        self.store, self.client = self.app.state.store, TestClient(self.app)

    def case(self, title, segments, workflow, facts, brief):
        from casepath.read.extract import extract
        case = self.store.create_case(title, {"source": "upload"}, "dev")
        row = extract(f"{title}.txt", "text/plain", "Synthetische Akte.".encode())
        row["segments"] = segments
        self.store.add_file(case["id"], f"{title}.txt", row["media_type"], row["kind"], b"x", row, "dev")
        run = self.store.create_run(case["id"], "dev")
        self.store.update_run(run["id"], status="completed", workflow_id=workflow, finished_at=datetime.now(timezone.utc).isoformat(),
                              result={"facts": [fact(k, v) for k, v in facts], "documents": [], "brief": brief})
        return case

    def row(self, case_id):
        return next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case_id)

    def close(self):
        self.app.state.runs.shutdown()
        self.store.close()
        self.tmp.cleanup()


LOAN = {"request": "Anna Muster will ihr Darlehen zurück.", "timeline": [],
        "parties": [{"role": "Darleiherin (VN)", "name": "Anna Muster"}, {"role": "Borger", "name": "Max Beispiel"}]}


class FirstContactAndHistoricFileTests(unittest.TestCase):
    """1 and 2: a case that came in today is not overdue; a whole old file is a historic file, listed apart."""

    def setUp(self):
        self.app = AppCase()

    def tearDown(self):
        self.app.close()

    def test_a_case_created_today_from_an_older_customer_letter_is_not_overdue(self):
        letter = (date.today() - timedelta(days=12)).strftime("%d.%m.%Y")
        case = self.app.case("Brief Kundin", [{"first_page": 1, "last_page": 1, "kind": "Schadenmeldung", "date": letter, "sender": "Anna Muster"}],
                             "vertrag-darlehen", [("rechtsgebiet", "Vertragsrecht / Darlehen")], LOAN)
        row = self.app.row(case["id"])
        self.assertIsNone(row["historic"])
        self.assertGreater(row["first_contact"]["due"], date.today().isoformat())  # three working days from today, not from the letter
        self.assertFalse(row["first_contact"]["late"])
        self.assertEqual(row["stand"]["kind"], "contact")
        self.assertTrue(row["stand"]["text"].startswith("Erstkontakt bis"))
        self.assertIn("Eröffnung des Falls", row["first_contact"]["rule"])

    def test_a_whole_old_file_is_historic_shows_no_first_contact_and_a_person_can_move_it(self):
        old = [{"first_page": 1, "last_page": 1, "kind": "Schadenmeldung", "date": "14.03.2023", "sender": "Anna Muster"},
               {"first_page": 2, "last_page": 2, "kind": "Brief", "date": "02.06.2023", "sender": "Protekta Rechtsschutz AG"}]
        case = self.app.case("Akte_2023_komplett", old, "vertrag-darlehen", [("rechtsgebiet", "Vertragsrecht / Darlehen")], LOAN)
        row = self.app.row(case["id"])
        self.assertEqual((row["historic"]["how"], row["historic"]["newest"]), ("old", "2023-06-02"))
        self.assertIsNone(row["first_contact"])
        self.assertNotIn("überfällig", row["stand"]["text"])
        self.assertNotIn("fällig", row["stand"]["text"])
        self.assertEqual(self.app.client.get(f"/api/cases/{case['id']}").json()["historic"]["newest"], "2023-06-02")  # the card says so
        # one action in «Mehr», logged: out of the historic files (the first contact counts again), and back
        self.assertEqual(self.app.client.put(f"/api/cases/{case['id']}/historic", json={"historic": False}).status_code, 200)
        moved = self.app.row(case["id"])
        self.assertIsNone(moved["historic"])
        self.assertIsNotNone(moved["first_contact"])
        self.app.client.put(f"/api/cases/{case['id']}/historic", json={"historic": True})
        self.assertEqual(self.app.row(case["id"])["historic"]["how"], "person")
        logged = [e for e in self.app.client.get(f"/api/cases/{case['id']}/events").json()["events"] if e["kind"] == "case.historic"]
        self.assertEqual([(e["historic"], e["expert"]) for e in logged], [(False, "dev"), (True, "dev")])
        self.assertEqual(self.app.client.post(f"/api/cases/{case['id']}/events", json={"kind": "case.historic", "fields": {"historic": False}}).status_code, 422)

    def test_the_twelve_month_line(self):
        created = "2026-11-14T08:00:00"
        file = lambda day: [{"extraction": {"segments": [{"date": day}]}}]
        self.assertIsNone(historic(file("15.11.2025"), created))
        self.assertEqual(historic(file("13.11.2025"), created)["how"], "old")
        self.assertIsNone(historic([], created))  # no dated document: a live case
        cut = [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}]
        self.assertEqual(historic(cut, created), {"newest": "2024-10-18", "how": "cut", "as_of": "2025-02-07"})
        stand = listing.stand(closed=True, run_status="completed", new_files=0, items=[{"kind": "next_action", "key": "0", "action": "A1"}],
                              follow_up="2023-07-01", events=[], completed_at="2026-11-14T08:00:00", files=file("02.06.2023"),
                              today=date(2026, 11, 14), historic=historic(file("02.06.2023"), created))
        self.assertNotIn("fällig", stand["text"])


class CutFollowUpTests(unittest.TestCase):
    """3: the follow-up of a cut counts from its «Stand am», never from an older document or action."""

    def test_the_follow_up_of_a_cut_is_never_before_its_as_of_day(self):
        cut = [{"extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2023"}, {"date": "02.11.2023"}]}}]
        for since in (None, "2023-11-02", "2025-02-07"):
            due = follow_up(21, cut, [], since=since)["due"]
            self.assertEqual(due, "2025-02-28", since)
        live = [{"extraction": {"segments": [{"date": "18.10.2026"}]}}]
        self.assertEqual(follow_up(21, live, [], since="2026-11-01")["due"], "2026-11-22")  # a live case: from its last action
        wf = area.workflow("mietmangel-handler")
        facts = [("rechtsgebiet", "Mietrecht / Mangel"), ("bisherige_handlungen", "A1 2023-09-01"), ("handlung_a1", "2023-09-01")]
        _, items = items_of("mietmangel-handler", facts, files=cut)
        nxt = by_id(items)["next_action:0"]
        clock = follow_up(nxt.get("next_in_days") or 21, cut, [], since=nxt.get("since"))
        self.assertGreaterEqual(clock["due"], "2025-02-07", wf["id"])


class TitleTests(unittest.TestCase):
    """4: area and customer, or area and the place or object of the dispute; never a cut sentence or a raw file name."""

    def items(self, request, parties):
        return [{"kind": "summary", "key": "0", "value": request}, {"kind": "next_action", "key": "0"}] + \
               [{"kind": "party", "key": str(i), "label": {"de": r}, "value": n} for i, (r, n) in enumerate(parties)]

    def test_the_title_rules(self):
        case = {"title": "Scan_2025_11_03_0012"}
        self.assertEqual(listing.display_title(case, self.items("Lea Brunner will ihr Darlehen zurück.", [("Darleiherin (VN)", "Lea Brunner")]), "Darlehen"),
                         "Darlehen · Lea Brunner")
        self.assertEqual(listing.display_title(case, self.items("Die Verwaltung kündigte die Wohnung an der Probegasse 7 auf Ende März.", []), "Kündigung Miete"),
                         "Kündigung Miete · Probegasse 7")
        self.assertEqual(listing.display_title(case, self.items("Seit Oktober zeigt sich Schimmel im Badezimmer der Wohnung.", [("Mieterin (VN)", "Name geschwärzt")]),
                                               "Mietmangel"), "Mietmangel · Schimmel im Badezimmer der Wohnung")
        self.assertEqual(listing.display_title(case, self.items("Die Nachbarin lässt die Äste ihrer Thuja über den Zaun wachsen.", []), "Nachbarrecht"),
                         "Nachbarrecht · Äste ihrer Thuja")
        self.assertEqual(listing.display_title(case, self.items("", []), "Darlehen"), "Darlehen")  # nothing to name: the area, not the file name
        self.assertEqual(listing.display_title(case, [], "Darlehen"), "Scan_2025_11_03_0012")  # before preparation the name as uploaded

    def test_no_title_of_a_shipped_example_ends_in_an_ellipsis_or_is_longer_than_five_words_after_the_area(self):
        for key, case in {**AREA_CASES, **KEY_CASES}.items():
            for parties in ([], [("Arbeitgeberin", "Muster AG")]):
                with self.subTest(case=key, parties=bool(parties)):
                    title = listing.display_title({"title": "Akte.pdf"}, self.items(case.get("request") or case["text"], parties), "Bereich")
                    self.assertFalse(title.endswith("…"), title)
                    self.assertNotEqual(title, "Akte.pdf")
                    self.assertLessEqual(len(title.split(" · ", 1)[1].split()) if " · " in title else 0, 5, title)
                    self.assertIn(title.split(" · ", 1)[-1].split()[-1] if " · " in title else "Bereich", (case.get("request") or case["text"]) + " Bereich")


class PlaceholderTests(unittest.TestCase):
    """5: no placeholder (DD.MM.YYYY, JJJJ-MM-TT, {…}, <…>) reaches the list or the card, in any workflow or example shipped."""

    def check(self, items, where):
        for i in items:
            if i["kind"] not in SHOWN_KINDS:
                continue
            for text in [(i.get("label") or {}).get("de"), (i.get("label") or {}).get("en"), i.get("reason"),
                         i.get("value") if isinstance(i.get("value"), str) else None]:
                self.assertFalse(placeholder(text), f"{where}: {i['item_id']}: {text}")
            if i["kind"] == "next_action":
                self.assertFalse(placeholder(listing.next_step(i)), where)

    def test_the_pattern_and_the_plain_text(self):
        for text in ("Frist bis (DD.MM.YYYY) setzen", "Datum (JJJJ-MM-TT)", "Hallo {name}", "an <Kanzlei>", "«beglichen YYYY-MM-DD»"):
            self.assertTrue(placeholder(text), text)
        self.assertFalse(placeholder("Frist bis 23.04.2025 · Schlichtungsverhandlung"))
        self.assertEqual(plain("Rückmeldung der Kundschaft bis (DD.MM.YYYY) abwarten"), "Rückmeldung der Kundschaft abwarten")
        self.assertEqual(plain("Zuletzt eingegangener Bericht der Kanzlei: Inhalt und Datum (JJJJ-MM-TT), auch ob er eine Information verlangt"),
                         "Zuletzt eingegangener Bericht der Kanzlei: Inhalt und Datum, auch ob er eine Information verlangt")

    def test_every_text_that_can_become_a_next_step_is_shown_without_placeholder(self):
        for w in area.shipped():
            texts = [f["question"] for f in w["facts"]] + [s["action"].get("title") for s in w["steps"] if s.get("action")] + \
                    [r.get("title") for r in w.get("clock") or ()] + [k["title"] for k in w.get("incoming") or ()] + \
                    [f.get("title") for f in w["forms"].values() if isinstance(f, dict)]
            for text in filter(None, texts):
                self.assertFalse(placeholder(plain(text)), f"{w['id']}: {text}")

    def test_items_of_every_area_and_example_in_several_states(self):
        for w in area.shipped():
            value = routing(w)
            states = [[("rechtsgebiet", value)],
                      [("rechtsgebiet", value), ("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei"),
                       ("bisherige_handlungen", "A1 2026-09-10; A10 2026-10-01"),
                       ("eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200"),
                       ("eingang_bericht", "Kanzlei Muster: Stand der Verhandlungen, 2026-10-20"),
                       ("eingang_angebot", "Gegenpartei: Vergleich CHF 800 per Saldo, Schreiben vom 2026-10-25")],
                      [("rechtsgebiet", value), ("bisherige_handlungen", "A1 2026-08-01; A6 2026-09-01")]]
            for facts in states:
                with self.subTest(area=w["id"], facts=len(facts)):
                    self.check(items_of(w["id"], facts)[1], w["id"])
        for key, case in AREA_CASES.items():
            facts = [("rechtsgebiet", (case.get("routing") or [routing(area.workflow(key))])[0])] + [(f, v) for f, v, _ in case["facts"]]
            self.check(items_of(key, facts)[1], key)
        for key, case in KEY_CASES.items():
            self.check(run(case)[2], key)

    def test_a_process_text_with_a_placeholder_never_reaches_the_list_or_the_card(self):
        import copy
        wf = copy.deepcopy(area.workflow("mietmangel-handler"))
        step = next(x for x in wf["steps"] if x["id"] == "klaeren")
        step["action"]["title"] = "Unterlagen anfordern, Rückmeldung bis (DD.MM.YYYY) an {kanzlei}"
        result = {"facts": [fact("rechtsgebiet", "Mietrecht / Mangel")], "documents": [], "brief": {"request": "", "parties": [], "timeline": []}}
        state = core.evaluate(wf, [], [], result, "c")
        nxt = by_id(build_items(state, result))["next_action:0"]
        self.assertEqual((nxt["label"]["de"], listing.next_step(nxt)), ("Unterlagen anfordern", "Unterlagen anfordern"))
        self.check(build_items(state, result), "patched")
        # the seeded examples on the synthetic workflow of the preview
        example = json.loads((FIXTURES / "example-defect.json").read_text())
        from casepath.process import workflows
        example = workflows.validate_workflow(example)
        state = core.evaluate(example, [], [], {"facts": [], "documents": []}, "c")
        self.check(build_items(state, {"facts": [], "documents": []}), "example-defect")


MANDATE = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei"),
           ("will_reduktion", "ja"), ("bisherige_handlungen", "A1 2026-09-10; A10 2026-10-01"), ("handlung_a1", "2026-09-10")]


class StageTests(unittest.TestCase):
    """6: the first assessment's key points do not lead the card at the mandate stage; the mandate's own facts do."""

    def test_at_the_mandate_stage_the_card_shows_the_mandates_facts_and_no_first_assessment_points(self):
        state, items = items_of("mietmangel-handler", MANDATE + [
            ("eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200"),
            ("eingang_kostenforderung_2", "Kanzlei Muster: Kostenvorschuss vom 2026-10-10 über CHF 2'000; beglichen 2026-10-15"),
            ("eingang_bericht", "Kanzlei Muster: Stand der Verhandlungen vom 2026-10-20"),
            ("eingang_angebot", "Gegenpartei: Vergleich CHF 800 per Saldo, Schreiben vom 2026-10-25")])
        self.assertEqual(state["evaluation"]["current"]["step"], "mandat")
        listed = by_id(items)
        self.assertEqual(listed["key_point:reduktion"]["value"], "applies")  # still known, for the assessment
        self.assertFalse(any(i["shown"] for i in items if i["kind"] == "key_point"))  # but not on the card at this stage
        lines = [i["value"] for i in items if i["kind"] == "stage_line"]
        self.assertEqual(lines, ["Kostengutsprache erteilt: 01.10.2026", "Letzter Bericht der Kanzlei: 20.10.2026",
                                 "Offene Kostenforderungen: 1", "Angebot wartet auf Antwort: 25.10.2026"])
        self.assertEqual(listed["stage_line:kostengutsprache"]["facts"], ["bisherige_handlungen"])

    def test_nothing_is_shown_that_the_file_does_not_establish(self):
        _, items = items_of("mietmangel-handler", MANDATE)
        self.assertEqual([i["value"] for i in items if i["kind"] == "stage_line"], ["Kostengutsprache erteilt: 01.10.2026"])
        _, early = items_of("mietmangel-handler", [("rechtsgebiet", "Mietrecht / Mangel"), ("will_reduktion", "ja")])
        self.assertFalse([i for i in early if i["kind"] == "stage_line"])  # not at the clarifying stage
        self.assertTrue(by_id(early)["key_point:reduktion"]["shown"])

    def test_each_point_names_the_stages_where_it_helps(self):
        points = {p["id"]: p for p in keypoints.evaluate(area.workflow("vertrag-darlehen"), {"termin_vereinbart": False, "schriftlich": False}, "gegenpartei")}
        self.assertTrue(points["ohne_termin"]["here"])  # named for the step against the other side too
        self.assertFalse(points["beweis"]["here"])  # by default only while clarifying and assessing
        for w in area.shipped():
            for p in w["key_points"]:
                self.assertLessEqual(set(p.get("stages") or keypoints.STAGES), {s["id"] for s in w["steps"]}, w["id"])


class AdviceTests(unittest.TestCase):
    """7: what the card knows and the customer can act on is in the first letter, with its article."""
    SENTENCE = ("Sie können das Darlehen schriftlich zurückfordern; ohne vereinbarten Termin ist es innert sechs Wochen ab der ersten "
                "Aufforderung zurückzuzahlen (Art. 318 OR).")

    def letter(self, facts, events=()):
        state, items = items_of("vertrag-darlehen", [("rechtsgebiet", "Vertragsrecht / Darlehen")] + facts, brief=LOAN)
        ctx = letters.context({"id": "c", "title": "Darlehen (synthetisch)"}, items, list(events), {"due": "2026-12-05"},
                              evaluation=state["evaluation"], process=state["process"])
        return by_id(items), letters.render("A1", state["process"]["forms"], ctx)[0]

    def test_the_loan_letter_carries_the_demand_in_writing(self):
        listed, text = self.letter([("rueckforderung_schriftlich", False)])
        self.assertEqual(listed["key_point:schriftlich_fordern"]["value"], "applies")
        self.assertEqual(listed["hint:kp-schriftlich_fordern"]["stated_as"], "established")
        self.assertIn(self.SENTENCE, text)
        self.assertEqual(text.count("sechs Wochen"), 1)  # it stands for the area's hint that said the same

    def test_offered_when_it_depends_on_an_open_fact_and_in_the_letter_once_ticked(self):
        listed, text = self.letter([])
        self.assertEqual(listed["key_point:schriftlich_fordern"]["value"], "open")
        row = listed.get("hint:kp-schriftlich_fordern") or listed["hint:aufforderung"]  # offered: the advice, or the area's hint saying it
        self.assertEqual(row["stated_as"], "put_to_handler")
        self.assertNotIn("innert sechs Wochen ab der ersten Aufforderung", text)
        ticked = [{"kind": "letter.line", "item_id": row["item_id"], "included": True}]
        self.assertIn("Aufforderung", self.letter([], ticked)[1].split("folgende Hinweise:", 1)[1])

    def test_every_area_marks_which_points_are_advice(self):
        rows = area.shipped()
        self.assertEqual(len(rows), 19)
        for w in rows:
            with self.subTest(area=w["id"]):
                self.assertTrue(all("advice" in p for p in w["key_points"]))  # each point says it, true or false
                advice = [p for p in w["key_points"] if p["advice"]]
                self.assertTrue(advice)
                for p in advice:
                    line = keypoints.advice_line({"advice": p["advice"], "cite": w["law"][p["law"][0].split("#")[1]]["cite"]})
                    self.assertRegex(line, r"\((Art\.|§) [^()]+\)\.$")

    def test_a_first_request_in_every_area_never_says_the_same_twice(self):
        for key, case in AREA_CASES.items():
            facts = [("rechtsgebiet", (case.get("routing") or [routing(area.workflow(key))])[0])] + [(f, v) for f, v, _ in case["facts"]]
            _, items = items_of(key, facts)
            hints = [i for i in items if i["kind"] == "hint" and i["stated_as"] == "established"]
            refs = lambda i: next((set(r for r in h.get("source_refs") or () if r.startswith("law#")) for h in area.workflow(key)["hints"] if h["id"] == i["key"]), set())
            for i in hints:
                if i["key"].startswith("kp-"):
                    point = next(p for p in area.workflow(key)["key_points"] if p["id"] == i["key_point"])
                    others = [h for h in hints if not h["key"].startswith("kp-") and refs(h) and refs(h) <= set(point["law"])]
                    self.assertFalse(others, f"{key}: {i['key']} and {[h['key'] for h in others]}")


class ContinuedPayTests(unittest.TestCase):
    """8: the dismissal area answers whether salary continues, from verified articles."""

    def test_the_point_on_continued_pay_applies_with_its_articles_and_answers_salary_questions(self):
        wf = area.workflow("arbeit-kuendigung")
        points = keypoints.evaluate(wf, {"arbeitsunfaehig": True})
        lohn = next(p for p in points if p["id"] == "lohn")
        self.assertEqual(lohn["state"], "applies")
        self.assertEqual([r["cite"] for r in lohn["law"]][:3], ["Art. 324a Abs. 1 OR", "Art. 324a Abs. 2 OR", "Art. 336c Abs. 1 lit. b OR"])
        self.assertTrue(all(r["verified"] for r in lohn["law"]))
        self.assertIn("drei Wochen", lohn["follows"])
        for question in ("Erhalte ich ab Dezember noch Lohn?", "Muss die Firma mir das Gehalt weiter zahlen?", "Bekomme ich Krankentaggeld?",
                         "Wer zahlt mir jetzt mein Salär?"):
            self.assertEqual(keypoints.answer_for(question, points)["id"], "lohn", question)
        self.assertEqual(keypoints.answer_for("Ist die Kündigung gültig?", points)["id"], "sperrfrist")
        self.assertEqual(keypoints.evaluate(wf, {"arbeitsunfaehig": None})[0]["state"], "open")

    def test_its_passages_are_in_the_saved_official_text(self):
        folder = os.environ.get("CASEPATH_LAW_SOURCES")
        if not folder:
            self.skipTest("CASEPATH_LAW_SOURCES not set")
        module = area.load(area.AREAS / "arbeit-kuendigung.json")
        texts = {sr: area.official_articles(Path(folder) / row["file"]) for sr, row in area.backbone()["laws"].items()
                 if (Path(folder) / row["file"]).is_file()}
        found = area.verify(module, texts)
        self.assertEqual(found, {k: r["verified"] for k, r in module["law"].items() if r["sr"] in texts})
        self.assertTrue(all(found[k] for k in ("324a", "324a.2", "324a.4", "336c.dauer")))


class PassedDateTests(unittest.TestCase):
    """9: a passed date names what it was and who set it; without what it was for, it says so, never the reader's question."""

    def test_a_date_with_and_without_what_it_was_for(self):
        set_ = {"fact": "frist", "question": "Läuft eine weitere Frist?", "date": "2025-04-23",
                "set": {"what": "Schlichtungsverhandlung", "by": "Schlichtungsbehörde Bern", "source": "Vorladung"}}
        bare = {"fact": "frist", "question": "Läuft eine weitere Frist (Vermieterschaft, Gericht)? Oder hat ein Gericht …", "date": "2025-04-23"}
        named = by_id(items_of("miete-kuendigung", [("rechtsgebiet", "Mietrecht / Kündigung")], deadlines=[set_])[1])["deadline:frist"]
        self.assertEqual((named["label"]["de"], named["what"], named["source"], named.get("unnamed")),
                         ("Schlichtungsverhandlung", "Schlichtungsverhandlung", "Vorladung", None))
        unnamed = by_id(items_of("miete-kuendigung", [("rechtsgebiet", "Mietrecht / Kündigung")], deadlines=[bare])[1])["deadline:frist"]
        self.assertEqual((unnamed["label"]["de"], unnamed["unnamed"]), (UNNAMED, True))
        self.assertNotIn("?", unnamed["label"]["de"])
        js = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text()
        self.assertIn("(d.set_by_others || d.unnamed) && dated(d)", js)  # the Fristen line: date · what · laut source · abgelaufen, source chip


if __name__ == "__main__":
    unittest.main()

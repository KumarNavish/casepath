"""The handler's process for every area: backbone + area module, composed at load (casepath/process/area.py)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from casepath.agents import core
from casepath.process import area, letters, workflows
from casepath.process.items import HASHED, build_items, items_sha256
from casepath.process.workflows import Catalogue, CatalogueError
from tests.scripted import ScriptedModel, report
from tests.test_handler_workflow import document, fact

FIXTURES = Path(__file__).parent / "fixtures"
FROZEN = json.loads((FIXTURES / "areas" / "mietmangel-handler.2026-11-12.5.json").read_text())  # the seed as it was before the split
CASES = {k: v for k, v in json.loads((FIXTURES / "areas" / "cases.json").read_text()).items() if not k.startswith("_")}
NEW_KEYS = {"short_title", "area", "action_kinds", "cooperation", "assess_needs", "deadlines", "law", "laws"}


def intakes(*ids):
    """Stand-ins for the customer-intake workflows of a deployed catalogue (osm-mold, osm-loan, osm-fallback)."""
    values = {"osm-mold": "Mietrecht / Mangel", "osm-loan": "Vertragsrecht / Darlehen", "osm-fallback": "Übriges Recht"}
    return [{"format": workflows.FORMAT, "id": i, "version": "1", "title": i, "status": "draft", **({"fallback": True} if i == "osm-fallback" else {}),
             "sources": [{"id": "d", "kind": "process_diagram", "title": "D"}], "applies_when": {"fact": "rechtsgebiet", "is": values[i]},
             "facts": [{"id": "rechtsgebiet", "type": "enum", "values": [values[i]], "question": "?", "source_refs": ["d#1"]}],
             "start": "a", "steps": [{"id": "a", "title": "A", "source_refs": ["d#1"], "documents": [], "next": []}], "documents": []} for i in ids]


def catalogue(*rows):
    with tempfile.TemporaryDirectory() as directory:
        for row in rows:
            Path(directory, f"{row['id']}.json").write_text(json.dumps(row, ensure_ascii=False))
        return Catalogue.load(directory)


def module(wid):
    return json.loads((area.AREAS / f"{wid}.json").read_text())


class CompositionTests(unittest.TestCase):
    # What the split changed on purpose: the clarifying stage's way out (silence, not incompleteness, ends benefits; a
    # replied case with its points answered goes to the assessment), three derived facts, and the assessment's
    # "bitte reichen Sie noch nach". Everything else is the former seed, field for field.
    CHANGED_FACTS = {"mitwirkung_fehlt", "kunde_geantwortet", "keine_punkte_offen", "beurteilbar"}

    def test_the_composed_tenancy_defect_workflow_is_the_seed_it_replaces_but_for_the_named_rule_change(self):
        composed = area.workflow("mietmangel-handler")
        same = lambda w: {k: v for k, v in w.items() if k not in NEW_KEYS | {"version", "facts", "steps", "forms"}}
        self.assertEqual(same(composed), same(FROZEN))
        self.assertEqual((composed["id"], composed["version"]), ("mietmangel-handler", "2026-11-14.1"))  # stored runs: same id, newer version governs
        self.assertEqual([f for f in composed["facts"] if f["id"] not in self.CHANGED_FACTS],
                         [f for f in FROZEN["facts"] if f["id"] not in self.CHANGED_FACTS])
        self.assertEqual([s for s in composed["steps"] if s["id"] != "klaeren"], [s for s in FROZEN["steps"] if s["id"] != "klaeren"])
        self.assertEqual({k: {f: x for f, x in v.items() if f != "needs"} for k, v in composed["forms"].items() if k != "A5"},
                         {k: v for k, v in FROZEN["forms"].items() if k != "A5"})
        self.assertEqual((composed["forms"]["A1"]["needs"], composed["forms"]["A8"]["needs"]), ([], ["deckung", "vorgehen"]))
        self.assertEqual(composed["short_title"], "Mietmangel")
        self.assertEqual(composed["action_kinds"]["A1"]["depends_on"], [])  # the cover decision does not block the first request
        self.assertIn("deckung", composed["action_kinds"]["A5"]["depends_on"])

    def test_items_and_letters_are_unchanged_on_the_handler_workflow_cases_apart_from_the_new_facts(self):
        old, new = workflows.validate_workflow(copy.deepcopy(FROZEN)), area.workflow("mietmangel-handler")
        base = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja"), fact("will_schadenersatz", "nein"),
                fact("streit_mietzins", "nein")]
        cases = [(base, [document("mietvertrag")]), ([fact("rechtsgebiet", "Mietrecht / Mangel"), fact("mangel_gemeldet", True)], []),
                 (base + [fact("bisherige_handlungen", "A1 2024-02-20; A2 2024-03-18")], [document("mietvertrag")]),
                 (base + [fact("handlung_a1", "2024-03-12")], []),
                 (base + [fact("handlung_a1", "2024-09-11"), fact("handlung_a5", "2024-10-18")], [document("mietvertrag")]),
                 (base + [fact("bisherige_handlungen", "A1 2024-08-28; A4 2024-09-10"), fact("deckung", "bestätigt")],
                  [document(d) for d in ("mietvertrag", "maengelruege", "fotos")])]
        looked = [{"name": "Schadenmeldung.pdf", "extraction": {"cut_of": {"as_of": "2025-02-07"}, "segments": [{"date": "18.10.2024"}]}}]
        case = {"id": "case_example", "title": "Schimmel (synthetisch) 1234.5678.9012", "intake": {}}
        # what an expert judges (the hashed fields) and what the screen says; a fact the new transitions branch on now
        # names its stage (node, chain), which explains an item and is not hashed
        kept = lambda rows: [{k: i.get(k) for k in HASHED + ("label", "legal_basis", "reason")} for i in rows if i["key"] not in self.CHANGED_FACTS]
        for facts, documents in cases:
            result = {"facts": facts, "documents": documents, "brief": {"request": "Schimmel.", "parties": [], "timeline": []}}
            a, b = (build_items(core.evaluate(w, [], [], result, "c", files=looked), result, looked) for w in (old, new))
            self.assertEqual(kept(a), kept(b))
            self.assertEqual(items_sha256([i for i in a if i["key"] not in self.CHANGED_FACTS]),
                             items_sha256([i for i in b if i["key"] not in self.CHANGED_FACTS]))
            for kind in ("A1", "A4", "A6", "A7", "A8", "A10", "A12"):
                ctx = letters.context(case, a, [], {"due": "2025-03-01"})
                self.assertEqual(letters.render(kind, old["forms"], ctx), letters.render(kind, new["forms"], ctx), kind)

    def test_every_shipped_area_is_valid_draft_cited_and_labelled(self):
        rows = area.shipped()
        self.assertEqual(len(rows), 10)
        for w in rows:
            self.assertEqual(w["status"], "draft")
            practice = w["id"] == "mietmangel-handler"
            self.assertEqual(w["area"]["label"], "aus Praxis und Gesetz abgeleitet, noch nicht freigegeben" if practice
                             else "aus dem Gesetz abgeleitet, noch nicht freigegeben")
            for row in w["law"].values():
                self.assertTrue(row["passage"] and len(row["passage"].split()) <= 40, row)
            if not practice:  # no observed counts outside the area that was observed
                self.assertNotRegex(json.dumps({k: v for k, v in w.items() if k != "law"}, ensure_ascii=False), r"\d+of\d+|\d+ von 7")

    def test_a_module_that_cites_law_without_its_passage_is_refused(self):
        bb = area.backbone()

        def refused(change):
            data = module("miete-kuendigung")
            change(data)
            with self.assertRaises(CatalogueError):
                area.compose(bb, data)
        refused(lambda m: m["law"]["273"].__setitem__("passage", ""))
        refused(lambda m: m["law"].pop("266o"))  # still cited in a document's reason and a hint
        refused(lambda m: m["hints"].append({"id": "x", "when": True, "text": "Siehe Art. 274g OR.", "source_refs": ["law#273"]}))
        refused(lambda m: m["documents"][0].__setitem__("source_refs", ["law#999"]))
        refused(lambda m: m["law"]["273"].__setitem__("passage", "Wort " * 41))
        refused(lambda m: m["law"]["273"].pop("verified"))
        refused(lambda m: m["documents"][0].__setitem__("why", "Verlangt in 3 von 7 Dossiers."))  # no invented practice counts
        refused(lambda m: m["deadlines"][0].__setitem__("trigger", "gegenpartei"))  # a deadline runs from a date
        area.compose(bb, module("miete-kuendigung"))

    def test_the_command_validates_and_describes_the_areas(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            area.main([str(area.AREAS / "vertrag-darlehen.json")])
        self.assertIn("vertrag-darlehen 2026-11-14.1 · Darlehen · aus dem Gesetz abgeleitet, noch nicht freigegeben", out.getvalue())
        self.assertIn("Rückzahlung des Darlehens ohne vereinbarten Termin (Art. 318 OR)", out.getvalue())


class CooperationTests(unittest.TestCase):
    """Lack of cooperation is silence after two requests with a deadline, never a reply that left documents missing."""

    def setUp(self):
        wf = area.workflow("mietmangel-handler")
        wf["documents"].append({"id": "korrespondenz", "title": "Sämtliche Korrespondenz mit der Verwaltung", "why": "Zeigt den Verlauf.",
                                "source_refs": ["practice#7of7"]})
        next(s for s in wf["steps"] if s["id"] == "klaeren")["documents"].append("korrespondenz")
        self.wf = workflows.validate_workflow(wf)
        self.answered = [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("deckung", "bestätigt"), fact("maengelruege_schriftlich", "ja"),
                         fact("will_schadenersatz", "nein"), fact("streit_mietzins", "nein")]

    def next_action(self, workflow, facts, documents, segments, as_of):
        files = [{"name": "Akte.pdf", "extraction": {"cut_of": {"as_of": as_of}, "segments": segments}}]
        result = {"facts": facts, "documents": documents, "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}}
        state = core.evaluate(workflow, [], [], result, "c", files=files)
        items = build_items(state, result, files)
        return state, items, {i["item_id"]: i for i in items}["next_action:0"]

    def test_a_reply_that_left_documents_missing_goes_to_the_assessment_which_asks_for_them(self):
        facts = self.answered + [fact("handlung_a1", "2024-03-01"), fact("handlung_a4", "2024-03-20")]
        documents = [document("maengelruege"), document("korrespondenz")]  # the open-ended need is partly there
        segments = [{"date": "20.03.2024", "sender": "Protekta Rechtsschutz AG"}, {"date": "28.03.2024", "sender": "Anna Beispiel"}]
        state, items, nxt = self.next_action(self.wf, facts, documents, segments, "2024-04-10")
        self.assertEqual((state["evaluation"]["current"] or {}).get("step"), "beurteilen")
        self.assertEqual(nxt["action"], "A5")
        self.assertFalse(state["facts"]["mitwirkung_fehlt"])
        text, _ = letters.render("A5", self.wf["forms"], letters.context({"id": "c", "title": "x", "intake": {}}, items, [], {"due": "2024-05-10"}))
        self.assertIn("Bitte reichen Sie uns noch nach:\n– Mietvertrag\n– Fotos des Mangels\n– Sämtliche Korrespondenz mit der Verwaltung", text)
        frozen = copy.deepcopy(FROZEN)  # the former rule ended benefits here: two requests and documents still missing
        frozen["documents"].append(self.wf["documents"][-1])
        next(s for s in frozen["steps"] if s["id"] == "klaeren")["documents"].append("korrespondenz")
        self.assertEqual(self.next_action(workflows.validate_workflow(frozen), facts, documents, segments, "2024-04-10")[2]["action"], "A12")

    def test_two_requests_with_a_deadline_met_with_silence_end_benefits_and_anything_received_prevents_it(self):
        facts = self.answered + [fact("handlung_a1", "2024-01-10"), fact("handlung_a6", "2024-02-20")]
        before = [{"date": "05.01.2024", "sender": "Anna Beispiel"}, {"date": "20.02.2024", "sender": "Protekta Rechtsschutz AG"}]
        state, _, nxt = self.next_action(self.wf, facts, [], before, "2024-04-01")  # the A6 deadline (25 days) has passed
        self.assertTrue(state["facts"]["mitwirkung_fehlt"])
        self.assertEqual((nxt["action"], state["evaluation"]["outcome"]["id"]), ("A12", "mitwirkung"))
        replied = before + [{"date": "01.03.2024", "sender": "Anna Beispiel"}]
        state, _, nxt = self.next_action(self.wf, facts, [], replied, "2024-04-01")
        self.assertFalse(state["facts"]["mitwirkung_fehlt"])
        self.assertNotEqual(nxt["action"], "A12")
        early = self.next_action(self.wf, facts, [], before, "2024-03-10")  # the last deadline has not passed yet
        self.assertFalse(early[0]["facts"]["mitwirkung_fehlt"])
        asked_back = self.answered + [fact("handlung_a1", "2024-01-10"), fact("handlung_a4", "2024-02-20")]  # A4 sets no deadline
        self.assertFalse(self.next_action(self.wf, asked_back, [], before, "2024-06-01")[0]["facts"]["mitwirkung_fehlt"])
        self.assertFalse(core.evaluate(self.wf, [], [], {"facts": facts, "documents": []}, "c")["facts"]["mitwirkung_fehlt"])  # files unknown


class DeadlineTests(unittest.TestCase):
    def deadline(self, period, **extra):
        return {"id": "d", "title": "T", "trigger": "t", "period": period, "basis": "Art. 273 Abs. 1 OR", "missed": "m", **extra}

    def test_periods_follow_the_verified_counting_rules(self):
        compute = area.compute_deadline
        self.assertEqual(compute(self.deadline({"days": 30}), "2026-11-03")[0], "2026-12-03")  # receipt day not counted
        self.assertEqual(compute(self.deadline({"days": 30}), "2026-10-22")[0], "2026-11-23")  # Saturday 21.11. → Monday
        self.assertEqual(compute(self.deadline({"days": 30}), "2026-10-23")[0], "2026-11-23")  # Sunday 22.11. → Monday
        self.assertEqual(compute(self.deadline({"days": 30}), "23.10.2026")[0], "2026-11-23")
        self.assertEqual(compute(self.deadline({"weeks": 6}), "2026-10-02")[0], "2026-11-13")  # same weekday
        self.assertEqual(compute(self.deadline({"months": 1}), "2025-01-31")[0], "2025-02-28")  # no 31st: the month's last day
        self.assertEqual(compute(self.deadline({"years": 1}), "2028-02-29")[0], "2029-02-28")
        self.assertEqual(compute(self.deadline({"years": 2}), "2026-09-20")[0], "2028-09-20")
        self.assertEqual(compute(self.deadline({"days": 0}, shift=False), "2027-01-02"),
                         ("2027-01-02", "am 02.01.2027; fällt auf ein Wochenende, prüfen; kantonale Feiertage nicht berücksichtigt"))
        self.assertEqual(compute(self.deadline({"years": 1}, direction="ab", shift=False), "2026-09-30")[0], "2027-09-30")

    def test_what_cannot_be_computed_says_pruefen(self):
        compute = area.compute_deadline
        self.assertEqual(compute(self.deadline("sofort"), "2026-11-05")[0], "prüfen")
        self.assertEqual(compute(self.deadline({"days": 30}), "2026-11")[0], "prüfen")  # only a month: no date is invented
        self.assertEqual(compute(self.deadline({"days_before": 60}), "2027-03-31")[0], "prüfen")
        conditional = self.deadline({"days": 30}, when={"fact": "befristet", "is": False})
        self.assertIsNone(compute(conditional, "2026-11-03", {"befristet": True}))
        self.assertIn("noch offenen Voraussetzung", compute(conditional, "2026-11-03", {})[1])

    def test_a_deadline_is_asked_and_hinted_while_its_trigger_is_open_and_computed_once_it_is_known(self):
        wf = area.workflow("miete-kuendigung")
        open_ = {"facts": [fact("rechtsgebiet", "Mietrecht / Kündigung")], "documents": []}
        listed = {i["item_id"]: i for i in build_items(core.evaluate(wf, [], [], open_, "c"), open_)}
        self.assertEqual(listed["letter_question:kuendigung_erhalten"]["value"], "Wann haben Sie die Kündigung erhalten?")
        self.assertIn("Möglicherweise läuft eine gesetzliche Frist", listed["hint:frist-anfechtung"]["value"])
        self.assertNotIn("deadline:anfechtung", listed)
        known = {"facts": open_["facts"] + [fact("kuendigung_erhalten", "2026-11-03")], "documents": []}
        listed = {i["item_id"]: i for i in build_items(core.evaluate(wf, [], [], known, "c"), known)}
        row = listed["deadline:anfechtung"]
        self.assertEqual((row["value"], row["stated_as"], row["legal_basis"], row["stated"]), ("2026-12-03", "computed", "Art. 273 Abs. 1 OR", "2026-11-03"))
        self.assertNotIn("hint:frist-anfechtung", listed)
        self.assertNotIn("letter_question:kuendigung_erhalten", listed)


class RoutingTests(unittest.TestCase):
    def test_with_the_deployed_intakes_every_area_joins_and_each_value_routes_to_its_area(self):
        full = catalogue(*intakes("osm-mold", "osm-loan", "osm-fallback"))
        self.assertEqual(sorted(w["id"] for w in full.routable()), sorted(w["id"] for w in area.shipped()))
        self.assertIsNotNone(full.get("osm-loan"))  # superseded intakes stay readable for stored runs
        for w in area.shipped():
            decision = workflows.route(full, {"rechtsgebiet": w["applies_when"]["is"]})
            self.assertEqual(decision["workflow"]["id"], w["id"])
        nothing = workflows.route(full, {})
        self.assertEqual((nothing["status"], nothing["workflow"]["id"], nothing["needs"]), ("fallback", "allgemein", ["rechtsgebiet"]))
        self.assertEqual(len(nothing["candidates"]), 9)  # never "kein Prozess": the general one, the others named for a person
        self.assertEqual(workflows.route(full, {"rechtsgebiet": "Übriges Recht"})["workflow"]["id"], "allgemein")
        self.assertEqual(full.routing_facts()[0]["question"], "Um welches Rechtsgebiet und welches Anliegen geht es (z.B. «Mietrecht / Kündigung»)?")

    def test_an_area_file_in_the_catalogue_directory_is_composed_and_a_local_copy_wins(self):
        local = module("vertrag-darlehen")
        local["version"] = "2099-01-01.1"
        rows = catalogue(*intakes("osm-loan"), local)
        self.assertEqual(rows.get("vertrag-darlehen")["version"], "2099-01-01.1")  # the directory's own copy governs
        self.assertEqual(len([w for w in rows.workflows if w["id"] == "vertrag-darlehen"]), 1)

    def test_a_second_topic_that_is_another_areas_own_is_offered_beside_the_chosen_one(self):
        full = catalogue(*intakes("osm-mold", "osm-loan", "osm-fallback"))
        text = "Die Vermieterin hat mir gekündigt. Ausserdem ist seit Monaten Schimmel im Bad."
        files = [{"id": "f1", "name": "m.txt", "kind": "text", "media_type": "text/plain", "extraction": {"text": text, "pages": None, "readable": True}}]
        model = ScriptedModel([], routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Kündigung", "citations": [{"file": "f1", "quote": "Die Vermieterin hat mir gekündigt."}]}],
                              other_topic=[{"topic": "Mietmangel", "file": "f1", "quote": "Ausserdem ist seit Monaten Schimmel im Bad."}])
        decision, workflow = core.route(model, full, {"title": "x", "intake": {}}, core.case_files(files), lambda e: None)
        self.assertEqual(workflow["id"], "miete-kuendigung")
        self.assertEqual([c["id"] for c in decision["candidates"]], ["mietmangel-handler"])


class SyntheticRunTests(unittest.TestCase):
    """Each shipped area, from a made-up case text to the first request, with the scripted model: no model, no API."""

    def run_case(self, wid, case):
        text = case["text"]
        cite = lambda quote: [{"file": "f1", "quote": quote}]
        routing = [{"fact": "rechtsgebiet", "value": case["routing"][0], "citations": cite(case["routing"][1])}] if case["routing"] else []
        # A handler's workflow defines the stages itself: the claim reader briefs and records in one turn, no process builder.
        model = ScriptedModel([
            [*[("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
             report("claim_reader", request=text.split(". ", 1)[1][:200])],
            [report("document_finder")],
            *[[report("result_checker", answer="Die erste Anforderung ist vorbereitet.")]] * 3,
        ], routing=routing)
        job = {"format": core.JOB, "case": {"id": f"case_{wid}", "title": f"{wid} (synthetisch) 1111.2222.3333", "intake": {}},
               "files": [{"id": "f1", "name": "schadenmeldung.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc",
                          "extraction": {"text": text, "pages": None, "readable": True, "note": ""}}],
               "workflows": list(catalogue(*intakes("osm-mold", "osm-loan", "osm-fallback")).workflows), "knowledge": [], "edits": [],
               "options": {"read_scans": True}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        return outcome

    def test_the_run_and_the_opened_case_agree_when_what_arrived_decides_the_stage(self):
        text = ("SYNTHETISCHER FALL. Protekta forderte am 1. März 2024 Unterlagen an und fragte am 20. März 2024 nach. "
                "Die Mieterin antwortete am 28. März 2024 und schickte die Mängelrüge. Die Mängelrüge ging schriftlich an die Verwaltung. "
                "Schadenersatz verlangt sie nicht. Über den Mietzins wird nicht gestritten.")
        cite = lambda quote: [{"file": "f1", "quote": quote}]
        record = lambda f, v, q: ("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)})
        model = ScriptedModel([
            [record("handlung_a1", "2024-03-01", "Protekta forderte am 1. März 2024 Unterlagen an"),
             record("handlung_a4", "2024-03-20", "fragte am 20. März 2024 nach"),
             record("maengelruege_schriftlich", "ja", "Die Mängelrüge ging schriftlich an die Verwaltung."),
             record("will_schadenersatz", "nein", "Schadenersatz verlangt sie nicht."),
             record("streit_mietzins", "nein", "Über den Mietzins wird nicht gestritten."), report("claim_reader", request="Schimmel im Bad.")],
            [("record_document", {"document": "maengelruege", "status": "present", "files": ["f1"], "citations": cite("schickte die Mängelrüge"), "note": ""}),
             report("document_finder")],
            *[[report("result_checker", answer="Die Einschätzung ist vorbereitet.")]] * 3,
        ], routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Mangel", "citations": cite("schickte die Mängelrüge")}])
        segments = [{"first_page": 1, "last_page": 1, "kind": "Brief", "date": "20.03.2024", "sender": "Protekta Rechtsschutz AG", "recipient": "", "title": "", "summary": ""},
                    {"first_page": 1, "last_page": 1, "kind": "E-Mail", "date": "28.03.2024", "sender": "Anna Beispiel", "recipient": "", "title": "", "summary": ""}]
        extraction = {"text": text, "pages": None, "readable": True, "note": "", "segments": segments, "cut_of": {"as_of": "2024-04-10"}}
        edits = [{"id": "ed_1", "op": "set_fact", "args": {"fact": "deckung", "value": "bestätigt"}, "status": "active"}]  # the handler's decision
        job = {"format": core.JOB, "case": {"id": "case_r", "title": "Schimmel (synthetisch)", "intake": {}},
               "files": [{"id": "f1", "name": "akte.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc", "extraction": extraction}],
               "workflows": list(catalogue(*intakes("osm-mold")).workflows), "knowledge": [], "edits": edits, "options": {"read_scans": True}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        stored = outcome["result"]
        view = core.evaluate(area.workflow("mietmangel-handler"), [], edits, stored, "case_r", files=[{"extraction": extraction}])
        self.assertEqual(view["evaluation"]["current"]["step"], "beurteilen")  # the customer answered: the assessment, not A12
        self.assertEqual(stored["evaluation"]["current"]["step"], view["evaluation"]["current"]["step"])
        action = lambda evaluation: {i["item_id"]: i for i in build_items({**view, "evaluation": evaluation}, stored, [{"extraction": extraction}])}["next_action:0"]["action"]
        self.assertEqual(action(stored["evaluation"]), action(view["evaluation"]))
        self.assertEqual(action(view["evaluation"]), "A5")

    def test_every_area_ends_on_a_complete_first_request(self):
        self.assertEqual(set(CASES), {w["id"] for w in area.shipped()})
        for wid, case in CASES.items():
            with self.subTest(area=wid):
                outcome = self.run_case(wid, case)
                self.assertEqual(outcome["workflow"]["id"], wid)
                wf = area.workflow(wid)
                state = core.evaluate(wf, [], [], outcome["result"], f"case_{wid}")
                items = build_items(state, outcome["result"])
                listed = {i["item_id"]: i for i in items}
                self.assertEqual(listed["next_action:0"]["action"], "A1")
                for fid, value in case["deadlines"].items():
                    row = listed[f"deadline:{fid}"]
                    self.assertEqual((row["value"], row["stated_as"]), (value, "computed"))
                    self.assertTrue(row["legal_basis"].startswith("Art. "))
                case_row = {"id": f"case_{wid}", "title": f"{wid} (synthetisch) 1111.2222.3333", "intake": {}}
                text, none = letters.render("A1", wf["forms"], letters.context(case_row, items, [], {"due": "2026-12-05"},
                                                                               evaluation=state["evaluation"], process=state["process"]))
                self.assertIsNone(none)
                for part in ("Ihr Dossier ist unter der Referenz 1111.2222.3333 provisorisch registriert",
                             "brauchen wir insbesondere noch:", "allfällige weitere relevante Unterlagen und Informationen",
                             "Weiter bitten wir Sie um die Beantwortung folgender Fragen:",
                             "Betreffend die geschilderte Situation erlauben wir uns bereits folgende Hinweise:",
                             "Bitte senden Sie uns Kopien oder Scans", "selbst für die Einhaltung allfällig laufender Fristen zuständig",
                             "Für Ihre Kenntnisnahme und Bemühungen danken wir Ihnen bestens.", f"({case['hint']})"):
                    self.assertIn(part, text)
                for bad in ("{", "…", "\n\n\n", "[bitte ergänzen"):
                    self.assertNotIn(bad, text)
                for title in case["documents"]:
                    self.assertIn(f"– {title}", text)
                for fid in case["questions"]:
                    self.assertIn(f"– {listed[f'letter_question:{fid}']['value']}", text)
                for fid, value in case["deadlines"].items():
                    if value != "prüfen":
                        shown = ".".join(reversed(value.split("-")))
                        self.assertIn(f"«{listed[f'deadline:{fid}']['label']['de']}»: nach unserer Berechnung", text)
                        self.assertIn(shown, text)


if __name__ == "__main__":
    unittest.main()

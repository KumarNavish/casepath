"""General rules from re-scoring stored runs without a model: a stage is not skipped, every action has its German title,
several items of a kind are each their own entry, an item without a date, no dead ends, an answered offer waits, what
came in is read twice, and a stored run of the previous backbone opens under the new rules. Scripted and model-free."""
import copy
import itertools
import json
import re
import tempfile
import unittest

from casepath.agents import core, team
from casepath.process import area, incoming, letters, workflows
from casepath.process.items import build_items, kind_title
from casepath.process.workflows import Catalogue, CatalogueError
from tests.scripted import ScriptedModel, report
from tests.test_areas import catalogue, intakes
from tests.test_handler_workflow import document

ANSWERED_CODE = re.compile(r"^A\d{1,2}$")
DEFECT = [("rechtsgebiet", "Mietrecht / Mangel"), ("maengelruege_schriftlich", "ja"), ("will_schadenersatz", "nein"), ("streit_mietzins", "nein")]
COMPLETE = ("mietvertrag", "maengelruege", "fotos")
MANDATE = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")]
HISTORY = "A1 2024-01-10; A5 2024-02-15; A10 2024-03-01"


def fact(fid, value, quote=None, page=None, file="f1"):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value,
            "citations": [{"file": file, "page": page, "quote": quote}] if quote else []}


def view(facts, history=None, documents=(), segments=None, as_of="2024-06-20", edits=(), wid="mietmangel-handler"):
    """The case as the screen shows it: (state, {item_id: item}, the next action)."""
    rows = [f if isinstance(f, dict) else fact(*f) for f in facts] + ([fact("bisherige_handlungen", history)] if history else [])
    segments = segments if segments is not None else [{"first_page": 1, "last_page": 1, "date": "01.03.2024", "sender": "Protekta"}]
    files = [{"id": "f1", "name": "Akte.pdf", "extraction": {"cut_of": {"as_of": as_of}, "segments": segments}}]
    result = {"facts": rows, "documents": [document(d) for d in documents], "brief": {"request": "Schimmel im Bad.", "parties": [], "timeline": []}}
    state = core.evaluate(area.workflow(wid), [], list(edits), result, "c", files=files)
    listed = {i["item_id"]: i for i in build_items(state, result, files)}
    return state, listed, listed.get("next_action:0")


def claim(n, day, extra="", page=None):
    fid = "eingang_kostenforderung" + ("" if n == 1 else f"_{n}")
    return fact(fid, f"Kanzlei Muster: Honorarnote {n} vom {day} über CHF {n}'000{extra}", f"Honorarnote {n} über CHF {n}'000", page)


class StageNotSkippedTests(unittest.TestCase):
    def test_a_customer_who_wants_action_but_has_no_assessment_is_at_assessing_with_a5_prepared(self):
        wants = DEFECT + [("deckung", "bestätigt"), ("weiteres_vorgehen", True)]
        for history in (None, "A1 2024-01-10"):  # complete at intake (no request needed) or after the first request
            state, _, nxt = view(wants, history, COMPLETE)
            self.assertEqual(state["evaluation"]["current"]["step"], "beurteilen")
            self.assertEqual(state["evaluation"]["current"]["held_for"], "A5")
            self.assertEqual((nxt["action"], nxt["value"], nxt["next_in_days"]), ("A5", "Rechtliche Einschätzung an die Kundschaft", 28))
            self.assertEqual(state["evaluation"]["gaps"][:1], [])  # held by its action, not a broken transition
        state, _, nxt = view(wants, "A1 2024-01-10; A5 2024-02-15", COMPLETE)  # the assessment is in the dated history
        self.assertEqual(state["evaluation"]["current"]["step"], "vorgehen")
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"], nxt["choices"]),
                         ("vorgehen", "Wie soll vorgegangen werden?", "vorgehen", ["Selbst führen", "Mandat an Anwaltskanzlei"]))
        forms = area.workflow("mietmangel-handler")["forms"]
        self.assertEqual(forms["vorgehen"]["needs"], ["vorgehen"])  # the decision is what blocks: [Selbst führen] [Mandat]
        self.assertIn("«Selbst führen» oder «Mandat an Anwaltskanzlei»", letters.render("vorgehen", forms, {})[1])
        self.assertEqual(view(wants, "A1 2024-01-10; A5", COMPLETE)[0]["evaluation"]["current"]["step"], "beurteilen")  # undated: not done
        self.assertEqual(view(wants + [("vorgehen", "Selbst führen")], "A1 2024-01-10", COMPLETE)[0]["evaluation"]["current"]["step"],
                         "gegenpartei")  # a handler decision places it beyond (the floor)

    def test_a_way_out_that_says_the_action_is_not_needed_is_taken_without_it(self):
        settled = DEFECT[:1] + [("reaktion_vermieter", "Mangel behoben / Einigung"), ("will_schadenersatz", False), ("streit_mietzins", False)]
        self.assertEqual(view(settled)[0]["evaluation"]["outcome"]["id"], "erledigt")  # no first request needed to close
        self.assertEqual(view(DEFECT + [("deckung", "abgelehnt")])[0]["evaluation"]["outcome"]["id"], "mitwirkung")
        steps = {s["id"]: s for s in area.workflow("mietmangel-handler")["steps"]}
        self.assertEqual([e["to"] for e in steps["beurteilen"]["next"] if e.get("without_action")], ["abschluss_still"])

    def test_every_stage_yields_an_action_kind_or_the_handlers_decision_and_the_validator_refuses_one_that_cannot(self):
        bb = area.backbone()
        for step in bb["steps"]:
            self.assertTrue(step.get("action", {}).get("kind") in bb["action_kinds"] or step.get("decision"), step["id"])
        for change in (lambda b: next(s for s in b["steps"] if s["id"] == "vorgehen").pop("decision"),
                       lambda b: next(s for s in b["steps"] if s["id"] == "beurteilen")["action"].__setitem__("kind", "request"),
                       lambda b: next(s for s in b["steps"] if s["id"] == "mandat")["action"].__setitem__("follow_up", "A99"),
                       lambda b: next(s for s in b["steps"] if s["id"] == "vorgehen")["decision"].__setitem__("fact", "weiteres_vorgehen")):
            broken = copy.deepcopy(bb)
            change(broken)
            with self.assertRaises(CatalogueError):
                area.validate_backbone(broken)


class TitleTests(unittest.TestCase):
    def test_every_action_kind_and_every_incoming_kind_shows_its_german_title_never_its_code(self):
        wf = area.workflow("mietmangel-handler")
        for kind in wf["action_kinds"]:
            self.assertNotRegex(kind_title(wf, kind), ANSWERED_CODE)
        for option in letters.action_options(wf, {"current": {"step": "mandat"}}, wf["forms"]):
            self.assertNotRegex(option["title"], ANSWERED_CODE)
        # the follow-up of a stage whose action is done, also one without a draft (the mandate's phone call, A2)
        _, _, nxt = view(MANDATE, HISTORY)
        self.assertEqual((nxt["action"], nxt["value"]), ("A2", "Stand bei der Kanzlei erfragen (Telefonnotiz)"))
        for kind in wf["incoming"]:  # each incoming kind, as the prepared action and as the case list's «Nächster Schritt»
            warned = [("mahnung_androhung", "Protekta: Aufforderung vom 2024-04-20 mit Androhung", "Androhung")] if kind["id"] == "mitwirkung" else []  # cover.py
            _, listed, nxt = view(MANDATE + warned + [(kind["fact"], f"Absender: Schreiben vom 2024-05-02 ({kind['id']})", "Schreiben")], HISTORY)
            self.assertEqual(nxt["incoming"]["kind"], kind["id"])
            self.assertNotRegex(nxt["label"]["de"], ANSWERED_CODE)
            self.assertEqual(nxt["label"]["de"], kind["action"]["title"])
        for history in ("A1 2024-01-10; A5 2024-02-15; A8 2024-03-01", "A1 2024-01-10; A5 2024-02-15; A10 2024-03-01; A11 2024-06-01"):
            for extra in ([], [("einigung", True)], [("einigung", True), ("zahlung_erhalten", True)]):
                facts = MANDATE[:2] + [("vorgehen", "Selbst führen" if "A8" in history else "Mandat an Anwaltskanzlei")] + extra
                self.assertNotRegex(view(facts, history)[2]["label"]["de"], ANSWERED_CODE)


class SeveralItemsTests(unittest.TestCase):
    def test_three_cost_claims_are_three_entries_and_the_oldest_open_one_is_prepared(self):
        claims = [claim(1, "2024-06-05"), claim(2, "2024-05-02"), claim(3, "2024-04-02")]  # latest first, as read
        state, _, nxt = view(MANDATE + claims, HISTORY)
        self.assertEqual((nxt["action"], nxt["incoming"]["fact"], nxt["incoming"]["date"]), ("A11", "eingang_kostenforderung_3", "2024-04-02"))
        self.assertEqual([(t["fact"], t["date"]) for t in nxt["then"]], [("eingang_kostenforderung_2", "2024-05-02"), ("eingang_kostenforderung", "2024-06-05")])
        self.assertEqual(nxt["evidence"][0]["quote"], "Honorarnote 3 über CHF 3'000")  # each item its own quote
        self.assertTrue(state["facts"]["kosten_offen"])

    def test_one_payment_after_all_claims_settles_one_not_all_and_the_file_can_show_each_settled(self):
        claims = [claim(1, "2024-05-02"), claim(2, "2024-04-02")]
        _, _, nxt = view(MANDATE + claims, HISTORY + "; A11 2024-05-20")  # one payment after both claims
        self.assertEqual((nxt["action"], nxt["incoming"]["fact"]), ("A11", "eingang_kostenforderung"))  # the later claim is still open
        self.assertNotIn("then", {k for k, v in nxt.items() if v})
        state, _, nxt = view(MANDATE + claims, HISTORY + "; A11 2024-05-20; A11 2024-05-28")
        self.assertNotIn("incoming", nxt)
        self.assertFalse(state["facts"]["kosten_offen"])
        paid = [claim(1, "2024-05-02", "; beglichen 2024-05-20"), claim(2, "2024-04-02", "; beglichen 2024-04-20")]  # the file shows each paid
        state, _, nxt = view(MANDATE + paid, HISTORY + "; A11 2024-04-20; A11 2024-05-20")
        self.assertFalse(state["facts"]["kosten_offen"])
        self.assertEqual(incoming.read_item("Honorarnote vom 2024-05-02; beglichen 2024-05-20")[0].isoformat(), "2024-05-02")
        _, _, nxt = view(MANDATE + [claim(1, "2024-05-02", "; beglichen 2024-05-20")], HISTORY)
        self.assertNotIn("incoming", nxt)  # the file's own record answers it, even before the history shows the payment

    def test_nothing_came_in_costs_nothing_and_a_kind_reads_at_most_three_items(self):
        state, listed, nxt = view(MANDATE, HISTORY)
        self.assertNotIn("incoming", nxt)
        self.assertEqual(incoming.items(area.workflow("mietmangel-handler"), state["facts"]), [])
        for kind in area.backbone()["incoming"]:
            self.assertLessEqual(len(incoming.slots(kind)), incoming.MAX_ITEMS)
        bb = area.backbone()
        bb["incoming"][2]["earlier"] = bb["incoming"][2]["earlier"] + ["eingang_bericht"]
        with self.assertRaises(CatalogueError):
            area.validate_backbone(bb)


class UndatedItemTests(unittest.TestCase):
    SEGMENTS = [{"first_page": 1, "last_page": 1, "date": "10.01.2024", "sender": "Protekta"},
                {"first_page": 2, "last_page": 2, "date": "02.05.2024", "sender": "Kanzlei Muster"},
                {"first_page": 3, "last_page": 3, "date": "", "sender": "Kanzlei Muster"},
                {"first_page": 4, "last_page": 4, "date": "20.05.2024", "sender": "Protekta"}]

    def undated(self, page):
        return fact("eingang_kostenforderung", "Kanzlei Muster: Schlussrechnung über CHF 4'100", "Schlussrechnung CHF 4'100", page)

    def test_an_item_without_a_date_takes_its_documents_date_and_is_answered_only_after_it(self):
        _, _, nxt = view(MANDATE + [self.undated(2)], HISTORY + "; A11 2024-04-30", segments=self.SEGMENTS)
        self.assertEqual((nxt["action"], nxt["incoming"]["date"], nxt["incoming"]["dated_by"]), ("A11", "2024-05-02", "document"))
        self.assertIn("vom 02.05.2024 (Datum des Schreibens in der Akte)", nxt["reason"])
        self.assertNotIn("incoming", view(MANDATE + [self.undated(2)], HISTORY + "; A11 2024-05-10", segments=self.SEGMENTS)[2])

    def test_a_document_without_a_date_is_bounded_by_its_dated_neighbours_and_otherwise_waits_for_the_handler(self):
        _, _, nxt = view(MANDATE + [self.undated(3)], HISTORY + "; A11 2024-05-10", segments=self.SEGMENTS)
        self.assertEqual(nxt["incoming"]["date"], "2024-05-20")  # between 02.05. and 20.05.: only an action after 20.05. answers it
        self.assertNotIn("incoming", view(MANDATE + [self.undated(3)], HISTORY + "; A11 2024-05-25", segments=self.SEGMENTS)[2])
        nowhere = view(MANDATE + [self.undated(None)], HISTORY + "; A11 2024-06-01", segments=self.SEGMENTS)[2]
        self.assertIsNone(nowhere["incoming"]["date"])  # no page, no date: no action answers it
        marked = [{"id": "e1", "op": "set_fact", "status": "active", "args": {"fact": "eingang_erledigt_bis", "value": "2024-06-01"}}]
        self.assertNotIn("incoming", view(MANDATE + [self.undated(None)], HISTORY, segments=self.SEGMENTS, edits=marked)[2])


class DeadEndTests(unittest.TestCase):
    def test_the_settlement_stage_with_a_cost_claim_open_prepares_the_claim_then_closes(self):
        settled = MANDATE + [("einigung", True), ("zahlung_erhalten", True)]
        state, _, nxt = view(settled + [claim(1, "2024-06-05")], HISTORY + "; A11 2024-06-03")
        self.assertEqual((state["evaluation"]["current"]["step"], nxt["action"], nxt["value"]), ("abwicklung", "A11", "Kostenforderung prüfen und begleichen"))
        state, _, nxt = view(settled + [claim(1, "2024-06-05")], HISTORY + "; A11 2024-06-03; A11 2024-06-12")
        self.assertEqual((state["evaluation"]["outcome"]["id"], nxt["action"], nxt["form"]), ("zahlung", "A12", "A12_erledigt"))

    def test_no_combination_leaves_a_case_without_a_named_next_step(self):
        histories = ["", "A1 2024-01-10", "A1 2024-01-10; A5 2024-02-15", "A1 2024-01-10; A5 2024-02-15; A8 2024-03-01",
                     "A1 2024-01-10; A5 2024-02-15; A10 2024-03-01", "A1 2024-01-10; A5 2024-02-15; A8 2024-03-01; A11 2024-06-10",
                     "A1 2024-01-10; A5 2024-02-15; A10 2024-03-01; A11 2024-06-10"]
        wf = area.workflow("mietmangel-handler")
        kinds = set(wf["action_kinds"]) | {"vorgehen"}
        seen = set()
        for history, cover, way, wants, settled, paid, cost in itertools.product(
                histories, ("bestätigt", None), ("Selbst führen", "Mandat an Anwaltskanzlei", None), (True, False), (True, None),
                (True,), (True, False)):
            facts = DEFECT + [(k, v) for k, v in (("deckung", cover), ("vorgehen", way), ("weiteres_vorgehen", wants), ("einigung", settled),
                                                  ("zahlung_erhalten", paid)) if v is not None]
            if cost:
                facts.append(claim(1, "2024-06-05"))
            state, _, nxt = view(facts, history or None, COMPLETE)
            ev = state["evaluation"]
            here = (ev["current"] or {}).get("step") or ev["path"][-1]["step"]
            seen.add(here)
            self.assertIsNotNone(nxt, (history, facts))
            self.assertIn(nxt["action"], kinds, (here, nxt["action"]))
            self.assertNotRegex(nxt["label"]["de"], ANSWERED_CODE)
            if cost and "A11 2024-06-10" not in history:  # never closes while a cost claim is open
                self.assertNotEqual((ev["outcome"] or {}).get("id"), "zahlung")
        self.assertLessEqual({"klaeren", "beurteilen", "vorgehen", "gegenpartei", "mandat", "abwicklung", "abschluss_zahlung"}, seen)

    def test_the_validator_refuses_a_dead_end_in_the_composed_workflow(self):
        mod = json.loads((area.AREAS / "arbeit-zeugnis.json").read_text())
        for change in (lambda b: next(s for s in b["steps"] if s["id"] == "abwicklung").__setitem__(
                           "next", [{"to": "abschluss_zahlung", "label": "x", "when": {"all": [{"fact": "kosten_offen", "is": True}, {"fact": "kosten_offen", "is": False}]}}]),
                       lambda b: next(s for s in b["steps"] if s["id"] == "mandat").__setitem__("next", []),
                       lambda b: b["incoming"][2]["action"].__setitem__("kind", "A2")):  # the claim's own action would never answer it
            bb = area.backbone()
            change(bb)
            with self.assertRaises(CatalogueError):
                area.compose(bb, mod)


class AnsweredOfferTests(unittest.TestCase):
    OWN = [("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Selbst führen"),
           ("eingang_angebot", "Anwalt der Vermieterin: Vergleichsangebot CHF 1'500, Schreiben vom 2024-05-10", "per Saldo CHF 1'500")]
    SEGMENTS = [{"first_page": 1, "last_page": 1, "date": "10.05.2024", "sender": "Anwalt der Vermieterin"}]

    def test_after_the_offer_is_answered_the_stage_waits_for_what_comes_next_or_the_clock(self):
        _, _, nxt = view(self.OWN, "A1 2024-01-10; A5 2024-02-15; A8 2024-04-20", segments=self.SEGMENTS, as_of="2024-05-12")
        self.assertEqual((nxt["action"], nxt["value"]), ("A9", "Antwort auf das Angebot der Gegenpartei"))
        _, _, nxt = view(self.OWN, "A1 2024-01-10; A5 2024-02-15; A8 2024-04-20; A9 2024-05-14", segments=self.SEGMENTS, as_of="2024-05-20")
        self.assertEqual((nxt["action"], nxt["value"], nxt["next_in_days"], nxt["since"]),
                         ("A9", "Antwort der Gegenpartei abwarten (ohne Antwort: mahnen)", 14, "2024-05-14"))  # waits, dated
        self.assertNotIn("incoming", nxt)
        _, _, nxt = view(self.OWN, "A1 2024-01-10; A5 2024-02-15; A8 2024-04-20; A9 2024-05-14", segments=self.SEGMENTS, as_of="2024-06-05")
        self.assertEqual((nxt["action"], nxt["value"]), ("A9", "Gegenpartei mahnen"))  # the clock: nothing came in for 14 days
        self.assertIn("keine Antwort seit A9 vom 14.05.2024", nxt["reason"])
        again = self.OWN[:3] + [("eingang_angebot", "Anwalt der Vermieterin: neues Angebot CHF 2'000, Schreiben vom 2024-06-01", "CHF 2'000"),
                                ("eingang_angebot_2", self.OWN[3][1], self.OWN[3][2])]
        _, _, nxt = view(again, "A1 2024-01-10; A5 2024-02-15; A8 2024-04-20; A9 2024-05-14", segments=self.SEGMENTS, as_of="2024-06-05")
        self.assertEqual((nxt["value"], nxt["incoming"]["date"]), ("Antwort auf das Angebot der Gegenpartei", "2024-06-01"))  # the next item


class SecondReadingTests(unittest.TestCase):
    def work(self, recorded):
        files = [{"id": "f1", "name": "akte.txt", "kind": "text", "text": "Honorarnote vom 2. Mai 2024.", "pages": None, "readable": True}]
        w = team.CaseWork(case={"id": "c", "title": "x", "intake": {}}, files=files, base_workflow=area.workflow("mietmangel-handler"))
        w.facts.update(recorded)
        return w

    def test_what_came_in_is_read_a_second_time_in_the_one_call_already_made_and_compared_by_its_date(self):
        ids = lambda w: {f["id"] for f in team.gating_facts(w)}
        plain = ids(self.work({}))
        self.assertLessEqual({"eingang_kostenforderung", "eingang_angebot", "eingang_zahlung", "eingang_bericht", "eingang_mitwirkung"}, plain)
        self.assertNotIn("eingang_kostenforderung_2", plain)  # an earlier slot only when the first reading found one
        found = {"eingang_kostenforderung_2": {"fact": "eingang_kostenforderung_2", "status": "established", "value": "x 2024-04-02", "citations": []}}
        self.assertIn("eingang_kostenforderung_2", ids(self.work(found)))
        definition = {"id": "eingang_kostenforderung", "type": "text"}
        self.assertTrue(team.same_reading(definition, "Kanzlei Muster: Zwischenrechnung vom 2024-05-02, CHF 3'200",
                                          "Zwischenhonorar der Kanzlei Muster AG, 2024-05-02"))  # same item, other words
        self.assertFalse(team.same_reading(definition, "Kanzlei Muster: Rechnung vom 2024-05-02", "Kanzlei Muster: Rechnung vom 2024-06-02"))

    def test_a_scripted_run_makes_one_second_reading_and_a_disagreement_keeps_the_item_open(self):
        text = "SYNTHETISCHE AKTE. Kanzlei Muster stellt mit Honorarnote vom 2. Mai 2024 CHF 3'200 in Rechnung."
        cite = [{"file": "f1", "quote": "Kanzlei Muster stellt mit Honorarnote vom 2. Mai 2024 CHF 3'200 in Rechnung."}]
        record = ("record_fact", {"part": None, "fact": "eingang_kostenforderung", "status": "established",
                                  "value": "Kanzlei Muster: Honorarnote vom 2024-05-02 über CHF 3'200", "citations": cite})
        calls = []

        class Counting(ScriptedModel):
            def respond_json(self, **kwargs):
                calls.append(kwargs["name"])
                if kwargs["name"] == "casepath_confirm_facts":
                    calls.append(sorted(f["id"] for f in json.loads(kwargs["input"][0]["content"])["facts"] if f["id"].startswith("eingang_")))
                return super().respond_json(**kwargs)
        model = Counting([[record, report("claim_reader", request="Kostennote.")], [report("document_finder")],
                          *[[report("result_checker", answer="Vorbereitet.")]] * 3],
                         routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Mangel", "citations": cite}],
                         second_reading=[{"fact": "eingang_kostenforderung", "status": "established",
                                          "value": "Kanzlei Muster: Honorarnote vom 2024-06-02", "citations": cite}])
        job = {"format": core.JOB, "case": {"id": "case_k", "title": "Kosten (synthetisch)", "intake": {}},
               "files": [{"id": "f1", "name": "akte.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc",
                          "extraction": {"text": text, "pages": None, "readable": True, "note": ""}}],
               "workflows": list(catalogue(*intakes("osm-mold")).workflows), "knowledge": [], "edits": [], "options": {"read_scans": True}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        self.assertEqual(calls.count("casepath_confirm_facts"), 1)  # no model call beyond the second reading already made
        self.assertEqual(calls[calls.index("casepath_confirm_facts") + 1],
                         ["eingang_angebot", "eingang_bericht", "eingang_kostenforderung", "eingang_mitwirkung", "eingang_zahlung"])
        row = next(f for f in outcome["result"]["facts"] if f["fact"] == "eingang_kostenforderung")
        self.assertEqual(row["status"], "conflicting")
        state = core.evaluate(area.workflow("mietmangel-handler"), [], [], outcome["result"], "case_k")
        nxt = {i["item_id"]: i for i in build_items(state, outcome["result"])}["next_action:0"]
        self.assertEqual(nxt["action"], "A11")  # a disagreement never hides what came in
        self.assertIn("eine zweite Lesung der Akte ergab «Kanzlei Muster: Honorarnote vom 2024-06-02», bitte prüfen", nxt["reason"])


class StoredRunTests(unittest.TestCase):
    def test_a_run_of_the_previous_backbone_opens_under_the_new_rules_and_the_new_facts_are_simply_not_established(self):
        rows = Catalogue(tuple(area.shipped()))
        self.assertIsNone(rows.get("mietmangel-handler", "2026-11-14.1"))
        governing = rows.get("mietmangel-handler", "2026-11-14.1") or rows.get("mietmangel-handler")  # as runner.case_state falls back
        self.assertEqual((governing["version"], governing["area"]["backbone"]), ("2026-11-15.1", "2026-11-15.1"))
        stored = {"facts": [fact(*f) for f in MANDATE] + [fact("bisherige_handlungen", HISTORY),
                                                         fact("eingang_kostenforderung", "Kanzlei Muster: Honorarnote vom 2024-05-02", "Honorarnote")],
                  "documents": [], "brief": {"request": "x", "parties": [], "timeline": []}}
        state = core.evaluate(governing, [], [], stored, "c")
        listed = {i["item_id"]: i for i in build_items(state, stored)}
        self.assertEqual(listed["next_action:0"]["action"], "A11")
        for slot in ("eingang_kostenforderung_2", "eingang_kostenforderung_3", "eingang_angebot_2", "eingang_zahlung_2"):
            self.assertEqual((listed[f"fact:{slot}"]["value"], listed[f"fact:{slot}"]["stated_as"]), (None, "unknown"))
            self.assertNotIn(slot, state["facts"])


class ScriptedRunTests(unittest.TestCase):
    """From the files to the case view: a first request, a mandate and the firm's cost note, no payment (scripted, no model)."""
    TEXT = ("SYNTHETISCHE AKTE. Protekta Rechtsschutz an Frau Lea Beispiel, 10. Januar 2024: Um die Versicherungsdeckung prüfen zu können, "
            "brauchen wir noch den Mietvertrag. "
            "Protekta Rechtsschutz an Kanzlei Muster, 1. März 2024: Wir erteilen Ihnen Kostengutsprache für die Abklärung der Sach- und Rechtslage. "
            "Kanzlei Muster an Protekta Rechtsschutz, 2. Mai 2024: Für unsere Bemühungen bis 30. April 2024 stellen wir Ihnen CHF 3'200 in Rechnung.")
    SEGMENTS = [{"first_page": 1, "last_page": 1, "kind": "Brief", "date": "10.01.2024", "sender": "Protekta Rechtsschutz AG", "recipient": "Lea Beispiel", "title": "Anforderung", "summary": ""},
                {"first_page": 2, "last_page": 2, "kind": "Brief", "date": "01.03.2024", "sender": "Protekta Rechtsschutz AG", "recipient": "Kanzlei Muster", "title": "Mandat", "summary": ""},
                {"first_page": 3, "last_page": 3, "kind": "Honorarnote", "date": "02.05.2024", "sender": "Kanzlei Muster", "recipient": "Protekta", "title": "Zwischenhonorar", "summary": ""}]

    def model(self):
        cite = lambda quote: [{"file": "f1", "quote": quote}]
        record = lambda f, v, q: ("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)})
        return ScriptedModel([
            [record("handlung_a1", "2024-01-10", "Protekta Rechtsschutz an Frau Lea Beispiel, 10. Januar 2024"),
             record("bisherige_handlungen", "A1 2024-01-10; A10 2024-03-01", "Wir erteilen Ihnen Kostengutsprache für die Abklärung der Sach- und Rechtslage."),
             record("eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorar vom 2024-05-02 über CHF 3'200 (Bemühungen bis 30.04.2024)",
                    "Für unsere Bemühungen bis 30. April 2024 stellen wir Ihnen CHF 3'200 in Rechnung."),
             report("claim_reader", request="Frau Beispiel lässt einen Mietmangel durch die Kanzlei Muster vertreten.")],
            [report("document_finder")],
            *[[report("result_checker", answer="Die Kostennote der Kanzlei ist zu prüfen.")]] * 3,
        ], routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Mangel", "citations": cite("brauchen wir noch den Mietvertrag.")}])

    def test_a_cost_note_of_the_mandated_firm_and_no_payment_prepares_the_cost_claim(self):
        extraction = {"text": self.TEXT, "pages": None, "readable": True, "note": "", "segments": self.SEGMENTS, "cut_of": {"as_of": "2024-05-20"}}
        job = {"format": core.JOB, "case": {"id": "case_k", "title": "Kostennote (synthetisch) 1234.5678.9012", "intake": {}},
               "files": [{"id": "f1", "name": "akte.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc", "extraction": extraction}],
               "workflows": list(catalogue(*intakes("osm-mold")).workflows), "knowledge": [], "edits": [], "options": {"read_scans": True}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job)), self.model(), core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        self.assertEqual(outcome["workflow"]["id"], "mietmangel-handler")
        files = [{"id": "f1", "name": "akte.txt", "extraction": extraction}]
        state = core.evaluate(area.workflow("mietmangel-handler"), [], [], outcome["result"], "case_k", files=files)
        self.assertEqual(state["evaluation"]["current"]["step"], "mandat")  # placed by the mandate in its history
        nxt = {i["item_id"]: i for i in build_items(state, outcome["result"], files)}["next_action:0"]
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"], nxt["next_in_days"]), ("A11", "Kostenforderung prüfen und begleichen", "A11_kosten", 30))
        self.assertEqual(nxt["reason"], "Kostenforderung vom 02.05.2024 eingegangen, noch offen – Kanzlei Muster: Zwischenhonorar über CHF 3'200 "
                                        "(Bemühungen bis 30.04.2024)")  # its own date once, as dd.mm.yyyy
        self.assertEqual(nxt["evidence"][0]["quote"], "Für unsere Bemühungen bis 30. April 2024 stellen wir Ihnen CHF 3'200 in Rechnung.")
        self.assertTrue(state["facts"]["kosten_offen"])


if __name__ == "__main__":
    unittest.main()

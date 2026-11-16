"""The substance of the assessment (A5): the customer's questions answered by the rule their tags name and the intent
their words ask, held for the handler where a guard does not trust the tag; the ways to proceed of the area's options file
with their conditions and review state, one proposed per wish, adopted or corrected by the handler; «In Ihrem Fall», the
claims and the residual request; the decisions that block the approval and the premise the letter rests on
(casepath/process/assessment.py, options.py, keypoints.status).

Scripted and model-free, on S-D11A, the synthetic analog of a development dossier (tests/episode.py); every name, amount
and sentence is invented."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from casepath.agents import core, team
from casepath.config import load_settings
from casepath.process import area, assessment, customer_letters, keypoints, letters, options, review, screen
from casepath.process.items import build_items
from casepath.process.workflows import CatalogueError
from casepath.web.app import create_app
from tests import episode as ep
from tests.scripted import ScriptedModel, claim, receipt, report

WID = ep.WID
NS = ep.EPISODE
FILES = [NS.dossier] + NS.files_b
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "questions" / "mietmangel-handler.json").read_text())
DECKUNG = ep.decided(("deckung", "bestätigt"))
_PREPARED = {}


def replied():
    """S-D11A after the two replies of d+35, as the scripted update leaves it: (prior run, result)."""
    if "result" not in _PREPARED:
        prior, _ = ep.prepared(NS)
        outcome, _ = ep.updated(prior, FILES, NS.turns_b(), NS)
        assert outcome["status"] == "completed", outcome.get("error")
        _PREPARED.update(prior=prior, result=outcome["result"])
    return copy.deepcopy(_PREPARED["result"])


NEUTRAL = {"file": "fb", "page": None, "start": 0, "end": 10, "quote": "Gerne beantworte ich"}


def changed(result, facts=None, questions=None, claims=None):
    """The result with facts changed as a reading would have them: a value (established and accepted, quoted where the
    run quoted the same value, else from the reply's first words), {value, status, quote?} for a presumed or contradictory
    reading or a value read from given words, None for unknown; the brief's questions and claims replaced where given."""
    rows = {f["fact"]: f for f in result["facts"]}
    for name, value in (facts or {}).items():
        if value is None:
            rows.pop(name, None)
            continue
        spec = value if isinstance(value, dict) else {"value": value, "status": "established"}
        old = rows.get(name) or {}
        same = old.get("value") == spec["value"]
        cites = ([{**NEUTRAL, "quote": spec["quote"]}] if spec.get("quote") else old.get("citations") if same and old.get("citations") else [NEUTRAL])
        rows[name] = {"fact": name, "status": spec["status"], "value": spec["value"], "citations": cites,
                      "verdict": "accepted" if spec["status"] == "established" else spec["status"], "by": "claim_reader"}
    result["facts"] = list(rows.values())
    if questions is not None:
        result["brief"]["questions"] = [ep.question("fb", text, about) for text, about in questions]
    if claims is not None:
        result["brief"]["claims"] = claims
    return result


class Case:
    """The case as its view builds it on the A5's day: state, items, brief, the prepared letter and the decision."""

    def __init__(self, result, edits=(), events=(), marks=None, day=None, files=None):
        files = ep.looked_at(files or FILES, day or NS.a5_day)
        self.result, self.events, self.marks = result, list(events), marks or {}
        self.state = core.evaluate(area.workflow(WID), [], list(edits), result, ep.case_row()["id"], files=files)
        self.items = build_items(self.state, result, files, self.events, self.marks)
        current = {**self.state, "case": ep.case_row(), "run": {"result": result}}
        self.brief = assessment.build(current, result, self.items, files, self.events, self.marks)
        self.draft = letters.draft(current, self.items, self.events, {"due": "2026-10-06"}, files, letters.SEED_FORMS,
                                   held=review.flags(self.state["process"], self.marks), assessment=self.brief)
        self.text = (self.draft or {}).get("text") or ""
        stage = ((self.state["evaluation"].get("current") or {}).get("step"))
        self.decision = screen.decision(self.items, self.draft, stage, assessment=self.brief)
        self.stage = stage

    def item(self, item_id):
        return next(i for i in self.items if i["item_id"] == item_id)

    def question(self, n):
        return self.brief["questions"][n]

    def option(self, option_id):
        return next(o for o in self.brief["options"] if o["id"] == option_id)

    def rule(self, rule_id):
        return next(r for r in self.brief["rules"] if r["id"] == rule_id)


def adopt(chosen, proposal, at="2026-09-08T10:00:00+00:00"):
    return {"kind": "item.corrected", "item_id": "point:empfehlung", "chosen": list(chosen), "proposal": list(proposal), "expert": "N. Kumar", "at": at}


def taken(n, point, intent=None):
    return {"kind": "item.corrected", "item_id": f"customer_question:{n}", "point": point, "intent": intent, "expert": "N. Kumar",
            "at": "2026-09-08T10:00:00+00:00"}


def asked(text, about=()):
    """One question in the S-D11A case, after the cover was confirmed: its row of the brief."""
    return Case(changed(replied(), questions=[(text, about)]), DECKUNG).question(0)


# -- the customer's questions ----------------------------------------------------------------------------------------------

class QuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = Case(replied(), DECKUNG)

    def test_a_question_tagged_with_a_point_that_applies_is_answered_by_its_intent(self):
        q = self.case.question(0)
        self.assertEqual((q["text"], q["state"], q["row"], q["points"], q["intent"]),
                         ("Muss ich weiterhin die volle Miete bezahlen?", "beantwortet", 10, ["hinterlegung"], "weiter_zahlen"))
        for words in ("vollständig zu bezahlen", "Zahlungsfrist", "(Art. 257d Abs. 1 OR)"):
            self.assertIn(words, q["answer"])
        self.assertEqual(self.case.item("customer_question:0")["answered_by"], "hinterlegung")
        self.assertIn(f"– «Muss ich weiterhin die volle Miete bezahlen?»: {q['answer']}", self.case.text)

    def test_a_question_whose_point_is_open_is_conditional_and_asks_the_missing_fact(self):
        case = Case(changed(replied(), facts={"will_schadenersatz": None}), DECKUNG)
        q = case.question(2)
        # changed with the precise questions (steering, point 2): the area's own question for the open fact, in the customer's
        # words, instead of the module's general «Was möchten Sie erreichen …?»
        customer = "Möchten Sie Ersatz für Kosten oder Schäden verlangen, die Ihnen der Mangel verursacht hat?"
        self.assertEqual((q["state"], q["row"], q["reason"], q["ask"]["fact"]), ("bedingt", 8, customer, "will_schadenersatz"))
        self.assertIn("kein Verschulden trifft (Art. 259e OR)", q["answer"])  # what the rule says, whatever the answer
        self.assertTrue(q["answer"].endswith(f"Das hängt noch von einer Angabe ab; bitte teilen Sie uns mit: {customer}"))
        ask = next(a for a in case.brief["asks"] if a["key"] == "fact:will_schadenersatz")
        self.assertEqual((ask["what"], ask["kind"], ask["ref"], ask["decides"]),
                         (customer, "fact", "will_schadenersatz", "die Antwort auf die Frage «Werden mir die Stromkosten für den Bautrockner ersetzt?»"))
        self.assertEqual((ask["blocks"]["question"], ask["blocks"]["option"]), ("customer_question:2", "schadenersatz"))
        self.assertEqual([(b["value"], b["proposal"]) for b in ask["branches"]],
                         [(True, ["Frist zur Beseitigung setzen", "Kosten belegen und Ersatz verlangen"]), (False, ["Frist zur Beseitigung setzen"])])
        self.assertIn("residual:claim.0", [a["key"] for a in case.brief["asks"]])  # the answer points to the receipts: asked below

    def test_a_keyword_alone_never_answers(self):
        # the probe: «hinterlegen» answered by the point on the reduction (its word «Miete») while the deposit's point is open
        facts = {"mangel_besteht": None, "will_reduktion": True}
        untagged = Case(changed(replied(), facts=facts, questions=[("Darf ich die Miete hinterlegen?", [])]), DECKUNG)
        q = untagged.question(0)
        self.assertEqual(keypoints.answer_for(q["text"], keypoints.evaluate(untagged.state["process"], untagged.state["facts"]))["id"], "reduktion")
        self.assertEqual((q["state"], q["row"], q["reason"], [o["point"] for o in q["offered"]]), ("pruefen", 1, "Vorschlag (Stichwort)", ["reduktion"]))
        self.assertIsNone(q["answer"])
        self.assertIn("– «Darf ich die Miete hinterlegen?»: [bitte ergänzen: Antwort auf diese Frage]", untagged.text)
        tagged = Case(changed(replied(), facts=facts, questions=[("Darf ich die Miete hinterlegen?", ["hinterlegung"])]), DECKUNG).question(0)
        self.assertEqual((tagged["state"], tagged["row"], tagged["reason"]), ("pruefen", 5, "Zuordnung prüfen"))
        self.assertEqual([o["point"] for o in tagged["offered"]], ["reduktion"])  # the deposit's point is open: only the applying one is offered

    def test_a_question_rejecting_a_remedy_is_not_answered_by_it(self):
        text = "Ich will keine Reduktion. Muss ich die volle Miete weiter bezahlen?"
        wrong = asked(text, ["reduktion"])
        self.assertEqual((wrong["state"], wrong["row"], wrong["reason"]), ("pruefen", 3, "Verneinung: Zuordnung prüfen"))
        self.assertIsNone(wrong["answer"])
        right = asked(text, ["hinterlegung"])
        self.assertEqual((right["state"], right["intent"]), ("beantwortet", "weiter_zahlen"))  # the rule it asks about answers it

    def test_a_paraphrase_is_answered_through_its_tag(self):
        q = self.case.question(2)
        self.assertEqual(q["text"], "Werden mir die Stromkosten für den Bautrockner ersetzt?")
        applying = [p for p in keypoints.evaluate(self.case.state["process"], self.case.state["facts"]) if p["state"] == "applies"]
        self.assertIsNone(keypoints.answer_for(q["text"], applying))  # «ersetzt» holds no keyword of the point: the old path left a gap
        self.assertEqual((q["state"], q["row"], q["points"], q["intent"]), ("bedingt", 9, ["schadenersatz"], "ersatz"))
        self.assertIn("kein Verschulden trifft (Art. 259e OR)", q["answer"])
        self.assertIn("steht unten", q["answer"])
        self.assertEqual(q["reason"], "Belege zu: Stromkosten für den Bautrockner")  # what it waits for

    def test_the_full_rent_question_gets_the_rule_that_answers_it(self):
        self.assertNotIn("Siehe oben", self.case.text)  # the probe: no reference to a sentence that does not answer it
        q = self.case.question(0)
        self.assertTrue(q["answer"].startswith("Wir empfehlen Ihnen, den Mietzins bis auf Weiteres vollständig zu bezahlen."))
        point = next(p for p in keypoints.evaluate(self.case.state["process"], self.case.state["facts"]) if p["id"] == "hinterlegung")
        self.assertNotIn(point["follows"], q["answer"])  # never the generic rule sentence

    def test_an_unknown_tag_is_dropped_and_counted(self):
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        brief = team._located_brief(work, {"summary": "x", "questions": [
            {"question": "Darf ich die Miete hinterlegen?", "citations": [{"file": "fb", "quote": "Darf ich die Miete hinterlegen?"}],
             "about": ["hinterlegung", "unbekannt", "hinterlegung"]}], "claims": []})
        self.assertEqual((brief["questions"][0]["about"], brief["dropped_tags"]), (["hinterlegung"], 1))
        stored = asked("Darf ich die Miete hinterlegen?", ["unbekannt"])  # a stored tag naming no point: no valid tag
        self.assertEqual((stored["state"], stored["row"], stored["points"]), ("pruefen", 1, []))

    def test_a_wrong_tag_on_a_failing_point_with_an_applying_keyword_point_is_checked(self):
        q = asked("Darf ich die Miete hinterlegen?", ["meldung"])  # the notice was given in writing: the point fails
        self.assertEqual((q["state"], q["row"], q["reason"], [o["point"] for o in q["offered"]]), ("pruefen", 5, "Zuordnung prüfen", ["hinterlegung"]))
        self.assertIn("droht sie nicht an", q["offered"][0]["text"])  # the deposit's answer, offered, not stated

    def test_an_untagged_stored_question_keeps_its_gap_and_shows_the_keyword_proposal(self):
        result = replied()
        for q in result["brief"]["questions"]:
            q.pop("about")  # a run before the reader tagged
        case = Case(result, DECKUNG)
        rows = [(q["state"], q["row"], q["reason"]) for q in case.brief["questions"]]
        self.assertEqual(rows, [("offen", 2, "keine Regel des Gebiets"), ("pruefen", 1, "Vorschlag (Stichwort)"), ("offen", 2, "keine Regel des Gebiets")])
        self.assertEqual(case.question(1)["offered"][0]["point"], "hinterlegung")
        self.assertEqual(case.text.count("[bitte ergänzen: Antwort auf diese Frage]"), 3)
        self.assertEqual(case.item("customer_question:1")["answer_state"], "pruefen")

    def test_a_wrong_tag_on_a_negated_question_is_checked(self):
        q = asked("Ich möchte keine Hinterlegung, nur eine Herabsetzung. Wie gehe ich vor?", ["hinterlegung"])
        self.assertEqual((q["state"], q["row"], q["reason"]), ("pruefen", 3, "Verneinung: Zuordnung prüfen"))
        carried = asked("Darf ich die Miete nicht mehr zahlen, bis der Schimmel weg ist?", ["hinterlegung"])
        self.assertEqual((carried["state"], carried["intent"]), ("beantwortet", "zurueckbehalten"))  # the negation is the intent's own

    def test_a_tagged_point_whose_wish_is_false_is_checked(self):
        q = asked("Kann ich eine Herabsetzung der Miete verlangen?", ["reduktion"])  # «Eine Mietzinsreduktion möchte ich nicht.»
        self.assertEqual((q["state"], q["row"], q["reason"]), ("pruefen", 4, "Sie möchten eine Herabsetzung des Mietzinses nicht: Zuordnung prüfen"))
        self.assertEqual(q["offered"], [])  # its point does not apply: the handler writes the answer

    def test_a_tag_and_an_applying_keyword_that_disagree_are_checked(self):
        case = Case(changed(replied(), facts={"will_reduktion": True}), DECKUNG)
        q = case.question(0)
        self.assertEqual((q["state"], q["row"], q["reason"]), ("pruefen", 5, "Zuordnung prüfen"))
        self.assertEqual([o["point"] for o in q["offered"]], ["hinterlegung", "reduktion"])  # both answers
        self.assertTrue(all(o["text"] for o in q["offered"]))

    def test_mixed_tags_with_one_failing_are_checked_and_offer_the_applying_answer(self):
        q = asked("Wie gehe ich jetzt weiter vor?", ["meldung", "hinterlegung"])
        self.assertEqual((q["state"], q["row"], [o["point"] for o in q["offered"]]), ("pruefen", 6, ["hinterlegung"]))
        none = asked("Muss ich der Verwaltung den Schimmel nochmals melden?", ["meldung"])
        self.assertEqual((none["state"], none["row"], none["reason"]), ("offen", 6, "Regel trifft nach der Akte nicht zu"))

    def test_a_question_about_cutting_the_rent_gets_the_no_self_help_answer(self):
        case = Case(changed(replied(), facts={"will_reduktion": True}, questions=[("Darf ich die Miete ab sofort kürzen?", ["reduktion"])]), DECKUNG)
        q = case.question(0)
        self.assertEqual((q["state"], q["row"], q["intent"]), ("beantwortet", 10, "zurueckbehalten"))
        self.assertTrue(q["answer"].startswith("Wir empfehlen Ihnen, den Mietzins nicht eigenmächtig zu kürzen oder zurückzubehalten."))
        self.assertIn("das Mietverhältnis kündigen (Art. 257d Abs. 1 OR)", q["answer"])
        self.assertNotIn("Der Mietzins kann entsprechend der Beeinträchtigung herabgesetzt werden", q["answer"])

    def test_an_unmatched_intent_is_checked_with_the_rule_sentence_offered(self):
        q = asked("Bekomme ich das Geld für den Strom zurück?", ["schadenersatz"])
        self.assertEqual((q["state"], q["row"], q["reason"]), ("pruefen", 11, "Absicht der Frage unklar"))
        self.assertEqual(q["offered"][0]["text"], "Für den Schaden aus dem Mangel muss die Vermieterschaft Ersatz leisten, wenn sie nicht beweist, "
                                                  "dass sie kein Verschulden trifft (Art. 259e OR).")
        self.assertIsNone(q["answer"])

    def test_an_implied_fact_is_not_asked(self):
        case = Case(changed(replied(), questions=[("Muss ich der Verwaltung den Schimmel nochmals melden?", ["meldung"])]), DECKUNG)
        q = case.question(0)
        self.assertEqual((q["state"], q["ask"]), ("offen", None))  # «schriftlich gemeldet» settles «gemeldet»: nothing is asked
        self.assertFalse(any(a["kind"] == "fact" for a in case.brief["asks"]))
        self.assertNotIn("mangel_gemeldet", case.state["facts"])  # the case's facts are untouched
        self.assertEqual(options.implied(case.state["facts"], options.load(WID))["mangel_gemeldet"], True)

    def test_the_hinterlegung_answer_states_every_condition(self):
        q = self.case.question(1)
        self.assertEqual((q["state"], q["row"], q["reason"]), ("bedingt", 9, "vorher mit uns besprechen"))
        for words in ("schriftlich eine angemessene Frist", "androhen", "künftig fällig", "vom Kanton bezeichneten Stelle", "schriftlich ankündigen",
                      "Innert 30 Tagen", "Schlichtungsbehörde", "(Art. 259h OR)", "als bezahlt", "Zahlungsfrist", "das Mietverhältnis kündigen",
                      "(Art. 259g Abs. 2 OR, Art. 257d Abs. 1 OR)", "eine Hinterlegung droht sie nicht an",
                      "Wir empfehlen Ihnen, eine Hinterlegung vorher mit uns zu besprechen."):
            self.assertIn(words, q["answer"])

    def test_answer_recommendation_and_template_agree_on_the_androhung(self):
        template = next(i for i in self.case.items if i["kind"] == "customer_letter" and i["key"] == "maengelruege")["text"]
        body = template.split("Sehr geehrte Damen und Herren", 1)[1].split("Freundliche Grüsse", 1)[0]
        self.assertNotRegex(body.lower(), r"androh|hinterleg")  # the enclosed template sets a deadline and threatens no deposit
        default = self.case.brief["letter"]["empfehlung"]
        self.assertIn("die beigelegte Vorlage setzt diese Frist", default)
        self.assertNotIn("androh", default)
        self.assertIn("eine Hinterlegung droht sie nicht an", self.case.question(1)["answer"])
        # picked under «ändern»: the recommendation threatens the deposit and gives the sentence to add to the template
        proposal = self.case.brief["proposal"]
        picked = Case(replied(), DECKUNG + ep.decided(("aussichten", "genügend")), [adopt(["frist_androhung", "schadenersatz"], proposal)])
        recommendation = picked.brief["letter"]["empfehlung"]
        added = "«Bei unbenütztem Ablauf der Frist werde ich die künftig fällig werdenden Mietzinse bei der vom Kanton bezeichneten Stelle hinterlegen.»"
        self.assertIn("ihr dabei anzudrohen", recommendation)
        self.assertIn(f"ergänzen Sie dazu die beigelegte Vorlage nach dem Satz mit der Frist um den Satz {added}", recommendation)
        self.assertNotIn(added.strip("«»"), template)
        self.assertEqual(picked.question(1)["answer"], self.case.question(1)["answer"])  # the answer stands as it was
        self.assertEqual(picked.brief["chosen"], ["frist_androhung", "schadenersatz"])

    def test_a_drafted_answer_is_taken_with_one_click(self):
        result = changed(replied(), questions=[("Darf ich die Miete hinterlegen?", ["meldung"])])
        before = Case(result, DECKUNG)
        self.assertEqual(before.question(0)["state"], "pruefen")
        after = Case(result, DECKUNG, [taken(0, "hinterlegung", "hinterlegen")])
        q = after.question(0)
        self.assertEqual((q["state"], q["taken"], q["row"], q["reason"]), ("beantwortet", True, None, "beantwortet (Fallbearbeitung)"))
        self.assertEqual(q["answer"], before.question(0)["offered"][0]["text"])  # exactly what the chip offered
        self.assertIn(f"– «Darf ich die Miete hinterlegen?»: {q['answer']}", after.text)
        lapsed = Case(changed(result, facts={"mangel_besteht": False}), DECKUNG, [taken(0, "hinterlegung", "hinterlegen")])
        self.assertNotEqual(lapsed.question(0)["state"], "beantwortet")  # a taken answer stands only while its point applies


class QuestionTableTests(unittest.TestCase):
    """The question table (tests/fixtures/questions/mietmangel-handler.json): each row's scripted tags, expected state,
    guard row, points and intent, through the live code path."""

    def test_each_question_of_the_table_gets_its_state_row_points_and_intent(self):
        self.assertGreaterEqual(len(FIXTURE["rows"]), 30)
        for row in FIXTURE["rows"]:
            with self.subTest(row["id"]):
                case = Case(changed(replied(), facts=row.get("facts"), questions=[(row["text"], row["about"])]), DECKUNG)
                q = case.question(0)
                self.assertEqual((q["state"], q["row"], q["points"], q["intent"]), (row["state"], row["row"], row["points"], row["intent"]))
                if "offered" in row:
                    self.assertEqual([o["point"] for o in q["offered"]], row["offered"])
                if "ask" in row:
                    self.assertEqual(q["ask"]["fact"], row["ask"])
                if q["state"] in ("pruefen", "offen"):
                    self.assertIsNone(q["answer"])  # never stated in the letter until taken
                    self.assertIn(f"«{row['text']}»: [bitte ergänzen: Antwort auf diese Frage]", case.text)
                else:
                    self.assertTrue(q["answer"])
                    self.assertNotIn("Siehe oben", case.text)


# -- options and the recommendation -----------------------------------------------------------------------------------------

class OptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = Case(replied(), DECKUNG)

    def test_options_hold_on_accepted_facts_and_a_weak_one_is_written_with_its_condition(self):
        self.assertEqual(self.case.option("frist_beseitigung")["state"], "holds")
        weak = Case(changed(replied(), facts={"mangel_besteht": {"value": True, "status": "presumed"}}), DECKUNG)
        option = weak.option("frist_beseitigung")
        self.assertEqual((option["state"], option["weak"]), ("holds", ["mangel_besteht"]))
        self.assertTrue(weak.brief["letter"]["empfehlung"].startswith("sofern der Mangel weiterhin besteht, der Vermieterschaft schriftlich"))
        self.assertIn("Wir empfehlen Ihnen, sofern der Mangel weiterhin besteht, der Vermieterschaft", weak.text)
        self.assertNotIn("Der Mangel war nach Ihren Angaben", weak.text)  # a presumed value is never stated as the customer's
        conflicting = Case(changed(replied(), facts={"reaktion_vermieter": {"value": None, "status": "conflicting"}}), DECKUNG)
        state = next(c for c in conflicting.option("frist_beseitigung")["conditions"] if c["fact"] == "reaktion_vermieter")["state"]
        self.assertEqual((state, conflicting.option("frist_beseitigung")["state"]), ("widersprüchlich", "open"))
        self.assertNotIn("frist_beseitigung", conflicting.brief["proposal"])

    def test_the_proposal_is_one_holding_proposable_option_per_wish_by_practice_then_file_order(self):
        self.assertEqual(self.case.brief["proposal"], ["frist_beseitigung", "schadenersatz"])
        self.assertEqual(self.case.option("frist_androhung")["state"], "holds")  # holds, but only selectable
        self.assertFalse(self.case.option("frist_androhung")["propose"])
        wanted = Case(changed(replied(), facts={"will_reduktion": True}), DECKUNG)
        self.assertEqual(wanted.brief["proposal"], ["frist_beseitigung", "reduktion", "schadenersatz"])  # the wishes' order
        data = copy.deepcopy(options.load(WID))
        facts = options.implied(self.case.state["facts"], data)
        evaluated = options.evaluate(data, facts, {}, review.flags(self.case.state["process"], {}), {}, intents={"hinterlegen"})
        for o in data["options"]:
            if o["id"] == "frist_androhung":
                o["propose"] = True
        evaluated = [{**e, "propose": True} if e["id"] == "frist_androhung" else e for e in evaluated]
        self.assertEqual(options.proposal(data, facts, evaluated), ["frist_beseitigung", "schadenersatz"])  # equal practice: the file's order
        for o in data["options"]:
            if o["id"] == "frist_androhung":
                o["observed"] = {"count": "3 von 7", "from": "stages.gegenpartei.suggestions[0]"}
        self.assertEqual(options.proposal(data, facts, evaluated), ["frist_androhung", "schadenersatz"])  # practice first

    def test_an_option_under_question_or_change_is_not_proposed_and_each_shows_its_review_state(self):
        mark = lambda kind: {"mark": kind, "content_sha256": "x"}
        held = Case(replied(), DECKUNG, marks={f"{WID}:empfehlung.frist_beseitigung": mark("frage")})
        self.assertEqual(held.brief["proposal"], ["schadenersatz"])
        self.assertEqual(held.option("frist_beseitigung")["review"], "Frage offen")
        changed_ = Case(replied(), DECKUNG, marks={f"{WID}:empfehlung.frist_beseitigung": mark("aenderung")})
        self.assertEqual((changed_.brief["proposal"], changed_.option("frist_beseitigung")["review"]), (["schadenersatz"], "in Prüfung"))
        self.assertEqual({o["review"] for o in self.case.brief["options"]}, {"nicht juristisch geprüft"})
        checked = Case(replied(), DECKUNG, marks={f"{WID}:empfehlung.{x}": mark("geprueft") for x in ("frist_beseitigung", "schadenersatz")})
        self.assertEqual(checked.decision["review"], "geprüft")
        half = Case(replied(), DECKUNG, marks={f"{WID}:empfehlung.schadenersatz": mark("geprueft")})
        self.assertEqual(half.decision["review"], "nicht juristisch geprüft")  # the weakest of the ways shown
        answer = Case(replied(), DECKUNG, marks={f"{WID}:antwort.hinterlegung.weiter_zahlen": mark("aenderung")})
        self.assertEqual((answer.question(0)["state"], answer.question(0)["reason"]), ("pruefen", "Antwort in Prüfung"))
        self.assertIn("«Muss ich weiterhin die volle Miete bezahlen?»: [bitte ergänzen: Antwort auf diese Frage (in Prüfung)]", answer.text)
        line = Case(replied(), DECKUNG, marks={f"{WID}:fall.besteht": mark("frage")})
        self.assertIn("[bitte ergänzen: Besteht der Mangel aktuell noch? (in Prüfung)]", line.text)

    def test_a_recommended_option_states_its_conditions(self):
        rule = self.case.rule("259b")
        self.assertEqual([(c["text"], c["kind"], c["state"]) for c in rule["conditions"]],
                         [("Die Vermieterschaft kennt den Mangel", "vorher", "erfüllt"), ("Sie hat ihn nicht beseitigt", "vorher", "erfüllt")])
        self.assertTrue(all(c["evidence"] for c in rule["conditions"]))  # each with its source
        self.assertEqual(rule["conditions"][0]["evidence"][0]["quote"],
                         f"Den Schimmel habe ich der Verwaltung am {ep.long_day(NS.day(-12))} schriftlich gemeldet.")  # implied: by its source
        letter = self.case.brief["letter"]["empfehlung"]
        self.assertIn("eine angemessene Frist zur Beseitigung des Mangels zu setzen (Art. 259g Abs. 1 OR)", letter)
        self.assertIn("wenn sie nicht beweist, dass sie kein Verschulden trifft (Art. 259e OR)", letter)  # the unchecked elements, stated

    def test_unchecked_elements_of_259e_show_nicht_geprueft(self):
        rule = self.case.rule("259e")
        self.assertEqual(rule["cite"], "Art. 259e OR")
        # the third condition is the evidence the residual asks for: «offen» until a receipt documents the claimed cost
        self.assertEqual([(c["text"], c["state"]) for c in rule["conditions"]],
                         [("Schaden durch den Mangel", "nicht geprüft"), ("kein Entlastungsbeweis der Vermieterschaft", "nicht geprüft"),
                          ("Kosten mit Belegen nachgewiesen", "offen")])
        self.assertEqual(rule["conditions"][2]["evidence"][0]["quote"], "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben.")
        self.assertEqual(self.case.option("schadenersatz")["state"], "holds")

    def test_hinterlegung_stays_open_on_its_unshown_precondition(self):
        option = self.case.option("hinterlegung")
        self.assertEqual((option["state"], option["conditions"][0]["state"]), ("open", "nicht geprüft"))
        self.assertNotIn("hinterlegung", self.case.brief["proposal"])
        remedied = Case(changed(replied(), facts={"reaktion_vermieter": "Mangel behoben / Einigung"}), DECKUNG)
        self.assertEqual(remedied.option("frist_beseitigung")["state"], "fails")
        self.assertIn({"condition": "Frist mit Androhung der Hinterlegung schriftlich gesetzt und unbenützt abgelaufen", "option": "hinterlegung"},
                      remedied.brief["changes_if"])  # the wish has no way that holds: what would open one

    def test_frist_beseitigung_does_not_hold_once_remedied_and_is_open_without_the_reaction(self):
        remedied = Case(changed(replied(), facts={"mangel_besteht": False}), DECKUNG)
        self.assertEqual(remedied.option("frist_beseitigung")["state"], "fails")
        self.assertNotIn("frist_beseitigung", remedied.brief["proposal"])
        unknown = Case(changed(replied(), facts={"reaktion_vermieter": None}), DECKUNG)
        option = unknown.option("frist_beseitigung")
        self.assertEqual((option["state"], next(c for c in option["conditions"] if c["fact"] == "reaktion_vermieter")["state"]), ("open", "offen"))

    def test_the_options_file_is_validated_like_a_module(self):
        workflow, good = area.workflow(WID), json.loads(options.path(WID).read_text())
        options.validate(copy.deepcopy(good), workflow)

        def option(data, oid):
            return next(o for o in data["options"] if o["id"] == oid)

        def answer(data, intent):
            return next(a for a in data["answers"] if a["intent"] == intent)
        refusals = {
            "format": lambda d: d.update(format="casepath.options/0"),
            "version": lambda d: d.update(version="neu"),
            "duplicate id": lambda d: d["options"].append(copy.deepcopy(d["options"][0])),
            "row without passage": lambda d: d["law"]["259g-2"].update(passage=""),
            "unverified row cited": lambda d: d["law"]["259g-2"].update(verified=False),
            "requires not in passage": lambda d: answer(d, "weiter_zahlen")["parts"][1]["requires"].append("Mietzinsdepot"),
            "condition requires": lambda d: option(d, "schadenersatz")["conditions"][0]["requires"].append("Gewinn"),
            "prudence with a duty": lambda d: option(d, "frist_beseitigung")["advice"][1].update(text=" und den Mietzins weiter zahlen müssen"),
            "answer prudence without empfehlen": lambda d: answer(d, "hinterlegen")["parts"][4].update(text="Besprechen Sie eine Hinterlegung vorher mit uns."),
            "unchecked element not stated": lambda d: option(d, "schadenersatz")["advice"].pop(1),
            "wish no fact": lambda d: option(d, "reduktion").update(wish="will_umzug"),
            "when unknown fact": lambda d: option(d, "frist_beseitigung")["when"].append({"fact": "gibt_es_nicht", "is": True}),
            "value outside the fact": lambda d: option(d, "frist_beseitigung")["conditions"][1].update({"in": ["Vielleicht"]}),
            "condition fact without sofern": lambda d: d["sofern"].pop("reaktion_vermieter"),
            "need not a document": lambda d: option(d, "reduktion")["needs"].append({"document": "steuererklaerung"}),
            "answer for unknown point": lambda d: answer(d, "melden").update(points=["unbekannt"]),
            "placeholder": lambda d: d["wording"].update(claims="Sie machen geltend: {kosten}."),
            "observed count": lambda d: option(d, "schadenersatz")["observed"].update(count="5 von 7"),
            "open question about nothing": lambda d: d["open_questions"].append({"text": "Stimmt das?", "about": "empfehlung.keine"}),
            "law row named twice": lambda d: d["law"].update({"259e": copy.deepcopy(d["law"]["259g-2"])}),
            "plain part states law": lambda d: option(d, "frist_beseitigung")["advice"][2].update(text="; Sie haben Anspruch darauf"),
        }
        for name, change in refusals.items():
            bad = copy.deepcopy(good)
            change(bad)
            with self.subTest(name), self.assertRaises(CatalogueError):
                options.validate(bad, workflow)

    def test_the_options_law_rows_verify_against_the_official_text(self):
        folder = os.environ.get("CASEPATH_LAW_SOURCES")
        if not folder:
            self.skipTest("CASEPATH_LAW_SOURCES not set")
        texts = {sr: area.official_articles(Path(folder) / row["file"]) for sr, row in area.backbone()["laws"].items()
                 if (Path(folder) / row["file"]).is_file()}
        data = options.load(WID)
        found = options.verify(data, texts)
        self.assertEqual(found, {k: True for k in data["law"]})  # every own row, word for word
        self.assertEqual(found, {k: r["verified"] for k, r in data["law"].items()})

    def test_the_options_are_reviewable_elements_and_a_changed_option_lapses_its_mark(self):
        model = review.Model.load()
        row = model.row(WID)
        groups = {g["id"]: g for g in row["groups"]}
        self.assertEqual([GROUP for GROUP in ("empfehlungen", "antworten", "faelle", "wortlaut") if GROUP in groups],
                         ["empfehlungen", "antworten", "faelle", "wortlaut"])
        self.assertEqual([review.GROUPS[g] for g in ("empfehlungen", "antworten", "faelle", "wortlaut")],
                         ["Empfehlungen", "Antworten auf Fragen", "Sätze zum Fall", "Verbindende Sätze"])
        key = f"{WID}:empfehlung.frist_beseitigung"
        lines = {l["label"]: l["text"] for l in model.elements[key]["lines"]}
        self.assertEqual(lines["Praxis"], "nicht erfasst")
        self.assertEqual(lines["Vorschlag"], "ja")
        self.assertIn("(vorher:", lines["Voraussetzungen"])
        self.assertTrue(lines["Wortlaut"].startswith("Wir empfehlen Ihnen, der Vermieterschaft schriftlich"))
        self.assertIn("nur wählbar", {l["label"]: l["text"] for l in model.elements[f"{WID}:empfehlung.frist_androhung"]["lines"]}["Vorschlag"])
        self.assertIn("Soll bei einer Frage nach der Hinterlegung", " ".join(model.elements[f"{WID}:empfehlung.frist_androhung"]["questions"]))
        self.assertIn(f"{WID}:antwort.hinterlegung.zurueckbehalten", model.elements)  # an answer shared by two points: reviewed once
        stich = [l for l in model.elements[f"{WID}:kernpunkt.hinterlegung"]["lines"] if l["label"] == "Stichwörter"]
        self.assertEqual(stich[0]["text"], "hinterleg · mietzins · zurückbehalt · nicht zahlen")
        mark = {"file": WID, "element": "empfehlung.frist_beseitigung", "content_sha256": model.elements[key]["sha256"], "mark": "geprueft",
                "reviewer": "Jurist A", "at": "2026-11-15T09:00:00+00:00"}
        self.assertEqual(model.state(key, mark), "geprueft")
        self.assertEqual(review.state_of(key, model.current({key: mark})), "geprüft")
        data = copy.deepcopy(options.load(WID))
        next(o for o in data["options"] if o["id"] == "frist_beseitigung")["advice"][0]["text"] += " und dies zu belegen"
        load = options.load
        with mock.patch.object(options, "load", side_effect=lambda area_id: data if area_id == WID else load(area_id)):
            changed_model = review.Model.load()
        self.assertEqual(changed_model.state(key, mark), "geaendert")  # the mark lapses with the content it was given on
        self.assertEqual(review.state_of(key, changed_model.current({key: mark})), "nicht juristisch geprüft")


# -- «In Ihrem Fall», the claims, the residual -------------------------------------------------------------------------------

class InCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = Case(replied(), DECKUNG)

    def test_the_in_case_paragraph_states_only_accepted_facts_each_with_its_source_and_date(self):
        lines = [l["text"] for l in self.case.brief["in_case"]]
        self.assertEqual(lines, ["Sie möchten die Beseitigung des Mangels und den Ersatz Ihrer Kosten und Schäden.",
                                 "Mit Ihrer Nachricht vom 05.09.2026 haben Sie unsere Fragen beantwortet.",
                                 "Sie haben den Mangel der Vermieterschaft schriftlich gemeldet.",
                                 "Der Mangel war nach Ihren Angaben vom 05.09.2026 nicht behoben.",
                                 "Nach Ihren Angaben hat die Vermieterschaft weitere Massnahmen abgelehnt oder Punkte offen gelassen.",
                                 "Sie machen folgende Kosten geltend: Stromkosten für den Bautrockner (nach Ihren Angaben CHF 85)."])
        self.assertTrue(all(l["evidence"] for l in self.case.brief["in_case"]))
        besteht = next(l for l in self.case.brief["in_case"] if l["key"] == "fall.besteht")
        self.assertEqual(besteht["evidence"][0]["quote"], "Der Schimmel ist immer noch da.")  # dated by the reply it is quoted from
        self.assertIn("In Ihrem Fall: Sie möchten die Beseitigung des Mangels", self.case.text)
        self.assertNotIn("[bitte ergänzen: was in diesem Fall sonst vorliegt]", self.case.text)
        rejected = replied()
        for f in rejected["facts"]:
            if f["fact"] == "reaktion_vermieter":
                f["verdict"] = "rejected"
        self.assertNotIn("abgelehnt", " ".join(l["text"] for l in Case(rejected, DECKUNG).brief["in_case"]))
        presumed = Case(changed(replied(), facts={"reaktion_vermieter": {"value": "Abgelehnt / offene Punkte", "status": "presumed"}}), DECKUNG)
        self.assertNotIn("abgelehnt", " ".join(l["text"] for l in presumed.brief["in_case"]))

    def test_the_replies_line_says_answered_only_when_every_asked_row_is_closed(self):
        result = replied()
        reply = next(e for e in result["record"]["entries"] if e["n"] == 13)
        reply["answers"] = reply["answers"][:1]  # the management's reaction is not answered
        line = next(l["text"] for l in Case(result, DECKUNG).brief["in_case"] if l["key"] == "replies")
        self.assertEqual(line, "Mit Ihrer Nachricht vom 05.09.2026 haben Sie zu unseren Fragen Stellung genommen.")

    def test_a_claim_whose_words_are_not_in_its_quote_is_never_named(self):
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        quote = "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben."
        brief = team._located_brief(work, {"summary": "x", "questions": [], "claims": [claim("Reinigung des Teppichs", quote, file="fc")]})
        self.assertFalse(brief["claims"][0]["checked"])
        case = Case(changed(replied(), claims=brief["claims"]), DECKUNG)
        self.assertNotIn("Teppich", case.text)
        self.assertNotIn("geltend", " ".join(l["text"] for l in case.brief["in_case"]))
        self.assertEqual([r for r in case.brief["residual"] if r["kind"] == "claim"], [])

    def test_a_claim_amount_not_in_its_quote_is_dropped(self):
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        quote = "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben."
        brief = team._located_brief(work, {"summary": "x", "questions": [], "claims": [
            claim("Stromkosten für den Bautrockner", quote, amount="CHF 120", file="fc"),
            claim("Stromkosten für den Bautrockner", quote, amount="rund CHF 85", file="fc")]})
        self.assertEqual([(c["amount"], c["checked"]) for c in brief["claims"]], [(None, True), ("rund CHF 85", True)])
        self.assertEqual(brief["dropped_amounts"], 1)
        self.assertEqual(options.amounts("vom 05.09.2026 für CHF 1'200.50 und 85.– sowie Fr. 3"), {1200.5, 85.0, 3.0})  # never a date
        line = next(l["text"] for l in Case(changed(replied(), claims=brief["claims"][:1]), DECKUNG).brief["in_case"] if l["key"] == "claims")
        self.assertEqual(line, "Sie machen folgende Kosten geltend: Stromkosten für den Bautrockner.")

    def test_an_unrelated_receipt_does_not_document_a_claim(self):
        # a shop's receipt, recorded on its entry: a receipt of the case, for another expense and amount
        shop = receipt("Total CHF 25.40", "Schimmelentferner und Fugenbürste", "Ersatzanschaffung", amount="CHF 25.40", party="Drogerie Exempel",
                       transaction="4711")
        result, files = arrival(replied(), [SHOP], entries=[ep.entry(16, "fq", None, None, "andere", "kunde", "andere", "Quittung der Drogerie",
                                                                     "Total CHF 25.40", receipt=shop)])
        self.assertEqual(next(e for e in result["record"]["entries"] if e["n"] == 16)["receipt"]["expense"], "Schimmelentferner und Fugenbürste")
        state = core.evaluate(area.workflow(WID), [], DECKUNG, result, "c")
        claims = assessment.claims_of(result, ep.looked_at(files, NS.a5_day), state["account"])
        self.assertEqual((claims[0]["documented"], claims[0]["receipt"]), (False, []))  # not the electricity cost's receipt
        self.assertEqual([r["kind"] for r in Case(result, DECKUNG, files=files).brief["residual"]], ["claim"])

    def test_the_residual_names_the_claimed_cost_and_never_asks_what_the_file_holds(self):
        self.assertEqual([r["line"] for r in self.case.brief["residual"]], ["Belege zu: Stromkosten für den Bautrockner"])
        self.assertIn("Bitte reichen Sie uns noch nach:\n– Belege zu: Stromkosten für den Bautrockner\n", self.case.text)
        self.assertNotIn("Kaufbelege und Liste der beschädigten Gegenstände", self.case.text)  # the generic need: not asked again
        self.assertNotIn("Mietvertrag", self.case.text.split("Bitte reichen Sie uns noch nach:", 1)[1])

    def test_the_residual_takes_open_requests_of_the_account_and_drops_delivered_ones(self):
        result = replied()
        reply = next(e for e in result["record"]["entries"] if e["n"] == 13)
        reply["answers"] = reply["answers"][:1]  # the A4's second question stays open
        first = next(e for e in result["record"]["entries"] if e["n"] == 4)
        first["answers"] = [a for a in first["answers"] if a["what"] != "Mietvertrag"]  # the lease not answered, but in the file
        case = Case(result, DECKUNG)
        keys = [r["key"] for r in case.brief["residual"]]
        self.assertEqual(keys, ["residual:claim.0", "residual:request.r10.1"])
        self.assertEqual(case.brief["residual"][1]["line"], "Reaktion der Verwaltung auf die letzte Meldung (erstmals verlangt am 17.08.2026)")
        self.assertNotIn("residual:request.r3.0", keys)  # asked, but the file holds the lease: never asked again

    def test_a_withdrawn_claim_leaves_the_residual(self):
        retract = NS.perturbations["P-retract"]
        prior = {"id": "run_b", "workflow_id": WID, "workflow_version": _PREPARED_version(), "routing": None, "result": replied()}
        first, second = retract.turns(first=16)
        promised, _ = ep.updated(prior, FILES + retract.core_files[:1], first, NS)
        withdrawn, _ = ep.updated({**prior, "result": promised["result"]}, FILES + retract.core_files, second, NS)
        files = ep.looked_at(FILES + retract.core_files, NS.a5_day)
        state = core.evaluate(area.workflow(WID), [], DECKUNG, withdrawn["result"], "case_s_d11a", files=files)
        items = build_items(state, withdrawn["result"], files)
        brief = assessment.build({**state, "case": ep.case_row()}, withdrawn["result"], items, files, [], {})
        self.assertEqual(state["facts"]["will_schadenersatz"], False)
        self.assertEqual([r for r in brief["residual"] if r["kind"] == "claim"], [])
        self.assertNotIn("schadenersatz", brief["proposal"])
        q = brief["questions"][2]
        self.assertEqual((q["state"], q["row"]), ("pruefen", 4))  # «Sie möchten den Ersatz … nicht»: the handler decides

    def test_a_residual_line_can_be_unticked(self):
        unticked = Case(replied(), DECKUNG, [{"kind": "letter.line", "item_id": "residual:claim.0", "included": False}])
        self.assertEqual([(r["key"], r["ticked"]) for r in unticked.brief["residual"]], [("residual:claim.0", False)])
        self.assertNotIn("Bitte reichen Sie uns noch nach", unticked.text)
        self.assertNotIn("steht unten", unticked.text)  # the answer no longer points to it
        self.assertEqual(unticked.brief["asks"], [])
        self.assertIn("residual", __import__("casepath.process.items", fromlist=["SCREEN_KINDS"]).SCREEN_KINDS)

    def test_the_asks_are_the_ticked_residual_and_each_conditional_answers_fact(self):
        self.assertEqual(self.case.brief["asks"], [{"key": "residual:claim.0", "what": "Belege zu: Stromkosten für den Bautrockner", "kind": "claim", "ref": 0,
                                                    "blocks": {"question": "customer_question:2", "option": "schadenersatz",
                                                               "condition": "Kosten mit Belegen nachgewiesen"}}])
        open_ = Case(changed(replied(), facts={"mangel_besteht": None}), DECKUNG)
        keys = [a["key"] for a in open_.brief["asks"]]
        self.assertIn("fact:mangel_besteht", keys)  # the deposit's point waits for it
        self.assertEqual(keys.count("fact:mangel_besteht"), 1)  # asked once, also by two questions


def _PREPARED_version():
    replied()
    return _PREPARED["prior"]["workflow_version"]


# -- decisions and the premise -------------------------------------------------------------------------------------------------

class DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = Case(replied())
        cls.decided = Case(replied(), DECKUNG)

    def test_the_cover_decision_shows_at_clarifying_when_only_it_blocks_the_assessment(self):
        act = self.before.item("next_action:0")
        self.assertEqual((self.before.stage, act["action"], act["premise"]), ("klaeren", "A5", {"deckung": "bestätigt"}))
        self.assertEqual(act["reason"], "Kundschaft hat geantwortet; Einschätzung nach dem Deckungsentscheid")
        self.assertEqual(self.before.decision["key"], "deckung")
        through_prospects = screen.decision(self.before.items, {**self.before.draft, "needs": []}, "klaeren", assessment=self.before.brief)
        self.assertEqual(through_prospects["key"], "deckung")  # the prospects branch asks the cover too, never «Erfolgsaussichten»
        self.assertEqual(self.decided.decision["key"], "empfehlung")
        self.assertEqual(self.decided.decision["question"], "Empfehlung: Frist zur Beseitigung setzen · Kosten belegen und Ersatz verlangen")
        self.assertEqual(self.decided.decision["review"], "nicht juristisch geprüft")
        # the recommendation alone: the prospects are a decision of their own (steering, point 1)
        self.assertEqual([a["label"] for a in self.decided.decision["answers"]], ["übernehmen", "ändern"])
        self.assertIn("frist_androhung", [o["id"] for o in self.decided.decision["options"]])  # the selectable-only way, under «ändern»

    def test_the_a5_under_the_premise_cannot_be_approved_before_the_decision(self):
        self.assertEqual([b["key"] for b in self.before.brief["blocking"]], ["deckung", "empfehlung", "aussichten"])
        self.assertTrue(self.before.brief["under_premise"])
        self.assertEqual([b["key"] for b in self.decided.brief["blocking"]], ["empfehlung", "aussichten"])
        adopted = Case(replied(), DECKUNG + ep.decided(("aussichten", "genügend")), [adopt(self.decided.brief["proposal"], self.decided.brief["proposal"])])
        self.assertEqual(adopted.brief["blocking"], [])
        self.assertIsNone(adopted.decision)

    def test_the_recommendation_and_the_prospects_are_two_decisions_that_can_differ(self):
        proposal = self.decided.brief["proposal"]
        self.assertFalse(letters.has_gap(self.decided.text))  # the proposal fills the letter before it is adopted
        # adopting the way judges nothing about the prospects: they are asked next, with their own basis (Art. 169 AVO)
        adopted = Case(replied(), DECKUNG, [adopt(proposal, proposal)])
        self.assertEqual((adopted.brief["chosen"], adopted.brief["adopted"]["valid"]), (proposal, True))
        self.assertEqual([b["key"] for b in adopted.brief["blocking"]], ["aussichten"])
        self.assertEqual((adopted.decision["key"], adopted.decision["question"], adopted.decision["detail"]),
                         ("aussichten", "Erfolgsaussichten", "Art. 169 Abs. 2 AVO"))
        self.assertEqual([r["cite"] for r in adopted.decision["law"]], ["Art. 169 Abs. 2 AVO", "Art. 169 Abs. 3 AVO"])
        self.assertIn("Ablehnung", adopted.decision["consequence"])
        self.assertEqual([a["label"] for a in adopted.decision["answers"]], ["genügend", "nicht genügend"])
        self.assertIn("Wir empfehlen Ihnen, der Vermieterschaft schriftlich eine angemessene Frist", adopted.text)
        # judged first, the prospects leave the recommendation open: the two never stand for each other
        judged = Case(replied(), DECKUNG + ep.decided(("aussichten", "genügend")))
        self.assertEqual(([b["key"] for b in judged.brief["blocking"]], judged.decision["key"]), (["empfehlung"], "empfehlung"))
        # they differ: another way adopted, the prospects sufficient; or the way adopted and the prospects not sufficient
        other = Case(replied(), DECKUNG + ep.decided(("aussichten", "genügend")), [adopt(["frist_androhung", "schadenersatz"], proposal)])
        self.assertEqual((other.brief["blocking"], other.decision, other.brief["chosen"]), ([], None, ["frist_androhung", "schadenersatz"]))
        low = Case(replied(), DECKUNG + ep.decided(("aussichten", "nicht genügend")), [adopt(proposal, proposal)])
        self.assertEqual(low.draft["form"], "A5_aussichtslos")  # the existing refusal for lack of prospects
        self.assertIsNone(low.brief["letter"])
        self.assertEqual(low.brief["blocking"], [])

    def test_an_adoption_lapses_when_a_chosen_option_fails_or_the_proposal_changes(self):
        proposal = self.decided.brief["proposal"]
        events = [adopt(proposal, proposal)]
        prospects = ep.decided(("aussichten", "genügend"))
        remedied = Case(changed(replied(), facts={"mangel_besteht": False}), DECKUNG + prospects, events)
        self.assertEqual(remedied.brief["blocking"], [{"kind": "decision", "key": "empfehlung",
                                                       "text": "Empfehlung erneut bestätigen: Frist zur Beseitigung setzen trifft nicht mehr zu"}])
        self.assertEqual(remedied.decision["lapse"], "Empfehlung erneut bestätigen: Frist zur Beseitigung setzen trifft nicht mehr zu")
        self.assertEqual(remedied.brief["chosen"], [])
        wanted = Case(changed(replied(), facts={"will_reduktion": True}), DECKUNG + prospects, events)
        self.assertEqual(wanted.brief["blocking"][0]["text"], "Empfehlung erneut bestätigen: Vorschlag geändert")

    def test_the_premise_lists_the_facts_the_letter_rests_on(self):
        self.assertEqual(self.decided.brief["premise"], {
            "deckung": "bestätigt", "aussichten": None, "will_beseitigung": True, "mangel_besteht": True, "mangel_gemeldet": True,
            "maengelruege_schriftlich": True, "reaktion_vermieter": "Abgelehnt / offene Punkte", "will_schadenersatz": True})
        self.assertEqual(self.before.brief["premise"]["deckung"], None)  # its current value: the decision is still open


# -- areas without options, the reader -------------------------------------------------------------------------------------------

class WithoutOptionsTests(unittest.TestCase):
    def test_without_an_options_file_no_recommendation_is_filled(self):
        from tests.test_key_points import KEY_CASES, run
        result, state, items = run(KEY_CASES["kuendigung-sperrfrist"])
        brief = assessment.build({**state, "case": {"title": "Kündigung"}}, result, items, [], [], {})
        self.assertFalse(brief["has_options"])
        self.assertIsNone(brief["letter"])
        self.assertEqual([c["id"] for c in brief["candidates"]], ["begruendung", "einsprache"])  # «Kandidaten (nicht übernommen)»
        ctx = letters.context({"title": "Kündigung"}, items, [], {"due": "2026-12-12"}, assessment=brief)
        text, _ = letters.render("A5", state["process"]["forms"], ctx)
        self.assertIn("Wir empfehlen Ihnen, [bitte ergänzen: die Empfehlung an die Kundschaft]", text)
        self.assertIsNone(options.load("arbeit-kuendigung"))

    def test_the_reader_is_given_the_key_points_and_keeps_only_known_tags(self):
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        view = team._process_view(work)
        self.assertEqual([p["id"] for p in view["key_points"]], ["meldung", "reduktion", "hinterlegung", "schadenersatz", "kuendigung"])
        self.assertTrue(all(p["statement"] and p["question"] for p in view["key_points"]))
        schema = team._report_schema(work, "claim_reader")
        about = schema["properties"]["questions"]["items"]["properties"]["about"]
        self.assertEqual((about["items"]["enum"], about["maxItems"]), (["meldung", "reduktion", "hinterlegung", "schadenersatz", "kuendigung"], 2))
        claims = schema["properties"]["claims"]["items"]["properties"]
        # what a claim is about, under the names Slice C's rule reads (NEEDS_C §1; steering, point 5)
        self.assertEqual(sorted(claims), ["amount", "citations", "expense", "expense_kind", "party", "period", "role", "transaction", "what"])
        self.assertEqual(sorted(claims["period"]["properties"]), ["from", "to"])
        record = team.steps_entry(work)["properties"]["receipt"]  # and what a receipt records, on its own entry
        self.assertEqual((record["type"], sorted(record["properties"])),
                         (["object", "null"], ["amount", "expense", "expense_kind", "party", "payer", "period", "quote", "role", "transaction"]))
        self.assertEqual(record["properties"]["role"]["enum"], ["requested", "promised", "disputed", "paid", "refunded"])
        from tests.test_team import FIXTURE as PLAIN, FILES as PLAIN_FILES
        bare = team.CaseWork(case={"title": "x"}, files=PLAIN_FILES, base_workflow=PLAIN)
        about = team._report_schema(bare, "claim_reader")["properties"]["questions"]["items"]["properties"]["about"]
        self.assertEqual(about["maxItems"], 0)  # a process without key points: no tag at all
        self.assertIn("In about, give the ids of the key\npoints (process view, key_points)", team.AGENTS["claim_reader"]["instructions"])
        self.assertIn("a question that rejects\na remedy is not about that remedy", team.AGENTS["claim_reader"]["instructions"])

    def test_the_update_reader_lists_new_questions_and_claims(self):
        self.assertIn("questions and claims, only those the new documents state, with about", team.UPDATE_READ)
        result = replied()
        self.assertEqual([q["about"] for q in result["brief"]["questions"]], [["hinterlegung"], ["hinterlegung"], ["schadenersatz"]])
        self.assertEqual([(c["what"], c["amount"], c["checked"], c["expense_kind"], c["role"]) for c in result["brief"]["claims"]],
                         [("Stromkosten für den Bautrockner", "CHF 85", True, "Energie", "requested")])
        self.assertNotIn("documented", result["brief"]["claims"][0])  # decided where the case is shown, by one rule (claims_of)
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        work.brief = copy.deepcopy(result["brief"])
        again = team._merge_brief(work, {"summary": "x", "questions": [], "claims": [
            claim("Stromkosten für den Bautrockner", "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben.", file="fc")]})
        self.assertEqual(len(again["claims"]), 1)  # a cost once, by its words

    def test_assessment_facts_are_read_twice_within_the_bound_and_the_rest_marked_once(self):
        prior, _ = ep.prepared(NS)
        # the update's second reader sees the new documents only: it confirms what they state (the defect persists); a
        # condition fact read once from the earlier file is asked too, and stays «einmal gelesen» unless a new document says it
        agreed = [{"fact": "mangel_besteht", "status": "established", "value": "ja",
                   "citations": [{"file": "fb", "quote": "Der Schimmel ist immer noch da."}]}]

        class Watched(ScriptedModel):
            def respond_json(self, **kwargs):
                if kwargs["name"] == "casepath_confirm_facts":
                    self.asked = [f["id"] for f in json.loads(kwargs["input"][0]["content"])["facts"]]
                return super().respond_json(**kwargs)
        model = Watched(NS.turns_b(), second_reading=agreed)
        outcome, _ = ep.updated(prior, FILES, None, NS, model=model)
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        changed_facts = set(outcome["result"]["update"]["facts"])
        self.assertEqual(set(model.asked) - changed_facts, {"will_beseitigung", "maengelruege_schriftlich"})  # read once, the assessment rests on them
        self.assertLessEqual(len(set(model.asked) - changed_facts), team.SECOND_READING_BOUND)
        rows = {f["fact"]: f for f in outcome["result"]["facts"]}
        self.assertTrue(rows["mangel_besteht"].get("read_twice"))
        self.assertFalse(rows["will_beseitigung"].get("read_twice"))  # asked, not confirmed: no new document says it
        case = Case(outcome["result"], DECKUNG)
        reads = {c["fact"]: c["read"] for r in case.brief["rules"] for c in r["conditions"] if c.get("fact")}
        self.assertEqual((reads["mangel_besteht"], reads["will_beseitigung"], reads["mangel_gemeldet"]), ("zweimal", "einmal gelesen", "einmal gelesen"))
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        work.facts = {f["fact"]: dict(f) for f in prior["result"]["facts"] if f.get("status") != "presumed"}
        work.record = {"entries": list(prior["result"]["record"]["entries"]), "dropped": 0, "elsewhere": 0, "issues": []}
        self.assertEqual(len(team.read_once(work, bound=1)), 1)  # never more than the bound


# -- end to end and invariants ---------------------------------------------------------------------------------------------------

class EpisodeTests(unittest.TestCase):
    def test_the_d11_analog_a5_has_no_gap_after_adoption(self):
        before = Case(replied())
        self.assertEqual((before.item("next_action:0")["action"], before.decision["key"]), ("A5", "deckung"))
        decided = Case(replied(), DECKUNG)
        brief = decided.brief
        self.assertEqual([(q["state"], q["row"]) for q in brief["questions"]], [("beantwortet", 10), ("bedingt", 9), ("bedingt", 9)])
        self.assertEqual([q["reason"] for q in brief["questions"][1:]], ["vorher mit uns besprechen", "Belege zu: Stromkosten für den Bautrockner"])
        self.assertEqual(brief["proposal"], ["frist_beseitigung", "schadenersatz"])
        self.assertEqual(decided.option("frist_androhung")["state"], "holds")
        self.assertEqual(decided.option("hinterlegung")["state"], "open")
        self.assertNotIn("Eine Mietzinsreduktion möchte ich nicht", [q["text"] for q in brief["questions"]])  # a statement, no question
        self.assertEqual(decided.state["facts"]["will_reduktion"], False)
        self.assertEqual([r["line"] for r in brief["residual"]], ["Belege zu: Stromkosten für den Bautrockner"])
        self.assertEqual([a["key"] for a in brief["asks"]], ["residual:claim.0"])
        self.assertEqual([q["item_id"] for q in brief["questions"] if q["state"] == "beantwortet"], ["customer_question:0"])
        self.assertEqual(brief["summary"], {"answered": 1, "conditional": 2, "open": 0, "check": 0, "residual": 1, "asked": 0, "resolved": 3,
                                            "decisions": ["empfehlung", "aussichten"],
                                            "proposal": ["Frist zur Beseitigung setzen", "Kosten belegen und Ersatz verlangen"]})
        self.assertTrue(all(isinstance(q["row"], int) for q in brief["questions"]))  # the guard row that decided each (MEASURE)
        adopted = Case(replied(), DECKUNG + ep.decided(("aussichten", "genügend")), [adopt(brief["proposal"], brief["proposal"])])
        self.assertNotIn("[bitte ergänzen", adopted.text)
        self.assertEqual((adopted.brief["blocking"], adopted.decision), ([], None))
        self.assertEqual(adopted.brief["options_sha256"], options.sha256(WID))

    def test_the_first_request_is_unchanged(self):
        claim_only = ep.paged("fa", "Schadenmeldung.pdf", [NS.dossier["extraction"]["text"].split("[page 6]\n", 1)[1].split("\n\n[page 7]", 1)[0]],
                              [ep.segment(1, 1, NS.d0, NS.names["kunde"], "Protekta", "E-Mail", "Schadenmeldung")])
        turns = ep.full_turns([ep.entry(1, "fa", 1, NS.d0, "kunde", "versicherer", "meldung", "Meldung", "Betreff: Schimmel in meiner Wohnung")],
                              [ep.fact("fa", "rechtsgebiet", "Mietrecht / Mangel", "Schimmel")], [], NS.request, NS.parties,
                              questions=[ep.question("fa", "Was kann ich tun?", ["hinterlegung"])])
        model = ScriptedModel(turns)
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(ep.job(NS, [claim_only]), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        files = ep.looked_at([claim_only], NS.d0)
        state = core.evaluate(area.workflow(WID), [], [], outcome["result"], "case_s_d11a", files=files)
        items = build_items(state, outcome["result"], files)
        act = next(i for i in items if i["kind"] == "next_action")
        self.assertEqual((act["action"], act.get("premise")), ("A1", None))  # the first request is the action; no premise
        brief = assessment.build({**state, "case": ep.case_row()}, outcome["result"], items, files, [], {})
        self.assertEqual((brief["letter"], brief["blocking"], brief["premise"]), (None, [], {}))  # nothing of the A5 reaches the A1
        ctx = letters.context(ep.case_row(), items, [], {"due": "2026-08-22"}, evaluation=state["evaluation"], process=state["process"], assessment=brief)
        plain = letters.context(ep.case_row(), items, [], {"due": "2026-08-22"}, evaluation=state["evaluation"], process=state["process"])
        self.assertEqual(letters.render("A1", state["process"]["forms"], ctx), letters.render("A1", state["process"]["forms"], plain))


# -- the package a handler adopts: every question, the conditions, the alternative, what would change it, the remainder ---------

class PackageTests(unittest.TestCase):
    """Steering, point 2: the package answers each question, applies each condition to the evidence, gives the recommended
    next step and the meaningful alternative, says what would change it, and asks only the smallest remainder; where the
    evidence cannot support an answer, a precise question with what its answer decides, never «bitte prüfen»."""

    @classmethod
    def setUpClass(cls):
        cls.case = Case(replied(), DECKUNG)

    def test_the_letter_says_what_the_recommendation_rests_on_and_the_brief_names_the_alternative(self):
        letter = self.case.brief["letter"]["empfehlung"]
        self.assertTrue(letter.endswith("Unsere Empfehlung beruht darauf, dass der Mangel weiterhin besteht und die Vermieterschaft den Mangel "
                                        "nicht behoben hat; ändert sich daran etwas, teilen Sie uns das bitte mit."))
        # the alternative to the proposed way, beside it, each with why it is not the proposal
        rows = {(a["to"], a["id"]): a for a in self.case.brief["alternatives"]}
        androhung = rows[("frist_beseitigung", "frist_androhung")]
        self.assertEqual((androhung["selectable"], androhung["why"], androhung["practice"]),
                         (True, "Ob die Vorlage die Hinterlegung androhen soll, ist eine offene Frage der Prüfung", "Praxis: 0 von 7"))
        deposit = rows[("frist_beseitigung", "hinterlegung")]
        self.assertEqual((deposit["selectable"], deposit["why"]), (False, "offen: Frist mit Androhung der Hinterlegung schriftlich gesetzt und unbenützt abgelaufen"))
        self.assertIn("eine Hinterlegung droht sie nicht an", self.case.question(1)["answer"])  # the customer reads the alternative where she asked it
        # each question answered, each condition applied to the evidence, nothing left to «prüfen» in the letter
        self.assertEqual([q["state"] for q in self.case.brief["questions"]], ["beantwortet", "bedingt", "bedingt"])
        self.assertTrue(all(c["state"] in ("erfüllt", "nicht geprüft", "offen") and (c["evidence"] or c["state"] == "nicht geprüft")
                            for r in self.case.brief["rules"] for c in r["conditions"]))
        self.assertNotIn("bitte prüfen", self.case.text)
        self.assertFalse(letters.has_gap(self.case.text))
        self.assertEqual([d["fact"] for d in self.case.brief["deciding"]],
                         ["will_beseitigung", "mangel_besteht", "maengelruege_schriftlich", "reaktion_vermieter", "will_schadenersatz"])
        self.assertEqual([d["changed"] for d in self.case.brief["deciding"]], [None, "neu", None, "neu", "neu"])  # what the replies brought

    def test_an_open_fact_is_asked_precisely_with_what_its_answer_decides(self):
        case = Case(changed(replied(), facts={"reaktion_vermieter": None}), DECKUNG)
        self.assertEqual(case.brief["proposal"], ["schadenersatz"])  # no way of the wish to remedy holds without the reaction
        self.assertIn("Bitte teilen Sie uns zudem mit, wie die Vermieterschaft auf Ihre Meldung reagiert hat; davon hängt ab, ob wir Ihnen "
                      "empfehlen, der Vermieterschaft schriftlich eine angemessene Frist zur Beseitigung des Mangels zu setzen.", case.text)
        ask = next(a for a in case.brief["asks"] if a["key"] == "fact:reaktion_vermieter")
        self.assertEqual((ask["what"], ask["blocks"]), ("Wie hat die Vermieterschaft auf Ihre Meldung reagiert?",
                                                         {"question": None, "option": "frist_beseitigung", "condition": "Sie hat ihn nicht beseitigt"}))
        self.assertEqual({b["value"]: b["proposal"] for b in ask["branches"]},  # what each answer decides, by the same rules
                         {"Mangel behoben / Einigung": ["Kosten belegen und Ersatz verlangen"],
                          "Abgelehnt / offene Punkte": ["Frist zur Beseitigung setzen", "Kosten belegen und Ersatz verlangen"],
                          "Keine Reaktion": ["Frist zur Beseitigung setzen", "Kosten belegen und Ersatz verlangen"]})
        self.assertNotIn("bitte prüfen", case.text)
        self.assertFalse(letters.has_gap(case.text))
        # nothing to propose at all: the recommendation is the question and what it decides, not a gap
        alone = Case(changed(replied(), facts={"reaktion_vermieter": None, "will_schadenersatz": False}), DECKUNG)
        self.assertIn("Wir empfehlen Ihnen, uns mitzuteilen, wie die Vermieterschaft auf Ihre Meldung reagiert hat; davon hängt ab, ob wir "
                      "Ihnen empfehlen, der Vermieterschaft schriftlich eine angemessene Frist zur Beseitigung des Mangels zu setzen.", alone.text)
        self.assertNotIn("[bitte ergänzen: die Empfehlung", alone.text)
        self.assertNotIn("Sie machen folgende Kosten geltend", alone.text)  # a claim no longer wanted is not stated
        held = Case(changed(replied(), facts={"reaktion_vermieter": None}), DECKUNG,
                    marks={f"{WID}:rueckfrage.reaktion_vermieter": {"mark": "frage", "content_sha256": "x"}})
        self.assertNotIn("wie die Vermieterschaft auf Ihre Meldung reagiert hat", held.text)  # a question under review is not used
        self.assertIn("[bitte ergänzen: die Frage, von der die Empfehlung abhängt (in Prüfung)]", held.text)
        self.assertEqual(next(a for a in held.brief["asks"] if a["key"] == "fact:reaktion_vermieter")["what"], "Wie hat die Vermieterschaft reagiert?")


# -- a plausible but wrong recommendation ----------------------------------------------------------------------------------------

class WrongRecommendationTests(unittest.TestCase):
    """Steering, point 3: not only a missing citation; an option whose conditions hold only on a presumed or contradicted
    fact, or one a question's word triggers while the customer wants the opposite, is not proposed, or only «unter
    Vorbehalt» with the failing condition named."""

    def test_a_wish_read_against_the_customers_own_words_is_not_proposed(self):
        # the reading recorded «Herabsetzung gewünscht» from the very sentence that rejects it
        misread = {"will_reduktion": {"value": True, "status": "established", "quote": "Eine Mietzinsreduktion möchte ich nicht."}}
        case = Case(changed(replied(), facts=misread), DECKUNG)
        self.assertEqual(case.brief["contradicted"], {"will_reduktion": "Eine Mietzinsreduktion möchte ich nicht."})
        self.assertNotIn("reduktion", case.brief["proposal"])
        self.assertEqual(case.option("reduktion")["state"], "open")
        self.assertEqual(case.option("reduktion")["triggers"][0]["state"], "widersprüchlich")
        self.assertNotIn("Herabsetzung", case.brief["in_case"][0]["text"])  # «Sie möchten …» states only what she wants
        self.assertNotIn("Herabsetzung des Mietzinses, soweit", case.text)
        asked = Case(changed(replied(), facts=misread, questions=[("Kann ich eine Herabsetzung der Miete verlangen?", ["reduktion"])]), DECKUNG).question(0)
        self.assertEqual((asked["state"], asked["row"]), ("pruefen", 7))  # the rule rests on a contradicted reading: the handler decides
        # the same holds when the question itself rejects the wish the reading recorded
        rejected = Case(changed(replied(), facts={"will_reduktion": {"value": True, "status": "established", "quote": "Ich habe Schimmel."}},
                                questions=[("Ich will keine Reduktion. Muss ich die volle Miete weiter bezahlen?", ["hinterlegung"])]), DECKUNG)
        self.assertEqual(rejected.brief["contradicted"], {"will_reduktion": "Ich will keine Reduktion. Muss ich die volle Miete weiter bezahlen?"})
        self.assertNotIn("reduktion", rejected.brief["proposal"])

    def test_a_question_negating_what_triggers_an_option_does_not_trigger_it(self):
        asking = Case(changed(replied(), questions=[("Darf ich die Miete hinterlegen?", ["hinterlegung"])]), DECKUNG)
        self.assertEqual(asking.option("frist_androhung")["state"], "holds")  # asked for: selectable under «ändern»
        negating = Case(changed(replied(), questions=[("Ich möchte keine Hinterlegung, nur eine Herabsetzung. Wie gehe ich vor?", ["hinterlegung"])]),
                        DECKUNG)
        self.assertEqual(negating.question(0)["intent"], "hinterlegen")  # the keyword matches …
        self.assertEqual(negating.option("frist_androhung")["state"], "fails")  # … but she wants the opposite: never offered
        self.assertNotIn("frist_androhung", [o["id"] for o in (negating.decision or {}).get("options") or ()])
        self.assertEqual(negating.question(0)["state"], "pruefen")

    def test_an_option_on_a_presumed_fact_is_proposed_only_unter_vorbehalt_with_the_condition_named(self):
        case = Case(changed(replied(), facts={"mangel_besteht": {"value": True, "status": "presumed"}}), DECKUNG)
        option = case.option("frist_beseitigung")
        self.assertEqual((option["state"], option["proposed"]), ("holds", True))
        self.assertEqual(option["reserve"], [{"fact": "mangel_besteht", "question": "Besteht der Mangel aktuell noch?",
                                              "condition": "Besteht der Mangel aktuell noch?", "state": "vermutet"}])
        self.assertEqual(case.decision["reserve"], ["Besteht der Mangel aktuell noch?"])
        self.assertIn("unter Vorbehalt: Besteht der Mangel aktuell noch?", case.decision["detail"])
        self.assertIn("Wir empfehlen Ihnen, sofern der Mangel weiterhin besteht, der Vermieterschaft schriftlich", case.text)

    def test_an_option_on_a_contradicted_or_corrected_fact_is_not_proposed(self):
        conflicting = Case(changed(replied(), facts={"reaktion_vermieter": {"value": "Abgelehnt / offene Punkte", "status": "conflicting"}}), DECKUNG)
        self.assertEqual(conflicting.option("frist_beseitigung")["state"], "open")  # a value read two ways is never relied on
        self.assertNotIn("frist_beseitigung", conflicting.brief["proposal"])
        corrected = Case(replied(), DECKUNG + ep.decided(("mangel_besteht", "nein")))  # P-contra: the handler corrected it
        self.assertEqual(corrected.option("frist_beseitigung")["state"], "fails")
        self.assertNotIn("Frist zur Beseitigung", corrected.brief["letter"]["empfehlung"])


# -- why evidence was asked, and what a later arrival settles ---------------------------------------------------------------------

def arrival(prior_result, new_files, entries=(), facts=(), claims=(), summary="Neue Unterlagen."):
    """An update of the replied case with ``new_files`` read by the scripted reader: (result, files)."""
    prior = {"id": "run_b", "workflow_id": WID, "workflow_version": _PREPARED_version(), "routing": None, "result": prior_result}
    files = FILES + list(new_files)
    outcome, _ = ep.updated(prior, files, ep.update_turns(list(entries), list(facts), summary, claims=list(claims)), NS)
    assert outcome["status"] == "completed", outcome.get("error")
    return outcome["result"], files


CARPET = ep.text_file("fu", "Quittung Teppichreinigung.txt", "Reinigung Muster GmbH\nTeppichreinigung Wohnzimmer am 02.09.2026\n"
                                                                "Total CHF 85.00\nBar bezahlt\n".encode())
SHOP = ep.text_file("fq", "Quittung Drogerie.txt", "Drogerie Exempel, Marktgasse 9\nQuittung Nr. 4711\nSchimmelentferner, Fugenbürste\n"
                                                   "Total CHF 25.40\nBar bezahlt\n".encode())
PHOTOS = ep.text_file("fp", "Fotos Schimmel.txt", "Foto 1: Ecke über dem Fenster, Schimmel unverändert.\nFoto 2: Bad, Decke.\n".encode())
BILL_WORDS = ep.text_file("fw", "Abrechnung Energie Beispiel.txt", "Energie Beispiel AG\nZusatzabrechnung Zähler 08-4411\n"
                                                                    "Energieverbrauch Bautrockner 07.08.2026 bis 04.09.2026: 212 kWh\n"
                                                                    "Betrag: CHF 85.40\n".encode())
QUOTE = "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben."
# what the reader records for each of them on its entry (NEEDS_C §1): same amount but another expense; another expense and
# amount; the same cost in other words («Energieverbrauch», kWh, a meter: never «Stromkosten»)
CARPET_RECORD = receipt("Total CHF 85.00", "Teppichreinigung Wohnzimmer", "Reinigung", amount="CHF 85.00", party="Reinigung Muster GmbH",
                        when={"from": "2026-09-02", "to": "2026-09-02"})
BILL_RECORD = receipt("Betrag: CHF 85.40", "Energieverbrauch des Bautrockners", "Energie", amount="CHF 85.40", role="requested",
                      party="Energie Beispiel AG", transaction="08-4411", when={"from": "2026-08-07", "to": "2026-09-04"})


def comparable(brief):
    return {"questions": [(q["item_id"], q["state"], q["row"], q["answer"]) for q in brief["questions"]],
            "options": [(o["id"], o["state"], [c["state"] for c in o["conditions"]]) for o in brief["options"]],
            "proposal": brief["proposal"], "residual": [(r["key"], r["line"], r["blocks"]) for r in brief["residual"]],
            "asks": [(a["key"], a.get("blocks")) for a in brief["asks"]], "letter": brief["letter"]}


class BlocksTests(unittest.TestCase):
    """Steering, point 4: CasePath remembers why evidence was requested. Every residual line and ask names the judgment it
    would settle (``blocks``: question, option, condition); a later arrival that establishes it re-evaluates the
    assessment and shows the consequence; an unrelated arrival changes nothing."""

    @classmethod
    def setUpClass(cls):
        cls.before = Case(replied(), DECKUNG)

    def test_every_residual_line_and_ask_names_the_judgment_it_blocks(self):
        for row in self.before.brief["residual"] + self.before.brief["asks"]:
            self.assertEqual(sorted(row["blocks"]), ["condition", "option", "question"])
        self.assertEqual(self.before.brief["residual"][0]["blocks"],
                         {"question": "customer_question:2", "option": "schadenersatz", "condition": "Kosten mit Belegen nachgewiesen"})
        gaps = Case(changed(replied(), facts={"mangel_besteht": None}), DECKUNG)
        ask = next(a for a in gaps.brief["asks"] if a["key"] == "fact:mangel_besteht")
        self.assertEqual(ask["blocks"], {"question": "customer_question:0", "option": "frist_beseitigung", "condition": "Besteht der Mangel aktuell noch?"})
        self.assertEqual(ask["what"], "Besteht der Mangel heute noch?")

    def test_the_receipt_asked_for_settles_the_judgment_it_was_asked_for(self):
        receipts = NS.branches["B-receipts"]  # the customer's reply A5 + 20 days, the bill attached, read as its own entry
        prior = {"id": "run_b", "workflow_id": WID, "workflow_version": _PREPARED_version(), "routing": None, "result": replied()}
        outcome, _ = ep.updated(prior, FILES + receipts.core_files(), receipts.turns(16, 17), NS)
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        files = FILES + receipts.core_files()
        bill = next(e for e in outcome["result"]["record"]["entries"] if e["file"] == "ft")
        self.assertEqual((bill["receipt"]["expense"], bill["receipt"]["citations"][0]["quote"]), ("Energieverbrauch des Bautrockners", "Betrag: CHF 85.40"))
        after = Case(outcome["result"], DECKUNG, files=files, day=NS.a5_day + ep.timedelta(days=ep.RECEIPTS_DAYS))
        self.assertEqual([r for r in after.brief["residual"] if r["kind"] == "claim"], [])  # nothing asked again
        q = after.question(2)
        self.assertEqual((q["state"], q["row"], q["reason"]), ("beantwortet", 10, "Belege liegen vor"))  # the answer it waited for
        self.assertIn("Die Belege zu Ihren Kosten liegen uns vor.", q["answer"])
        self.assertNotIn("steht unten", q["answer"])
        condition = next(c for c in after.rule("259e")["conditions"] if c["text"] == "Kosten mit Belegen nachgewiesen")
        self.assertEqual((condition["state"], condition["evidence"][0]["quote"]), ("erfüllt", "Betrag: CHF 85.40"))
        self.assertEqual(after.option("schadenersatz")["state"], "holds")
        settled = next(r for r in after.brief["resolved"] if r["key"] == "residual:claim.0")
        self.assertEqual((settled["line"], settled["by"][0]["file"], settled["by"][0]["quote"], settled["blocks"], settled["now"]),
                         ("Belege zu: Stromkosten für den Bautrockner", "ft", "Betrag: CHF 85.40",
                          {"question": "customer_question:2", "option": "schadenersatz", "condition": "Kosten mit Belegen nachgewiesen"},
                          {"option": "holds", "condition": "erfüllt", "question": "beantwortet"}))
        self.assertNotIn("Bitte reichen Sie uns noch nach", after.text)

    def test_a_fact_arriving_later_answers_the_question_that_waited_for_it(self):
        waiting = Case(changed(replied(), facts={"mangel_besteht": None}), DECKUNG)
        q = waiting.question(0)
        self.assertEqual((q["state"], q["row"], q["reason"]), ("bedingt", 8, "Besteht der Mangel heute noch?"))
        self.assertNotIn("frist_beseitigung", waiting.brief["proposal"])
        settled = Case(replied(), DECKUNG)  # the reply says it: «Der Schimmel ist immer noch da.»
        self.assertEqual((settled.question(0)["state"], settled.option("frist_beseitigung")["state"]), ("beantwortet", "holds"))
        row = next(r for r in settled.brief["resolved"] if r["key"] == "fact:mangel_besteht")
        self.assertEqual((row["blocks"]["question"], row["blocks"]["option"], row["now"]),
                         ("customer_question:0", "frist_beseitigung", {"question": "beantwortet", "option": "holds", "condition": "erfüllt"}))
        self.assertEqual(row["by"][0]["quote"], "Der Schimmel ist immer noch da.")

    def test_an_unrelated_arrival_changes_nothing(self):
        for name, new, entry in (
                ("photos", [PHOTOS], ep.entry(16, "fp", None, None, "kunde", "versicherer", "unterlagen", "Fotos des Schimmels", "Foto 1: Ecke über dem Fenster")),
                ("a same-amount receipt of another expense", [CARPET],
                 ep.entry(16, "fu", None, None, "andere", "kunde", "andere", "Quittung Teppichreinigung", "Total CHF 85.00", receipt=CARPET_RECORD))):
            with self.subTest(name):
                result, files = arrival(replied(), new, entries=[entry])
                after = Case(result, DECKUNG, files=files)
                self.assertEqual(comparable(after.brief), comparable(self.before.brief))
                self.assertFalse(any(r["key"].startswith("residual:") for r in after.brief["resolved"]))


# -- claims and receipts: a shared word or amount is a candidate, not proof ---------------------------------------------------

class ReceiptTests(unittest.TestCase):
    """Steering, point 5: the reader records what a claim is about and, on a receipt's own entry, what the receipt records
    (expense, party, period, transaction, the amount's role); «documented» needs them to agree, decided by one rule
    (assessment.documented_by: Slice C's account.documented once merged, the same comparison standing in until then).
    Deterministic, no model call per field."""

    def arrived(self, new_file, record):
        result, files = arrival(replied(), [new_file], entries=[ep.entry(16, new_file["id"], None, None, "andere", "kunde", "andere",
                                                                         new_file["name"], record["quote"], receipt=record)])
        return result, files, Case(result, DECKUNG, files=files)

    def test_a_same_amount_receipt_for_another_expense_is_rejected_and_a_paraphrase_is_accepted(self):
        self.assertIn(85.0, options.amounts(CARPET_RECORD["quote"]))  # the same amount: a candidate …
        self.assertNotIn("strom", BILL_WORDS["extraction"]["text"].lower())  # … the bill names the cost in other words
        _, _, refused = self.arrived(CARPET, CARPET_RECORD)
        line = refused.brief["residual"][0]
        # one rule decides (Slice C's account.documented): every candidate that shares a word or the amount is set aside with
        # its reasons, the earlier mails about the dryer among them; the same-amount receipt is set aside for its expense
        carpet = next(x for x in line["set_aside"] if x["file"] == CARPET["id"])
        self.assertEqual((line["key"], carpet["expense"], carpet["why"]), ("residual:claim.0", "Teppichreinigung Wohnzimmer",
                                                                           ["andere Ausgabe: Teppichreinigung Wohnzimmer"]))
        self.assertEqual((refused.question(2)["state"], [r["key"] for r in refused.brief["asks"]]), ("bedingt", ["residual:claim.0"]))
        _, _, accepted = self.arrived(BILL_WORDS, {**BILL_RECORD, "expense": "Energieverbrauch Bautrockner"})
        # accepted without the handler entering anything: the claim line goes, the question it blocked is answered
        self.assertEqual(([r["key"] for r in accepted.brief["residual"]], accepted.question(2)["state"]), ([], "beantwortet"))
        self.assertEqual(accepted.brief["resolved"][0]["by"][0]["file"], "fw")

    def test_one_rule_decides_whether_a_receipt_documents_a_claim(self):
        result, files, _ = self.arrived(BILL_WORDS, BILL_RECORD)
        state = core.evaluate(area.workflow(WID), [], DECKUNG, result, "c")
        looked = ep.looked_at(files, NS.a5_day)
        self.assertTrue(assessment.claims_of(result, looked, state["account"])[0]["documented"])  # the stand-in agrees
        # once Slice C's account.documented is there, it alone decides: its «no» is the residual's «no»
        seen = []
        with mock.patch.object(assessment.account, "documented", create=True,
                               side_effect=lambda claim, files, entries, why=None: seen.append(claim["what"]) or None):
            claims = assessment.claims_of(result, looked, state["account"])
            case = Case(result, DECKUNG, files=files)
        self.assertEqual((claims[0]["documented"], seen[0]), (False, "Stromkosten für den Bautrockner"))
        self.assertEqual([r["kind"] for r in case.brief["residual"]], ["claim"])
        with mock.patch.object(assessment.account, "documented", create=True,
                               side_effect=lambda claim, files, entries, why=None: {"file": "fw", "how": "receipt", "n": 16, "basis": {}}):
            self.assertEqual(Case(result, DECKUNG, files=files).question(2)["state"], "beantwortet")

    def test_the_amounts_role_period_and_party_must_agree(self):
        claim_ = {"expense_kind": "Energie", "party": None, "period": None, "transaction": None, "amount": "CHF 85",
                  "citations": [{"quote": QUOTE}]}  # «von rund CHF 85»: within its rounding
        bill = {**BILL_RECORD, "payer": "kunde"}
        self.assertTrue(options.agreement(claim_, bill)["documented"])
        for field, value in (("role", "refunded"), ("role", "promised"), ("role", "disputed"), ("payer", "gegenpartei"), ("expense_kind", "Reinigung"),
                             ("amount", "CHF 120.00"), ("expense_kind", "andere")):
            with self.subTest(f"{field}={value}"):
                self.assertFalse(options.agreement(claim_, {**bill, field: value})["documented"])
        exact = options.agreement({**claim_, "citations": [{"quote": "Die Stromkosten von CHF 85 möchte ich ersetzt haben."}]}, {**bill, "amount": "CHF 88.40"})
        self.assertEqual(exact["amount"], False)  # not «rund»: the amount must be the one written
        last_year = options.agreement({**claim_, "period": {"from": "2026-08-01", "to": "2026-08-31"}},
                                      {**bill, "period": {"from": "2025-01-01", "to": "2025-03-31"}})
        self.assertEqual((last_year["period"], last_year["documented"]), (False, False))
        other_issuer = options.agreement({**claim_, "party": "Energie Beispiel AG"}, {**bill, "party": "Teppich Muster GmbH"})
        self.assertEqual((other_issuer["party"], other_issuer["documented"]), (False, False))
        nothing_but_the_kind = options.agreement({"expense_kind": "Energie"}, {"expense_kind": "Energie", "role": "paid"})
        self.assertFalse(nothing_but_the_kind["documented"])  # the same kind of expense alone documents nothing
        self.assertEqual(options.period_of("Verbrauch 07.08.2026 bis 04.09.2026"), (ep.date(2026, 8, 7), ep.date(2026, 9, 4)))
        self.assertEqual(options.period_of("im August 2026"), (ep.date(2026, 8, 1), ep.date(2026, 8, 31)))

    def test_a_claim_paid_back_is_not_named(self):
        work = team.CaseWork(case=ep.case_row(), files=core.case_files(FILES), base_workflow=area.workflow(WID))
        refunded = team._located_brief(work, {"summary": "x", "questions": [], "claims": [
            claim("Stromkosten für den Bautrockner", QUOTE, amount="CHF 85", file="fc", kind="Energie", role="refunded")]})["claims"][0]
        self.assertFalse(refunded["checked"])


# -- the routes ---------------------------------------------------------------------------------------------------------------------

class RouteTests(unittest.TestCase):
    """POST /api/cases/{id}/recommendation and /answer, and the events route for a residual line, on S-D11A in a case store."""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": cls.directory.name, "CASEPATH_DEV_USER": "dev"}),
                                           model_factory=lambda: None))
        store, runs = cls.client.app.state.store, cls.client.app.state.runs
        case = ep.seed_phase_a(store, runs)
        ep.add_replies(store, case["id"])
        runs.model_factory = lambda token=None: ep.update_model(store, case["id"], NS.turns_b(), NS.reply_names)
        run = ep.wait(store, runs.update(case["id"], "dev")["id"])
        assert run["status"] == "completed", run.get("error")
        cls.case_id = case["id"]
        cls.source, cls.copy = ep.seed_frozen_copy(store, runs)

    @classmethod
    def tearDownClass(cls):
        cls.client.app.state.runs.shutdown()
        cls.client.app.state.store.close()
        cls.directory.cleanup()

    def view(self):
        return self.client.get(f"/api/cases/{self.case_id}").json()

    def test_the_case_view_carries_the_brief_and_the_routes_decide_on_it(self):
        view = self.view()
        self.assertEqual((view["assessment"]["under_premise"], view["screen"]["decision"]["key"]), (True, "deckung"))
        self.assertEqual(self.client.post(f"/api/cases/{self.case_id}/recommendation", json={"chosen": ["frist_beseitigung"],
                                          "proposal": view["assessment"]["proposal"]}).status_code, 409)  # the cover first
        edit = self.client.post(f"/api/cases/{self.case_id}/edits", json={"op": "set_fact", "args": {"fact": "deckung", "value": "bestätigt"},
                                                                         "reason": "", "reason_code": "none", "recheck": False})
        self.assertEqual(edit.status_code, 201, edit.text)
        view = self.view()
        proposal = view["assessment"]["proposal"]
        self.assertEqual((view["screen"]["decision"]["key"], proposal), ("empfehlung", ["frist_beseitigung", "schadenersatz"]))
        wrong = self.client.post(f"/api/cases/{self.case_id}/recommendation", json={"chosen": ["hinterlegung"], "proposal": proposal})
        self.assertEqual((wrong.status_code, wrong.json()["detail"]), (422, "«Mietzins hinterlegen» trifft nach der Akte nicht zu."))
        stale = self.client.post(f"/api/cases/{self.case_id}/recommendation", json={"chosen": proposal, "proposal": ["frist_beseitigung"]})
        self.assertEqual(stale.status_code, 422)
        two = self.client.post(f"/api/cases/{self.case_id}/recommendation", json={"chosen": ["frist_beseitigung", "frist_androhung"], "proposal": proposal})
        self.assertEqual((two.status_code, two.json()["detail"]), (422, "Je Wunsch der Kundschaft ein Weg."))
        done = self.client.post(f"/api/cases/{self.case_id}/recommendation", json={"chosen": proposal, "proposal": proposal})
        self.assertEqual(done.status_code, 201, done.text)
        self.assertEqual(sorted(done.json()), ["event"])  # adopting the way judges nothing about the prospects
        view = self.view()
        self.assertEqual((view["assessment"]["chosen"], [b["key"] for b in view["assessment"]["blocking"]], view["screen"]["decision"]["key"]),
                         (proposal, ["aussichten"], "aussichten"))
        prospects = self.client.post(f"/api/cases/{self.case_id}/edits", json={"op": "set_fact", "args": {"fact": "aussichten", "value": "genügend"},
                                                                              "reason": "", "reason_code": "none", "recheck": False})
        self.assertEqual(prospects.status_code, 201, prospects.text)
        view = self.view()
        self.assertEqual((view["assessment"]["blocking"], view["screen"]["decision"]), ([], None))
        self.assertNotIn("[bitte ergänzen", view["draft"]["text"])
        events = self.client.get(f"/api/cases/{self.case_id}/events").json()["events"]
        # two decisions, each recorded by itself: the way adopted, then the prospects judged through the edit
        self.assertEqual([e["item_id"] for e in events if e["kind"] == "item.corrected"][-2:], ["point:empfehlung", "fact:aussichten"])
        # «übernehmen» on a question's drafted answer
        taken_ = self.client.post(f"/api/cases/{self.case_id}/answer", json={"item_id": "customer_question:1", "point": "hinterlegung", "intent": "hinterlegen"})
        self.assertEqual(taken_.status_code, 201, taken_.text)
        q = self.view()["assessment"]["questions"][1]
        self.assertEqual((q["state"], q["taken"]), ("beantwortet", True))
        self.assertEqual(self.client.post(f"/api/cases/{self.case_id}/answer", json={"item_id": "customer_question:1", "point": "reduktion"}).status_code,
                         422)  # «Eine Mietzinsreduktion möchte ich nicht»: the point does not apply
        self.assertEqual(self.client.post(f"/api/cases/{self.case_id}/answer", json={"item_id": "customer_question:1", "point": "hinterlegung",
                                                                                    "intent": "ersatz"}).status_code, 422)
        # a residual line unticked through the events route
        line = self.client.post(f"/api/cases/{self.case_id}/events", json={"kind": "letter.line", "item_id": "residual:claim.0", "fields": {"included": False}})
        self.assertEqual(line.status_code, 201, line.text)
        view = self.view()
        self.assertEqual(view["assessment"]["asks"], [])
        self.assertNotIn("Bitte reichen Sie uns noch nach", view["draft"]["text"])

    def test_a_study_copy_decides_nothing(self):
        for path, body in (("recommendation", {"chosen": ["frist_beseitigung"], "proposal": []}),
                           ("answer", {"item_id": "customer_question:0", "point": "hinterlegung"})):
            self.assertEqual(self.client.post(f"/api/cases/{self.copy['id']}/{path}", json=body).status_code, 409, path)


if __name__ == "__main__":
    unittest.main()

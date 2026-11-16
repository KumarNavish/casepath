"""The trial «reader_intents» (process/live.py): the reader names what a customer's question asks, by meaning, as it names
the key points; the area's word stems stay the fallback and every guard stays code's. Off unless the deployment names the
trial (CASEPATH_SPEED_TRIALS): without it the reader's contract and every result are as before.

Why: on the one real later arrival read by a model (2026-11-16), two of three questions the reader had tagged with key
points that applied waited as «Absicht der Frage unklar», because none of the area's stems stood in their wording.

Scripted and model-free."""
import copy
import unittest

from casepath.agents import team
from casepath.config import load_settings
from casepath.process import area, live, options
from tests.scripted import ScriptedModel, report
from tests.test_account_coverage import CASE, FIRST, MORE, WID, long_files
from tests.test_assessment import DECKUNG, Case, changed, replied

STROM = "Bekomme ich das Geld für den Strom zurück?"  # about damages, and no stem of the area in it


def asked(text, about, intent=None):
    result = changed(replied(), questions=[(text, about)])
    if intent:
        result["brief"]["questions"][0]["intent"] = intent
    return Case(result, DECKUNG).question(0)


class MeaningTests(unittest.TestCase):
    def test_every_answer_row_of_the_area_has_its_meaning_and_no_other_is_written(self):
        answers = options.load(WID)["answers"]
        by_point = live.intents(WID, answers)
        named = {row["intent"] for rows in by_point.values() for row in rows}
        self.assertEqual(named, {a["intent"] for a in answers})  # a row added to the area needs its meaning written, or the trial cannot name it
        self.assertEqual([r["intent"] for r in by_point["hinterlegung"]], ["hinterlegen", "weiter_zahlen", "zurueckbehalten"])
        self.assertEqual(by_point["schadenersatz"], [{"intent": "ersatz", "meaning": "ob Kosten oder ein Schaden ersetzt werden und wer dafür aufkommt"}])
        self.assertEqual(live.intents("werkvertrag-bau", answers), {})  # an area without meanings: the trial changes nothing there

    def test_the_trial_is_named_by_the_deployment_and_off_by_default(self):
        self.assertEqual(load_settings({}).speed_trials, ())
        self.assertEqual(load_settings({"CASEPATH_SPEED_TRIALS": "reader_intents, unknown"}).speed_trials, ("reader_intents",))


class StatusTests(unittest.TestCase):
    def test_a_named_intent_answers_where_no_stem_stood_in_the_wording(self):
        before = asked(STROM, ["schadenersatz"])
        self.assertEqual((before["state"], before["row"], before["reason"]), ("pruefen", 11, "Absicht der Frage unklar"))
        named = asked(STROM, ["schadenersatz"], "ersatz")
        self.assertEqual((named["state"], named["row"], named["intent"]), ("bedingt", 9, "ersatz"))  # the area's own row for it: an answer with its condition

    def test_the_guards_stay_codes(self):
        # an intent of a key point the question is not tagged with is not taken (the reader's report drops it, and the
        # assessment looks only among the rows of the question's own key points)
        other = asked(STROM, ["schadenersatz"], "melden")
        self.assertEqual((other["state"], other["row"]), ("pruefen", 11))
        # a negation before a word of the tagged point still holds the question for the handler
        negated = asked("Ich will keinen Schadenersatz, wer zahlt mir den Strom?", ["schadenersatz"], "ersatz")
        self.assertEqual((negated["state"], negated["row"]), ("pruefen", 3))
        # no key point, no answer: a named intent alone decides nothing
        untagged = asked(STROM, [], "ersatz")
        self.assertEqual((untagged["state"], untagged["row"]), ("offen", 2))
        # where a stem matches and the reader names another intent of the same key point, the reader's reading governs
        both = asked("Darf ich die Miete hinterlegen?", ["hinterlegung"], "weiter_zahlen")
        self.assertEqual(both["intent"], "weiter_zahlen")


class Recording(ScriptedModel):
    """The scripted model, keeping each call's tools as offered (the scripted one keeps their names)."""

    def respond(self, *, tools=(), **kw):
        self.offered = getattr(self, "offered", []) + [list(tools)]
        return super().respond(tools=tools, **kw)


class ReaderTests(unittest.TestCase):
    def run_with(self, trials, questions):
        cite = [{"file": "f1", "quote": "Die Vermieterin zahlt nichts."}]
        fact = ("record_fact", {"part": None, "fact": "rechtsgebiet", "status": "established", "value": "Mietrecht / Mangel", "citations": cite})
        steps = [("record_steps", {"entries": copy.deepcopy(FIRST + MORE)})]
        asked_ = [{"question": q, "citations": cite, "about": about, **({"asks": asks} if asks is not None else {})} for q, about, asks in questions]
        model = Recording([[("list_files", {})], [*steps, fact], [report("claim_reader", request="Reparaturkosten.", questions=asked_)],
                               [report("document_finder")], *[[report("result_checker", answer="Vorbereitet.")]] * 3])
        result = team.CaseTeam(model, speed_trials=trials).run(case={**CASE, "workflow_id": WID},
                                                              files=[{"id": "f1", "name": "Akte Bianchi.pdf", **long_files()[0]["extraction"]}],
                                                              workflow=area.workflow(WID))
        return result, model

    def schema_of(self, model):
        """The claim reader's report tool as the model was offered it."""
        tools = next(t for t in model.offered if any(x["name"] == "report" and "questions" in x["parameters"]["properties"] for x in t))
        return next(x for x in tools if x["name"] == "report")["parameters"]["properties"]["questions"]["items"]

    def test_without_the_trial_the_readers_contract_is_as_before(self):
        result, model = self.run_with((), [(STROM, ["schadenersatz"], None)])
        self.assertEqual(sorted(self.schema_of(model)["properties"]), ["about", "citations", "question"])
        self.assertEqual(result["brief"]["questions"], [{"question": STROM, "citations": result["brief"]["questions"][0]["citations"], "about": ["schadenersatz"]}])
        self.assertNotIn("ob Kosten oder ein Schaden ersetzt werden", str(model.inputs))  # no meaning is shown to the reader

    def test_with_the_trial_the_reader_is_asked_and_only_a_fitting_answer_is_kept(self):
        result, model = self.run_with({"reader_intents"}, [(STROM, ["schadenersatz"], "ersatz"),  # fits its key point
                                                           ("Muss ich weiter zahlen?", ["schadenersatz"], "weiter_zahlen"),  # of another key point
                                                           ("Und sonst?", [], "none")])
        asks = self.schema_of(model)["properties"]["asks"]
        self.assertEqual(asks["enum"], ["ausziehen", "ersatz", "herabsetzung", "hinterlegen", "melden", "weiter_zahlen", "zurueckbehalten", "none"])
        self.assertIn("by meaning, not by its words", asks["description"])
        self.assertIn("asks", self.schema_of(model)["required"])
        self.assertEqual([(q["about"], q.get("intent")) for q in result["brief"]["questions"]],
                         [(["schadenersatz"], "ersatz"), (["schadenersatz"], None), ([], None)])
        self.assertIn("ob Kosten oder ein Schaden ersetzt werden und wer dafür aufkommt", str(model.inputs))  # the process view names what each key point's questions ask


if __name__ == "__main__":
    unittest.main()

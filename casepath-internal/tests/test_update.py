"""«Aktualisieren»: an update run reads only what came in after a preparation (casepath/agents/core.py update,
casepath/agents/team.py CaseTeam.update). The reader gets the new documents in full and the case so far in one compact
view; the document finder only the needs still missing; the second reading and the source checker what changed; the
result checker does not run. Code re-derives the account, the evaluation, the items and the next action from the merged
result, as for a full run.

Equivalence, on the scripted team: a case prepared from files A and then updated with file B ends with the same account
entries, facts, documents and next action as a case prepared from A and B together. Entry numbers may differ (an update
numbers after the existing entries), so entries and their links are compared by the document they stand for.

Scripted and model-free; every file, name and amount is made up."""
import copy
import json
import tempfile
import unittest

from casepath.agents import core, team
from casepath.process import account, area
from casepath.process.items import build_items
from tests.scripted import ScriptedModel, report

WID = "mietmangel-handler"
CASE = {"id": "case_u", "title": "Mietmangel (synthetisch) 4321.5555.0001", "intake": {}, "workflow_id": WID}
AS_OF = "2026-11-15"


def paged(fid, name, pages, segments=None):
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in enumerate(pages, 1))
    return {"id": fid, "name": name, "kind": "pdf", "media_type": "application/pdf", "sha256": fid,
            "extraction": {"text": text, "pages": len(pages), "readable": True, "note": "", **({"segments": segments} if segments else {})}}


def mail(fid, name, body):
    return {"id": fid, "name": name, "kind": "email", "media_type": "message/rfc822", "sha256": fid,
            "extraction": {"text": body, "pages": 1, "readable": True, "note": ""}}


def segment(page, day, sender, kind, title):
    return {"first_page": page, "last_page": page, "kind": kind, "date": day, "sender": sender, "recipient": None, "title": title, "summary": ""}


def entry(n, fid, page, day, sender, to, kind, what, quote, **elements):
    return {"n": n, "file": fid, "page": page, "date": day, "from": sender, "to": to, "kind": kind, "phone": False, "what": what,
            "quote": quote, "asks": [], "answers": [], "terms": [], "paid": [], "next": [], **elements}


def ask(what, of, quote, by_date=None):
    return {"what": what, "of": of, "by": None, "by_date": by_date, "repeats": None, "warns": False, "quote": quote}


def answer(what, n, quote):
    return {"what": what, "answers": n, "quote": quote}


def fact(fid, name, value, quote):
    return ("record_fact", {"part": None, "fact": name, "status": "established", "value": value, "citations": [{"file": fid, "quote": quote}]})


def document(fid, name, quote, status="present"):
    return ("record_document", {"document": name, "status": status, "files": [fid] if status != "absent" else [],
                                "citations": [{"file": fid, "quote": quote}] if status != "absent" else [], "note": ""})


def decided(*pairs):
    return [{"id": f"e{i}", "op": "set_fact", "args": {"fact": f, "value": v}, "by": "handler", "status": "active"} for i, (f, v) in enumerate(pairs)]


def job(files, edits=()):
    return {"format": core.JOB, "case": dict(CASE), "files": copy.deepcopy(files), "workflows": [area.workflow(WID)], "knowledge": [],
            "edits": list(edits), "options": {"read_scans": False}}


class Recorded(ScriptedModel):
    """The scripted model, keeping every call's name and input as it went out (for what each agent receives)."""

    def __init__(self, turns, **kwargs):
        super().__init__(turns, **kwargs)
        self.calls = []

    def respond(self, **kwargs):
        self.calls.append(("turn", kwargs["instructions"], kwargs["input"], [t["name"] for t in kwargs.get("tools") or ()]))
        return super().respond(**kwargs)

    def respond_json(self, **kwargs):
        self.calls.append((kwargs["name"], kwargs["instructions"], kwargs["input"], None))
        return super().respond_json(**kwargs)


def prepared(files, turns, edits=()):
    model = Recorded(turns)
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.prepare(job(files, edits), model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    return {"id": "run_base", "workflow_id": WID, "workflow_version": outcome["workflow"]["version"], "routing": outcome["routing"],
            "result": outcome["result"]}, model


def updated(files, prior, turns, edits=()):
    model = Recorded(turns)
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.update(job(files, edits), prior, model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    return outcome["result"], model


def looked_at(files):
    """The files as the case view evaluates them, on a fixed day."""
    return [{**f, "extraction": {**f["extraction"], "cut_of": {"as_of": AS_OF}}} for f in files]


def view(result, files, edits=()):
    files = looked_at(files)
    state = core.evaluate(area.workflow(WID), [], list(edits), result, "case_u", files=files)
    items = build_items(state, result, files)
    return state, {i["item_id"]: i for i in items}


def same_shape(state, result, items):
    """What must agree: the account's entries (by the document each stands for, with what they ask, answer, agree and
    pay; links by document), every fact, every document finding, and the next action."""
    entries = state["account"]["entries"]
    where = {e["n"]: (e["file"], e["page"], e["date"]) for e in entries}
    cites = lambda rows: [(c.get("file"), c.get("page"), c.get("quote")) for c in rows or ()]
    shaped = []
    for e in entries:
        row = {k: e.get(k) for k in ("file", "page", "date", "from", "to", "kind", "phone", "what")}
        row["citations"] = cites(e.get("citations"))
        for key in account.ELEMENTS:
            row[key] = [{**{k: v for k, v in x.items() if k not in {"citations", "repeats", "answers"}}, "citations": cites(x.get("citations")),
                         **({"repeats": where.get(x["repeats"])} if x.get("repeats") else {}), **({"answers": where.get(x["answers"])} if x.get("answers") else {})}
                        for x in e.get(key) or ()]
        shaped.append(row)
    ledger = [(r["what"], r["by"], r["of"], r["due"], r["times"], where[r["answered"]["n"]] if r["answered"] else None) for r in state["account"]["requests"]]
    facts = {f["fact"]: (f["status"], f.get("value"), f.get("verdict"), cites(f.get("citations"))) for f in result["facts"]}
    documents = {d["document"]: (d["status"], d.get("verdict"), d.get("files"), cites(d.get("citations"))) for d in result["documents"]}
    nxt = items["next_action:0"]
    action = {k: nxt.get(k) for k in ("action", "value", "form", "reason", "incoming", "then", "next_in_days", "since")}
    return {"entries": shaped, "ledger": ledger, "facts": facts, "documents": documents, "next_action": action,
            "stage": (state["evaluation"].get("current") or {}).get("step")}


# -- 1. a cost note arrives in a mandate case -------------------------------------------------------------------------------

MANDATE_A = paged("fa", "Akte Beispiel.pdf", [
    "Von: Lea Beispiel <lea@beispiel.example>\nGesendet: Dienstag, 1. September 2026 09:12\nBetreff: Schimmel im Schlafzimmer\n\n"
    "In meiner Wohnung an der Probegasse 7 wächst seit Juli Schimmel. Die Vermieterin Muster Immobilien AG repariert nichts.",
    "Protekta Rechtsschutz\nBern, 10. September 2026\n\nUm die Versicherungsdeckung prüfen zu können, brauchen wir noch den Mietvertrag. "
    "Bitte senden Sie ihn uns bis 30. September 2026.",
    "Von: Lea Beispiel\nGesendet: Freitag, 18. September 2026 17:40\nBetreff: AW: Unterlagen\n\nIm Anhang sende ich Ihnen den Mietvertrag vom 1. April 2021.",
    "Protekta Rechtsschutz\nBern, 1. Oktober 2026\n\nWir erteilen der Kanzlei Muster Kostengutsprache für die Abklärung der Sach- und "
    "Rechtslage sowie aussergerichtliche Bemühungen.",
], [segment(1, "01.09.2026", "Lea Beispiel", "E-Mail", "Schadenmeldung"), segment(2, "10.09.2026", "Protekta", "Brief", "Anforderung"),
    segment(3, "18.09.2026", "Lea Beispiel", "E-Mail", "Unterlagen"), segment(4, "01.10.2026", "Protekta", "Brief", "Kostengutsprache")])
MANDATE_B = paged("fb", "Zwischenhonorar Kanzlei Muster.pdf", [
    "Kanzlei Muster\nZürich, 5. November 2026\n\nZwischenhonorar: Für unsere Bemühungen bis 31. Oktober 2026 stellen wir Ihnen CHF 3'200 "
    "in Rechnung. Zahlbar innert 30 Tagen."])
MANDATE_ENTRIES_A = [
    entry(1, "fa", 1, "2026-09-01", "kunde", "versicherer", "meldung", "Meldung Schimmel", "Betreff: Schimmel im Schlafzimmer"),
    entry(2, "fa", 2, "2026-09-10", "versicherer", "kunde", "anforderung", "Mietvertrag verlangt", "Bern, 10. September 2026",
          asks=[ask("Mietvertrag", "kunde", "brauchen wir noch den Mietvertrag", "2026-09-30")]),
    entry(3, "fa", 3, "2026-09-18", "kunde", "versicherer", "unterlagen", "Mietvertrag zugestellt", "Betreff: AW: Unterlagen",
          answers=[answer("Mietvertrag", 2, "Im Anhang sende ich Ihnen den Mietvertrag")]),
    entry(4, "fa", 4, "2026-10-01", "versicherer", "kanzlei", "kostengutsprache", "Mandat und Kostengutsprache an Kanzlei Muster",
          "Bern, 1. Oktober 2026")]
MANDATE_ENTRY_B = entry(5, "fb", 1, "2026-11-05", "kanzlei", "versicherer", "kostenforderung", "Zwischenhonorar CHF 3'200", "Zürich, 5. November 2026",
                        terms=[])
MANDATE_FACTS_A = [fact("fa", "rechtsgebiet", "Mietrecht / Mangel", "In meiner Wohnung an der Probegasse 7 wächst seit Juli Schimmel."),
                   fact("fa", "gegenpartei", "Muster Immobilien AG", "Die Vermieterin Muster Immobilien AG repariert nichts.")]
MANDATE_FACT_B = fact("fb", "eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200 (Bemühungen bis 31.10.2026)",
                      "Für unsere Bemühungen bis 31. Oktober 2026 stellen wir Ihnen CHF 3'200 in Rechnung.")
MANDATE_DOCS_A = [document("fa", "mietvertrag", "Im Anhang sende ich Ihnen den Mietvertrag vom 1. April 2021.")]
MANDATE_EDITS = decided(("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei"))

# -- 2. the customer's reply delivers two of three requested documents --------------------------------------------------------

REPLY_A = paged("ra", "Akte Bianchi.pdf", [
    "Von: Marco Bianchi <marco@beispiel.example>\nGesendet: Donnerstag, 1. Oktober 2026 08:30\nBetreff: Feuchtigkeit im Bad\n\n"
    "Im Bad meiner Wohnung an der Seestrasse 12 ist die Wand seit August feucht. Ich habe die Verwaltung am 20. September 2026 schriftlich informiert.",
    "Protekta Rechtsschutz\nBern, 5. Oktober 2026\n\nUm die Sach- und Rechtslage beurteilen zu können, brauchen wir insbesondere noch:\n"
    "– Mietvertrag\n– Mängelrüge an die Verwaltung\n– Fotos des Mangels\nBitte senden Sie uns die Unterlagen bis 26. Oktober 2026.",
], [segment(1, "01.10.2026", "Marco Bianchi", "E-Mail", "Schadenmeldung"), segment(2, "05.10.2026", "Protekta", "Brief", "Anforderung")])
REPLY_B = mail("rb", "AW Unterlagen.eml", "From: marco@beispiel.example\nTo: schaden@rechtsschutz.example\nDate: Tue, 20 Oct 2026 19:05:00 +0200\n"
                                         "Subject: AW: Unterlagen\n\nAnbei sende ich Ihnen den Mietvertrag und meine Mängelrüge an die Verwaltung "
                                         "vom 20. September 2026. Die Fotos reiche ich nach.")
REPLY_ENTRIES_A = [
    entry(1, "ra", 1, "2026-10-01", "kunde", "versicherer", "meldung", "Meldung Feuchtigkeit", "Betreff: Feuchtigkeit im Bad"),
    entry(2, "ra", 2, "2026-10-05", "versicherer", "kunde", "anforderung", "Unterlagen verlangt", "Bern, 5. Oktober 2026",
          asks=[ask("Mietvertrag", "kunde", "– Mietvertrag", "2026-10-26"), ask("Mängelrüge an die Verwaltung", "kunde", "– Mängelrüge an die Verwaltung", "2026-10-26"),
                ask("Fotos des Mangels", "kunde", "– Fotos des Mangels", "2026-10-26")])]
REPLY_ENTRY_B = entry(3, "rb", None, "2026-10-20", "kunde", "versicherer", "unterlagen", "Mietvertrag und Mängelrüge zugestellt", "Subject: AW: Unterlagen",
                      answers=[answer("Mietvertrag", 2, "Anbei sende ich Ihnen den Mietvertrag"),
                               answer("Mängelrüge an die Verwaltung", 2, "meine Mängelrüge an die Verwaltung vom 20. September 2026")],
                      next=[{"what": "Fotos nachreichen", "who": "kunde", "by": None, "by_date": None, "quote": "Die Fotos reiche ich nach."}])
REPLY_FACTS_A = [fact("ra", "rechtsgebiet", "Mietrecht / Mangel", "Im Bad meiner Wohnung an der Seestrasse 12 ist die Wand seit August feucht."),
                 fact("ra", "maengelruege_schriftlich", "ja", "Ich habe die Verwaltung am 20. September 2026 schriftlich informiert.")]
REPLY_DOCS_ABSENT = [document("ra", "fotos", "", status="absent")]
REPLY_DOCS_B = [document("rb", "mietvertrag", "Anbei sende ich Ihnen den Mietvertrag"),
                document("rb", "maengelruege", "meine Mängelrüge an die Verwaltung vom 20. September 2026")]

# -- 3. the other side's letter with an offer, after the insurer's last step --------------------------------------------------

OFFER_A = paged("oa", "Akte Keller.pdf", [
    "Von: Sandra Keller <sandra@beispiel.example>\nGesendet: Dienstag, 1. September 2026 10:00\nBetreff: Heizung kaputt\n\n"
    "Seit August fällt in meiner Wohnung an der Gartenstrasse 14 die Heizung aus. Die Muster Immobilien AG reagiert nicht.",
    "Protekta Rechtsschutz\nBern, 10. Oktober 2026\nAn: Muster Immobilien AG\n\nWir zeigen Ihnen an, dass wir die Interessen von Frau "
    "Sandra Keller vertreten. Wir fordern Sie auf, die Heizung bis 31. Oktober 2026 reparieren zu lassen.",
], [segment(1, "01.09.2026", "Sandra Keller", "E-Mail", "Schadenmeldung"), segment(2, "10.10.2026", "Protekta", "Brief", "Schreiben an die Gegenpartei")])
OFFER_B = paged("ob", "Schreiben Muster Immobilien.pdf", [
    "Muster Immobilien AG\nBern, 5. November 2026\n\nOhne Anerkennung einer Rechtspflicht bieten wir Frau Keller zur Erledigung eine "
    "Mietzinsreduktion von CHF 2'000 an, zahlbar bis 30. November 2026."])
OFFER_ENTRIES_A = [
    entry(1, "oa", 1, "2026-09-01", "kunde", "versicherer", "meldung", "Meldung Heizungsausfall", "Betreff: Heizung kaputt"),
    entry(2, "oa", 2, "2026-10-10", "versicherer", "gegenpartei", "schreiben_gegenpartei", "Aufforderung zur Reparatur", "Bern, 10. Oktober 2026",
          asks=[ask("Heizung reparieren lassen", "gegenpartei", "die Heizung bis 31. Oktober 2026 reparieren zu lassen", "2026-10-31")])]
OFFER_ENTRY_B = entry(3, "ob", 1, "2026-11-05", "gegenpartei", "versicherer", "angebot", "Angebot Mietzinsreduktion CHF 2'000", "Bern, 5. November 2026",
                      terms=[{"what": "Mietzinsreduktion", "amount": "CHF 2'000", "payer": "gegenpartei", "by": None, "by_date": "2026-11-30",
                              "agreed": False, "quote": "eine Mietzinsreduktion von CHF 2'000 an, zahlbar bis 30. November 2026"}])
OFFER_FACTS_A = [fact("oa", "rechtsgebiet", "Mietrecht / Mangel", "Seit August fällt in meiner Wohnung an der Gartenstrasse 14 die Heizung aus.")]
OFFER_FACT_B = fact("ob", "eingang_angebot", "Muster Immobilien AG: Angebot vom 2026-11-05, Mietzinsreduktion CHF 2'000, zahlbar bis 2026-11-30",
                    "bieten wir Frau Keller zur Erledigung eine Mietzinsreduktion von CHF 2'000 an")
OFFER_EDITS = decided(("deckung", "bestätigt"), ("vorgehen", "Selbst führen"))


def full_turns(entries, facts, documents, request="Vorbereitet."):
    return [[("record_steps", {"entries": copy.deepcopy(entries)}), *facts, report("claim_reader", request=request)],
            [*documents, report("document_finder")], [report("result_checker", answer="Vorbereitet.")]]


def update_turns(entries, facts, documents):
    return [[("record_steps", {"entries": copy.deepcopy(entries)}), *facts, report("claim_reader", summary="Neu: ein Dokument.")],
            [*documents, report("document_finder")]]


SITUATIONS = {
    "cost_note": dict(a=[MANDATE_A], b=MANDATE_B, entries_a=MANDATE_ENTRIES_A, entries_b=[MANDATE_ENTRY_B], facts_a=MANDATE_FACTS_A,
                      facts_b=[MANDATE_FACT_B], docs_a=MANDATE_DOCS_A, docs_b=[], edits=MANDATE_EDITS),
    "reply": dict(a=[REPLY_A], b=REPLY_B, entries_a=REPLY_ENTRIES_A, entries_b=[REPLY_ENTRY_B], facts_a=REPLY_FACTS_A, facts_b=[],
                  docs_a=REPLY_DOCS_ABSENT, docs_b=REPLY_DOCS_B, edits=()),
    "offer": dict(a=[OFFER_A], b=OFFER_B, entries_a=OFFER_ENTRIES_A, entries_b=[OFFER_ENTRY_B], facts_a=OFFER_FACTS_A, facts_b=[OFFER_FACT_B],
                  docs_a=[], docs_b=[], edits=OFFER_EDITS),
}


def both_ways(name):
    """The situation prepared from A and B together, and prepared from A then updated with B: (full, base, update)."""
    s = SITUATIONS[name]
    together, _ = prepared(s["a"] + [s["b"]], full_turns(s["entries_a"] + s["entries_b"], s["facts_a"] + s["facts_b"], s["docs_a"] + s["docs_b"]), s["edits"])
    base, base_model = prepared(s["a"], full_turns(s["entries_a"], s["facts_a"], s["docs_a"]), s["edits"])
    later, model = updated(s["a"] + [s["b"]], base, update_turns(s["entries_b"], s["facts_b"], s["docs_b"]), s["edits"])
    return together["result"], base, later, model


class EquivalenceTests(unittest.TestCase):
    def check(self, name):
        s = SITUATIONS[name]
        together, base, later, model = both_ways(name)
        files = s["a"] + [s["b"]]
        full_state, full_items = view(together, files, s["edits"])
        up_state, up_items = view(later, files, s["edits"])
        self.assertEqual(same_shape(up_state, later, up_items), same_shape(full_state, together, full_items))
        base_state, base_items = view(base["result"], s["a"], s["edits"])
        return base_items["next_action:0"], up_items["next_action:0"], up_state, later, model

    def test_a_cost_note_in_a_mandate_case_makes_the_cost_claim_the_next_action(self):
        before, after, state, result, _ = self.check("cost_note")
        self.assertEqual((before["action"], before["value"]), ("A2", "Stand bei der Kanzlei erfragen (Telefonnotiz)"))
        self.assertEqual((after["action"], after["value"], after["form"]), ("A11", "Kostenforderung prüfen und begleichen", "A11_kosten"))
        self.assertEqual(after["incoming"]["fact"], "eingang_kostenforderung")
        self.assertEqual(result["update"]["entries"], [5])
        self.assertEqual(result["update"]["facts"], ["eingang_kostenforderung"])

    def test_a_reply_with_two_of_three_documents_marks_them_answered_and_the_next_action_follows(self):
        before, after, state, result, _ = self.check("reply")
        rows = {r["what"]: r for r in state["account"]["requests"]}
        self.assertEqual(rows["Mietvertrag"]["answered"]["n"], 3)
        self.assertEqual(rows["Mängelrüge an die Verwaltung"]["answered"]["n"], 3)
        self.assertIsNone(rows["Fotos des Mangels"]["answered"])
        # before: nobody answered our request (the clock); after: the customer answered, the case waits for the photos
        self.assertEqual((before["action"], before["reason"]), ("A6", "keine Antwort seit A1 vom 05.10.2026 (41 Tage)"))
        self.assertEqual((after["action"], after["value"], after.get("reason")), ("A6", "Dossier pendent halten mit Frist", None))
        self.assertEqual(sorted(result["update"]["documents"]), ["maengelruege", "mietvertrag"])

    def test_a_letter_with_an_offer_after_our_last_step_becomes_an_open_incoming_item(self):
        before, after, state, result, _ = self.check("offer")
        self.assertEqual((before["action"], before["value"]), ("A9", "Gegenpartei mahnen"))  # silence after our letter
        self.assertNotIn("incoming", before)
        self.assertEqual((after["action"], after["value"]), ("A9", "Antwort auf das Angebot der Gegenpartei"))
        self.assertEqual(after["incoming"]["kind"], "angebot")


class WhatEachAgentReceivesTests(unittest.TestCase):
    """The update's calls, as they went out: two turns (the reader, the document finder), the second reading of what
    changed and the source check of what changed; no routing, no result checker, nothing of the earlier files' text."""

    @classmethod
    def setUpClass(cls):
        _, cls.base, cls.result, cls.model = both_ways("cost_note")

    def opening(self, n):
        return json.loads(self.model.calls[n][2][0]["content"])

    def test_the_calls_are_the_reader_the_finder_the_second_reading_and_the_source_check_of_what_changed(self):
        self.assertEqual([c[0] for c in self.model.calls], ["turn", "turn", "casepath_confirm_facts", "casepath_source_check"])
        self.assertNotIn("casepath_route", [c[0] for c in self.model.calls])
        self.assertEqual(self.result["update"]["skipped"], {"result_checker": team.RESULT_CHECKER_SKIPPED})
        self.assertEqual({u["agent"] for u in self.result["usage"]}, {"claim_reader", "document_finder", "source_checker"})

    def test_the_reader_gets_the_new_document_in_full_and_the_case_so_far_one_line_each(self):
        opening = self.opening(0)
        self.assertIn("Read only these new documents", opening["instruction"])
        self.assertIn("the last is 4", opening["instruction"])
        self.assertEqual([f["file"] for f in opening["files"]], ["fb"])  # the new file only
        self.assertEqual(list(opening["files_text"]), ["fb"])
        self.assertIn("CHF 3'200", opening["files_text"]["fb"])
        self.assertNotIn("Probegasse", json.dumps(opening["files_text"]))  # nothing of the earlier file's text
        so_far = opening["case_so_far"]
        self.assertEqual(so_far["entries"][3], "4 · 2026-10-01 · versicherer → kanzlei · kostengutsprache · Mandat und Kostengutsprache an Kanzlei Muster")
        self.assertEqual(len(so_far["entries"]), 4)
        facts = {f["id"]: f for f in so_far["facts"]}  # the deciding facts the files settle (not the handler's, not computed ones)
        self.assertNotIn("rechtsgebiet", facts)  # it chose the process; it decides no step
        self.assertNotIn("deckung", facts)
        self.assertNotIn("value", facts["eingang_kostenforderung"])  # nothing came in yet: its question only
        self.assertTrue(facts["eingang_kostenforderung"]["question"])
        self.assertLess(len(json.dumps(so_far, ensure_ascii=False)), 5000)
        self.assertEqual(so_far["open_requests"], [])
        self.assertEqual(so_far["decisions"], {"deckung": "bestätigt", "vorgehen": "Mandat an Anwaltskanzlei"})
        self.assertIn("record_steps", self.model.calls[0][3])

    def test_the_finder_checks_only_the_needs_still_missing_in_the_new_file(self):
        instruction = self.opening(1)["instruction"]
        self.assertIn("Check only these new files", instruction)
        self.assertIn("Still missing: maengelruege", instruction)
        self.assertIn("Already in the case: mietvertrag (Mietvertrag)", instruction)
        self.assertEqual([f["file"] for f in self.opening(1)["files"]], ["fb"])

    def test_the_second_reading_and_the_source_check_see_only_what_changed(self):
        confirm = json.loads(self.model.calls[2][2][0]["content"])
        self.assertEqual([f["id"] for f in confirm["facts"]], ["eingang_kostenforderung"])
        self.assertEqual(list(confirm["files_text"]), ["fb"])
        checked = json.loads(self.model.calls[3][2][0]["content"])
        self.assertEqual([i["item"] for i in checked["items"]], ["fact:eingang_kostenforderung"])

    def test_what_the_update_did_not_touch_keeps_its_value_quotes_and_verdict(self):
        before = {f["fact"]: f for f in self.base["result"]["facts"]}
        after = {f["fact"]: f for f in self.result["facts"]}
        for name in ("rechtsgebiet", "gegenpartei"):
            self.assertEqual(after[name], before[name])
        self.assertEqual(after["eingang_kostenforderung"]["verdict"], "accepted")
        self.assertEqual({d["document"]: d for d in self.result["documents"]}, {d["document"]: d for d in self.base["result"]["documents"]})
        self.assertEqual(self.result["read_files"], ["fa", "fb"])
        self.assertEqual(self.result["update"]["builds_on"], "run_base")
        self.assertEqual(self.result["summary"], self.base["result"]["summary"])  # the result checker's, from the run it builds on

    def test_an_update_refuses_what_a_new_document_does_not_state(self):
        refusals = [json.loads(m["output"]) for m in self.model.calls[1][2] if m.get("type") == "function_call_output"]
        self.assertEqual(refusals, [r for r in refusals if r.get("accepted") is not False])  # the script asked nothing refused
        work = team.CaseWork(case=CASE, files=[{"id": "fb", "name": "B", **MANDATE_B["extraction"]}], base_workflow=area.workflow(WID))
        work.updating = {"facts": set(), "documents": set(), "files": ["fb"]}
        work.facts = {"rechtsgebiet": {"fact": "rechtsgebiet", "status": "established", "value": "Mietrecht / Mangel", "citations": [], "verdict": "accepted"}}
        out = team._record_fact(work, "claim_reader", {"fact": "rechtsgebiet", "status": "unknown", "value": None, "citations": [], "part": None})
        self.assertFalse(out["accepted"])
        self.assertEqual(work.facts["rechtsgebiet"]["value"], "Mietrecht / Mangel")
        work.documents = {"mietvertrag": {"document": "mietvertrag", "status": "present", "verdict": "accepted", "files": ["fa"], "citations": []}}
        for status in ("absent", "unusable"):
            out = team._record_document(work, "document_finder", {"document": "mietvertrag", "status": status, "files": ["fb"],
                                                                  "citations": [{"file": "fb", "quote": "Zwischenhonorar: Für unsere Bemühungen"}], "note": ""})
            self.assertFalse(out["accepted"], status)
        self.assertEqual(work.documents["mietvertrag"]["status"], "present")


class LiveEventsTests(unittest.TestCase):
    """While a run works, «Der Fall» fills in from its events: each fact with its value, each recorded entry as one row
    with its quote for the viewer, the pages an agent reads."""

    def test_the_events_carry_the_values_and_rows_the_screen_fills_in(self):
        events = []
        model = Recorded(update_turns([MANDATE_ENTRY_B], [MANDATE_FACT_B], []))
        base, _ = prepared([MANDATE_A], full_turns(MANDATE_ENTRIES_A, MANDATE_FACTS_A, MANDATE_DOCS_A), MANDATE_EDITS)
        with tempfile.TemporaryDirectory() as blobs:
            core.update(job([MANDATE_A, MANDATE_B], MANDATE_EDITS), base, model, core.DirectoryBlobs(blobs), on_event=events.append)
        located = next(e for e in events if e["kind"] == "fact.located")
        self.assertEqual((located["fact"], located["value"]), ("eingang_kostenforderung", MANDATE_FACT_B[1]["value"]))
        recorded = next(e for e in events if e["kind"] == "record.recorded")
        self.assertEqual(recorded["rows"], [{"n": 5, "date": "2026-11-05", "from": "kanzlei", "to": "versicherer", "kind": "kostenforderung",
                                             "phone": False, "what": "Zwischenhonorar CHF 3'200", "file": "fb", "page": 1}])
        self.assertEqual((recorded["cite"]["file"], recorded["cite"]["page"]), ("fb", 1))  # the viewer shows where it stands
        self.assertEqual(next(e for e in events if e["kind"] == "update.started")["files"], ["fb"])
        self.assertEqual(team.shown_value(True), {"value": True})
        self.assertEqual(len(team.shown_value("x" * 400)["value"]), 160)


class IncomingSlotTests(unittest.TestCase):
    def test_a_new_item_of_what_came_in_takes_the_plain_fact_and_moves_the_earlier_one_down_with_its_verdict(self):
        work = team.CaseWork(case=CASE, files=[{"id": "fb", "name": "B", **MANDATE_B["extraction"]}], base_workflow=area.workflow(WID))
        work.updating = {"facts": set(), "documents": set(), "files": ["fb"]}
        older = {"fact": "eingang_kostenforderung", "status": "established", "value": "Kanzlei Muster: Honorarnote vom 2026-06-02 über CHF 900",
                 "citations": [{"file": "fa", "page": 3, "quote": "CHF 900"}], "verdict": "accepted"}
        work.facts = {"eingang_kostenforderung": dict(older)}
        out = team._record_fact(work, "claim_reader", {"fact": "eingang_kostenforderung", "status": "established", "part": None,
                                                       "value": "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200",
                                                       "citations": [{"file": "fb", "quote": "stellen wir Ihnen CHF 3'200 in Rechnung"}]})
        self.assertTrue(out["accepted"])
        self.assertEqual(work.facts["eingang_kostenforderung"]["value"], "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200")
        self.assertIsNone(work.facts["eingang_kostenforderung"]["verdict"])  # to be checked
        self.assertEqual(work.facts["eingang_kostenforderung_2"], {**older, "fact": "eingang_kostenforderung_2"})  # moved, verdict kept
        # an older item read in an update lands below the latest one
        out = team._record_fact(work, "claim_reader", {"fact": "eingang_kostenforderung", "status": "established", "part": None,
                                                       "value": "Bezirksgericht Beispiel: Kostenvorschuss vom 2026-08-01 über CHF 500",
                                                       "citations": [{"file": "fb", "quote": "Zahlbar innert 30 Tagen."}]})
        self.assertEqual(out["recorded_as"], "eingang_kostenforderung_2")
        self.assertEqual(work.facts["eingang_kostenforderung_3"]["value"], older["value"])
        self.assertEqual(work.updating["facts"], {"eingang_kostenforderung", "eingang_kostenforderung_2"})


if __name__ == "__main__":
    unittest.main()

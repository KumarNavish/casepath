"""The running account read per document, not per stored segment (casepath/agents/team.py, casepath/process/account.py):
pages without an entry given back to the reader once and counted; a quote found within its document's page range, or
kept and marked when it stands elsewhere in the file; the written warning, the dates and the open items as the account
holds them; record_steps as a model meets it; the segmentation that leaves no page outside a segment; the speed trial
that records the account in a second conversation.

Scripted and model-free: the entries are what a reader would have recorded with their quotes."""
import copy
import json
import tempfile
import unittest

from casepath.agents import core, team
from casepath.process import account, area, cover, letters
from casepath.process.items import build_items
from casepath.read import cut, hygiene
from casepath.read.evidence import Evidence, complete_segments
from tests.scripted import ScriptedModel, report

WID = "mietmangel-handler"
CASE = {"id": "case_m", "title": "Wasserschaden, Mandat (synthetisch) 1234.5678.9012", "intake": {}}


def entry(n, page, day, sender, to, kind, what, quote, **elements):
    row = {"n": n, "file": "f1", "page": page, "date": day, "from": sender, "to": to, "kind": kind, "phone": False, "what": what,
           "quote": quote, "asks": [], "answers": [], "terms": [], "paid": [], "next": []}
    return {**row, **elements}


def ask(what, of, quote, by=None, by_date=None, warns=False):
    return {"what": what, "of": of, "by": by, "by_date": by_date, "repeats": None, "warns": warns, "quote": quote}


# -- a long file stored as one large segment: twelve pages, six documents ------------------------------------------------

LONG = {
    1: "Von: Marco Bianchi\nGesendet: Montag, 3. Februar 2025\nBetreff: Wasserschaden, Reparatur verweigert\nDie Vermieterin zahlt nichts.",
    2: "Die Reparatur kostete viel. Ich habe sie selbst bezahlt und lege die Fotos bei.",
    3: "Protekta Rechtsschutz\nBern, 10. Februar 2025\nMandat und Kostengutsprache an die Kanzlei Recht & Partner.",
    4: "Kanzlei Recht & Partner\nZürich, 1. März 2025\nBitte reichen Sie uns die Belege der Reparaturkosten ein.",
    5: "Die Belege sind für die Klage nötig. Wir danken für Ihre Mitwirkung.",
    6: "Fortsetzung des Schreibens vom 1. März 2025: weitere Hinweise zum Verfahren.",
    7: "Kanzlei Recht & Partner\nZürich, 20. März 2025\nHonorarnote: für unsere Bemühungen stellen wir CHF 1'200 in Rechnung.",
    8: "Zahlbar innert 30 Tagen. Aufstellung der Positionen vom 20.03.2025.",
    9: "Position 1: Besprechung. Position 2: Schreiben an die Vermieterin vom 25.02.2025.",
    10: "Protekta Rechtsschutz\nBern, 2. April 2025\nWir haben die Honorarnote von CHF 1'200 heute bezahlt.",
    11: "Zahlungsbeleg vom 02.04.2025 über CHF 1'200 an Kanzlei Recht & Partner.",
    12: "Ende der Akte. Abgelegt am 03.04.2025.",
}


def long_files(segments=None):
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in LONG.items())
    extraction = {"text": text, "pages": 12, "readable": True, "note": "",
                  "segments": segments if segments is not None else [{"first_page": 1, "last_page": 12, "kind": "Akte", "title": "Akte"}]}
    return [{"id": "f1", "name": "Akte Bianchi.pdf", "kind": "pdf", "media_type": "application/pdf", "sha256": "abc", "extraction": extraction}]


FIRST = [entry(1, 1, "2025-02-03", "kunde", "versicherer", "meldung", "Meldung Wasserschaden", "Betreff: Wasserschaden, Reparatur verweigert"),
         entry(2, 3, "2025-02-10", "versicherer", "kanzlei", "mandat", "Mandat an die Kanzlei", "Bern, 10. Februar 2025")]
MORE = [entry(3, 4, "2025-03-01", "kanzlei", "kunde", "anforderung", "Kanzlei verlangt Belege", "Zürich, 1. März 2025",
              asks=[ask("Belege der Reparaturkosten", "kunde", "Die Belege sind für die Klage nötig.")]),  # on the next page of its document
        entry(4, 7, "2025-03-20", "kanzlei", "versicherer", "kostenforderung", "Honorarnote CHF 1'200", "Zürich, 20. März 2025"),
        entry(5, 10, "2025-04-02", "versicherer", "kanzlei", "zahlung", "Honorarnote bezahlt", "Bern, 2. April 2025",
              paid=[{"amount": "CHF 1'200", "payer": "versicherer", "date": "2025-04-02", "quote": "Zahlungsbeleg vom 02.04.2025"}])]


def run_long(turns_after, trials=(), files=None):
    """The long file through the scripted team: the reader first records two entries and reports."""
    cite = [{"file": "f1", "quote": "Die Vermieterin zahlt nichts."}]
    model = ScriptedModel([
        [("list_files", {})],
        [("record_steps", {"entries": copy.deepcopy(FIRST)}),
         ("record_fact", {"part": None, "fact": "rechtsgebiet", "status": "established", "value": "Mietrecht / Mangel", "citations": cite})],
        [report("claim_reader", request="Reparaturkosten.")],
        *turns_after,
        [report("document_finder")],
        *[[report("result_checker", answer="Vorbereitet.")]] * 3,
    ])
    job = {"format": core.JOB, "case": {**CASE, "workflow_id": WID}, "files": files or long_files(),
           "workflows": [area.workflow(WID)], "knowledge": [], "edits": [], "options": {"read_scans": False, **({"speed_trials": list(trials)} if trials else {})}}
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    return outcome["result"], model


class CoverageTests(unittest.TestCase):
    def test_pages_without_an_entry_go_back_to_the_reader_once_and_what_it_added_is_counted(self):
        result, model = run_long([[("record_steps", {"entries": copy.deepcopy(MORE)})], [report("claim_reader", request="Reparaturkosten.")]])
        given = [json.loads(m["output"]) for m in model.inputs[3] if m.get("type") == "function_call_output" and "have no entry" in m["output"]]
        self.assertEqual(len(given), 1)  # the first report came back, with the pages and what to do there
        self.assertIn("pages 4–12 have no entry", given[0]["reason"])
        self.assertIn("one entry per letter, e-mail, note, invoice and decision", given[0]["reason"])
        record = result["record"]
        self.assertEqual([e["n"] for e in record["entries"]], [1, 2, 3, 4, 5])
        self.assertEqual([e["page"] for e in record["entries"]], [1, 3, 4, 7, 10])  # each document its own first page, not the segment's
        cov = record["coverage"]
        self.assertEqual((cov["pages"], cov["covered"], cov["gaps"]), (12, 12, []))
        self.assertEqual((cov["given_back_pages"], cov["covered_after"], cov["added"]), (9, 9, 3))
        self.assertEqual([g["from"] for g in cov["given_back"]], [4])
        self.assertEqual(record["entries"][2]["asks"][0]["citations"][0]["page"], 5)  # the quote on the next page of its document
        self.assertNotIn("elsewhere", record["entries"][2]["asks"][0])
        self.assertIn("invoice", model.instructions and team.RECORD)
        self.assertIn("a segment\n(or a range «nicht gegliedert») may hold several documents", team.RECORD)

    def test_given_back_once_only_and_the_verlauf_says_which_pages_have_no_entry(self):
        result, model = run_long([[report("claim_reader", request="Reparaturkosten.")]])  # the reader adds nothing
        cov = result["record"]["coverage"]
        self.assertEqual((cov["covered"], cov["added"], cov["covered_after"]), (3, 0, 0))
        self.assertEqual(cov["gaps"], [{"file": "f1", "from": 4, "to": 12, "pages": 9}])
        files = long_files()
        state = core.evaluate(area.workflow(WID), [], [], result, "case_m", files=files)
        items = build_items(state, result, files)
        gap = [i for i in items if i["kind"] == "record_gap"]
        self.assertEqual([(i["value"], i["label"]["de"]) for i in gap], [("S. 4–12 ohne Eintrag", "S. 4–12 ohne Eintrag (Akte Bianchi.pdf)")])

    def test_no_give_back_without_a_turn_left_to_record_and_a_short_run_of_pages_is_no_gap(self):
        pages = {"f1": [(n, LONG[n]) for n in LONG]}
        self.assertEqual(account.gaps(FIRST + MORE, pages), [])
        self.assertEqual(account.gaps([dict(FIRST[0])], {"f1": [(n, LONG[n]) for n in range(1, 5)]}), [])  # three pages: not more than GAP_PAGES
        undated = {"f1": [(n, "Fortsetzung ohne Datum.") for n in range(1, 13)]}
        self.assertEqual(account.gaps(FIRST, undated), [])  # nothing dated stands there
        files = long_files()
        work = team.CaseWork(case=CASE, files=[{"id": "f1", "name": "Akte Bianchi.pdf", **files[0]["extraction"]}], base_workflow=area.workflow(WID))
        self.assertIsNone(work.coverage_round(can_record=False))

    def test_the_turns_for_a_dossier_count_its_pages_when_its_segments_are_few(self):
        files = long_files()
        many = "\n\n".join(f"[page {n}]\nSeite {n} vom 01.02.2025" for n in range(1, 96))
        work = team.CaseWork(case=CASE, files=[{"id": "f1", "name": "A", **{**files[0]["extraction"], "text": many, "pages": 95}}],
                             base_workflow=area.workflow(WID))
        self.assertEqual(team.record_turns(work), 1)  # 95 pages ≈ 31 documents: one turn more, not none for one segment


class QuoteRangeTests(unittest.TestCase):
    def test_a_quote_is_found_within_its_documents_pages_kept_and_marked_elsewhere_dropped_when_nowhere(self):
        files = long_files()
        work = team.CaseWork(case=CASE, files=[{"id": "f1", "name": "Akte Bianchi.pdf", **files[0]["extraction"]}], base_workflow=area.workflow(WID))
        raw = entry(3, 4, "2025-03-01", "kanzlei", "kunde", "anforderung", "Kanzlei verlangt Belege", "Zürich, 1. März 2025",
                    asks=[ask("Belege", "kunde", "Die Belege sind für die Klage nötig."),            # page 5: its own document
                          ask("Zahlung", "kunde", "Zahlbar innert 30 Tagen."),                       # page 8: another document of the file
                          ask("Unterschrift", "kunde", "Bitte unterschreiben Sie die Vollmacht.")])  # nowhere
        nxt = entry(4, 7, "2025-03-20", "kanzlei", "versicherer", "kostenforderung", "Honorarnote", "Zürich, 20. März 2025")
        out = team._record_steps(work, "claim_reader", {"entries": [raw, nxt]})
        self.assertEqual((out["accepted"], out["dropped_quotes"], out["kept_elsewhere"]), (2, 1, 1))
        kept = next(e for e in work.record["entries"] if e["n"] == 3)["asks"]
        self.assertEqual([(a["what"], a["citations"][0]["page"], a.get("elsewhere")) for a in kept],
                         [("Belege", 5, None), ("Zahlung", 8, {"page": 8})])
        self.assertEqual(work.record["issues"], [{"n": 3, "kind": "asks", "reason": "elsewhere", "kept": True, "page": 8},
                                                 {"n": 3, "kind": "asks", "reason": "not_found", "kept": False}])
        self.assertEqual(work.page_range("f1", 4, [1, 3, 4, 7, 10]), (4, 7))  # to the next entry's first page, within the segment

    def test_an_entry_whose_own_quote_is_outside_its_document_is_dropped_with_its_reason(self):
        files = long_files()
        work = team.CaseWork(case=CASE, files=[{"id": "f1", "name": "A", **files[0]["extraction"]}], base_workflow=area.workflow(WID))
        out = team._record_steps(work, "claim_reader", {"entries": [entry(1, 1, "2025-02-03", "kunde", "versicherer", "meldung", "x", "Bern, 2. April 2025"),
                                                                     entry(2, 3, "2025-02-10", "versicherer", "kanzlei", "mandat", "y", "Bern, 10. Februar 2025")]})
        self.assertEqual((out["accepted"], out["dropped_entries"]), (1, 1))
        self.assertEqual(work.record["issues"], [{"n": 1, "kind": "entry", "reason": "elsewhere", "kept": False, "page": 10}])


# -- a mandate: the firm warns the customer, reports that she does not cooperate; the other side proposes a settlement -----

MANDATE = {
    1: "Von: Marco Bianchi\nGesendet: Montag, 3. Februar 2025\nBetreff: Wasserschaden, Reparatur verweigert",
    2: "Protekta Rechtsschutz\nBern, 10. Februar 2025\nMandat und Kostengutsprache an die Kanzlei Recht & Partner.",
    3: ("Kanzlei Recht & Partner\nZürich, 1. März 2025\nSehr geehrter Herr Bianchi\nBitte reichen Sie uns die Belege der Reparaturkosten "
        "und die Mängelrüge innert 14 Tagen ein. Andernfalls müssen wir das Mandat niederlegen."),
    4: ("Kanzlei Recht & Partner\nZürich, 2. April 2025\nAn Protekta\nDer Klient hat trotz Mahnung die Belege nicht eingereicht und "
        "verhält sich unkooperativ; wir legen das Mandat nieder."),
    5: ("Muster Immobilien AG\nBern, 5. April 2025\nAn Protekta\nWir schlagen zur Erledigung CHF 2'000 per Saldo vor. Bitte teilen "
        "Sie uns bis 30. April 2025 mit, ob Ihr Versicherter einverstanden ist."),
}
REPORT_QUOTE = "Der Klient hat trotz Mahnung die Belege nicht eingereicht"
MANDATE_ENTRIES = [
    entry(1, 1, "2025-02-03", "kunde", "versicherer", "meldung", "Meldung Wasserschaden", "Betreff: Wasserschaden, Reparatur verweigert"),
    entry(2, 2, "2025-02-10", "versicherer", "kanzlei", "mandat", "Mandat an die Kanzlei", "Bern, 10. Februar 2025"),
    entry(3, 3, "2025-03-01", "kanzlei", "kunde", "anforderung", "Kanzlei verlangt Belege mit Frist", "Zürich, 1. März 2025",
          asks=[ask("Belege der Reparaturkosten", "kunde", "Bitte reichen Sie uns die Belege der Reparaturkosten", by="innert 14 Tagen", warns=True),
                ask("Mängelrüge an die Vermieterin", "kunde", "und die Mängelrüge innert 14 Tagen ein", by="innert 14 Tagen", warns=True)]),
    entry(4, 4, "2025-04-02", "kanzlei", "versicherer", "bericht", "Kanzlei meldet fehlende Mitwirkung, legt Mandat nieder", "Zürich, 2. April 2025"),
    entry(5, 5, "2025-04-05", "gegenpartei", "versicherer", "angebot", "Vergleichsvorschlag CHF 2'000", "Bern, 5. April 2025",
          terms=[{"what": "Vergleich per Saldo", "amount": "CHF 2'000", "payer": "gegenpartei", "by": "bis 30. April 2025", "by_date": None,
                  "agreed": False, "quote": "Wir schlagen zur Erledigung CHF 2'000 per Saldo vor."}]),
]


def mandate_view(entries=MANDATE_ENTRIES, decided=(), as_of="2025-04-15"):
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in MANDATE.items())
    extraction = {"text": text, "pages": 5, "readable": True, "note": "", "cut_of": {"as_of": as_of},
                  "segments": [{"first_page": n, "last_page": n, "kind": "Schreiben"} for n in MANDATE]}
    files = [{"id": "f1", "name": "Mandat Bianchi.pdf", "kind": "pdf", "extraction": extraction}]
    evidence = Evidence([{"id": "f1", "name": "Mandat Bianchi.pdf", "kind": "pdf", **extraction}])
    kinds = area.workflow(WID)["record"]["kinds"]
    located = [account.check(raw, lambda q, p=raw["page"]: evidence.locate("f1", q, p, p), kinds)[0] for raw in entries]
    fact = lambda fid, value, quote=None: {"fact": fid, "status": "established", "verdict": "accepted", "value": value,
                                           "citations": [{"file": "f1", "page": 4, "quote": quote}] if quote else []}
    result = {"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("deckung", "bestätigt"), fact("vorgehen", "Mandat an Anwaltskanzlei"),
                        fact("eingang_mitwirkung", "Kanzlei Recht & Partner: Mandat niedergelegt am 2025-04-02, Belege nicht eingereicht", REPORT_QUOTE)],
              "documents": [], "brief": {"request": "Reparaturkosten.", "parties": [{"role": "Versicherter", "name": "Marco Bianchi"}], "timeline": []},
              "record": {"entries": [e for e in located if e], "dropped": 0}}
    edits = [{"id": f"e{i}", "op": "set_fact", "args": {"fact": k, "value": v}, "status": "active"} for i, (k, v) in enumerate(decided)]
    state = {**core.evaluate(area.workflow(WID), [], edits, result, "case_m", files=files), "case": {"id": "case_m"}}
    items = build_items(state, result, files)
    return state, items, {i["item_id"]: i for i in items}, files


def render(items, form, files):
    return letters.render(form, area.workflow(WID)["forms"], letters.context(CASE, items, [], {"due": "2025-05-06"}, files))


class WarningTests(unittest.TestCase):
    def test_a_warning_by_the_firm_is_shown_as_such_to_check_and_the_insurers_own_demand_is_prepared(self):
        state, items, by_id, files = mandate_view()
        check = by_id["check:androhung"]
        self.assertEqual(check["value"], "andere")
        # Slice C (C10g): the first ask's quote stops before «innert 14 Tagen»: its date is to check, not stated
        self.assertEqual(check["lines"], ["Kanzlei, Schreiben vom 01.03.2025: Belege der Reparaturkosten (Frist laut Akte, Datum prüfen) · "
                                          "Aufforderung durch die Kanzlei, nicht durch Protekta · ob das genügt: prüfen",
                                          "Kanzlei, Schreiben vom 01.03.2025: Mängelrüge an die Vermieterin bis 15.03.2025 · Aufforderung durch "
                                          "die Kanzlei, nicht durch Protekta · ob das genügt: prüfen"])
        self.assertEqual(check["evidence"][0]["page"], 3)  # its source
        self.assertNotIn("nicht in der Akte", check["text"])
        nxt = by_id["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"]), ("A6", "A6_androhung"))  # the insurer has sent none: its own demand first
        self.assertEqual(nxt["because"], "schriftliche Aufforderung mit Androhung durch Protekta fehlt (nur durch die Kanzlei)")

    def test_the_insurers_own_warning_in_the_account_counts_and_none_at_all_says_not_in_the_file(self):
        own = MANDATE_ENTRIES + [entry(6, 5, "2025-03-25", "versicherer", "kunde", "mahnung", "Letzte Aufforderung", "Bern, 5. April 2025",
                                       asks=[ask("Belege der Reparaturkosten", "kunde", "Wir schlagen zur Erledigung", by_date="2025-04-22", warns=True)])]
        _, _, by_id, _ = mandate_view(own)
        self.assertEqual(by_id["check:androhung"]["value"], "vorhanden")
        self.assertEqual(by_id["check:androhung"]["own_date"], "2025-03-25")
        self.assertNotEqual(by_id["next_action:0"].get("form"), "A6_androhung")
        none = [dict(e, asks=[{**a, "warns": False} for a in e["asks"]]) for e in MANDATE_ENTRIES]
        _, _, by_id, _ = mandate_view(none)
        self.assertEqual((by_id["check:androhung"]["value"], by_id["check:androhung"]["text"]),
                         ("fehlt", "nicht in der Akte: zuerst die Aufforderung mit Frist und Androhung"))
        self.assertEqual(by_id["next_action:0"]["because"], "schriftliche Aufforderung mit Androhung fehlt")


class LetterWordingTests(unittest.TestCase):
    def test_the_demand_names_what_was_asked_in_neutral_words_with_its_first_date_never_the_firms_words(self):
        _, items, by_id, files = mandate_view()
        text, none = render(items, "A6_androhung", files)
        self.assertIsNone(none)
        self.assertIn("Die von Ihnen beauftragte Kanzlei hat uns mitgeteilt (Schreiben vom 02.04.2025), dass für die Bearbeitung Ihres Falles "
                      "folgende Unterlagen oder Angaben fehlen:\n– Belege der Reparaturkosten (erstmals verlangt am 01.03.2025)\n"
                      "– Mängelrüge an die Vermieterin (erstmals verlangt am 01.03.2025)", text)
        for words in (REPORT_QUOTE, "unkooperativ", "trotz Mahnung"):
            self.assertNotIn(words, text)
        self.assertIn(REPORT_QUOTE, by_id["next_action:0"]["evidence"][0]["quote"])  # the firm's words stay one click away on the screen

    def test_the_ending_after_the_firms_report_lists_the_same_and_no_letter_to_the_customer_carries_the_report(self):
        _, items, _, files = mandate_view(decided=[("leistungen_einstellen", "ja")])
        text, _ = render(items, "A12_mitwirkung_kanzlei", files)
        self.assertIn("folgende Unterlagen oder Angaben trotz Aufforderung nicht eingegangen sind:\n– Belege der Reparaturkosten "
                      "(erstmals verlangt am 01.03.2025)", text)
        ctx = letters.context(CASE, items, [], {"due": "2025-05-06"}, files)
        forms = area.workflow(WID)["forms"]
        for kind, form in forms.items():  # no form to the customer is filled with the report's words
            if isinstance(form, dict) and "Kundschaft" in str(form.get("to") or ""):
                drafted, _ = letters.render(kind, forms, ctx)
                self.assertNotIn("unkooperativ", drafted or "", kind)
                self.assertNotIn(REPORT_QUOTE, drafted or "", kind)
        self.assertNotIn("unkooperativ", ctx["im_fall"])


class DateTests(unittest.TestCase):
    def test_open_dates_of_the_account_reach_fristen_with_what_who_set_it_and_for_whom_a_passed_one_too(self):
        _, items, by_id, _ = mandate_view()
        rows = sorted((i["key"], i["value"], i["what"], i["by"], i["for"], i["source"], i["stated_as"]) for i in items
                      if i["kind"] == "deadline" and i.get("account"))
        # a request's id is stable: the entry that first asks it (3) and the ask's place in it (0, 1), not its place in time order
        # Slice C (C10g): a date is kept only where its own quote writes it (or the period it is counted from): the first ask's
        # quote stops before «innert 14 Tagen», the offer's before «bis 30. April 2025»: both «Frist laut Akte, Datum prüfen»
        self.assertEqual(rows, [
            ("konto-r3.0", "prüfen", "Belege der Reparaturkosten", "Kanzlei", "Kundschaft", "Schreiben vom 01.03.2025", "possible"),
            ("konto-r3.1", "2025-03-15", "Mängelrüge an die Vermieterin", "Kanzlei", "Kundschaft", "Schreiben vom 01.03.2025", "computed"),
            ("konto-t5", "prüfen", "Antwort auf das Angebot: Gegenpartei zahlt CHF 2'000 (Vergleich per Saldo)", "Gegenpartei", "Protekta",
             "Schreiben vom 05.04.2025", "possible")])
        self.assertEqual(by_id["deadline:konto-r3.1"]["rule"], "innert 14 Tagen ab Schreiben vom 01.03.2025, nach Kalendertagen berechnet")
        self.assertEqual(by_id["deadline:konto-t5"]["party"], "versicherer")  # the insurer's to meet: it can lead the card
        self.assertIsNone(letters.set_date_line(by_id["deadline:konto-t5"]))  # stays on the screen, not in a letter

    def test_a_date_the_set_date_reading_already_gives_is_not_added_twice_and_an_answered_one_is_gone(self):
        # Slice C (C10g): the offer's date counts only with its quote writing it, so this offer quotes the sentence with the date
        offer = dict(MANDATE_ENTRIES[4], terms=[{**MANDATE_ENTRIES[4]["terms"][0],
                                                 "quote": "Wir schlagen zur Erledigung CHF 2'000 per Saldo vor. Bitte teilen Sie uns bis 30. April 2025 mit"}])
        acc = account.build([account.check(e, lambda q: {"file": "f1", "page": e["page"], "quote": q}, area.workflow(WID)["record"]["kinds"])[0]
                             for e in MANDATE_ENTRIES[:4] + [offer]], area.workflow(WID))
        items = [{"item_id": "deadline:frist", "kind": "deadline", "key": "frist", "value": "2025-04-30", "what": "Antwort auf den Vergleichsvorschlag",
                  "set_by_others": True, "origin": "workflow"}]
        from casepath.process.items import account_dates
        account_dates(items, acc)
        self.assertEqual(sorted(i["key"] for i in items), ["frist", "konto-r3.0", "konto-r3.1"])  # the stable request ids (r<n>.<i>)
        answered = MANDATE_ENTRIES + [entry(6, 5, "2025-03-10", "kunde", "kanzlei", "unterlagen", "Belege", "Bern, 5. April 2025",
                                            answers=[{"what": "Belege der Reparaturkosten", "answers": 3, "quote": "Wir schlagen zur Erledigung"}])]
        acc = account.build([account.check(e, lambda q: {"file": "f1", "page": e["page"], "quote": q}, area.workflow(WID)["record"]["kinds"])[0]
                             for e in answered], area.workflow(WID))
        self.assertEqual([d["key"] for d in account.open_dates(acc)], ["konto-r3.1", "konto-t5"])  # the stable request ids (r<n>.<i>)


class StandTests(unittest.TestCase):
    def test_one_open_item_per_line_at_most_three_per_party_then_more_which_the_verlauf_filters(self):
        kinds = area.workflow(WID)["record"]["kinds"]
        things = ["Mietvertrag", "Mängelrüge", "Fotos", "Rechnungen", "Korrespondenz"]
        raws = [entry(1, 1, "2025-02-01", "versicherer", "kunde", "anforderung", "Anforderung", "q" * 8,
                      asks=[ask(t, "kunde", "q" * 8, by_date="2025-02-20") for t in things]),
                entry(2, 2, "2025-03-01", "versicherer", "kunde", "mahnung", "Mahnung", "q" * 8,
                      asks=[{**ask("Mietvertrag", "kunde", "q" * 8, warns=True), "repeats": 1}])]
        acc = account.build([account.check(r, lambda q: {"file": "f1", "page": 1, "quote": q}, kinds)[0] for r in raws], area.workflow(WID))
        line = next(x for x in account.stand(acc, account.parse_date("2025-04-01")) if x["id"] == "offen_kunde")
        self.assertEqual([r["text"] for r in line["rows"]], ["Mietvertrag · seit 01.02.2025 · 2× verlangt · mit Androhung",
                                                             "Mängelrüge · seit 01.02.2025 · 1× verlangt", "Fotos · seit 01.02.2025 · 1× verlangt"])
        self.assertEqual((line["more"], line["party"]), (2, "kunde"))
        self.assertNotIn("(", line["text"])
        self.assertEqual({tuple(r["open_of"]) for r in account.rows(acc)}, {("kunde",)})


class RecordStepsTests(unittest.TestCase):
    def setUp(self):
        files = long_files()
        self.work = team.CaseWork(case=CASE, files=[{"id": "f1", "name": "Akte Bianchi.pdf", **files[0]["extraction"]}], base_workflow=area.workflow(WID))

    def test_what_a_model_writes_often_is_accepted_cut_or_mapped_and_said(self):
        raw = entry("3", 4, "01.03.2025", "Kanzlei Recht & Partner", None, "Schreiben der Kanzlei (Aufforderung)", "x" * 400, "Zürich, 1. März 2025",
                    asks=[ask("Belege", "VN", "Bitte reichen Sie uns die Belege der Reparaturkosten ein.",
                              by="innert 14 Tagen ab Erhalt dieses Schreibens, spätestens aber vor der Schlichtungsverhandlung, die noch angesetzt wird")],
                    terms=[{"what": f"Punkt {i}", "amount": None, "payer": "Vermieterin", "by": None, "by_date": None, "agreed": False,
                            "quote": "Die Belege sind für die Klage nötig."} for i in range(5)])
        raw.pop("next")  # a field left out
        raw["extra"] = "dropped"
        args, changes = team.fit_steps(self.work, {"entries": [raw]})
        self.assertEqual([c["field"] for c in changes], ["entries[0].what"])
        out = team._dispatch(self.work, "claim_reader", "record_steps", {**args, "_fitted": ["entries[0].what: text cut (400 → 300)"]})
        self.assertEqual(out["accepted"], 1)
        self.assertEqual(out["cut"], ["entries[0].what: text cut (400 → 300)"])
        e = self.work.record["entries"][0]
        self.assertEqual((e["n"], e["date"], e["from"], e["to"], e["kind"]), (3, "2025-03-01", "kanzlei", "kanzlei", "anforderung"))
        self.assertEqual((e["asks"][0]["of"], e["asks"][0]["by"], e["asks"][0]["by_computed"]), ("kunde", "2025-03-15", True))
        self.assertEqual(len(e["terms"]), 5)
        self.assertEqual({t["payer"] for t in e["terms"]}, {"gegenpartei"})

    def test_an_invalid_entry_is_refused_alone_with_its_field_and_what_is_allowed(self):
        good = entry(1, 1, "2025-02-03", "kunde", "versicherer", "meldung", "Meldung", "Betreff: Wasserschaden, Reparatur verweigert")
        bad = entry(2, 3, "2025-02-10", "versicherer", "kanzlei", "mandat", "Mandat", "Bern")  # a quote under eight characters
        args, _ = team.fit_steps(self.work, {"entries": [good, bad]})
        out = team._record_steps(self.work, "claim_reader", args)
        self.assertEqual(out["accepted"], 1)
        self.assertEqual(out["not_accepted"], [{"entry": 1, "n": 2, "error": "entries[1].quote: 4 characters; allowed: 8 to 600"}])
        with self.assertRaises(ValueError) as caught:
            team.fit_steps(self.work, {"entry": []})
        self.assertIn("$.entries: a list of entries is required", str(caught.exception))

    def test_a_number_used_by_another_document_gets_the_next_free_one_and_a_second_reading_replaces(self):
        team._record_steps(self.work, "claim_reader", team.fit_steps(self.work, {"entries": copy.deepcopy(FIRST)})[0])
        later = copy.deepcopy(MORE[:1])
        later[0]["n"] = 1  # a second batch that numbers from one again
        out = team._record_steps(self.work, "claim_reader", team.fit_steps(self.work, {"entries": later})[0])
        self.assertEqual(out["renumbered"], {"1": 3})
        self.assertEqual(sorted(e["n"] for e in self.work.record["entries"]), [1, 2, 3])
        again = copy.deepcopy(FIRST[:1])
        again[0]["what"] = "Meldung, gelesen"
        team._record_steps(self.work, "claim_reader", team.fit_steps(self.work, {"entries": again})[0])
        self.assertEqual([e["what"] for e in self.work.record["entries"] if e["n"] == 1], ["Meldung, gelesen"])

    def test_the_schema_messages_name_the_field_and_what_is_allowed(self):
        from casepath.agents.schema import validate_result, choice, obj
        with self.assertRaises(ValueError) as caught:
            validate_result({"kind": "brief"}, obj(kind=choice(["meldung", "andere"])))
        self.assertEqual(str(caught.exception), '$.kind: "brief" is not allowed; allowed: meldung, andere')
        self.assertEqual(account.kind_of("Erinnerung", area.workflow(WID)["record"]["kinds"]), "mahnung")
        self.assertEqual(account.kind_of("Honorarnote", area.workflow(WID)["record"]["kinds"]), "kostenforderung")
        self.assertEqual([account.party_of(x) for x in ("RA", "Vermieterin", "VN", "Bezirksgericht", "Protekta", "?")],
                         ["kanzlei", "gegenpartei", "kunde", "behoerde", "versicherer", "andere"])


class SegmentTests(unittest.TestCase):
    def test_every_page_belongs_to_a_segment_or_an_explicit_range_the_reader_is_shown(self):
        stored = [{"first_page": 55, "last_page": 60, "kind": "Brief", "title": "Brief"}, {"first_page": 61, "last_page": 95, "kind": "Urteil", "title": "Urteil"}]
        rows = complete_segments(stored, list(range(1, 96)))
        self.assertEqual([(s["first_page"], s["last_page"], s["kind"]) for s in rows],
                         [(1, 54, "nicht gegliedert"), (55, 60, "Brief"), (61, 95, "Urteil")])
        text = "\n\n".join(f"[page {n}]\nSeite {n}" for n in range(1, 96))
        evidence = Evidence([{"id": "f1", "name": "A", "kind": "pdf", "text": text, "pages": 95, "segments": stored}])
        listed = evidence.catalogue()[0]["documents"]
        self.assertEqual(listed[0]["title"], "Seiten 1–54 nicht gegliedert")
        self.assertIn("kann mehrere Dokumente enthalten", listed[0]["summary"])
        self.assertEqual(hygiene.documents(evidence.files)[:2], [("f1", 55, 60), ("f1", 61, 95)])  # a range is no document

    def test_a_cut_keeps_a_segment_whose_first_page_was_cut_away(self):
        extraction = {"text": "\n\n".join(f"[page {n}]\ntext {n}" for n in range(1, 11)), "pages": 10,
                      "segments": [{"first_page": 1, "last_page": 6}, {"first_page": 7, "last_page": 10}]}
        out = cut.cut_extraction(extraction, [4, 5, 6, 7, 8])
        self.assertEqual([(s["first_page"], s["last_page"], s.get("cut_before", False)) for s in out["segments"]], [(4, 6, True), (7, 8, False)])

    def test_a_window_the_segmentation_lost_stays_as_a_range(self):
        from casepath.read import reading
        from casepath.agents.azure_model import ModelError

        class Model:
            def respond_json(self, *, name, instructions, input, schema, effort="low"):
                pages = json.loads(input[0]["content"])["pages"]
                if pages[0]["page"] == 1:
                    raise ModelError("http_500", "busy")
                first = pages[0]["page"]
                return type("R", (), {"value": {"documents": [{"first_page": first, "last_page": pages[-1]["page"], "continues": False, "kind": "Brief",
                                                               "date": "", "sender": "", "recipient": "", "title": "Brief", "summary": "",
                                                               "quote": pages[0]["text"][:20]}]}})()
        text = "\n\n".join(f"[page {n}]\n" + ("Seite %d " % n) * 3000 for n in range(1, 7))
        rows = reading.segment(Model(), {"id": "f1", "name": "A", "kind": "pdf", "extraction": {"text": text, "pages": 6}})
        self.assertEqual(rows[0]["kind"], "nicht gegliedert")
        self.assertEqual({p for s in rows for p in range(s["first_page"], s["last_page"] + 1)}, set(range(1, 7)))


class RecordApartTrialTests(unittest.TestCase):
    def run_with(self, trials):
        """The same reading with the account recorded in the reader's conversation (off) or in a second one (on)."""
        cite = [{"file": "f1", "quote": "Die Vermieterin zahlt nichts."}]
        fact = ("record_fact", {"part": None, "fact": "rechtsgebiet", "status": "established", "value": "Mietrecht / Mangel", "citations": cite})
        steps = [("record_steps", {"entries": copy.deepcopy(FIRST + MORE)})]
        reader = [[("list_files", {})], [*steps, fact], [report("claim_reader", request="Reparaturkosten.")]] if not trials else \
                 [[("list_files", {})], [fact], [report("claim_reader", request="Reparaturkosten.")],
                  [*steps], [report("claim_reader", summary="Verlauf erfasst.")]]
        model = ScriptedModel([*reader, [report("document_finder")], *[[report("result_checker", answer="Vorbereitet.")]] * 3])
        result = team.CaseTeam(model, speed_trials=trials).run(case={**CASE, "workflow_id": WID},
                                                              files=[{"id": "f1", "name": "Akte Bianchi.pdf", **long_files()[0]["extraction"]}],
                                                              workflow=area.workflow(WID))
        return result, model

    def test_the_result_with_the_second_conversation_equals_the_result_without(self):
        off, _ = self.run_with(())
        on, model = self.run_with({"record_apart"})
        keep = lambda r: {k: r[k] for k in ("facts", "documents", "evaluation", "brief")} | {"record": {k: v for k, v in r["record"].items()}}
        self.assertEqual(keep(on), keep(off))
        self.assertEqual(on["record"]["coverage"]["covered"], 12)
        # both conversations open the same way (instructions, tools, opening): the second is served from the cache
        self.assertEqual(model.inputs[0][0], model.inputs[3][0])
        self.assertEqual(model.tools[0], model.tools[3])
        self.assertEqual((model.inputs[0][1]["content"], model.inputs[3][1]["content"]), (team.FACTS_ONLY, team.RECORD_ONLY))
        self.assertIn("record_apart", team.load_settings({"CASEPATH_SPEED_TRIALS": "record_apart"}).speed_trials if hasattr(team, "load_settings") else
                      __import__("casepath.config", fromlist=["x"]).load_settings({"CASEPATH_SPEED_TRIALS": "record_apart"}).speed_trials)


if __name__ == "__main__":
    unittest.main()

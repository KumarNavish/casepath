"""The mandate package, settlement and payout, the check of a firm's cost claim, and the letters a customer sends in his
own name (mandate.py, settlement.py, customer_letters.py). Scripted and model-free: the facts are what a reader would have
recorded with their quotes, the files carry their text page by page."""
import copy
import re
import unittest

from casepath.agents import core
from casepath.process import area, customer_letters, letters, mandate, settlement
from casepath.process.items import build_items
from casepath.process.workflows import CatalogueError
from tests.test_cover import CASE, TENANT, edits, fact

FORMS = area.workflow("mietmangel-handler")["forms"]
IBAN = "CH93 0076 2011 6238 5295 7"  # the standard example of a valid Swiss IBAN
TEXT = ("[page 1]\nSchadenmeldung\nLea Beispiel, Mieterin, Bahnhofstrasse 1, 3000 Bern\nIm Bad meiner Mietwohnung wächst Schimmel.\n"
        "Vermieterin: Immo Verwaltung AG\n\n"
        "[page 2]\nMietvertrag zwischen Immo Verwaltung AG und Lea Beispiel, Mietbeginn 1. April 2024.\n\n"
        "[page 3]\nE-Mail vom 10.03.2026: Ich melde Ihnen den Schimmel im Bad. Lea Beispiel\n\n"
        "[page 4]\nFoto Schimmel Bad, 12.03.2026\n")
SEGMENTS = [{"first_page": 1, "last_page": 1, "date": "12.11.2026", "kind": "Schadenmeldung", "sender": "Lea Beispiel"},
            {"first_page": 2, "last_page": 2, "date": "01.04.2024", "kind": "Mietvertrag", "sender": "Immo Verwaltung AG"},
            {"first_page": 3, "last_page": 3, "date": "10.03.2026", "kind": "E-Mail", "sender": "Lea Beispiel"},
            {"first_page": 4, "last_page": 4, "date": "12.03.2026", "kind": "Foto", "sender": "Lea Beispiel"}]


def cite(page, quote):
    return [{"file": "f1", "page": page, "quote": quote}]


def build(facts, history=None, set_by_hand=None, wid="mietmangel-handler", text=TEXT, segments=SEGMENTS, events=(), timeline=(), parties=None):
    """A case as the screen builds it: (items by id, items, files). ``facts``: (id, value, page, quote)."""
    rows = [{"fact": f[0], "status": "established", "verdict": "accepted", "value": f[1], "citations": cite(f[2], f[3]) if len(f) > 3 and f[3] else []}
            for f in facts] + ([fact("bisherige_handlungen", history)] if history else [])
    files = [{"id": "f1", "name": "Akte.pdf", "extraction": {"cut_of": {"as_of": "2026-11-14"}, "text": text, "segments": segments}}]
    result = {"facts": rows, "documents": [{"document": "mietvertrag", "status": "present", "verdict": "accepted", "files": ["f1"], "citations": cite(2, "Mietvertrag")}],
              "brief": {"request": "Die Mieterin verlangt die Beseitigung des Schimmels im Bad und eine Herabsetzung des Mietzinses.",
                        "parties": parties if parties is not None else [{"role": "Mieterin (VN)", "name": "Lea Beispiel"}, {"role": "Vermieterin", "name": "Immo Verwaltung AG"}],
                        "timeline": list(timeline)},
              # a date others set, as the reader records it with what, who and where (the deadline question of every area)
              "deadlines": [{"fact": "frist", "date": str(f[1])[:10], "set": dict(zip(("what", "by", "source"), str(f[1]).split(" · ")[1:]))}
                            for f in facts if f[0] == "frist"]}
    state = {**core.evaluate(area.workflow(wid), [], edits(**(set_by_hand or {})), result, "c", files=files), "case": {"id": "c", "created_at": "2026-11-14T08:00:00"}}
    items = build_items(state, result, files, list(events))
    return {i["item_id"]: i for i in items}, items, files


def context(items, files):
    return letters.context(CASE, items, [], {"due": "2026-12-01"}, files)


TENANT_ROWS = [("rechtsgebiet", "Mietrecht / Mangel", 1, "Im Bad meiner Mietwohnung wächst Schimmel."), ("maengelruege_schriftlich", True, 3, "Ich melde Ihnen den Schimmel im Bad."),
               ("will_schadenersatz", False), ("streit_mietzins", False), ("will_reduktion", True, 1, "eine Herabsetzung des Mietzinses"),
               ("will_beseitigung", True, 1, "die Beseitigung des Schimmels"), ("mangel_besteht", True, 4, "Foto Schimmel Bad, 12.03.2026"),
               ("mangel_seit", "2026-03-10", 3, "E-Mail vom 10.03.2026"), ("gegenpartei", "Immo Verwaltung AG", 1, "Vermieterin: Immo Verwaltung AG"),
               ("frist", "2026-12-10 · Schlichtungsverhandlung · Schlichtungsbehörde Bern · Vorladung", 4, "Vorladung zur Schlichtungsverhandlung am 10.12.2026")]
TIMELINE = [{"date": "2026-03-10", "event": "Mangel per E-Mail gemeldet", "citations": cite(3, "Ich melde Ihnen den Schimmel im Bad.")},
            {"date": "2024-04-01", "event": "Mietbeginn", "citations": cite(2, "Mietbeginn 1. April 2024")},
            {"date": "2026-03-12", "event": "Schimmel fotografiert", "citations": cite(4, "Foto Schimmel Bad")}]
MANDATE = TENANT_ROWS + [("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")]


class MandatePackageTests(unittest.TestCase):
    def setUp(self):
        self.listed, self.items, self.files = build(MANDATE, history="A1 2026-09-01; A5 2026-10-01", timeline=TIMELINE)

    def test_the_mandate_stage_prepares_four_letters_each_on_its_own(self):
        self.assertEqual(self.listed["next_action:0"]["action"], "A10")
        self.assertEqual(letters.accompanying("A10", FORMS, self.items), ["A10_kostengutsprache", "A10_zusammenfassung", "A10_kunde"])
        ctx = context(self.items, self.files)
        request = letters.render("A10", FORMS, ctx)[0]
        self.assertIn("Sehr geehrte Damen und Herren", request)  # to the firm, not the customer's greeting
        self.assertIn("Kundschaft: Lea Beispiel (Mieterin)\nGegenpartei: Immo Verwaltung AG", request)  # each role once, the other side by its role
        self.assertIn("Auftrag: Abklärung der Sach- und Rechtslage und aussergerichtliche Geltendmachung der Ansprüche", request)
        self.assertFalse(letters.has_gap(request))
        info = letters.render("A10_kunde", FORMS, ctx)[0]  # the customer's information keeps its required parts
        self.assertEqual(cover_missing(info), [])

    def test_the_guarantee_states_scope_extension_and_reporting_and_never_an_amount_nobody_entered(self):
        text = letters.render("A10_kostengutsprache", FORMS, context(self.items, self.files))[0]
        self.assertIn("Kostengutsprache nach den bekannten Modalitäten wie folgt: Abklärung der Sach- und Rechtslage sowie aussergerichtliche Bemühungen.", text)
        self.assertIn("vorgängige Kontaktaufnahme für eine Erweiterung der Kostengutsprache", text)
        self.assertIn("regelmässig über den Stand der Sache informiert und stellen Sie uns Kopien der wichtigsten Unterlagen zu", text)
        self.assertNotIn("CHF", text)
        self.assertNotRegex(text.split("\n", 1)[1], r"\d")  # no number at all besides the reference
        _, items, files = build(MANDATE, history="A1 2026-09-01; A5 2026-10-01",
                                set_by_hand={"kostengutsprache_umfang": "mit Schlichtungsverfahren", "kostengutsprache_betrag": "5000"})
        text = letters.render("A10_kostengutsprache", FORMS, context(items, files))[0]
        self.assertIn("aussergerichtliche Bemühungen sowie das Schlichtungsverfahren.", text)
        self.assertIn("Die Kostengutsprache ist auf CHF 5'000.– begrenzt.", text)
        self.assertIn("Vertretung im Schlichtungsverfahren", letters.render("A10", FORMS, context(items, files))[0])

    def test_the_summary_for_the_firm_traces_every_line_to_its_source_and_leaves_no_section_empty(self):
        rows = mandate.summary(self.items, self.files)
        self.assertEqual([s for s, _ in rows], list(mandate.SECTIONS))
        pages = {int(p) for p in re.findall(r"\[page (\d+)\]", TEXT)}
        for section, lines in rows:
            self.assertTrue(lines, section)
            for line in lines:
                self.assertFalse(line.get("gap"), f"{section}: {line}")  # this case states something for every section
                self.assertTrue(line["source"], f"{section}: {line}")
                for page in re.findall(r"S\. (\d+)", line["source"]):
                    self.assertIn(int(page), pages)
        by = dict(rows)
        self.assertEqual([l["text"][:10] for l in by["Sachverhalt"]], ["01.04.2024", "10.03.2026", "12.03.2026"])  # in time order
        self.assertIn({"text": "Mieterin (VN): Lea Beispiel", "source": "S. 1"}, by["Parteien"])
        self.assertTrue(any("Art. 259d OR" in l["source"] for l in by["Rechtliche Punkte"]))
        self.assertTrue(any(l["text"].startswith("10.12.2026: Schlichtungsverhandlung") for l in by["Fristen und Termine"]))
        self.assertIn("Beseitigung des Mangels", " ".join(l["text"] for l in by["Ziel der Kundschaft"]))
        text = letters.render("A10_zusammenfassung", FORMS, context(self.items, self.files))[0]
        self.assertNotIn("Fundstelle nicht ermittelt", text)
        self.assertNotIn("Sehr geehrte", text)  # a summary, not a letter
        self.assertLessEqual(len(text.splitlines()), mandate.MAX_LINES + 2)
        self.assertLessEqual(len(text), 4500)  # one page

    def test_a_section_the_file_is_silent_on_is_marked_and_nothing_is_invented(self):
        _, items, files = build([("rechtsgebiet", "Mietrecht / Mangel"), ("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")],
                                history="A5 2026-10-01", text="", segments=[], parties=[])
        rows = dict(mandate.summary(items, files))
        self.assertEqual(rows["Sachverhalt"], [{"text": "nicht in der Akte festgestellt", "source": None, "gap": True}])
        self.assertEqual(rows["Parteien"][0]["text"], "nicht in der Akte festgestellt")

    def test_the_file_note_records_all_four_and_which_were_copied(self):
        ctx = context(self.items, self.files)
        package = [("A10", FORMS["A10"]["title"])] + [(k, FORMS[k]["title"]) for k in letters.accompanying("A10", FORMS, self.items)]
        events = [{"kind": "letter.copied", "form": "A10"}, {"kind": "letter.copied", "also": "A10_kostengutsprache"}]
        note = letters.file_note(CASE, self.items, events, {"due": "2026-12-14"}, self.files, package=package)
        self.assertIn("Paket (4 Schreiben, je einzeln): Mandatsanfrage an die Kanzlei – kopiert; Kostengutsprache (Umfang: Abklärung der Sach- und "
                      "Rechtslage sowie aussergerichtliche Bemühungen; nach den bekannten Modalitäten, ohne Betrag) – kopiert; "
                      "Zusammenfassung für die Kanzlei; Information der Kundschaft zum Mandat.", note)
        self.assertTrue(ctx["zusammenfassung"])


def cover_missing(text):
    from casepath.process import cover
    return cover.missing_required(text, cover.required_for("A10_kunde"))


SETTLED = TENANT_ROWS + [("deckung", "bestätigt"), ("weiteres_vorgehen", True), ("vorgehen", "Selbst führen"), ("einigung", True),
                         ("eingang_angebot", "Immo Verwaltung AG: Schreiben vom 2026-11-05, Vergleich CHF 800.00 per Saldo, zahlbar bis 2026-12-15", 5,
                          "zahlen wir Ihnen CHF 800.00 per Saldo bis 15.12.2026")]
ANSWERED = [("eingang_erledigt_bis", "2026-11-06")]


class SettlementTests(unittest.TestCase):
    def step(self, facts=(), events=(), text=TEXT, hand=None):
        listed, items, files = build(SETTLED + list(facts), history="A1 2026-09-01; A5 2026-10-01; A8 2026-10-10", text=text, events=events,
                                     set_by_hand={"eingang_erledigt_bis": "2026-11-06", **(hand or {})})
        return listed, items, files

    def test_the_agreement_is_recorded_from_the_file_with_its_source_and_the_handler_confirms_it(self):
        listed, items, _ = self.step()
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"], nxt["value"]), ("A11", "A11_einigung", "Einigung festhalten"))
        line = listed["stage_line:vg-einigung"]
        self.assertEqual(line["value"], "Einigung laut Akte: CHF 800.00 · zahlt: Immo Verwaltung AG · bis 15.12.2026")
        self.assertEqual(line["evidence"][0]["page"], 5)
        self.assertEqual(FORMS["A11_einigung"]["needs"], ["vergleich_bestaetigt"])
        listed, _, _ = self.step(hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual(listed["next_action:0"]["form"], "A11_iban")

    def test_bank_details_are_asked_once_and_not_when_the_file_holds_the_customers_iban(self):
        listed, items, files = self.step(hand={"vergleich_bestaetigt": "ja"})
        text = letters.render("A11_iban", FORMS, context(items, files))[0]
        self.assertIn("Immo Verwaltung AG bezahlt CHF 800.00 bis 15.12.2026.", text)
        self.assertIn("IBAN: ____", text)
        asked = [{"kind": "letter.copied", "form": "A11_iban"}]
        listed, items, files = self.step(events=asked, hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual(listed["next_action:0"]["form"], "A11_auszahlung")  # asked once: never proposed again
        self.assertIn("[bitte ergänzen: IBAN der Kundschaft]", letters.render("A11_auszahlung", FORMS, context(items, files))[0])
        with_iban = TEXT + f"\n[page 6]\nMein Konto: IBAN {IBAN}, lautend auf Lea Beispiel\n"
        listed, items, files = self.step(text=with_iban, hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual(listed["next_action:0"]["form"], "A11_auszahlung")
        self.assertEqual(listed["stage_line:vg-iban"]["value"], f"IBAN laut Akte: {IBAN}")
        self.assertEqual(listed["stage_line:vg-iban"]["evidence"][0]["page"], 6)
        text = letters.render("A11_auszahlung", FORMS, context(items, files))[0]
        self.assertIn(f"IBAN: {IBAN}", text)
        self.assertIn("Kontoinhaberin / Kontoinhaber: Lea Beispiel", text)
        self.assertIn("bis 15.12.2026", text)

    def test_an_iban_of_someone_else_is_shown_but_does_not_stand_for_the_customers(self):
        other = TEXT + f"\n[page 6]\nHonorarnote, zahlbar auf IBAN {IBAN} der Kanzlei Muster\n"
        listed, _, _ = self.step(text=other, hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual(listed["next_action:0"]["form"], "A11_iban")
        self.assertIn("Kontoinhaber nicht erkennbar", listed["stage_line:vg-iban"]["value"])
        self.assertIsNone(settlement.customer_iban([{"extraction": {"text": "[page 1]\nIBAN CH93 0076 2011 6238 5295 8"}}], "Lea Beispiel"))  # checksum

    def test_payout_receipt_and_closing_follow_and_a_step_done_is_not_proposed_again(self):
        done = [{"kind": "letter.copied", "form": "A11_iban"}, {"kind": "letter.copied", "form": "A11_auszahlung"}]
        listed, items, files = self.step(events=done, hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual(listed["next_action:0"]["form"], "A11_eingang")
        self.assertIn("Bitte bestätigen Sie uns kurz, dass der Betrag auf Ihrem Konto eingegangen ist.", letters.render("A11_eingang", FORMS, context(items, files))[0])
        paid = [("eingang_zahlung", "Immo Verwaltung AG: Zahlung CHF 800.00 am 2026-12-10", 7, "CHF 800.00 überwiesen")]
        listed, items, files = self.step(facts=paid, events=done[:1], hand={"vergleich_bestaetigt": "ja", "eingang_erledigt_bis": "2026-11-06"})
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"]), ("A11", "A11_eingang"))  # the payment came in: confirm it, no payout letter
        self.assertIn("die Zahlung über CHF 800.00 am 10.12.2026 eingegangen ist", letters.render("A11_eingang", FORMS, context(items, files))[0])
        listed, _, _ = self.step(events=done + [{"kind": "letter.copied", "form": "A11_eingang"}], hand={"vergleich_bestaetigt": "ja"})
        self.assertEqual((listed["next_action:0"]["action"], listed["next_action:0"]["form"]), ("A12", "A12_erledigt"))

    def test_under_a_mandate_the_firm_handles_the_payout(self):
        self.assertFalse(settlement.applies("abwicklung", {"vorgehen": "Mandat an Anwaltskanzlei"}))
        self.assertTrue(settlement.applies("abwicklung", {"vorgehen": "Selbst führen"}))

    def test_the_running_account_plugs_in_at_one_place_and_wins(self):
        terms = settlement.agreement({"eingang_angebot": "X: CHF 1.00"}, {}, account={"amount": "CHF 900.00", "payer": "Y", "due": "2027-01-31"})
        self.assertEqual((terms["amount"], terms["payer"], terms["fact"]), ("CHF 900.00", "Y", "account"))


CLAIM = ("eingang_kostenforderung", "Kanzlei Muster: Honorarnote vom 2026-11-02 über CHF 4'250.00 für Leistungen vom 01.09.2026 bis 31.10.2026, inkl. Klageentwurf",
         9, "Honorarnote CHF 4'250.00, Leistungen 01.09.2026 bis 31.10.2026")
FIRM_TEXT = (TEXT + "\n[page 6]\nKostengutsprache: Wir erteilen Ihnen Kostengutsprache nach den bekannten Modalitäten wie folgt: Abklärung der Sach- und "
             "Rechtslage sowie aussergerichtliche Bemühungen.\n\n[page 7]\nZwischenbericht der Kanzlei Muster\n\n[page 8]\nBericht zum Stand der Sache\n")
FIRM_SEGMENTS = SEGMENTS + [{"first_page": 6, "last_page": 6, "date": "01.10.2026", "kind": "Brief", "sender": "Protekta"},
                            {"first_page": 7, "last_page": 7, "date": "15.10.2026", "kind": "Zwischenbericht", "sender": "Kanzlei Muster"},
                            {"first_page": 8, "last_page": 8, "date": "28.10.2026", "kind": "Bericht", "sender": "Kanzlei Muster"}]


class FeeNoteTests(unittest.TestCase):
    def test_with_the_guarantee_in_the_file_each_line_has_its_source_and_the_scope_is_a_question(self):
        listed, items, files = build(MANDATE + [CLAIM], history="A1 2026-09-01; A5 2026-10-01; A10 2026-10-01", text=FIRM_TEXT, segments=FIRM_SEGMENTS)
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"]), ("A11", "A11_kosten"))
        lines = [i for i in items if i["kind"] == "stage_line"]
        self.assertEqual([i["key"] for i in lines], ["kg-gutsprache", "kg-erweiterung", "kg-berichte", "kg-forderung", "kg-frage"])
        by = {i["key"]: i for i in lines}
        self.assertEqual(by["kg-gutsprache"]["value"], "Kostengutsprache erteilt am 01.10.2026 · Umfang: Abklärung der Sach- und Rechtslage sowie aussergerichtliche Bemühungen")
        self.assertEqual(by["kg-gutsprache"]["evidence"][0]["page"], 6)
        self.assertEqual(by["kg-erweiterung"]["value"], "Erweiterung der Kostengutsprache: nicht in der Akte")
        self.assertEqual((by["kg-berichte"]["value"], by["kg-berichte"]["evidence"][0]["page"]), ("Berichte der Kanzlei: 2, zuletzt vom 28.10.2026", 8))
        self.assertEqual(by["kg-forderung"]["value"], "Forderung vom 02.11.2026: CHF 4'250.00 · Zeitraum 01.09.2026 bis 31.10.2026")
        self.assertEqual(by["kg-forderung"]["evidence"][0]["page"], 9)
        self.assertTrue(by["kg-frage"]["value"].startswith("? Gerichtliche Schritte abgerechnet? Kostengutsprache umfasst nur aussergerichtliche Bemühungen"))
        self.assertIn("«Klage»", by["kg-frage"]["value"])  # a question that names what it noticed, never a conclusion
        self.assertNotIn("stage_line:kosten", listed)  # the stage's own line it repeats goes
        self.assertEqual(letters.accompanying("A11_kosten", FORMS, items), ["A11_rueckfrage", "A11_teilablehnung"])
        ctx = context(items, files)
        query = letters.render("A11_rueckfrage", FORMS, ctx)[0]
        self.assertIn("Vielen Dank für Ihre Kostenforderung vom 02.11.2026 über CHF 4'250.00.", query)
        self.assertIn("Unsere Kostengutsprache vom 01.10.2026 umfasst Abklärung der Sach- und Rechtslage sowie aussergerichtliche Bemühungen.", query)
        self.assertFalse(letters.has_gap(query))
        partial = letters.render("A11_teilablehnung", FORMS, ctx)[0]
        self.assertIn("Nicht übernehmen können wir: [bitte ergänzen: welche Positionen nicht und weshalb", partial)  # the reason is the handler's

    def test_without_a_guarantee_in_the_file_the_lines_say_so(self):
        listed, items, files = build(MANDATE + [CLAIM], history="A1 2026-09-01; A5 2026-10-01")
        by = {i["key"]: i for i in items if i["kind"] == "stage_line"}
        self.assertEqual(by["kg-gutsprache"]["value"], "Kostengutsprache: nicht in der Akte")
        self.assertEqual(by["kg-berichte"]["value"], "Berichte der Kanzlei: nicht in der Akte")
        self.assertIn("Umfang ist nicht in der Akte", by["kg-frage"]["value"])
        query = letters.render("A11_rueckfrage", FORMS, context(items, files))[0]
        self.assertIn("[bitte ergänzen: Datum der Kostengutsprache]", query)

    def test_a_court_claim_gets_no_firm_check(self):
        court = ("eingang_kostenforderung", "Bezirksgericht Bern: Kostenvorschuss CHF 1'500 vom 2026-11-02", 9, "Kostenvorschuss")
        _, items, _ = build(MANDATE + [court], history="A10 2026-10-01")
        self.assertFalse([i for i in items if i["kind"] == "stage_line" and i["key"].startswith("kg-")])
        self.assertEqual(letters.accompanying("A11_kosten", FORMS, items), [])


TEMPLATES = {  # area: (facts, template id, recipient's words, its deadline line, a gap the file leaves)
    "mietmangel-handler": ([("rechtsgebiet", "Mietrecht / Mangel"), ("mangel_besteht", True), ("mangel_seit", "2026-10-01")], "maengelruege",
                           "an die Vermieterschaft", "bis 14.12.2026 zu beseitigen", "[einsetzen: Beschreibung des Mangels"),
    "vertrag-darlehen": ([("rechtsgebiet", "Vertragsrecht / Darlehen"), ("termin_vereinbart", False)], "rueckforderung",
                         "an die Schuldnerin oder den Schuldner", "innert sechs Wochen ab dieser Aufforderung, das heisst bis 26.12.2026", "[einsetzen: Betrag und Tag der Übergabe"),
    "arbeit-kuendigung": ([("rechtsgebiet", "Arbeitsrecht / Kündigung"), ("arbeitsende", "2026-11-30"), ("fristlos", False), ("grund_genannt", False)], "einsprache",
                          "an die Arbeitgeberin", "bis zum Ende der Kündigungsfrist vorliegen, spätestens am 30.11.2026", "[einsetzen: Tag, an dem Sie die Kündigung erhalten haben]"),
    "miete-kuendigung": ([("rechtsgebiet", "Mietrecht / Kündigung"), ("grund_genannt", False), ("kuendigung_erhalten", "2026-11-02")], "begruendung",
                         "an die Vermieterschaft", "spätestens am 02.12.2026", "[einsetzen: Adresse der Mietwohnung]"),
    "betreibung-schuldner": ([("rechtsgebiet", "Schuldbetreibungs- und Konkursrecht / Zahlungsbefehl gegen die Kundschaft"), ("rechtsvorschlag_erhoben", False),
                              ("zahlungsbefehl_zugestellt", "2026-11-10")], "rechtsvorschlag", "Rechtsvorschlag beim Betreibungsamt", "spätestens am 20.11.2026",
                             "[einsetzen: Betreibungsnummer laut Zahlungsbefehl]"),
    "vertrag-kauf": ([("rechtsgebiet", "Vertragsrecht / Kauf mit Mangel"), ("angezeigt", False), ("mangel_entdeckt", "2026-11-09")], "maengelanzeige",
                     "an die Verkäuferschaft", "sofort nach der Entdeckung des Mangels erfolgen, also ohne Aufschub", "[einsetzen: gekaufte Sache und Kaufdatum]"),
    "miete-kaution": ([("rechtsgebiet", "Mietrecht / Kaution und Rückgabe"), ("mietende", "2026-09-30"), ("forderung_vermieter", False)], "freigabe",
                      "an die Vermieterschaft", "bis 14.12.2026 zu bestätigen", "[einsetzen: Betrag der Kaution und Bank]"),
}


class CustomerLetterTests(unittest.TestCase):
    def letter(self, wid, facts, key):
        listed, items, files = build(facts, wid=wid, text="", segments=[])
        return listed.get(f"customer_letter:{key}"), items, files

    def test_each_template_renders_with_its_deadline_and_with_gaps_where_the_file_is_silent(self):
        for wid, (facts, key, to, deadline, gap) in TEMPLATES.items():
            item, _, _ = self.letter(wid, facts, key)
            self.assertIsNotNone(item, wid)
            text = item["text"]
            self.assertIn(to, item["label"]["de"], wid)
            self.assertIn("kein Schreiben von Protekta", text.splitlines()[0], wid)  # the customer's own letter
            self.assertIn(deadline, text, wid)
            self.assertIn(gap, text, wid)
            self.assertNotIn("[bitte ergänzen", text, wid)  # gaps for the customer, not for the handler
            self.assertNotIn("Unsere Referenz", text, wid)
            self.assertRegex(text, r"\(Art\. \d+[a-z]*", wid)
        self.assertEqual(sum(len(w.get("customer_letters") or []) for w in area.shipped()), 11)  # + the objection to a penalty order, two conciliation requests

    def test_with_time_short_the_first_request_carries_the_template_and_says_so_in_one_sentence(self):
        facts = TEMPLATES["arbeit-kuendigung"][0] + [("kuendigung_erhalten", "2026-10-28"), ("gegenpartei", "Beispiel AG")]
        item, items, files = self.letter("arbeit-kuendigung", facts, "einsprache")
        self.assertEqual((item["offered_with"], item["due"]), (["A5", "A1"], "2026-11-30"))
        self.assertIn("Beispiel AG\n[einsetzen: Adresse]", item["text"])
        self.assertIn("Am 28.10.2026 habe ich Ihre Kündigung", item["text"])
        listed = {i["item_id"]: i for i in items}
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        wf = area.workflow("arbeit-kuendigung")
        a1 = letters.render("A1", wf["forms"], letters.context(CASE, items, [], {"due": "2026-11-25"}, files))[0]
        self.assertEqual(a1.count("legen wir Ihnen eine Vorlage bei"), 1)
        self.assertIn("Für Ihr Schreiben an die Arbeitgeberin legen wir Ihnen eine Vorlage bei, die Sie prüfen, ergänzen und in Ihrem eigenen Namen senden; "
                      "es muss der Arbeitgeberin spätestens am 30.11.2026 zugehen.", a1)
        later = TEMPLATES["arbeit-kuendigung"][0][:1] + [("arbeitsende", "2027-03-31"), ("fristlos", False)]
        item, _, _ = self.letter("arbeit-kuendigung", later, "einsprache")
        self.assertEqual(item["offered_with"], ["A5"])  # time is not short: only with the assessment
        self.assertIsNone(self.letter("arbeit-kuendigung", later[:1] + [("arbeitsende", "2027-03-31"), ("fristlos", True)], "einsprache")[0])

    def test_the_assessment_refers_to_the_template(self):
        facts, key, *_ = TEMPLATES["mietmangel-handler"]
        _, items, files = self.letter("mietmangel-handler", facts, key)
        ctx = letters.context(CASE, items, [], {"due": "2026-12-01"}, files)
        a5 = letters.render("A5", FORMS, ctx)[0]
        self.assertIn("Für Ihr Schreiben an die Vermieterschaft legen wir Ihnen eine Vorlage bei", a5)
        self.assertNotIn("Vorlage bei", letters.render("A1", FORMS, ctx)[0] or "")  # no deadline of the customer: not with the first request

    def test_the_validator_refuses_a_statement_without_a_passage_and_an_instruction_the_law_does_not_support(self):
        bb = area.backbone()
        base = next(m for m in [area.load(area.AREAS / "mietmangel-handler.json")])
        area.validate_module(base, bb)

        def refused(change):
            module = copy.deepcopy(base)
            change(module["customer_letters"][0])
            with self.assertRaises(CatalogueError):
                area.validate_module(module, bb)
        refused(lambda l: l["parts"].append({"text": "Sie müssen den Mangel innert 30 Tagen beheben.", "plain": True}))  # law said as plain text
        refused(lambda l: l["parts"].append({"text": "Der Mietzins darf herabgesetzt werden."}))  # a statement without its article
        refused(lambda l: l["parts"].append({"text": "Ich hinterlege den Mietzins.", "law": ["law#999"]}))  # an article without a passage
        refused(lambda l: l["advice"].append({"text": "Die Mängelrüge muss eingeschrieben erfolgen", "law": ["law#257g"], "requires": ["eingeschrieben"]}))
        refused(lambda l: l["send"].update({"text": "Sie müssen eingeschrieben senden"}))  # prudence never says «muss»
        refused(lambda l: l.update({"when": True}))  # a template needs its condition on facts
        refused(lambda l: l["parts"].append({"text": "Protekta vertritt mich.", "law": ["law#257g"]}))  # never the insurer's letter
        refused(lambda l: l["parts"].append({"text": "Seit {erfunden}.", "plain": True}))  # a placeholder that is neither a fact nor a gap


if __name__ == "__main__":
    unittest.main()

"""The running account of a case (casepath/process/account.py): one entry per document, read by the claim reader with
located quotes, and by code the requests ledger, the agreement as it stands, who owes what, the actions taken, silence,
the «Stand» lines and the Verlauf; and the hygiene step that keeps repeated text from the model (casepath/read/hygiene.py).

Scripted and model-free: the entries are what a reader would have recorded with their quotes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from casepath.agents import core, team
from casepath.process import account, area, letters
from casepath.process.items import build_items
from casepath.read.evidence import Evidence
from casepath.read import hygiene
from tests.scripted import ScriptedModel, report

CASES = json.loads((Path(__file__).parent / "fixtures" / "account" / "cases.json").read_text())


def files_of(case, cut=True):
    extraction = {"text": case["text"], "pages": case["pages"], "readable": True, "note": "",
                  **({"segments": case["segments"]} if case["segments"] else {}), **({"cut_of": {"as_of": case["as_of"]}} if cut else {})}
    return [{"id": "f1", "name": case["name"], "kind": "pdf", "media_type": "application/pdf", "sha256": "abc", "extraction": extraction}]


def run(case, *, entries=None, calls=1):
    """The case through the scripted team: the reader records the entries (in ``calls`` calls) and the routing fact."""
    entries = case["entries"] if entries is None else entries
    cite = lambda quote: [{"file": "f1", "quote": quote}]
    size = -(-len(entries) // calls)
    batches = [entries[i:i + size] for i in range(0, len(entries), size)]
    model = ScriptedModel([
        [("list_files", {})],
        [("record_steps", {"entries": b}) for b in batches]
        + [("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
        [report("claim_reader", request="Heizung fällt aus.", parties=[{"role": "Versicherte", "name": "Sandra Keller"}])],
        [report("document_finder")],
        *[[report("result_checker", answer="Vorbereitet.")]] * 3,
    ])
    case_row = {"id": "case_a", "title": case["title"], "intake": {}, "workflow_id": case["workflow"]}
    job = {"format": core.JOB, "case": case_row, "files": files_of(case, cut=False),
           "workflows": [area.workflow(case["workflow"])], "knowledge": [], "edits": [], "options": {"read_scans": False}}
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    return outcome["result"], model


def decisions(case):
    return [{"id": f"e{i}", "op": "set_fact", "args": {"fact": f, "value": v}, "status": "active"} for i, (f, v) in enumerate(case["decisions"])]


def view(case, result):
    files = files_of(case)
    state = core.evaluate(area.workflow(case["workflow"]), [], decisions(case), result, "case_a", files=files)
    items = build_items(state, result, files)
    return state, items, {i["item_id"]: i for i in items}


def stored(case):
    """A result as a run stores it: the entries located as the reader's tool locates them."""
    evidence = Evidence([{"id": "f1", "name": case["name"], "kind": "pdf", **files_of(case)[0]["extraction"]}])
    kinds = area.workflow(case["workflow"])["record"]["kinds"]
    entries = []
    for raw in case["entries"]:
        page = raw["page"]
        entry, _ = account.check(raw, lambda q: evidence.locate("f1", q, page if case["segments"] else None, page if case["segments"] else None), kinds)
        if entry:
            entries.append(entry)
    return {"facts": [], "documents": [], "brief": {"request": "", "parties": [], "timeline": []}, "record": {"entries": entries, "dropped": 0}}


class SelfConductedCaseTests(unittest.TestCase):
    """A case Protekta conducts itself: eight documents, three phone notes, a request asked twice, an offer, a counter-offer
    by phone, an acceptance, bank details asked once and delivered, a payout promised and not yet confirmed."""

    @classmethod
    def setUpClass(cls):
        cls.case = CASES["selbst"]
        cls.result, cls.model = run(cls.case, calls=2)
        cls.state, cls.items, cls.by_id = view(cls.case, cls.result)
        cls.acc = cls.state["account"]

    def test_a_every_document_has_its_entry_and_an_element_whose_quote_is_not_in_its_document_is_dropped_or_marked(self):
        record = self.result["record"]
        self.assertEqual([e["n"] for e in record["entries"]], list(range(1, 9)))
        # a payment the note never states is dropped; a quote from another document of the file is kept and marked
        self.assertEqual((record["dropped"], record["elsewhere"]), (self.case["dropped"] - 1, 1))
        self.assertEqual(record["issues"], [{"n": 6, "kind": "paid", "reason": "not_found", "kept": False},
                                            {"n": 8, "kind": "answers", "reason": "elsewhere", "kept": True, "page": 2}])
        self.assertEqual(record["entries"][5]["paid"], [])
        self.assertEqual([(a["what"], a.get("elsewhere")) for a in record["entries"][7]["answers"]],
                         [("IBAN für die Zahlung", None), ("Mietvertrag", {"page": 2})])
        self.assertEqual(account._where(record["entries"][7]["answers"][1]), " · andere Stelle, S. 2")  # as the Verlauf marks it
        self.assertEqual(record["coverage"]["covered"], record["coverage"]["pages"])  # every page lies in an entry's document
        self.assertEqual(sum(e["phone"] for e in record["entries"]), 3)
        for e in record["entries"]:  # each element is located in its own document (its page)
            for key in account.ELEMENTS:
                for element in e[key]:
                    if element.get("elsewhere"):
                        continue
                    self.assertEqual({c["page"] for c in element["citations"][:1]}, {e["page"]})
        self.assertIn("record_steps", self.model.tools[0])

    def test_b_the_ledger_holds_each_request_with_who_asked_whom_how_often_and_the_entry_that_answered_it(self):
        rows = {r["what"]: r for r in self.acc["requests"]}
        # Slice C (C10a): the combined ask «Mietvertrag und Mängelrüge an die Verwaltung» is one row per item, with the same
        # quote and the ids r2.0 and r2.1; each was asked twice, each is answered by entry 4. The reminder's own quote writes
        # no date (C10g), the date it carries is the one the customer gave in the same call (21.02.2025)
        self.assertEqual((rows["Mietvertrag"]["id"], rows["Mängelrüge an die Verwaltung"]["id"]), ("r2.0", "r2.1"))
        for what in ("Mietvertrag", "Mängelrüge an die Verwaltung"):
            docs = rows[what]
            self.assertEqual((docs["by"], docs["of"], docs["first"], docs["last"], docs["times"], docs["due"]),
                             ("versicherer", "kunde", "2025-01-14", "2025-02-11", 2, "2025-02-21"))
            self.assertEqual((docs["answered"]["n"], docs["answered"]["how"], docs["answered"]["confirmed"]), (4, "entry", True))
        iban = rows["IBAN"]
        self.assertEqual((iban["times"], iban["answered"]["n"], iban["answered"]["confirmed"]), (1, 8, True))
        question = rows["Kann ich den Mietzins reduzieren?"]
        self.assertEqual((question["by"], question["of"], question["answered"]), ("kunde", "versicherer", None))

    def test_c_the_agreement_as_it_stands_is_the_phone_notes_amount_and_the_letters_is_history(self):
        a = self.acc["agreement"]
        self.assertEqual((a["amount"], a["payer"], a["by"], a["n"], a["accepts"]), ("CHF 3'000", "gegenpartei", "2025-04-30", 7, 6))
        self.assertEqual([(t["n"], t["amount"], t["agreed"]) for t in self.acc["superseded"]], [(5, "CHF 2'000.–", False), (6, "CHF 3'000", False)])
        self.assertIsNone(self.acc["payment"])
        self.assertTrue(self.state["facts"]["einigung"])
        self.assertFalse(self.state["facts"]["zahlung_erhalten"])

    def test_d_who_owes_what_now(self):
        owes = {p: [(o["kind"], o.get("what")) for o in rows] for p, rows in self.acc["owes"].items() if rows}
        self.assertEqual(owes, {"gegenpartei": [("payment", "Entschädigung")], "versicherer": [("request", "Kann ich den Mietzins reduzieren?")]})

    def test_e_the_actions_taken_come_from_the_entries_and_replace_the_read_action_facts(self):
        self.assertEqual(self.state["facts"]["bisherige_handlungen"],
                         "A1 2025-01-14; A1 2025-02-11; A2 2025-02-11; A2 2025-03-25; A9 2025-03-25; A2 2025-03-27; A9 2025-03-27")
        self.assertEqual((self.state["facts"]["handlung_a1"], self.state["facts"]["handlung_a2"]), ("2025-02-11", "2025-03-27"))
        self.assertEqual(self.state["facts"]["anforderungen"], "2+")
        self.assertTrue(self.state["facts"]["kunde_geantwortet"])

    def test_f_the_next_action_chases_the_payout_not_a_pending_letter_of_the_first_stage(self):
        nxt = self.by_id["next_action:0"]
        self.assertEqual(self.state["evaluation"]["current"]["step"], "abwicklung")
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"]), ("A11", "Auszahlung bei der Gegenpartei nachfragen", "A11_nachfragen"))
        self.assertEqual(nxt["reason"], "vereinbart (Telefon vom 27.03.2025): Gegenpartei zahlt CHF 3'000 (Entschädigung) bis 30.04.2025; keine Zahlung in den Akten")

    def test_f2_the_chase_has_its_letter_and_the_settlement_sequence_reads_the_agreement_from_the_account(self):
        from casepath.process import settlement
        self.assertEqual(self.by_id["stage_line:vg-einigung"]["value"], "Einigung laut Verlauf: CHF 3'000 · zahlt: die Gegenpartei · bis 30.04.2025")
        self.assertEqual(self.by_id["stage_line:vg-iban"]["value"], "IBAN laut Akte: CH93 0076 2011 6238 5295 7")
        self.assertEqual([i["action"] for i in self.items if i["kind"] == "next_action"], ["A11"])  # one chase, not the sequence's step beside it
        wf = area.workflow(self.case["workflow"])
        text, none = letters.render("A11_nachfragen", wf["forms"], letters.context({"title": self.case["title"]}, self.items, [], {"due": "2025-05-20"}, files_of(self.case)))
        self.assertIsNone(none)
        self.assertIn("Sehr geehrte Damen und Herren", text)
        self.assertIn("Vereinbarung vom 27.03.2025: Zahlung von CHF 3'000 bis 30.04.2025.", text)
        self.assertIn("den Betrag von CHF 3'000 bis 20.05.2025 zu überweisen", text)
        self.assertIn("Kontoinhaberin / Kontoinhaber: Sandra Keller\nIBAN: CH93 0076 2011 6238 5295 7", text)
        self.assertFalse(letters.has_gap(text))
        paid = {**self.acc, "payment": {"amount": "CHF 3'000", "date": "2025-05-02"}}
        terms = settlement.agreement({}, None, settlement.from_account(paid, {"gegenpartei": "Muster Immobilien AG"}))
        self.assertEqual((terms["payer"], terms["paid"], terms["fact"]), ("Muster Immobilien AG", True, "account"))
        self.assertIsNone(settlement.from_account(None))  # no account: the sequence reads the file as before

    def test_g_the_stand_lines_say_what_is_agreed_open_at_whom_and_the_last_contact_each_with_its_sources(self):
        lines = [(i["key"], i["label"]["de"], i["value"]) for i in self.items if i["kind"] == "stand"]
        self.assertEqual(lines, [
            ("vereinbart", "Vereinbart", "CHF 3'000 von der Gegenpartei bis 30.04.2025 · überfällig"),
            ("offen_versicherer", "Offen bei uns", "Kann ich den Mietzins reduzieren? · Frage der Kundschaft vom 10.01.2025"),
            ("kontakt", "Letzter Kontakt", "28.03.2025 · Unterlagen zugestellt von der Kundschaft")])
        for i in self.items:
            if i["kind"] == "stand":
                self.assertTrue(i["evidence"] and all(e["quote"] for e in i["evidence"]))
        note = letters.file_note({"title": self.case["title"]}, self.items, [], None, files_of(self.case))
        self.assertIn("Vereinbart: Gegenpartei zahlt CHF 3'000 (Entschädigung) bis 30.04.2025 · überfällig · Telefon vom 27.03.2025; "
                      "ersetzt CHF 2'000.– (Schreiben vom 20.03.2025).", note)
        self.assertIn("Nächster Schritt: Auszahlung bei der Gegenpartei nachfragen", note)

    def test_h_the_verlauf_has_one_row_per_document_in_time_order_with_open_requests_marked(self):
        rows = [i for i in self.items if i["kind"] == "entry"]
        self.assertEqual([r["date"] for r in rows], sorted(r["date"] for r in rows))
        self.assertEqual([r["key"] for r in rows if r["open"]], ["1", "7"])  # the customer's question; the agreed payment, not yet made
        phone = [r for r in rows if r["phone"]]
        self.assertEqual([r["date"] for r in phone], ["2025-02-11", "2025-03-25", "2025-03-27"])
        # Slice C: one note per item (C10a); the reminder's quote writes no date, so its own date is «prüfen» (C10g)
        for what in ("Mietvertrag", "Mängelrüge an die Verwaltung"):
            self.assertIn({"kind": "asked", "text": f"erneut verlangt (2.): {what} (Frist laut Akte, Datum prüfen) · beantwortet (Nr. 4)", "open": False},
                          rows[2]["notes"])
            self.assertIn({"kind": "asked", "text": f"verlangt von der Kundschaft: {what} bis 04.02.2025", "open": False}, rows[1]["notes"])

    def test_i_the_reader_read_less_and_every_quote_is_still_found_in_the_original(self):
        hygiene_stats = self.result["record"]["hygiene"]
        self.assertEqual((hygiene_stats["blocks"], hygiene_stats["quoted"]), (2, 1))  # two repeated disclaimers, one quoted mail
        self.assertGreater(hygiene_stats["removed"] / hygiene_stats["chars"], 0.2)


class LedgerTests(unittest.TestCase):
    def test_a_mandate_where_the_firm_asked_three_times_and_warned_once_shows_it_with_the_sender(self):
        case = CASES["mandat"]
        state, items, by_id = view(case, stored(case))
        rows = state["account"]["requests"]
        self.assertEqual([(r["by"], r["of"], r["what"], r["times"], r["warned"], r["due"], r["answered"]) for r in rows],
                         [("kanzlei", "kunde", "Belege der Reparaturkosten", 3, 1, "2025-04-24", None)])
        self.assertEqual(by_id["stand:offen_kunde"]["value"],
                         "Belege der Reparaturkosten · seit 01.03.2025 · 3× verlangt von der Kanzlei · mit Androhung")
        self.assertEqual(state["facts"]["bisherige_handlungen"], "A10 2025-02-10")  # what the firm asks is not the insurer's request
        self.assertEqual(state["facts"]["anforderungen"], "0")

    def test_a_first_report_only_has_no_stand(self):
        case = CASES["erstmeldung"]
        state, items, _ = view(case, stored(case))
        self.assertEqual(len(state["account"]["entries"]), 1)
        self.assertEqual([i for i in items if i["kind"] == "stand"], [])

    def test_a_run_made_before_the_account_opens_as_today_with_no_stand_and_nothing_invented(self):
        case = CASES["selbst"]
        result = stored(case)
        result.pop("record")
        state, items, by_id = view(case, result)
        self.assertIsNone(state["account"])
        self.assertEqual([i for i in items if i["kind"] in {"stand", "entry"}], [])
        self.assertNotIn("bisherige_handlungen", state["facts"])
        self.assertNotIn("einigung", state["facts"])

    def test_a_back_dated_entry_keeps_the_request_ids(self):
        graph = area.workflow("mietmangel-handler")
        entries = stored(CASES["selbst"])["record"]["entries"]
        ids = lambda acc: {r["what"]: r["id"] for r in acc["requests"]}
        before = ids(account.build(entries, graph))
        # Slice C (C10a): the combined ask of entry 2 is two rows, numbered in order within the entry (r2.0, r2.1)
        self.assertEqual(before, {"Kann ich den Mietzins reduzieren?": "r1.0", "Mietvertrag": "r2.0", "Mängelrüge an die Verwaltung": "r2.1", "IBAN": "r7.0"})
        # the handler enters a call made two days after the report, before our first request, in which a document was asked
        call = {"id": "e1", "op": "add_entry", "status": "active", "args": {"kind": "telefon", "party": "kunde", "date": "2025-01-12", "n": 9001,
                                                                            "said": "Kundin angerufen.", "asked": {"what": "Police der Hausratversicherung"}}}
        after = ids(account.build(account.with_handler(entries, [call]), graph))
        self.assertEqual({k: after[k] for k in before}, before)  # every request keeps its id: its asking entry and its place there
        self.assertEqual(after["Police der Hausratversicherung"], "r9001.0")
        frozen = lambda edits: ids(account.build(account.with_handler(entries, edits), graph, checked=False))  # a frozen study copy's rules
        self.assertEqual((frozen([])["IBAN"], frozen([call])["IBAN"]), ("r3", "r4"))  # by place in time order, ids move

    def test_silence_reads_the_ledger_only_the_party_asked_ends_it(self):
        graph = area.workflow("mietmangel-handler")
        entries = stored(CASES["selbst"])["record"]["entries"][:2]  # the report and the first request, nothing since
        acc = account.build(entries, graph)
        from datetime import date
        quiet = account.silence(acc, graph["clock"], date(2025, 3, 1), "klaeren")
        self.assertEqual((quiet["then"], quiet["last"], quiet["since"]), ("A6", "A1", "2025-01-14"))
        other = dict(entries[0], n=9, date="2025-02-01", **{"from": "gegenpartei"})  # the other side wrote: the customer is still silent
        self.assertIsNotNone(account.silence(account.build(entries + [other], graph), graph["clock"], date(2025, 3, 1), "klaeren"))
        mine = dict(entries[0], n=9, date="2025-02-01")
        self.assertIsNone(account.silence(account.build(entries + [mine], graph), graph["clock"], date(2025, 3, 1), "klaeren"))

    def test_lack_of_cooperation_is_a_request_asked_twice_unanswered_past_its_date(self):
        graph = area.workflow("mietmangel-handler")
        rules = {**graph["cooperation"]}
        entries = stored(CASES["selbst"])["record"]["entries"][:3]
        from datetime import date
        acc = account.build(entries, graph)
        self.assertTrue(account.derived(acc, "silent_after_requests", rules, date(2025, 3, 1)))
        self.assertFalse(account.derived(acc, "silent_after_requests", rules, date(2025, 2, 20)))
        acc = account.build(stored(CASES["selbst"])["record"]["entries"][:4], graph)
        self.assertFalse(account.derived(acc, "silent_after_requests", rules, date(2025, 3, 1)))


class HygieneTests(unittest.TestCase):
    def test_disclaimers_in_three_mails_and_a_quoted_mail_are_left_out_after_the_first_and_quotes_still_locate(self):
        case = CASES["selbst"]
        evidence = Evidence([{"id": "f1", "name": case["name"], "kind": "pdf", **files_of(case)[0]["extraction"]}])
        read = {p: t for p, t in evidence.files["f1"]["pages_read"]}
        disclaimer = "This e-mail contains confidential information intended solely for the addressee."
        self.assertIn(disclaimer, read[1])  # the first document that has it keeps it
        self.assertNotIn(disclaimer, read[4])
        self.assertNotIn(disclaimer, read[8])
        self.assertNotIn("> Wie telefonisch", read[8])  # the quoted earlier mail is its own document (page 4)
        self.assertIn("Wie telefonisch besprochen", read[4])
        self.assertIn("IBAN CH93", read[8])
        self.assertIsNotNone(evidence.locate("f1", disclaimer, 8, 8))  # a quote is still found in the original
        self.assertNotIn(disclaimer, evidence.read("f1")["text"].split("[page 2]")[1])

    def test_a_short_repeated_sentence_and_a_block_in_only_two_documents_stay(self):
        block = "Dies ist ein langer Hinweis zur Vertraulichkeit, der in zwei Schreiben steht und daher bleiben muss, weil zwei nicht drei sind."
        files = {"a": {"pages_raw": [(None, f"Brief eins.\nBitte senden Sie uns die Unterlagen.\n{block}")]},
                 "b": {"pages_raw": [(None, f"Brief zwei.\nBitte senden Sie uns die Unterlagen.\n{block}")]},
                 "c": {"pages_raw": [(None, "Brief drei.\nBitte senden Sie uns die Unterlagen.")]}}
        out, stats = hygiene.clean(files)
        self.assertEqual(stats["removed"], 0)
        self.assertEqual(out["b"], files["b"]["pages_raw"])


class ReaderCostTests(unittest.TestCase):
    def test_the_reader_with_the_record_replaces_the_history_paragraph(self):
        self.assertIn("record_steps", team.reader_instructions(True))
        self.assertNotIn("handlung_a1, handlung_a2", team.reader_instructions(True))
        self.assertIn("handlung_a1, handlung_a2", team.reader_instructions(False))


if __name__ == "__main__":
    unittest.main()

"""The handler's own entries in the running account (casepath/process/account.py handler_entry): a phone call, a
conversation, a note or an e-mail outside the file, entered in a short form and kept as the case's edits. Each counts at
once, without a model: the account, «Stand», the dates and the next action are recomputed from it.

Scripted and model-free: the cases are the update tests' synthetic situations (tests/test_update.py)."""
import unittest

from casepath.agents import core
from casepath.process import account, area, letters
from casepath.process.clock import follow_up
from casepath.process.items import build_items
from tests.test_update import AS_OF, OFFER_A, OFFER_B, REPLY_A, SITUATIONS, WID, both_ways, looked_at, prepared, full_turns

TODAY = AS_OF


def entry_edit(n, form, status="active", at="2026-11-15T10:00:00+00:00", eid=None):
    return {"id": eid or f"h{n}", "op": "add_entry", "args": {**form, "n": n}, "by": "N. Kumar", "reason": "Eintrag der Fallbearbeitung",
            "status": status, "at": at}


AGREEMENT = {"kind": "telefon", "party": "gegenpartei", "name": "Herr Muster", "date": TODAY, "said": "Einigung CHF 2'500, Zahlung bis 30.12.",
             "agreed": {"what": "Einigung", "amount": "2500", "payer": "gegenpartei", "by": "30.12.2026"}}
PROMISE = {"kind": "telefon", "party": "kunde", "date": TODAY, "said": "Kunde sagt, die Unterlagen folgen bis 15.12.",
           "next": {"what": "Unterlagen schicken", "by": "2026-12-15"}}


def view(result, files, edits):
    files = looked_at(files)
    state = core.evaluate(area.workflow(WID), [], list(edits), result, "case_u", files=files)
    items = build_items(state, result, files)
    return state, items, {i["item_id"]: i for i in items}


class FormTests(unittest.TestCase):
    def test_the_form_keeps_what_was_filled_and_names_what_is_missing_in_the_handlers_words(self):
        form = account.check_form(AGREEMENT)
        self.assertEqual(form["agreed"], {"what": "Einigung", "amount": "CHF 2'500", "payer": "gegenpartei", "by": "2026-12-30"})
        self.assertEqual((form["asked"], form["next"], form["date"]), (None, None, "2026-11-15"))
        for broken, message in (({**AGREEMENT, "kind": "brief"}, "Art des Eintrags"), ({**AGREEMENT, "party": "versicherer"}, "Mit wem"),
                                ({**AGREEMENT, "date": "gestern"}, "Datum"), ({"kind": "notiz", "date": TODAY, "said": " "}, "Was besprochen wurde"),
                                ({**AGREEMENT, "agreed": {"amount": "2500", "by": "Ende Jahr"}}, "Vereinbart: «bis» ist kein Datum")):
            with self.assertRaises(account.FormError) as caught:
                account.check_form(broken)
            self.assertIn(message, str(caught.exception))

    def test_an_entry_is_the_insurers_note_with_the_handler_as_its_source_numbered_apart_from_the_readers(self):
        e = account.handler_entry(account.check_form(AGREEMENT), 9001, by="N. Kumar", at="2026-11-15T10:00:00+00:00", edit="h1")
        self.assertEqual((e["from"], e["to"], e["kind"], e["phone"], e["citations"], e["file"]), ("versicherer", "gegenpartei", "annahme", True, [], None))
        self.assertEqual(e["handler"]["by"], "N. Kumar")
        self.assertEqual(account.code_of(e, area.workflow(WID)["record"]["kinds"]), ["9", "2"])  # a negotiation step and a file note
        note = account.handler_entry(account.check_form({"kind": "notiz", "party": "kanzlei", "date": TODAY, "said": "Bericht gelesen."}), 9002)
        self.assertEqual((note["to"], note["kind"], note["phone"]), ("versicherer", "telefon", False))  # a file note is to no one
        edits = [entry_edit(9001, AGREEMENT), entry_edit(9002, PROMISE, status="removed")]
        self.assertEqual(account.next_handler_number(edits), 9003)  # a removed entry's number is never used again
        self.assertEqual(account.next_handler_number([]), 9001)
        self.assertEqual([x["n"] for x in account.handler_entries(edits)], [9001])

    def test_a_changed_entry_is_a_new_edit_with_the_same_number_and_only_the_one_in_force_counts(self):
        changed = {**AGREEMENT, "agreed": {**AGREEMENT["agreed"], "amount": "2700"}}
        edits = [entry_edit(9001, AGREEMENT, status="replaced"), entry_edit(9001, changed, eid="h1b")]
        rows = account.handler_entries(edits)
        self.assertEqual([(r["n"], r["terms"][0]["amount"], r["handler"]["edit"]) for r in rows], [(9001, "CHF 2'700", "h1b")])


class AgreementByPhoneTests(unittest.TestCase):
    """A case Protekta conducts itself with an offer from the other side open; the handler enters a phone call with the
    other side: «Einigung CHF 2'500, Zahlung bis 30.12.»."""

    @classmethod
    def setUpClass(cls):
        cls.edits = SITUATIONS["offer"]["edits"]
        _, _, cls.result, _ = both_ways("offer")
        cls.files = [OFFER_A, OFFER_B]
        cls.before = view(cls.result, cls.files, cls.edits)
        cls.state, cls.items, cls.by_id = view(cls.result, cls.files, list(cls.edits) + [entry_edit(9001, AGREEMENT)])

    def test_stand_shows_the_agreement_from_the_handlers_entry(self):
        line = self.by_id["stand:vereinbart"]
        self.assertEqual(line["value"], "CHF 2'500 von der Gegenpartei bis 30.12.2026 · offen")
        self.assertEqual(line["detail"], "Gegenpartei zahlt CHF 2'500 (Einigung) bis 30.12.2026 · offen · Telefon vom 15.11.2026; "
                                         "ersetzt CHF 2'000 (Schreiben vom 05.11.2026)")  # the offer it settles
        self.assertEqual(line["handler"]["by"], "N. Kumar")
        self.assertEqual(self.by_id["stand:kontakt"]["value"], "15.11.2026 · Telefon mit der Gegenpartei")

    def test_the_next_action_becomes_the_settlement_sequence_not_the_answer_to_the_offer(self):
        before = self.before[2]["next_action:0"]
        self.assertEqual((before["action"], before["value"]), ("A9", "Antwort auf das Angebot der Gegenpartei"))
        nxt = self.by_id["next_action:0"]
        self.assertEqual(self.state["evaluation"]["current"]["step"], "abwicklung")
        self.assertEqual((nxt["action"], nxt["value"], nxt["form"]), ("A11", "Bankverbindung der Kundschaft erfragen", "A11_iban"))
        self.assertNotIn("incoming", nxt)  # the offer is answered by the agreement (A9 of the same day)
        self.assertTrue(self.state["facts"]["einigung"])
        self.assertEqual(self.by_id["stage_line:vg-einigung"]["value"],
                         "Einigung laut Eintrag der Fallbearbeitung: CHF 2'500 · zahlt: die Gegenpartei · bis 30.12.2026")

    def test_the_verlauf_marks_the_entry_as_entered_by_a_person_and_numbers_every_row_in_time_order(self):
        rows = [i for i in self.items if i["kind"] == "entry"]
        self.assertEqual([r["number"] for r in rows], [1, 2, 3, 4])
        own = rows[-1]
        self.assertEqual((own["key"], own["label"]["de"], own["origin"], own["handler"]["source"]), ("9001", "Telefon", "handler", "Fallbearbeitung"))
        self.assertEqual(own["evidence"], [])
        self.assertIn({"kind": "agreed", "text": "vereinbart: Gegenpartei zahlt CHF 2'500 (Einigung) bis 30.12.2026", "open": True}, own["notes"])

    def test_the_file_note_names_what_the_handler_entered_since_it_was_last_copied(self):
        note = letters.file_note({"title": "x"}, self.items, [], None, looked_at(self.files))
        self.assertIn("Erfasst durch die Fallbearbeitung: Telefon mit der Gegenpartei (Herr Muster) am 15.11.2026: Einigung CHF 2'500, "
                      "Zahlung bis 30.12 (vereinbart: Gegenpartei zahlt CHF 2'500 (Einigung) bis 30.12.2026).", note)
        later = letters.file_note({"title": "x"}, self.items, [{"kind": "filenote.copied", "at": "2026-11-15T11:00:00+00:00"}], None, looked_at(self.files))
        self.assertNotIn("Erfasst durch die Fallbearbeitung", later)


class PromiseByPhoneTests(unittest.TestCase):
    """The customer says by phone that the documents follow by 15.12.: the open requests show that date, and the
    follow-up date follows it."""

    @classmethod
    def setUpClass(cls):
        s = SITUATIONS["reply"]
        base, _ = prepared(s["a"], full_turns(s["entries_a"], s["facts_a"], s["docs_a"]))
        cls.result, cls.files = base["result"], [REPLY_A]
        cls.before = view(cls.result, cls.files, [])
        cls.state, cls.items, cls.by_id = view(cls.result, cls.files, [entry_edit(9001, PROMISE)])

    def test_the_open_requests_show_the_date_the_customer_gave(self):
        rows = self.by_id["stand:offen_kunde"]["rows"]
        self.assertEqual([r["text"] for r in rows], [f"{what} · seit 05.10.2026 · 1× verlangt · zugesagt bis 15.12.2026 (Telefon vom 15.11.2026)"
                                                     for what in ("Mietvertrag", "Mängelrüge an die Verwaltung", "Fotos des Mangels")])
        self.assertTrue(all(r["handler"] for r in rows))
        self.assertEqual({r["due"] for r in self.state["account"]["requests"]}, {"2026-12-15"})
        self.assertEqual({r["times"] for r in self.state["account"]["requests"]}, {1})  # a date given, not asked again
        dated = [i for i in self.items if i["kind"] == "deadline" and i.get("account")]
        self.assertEqual([(d["value"], d["what"], d["for"], d["by"]) for d in dated],
                         [("2026-12-15", "Mietvertrag, Mängelrüge an die Verwaltung, Fotos des Mangels (zugesagt)", "Kundschaft", "Kundschaft")])

    def test_the_follow_up_date_follows_the_date_given(self):
        before = self.before[2]["next_action:0"]
        self.assertEqual(before["reason"], "keine Antwort seit unserer Anforderung vom 05.10.2026 (41 Tage)")  # silence until the call
        nxt = self.by_id["next_action:0"]
        self.assertEqual((nxt["action"], nxt["value"], nxt["until"]), ("A6", "Dossier pendent halten mit Frist", "2026-12-15"))
        clock = follow_up(nxt.get("next_in_days"), looked_at(self.files), [], since=nxt.get("since"), until=nxt.get("until"))
        self.assertEqual(clock["due"], "2026-12-15")
        self.assertEqual(follow_up(nxt.get("next_in_days"), looked_at(self.files), [{"kind": "followup.set", "date": "2026-12-01"}],
                                   until=nxt.get("until"))["due"], "2026-12-01")  # a date the handler set still governs
        self.assertTrue(self.state["facts"]["anruf_offen"])  # «Vielen Dank für das Telefongespräch» in the pending letter


class OlderRunTests(unittest.TestCase):
    def test_a_run_made_before_the_account_lists_the_entry_and_changes_nothing_else(self):
        s = SITUATIONS["reply"]
        base, _ = prepared(s["a"], full_turns(s["entries_a"], s["facts_a"], s["docs_a"]))
        old = {k: v for k, v in base["result"].items() if k != "record"}
        before = view(old, [REPLY_A], [])
        state, items, by_id = view(old, [REPLY_A], [entry_edit(9001, PROMISE)])
        self.assertIsNone(state["account"])
        rows = [i for i in items if i["kind"] == "entry"]
        self.assertEqual([(r["key"], r.get("waiting")) for r in rows], [("9001", True)])
        self.assertEqual([i for i in items if i["kind"] == "stand"], [])
        self.assertEqual(by_id["next_action:0"]["action"], before[2]["next_action:0"]["action"])


if __name__ == "__main__":
    unittest.main()

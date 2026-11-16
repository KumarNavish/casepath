"""The account's consequential distinctions, checked by code (Slice C, C10): a promise or a refusal is not a delivery, a
partial answer closes only its item, an answer closes only what its addressee asked, a document read twice or a quoted
dispatch counts once, a dateless question back never makes lack of cooperation, the customer's assent passed to us is not
an agreement, an instruction is not a payment, values count only where their quotes write them, and a need or a claim is
delivered only by a file of the reply that holds it; a claim's receipt only when what the reading records about it agrees
with the claim (a shared word or amount is a candidate, never proof). A frozen study copy keeps the rules it was frozen
with (checked False).

The map's probes as regressions; all synthetic, model-free."""
from datetime import date
import unittest

from casepath.process import account, area

WID = "mietmangel-handler"
GRAPH = area.workflow(WID)
RULES = GRAPH["cooperation"] if "cooperation" in GRAPH else None


def cite(quote, file="f1", page=1):
    return [{"file": file, "page": page, "quote": quote}]


def entry(n, day, sender, to, kind, what, quote=None, file="f1", page=None, **elements):
    """A located entry as the account keeps it (account.check's shape)."""
    return {"n": n, "file": file, "page": page if page is not None else n, "date": day, "from": sender, "to": to, "kind": kind, "phone": False,
            "what": what, "citations": cite(quote or what, file, page if page is not None else n),
            **{k: elements.get(k, []) for k in account.ELEMENTS}}


def ask(what, of, quote=None, by=None):
    return {"what": what, "of": of, "by": by, "repeats": None, "warns": False, "citations": cite(quote or what)}


def answer(what, n, quote=None):
    return {"what": what, "answers": n, "citations": cite(quote or what)}


def rows(acc):
    return {r["what"]: r for r in acc["requests"]}


A1 = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Unterlagen verlangt",
           asks=[ask("Belege zu den Stromkosten", "kunde", "– Belege zu den Stromkosten für den Bautrockner"),
                 ask("Fotos des Mangels", "kunde", "– Fotos des Mangels")])


class PromiseAndRefusalTests(unittest.TestCase):
    def test_a_promise_is_not_a_delivery(self):
        """R4: «folgen» is a promise; the row stays open, «zugesagt, ohne Datum»; with a date written, that date, and once it
        passed «zugesagt bis …, nicht eingegangen»."""
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Belege angekündigt",
                      answers=[answer("Belege zu den Stromkosten folgen", 1, "Die Belege zu den Stromkosten folgen.")])
        acc = account.build([A1, reply], GRAPH)
        row = rows(acc)["Belege zu den Stromkosten"]
        self.assertIsNone(row["answered"])
        self.assertEqual((row["promised"]["by"], row["due"]), (None, None))
        self.assertIn("zugesagt, ohne Datum", account._request_text(row))
        dated = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Belege angekündigt",
                      answers=[answer("Belege zu den Stromkosten folgen bis 30.09.2026", 1, "Die Belege zu den Stromkosten folgen bis 30.09.2026.")])
        acc = account.build([A1, dated], GRAPH)
        row = rows(acc)["Belege zu den Stromkosten"]
        self.assertEqual((row["answered"], row["due"]), (None, "2026-09-30"))
        self.assertEqual(account.awaited(acc, "kunde", date(2026, 9, 1))["date"], "2026-09-30")
        late = account.awaited(acc, "kunde", date(2026, 10, 2))
        self.assertTrue(late["overdue"])
        self.assertEqual(late["text"], "zugesagt bis 30.09.2026, nicht eingegangen: Belege zu den Stromkosten")

    def test_a_negation_never_closes_a_row(self):
        """«Für die Stromkosten habe ich keine Belege»: a refusal; the row stays open with «abgelehnt: …»."""
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Keine Belege",
                      answers=[answer("Keine Belege zu den Stromkosten", 1, "Für die Stromkosten habe ich keine Belege.")])
        acc = account.build([A1, reply], GRAPH)
        row = rows(acc)["Belege zu den Stromkosten"]
        self.assertIsNone(row["answered"])
        self.assertEqual(row["refused"]["n"], 2)
        self.assertEqual([r["request"] for r in acc["refused"]], ["r1.0"])
        self.assertIn("abgelehnt: Keine Belege zu den Stromkosten", account._request_text(row))
        notes = [n["text"] for r in account.rows(acc, GRAPH) for n in r["notes"] if n["kind"] == "refused"]
        self.assertEqual(notes, ["abgelehnt: Keine Belege zu den Stromkosten (zu Nr. 1)"])
        # a «no» to a question asked for information answers it (it delivers nothing asked)
        question = entry(3, "2026-08-12", "versicherer", "kunde", "anforderung", "Rückfrage",
                         asks=[ask("Haben Sie den Mangel schriftlich gemeldet?", "kunde")])
        no = entry(4, "2026-08-14", "kunde", "versicherer", "antwort", "Antwort",
                   answers=[answer("Mangel nicht schriftlich gemeldet", 3, "Nein, ich habe den Mangel nicht schriftlich gemeldet.")])
        self.assertEqual(rows(account.build([question, no], GRAPH))["Haben Sie den Mangel schriftlich gemeldet?"]["answered"]["n"], 4)

    def test_a_mixed_element_is_split_before_it_is_typed(self):
        """«Fotos anbei, Belege zu den Stromkosten folgen»: one delivery and one promise."""
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Fotos zugestellt, Belege folgen",
                      answers=[answer("Fotos anbei, Belege zu den Stromkosten folgen", 1, "Fotos anbei, Belege zu den Stromkosten folgen.")])
        acc = account.build([A1, reply], GRAPH)
        self.assertEqual([p["type"] for p in account.typed_parts(acc["entries"][1]["answers"][0])], ["answer", "promise"])
        fotos, belege = rows(acc)["Fotos des Mangels"], rows(acc)["Belege zu den Stromkosten"]
        self.assertEqual(fotos["answered"]["n"], 2)
        self.assertIsNone(belege["answered"])
        self.assertEqual(belege["promised"]["n"], 2)


class PartialTests(unittest.TestCase):
    def test_a_partial_answer_closes_only_its_item(self):
        """P1: a combined ask is one row per item (ids r1.0, r1.1, r1.2, the same quote); an answer naming two of them closes
        those two; an answer naming part of an item is «teilweise» with what remains."""
        combined = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Unterlagen verlangt",
                         asks=[ask("Mietvertrag, Fotos des Mangels und Belege der Stromkosten", "kunde",
                                   "Bitte senden Sie uns den Mietvertrag, Fotos des Mangels und Belege der Stromkosten.")])
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "unterlagen", "Mietvertrag und Fotos zugestellt",
                      answers=[answer("Mietvertrag und Fotos des Mangels anbei", 1, "Anbei der Mietvertrag und Fotos des Mangels.")])
        acc = account.build([combined, reply], GRAPH)
        self.assertEqual([(r["id"], r["what"]) for r in acc["requests"]],
                         [("r1.0", "Mietvertrag"), ("r1.1", "Fotos des Mangels"), ("r1.2", "Belege der Stromkosten")])
        self.assertEqual(len({r["citations"][0]["quote"] for r in acc["requests"]}), 1)
        self.assertEqual([r["id"] for r in acc["requests"] if r["answered"]], ["r1.0", "r1.1"])
        some = entry(2, "2026-08-10", "kunde", "versicherer", "unterlagen", "Belege",
                     answers=[answer("Belege anbei", 1, "Belege anbei.")])
        ask_ = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Belege verlangt",
                     asks=[ask("Belege der Stromkosten für den Bautrockner", "kunde"), ask("Fotos des Mangels", "kunde")])
        row = rows(account.build([ask_, some], GRAPH))["Belege der Stromkosten für den Bautrockner"]
        self.assertIsNone(row["answered"])
        self.assertEqual(row["partial"]["rest"], "Stromkosten Bautrockner")
        self.assertIn("teilweise: Belege anbei – offen: Stromkosten Bautrockner", account._request_text(row))

    def test_a_letter_level_answer_over_several_requests_closes_none(self):
        """R3: an answer that names the asking entry, which holds two open rows, and shares no word with either, closes none:
        «Antwort ohne Zuordnung – prüfen»; it still counts as a reply."""
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Antwort", answers=[answer("Hier meine Antwort", 1, "Hier meine Antwort.")])
        acc = account.build([A1, reply], GRAPH)
        self.assertEqual([r["answered"] for r in acc["requests"]], [None, None])
        self.assertEqual([(u["n"], sorted(u["rows"])) for u in acc["unspecified"]], [(2, ["r1.0", "r1.1"])])
        notes = [n["text"] for r in account.rows(acc, GRAPH) for n in r["notes"] if n["kind"] == "unspecified"]
        self.assertEqual(notes, ["Antwort ohne Zuordnung – prüfen: Hier meine Antwort"])
        self.assertTrue(account.derived(acc, "replied_since_request", GRAPH.get("cooperation") or {}, date(2026, 8, 20)))

    def test_a_delivery_to_protekta_does_not_close_the_landlords_demand(self):
        """P4: the landlord asks the customer for the same thing we do; the customer's delivery to us closes our row only."""
        theirs = entry(1, "2026-08-01", "gegenpartei", "kunde", "andere", "Forderung der Verwaltung",
                       asks=[ask("Belege der Reparaturkosten", "kunde")])
        ours = entry(2, "2026-08-02", "versicherer", "kunde", "anforderung", "Belege verlangt", asks=[ask("Belege der Reparaturkosten", "kunde")])
        reply = entry(3, "2026-08-10", "kunde", "versicherer", "unterlagen", "Belege zugestellt",
                      answers=[{"what": "Belege der Reparaturkosten anbei", "answers": None, "citations": cite("Belege der Reparaturkosten anbei.")}])
        acc = account.build([theirs, ours, reply], GRAPH)
        by_asker = {r["by"]: r for r in acc["requests"]}
        self.assertEqual(by_asker["versicherer"]["answered"]["n"], 3)
        self.assertIsNone(by_asker["gegenpartei"]["answered"])


class SameDocumentTests(unittest.TestCase):
    def test_a_duplicate_entry_never_counts_as_asking_twice(self):
        """R5b: the A1 read twice (same day, sender, addressee, kind and quote) is one document: one row, asked once; the same
        ask again on the same day is no repeat either."""
        again = {**A1, "n": 7, "page": 7}
        acc = account.build([A1, again], GRAPH)
        self.assertEqual([(r["id"], r["times"]) for r in acc["requests"]], [("r1.0", 1), ("r1.1", 1)])
        self.assertEqual(acc["merged"], [{"n": 7, "into": 1, "why": "same"}])
        same_day = entry(8, "2026-08-02", "versicherer", "kunde", "mahnung", "Erinnerung", "Erinnerung an die Belege",
                         asks=[ask("Belege zu den Stromkosten", "kunde", "Erinnerung: Belege zu den Stromkosten")])
        self.assertEqual(rows(account.build([A1, same_day], GRAPH))["Belege zu den Stromkosten"]["times"], 1)
        later = {**same_day, "date": "2026-08-30"}
        self.assertEqual(rows(account.build([A1, later], GRAPH))["Belege zu den Stromkosten"]["times"], 2)

    def test_a_quoted_dispatch_joins_its_dispatch_entry(self):
        """The A5 quoted below the receipts e-mail is the dispatched A5 (ours, to the same addressee, the same action, within
        three days): its quote joins the dispatch's entry; its ask is not asked a second time."""
        sent = {**entry(9101, "2026-09-08", "versicherer", "kunde", "einschaetzung", "Rechtliche Einschätzung", file=None, page=0),
                "citations": [], "code": "5", "dispatch": {"version": "v1", "by": "N. Kumar", "at": "2026-09-08T14:05:00+02:00", "channel": "E-Mail"},
                "asks": [{**ask("Belege zu: Stromkosten für den Bautrockner", "kunde"), "citations": [], "kind": "claim", "ref": 0}]}
        quoted = entry(20, "2026-09-08", "versicherer", "kunde", "einschaetzung", "Rechtliche Einschätzung (zitiert)",
                       "Betreff: Rechtliche Einschätzung 4321.6011.0001", file="fs",
                       asks=[ask("Belege zu: Stromkosten für den Bautrockner", "kunde", "> – Belege zu: Stromkosten für den Bautrockner")])
        acc = account.build([sent, quoted], GRAPH)
        self.assertEqual(acc["merged"], [{"n": 20, "into": 9101, "why": "dispatch"}])
        row, = acc["requests"]
        self.assertEqual((row["id"], row["times"], row["ask"]), ("r9101.0", 1, {"kind": "claim", "ref": 0}))
        dispatched = next(e for e in acc["entries"] if e["n"] == 9101)
        self.assertEqual((dispatched["quoted"], dispatched["citations"][0]["file"]), ([20], "fs"))
        self.assertEqual([a["code"] for a in acc["actions"]], ["5"])  # one A5, not two


class CooperationAndAgreementTests(unittest.TestCase):
    def test_a_dateless_question_back_never_counts_for_lack_of_cooperation(self):
        """P10: an A4-like question without a date, asked twice and unanswered, is no lack of cooperation; with a date it is."""
        rules = GRAPH.get("cooperation") or {"requests": {"1": 21}, "min_requests": 2}
        q = lambda n, day, by=None: entry(n, day, "versicherer", "kunde", "anforderung", "Rückfrage",
                                          f"Rückfrage vom {day}" + (f", Antwort bis {by}" if by else ""),
                                          asks=[ask("Besteht der Schimmel weiterhin?", "kunde",
                                                    "Besteht der Schimmel weiterhin?" + (f" Bitte antworten Sie bis {account.day(by)}." if by else ""), by)])
        undated = account.build([q(1, "2026-08-02"), q(2, "2026-08-20")], GRAPH)
        self.assertEqual(rows(undated)["Besteht der Schimmel weiterhin?"]["times"], 2)
        self.assertFalse(account.derived(undated, "silent_after_requests", rules, date(2026, 11, 1)))
        dated = account.build([q(1, "2026-08-02", "2026-08-16"), q(2, "2026-08-20", "2026-09-03")], GRAPH)
        self.assertTrue(account.derived(dated, "silent_after_requests", rules, date(2026, 11, 1)))
        frozen = account.build([q(1, "2026-08-02"), q(2, "2026-08-20")], GRAPH, checked=False)  # a study copy: the rules it was frozen with
        self.assertTrue(account.derived(frozen, "silent_after_requests", rules, date(2026, 11, 1)))

    def test_the_customers_consent_to_protekta_is_not_an_agreement(self):
        """O2: the other side offers CHF 2'000; the customer tells us she agrees: «Zustimmung der Kundschaft», no agreement;
        our acceptance to the other side makes it one."""
        offer = entry(1, "2026-09-01", "gegenpartei", "versicherer", "angebot", "Vergleichsangebot",
                      terms=[{"what": "Vergleich per Saldo", "amount": "CHF 2'000", "payer": "gegenpartei", "by": None, "agreed": False,
                              "citations": cite("Wir bieten CHF 2'000 per Saldo aller Ansprüche.")}])
        consent = entry(2, "2026-09-03", "kunde", "versicherer", "antwort", "Kundin einverstanden",
                        terms=[{"what": "Vergleich per Saldo", "amount": "CHF 2'000", "payer": "gegenpartei", "by": None, "agreed": True,
                                "citations": cite("Mit den CHF 2'000 bin ich einverstanden.")}])
        acc = account.build([offer, consent], GRAPH)
        self.assertIsNone(acc["agreement"])
        self.assertEqual([t["n"] for t in acc["consent"]], [2])
        stand = {line["id"]: line["text"] for line in account.stand(acc, date(2026, 9, 5), GRAPH)}
        self.assertTrue(stand["zustimmung"].startswith("Zustimmung der Kundschaft (nicht der Gegenpartei)"))
        accept = entry(3, "2026-09-04", "versicherer", "gegenpartei", "annahme", "Annahme des Angebots", "Wir nehmen Ihr Angebot von CHF 2'000 an.")
        acc = account.build([offer, consent, accept], GRAPH)
        self.assertEqual((acc["agreement"]["n"], acc["agreement"]["amount"]), (3, "CHF 2'000"))

    def test_an_instruction_is_not_a_payment_and_a_partial_payment_says_so(self):
        """O3, P8: «wir werden überweisen» is an announcement (a next step); CHF 500 paid of CHF 2'000 is «teilweise bezahlt»
        and the rest is still owed."""
        agreed = entry(1, "2026-09-01", "gegenpartei", "versicherer", "annahme", "Vergleich",
                       terms=[{"what": "Vergleich", "amount": "CHF 2'000", "payer": "gegenpartei", "by": "2026-09-10", "agreed": True,
                               "citations": cite("Wir zahlen CHF 2'000 per Saldo bis 10.09.2026.")}])
        announced = entry(2, "2026-09-05", "gegenpartei", "versicherer", "andere", "Zahlung angekündigt",
                          paid=[{"amount": "CHF 2'000", "payer": "gegenpartei", "date": None,
                                 "citations": cite("Wir werden die CHF 2'000 nächste Woche überweisen.")}])
        acc = account.build([agreed, announced], GRAPH)
        self.assertIsNone(acc["payment"])
        self.assertEqual([x["what"] for x in acc["entries"][1]["next"]], ["Zahlung CHF 2'000 angekündigt"])
        part = entry(3, "2026-09-12", "gegenpartei", "versicherer", "zahlung", "Teilzahlung",
                     paid=[{"amount": "CHF 500", "payer": "gegenpartei", "date": "2026-09-12", "citations": cite("CHF 500 haben wir heute überwiesen.")}])
        acc = account.build([agreed, announced, part], GRAPH)
        self.assertIsNone(acc["payment"])
        self.assertEqual((acc["partly_paid"]["paid"], acc["partly_paid"]["of"]), (500.0, 2000.0))
        line = next(x for x in account.stand(acc, date(2026, 9, 15), GRAPH) if x["id"] == "vereinbart")
        self.assertIn("teilweise bezahlt: CHF 500 von CHF 2'000", line["detail"])
        self.assertIsNotNone(account.payout_due(acc, date(2026, 9, 15)))


class ValueTests(unittest.TestCase):
    def test_a_date_not_in_its_quote_is_to_check(self):
        """A date the reader gives that its quote does not write: «Frist laut Akte, Datum prüfen», never a date."""
        given = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Belege verlangt",
                      asks=[ask("Belege der Stromkosten", "kunde", "Bitte reichen Sie die Belege der Stromkosten ein.", "2026-09-30")])
        row = rows(account.build([given], GRAPH))["Belege der Stromkosten"]
        self.assertEqual((row["due"], row["due_text"], row.get("by_check")), (None, account.CHECK_DATE, True))
        written = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Belege verlangt",
                        asks=[ask("Belege der Stromkosten", "kunde", "Bitte reichen Sie die Belege der Stromkosten bis 30. September 2026 ein.", "2026-09-30")])
        self.assertEqual(rows(account.build([written], GRAPH))["Belege der Stromkosten"]["due"], "2026-09-30")
        self.assertEqual(rows(account.build([given], GRAPH, checked=False))["Belege der Stromkosten"]["due"], "2026-09-30")  # the frozen rules

    def test_a_forwarded_message_keeps_its_own_date(self):
        """The d+13 shape: a reply with forwarded e-mails; each forwarded message keeps the day its own header writes; an
        entry whose day is written nowhere on its page is «Datum prüfen» and dates nothing."""
        page = ("---------- Weitergeleitete Nachricht ----------\nVon: Sara Exempel\nGesendet: 20. Juli 2026 21:05\nAn: Immo Beispiel AG, Verwaltung\n"
                "Betreff: Schimmel Ahornweg 12\n\nIch bitte Sie, den Mangel zu beheben.")
        kinds = GRAPH["record"]["kinds"]
        raw = {"n": 5, "file": "fa", "page": 9, "date": "2026-07-20", "from": "kunde", "to": "gegenpartei", "kind": "andere", "what": "Mängelrüge",
               "quote": "Betreff: Schimmel Ahornweg 12", "asks": [{"what": "Mangel beheben", "of": "gegenpartei", "quote": "Ich bitte Sie, den Mangel zu beheben."}]}
        locate = lambda quote: {"file": "fa", "page": 9, "quote": quote} if quote and quote in page else None
        kept, _ = account.check(raw, locate, kinds, page_text=lambda f, p: page)
        self.assertNotIn("date_check", kept)
        wrong, _ = account.check({**raw, "date": "2026-08-14"}, locate, kinds, page_text=lambda f, p: page)
        self.assertTrue(wrong["date_check"])
        # the page's own lines name the addressee (the management), the reader said the customer: «Absender prüfen»
        sender, _ = account.check({**raw, "from": "gegenpartei", "to": "kunde"}, locate, kinds, page_text=lambda f, p: page)
        self.assertTrue(sender.get("to_check"))
        self.assertIn("Absender prüfen", [n["text"] for r in account.rows(account.build([sender], GRAPH), GRAPH) for n in r["notes"] if n["kind"] == "check"])
        notes = [n["text"] for r in account.rows(account.build([wrong], GRAPH), GRAPH) for n in r["notes"] if n["kind"] == "check"]
        self.assertIn("Datum prüfen", notes)

    def test_an_amount_not_in_its_quote_is_dropped(self):
        """Terms whose amount the quote does not write: the amount is dropped, «Betrag nicht im Zitat – prüfen», and they agree
        nothing."""
        offer = entry(1, "2026-09-01", "gegenpartei", "versicherer", "annahme", "Vergleich",
                      terms=[{"what": "Vergleich", "amount": "CHF 3'000", "payer": "gegenpartei", "by": None, "agreed": True,
                              "citations": cite("Wir sind mit einem Vergleich einverstanden.")}])
        acc = account.build([offer], GRAPH)
        self.assertIsNone(acc["agreement"])
        term, = acc["terms"]
        self.assertEqual((term["amount"], term["amount_check"], term["flag"]), (None, "CHF 3'000", "Betrag nicht im Zitat – prüfen"))
        self.assertIsNotNone(account.build([offer], GRAPH, checked=False)["agreement"])  # the frozen rules took it


class HeldTests(unittest.TestCase):
    MAIL = {"id": "fm", "name": "AW Unterlagen.eml", "extraction": {"segments": []}}
    LEASE = {"id": "fl", "name": "Scan_0042.pdf", "extraction": {"attached_to": "AW Unterlagen.eml", "segments": [
        {"first_page": 1, "last_page": 5, "kind": "Mietvertrag", "title": "Mietvertrag"}]}}

    def test_a_need_counts_as_delivered_only_when_a_file_of_the_reply_holds_it(self):
        """A module need: «Mietvertrag anbei» delivers the lease only when a file of the reply (its attachment) is the lease;
        otherwise the need stays missing, «laut Antwort vom … beigelegt, nicht in der Akte». A dispatch's ask (Slice B's row
        without an answer) is looked for in the reply's files given."""
        ask_ = entry(1, "2026-08-02", "versicherer", "kunde", "anforderung", "Mietvertrag verlangt", asks=[ask("Mietvertrag", "kunde")])
        reply = entry(2, "2026-08-10", "kunde", "versicherer", "unterlagen", "Mietvertrag zugestellt", file="fm",
                      answers=[answer("Mietvertrag anbei", 1, "Den Mietvertrag sende ich Ihnen anbei.")])
        needs = [{"id": "mietvertrag", "title": "Mietvertrag"}]
        acc = account.build([ask_, reply], GRAPH)
        got = account.delivered(acc, needs, [self.MAIL, self.LEASE])
        self.assertEqual((got["mietvertrag"]["files"], got["mietvertrag"]["held"]["how"]), (["fl"], "segment"))
        acc = account.build([ask_, reply], GRAPH)
        self.assertEqual(account.delivered(acc, needs, [self.MAIL]), {})  # the e-mail says so; nothing of the reply holds it
        row = rows(acc)["Mietvertrag"]
        self.assertEqual(row["answered"]["unheld"], "laut Antwort vom 10.08.2026 beigelegt, nicht in der Akte: Mietvertrag")
        dispatch_row = {"what": "Mietvertrag", "need": "mietvertrag", "title": "Mietvertrag"}
        self.assertEqual(account.held(dispatch_row, [self.MAIL, self.LEASE])["file"], "fl")
        self.assertIsNone(account.held(dispatch_row, [self.MAIL]))

    def test_a_receipt_is_held_for_a_claim_only_when_what_the_reading_records_agrees(self):
        """The newer steering's semantic check: the claim «Stromkosten für den Bautrockner» (rund CHF 85). A bill whose words
        are other words for it («Energieverbrauch des Bautrockners», CHF 85.40, billed to the customer) delivers it without
        the handler entering anything; a shop's receipt for the same amount for something else does not, nor does a credit
        note refunding the cost; each set-aside candidate says why."""
        claim = {"what": "Stromkosten für den Bautrockner", "amount": "CHF 85",
                 "citations": cite("Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben.", "fc")}
        asked = entry(1, "2026-09-08", "versicherer", "kunde", "einschaetzung", "Rechtliche Einschätzung",
                      asks=[ask("Belege zu: Stromkosten für den Bautrockner", "kunde", "– Belege zu: Stromkosten für den Bautrockner")])
        mail = {"id": "fs", "name": "AW Rechtliche Einschaetzung.eml", "extraction": {"segments": []}}

        def reply_with(fid, name, what, quote, sender="andere"):
            attached = {"id": fid, "name": name, "extraction": {"attached_to": mail["name"], "segments": []}}
            entries = [asked, entry(2, "2026-09-28", "kunde", "versicherer", "unterlagen", "Beleg zugestellt", file="fs",
                                    answers=[answer("Beleg zu den Stromkosten", 1, "Den Beleg sende ich Ihnen anbei.")]),
                       entry(3, None, sender, "kunde", "andere", what, quote, file=fid)]
            acc = account.build(entries, GRAPH)
            account.delivered(acc, [], [mail, attached], {}, [claim])
            return rows(acc)["Belege zu: Stromkosten für den Bautrockner"]["answered"]

        paraphrase = reply_with("fp", "EW Zusatzabrechnung.txt", "Abrechnung Energieverbrauch Bautrockner",
                                "Energieverbrauch des Bautrockners vom 07.08.2026 bis 04.09.2026: 212 kWh, Betrag CHF 85.40, zahlbar innert 30 Tagen")
        self.assertEqual((paraphrase["held"]["file"], paraphrase["held"]["how"]), ("fp", "receipt"))
        self.assertEqual((paraphrase["held"]["basis"]["amounts"], paraphrase["held"]["basis"]["role"]), ([85.4], "requested"))
        same_amount = reply_with("fu", "Quittung.txt", "Quittung Drogerie: Luftentfeuchter-Granulat", "2 kg Luftentfeuchter-Granulat CHF 85.40, bar bezahlt")
        self.assertNotIn("held", same_amount)
        self.assertEqual(same_amount["unheld"], "laut Antwort vom 28.09.2026 beigelegt, nicht in der Akte: Belege zu: Stromkosten für den Bautrockner")
        self.assertEqual(same_amount["aside"][0]["why"], ["andere Ausgabe: Quittung Drogerie: Luftentfeuchter-Granulat"])
        refunded = reply_with("fv", "Gutschrift.txt", "Gutschrift Stromkosten Bautrockner",
                              "Wir vergüten Ihnen die Stromkosten für den Bautrockner von CHF 85.40.", sender="gegenpartei")
        self.assertNotIn("held", refunded)
        self.assertEqual(refunded["aside"][0]["why"], ["Betrag erstattet, nicht belegt"])
        # what the reading records, where it records it (Slice A: the entry's receipt record), decides over the line
        recorded = {**entry(3, None, "andere", "kunde", "andere", "Beleg", "Betrag CHF 85.40", file="fp"),
                    "receipt": {"expense": "Strom für den Bautrockner", "party": "Energie Beispiel AG", "payer": "kunde",
                                "period": None, "transaction": "08-4411", "amount": "CHF 85.40", "role": "requested", "citations": cite("Betrag CHF 85.40", "fp")}}
        self.assertEqual(account.documented({**claim, "transaction": "08-4411"}, [mail], [recorded], ["fp"])["file"], "fp")
        why = []
        self.assertIsNone(account.documented({**claim, "transaction": "08-9999"}, [mail], [recorded], ["fp"], why))
        self.assertEqual(why[0]["why"], ["andere Nummer: 08-4411"])


class StudyCopyTests(unittest.TestCase):
    def test_a_study_copy_gets_none_of_these_checks(self):
        """checked False, the rules a frozen study copy was frozen with: positional ids, the combined ask one row, a refusal
        closing its row by its words, no flags."""
        refused = entry(2, "2026-08-10", "kunde", "versicherer", "antwort", "Keine Belege",
                        answers=[answer("Keine Belege zu den Stromkosten", 1, "Für die Stromkosten habe ich keine Belege.")])
        frozen = account.build([A1, refused], GRAPH, checked=False)
        self.assertEqual([r["id"] for r in frozen["requests"]], ["r1", "r2"])
        self.assertEqual(rows(frozen)["Belege zu den Stromkosten"]["answered"]["n"], 2)  # as before this release
        self.assertNotIn("checked", frozen)
        self.assertFalse([n for r in account.rows(frozen, GRAPH) for n in r["notes"] if n["kind"] in ("refused", "check", "unspecified")])
        live = account.build([A1, refused], GRAPH)
        self.assertEqual(([r["id"] for r in live["requests"]], rows(live)["Belege zu den Stromkosten"]["answered"]), (["r1.0", "r1.1"], None))



class NegatedAmountTests(unittest.TestCase):
    def test_a_corrected_amount_is_no_refusal(self):
        """«CHF 120, nicht rund CHF 85» corrects a number: typed an answer; «keine Belege» still refuses."""
        part = lambda quote: account.typed_parts({"what": "Stromkosten", "citations": [{"quote": quote}]})[0]["type"]
        self.assertEqual(part("Die Stromkosten für den Bautrockner betragen CHF 120, nicht rund CHF 85."), "answer")
        self.assertEqual(part("Es sind CHF 120 und nicht 85 Franken."), "answer")
        self.assertEqual(part("Für die Stromkosten habe ich keine Belege."), "refusal")
        self.assertEqual(part("Die Belege zu den Stromkosten kann ich nicht liefern."), "refusal")


if __name__ == "__main__":
    unittest.main()
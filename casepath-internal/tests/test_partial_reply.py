"""The customer answers in part: the next step is the question back that names what came and asks exactly what is
still open (account.partial_reply, process/partial.py), and a follow-up is due on its day. Synthetic ledgers, no model."""
import unittest

from casepath.process import account, partial

INSURER = account.INSURER


def entry(n, day, sender, to, kind="andere", asks=(), answers=()):
    return {"n": n, "date": day, "from": sender, "to": to, "kind": kind, "asks": list(asks), "answers": list(answers)}


def request(rid, what, answered=None, by=INSURER, of="kunde", first="2025-05-28", **more):
    return {"id": rid, "by": by, "of": of, "what": what, "first": first, "last": first, "answered": answered, "times": 1, **more}


def ledger(requests, last_ask="2025-05-28"):
    return {"checked": True, "entries": [entry(2, last_ask, INSURER, "kunde", "anforderung", asks=[{"of": "kunde", "what": "x"}]),
                                         entry(3, "2025-06-11", "kunde", INSURER, "unterlagen")],
            "requests": requests, "actions": [{"n": 2, "code": "1", "date": last_ask}]}


class PartialReplyTests(unittest.TestCase):
    def test_something_came_and_something_is_open(self):
        acc = ledger([request("r2.0", "Arbeitszeugnis", {"n": 3, "date": "2025-06-11"}),
                      request("r2.1", "Belege zur Leistung", ask={"kind": "document", "ref": "belege"}),
                      request("r2.2", "Seit wann arbeiten Sie dort?"),
                      request("r1.0", "Was kann ich tun?", by="kunde", of=INSURER)])  # the customer's own question is not ours to ask back
        part = account.partial_reply(acc)
        self.assertEqual((part["date"], part["received"]), ("2025-06-11", [{"what": "Arbeitszeugnis", "request": "r2.0"}]))
        self.assertEqual([(o["what"], o["request"], o.get("ref")) for o in part["open"]],
                         [("Belege zur Leistung", "r2.1", "belege"), ("Seit wann arbeiten Sie dort?", "r2.2", None)])

    def test_nothing_came_everything_came_or_it_came_before_we_asked(self):
        self.assertIsNone(account.partial_reply(ledger([request("r2.0", "Arbeitszeugnis"), request("r2.1", "Belege")])))  # silence: the clock's matter
        both = [request("r2.0", "Arbeitszeugnis", {"n": 3, "date": "2025-06-11"}), request("r2.1", "Belege", {"n": 3, "date": "2025-06-11"})]
        self.assertIsNone(account.partial_reply(ledger(both)))  # complete: the case moves on
        early = [request("r2.0", "Arbeitszeugnis", {"n": 1, "date": "2025-05-20"}), request("r2.1", "Belege")]
        self.assertIsNone(account.partial_reply(ledger(early)))  # delivered before our last request: no reply to it
        settled = [request("r2.0", "Arbeitszeugnis", {"n": None, "date": "2025-06-11", "settled": True}), request("r2.1", "Belege")]
        self.assertIsNone(account.partial_reply(ledger(settled)))  # closed by the handler, not delivered by the customer
        self.assertIsNone(account.partial_reply(None))

    def test_the_letter_names_what_came_and_asks_exactly_what_is_open(self):
        base = {"title": "Rückfrage zu einem Punkt", "to": "Kundschaft", "parts": ["Vielen Dank für Ihre Unterlagen.", "… zu folgendem Punkt:\n{fragen_oder_offen}",
                                                                                 "Wir danken Ihnen für Ihre Antwort bis {frist}."]}
        part = {"date": "2025-06-11", "received": [{"what": "Arbeitszeugnis", "request": "r2.0"}],
                "open": [{"what": "Belege zur Leistung", "request": "r2.1", "kind": "document", "ref": "belege"}, {"what": "Seit wann arbeiten Sie dort?", "request": "r2.2"}]}
        form = partial.form(base, part)
        self.assertEqual(form["parts"], ["Vielen Dank für Ihre Nachricht vom 11.06.2025. Erhalten haben wir: Arbeitszeugnis.",
                                         "Damit wir weiterfahren können, benötigen wir noch:\n– Belege zur Leistung\n– Seit wann arbeiten Sie dort?",
                                         "Wir danken Ihnen für Ihre Antwort bis {frist}."])
        self.assertEqual(form["title"], "Rückfrage zu den offenen Punkten")
        self.assertEqual(partial.asks(part, "kunde", "2025-06-27"),
                         [{"what": "Belege zur Leistung", "of": "kunde", "by": "2025-06-27", "kind": "document", "ref": "belege"},
                          {"what": "Seit wann arbeiten Sie dort?", "of": "kunde", "by": "2025-06-27"}])


class ReopenTests(unittest.TestCase):
    def test_a_request_read_as_delivered_is_open_again_until_something_later_answers_it(self):
        rows = [request("r2.0", "Arbeitszeugnis", {"n": 3, "date": "2025-06-11"}), request("r2.1", "Belege")]
        entries = [{"n": 2, "settled": [{"request": "r2.0", "how": "offen", "by": "A. Handler", "at": "2025-06-12T08:00:00+00:00", "edit": "e1"}]}]
        account._settle(rows, entries, {})
        self.assertIsNone(rows[0]["answered"])
        self.assertEqual((rows[0]["reopened"]["by"], rows[0]["reopened"]["was"]), ("A. Handler", {"n": 3, "date": "2025-06-11"}))
        later = [request("r2.0", "Arbeitszeugnis", {"n": 5, "date": "2025-06-20"})]  # it came after the correction: answered
        account._settle(later, entries, {})
        self.assertEqual(later[0]["answered"]["n"], 5)
        closed = [request("r2.0", "Arbeitszeugnis", {"n": None, "date": "2025-06-10", "settled": True})]  # the handler's own settlement stays
        account._settle(closed, entries, {})
        self.assertTrue(closed[0]["answered"]["settled"])


class DueDayTests(unittest.TestCase):
    RULES = [{"after": ["6"], "days": 28, "then": "A7", "stages": ["klaeren"]}]

    def acc(self, checked):
        return {"checked": checked, "entries": [entry(4, "2025-06-12", INSURER, "kunde", "abschlussankuendigung")], "requests": [],
                "actions": [{"n": 4, "code": "6", "date": "2025-06-12"}]}

    def test_the_follow_up_is_prepared_on_the_day_it_falls_due(self):
        from datetime import date
        due, before = date(2025, 7, 10), date(2025, 7, 9)
        self.assertEqual(account.silence(self.acc(True), self.RULES, due, stage="klaeren")["then"], "A7")
        self.assertIsNone(account.silence(self.acc(True), self.RULES, before, stage="klaeren"))
        self.assertIsNone(account.silence(self.acc(False), self.RULES, due, stage="klaeren"))  # the frozen study keeps its rule: the day after
        self.assertEqual(account.silence(self.acc(False), self.RULES, date(2025, 7, 11), stage="klaeren")["then"], "A7")


if __name__ == "__main__":
    unittest.main()

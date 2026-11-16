"""«Stand am» by code (casepath/quality/asof.py): the case as it stood on an earlier day, rebuilt from one stored run of the
whole file, evaluated by the case view's own path, against the way it was measured before: the file cut on that day and
prepared by the team again.

Scripted and model-free. tests/fixtures/replay/three_phases.json: a tenancy defect in three phases (the report and the
first request; the reply with the lease and photos, a phone note; a mandate and a fee note), what a reader records for
the whole file and for each cut. tests/fixtures/replay/reply_assessment.json: S-D11A, the shape of D11 from the claim to
the status inquiry, cut on each labelled point's day with the brief a reader writes from those pages alone."""
from datetime import date
import json
import re
import unittest
from unittest import mock

from casepath.process import account
from casepath.quality import asof
from tests import phased

MEASURED = ("action", "form", "title", "next_in_days", "follow_up", "stage", "outcome", "now", "offered", "later", "parts", "questions",
            "questions_offered", "hints", "lists_documents")


class SameAsACutTests(unittest.TestCase):
    """The same next action, the same first-request lines and the same follow-up date as a scripted run on the cut."""

    @classmethod
    def setUpClass(cls):
        cls.case = phased.load("three_phases")
        cls.desk = phased.Desk()
        cls.whole = cls.desk.prepare(cls.case)  # the team runs once, on all of it

    @classmethod
    def tearDownClass(cls):
        cls.desk.close()

    def compare(self, cut):
        decisions = [d for d in self.case["decisions"] if d["from"] <= cut["as_of"]]
        alone = self.desk.prepare(self.case, cut, cut["pages"], cut["as_of"], decisions)
        on_cut = asof.measure(asof.view(self.desk.store, self.desk.catalogue, alone))
        shown, rebuilt = asof.as_of_view(self.desk.store, self.desk.catalogue, self.whole, cut["as_of"], self.case["decisions"])
        return on_cut, asof.measure(shown), rebuilt

    def test_a_before_the_first_request_the_same_first_request(self):
        on_cut, rebuilt_view, rebuilt = self.compare(self.case["cuts"][0])
        self.assertEqual({k: rebuilt_view[k] for k in MEASURED}, {k: on_cut[k] for k in MEASURED})
        self.assertEqual((rebuilt_view["action"], rebuilt_view["follow_up"]), ("A1", "2025-02-26"))
        self.assertIn("mietvertrag", rebuilt_view["now"])
        self.assertIn(("dokumentieren", "established"), rebuilt_view["hints"])  # the first request's ticked hint

    def test_b_between_phase_1_and_2_the_same_next_action_lines_and_date(self):
        on_cut, rebuilt_view, rebuilt = self.compare(self.case["cuts"][1])
        self.assertEqual({k: rebuilt_view[k] for k in MEASURED}, {k: on_cut[k] for k in MEASURED})
        self.assertEqual((rebuilt_view["stage"], rebuilt_view["action"], rebuilt_view["follow_up"]), ("klaeren", "A6", "2025-03-08"))
        self.assertEqual(sorted(rebuilt_view["now"]), sorted(on_cut["now"]))
        self.assertEqual(rebuilt["limits"]["entries_kept"], 2)  # the report and the first request; the reply is later

    def test_c_between_phase_2_and_3_the_same_with_the_cover_decision_in_force(self):
        on_cut, rebuilt_view, rebuilt = self.compare(self.case["cuts"][2])
        self.assertEqual({k: rebuilt_view[k] for k in MEASURED}, {k: on_cut[k] for k in MEASURED})
        self.assertEqual((rebuilt_view["action"], rebuilt_view["next_in_days"], rebuilt_view["follow_up"]), ("A6", 25, "2025-03-30"))  # after the call
        self.assertNotIn("mietvertrag", rebuilt_view["now"])  # the lease came with the reply
        self.assertEqual([e["op"] for e in rebuilt["edits"]], ["set_fact"])  # cover from 26.02.; the way to proceed only from 14.03.

    def test_d_the_one_difference_is_named_a_yes_no_quoted_on_both_sides_of_the_day(self):
        """Allowed difference: will_beseitigung is read «ja» from the report and from the later mandate letter. A reading of the
        cut has only the report and settles it; the rebuild cannot tell from words which quote supports a yes or no, so it
        leaves the fact open and names it. It changes nothing measured on these days (no stage, need or letter line of the
        area depends on it); where it would, the diagnosis says so (``rebuild undecided``)."""
        for cut in self.case["cuts"]:
            shown, rebuilt = asof.as_of_view(self.desk.store, self.desk.catalogue, self.whole, cut["as_of"], self.case["decisions"])
            self.assertEqual(rebuilt["limits"]["undecided"], ["will_beseitigung"])
            self.assertIsNone(shown["state"]["facts"].get("will_beseitigung"))
            # the counterparty, quoted from the report and from the later lease, keeps its value: the report holds its words
            self.assertEqual(shown["state"]["facts"]["gegenpartei"], "Immo Seeblick AG")


class PrefixTests(unittest.TestCase):
    """True chronology where the future is out of reach: each cut of S-D11A prepared by the team from its own pages and the
    brief a reader writes from them, against the rebuild of the whole-file run on that day. What the replay scores
    (MEASURED) is equal on every cut. What the brief puts on the screen and in the letter (asof.surface: the parties, the
    summary, the customer's questions, the greeting, «In Ihrem Fall», the answers, the request, the firm's summary, the cover
    check's hint on the insured person, the customer's name) differs only where the whole file states more later: the
    request, which carries no quote. The count is fixed per cut; a change to the rebuild or the brief shows here first."""
    SURFACE_DIFFERS = [["summary", "im_fall", "anliegen", "zusammenfassung"], ["summary", "im_fall", "anliegen", "zusammenfassung"], [], []]

    @classmethod
    def setUpClass(cls):
        cls.case = phased.load("reply_assessment")
        cls.desk = phased.Desk()
        active = lambda: [(k["id"], k["version"]) for k in cls.desk.store.list_knowledge(statuses={"active"})]
        cls.knowledge = active()  # one Knowledge snapshot for both arms
        cls.whole = cls.desk.prepare(cls.case)
        cls.arms = []
        for cut in cls.case["cuts"]:
            decisions = [d for d in cls.case["decisions"] if d["from"] <= cut["as_of"]]
            alone = cls.desk.prepare(cls.case, cut, cut["pages"], cut["as_of"], decisions)
            on_cut = asof.view(cls.desk.store, cls.desk.catalogue, alone)
            shown, rebuilt = asof.as_of_view(cls.desk.store, cls.desk.catalogue, cls.whole, cut["as_of"], cls.case["decisions"])
            cls.arms.append((on_cut, shown, rebuilt))
        cls.knowledge_after = active()

    @classmethod
    def tearDownClass(cls):
        cls.desk.close()

    def differing(self, on_cut, shown):
        mine, theirs = asof.surface(on_cut, asof.letter(on_cut)), asof.surface(shown, asof.letter(shown))
        return [k for k in asof.SURFACE if mine[k] != theirs[k]]

    def test_a_each_cut_measures_the_same_and_its_surface_differs_by_a_fixed_count(self):
        self.assertEqual(self.knowledge_after, self.knowledge)
        for k, (on_cut, shown, rebuilt) in enumerate(self.arms):
            mine, theirs = asof.measure(on_cut), asof.measure(shown)
            same = [f for f in MEASURED if mine[f] == theirs[f]]
            differ = self.differing(on_cut, shown)
            print(f"cut {k} · measured {len(same)}/{len(MEASURED)} · surface {len(differ)}/{len(asof.SURFACE)}")
            self.assertEqual(same, list(MEASURED), [(f, mine[f], theirs[f]) for f in MEASURED if f not in same])
            self.assertEqual(differ, self.SURFACE_DIFFERS[k])
        self.assertEqual([asof.measure(shown)["action"] for _, shown, _ in self.arms], ["A1", "A6", "A5", "A7"])

    def test_b_a_party_named_only_later_is_dropped_and_counted_and_the_parties_then_agree(self):
        on_cut, shown, rebuilt = self.arms[0]
        self.assertEqual(rebuilt["limits"]["brief"]["parties_named_later"], 1)  # the shop of the receipt, named from the reply on
        self.assertEqual([i["value"] for i in shown["items"] if i["kind"] == "party"], [i["value"] for i in on_cut["items"] if i["kind"] == "party"])
        with mock.patch.object(asof, "named_in", lambda party, words: True):  # without the filter: one difference more
            unfiltered, _ = asof.as_of_view(self.desk.store, self.desk.catalogue, self.whole, self.case["cuts"][0]["as_of"], self.case["decisions"])
        self.assertEqual(self.differing(on_cut, unfiltered), ["parties"] + self.SURFACE_DIFFERS[0])
        self.assertEqual([self.arms[k][2]["limits"]["brief"]["parties_named_later"] for k in range(4)], [1, 0, 0, 0])

    def test_c_what_reaches_the_day_from_the_whole_file_is_counted_as_exposure(self):
        brief = [rebuilt["limits"]["brief"] for _, _, rebuilt in self.arms]
        self.assertEqual([b["request_uncited"] for b in brief], [1, 1, 1, 1])  # the request carries no quote
        self.assertEqual([b["form_renders_brief"] for b in brief], [0, 0, 1, 0])  # the assessment writes the request and the answers
        self.assertEqual([b["knowledge_from_same_case"] + b["agent_edits_applied"] for b in brief], [0, 0, 0, 0])
        questions = [len([i for i in shown["items"] if i["kind"] == "customer_question"]) for _, shown, _ in self.arms]
        self.assertEqual(questions, [0, 0, 3, 3])  # the questions keep their quotes: none before the replies

    def test_d_the_surface_is_content_free(self):
        on_cut, shown, _ = self.arms[2]
        surface = asof.surface(shown, asof.letter(shown))
        self.assertEqual(surface["counts"], {"parties": 3, "questions": 3})
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{12}", surface[k]) for k in asof.SURFACE))
        text = json.dumps(surface, ensure_ascii=False)
        self.assertFalse([w for w in ("Steiner", "Sonnmatt", "Stromkosten", "Miete") if w in text])


def entry(n, page, day, sender, to, kind="andere", phone=False):
    return {"n": n, "file": "f", "page": page, "date": day, "from": sender, "to": to, "kind": kind, "phone": phone, "what": "",
            "citations": [{"file": "f", "page": page, "quote": "x"}], "asks": [], "answers": [], "terms": [], "paid": [], "next": []}


def file_of(pages, segments):
    return {"id": "f", "name": "Akte.pdf", "case_id": "c", "extraction": {"text": "\n\n".join(f"[page {n}]\nSeite {n}" for n in range(1, pages + 1)),
                                                                          "pages": pages, "segments": segments}}


class RuleTests(unittest.TestCase):
    """Which pages, entries, facts and documents a day keeps."""

    def test_an_enclosure_is_known_from_the_letter_it_came_with_and_a_later_letter_is_never_dated_back(self):
        segments = [{"first_page": 1, "last_page": 1, "date": None},  # an undated cover sheet before the first entry
                    {"first_page": 2, "last_page": 2, "date": "10.01.2025", "sender": "Kundin"},
                    {"first_page": 3, "last_page": 3, "date": "01.04.2021", "sender": "Vermieterin"},  # a lease enclosed in the e-mail
                    {"first_page": 4, "last_page": 4, "date": "20.03.2025", "sender": "Vermieterin"},  # a letter the reader gave no entry
                    {"first_page": 5, "last_page": 5, "date": None},  # an undated page after it
                    {"first_page": 6, "last_page": 6, "date": "02.04.2025", "sender": "Protekta Rechtsschutz"}]
        dating = asof.Dating([file_of(6, segments)], [entry(1, 2, "2025-01-10", "kunde", "versicherer"), entry(2, 6, "2025-04-02", "versicherer", "kunde")])
        kept = lambda t: dating.kept_pages("f", date.fromisoformat(t))
        self.assertEqual(kept("2025-01-10"), [2, 3])  # the cover sheet: the later of its dated neighbours, strictly before
        self.assertEqual(dating.how["f"][1], "neighbours")
        self.assertEqual(kept("2025-02-01"), [1, 2, 3])  # the lease with its e-mail, though dated 2021
        self.assertEqual(kept("2025-03-20"), [1, 2, 3, 4, 5])  # the unrecorded letter and the page after it, from its own day
        self.assertEqual(kept("2025-03-19"), [1, 2, 3])
        self.assertEqual(kept("2025-04-02"), [1, 2, 3, 4, 5])  # the insurer's own letter of the day is the step measured
        self.assertEqual(kept("2025-04-03"), [1, 2, 3, 4, 5, 6])
        dating = asof.Dating([file_of(2, [{"first_page": 1, "last_page": 2, "date": "05.05.2025", "sender": "Gegenpartei"}])], [])
        self.assertEqual(dating.kept_pages("f", date(2025, 5, 5)), [1, 2])  # another party's document of the day is known

    def test_facts_keep_the_earlier_quotes_and_the_value_they_state_else_they_are_open_and_named(self):
        graph = {"facts": [{"id": "frist", "type": "date"}, {"id": "gegenpartei", "type": "text"}, {"id": "schriftlich", "type": "boolean"},
                           {"id": "seit", "type": "date"}, {"id": "eingang_zahlung", "type": "text"}],
                 "incoming": [{"id": "zahlung", "fact": "eingang_zahlung"}]}
        cite = lambda page, quote: {"file": "f", "page": page, "quote": quote}
        fact = lambda f, v, *c: {"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": list(c)}
        result = {"process": graph, "documents": [], "facts": [
            fact("frist", "2025-02-28", cite(1, "bis 28. Februar 2025"), cite(3, "Frist läuft")),
            fact("gegenpartei", "Immo AG", cite(1, "Die Immo AG antwortet nicht"), cite(3, "Vermieterin Immo AG")),
            fact("schriftlich", True, cite(1, "schriftlich gemeldet"), cite(3, "Einschreiben vom")),
            fact("seit", "2024-11", cite(3, "seit November 2024")),
            fact("eingang_zahlung", "Immo AG: Zahlung vom 2025-01-20 über CHF 500", cite(1, "CHF 500 erhalten"), cite(3, "Zahlung bestätigt"))]}
        files = [file_of(3, [{"first_page": 1, "last_page": 1, "date": "25.01.2025", "sender": "Kundin"},
                             {"first_page": 2, "last_page": 3, "date": "15.03.2025", "sender": "Kundin"}])]
        rebuilt = asof.rebuild({"id": "r", "result": result}, files, "2025-02-01")
        kept = {f["fact"]: f for f in rebuilt["run"]["result"]["facts"]}
        self.assertEqual(kept["frist"]["value"], "2025-02-28")  # the earlier quote names the date
        self.assertEqual([c["page"] for c in kept["frist"]["citations"]], [1])
        self.assertEqual(kept["gegenpartei"]["value"], "Immo AG")  # its words are in the earlier quote
        self.assertEqual(kept["eingang_zahlung"]["value"], "Immo AG: Zahlung vom 2025-01-20 über CHF 500")  # an item dated before the day
        self.assertNotIn("schriftlich", kept)  # a yes/no cannot be decided from words
        self.assertNotIn("seit", kept)  # quoted only later
        self.assertEqual((rebuilt["limits"]["undecided"], rebuilt["limits"]["later_only"]), (["schriftlich"], ["seit"]))
        self.assertEqual(rebuilt["files"][0]["extraction"]["kept_pages"], [1])
        self.assertEqual(rebuilt["files"][0]["extraction"]["cut_of"]["as_of"], "2025-02-01")  # the clock counts from the day

    def test_a_found_document_needs_a_known_page_and_the_account_keeps_what_was_known(self):
        segments = [{"first_page": 1, "last_page": 1, "date": "10.01.2025"}, {"first_page": 2, "last_page": 2, "date": "12.02.2025"}]
        ask = {"what": "Mietvertrag", "of": "kunde", "by": "2025-01-31", "repeats": None, "warns": False,
               "citations": [{"file": "f", "page": 1, "quote": "Mietvertrag bis 31.01.2025"}]}
        answer = {"what": "Mietvertrag", "answers": 1, "citations": [{"file": "f", "page": 2, "quote": "anbei der Mietvertrag"}]}
        result = {"process": {"facts": []}, "facts": [], "record": {"entries": [
            {**entry(1, 1, "2025-01-10", "versicherer", "kunde", "anforderung"), "asks": [ask]},
            {**entry(2, 2, "2025-02-12", "kunde", "versicherer", "unterlagen"), "answers": [answer]}]},
            "documents": [{"document": "mietvertrag", "status": "present", "verdict": "accepted", "files": ["f"],
                           "citations": [{"file": "f", "page": 2, "quote": "Mietvertrag"}]}]}
        early = asof.rebuild({"id": "r", "result": result}, [file_of(2, segments)], "2025-02-01")["run"]["result"]
        self.assertEqual([(d["document"], d["status"], d["verdict"]) for d in early["documents"]], [("mietvertrag", "missing", "not_checked")])
        ledger = account.build(early["record"]["entries"])
        self.assertEqual([(r["what"], r["answered"]) for r in ledger["requests"]], [("Mietvertrag", None)])  # asked, not yet answered
        later = asof.rebuild({"id": "r", "result": result}, [file_of(2, segments)], "2025-02-12")["run"]["result"]
        self.assertEqual(later["documents"][0]["status"], "present")
        self.assertEqual(account.build(later["record"]["entries"])["requests"][0]["answered"]["n"], 2)

    def test_the_handlers_decisions_hold_from_their_day_and_the_latest_of_a_fact_governs(self):
        decisions = [{"fact": "deckung", "value": "offen", "from": "2025-01-05"}, {"fact": "deckung", "value": "bestätigt", "from": "2025-02-01"},
                     {"fact": "vorgehen", "value": "Selbst führen", "from": "2025-03-01"}]
        edits = asof.decisions_on(decisions, date(2025, 2, 1))
        self.assertEqual([(e["args"]["fact"], e["args"]["value"]) for e in edits], [("deckung", "offen"), ("deckung", "bestätigt")])
        self.assertEqual(asof.decisions_on(decisions, date(2025, 1, 4)), [])


if __name__ == "__main__":
    unittest.main()

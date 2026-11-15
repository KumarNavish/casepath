"""What the product decides, as rules in data, each with a scripted case (process 2026-11-16.1):

1. the most urgent thing leads: a deadline the customer must meet, ending within the backbone's threshold, makes «Frist
   wahren» (A13) the prepared action, its letter saying what to do by when and where, the customer's own template
   attached and prefilled, the first request after it; never for a deadline whose condition fails, never for one passed;
2. one truth: the documents still missing, the deadlines and the next step are decided once for every tab and the list;
   a document the running account shows delivered is in the file;
3. deadlines: one depending on an open fact is shown once, compactly, never leads and is never stated in a letter;
4. customer-facing text: no rule's condition, no title in quotation marks, no «nach unserer Berechnung», no code, id,
   ISO date or placeholder the file could fill, in any form or template of any area's example;
5. roles and decisions: the mandate names the other side by its role, never the firm; no role twice; a decision the stage
   settles is not asked; the cover decision never at intake; the fee note has three answers; the payout one progress line.
And two faults found on a real file: a letter to the customer lists only what the insurer or the mandated firm asked (never
the other side's claim against the customer), and a run stored before ``by_date`` shows its open dates from the words.
The case screen says each thing once: an open request with its date in «Als Nächstes», not again under «Fristen»; a
passed statutory deadline behind the process does not lead; what goes out is tabs named by whom it goes to. Model-free."""
import json
import re
import unittest
from datetime import date
from pathlib import Path

from casepath.agents import core
from casepath.process import account, area, cover, customer_letters, letters, screen, urgent
from casepath.process.items import build_items
from casepath.web import listing

CASES = json.loads((Path(__file__).parent / "fixtures" / "areas" / "cases.json").read_text())
CASE = {"id": "case_r", "title": "Strafbefehl (synthetisch) 1111.2222.3333", "intake": {}}
TRAFFIC = [("rechtsgebiet", "Strafrecht, Ausweisentzug / Strassenverkehr"), ("strafbefehl", True), ("strafbefehl_erhalten", "2026-11-06"),
           ("vorwurf", "Geschwindigkeitsüberschreitung von 32 km/h"), ("entzug_verfahren", True), ("beruflich", True)]


def view(wid, facts, as_of, events=(), parties=None, decided=(), entries=None, documents=()):
    """A case as the screen builds it, looked at on ``as_of``: (state, items, items by id, files)."""
    rows = [{"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": [{"file": "f1", "page": 1, "quote": f"zu {f}"}]}
            for f, v in facts]
    files = [{"id": "f1", "name": "Akte.pdf", "extraction": {"cut_of": {"as_of": as_of}, "text": "[page 1]\nAkte", "segments": []}}]
    result = {"facts": rows, "documents": list(documents),
              "brief": {"request": "Der Kunde wehrt sich gegen einen Strafbefehl.", "timeline": [],
                        "parties": parties if parties is not None else [{"role": "Kundschaft (VN)", "name": "Lukas Beispiel"}]}}
    if entries is not None:
        result["record"] = {"entries": entries, "dropped": 0}
    edits = [{"id": f"e{i}", "op": "set_fact", "args": {"fact": k, "value": v}, "status": "active"} for i, (k, v) in enumerate(decided)]
    state = {**core.evaluate(area.workflow(wid), [], edits, result, "case_r", files=files), "case": {"id": "case_r", "created_at": f"{as_of}T08:00:00"}}
    items = build_items(state, result, files, list(events))
    return state, items, {i["item_id"]: i for i in items}, files


def draft(state, items, files, kind, events=()):
    ctx = letters.context(CASE, items, list(events), {"due": "2026-12-05"}, files, evaluation=state["evaluation"], process=state["process"])
    return letters.render(kind, state["process"]["forms"], ctx)


INTERNAL = [("code", r"\bA(?:1[0-3]|[0-9])\b"), ("ISO date", r"\b\d{4}-\d{2}-\d{2}\b"), ("placeholder", r"\{[a-z_]+\}"),
            ("id", r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{8}\b"), ("rule", r"nach unserer Berechnung|\(nur bei|solange keine")]


def internal(text, titles=()):
    hits = [f"{name}: {m.group(0)}" for name, pattern in INTERNAL for m in re.finditer(pattern, text or "")]
    return hits + [f"title in quotes: {t}" for t in titles if t and f"«{t}»" in (text or "")]


class FristWahrenTests(unittest.TestCase):
    def test_a_penalty_order_with_one_day_left_is_frist_wahren_with_the_objection_attached(self):
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-15")
        act = listed["next_action:0"]
        self.assertEqual((act["action"], act["value"], act["deadline"], act["urgency"]), ("A13", "Frist wahren", "deadline:einsprache_strafbefehl", "dringend"))
        self.assertEqual([(t["code"], t["action"]) for t in act["then"]], [("A1", "Unterlagen und Angaben anfordern")])  # «danach»
        self.assertEqual(act["reason"], "Ohne gültige Einsprache wird der Strafbefehl zum rechtskräftigen Urteil")
        self.assertIsNone(listed["deadline:einsprache_strafbefehl"].get("condition"))  # a step the file does not show is not taken
        text, none = draft(state, items, files, "A13")
        self.assertIsNone(none)
        for part in ("Die Frist für die Einsprache gegen den Strafbefehl endet am 16.11.2026.",
                     "Erheben Sie die Einsprache schriftlich bei der Staatsanwaltschaft, die den Strafbefehl erlassen hat (Art. 354 Abs. 1 StPO).",
                     "Eine Begründung ist nicht nötig (Art. 354 Abs. 2 StPO).", "der Schweizerischen Post übergeben (Art. 91 Abs. 2 StPO).",
                     "Ohne gültige Einsprache wird der Strafbefehl zum rechtskräftigen Urteil (Art. 354 Abs. 3 StPO). Wenn Sie jetzt handeln, wahren Sie Ihre Rechte.",
                     "Für Ihr Schreiben an die Staatsanwaltschaft legen wir Ihnen eine Vorlage bei", "Die Versicherungsdeckung prüfen wir parallel.",
                     "provisorisch registriert", "Welche Unterlagen wir für die Prüfung noch brauchen, teilen wir Ihnen separat mit."):
            self.assertIn(part, text)
        self.assertEqual(internal(text, [listed["deadline:einsprache_strafbefehl"]["label"]["de"]]), [])
        template = customer_letters.with_letter(items, [], "A13")
        self.assertEqual([t["key"] for t in template], ["einsprache"])
        body = template[0]["text"]
        self.assertIn("Am 06.11.2026 habe ich Ihren Strafbefehl", body)  # prefilled from the file
        self.assertIn("Staatsanwaltschaft\n[einsetzen: Adresse]", body)  # to the authority, never to the other side
        self.assertIn("spätestens am 16.11.2026 (Art. 91 Abs. 2 StPO)", body)
        self.assertNotIn("[einsetzen: Ihr Vor- und Nachname]", body)  # the customer's name is in the file
        self.assertEqual(listing.stand(closed=False, run_status="completed", new_files=0, items=items, follow_up=None, events=[], completed_at=None,
                                       files=files)["text"], "dringend")

    def test_the_threshold_is_data_and_ten_days_out_it_is_still_the_first_request(self):
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-05")  # 11 days before the deadline
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        wf = area.workflow("verkehr")
        self.assertEqual((wf["urgent"]["days"], wf["urgent"]["dringend"], wf["urgent"]["kind"]), (10, 3, "A13"))
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-06")  # ten days left: «Frist», not yet «dringend»
        self.assertEqual((listed["next_action:0"]["action"], listed["next_action:0"]["urgency"]), ("A13", "Frist"))

    def test_never_for_a_deadline_whose_condition_fails_nor_for_one_passed(self):
        filed = TRAFFIC + [("einsprache_erhoben", True)]
        state, items, listed, _ = view("verkehr", filed, "2026-11-15")
        self.assertNotIn("deadline:einsprache_strafbefehl", listed)  # established as not met: shown nowhere
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-18")  # passed
        self.assertEqual(listed["next_action:0"]["action"], "A1")
        lead = screen.lead(items, date(2026, 11, 18), area.workflow("verkehr")["urgent"])
        self.assertEqual((lead["date"], lead["word"]), ("16.11.2026", "abgelaufen"))  # the card says it passed

    def test_done_once_its_letter_and_the_template_went_out_then_the_first_request(self):
        copied = [{"kind": "letter.copied", "form": "A13", "deadline": "deadline:einsprache_strafbefehl"}]
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-15", events=copied)
        self.assertEqual(listed["next_action:0"]["action"], "A13")  # the template has not gone out yet
        both = copied + [{"kind": "letter.copied", "also": "vorlage:einsprache", "deadline": "deadline:einsprache_strafbefehl"}]
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-15", events=both)
        self.assertEqual(listed["next_action:0"]["action"], "A1")

    def test_not_at_the_mandate_stage_and_not_for_the_other_sides_obligation(self):
        loan = [("rechtsgebiet", "Vertragsrecht / Darlehen"), ("termin_vereinbart", False), ("aufforderung", "2026-10-05")]  # repayment 16.11.
        state, items, listed, _ = view("vertrag-darlehen", loan, "2026-11-15")
        self.assertEqual(listed["deadline:rueckzahlung"]["party"], "gegenpartei")
        self.assertNotEqual(listed["next_action:0"]["action"], "A13")
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-15", decided=[("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")])
        self.assertEqual(listed["next_action:0"]["action"], "A10")  # the firm keeps the deadline under its mandate

    def test_a_conciliation_request_goes_with_the_rent_increase_and_the_termination(self):
        for wid, facts, key in (("miete-mietzinserhoehung", [("rechtsgebiet", "Mietrecht / Mietzinserhöhung"), ("erhoehung_erhalten", "2026-10-22")], "anfechtung"),
                                ("miete-kuendigung", [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-10-19")], "anfechtung")):
            state, items, listed, files = view(wid, facts, "2026-11-15")
            self.assertEqual(listed["next_action:0"]["action"], "A13", wid)
            template = customer_letters.with_letter(items, [], "A13")
            self.assertEqual([t["key"] for t in template], [key], wid)
            self.assertIn("Schlichtungsbehörde für Mietsachen", template[0]["text"])
            self.assertIn("Rechtsbegehren:", template[0]["text"])
            text, _ = draft(state, items, files, "A13")
            self.assertIn("Schlichtungsgesuch", text)
            self.assertEqual(internal(text), [], wid)


class OneTruthTests(unittest.TestCase):
    def test_one_count_of_missing_documents_and_the_handlers_tick_counts(self):
        state, items, listed, files = view("verkehr", TRAFFIC, "2026-11-01")
        asked = screen.missing(items, [])
        self.assertEqual(len(asked), len([i for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present" and not i.get("part_of")]))
        unticked = [{"kind": "letter.line", "item_id": asked[0]["item_id"], "included": False}]
        self.assertEqual(len(screen.missing(items, unticked)), len(asked) - 1)
        text, _ = draft(state, items, files, "A1", unticked)
        self.assertEqual(sum(1 for i in screen.missing(items, unticked) if f"– {i['label']['de']}" in text), len(asked) - 1)

    def test_a_document_the_account_shows_delivered_is_present(self):
        entries = [{"n": 1, "file": "f1", "page": 1, "date": "2025-01-14", "from": "versicherer", "to": "kunde", "kind": "anforderung", "phone": False,
                    "what": "Anforderung", "citations": [{"file": "f1", "page": 1, "quote": "Bitte senden"}],
                    "asks": [{"what": "Mietvertrag und Mängelrüge", "of": "kunde", "by": "2025-02-04", "repeats": None, "warns": False,
                              "citations": [{"file": "f1", "page": 1, "quote": "Bitte senden"}]}], "answers": [], "terms": [], "paid": [], "next": []},
                   {"n": 2, "file": "f1", "page": 1, "date": "2025-02-19", "from": "kunde", "to": "versicherer", "kind": "unterlagen", "phone": False,
                    "what": "Unterlagen", "citations": [{"file": "f1", "page": 1, "quote": "im Anhang"}], "asks": [], "terms": [], "paid": [], "next": [],
                    "answers": [{"what": "Mietvertrag und Mängelrüge vom 3. Dezember 2024", "answers": 1, "citations": [{"file": "f1", "page": 1, "quote": "im Anhang"}]}]}]
        state, items, listed, _ = view("mietmangel-handler", [("rechtsgebiet", "Mietrecht / Mangel")], "2025-03-01", entries=entries)
        for need in ("mietvertrag", "maengelruege"):
            self.assertEqual(listed[f"document:{need}"]["status"], "present", need)
            self.assertIsNone(listed[f"document:{need}"]["ask"], need)
        self.assertNotIn("mietvertrag", [i["key"] for i in screen.missing(items, [])])


class DeadlineTests(unittest.TestCase):
    def test_an_open_condition_shows_once_compactly_never_leads_and_is_never_in_the_letter(self):
        facts = [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-11-03")]  # befristet open: Erstreckung «nur bei …»
        state, items, listed, files = view("miete-kuendigung", facts, "2026-11-14")
        row = listed["deadline:erstreckung"]
        self.assertEqual(row["condition"], "nur bei unbefristetem Mietverhältnis")
        rows = screen.fristen(items, date(2026, 11, 14))
        shown = [p for r in rows for p in r.get("parts") or [r] if p["item_id"] == "deadline:erstreckung"]
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["condition"], "nur bei unbefristetem Mietverhältnis")
        same_day = next(r for r in rows if "deadline:erstreckung" in r.get("also", []))  # ending the day the contest ends: one row, the date once
        self.assertEqual((same_day["item_id"], same_day["date"]), ("deadline:anfechtung", "03.12.2026"))
        self.assertIn("nur bei unbefristetem Mietverhältnis: Erstreckungsbegehren bei einem unbefristeten Mietverhältnis", same_day["title"])
        lead = screen.lead(items, date(2026, 11, 14), state["process"]["urgent"])
        self.assertEqual(lead["item_id"], "deadline:anfechtung")  # never the conditional one
        text, _ = draft(state, items, files, "A1")
        self.assertNotIn("Erstreckungsbegehren bei einem unbefristeten Mietverhältnis", text)  # the deadline is not stated
        self.assertNotIn("nur bei", text)
        self.assertIn("– Möchten Sie eine Erstreckung des Mietverhältnisses verlangen", text)  # the question that settles it is asked

    def test_the_lead_is_the_customers_or_ours_within_thirty_days_or_passed(self):
        facts = [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-09-01"), ("befristet", False)]
        state, items, listed, _ = view("miete-kuendigung", facts, "2026-11-14")
        lead = screen.lead(items, date(2026, 11, 14), state["process"]["urgent"])
        self.assertEqual((lead["word"], lead["kind"]), ("abgelaufen", "Frist"))
        far = [("rechtsgebiet", "Vertragsrecht / Kauf mit Mangel"), ("ablieferung", "2026-09-20")]  # two years: no lead within 30 days
        state, items, listed, _ = view("vertrag-kauf", far, "2026-11-14")
        self.assertIsNone(screen.lead(items, date(2026, 11, 14), state["process"]["urgent"]))

    def test_a_run_stored_before_by_date_shows_its_open_dates_from_the_words(self):
        """Fault 2: a reply date in a settlement proposal and a period the firm set, kept only as words."""
        cite = [{"file": "f1", "page": 1, "quote": "x"}]
        entries = [{"n": 1, "file": "f1", "page": 1, "date": "2025-03-03", "from": "kanzlei", "to": "kunde", "kind": "anforderung", "phone": False,
                    "what": "Belege verlangt", "citations": cite, "answers": [], "terms": [], "paid": [], "next": [],
                    "asks": [{"what": "Belege der Reparaturkosten", "of": "kunde", "by": "innert 14 Tagen", "repeats": None, "warns": False, "citations": cite}]},
                   {"n": 2, "file": "f1", "page": 1, "date": "2025-03-10", "from": "gegenpartei", "to": "kanzlei", "kind": "angebot", "phone": False,
                    "what": "Vergleichsvorschlag", "citations": cite, "asks": [], "answers": [], "paid": [], "next": [],
                    "terms": [{"what": "Vergleich", "amount": "CHF 800", "payer": "gegenpartei", "by": "30. April 2025", "agreed": False, "citations": cite}]},
                   {"n": 3, "file": "f1", "page": 1, "date": "2025-03-12", "from": "kanzlei", "to": "kunde", "kind": "anforderung", "phone": False,
                    "what": "Rückfrage", "citations": cite, "answers": [], "terms": [], "paid": [], "next": [],
                    "asks": [{"what": "Stellungnahme zum Vergleich", "of": "kunde", "by": "nach Rücksprache mit der Familie", "repeats": None, "warns": False, "citations": cite}]}]
        state, items, listed, _ = view("mietmangel-handler", [("rechtsgebiet", "Mietrecht / Mangel")], "2025-03-20", entries=entries)
        dated = {i["label"]["de"]: (i["value"], i.get("stated_as"), i.get("due_text")) for i in items if i["kind"] == "deadline" and i.get("account")}
        self.assertEqual(dated["Belege der Reparaturkosten"][:2], ("2025-03-17", "computed"))  # counted from the entry's date, marked
        self.assertEqual(dated["Antwort auf das Angebot: Gegenpartei zahlt CHF 800 (Vergleich)"][0], "2025-04-30")  # a written date as such
        self.assertEqual(dated["Stellungnahme zum Vergleich"], ("prüfen", "possible", "Frist laut Akte, Datum prüfen"))
        rows = screen.fristen(items, date(2025, 3, 20))
        self.assertTrue(rows)  # never «keine Frist gefunden» while the account holds open dates
        self.assertIn("Frist laut Akte, Datum prüfen", [r["state"] for r in rows])


class CustomerTextTests(unittest.TestCase):
    def test_every_form_and_template_of_every_areas_example_is_free_of_internal_words(self):
        for wid, case in CASES.items():
            if wid.startswith("_"):
                continue
            facts = [(f, {"ja": True, "nein": False}.get(v, v)) for f, v, _ in case["facts"]] + ([("rechtsgebiet", case["routing"][0])] if case["routing"] else [])
            state, items, listed, files = view(wid, facts, "2026-11-15", parties=[{"role": "Kundschaft (VN)", "name": "Anna Beispiel"}])
            titles = [i["label"]["de"] for i in items if i["kind"] in ("deadline", "key_point")]
            ctx = letters.context(CASE, items, [], {"due": "2026-12-05"}, files, evaluation=state["evaluation"], process=state["process"])
            for kind, form in state["process"]["forms"].items():
                if kind.startswith("_") or form.get("none"):
                    continue
                text, _ = letters.render(kind, state["process"]["forms"], ctx)
                with self.subTest(area=wid, form=kind):
                    self.assertEqual(internal(text, titles), [])
            for t in [i for i in items if i["kind"] == "customer_letter"]:
                with self.subTest(area=wid, template=t["key"]):
                    self.assertEqual(internal(t["text"], titles), [])
                    stated = {k for k, v in (state["facts"] or {}).items() if v not in (None, "")}
                    row = next(c for c in state["process"]["customer_letters"] if c["id"] == t["key"])
                    for fact_id, words in (row.get("fill") or {}).items():
                        if fact_id in stated:  # what the file states is filled in, never left as a gap
                            self.assertNotIn(f"[einsetzen: {words}]", t["text"])
            self.assertEqual(internal(ctx["hinweise"], titles), [], wid)


class RoleAndDecisionTests(unittest.TestCase):
    PARTIES = [{"role": "Mieterin (VN)", "name": "Frau Lea Beispiel"}, {"role": "beauftragte Kanzlei", "name": "Kanzlei Muster"}]

    def test_the_mandate_names_the_other_side_by_its_role_never_the_firm(self):
        facts = [("rechtsgebiet", "Mietrecht / Mangel")]
        state, items, listed, files = view("mietmangel-handler", facts, "2026-11-14", parties=self.PARTIES + [{"role": "Verwaltung (GP)", "name": "Muster Immobilien AG"}],
                                           decided=[("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")])
        text, _ = draft(state, items, files, "A10")
        self.assertIn("Kundschaft: Frau Lea Beispiel (Mieterin)\nGegenpartei: Muster Immobilien AG (Verwaltung)", text)
        self.assertNotIn("(VN))", text)
        state, items, listed, files = view("mietmangel-handler", facts, "2026-11-14", parties=self.PARTIES,
                                           decided=[("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")])
        text, _ = draft(state, items, files, "A10")
        self.assertNotIn("Gegenpartei: Kanzlei Muster", text)
        self.assertIn("Gegenpartei: [bitte ergänzen: Gegenpartei]", text)  # the file names no other side: a gap, never the firm

    def test_the_cover_decision_is_never_asked_at_intake_and_never_once_the_stage_settles_it(self):
        state, items, listed, _ = view("verkehr", TRAFFIC, "2026-11-01")
        stage = state["evaluation"]["current"]["step"]
        self.assertEqual(stage, "klaeren")
        self.assertIsNone(screen.decision(items, {"needs": []}, stage))
        self.assertIsNone(screen.cover_line(items, stage))
        self.assertIsNone(screen.decision(items, {"needs": ["deckung", "vorgehen"]}, "mandat"))  # settled by the mandate
        self.assertEqual(screen.cover_line(items, "mandat")["text"], "mit dem Vorgehen gegeben")

    def test_at_the_assessment_the_cover_then_the_prospects_are_the_one_decision(self):
        facts = [("rechtsgebiet", "Arbeitsrecht / Kündigung"), ("kuendigung_erhalten", "2026-11-04"), ("arbeitsende", "2027-01-31")]
        history = [("handlung_a1", "2026-11-05"), ("kunde_geantwortet", True)]
        state, items, listed, _ = view("arbeit-kuendigung", facts + history, "2026-11-14")
        if state["evaluation"]["current"]["step"] != "beurteilen":
            state, items, listed, _ = view("arbeit-kuendigung", facts, "2026-11-14", decided=[("weiteres_gewuenscht", True)])
        stage = state["evaluation"]["current"]["step"]
        decided = screen.decision(items, {"needs": ["deckung"]}, "beurteilen")
        self.assertEqual((decided["key"], [a["label"] for a in decided["answers"]]), ("deckung", ["bestätigen", "ablehnen"]))
        self.assertIsNotNone(stage)

    def test_the_fee_note_has_three_answers(self):
        items = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A11", "form": "A11_kosten", "incoming": {"date": "2026-11-05"}}]
        decided = screen.decision(items, {"form": "A11_kosten", "needs": []}, "mandat")
        self.assertEqual([a["label"] for a in decided["answers"]], ["Zahlung freigeben", "Rückfrage", "Teilweise ablehnen"])
        self.assertEqual((decided["answers"][0]["decide"], decided["answers"][0]["value"]), ("eingang_erledigt_bis", "2026-11-05"))
        self.assertEqual([a.get("document") for a in decided["answers"][1:]], ["A11_rueckfrage", "A11_teilablehnung"])

    def test_the_payout_is_one_progress_line(self):
        items = [{"kind": "next_action", "key": "0", "item_id": "next_action:0", "action": "A11", "owed": {"amount": "CHF 3'000"},
                  "settlement": {"step": "einigung", "done": [], "terms": True, "iban": True}}]
        line = " · ".join(("✓ " if s["state"] == "done" else "● " if s["state"] == "now" else "○ ") + s["label"] for s in screen.progress(items))
        self.assertEqual(line, "✓ Einigung · ✓ Bankverbindung · ● Auszahlung nachfragen · ○ Eingang · ○ Abschluss")


class WhoAsksWhomTests(unittest.TestCase):
    """Fault 1: a demand of the other side against the customer is never something the customer owes the insurer."""

    def test_the_written_demand_lists_only_what_the_insurer_or_the_firm_asked(self):
        cite = [{"file": "f1", "page": 1, "quote": "x"}]
        base = {"file": "f1", "page": 1, "phone": False, "citations": cite, "answers": [], "terms": [], "paid": [], "next": []}
        entries = [{**base, "n": 1, "date": "2025-01-10", "from": "versicherer", "to": "kunde", "kind": "anforderung", "what": "Anforderung",
                    "asks": [{"what": "Belege der Reparaturkosten", "of": "kunde", "by": "2025-01-31", "repeats": None, "warns": False, "citations": cite}]},
                   {**base, "n": 2, "date": "2025-01-20", "from": "gegenpartei", "to": "kunde", "kind": "anforderung", "what": "Forderung der Vermieterin",
                    "asks": [{"what": "Schadenersatz und Entfernungskosten", "of": "kunde", "by": "2025-02-10", "repeats": None, "warns": False, "citations": cite}]},
                   {**base, "n": 3, "date": "2025-02-14", "from": "versicherer", "to": "kunde", "kind": "mahnung", "what": "Mahnung",
                    "asks": [{"what": "Belege der Reparaturkosten", "of": "kunde", "by": "2025-02-28", "repeats": 1, "warns": False, "citations": cite}]}]
        acc = account.build(entries, area.workflow("mietmangel-handler"))
        self.assertEqual([r["what"] for r in account.open_items(acc, "kunde", account.OWED_TO_US)], ["Belege der Reparaturkosten"])
        stand = {line["label"]: line["text"] for line in account.stand(acc, date(2025, 3, 20), area.workflow("mietmangel-handler"))}
        self.assertNotIn("Schadenersatz", stand["Offen bei der Kundschaft"])
        self.assertIn("Schadenersatz und Entfernungskosten", stand["Forderung der Gegenpartei"])
        # every list a letter takes from the ledger: the check before an ending holds everything open at the customer, and the
        # letters take only what the insurer or the firm asked
        held = [{"kind": "check", "key": "androhung", "item_id": "check:androhung", "open_requests": account.open_items(acc, "kunde")}]
        self.assertEqual(cover.missing_lines(held, fallback=False), ["– Belege der Reparaturkosten (erstmals verlangt am 10.01.2025)"])
        self.assertEqual(cover.missing_lines(held, "versicherer", fallback=False), ["– Belege der Reparaturkosten (erstmals verlangt am 10.01.2025)"])
        self.assertEqual(cover.missing_lines(held, "gegenpartei", fallback=False), [])  # never the other side's, whoever asks for it
        ctx = letters.context(CASE, held, [], {"due": "2025-05-01"})
        for key in ("vorenthalten", "verlangt", "androhung_anlass"):
            self.assertNotIn("Schadenersatz", ctx[key], key)
        self.assertIn("Belege der Reparaturkosten", ctx["vorenthalten"])


class ScreenTests(unittest.TestCase):
    """The case screen says each thing once (process/screen.py), in the case list's words."""

    def test_an_open_request_carries_its_date_and_is_not_a_second_deadline_line(self):
        rows = [{"text": "Mietvertrag · seit 03.11.2026 · 1× verlangt", "request": "r1", "evidence": []},
                {"text": "Fotos · seit 04.11.2026 · 1× verlangt", "request": "r2", "evidence": []}]
        items = [{"item_id": "stand:offen_kunde", "kind": "stand", "key": "offen_kunde", "label": {"de": "Offen bei der Kundschaft"}, "open": True,
                  "party": "kunde", "more": 0, "evidence": [], "rows": rows},
                 {"item_id": "deadline:konto-r1", "kind": "deadline", "key": "konto-r1", "account": True, "party": "kunde", "value": "2026-11-20",
                  "label": {"de": "Mietvertrag"}, "set_by": "versicherer"},
                 {"item_id": "deadline:konto-r2", "kind": "deadline", "key": "konto-r2", "account": True, "party": "kunde", "value": "2026-11-10",
                  "label": {"de": "Fotos"}, "set_by": "versicherer"}]
        lines, carried = screen.account_lines(items, date(2026, 11, 15), {}, set())
        self.assertEqual([r["text"] for r in lines[0]["rows"]], ["Mietvertrag · seit 03.11.2026 · 1× verlangt · bis 20.11.2026",
                                                                 "Fotos · seit 04.11.2026 · 1× verlangt · bis 10.11.2026 (abgelaufen)"])
        self.assertEqual(carried, {"deadline:konto-r1", "deadline:konto-r2"})
        self.assertEqual(screen.fristen(items, date(2026, 11, 15), carried), [])  # not a second line under «Fristen»
        lines, _ = screen.account_lines(items, date(2026, 11, 15), {}, {"04.11.2026"}, lead_id="deadline:konto-r1")
        self.assertEqual(lines, [])  # what the card head states (the deadline that leads, a date of its reason) is not said again

    def test_a_passed_statutory_deadline_does_not_lead_once_the_case_is_past_the_way_to_proceed(self):
        facts = [("rechtsgebiet", "Mietrecht / Kündigung"), ("kuendigung_erhalten", "2026-09-01"), ("befristet", False)]
        state, items, _, _ = view("miete-kuendigung", facts, "2026-11-14")
        rule = state["process"]["urgent"]
        self.assertEqual(screen.lead(items, date(2026, 11, 14), rule, "klaeren")["word"], "abgelaufen")  # at intake: it may be lost
        self.assertIsNone(screen.lead(items, date(2026, 11, 14), rule, "mandat"))  # behind the process; still listed under «Fristen»
        passed = lambda stage: next(r for r in screen.fristen(items, date(2026, 11, 14), stage=stage) if r["state"] == "abgelaufen")
        self.assertEqual((passed("klaeren")["late"], passed("mandat")["late"]), (True, False))  # listed, not marked late, once past it

    def test_a_date_set_in_a_summons_is_said_in_good_german(self):
        from casepath.process.items import pair_set_dates
        law = {"item_id": "deadline:anfechtung", "kind": "deadline", "origin": "law", "value": "2026-11-02", "stated": "2026-10-03",
               "label": {"de": "Anfechtung der Kündigung"}}
        given = {"item_id": "deadline:frist", "kind": "deadline", "origin": "claim_reader", "value": "2026-12-10",
                 "what": "Anfechtung der Kündigung", "source": "Vorladung zur Schlichtungsverhandlung"}
        pair_set_dates([law, given])
        self.assertEqual(law["set_date"]["lines"], ["gesetzlich: 02.11.2026", "in der Vorladung zur Schlichtungsverhandlung gesetzt: 10.12.2026", "prüfen, welche gilt"])

    def test_the_reason_leaves_its_date_to_the_deadline_line(self):
        reason = "Angebot der Gegenpartei vom 05.11.2026 eingegangen, noch offen – Muster AG: Mietzinsreduktion CHF 2'000, zahlbar bis 30.11.2026"
        self.assertEqual(screen.without_date(reason, "30.11.2026"), "Angebot der Gegenpartei vom 05.11.2026 eingegangen, noch offen – Muster AG: Mietzinsreduktion CHF 2'000")
        self.assertEqual(screen.without_date("Die Meldung ist eingegangen", "30.11.2026"), "Die Meldung ist eingegangen")

    def test_what_goes_out_is_tabs_named_by_whom_it_goes_to_each_ticked_once_copied(self):
        twin = "Vorlage für Ihr Schreiben an die Arbeitgeberin"
        draft_ = {"form": "A1", "to": "Kundschaft", "title": "Unterlagen und Angaben anfordern", "text": "Brief",
                  "also": [{"kind": "vorlage:einsprache", "title": twin, "name": "Einsprache gegen die Kündigung", "text": "a", "template": True},
                           {"kind": "vorlage:begruendung", "title": twin, "name": "Begründung der Kündigung verlangen", "text": "b", "template": True}]}
        events = [{"kind": "letter.copied", "form": "A1", "at": "2026-11-15T10:00:00"}, {"kind": "letter.copied", "also": "vorlage:einsprache", "at": "2026-11-14T10:00:00"}]
        tabs = screen.documents(draft_, events, since="2026-11-15T09:00:00")
        self.assertEqual([(t["title"], t["copied"]) for t in tabs], [("Brief an die Kundschaft", True), ("Vorlage: Einsprache gegen die Kündigung", False),
                                                                      ("Vorlage: Begründung der Kündigung verlangen", False)])  # a copy before the preparation does not count
        alone = screen.documents({**draft_, "to": "Anwaltskanzlei", "also": draft_["also"][:1]}, [])
        self.assertEqual([t["title"] for t in alone], ["Brief an die Kanzlei", "Vorlage an die Arbeitgeberin"])

    def test_the_screen_says_neither_the_holiday_note_nor_a_point_the_letter_already_cites(self):
        self.assertEqual(screen.shown_rule({"rule": "am 02.01.2027; fällt auf ein Wochenende, prüfen; kantonale Feiertage nicht berücksichtigt"}),
                         "am 02.01.2027; fällt auf ein Wochenende, prüfen")
        point = {"item_id": "key_point:einsprache", "kind": "key_point", "value": "open", "shown": True, "legal_basis": "Art. 354 Abs. 3 StPO",
                 "follows": "Der Strafbefehl wird rechtskräftig", "label": {"de": "Einsprache erhoben?"}}
        self.assertEqual(screen.key_points([point], "Ohne Einsprache wird er zum Urteil (Art. 354 Abs. 3 StPO)."), [])
        self.assertEqual(len(screen.key_points([point], "Guten Tag")), 1)

    def test_the_status_counts_the_copy_of_the_step_now_prepared(self):
        since = "2026-11-15T09:00:00"
        done = [{"kind": "letter.copied", "form": "A13", "at": "2026-11-15T10:00:00"}, {"kind": "letter.copied", "also": "vorlage:einsprache", "at": "2026-11-15T10:01:00"}]
        self.assertTrue(listing.step_copied({"kind": "next_action", "action": "A13", "form": "A13"}, done, since))
        first = {"kind": "next_action", "action": "A1"}  # «Frist wahren» went out; the first request now prepared has not
        self.assertFalse(listing.step_copied(first, done, since))
        self.assertTrue(listing.step_copied(first, done + [{"kind": "letter.copied", "form": "A1", "at": "2026-11-15T10:02:00"}], since))
        self.assertFalse(listing.step_copied(first, [{"kind": "letter.copied", "form": "A1", "at": "2026-11-14T10:00:00"}], since))  # before it was prepared

    def test_the_case_is_named_by_what_it_is_about_and_the_newest_comes_first(self):
        request = "Rita Exempel hat die Kündigung seiner Wohnung angefochten und ist zur Schlichtungsverhandlung am 10. Dezember 2026 vorgeladen."
        self.assertEqual(listing.dispute_object(request, ["Rita Exempel", "Kündigung Miete"]), "Wohnung")  # not the hearing
        import tempfile
        from casepath.web.store import CaseStore
        with tempfile.TemporaryDirectory() as d:
            store = CaseStore(d)
            first, second = store.create_case("eins", {}, "x"), store.create_case("zwei", {}, "x")
            self.assertEqual([c["id"] for c in store.list_cases()], [second["id"], first["id"]])  # also within one second


if __name__ == "__main__":
    unittest.main()

"""The cover decision prepared and the letters whose content is prescribed (casepath/process/cover.py).

Scripted and model-free: the facts are what a reader would have recorded with their quotes; one run goes through the
agent team with the scripted model."""
import copy
from datetime import date
import json
import os
import tempfile
import unittest

from casepath.agents import core
from casepath.process import area, cover, letters
from casepath.process.items import build_items, items_sha256
from casepath.process.workflows import CatalogueError
from tests.scripted import ScriptedModel, report
from tests.test_areas import catalogue, intakes

CASE = {"id": "c", "title": "Schimmel (synthetisch) 1234.5678.9012", "intake": {}}
TENANT = [("rechtsgebiet", "Mietrecht / Mangel", "Im Bad meiner Mietwohnung wächst Schimmel."), ("maengelruege_schriftlich", "ja", None),
          ("will_schadenersatz", "nein", None), ("streit_mietzins", "nein", None)]
CAUSE = ("ursache_datum", "2026-03-10", "Seit dem 10. März 2026 ist die Wand im Bad nass.")


def fact(fid, value, quote=None):
    return {"fact": fid, "status": "established", "verdict": "accepted", "value": value,
            "citations": [{"file": "f1", "page": 1, "quote": quote}] if quote else []}


def edits(**values):
    return [{"id": f"e{i}", "op": "set_fact", "args": {"fact": k, "value": v}, "status": "active"} for i, (k, v) in enumerate(values.items())]


def view(facts, history=None, set_by_hand=None, wid="mietmangel-handler", as_of="2026-11-14", segments=None, documents=(), created="2026-11-14T08:00:00",
         events=()):
    rows = [fact(*f) for f in facts] + ([fact("bisherige_handlungen", history)] if history else [])
    files = [{"id": "f1", "name": "Akte.pdf", "extraction": {**({"cut_of": {"as_of": as_of}} if as_of else {}),
                                                            "segments": segments if segments is not None else [{"date": "12.11.2026", "kind": "Schadenmeldung", "sender": "Lea Beispiel"}]}}]
    result = {"facts": rows, "documents": [{"document": d, "status": "present", "verdict": "accepted", "files": ["f1"], "citations": []} for d in documents],
              "brief": {"request": "Schimmel im Bad.", "parties": [{"role": "Mieterin (VN)", "name": "Lea Beispiel"}], "timeline": []}}
    state = {**core.evaluate(area.workflow(wid), [], edits(**(set_by_hand or {})), result, "c", files=files), "case": {"id": "c", "created_at": created}}
    items = build_items(state, result, files, list(events))
    return state, {i["item_id"]: i for i in items}, items


def draft(items, form):
    return letters.render(form, area.workflow("mietmangel-handler")["forms"], letters.context(CASE, items, [], {"due": "2026-12-01"}))


class PassageTests(unittest.TestCase):
    def test_every_clause_is_word_for_word_in_the_stored_conditions_and_short(self):
        found = cover.confirm_avb()
        self.assertTrue(found and all(found.values()), [k for k, ok in found.items() if not ok])
        for row in list(cover.data()["avb"].values()) + list(cover.data()["law"].values()):
            self.assertLessEqual(len(row["passage"].split()), 50, row["cite"])
        self.assertNotIn("Rechts- massnahmen", cover.edition_text("unternehmen"))  # line-end hyphens joined
        self.assertIn("Melde- oder Verhaltenspflichten", cover.edition_text("unternehmen"))

    def test_law_marked_verified_is_found_in_the_saved_official_text(self):
        folder = os.environ.get("CASEPATH_LAW_SOURCES")  # the folder of saved fedlex HTML and web pages (its index.tsv layout)
        if not folder:
            self.skipTest("CASEPATH_LAW_SOURCES not set")
        law, public = cover.confirm_law(folder), cover.confirm_public(folder)
        self.assertEqual(law, {k: r["verified"] for k, r in cover.data()["law"].items()})
        self.assertEqual(public, {k: r["verified"] for k, r in cover.data()["public"].items()})

    def test_every_area_carries_the_cover_facts_and_forms(self):
        own = {f["id"] for f in cover.data()["facts"]}
        read = {f["id"] for f in cover.data()["facts"] if not f.get("handler_only")}
        self.assertEqual(read, {"ursache_datum", "ausschluss_hinweis", "vorab_schritte", "mahnung_androhung"})  # what a run reads
        for w in area.shipped():
            self.assertLessEqual(own, {f["id"] for f in w["facts"]})
            self.assertLessEqual({"A5_aussichtslos", "A6_androhung", "A12_mitwirkung", "A10_kunde"}, set(w["forms"]))
        # the area's own date stands for the cause: the cause date is only offered, not asked twice
        asked = {f["id"]: f for f in area.workflow("mietmangel-handler")["facts"]}["ursache_datum"]["ask_customer"]
        self.assertEqual(asked, "offered")
        self.assertIs({f["id"]: f for f in area.workflow("arbeit-zeugnis")["facts"]}["ursache_datum"]["ask_customer"], True)


class CoverPointTests(unittest.TestCase):
    def test_a_tenancy_case_some_points_from_the_file_some_open_policy_points_with_their_dates(self):
        state, listed, items = view(TENANT + [CAUSE])
        points = {i["key"]: i for i in items if i["kind"] == "cover" and i["key"] != "summary"}
        self.assertEqual(list(points), ["vertrag", "person", "eigenschaft", "rechtsgebiet", "zeitraum", "wartefrist", "gebiet", "ausschluss", "pflichten", "grenzen"])
        self.assertEqual(points["eigenschaft"]["value"], "akte")
        self.assertEqual(points["eigenschaft"]["evidence"][0]["quote"], TENANT[0][2])  # met from the file, with its source
        self.assertEqual((points["ausschluss"]["value"], points["pflichten"]["value"]), ("kein_hinweis", "kein_hinweis"))
        self.assertEqual(points["vertrag"]["aid"], "Police am 10.03.2026 (Ursache) in Kraft?")
        self.assertEqual(points["zeitraum"]["aid"], "Antrag vor dem 10.03.2026 gestellt und Police an diesem Tag in Kraft?")
        self.assertEqual(points["wartefrist"]["aid"], "bei drei Monaten: Police spätestens am 10.12.2025 in Kraft")
        self.assertEqual(points["wartefrist"]["text"], "gemäss Police; allgemein drei Monate")  # never a fact about this policy
        self.assertEqual(points["rechtsgebiet"]["text"], "«Miet- und Pachtrecht» in der Police eingeschlossen?")
        self.assertEqual(points["person"]["aid"], "laut Akte: Lea Beispiel (Mieterin)")  # the role once, without its marker
        self.assertEqual(listed["cover:summary"]["value"], "Deckung: 3 aus der Akte geklärt · 7 in der Police prüfen")
        self.assertEqual(points["zeitraum"]["legal_basis"], "Art. A2 Ziff. 1 und 2")
        self.assertIn("Ursache bei Antragsstellung", points["zeitraum"]["clauses"][0]["passage"])
        # without the cause date it is asked in the first request; the area's own date stands in, to be checked
        state, listed, items = view(TENANT)
        self.assertEqual(listed["cover:zeitraum"]["value"], "kunde")
        self.assertIn("letter_question:mangel_seit", listed)
        state, listed, items = view(TENANT + [("mangel_seit", "2026-02-01", "seit Februar")])
        self.assertEqual(listed["cover:zeitraum"]["text"], "Ursache am 01.02.2026")
        self.assertIn("als Ursache prüfen", listed["cover:zeitraum"]["note"])

    def test_a_cause_inside_the_stated_waiting_period_is_flagged_once_the_policy_date_is_entered(self):
        _, listed, _ = view(TENANT + [CAUSE], set_by_hand={"police_wartefrist": "drei Monate"})
        self.assertEqual(listed["cover:wartefrist"]["value"], "police")  # no policy date yet
        _, listed, items = view(TENANT + [CAUSE], set_by_hand={"police_wartefrist": "drei Monate", "police_beginn": "2026-01-15"})
        self.assertEqual(listed["cover:wartefrist"]["value"], "hinweis")
        self.assertIn("liegt in der Wartefrist der Police von drei Monaten ab 15.01.2026 (bis 14.04.2026)", listed["cover:wartefrist"]["text"])
        self.assertEqual(listed["cover:zeitraum"]["value"], "police_ok")
        self.assertTrue(listed["cover:summary"]["value"].endswith("· 1 Hinweis"))
        _, listed, _ = view(TENANT + [CAUSE], set_by_hand={"police_wartefrist": "drei Monate", "police_beginn": "2025-11-01"})
        self.assertEqual(listed["cover:wartefrist"]["value"], "police_ok")
        _, listed, _ = view(TENANT + [CAUSE], set_by_hand={"police_beginn": "2026-04-01"})
        self.assertEqual(listed["cover:zeitraum"]["value"], "hinweis")  # the cause before the cover began
        self.assertEqual(listed["cover:wartefrist"]["value"], "hinweis")  # within the general three months, «in der Police prüfen»
        self.assertIn("allgemeinen Wartefrist", listed["cover:wartefrist"]["text"])

    def test_the_edition_switch_changes_the_clause_tags(self):
        tags = lambda listed: {k: listed[f"cover:{k}"]["legal_basis"] for k in ("vertrag", "wartefrist", "pflichten", "eigenschaft")}
        self.assertEqual(tags(view(TENANT + [CAUSE])[1]), {"vertrag": "Art. A1 Ziff. 3 und 4", "wartefrist": "Art. A2 Ziff. 4",
                                                           "pflichten": "Art. M Ziff. 1 und 4", "eigenschaft": "Art. C Ziff. 3"})
        business = view(TENANT + [CAUSE], set_by_hand={"avb_ausgabe": "Unternehmen 09.2025"})[1]
        self.assertEqual(tags(business), {"vertrag": "Art. A1 Ziff. 2 und 3", "wartefrist": "Art. A3 Ziff. 4",
                                          "pflichten": "Art. F Ziff. 1 und 4", "eigenschaft": "Art. B2"})
        self.assertEqual(business["cover:eigenschaft"]["value"], "police")  # the activity is in the policy
        other = view(TENANT + [CAUSE], set_by_hand={"avb_ausgabe": "andere Ausgabe"})[1]
        self.assertEqual({other[f"cover:{k}"]["legal_basis"] for k in ("vertrag", "wartefrist")}, {"Ziffer prüfen"})

    def test_ticks_and_the_decision_are_handler_facts_and_change_the_item_list(self):
        _, _, before = view(TENANT + [CAUSE])
        _, listed, after = view(TENANT + [CAUSE], set_by_hand={"police_vertrag": "ja", "deckung": "abgelehnt", "deckung_grund": "wartefrist"})
        self.assertEqual((listed["cover:vertrag"]["value"], listed["cover:vertrag"]["tick"]), ("police_ok", "police_vertrag"))
        self.assertEqual((listed["cover:summary"]["decision"], listed["cover:summary"]["reason"]), ("abgelehnt", "wartefrist"))
        self.assertEqual(listed["fact:police_vertrag"]["verdict"], "set_by_handler")
        self.assertNotEqual(items_sha256(before), items_sha256(after))
        self.assertEqual(view(TENANT + [CAUSE], set_by_hand={"police_vertrag": "nein"})[1]["cover:vertrag"]["value"], "hinweis")

    def test_a_scripted_run_reads_the_cause_date_with_its_quote(self):
        text = "SYNTHETISCHER FALL. Ich miete die Wohnung seit 2020. Seit dem 10. März 2026 ist die Wand im Bad nass und schimmlig."
        cite = lambda q: [{"file": "f1", "quote": q}]
        model = ScriptedModel([
            [("record_fact", {"part": None, "fact": "ursache_datum", "status": "established", "value": "2026-03-10",
                              "citations": cite("Seit dem 10. März 2026 ist die Wand im Bad nass")}), report("claim_reader", request="Schimmel im Bad.")],
            [report("document_finder")], *[[report("result_checker", answer="Erste Anforderung.")]] * 3,
        ], routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Mangel", "citations": cite("Wand im Bad nass und schimmlig")}])
        job = {"format": core.JOB, "case": {"id": "case_c", "title": "Schimmel (synthetisch)", "intake": {}},
               "files": [{"id": "f1", "name": "meldung.txt", "kind": "text", "media_type": "text/plain", "sha256": "abc",
                          "extraction": {"text": text, "pages": None, "readable": True, "note": ""}}],
               "workflows": list(catalogue(*intakes("osm-mold")).workflows), "knowledge": [], "edits": [], "options": {"read_scans": True}}
        with tempfile.TemporaryDirectory() as blobs:
            outcome = core.prepare(json.loads(json.dumps(job)), model, core.DirectoryBlobs(blobs))
        self.assertEqual(outcome["status"], "completed", outcome.get("error"))
        state = core.evaluate(area.workflow("mietmangel-handler"), [], [], outcome["result"], "case_c")
        listed = {i["item_id"]: i for i in build_items(state, outcome["result"])}
        self.assertEqual(listed["cover:zeitraum"]["text"], "Ursache am 10.03.2026")
        self.assertEqual(listed["cover:zeitraum"]["evidence"][0]["quote"], "Seit dem 10. März 2026 ist die Wand im Bad nass")


class RefusalTests(unittest.TestCase):
    ASSESS = TENANT + [("deckung", "bestätigt", None), ("handlung_a1", "2026-10-01", None), ("mangel_seit", "2026-02-01", None),
                       ("mangel_besteht", True, None)]
    SEGMENTS = [{"date": "01.10.2026", "sender": "Protekta"}, {"date": "20.10.2026", "sender": "Lea Beispiel"}]

    def test_the_refusal_for_lack_of_prospects_carries_its_required_parts_and_copying_is_refused_without_them(self):
        _, listed, _ = view(self.ASSESS, segments=self.SEGMENTS)
        self.assertEqual((listed["next_action:0"]["action"], listed["next_action:0"].get("form")), ("A5", None))
        self.assertIsNone(listed["check:aussichten"]["value"])  # the decision on prospects is asked at the assessment
        _, listed, items = view(self.ASSESS, segments=self.SEGMENTS, set_by_hand={"aussichten": "nicht genügend"})
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"], nxt["value"]), ("A5", "A5_aussichtslos", "Ablehnung mangels Erfolgsaussichten"))
        text, none = draft(items, "A5_aussichtslos")
        self.assertIsNone(none)
        required = cover.required_for("A5_aussichtslos", {})
        self.assertEqual([r["id"] for r in required], ["begruendung", "loesung", "eigene_kosten", "verfahren"])
        self.assertEqual(required[3]["basis"], "Art. 169 Abs. 2 AVO; Art. M Ziff. 8 AVB")
        self.assertEqual(cover.missing_required(text, required), [])
        self.assertIn("innert 20 Tagen nach Erhalt dieses Entscheides bei uns ein Schiedsverfahren beantragen (Art. M Ziff. 8 der Allgemeinen Bedingungen)", text)
        self.assertIn("ersetzen wir Ihnen die Kosten des Verfahrens (Art. M Ziff. 7 der Allgemeinen Bedingungen)", text)
        self.assertTrue(letters.has_gap(text))  # the reasons and the solution are the handler's: copying waits for them
        cut = text.replace("Sie können selbst die Ihnen gut scheinenden Massnahmen ergreifen.", "")
        self.assertEqual([r["id"] for r in cover.missing_required(cut, required)], ["eigene_kosten"])
        other = view(self.ASSESS, segments=self.SEGMENTS, set_by_hand={"aussichten": "nicht genügend", "avb_ausgabe": "andere Ausgabe"})[2]
        text = draft(other, "A5_aussichtslos")[0]
        self.assertIn("innert [bitte ergänzen: Frist für das Schiedsverfahren", text)
        self.assertEqual(view(self.ASSESS, segments=self.SEGMENTS, set_by_hand={"aussichten": "genügend"})[1]["next_action:0"].get("form"), None)

    def test_an_area_module_cannot_remove_a_required_part_and_a_basis_must_be_verified(self):
        module = json.loads((area.AREAS / "arbeit-zeugnis.json").read_text())
        forms = cover.forms()
        forms["A5_aussichtslos"]["parts"] = [p for p in forms["A5_aussichtslos"]["parts"] if "Schiedsverfahren" not in p]
        with self.assertRaises(CatalogueError):
            area.compose(area.backbone(), {**module, "forms": {"A5_aussichtslos": {k: v for k, v in forms["A5_aussichtslos"].items() if k != "required"}}})
        kept = {k: v for k, v in cover.forms()["A5_aussichtslos"].items() if k != "required"}
        area.compose(area.backbone(), {**module, "forms": {"A5_aussichtslos": {**kept, "title": "Ablehnung (eigener Titel)"}}})  # kept: accepted
        data = cover.data()
        data["law"]["avo-169.2"]["verified"] = False
        with self.assertRaises(CatalogueError):
            cover.validate(data)
        data = cover.data()
        data["forms"]["A6_androhung"]["parts"][2]["required"]["basis"] = []
        with self.assertRaises(CatalogueError):
            cover.validate(data)


class CooperationTests(unittest.TestCase):
    SILENT = TENANT + [("deckung", "bestätigt", None), ("handlung_a1", "2026-08-01", None), ("handlung_a6", "2026-09-01", None)]
    SEGMENTS = [{"date": "20.07.2026", "sender": "Lea Beispiel"}, {"date": "01.09.2026", "sender": "Protekta"}]
    WARNED = ("mahnung_androhung", "Protekta: Aufforderung vom 2026-10-01, Unterlagen bis 2026-10-15, sonst Leistungseinstellung",
              "Erhalten wir die Unterlagen bis 15. Oktober 2026 nicht, stellen wir unsere Leistungen ein.")

    def test_without_a_written_warning_the_demand_comes_first_and_with_one_the_ending(self):
        state, listed, items = view(self.SILENT, segments=self.SEGMENTS)
        self.assertEqual(state["evaluation"]["outcome"]["id"], "mitwirkung")
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"], nxt["value"]), ("A6", "A6_androhung", "Letzte Aufforderung mit Androhung der Säumnisfolgen"))
        self.assertIn("Art. 39 Abs. 2 Ziff. 2 VVG", nxt["reason"])
        check = listed["check:androhung"]
        self.assertEqual((check["value"], check["legal_basis"]), ("fehlt", "Art. 39 Abs. 2 Ziff. 2 VVG"))
        self.assertEqual(check["note"]["law"]["cite"], "Art. 45 Abs. 1 VVG")  # fault and causal effect: a check, not a conclusion
        text, _ = draft(items, "A6_androhung")
        self.assertIn("Mit Schreiben vom 01.09.2026 haben wir Sie um folgende Unterlagen und Angaben gebeten:\n– Mietvertrag", text)
        self.assertIn("Wir fordern Sie hiermit auf, uns diese Unterlagen und Angaben bis 01.12.2026 zuzustellen.", text)
        self.assertIn("stellen wir unsere Leistungen in diesem Fall ein und schliessen Ihr Dossier (Art. M Ziff. 1 und 4 der Allgemeinen Bedingungen)", text)
        self.assertEqual(cover.missing_required(text, cover.required_for("A6_androhung")), [])

        state, listed, items = view(self.SILENT + [self.WARNED], segments=self.SEGMENTS)
        nxt = listed["next_action:0"]
        self.assertEqual((nxt["action"], nxt["form"]), ("A12", "A12_mitwirkung"))
        self.assertEqual(listed["check:androhung"]["value"], "vorhanden")
        text, _ = draft(items, "A12_mitwirkung")
        self.assertIn("Mit Schreiben vom 01.10.2026 haben wir Sie unter Androhung der Säumnisfolgen aufgefordert", text)
        self.assertIn("gemäss den Allgemeinen Bedingungen (Art. M Ziff. 1 und 4) verletzt", text)
        business = view(self.SILENT + [self.WARNED], segments=self.SEGMENTS, set_by_hand={"avb_ausgabe": "Unternehmen 09.2025"})[2]
        self.assertIn("(Art. F Ziff. 1 und 4)", draft(business, "A12_mitwirkung")[0])
        # the handler may decide otherwise: benefits end without the warning, which stays shown as missing
        _, listed, _ = view(self.SILENT, segments=self.SEGMENTS, set_by_hand={"leistungen_einstellen": "ja"})
        self.assertEqual((listed["next_action:0"]["action"], listed["check:androhung"]["value"]), ("A12", "fehlt"))


class MandateAndOfferTests(unittest.TestCase):
    def test_the_mandate_information_states_the_free_choice_and_an_offer_shows_the_consent_for_a_settlement(self):
        mandate = TENANT + [("deckung", "bestätigt", None), ("vorgehen", "Mandat an Anwaltskanzlei", None)]
        _, listed, items = view(mandate, history="A1 2026-09-01; A5 2026-10-01")
        self.assertEqual(listed["next_action:0"]["action"], "A10")
        self.assertEqual(cover.accompanying("A10"), ["A10_kunde"])
        text, none = draft(items, "A10_kunde")
        self.assertIsNone(none)
        self.assertIn("dürfen Sie einen Anwalt mit Sitz im Gebiet des für die Beurteilung des Rechtsstreits zuständigen Gerichtes frei wählen "
                      "und vorschlagen (Art. M Ziff. 3 der Allgemeinen Bedingungen)", text)
        self.assertIn("nachdem Sie unsere Zustimmung und unsere Kostengutsprache eingeholt haben", text)
        self.assertEqual(cover.missing_required(text, cover.required_for("A10_kunde")), [])
        self.assertEqual(cover.required_for("A10_kunde")[0]["basis"], "Art. 167 Abs. 1 AVO; Art. M Ziff. 3 AVB")
        offer = TENANT + [("deckung", "bestätigt", None), ("vorgehen", "Selbst führen", None),
                          ("eingang_angebot", "Verwaltung: Vergleichsangebot CHF 800 per Saldo, Schreiben vom 2026-10-20", "CHF 800 per Saldo")]
        _, listed, _ = view(offer, history="A1 2026-09-01; A8 2026-10-01")
        self.assertEqual(listed["next_action:0"]["action"], "A9")
        self.assertEqual(listed["check:vergleich"]["legal_basis"], "Art. M Ziff. 5")
        self.assertIn("Zustimmung einholen", listed["check:vergleich"]["clauses"][0]["passage"])


class FirstContactTests(unittest.TestCase):
    """The three working days count from the day the case came in to the insurer as CasePath can know it: the day the
    case was created, or the insurer's own receipt of the report in the file; never the date of the customer's letter."""
    LETTER = {"date": "02.11.2026", "kind": "Schadenmeldung", "sender": "Lea Beispiel"}  # the customer's own letter, twelve days old

    def test_three_working_days_from_the_day_the_case_was_created_not_from_the_customers_letter(self):
        self.assertEqual(cover.add_working_days(date(2026, 11, 13), 3), date(2026, 11, 18))  # Friday → Wednesday
        _, listed, _ = view(TENANT, segments=[self.LETTER], as_of=None, created="2026-11-13T09:12:00")
        row = listed["contact:erstkontakt"]
        self.assertEqual((row["value"], row["stated"]), ("2026-11-18", "2026-11-13"))
        self.assertIn("Eröffnung des Falls vom 13.11.2026", row["rule"])
        self.assertIn("Feiertage nicht berücksichtigt", row["rule"])
        self.assertIn("innerhalb von drei Arbeitstagen", row["legal_basis"])
        self.assertTrue(view(TENANT, segments=[self.LETTER], as_of="2026-11-19", created="2026-11-13T09:12:00")[1]["contact:erstkontakt"]["late"])

    def test_the_insurers_own_receipt_in_the_file_sets_the_day_earlier_or_later(self):
        for day, due in (("06.11.2026", "2026-11-11"), ("16.11.2026", "2026-11-19")):
            receipt = {"date": day, "kind": "Eingangsbestätigung", "title": "Eingang Ihrer Schadenmeldung", "sender": "Protekta Rechtsschutz AG"}
            row = view(TENANT, segments=[self.LETTER, receipt], as_of=None, created="2026-11-13T09:12:00")[1]["contact:erstkontakt"]
            self.assertEqual(row["value"], due)
            self.assertIn("Eingangsbestätigung der Versicherung", row["rule"])
        not_ours = {"date": "06.11.2026", "kind": "Brief", "title": "Registrierung beim Verein", "sender": "Lea Beispiel"}
        self.assertEqual(view(TENANT, segments=[self.LETTER, not_ours], as_of=None, created="2026-11-13T09:12:00")[1]["contact:erstkontakt"]["stated"], "2026-11-13")

    def test_gone_once_the_insurer_made_contact_and_never_on_a_historic_file(self):
        here = dict(segments=[self.LETTER], as_of=None, created="2026-11-13T09:12:00")
        self.assertNotIn("contact:erstkontakt", view(TENANT, history="A1 2026-11-16", **here)[1])
        self.assertNotIn("contact:erstkontakt", view(TENANT + [("handlung_a2", "2026-11-14", None)], **here)[1])
        # Rewritten for SLICE_B B9: contact is a letter dispatched, or a copy by a browser before this release (no «measure»);
        # a copy measured by this release's browser is no contact
        self.assertNotIn("contact:erstkontakt", view(TENANT, events=[{"kind": "letter.copied", "at": "2026-11-13T10:00:00"}], **here)[1])
        self.assertIn("contact:erstkontakt", view(TENANT, events=[{"kind": "letter.copied", "at": "2026-11-13T10:00:00", "measure": True}], **here)[1])
        sent = [{"kind": "action.approved", "version": "v1", "form": "A1", "recipients": [{"to": "kunde", "forms": ["A1"]}], "at": "2026-11-13T10:00:00"},
                {"kind": "action.dispatched", "version": "v1", "recipient": "kunde", "date": "2026-11-13", "edit_id": "e1", "at": "2026-11-13T10:05:00"}]
        self.assertNotIn("contact:erstkontakt", view(TENANT, events=sent, **here)[1])
        # a test cut looked at as of a day before it was made, and a whole old file uploaded for testing
        self.assertNotIn("contact:erstkontakt", view(TENANT, segments=[self.LETTER], as_of="2025-02-07", created="2026-11-13T09:12:00")[1])
        old = [{"date": "14.03.2024", "kind": "Schadenmeldung", "sender": "Lea Beispiel"}, {"date": "02.10.2025", "kind": "Brief", "sender": "Verwaltung"}]
        self.assertNotIn("contact:erstkontakt", view(TENANT, segments=old, as_of=None, created="2026-11-13T09:12:00")[1])
        recent = old[:1] + [{"date": "20.11.2025", "kind": "Brief", "sender": "Verwaltung"}]  # within twelve months: a live case
        self.assertIn("contact:erstkontakt", view(TENANT, segments=recent, as_of=None, created="2026-11-13T09:12:00")[1])
        moved = [{"kind": "case.historic", "historic": False, "at": "2026-11-13T10:00:00"}]  # a person moved it out of the historic files
        self.assertIn("contact:erstkontakt", view(TENANT, segments=old, as_of=None, created="2026-11-13T09:12:00", events=moved)[1])


if __name__ == "__main__":
    unittest.main()

"""The law table and the counting rules per procedure (backbone ``laws`` and ``counting``, area.compute_deadline), with
fixed dates: each date is what the verified text gives, and where the text gives no rule the deadline says «prüfen»."""
import copy
import unittest

from casepath.process import area
from casepath.process.workflows import CatalogueError


def compute(counting, period, trigger, facts=None, **extra):
    d = {"id": "d", "title": "T", "trigger": "t", "period": period, "basis": "Art. 1 X", "missed": "m", "counting": counting, **extra}
    return area.compute_deadline(d, trigger, facts)


class LawTableTests(unittest.TestCase):
    def test_a_law_is_any_federal_text_by_sr_number_and_short_name_and_every_passage_is_verified(self):
        bb = area.backbone()
        self.assertLessEqual({"220", "210", "221.229.1", "272", "281.1", "312.0", "314.1", "741.01", "830.1", "831.20", "101", "173.110.3"},
                             set(bb["laws"]))
        self.assertEqual(area.cited_articles("Art. 38 Abs. 4 ATSG, Art. 57a Abs. 3 IVG und Art. 74 SchKG", bb["laws"]),
                         {("830.1", "38"), ("831.20", "57a"), ("281.1", "74")})
        self.assertEqual(area.cited_articles("Art. 257g, 259a OR"), {("220", "257g"), ("220", "259a")})
        self.assertTrue(all(row["verified"] for row in bb["law"].values()))
        self.assertEqual(bb["law"]["77-andere"]["cite"], "Art. 77 Abs. 2 OR")  # «In gleicher Weise …» is Abs. 2, not Abs. 3

    def test_a_citation_of_any_law_needs_its_passage_and_a_counting_rule_needs_verified_text(self):
        bb = area.backbone()
        module = area.load(area.AREAS / "sozialversicherung.json")
        module["hints"].append({"id": "x", "when": True, "text": "Siehe Art. 61 lit. c ATSG und Art. 43 ATSG.", "source_refs": ["law#atsg-52.1"]})
        with self.assertRaisesRegex(CatalogueError, "Art. 43 ATSG is cited without a law entry"):
            area.compose(bb, module)
        module = area.load(area.AREAS / "sozialversicherung.json")
        module["deadlines"][0]["counting"] = "verwaltung"
        with self.assertRaisesRegex(CatalogueError, "unknown counting rule"):
            area.compose(bb, module)
        broken = copy.deepcopy(bb)
        broken["law"]["atsg-38.4"]["verified"] = False
        with self.assertRaisesRegex(CatalogueError, "not a verified passage"):
            area.validate_backbone(broken)
        broken = copy.deepcopy(bb)
        broken["laws"]["830.1"]["url"] = "https://example.org/atsg.html"
        with self.assertRaisesRegex(CatalogueError, "fedlex filestore url"):
            area.validate_backbone(broken)


class CountingTests(unittest.TestCase):
    def test_easter(self):
        self.assertEqual([area.easter(y).isoformat() for y in (2025, 2026, 2027)], ["2025-04-20", "2026-04-05", "2027-03-28"])

    def test_code_of_obligations_saturday_sunday_federal_holiday_and_an_agreed_period(self):
        self.assertEqual(compute("or", {"days": 30}, "2026-07-02")[0], "2026-08-03")  # 1 August 2026: a Saturday and the federal holiday
        self.assertEqual(compute("or", {"months": 1}, "2026-07-01")[0], "2026-08-03")
        self.assertEqual(compute("or", {"days": 10}, "2026-12-15")[0], "prüfen")  # 25 December: a holiday in the cantons, not in the verified texts
        agreed = compute("or", {"weeks": 6}, "2025-02-10", {"k": "3 Monate"}, period_from="k")
        self.assertEqual(agreed[0], "prüfen")  # 10 May 2025, a Saturday: the Saturday act covers statutory and official periods only
        self.assertIn("SR 173.110.3", agreed[1])

    def test_criminal_procedure_next_day_weekend_and_no_court_holidays(self):
        self.assertEqual(compute("stpo", {"days": 10}, "2026-11-04")[0], "2026-11-16")  # Saturday 14.11. → Monday
        self.assertEqual(compute("stpo", {"days": 10}, "2026-07-10")[0], "2026-07-20")  # summer: no court holidays (Art. 89 Abs. 2 StPO)
        self.assertEqual(compute("stpo", {"days": 10}, "2026-12-15")[0], "prüfen")
        month = compute("stpo", {"months": 1}, "2026-07-10")
        self.assertEqual(month[0], "prüfen")
        self.assertIn("Art. 90 StPO nennt keine Regel", month[1])

    def test_social_insurance_periods_stand_still_at_easter_in_summer_and_at_christmas(self):
        self.assertEqual(compute("atsg", {"days": 30}, "2026-12-10")[0], "2027-01-25")  # 18.12.–2.1. not counted
        self.assertEqual(compute("atsg", {"days": 30}, "2026-12-20")[0], "2027-02-01")  # notified during it: counting starts on 3 January
        self.assertEqual(compute("atsg", {"days": 30}, "2027-03-15")[0], "2027-04-29")  # Easter 28.3.2027: 21.3.–4.4. not counted
        self.assertEqual(compute("atsg", {"days": 30}, "2026-07-01")[0], "2026-09-01")  # 15.7.–15.8. not counted
        self.assertEqual(compute("atsg", {"days": 30}, "2026-10-05")[0], "2026-11-04")  # no standstill in between
        self.assertEqual(compute("atsg", {"months": 3}, "2026-03-01")[0], "prüfen")

    def test_civil_procedure_standstill_its_exceptions_and_months(self):
        self.assertEqual(compute("zpo", {"days": 30}, "2026-07-10")[0], "2026-09-10")
        self.assertEqual(compute("zpo-ohne-stillstand", {"days": 20}, "2026-07-10")[0], "2026-07-30")  # conciliation, summary procedure
        months = compute("zpo", {"months": 3}, "2026-01-10")
        self.assertEqual(months[0], "prüfen")
        self.assertIn("Art. 142 Abs. 2 ZPO", months[1])

    def test_debt_enforcement_holidays_extend_the_period_and_a_court_action_follows_the_zpo_standstill(self):
        self.assertEqual(compute("schkg", {"days": 10}, "2026-09-01")[0], "2026-09-11")
        self.assertEqual(compute("schkg", {"days": 10}, "2026-07-01")[0], "2026-07-13")  # Saturday 11.7. → Monday, before the holidays
        summer = compute("schkg", {"days": 10}, "2026-07-08")
        self.assertEqual(summer[0], "2026-08-05")  # ends in 15.–31.7.: third working day after (1.8. a Saturday and the federal holiday)
        self.assertIn("Betreibungsferien", summer[1])
        self.assertEqual(compute("schkg", {"days": 10}, "2026-03-25")[0], "2026-04-15")  # Easter 5.4.2026: holidays 29.3.–12.4.
        christmas = compute("schkg", {"days": 10}, "2026-12-10")
        self.assertEqual(christmas[0], "prüfen")  # holidays to 1.1., and 2 January is a holiday in many cantons
        self.assertEqual(compute("schkg", {"days": 10}, "2026-07-20", served=True)[0], "prüfen")  # served during the holidays (Art. 56 SchKG)
        self.assertEqual(compute("schkg-klage", {"days": 20}, "2026-07-10")[0], "2026-08-31")  # Art. 56 Abs. 2 SchKG, Art. 145 Abs. 4 ZPO

    def test_a_fine_and_a_cantonal_period_say_pruefen_with_the_reason(self):
        fine = compute("obg", {"days": 30}, "2026-09-03")
        self.assertEqual(fine[0], "prüfen")
        self.assertIn("Ordnungsbussengesetz nennt keine Regel", fine[1])
        cantonal = compute("kantonal", "kantonal", "2026-09-03", {"r": "30 Tage"}, period_from="r", period_from_label="Frist laut Rechtsmittelbelehrung")
        self.assertEqual(cantonal[0], "prüfen")
        self.assertIn("Frist laut Rechtsmittelbelehrung «30 Tage»", cantonal[1])

    def test_a_stored_deadline_without_its_rule_counts_by_the_code_of_obligations(self):
        d = {"id": "d", "title": "T", "trigger": "t", "period": {"days": 30}, "basis": "Art. 273 Abs. 1 OR", "missed": "m"}
        self.assertEqual(area.compute_deadline(d, "2026-11-03")[0], "2026-12-03")
        composed = next(x for x in area.workflow("sozialversicherung")["deadlines"] if x["id"] == "einsprache")
        self.assertEqual((composed["counting"], composed["counting_rule"]["title"].split(" ")[0]), ("atsg", "Sozialversicherungsverfahren"))


class NewAreaTests(unittest.TestCase):
    def deadlines(self, wid, triggers, facts):
        out = {}
        for d in area.workflow(wid)["deadlines"]:
            if d["trigger"] not in triggers:
                continue  # as items.build_items: no trigger date, no computed deadline (its question is asked)
            value = area.compute_deadline(d, triggers[d["trigger"]], facts)
            if value is not None:
                out[d["id"]] = value[0]
        return out

    def test_each_is_a_draft_from_the_law_routed_by_the_conditions_name(self):
        names = {"verkehr": "Strafrecht", "sozialversicherung": "Sozialversicherungsrecht", "privatversicherung": "Privatversicherungsrecht",
                 "betreibung-schuldner": "Schuldbetreibungs- und Konkursrecht"}
        for wid, name in names.items():
            w = area.workflow(wid)
            self.assertEqual((w["status"], w["area"]["label"]), ("draft", "aus dem Gesetz abgeleitet, noch nicht freigegeben"))
            self.assertTrue(w["applies_when"]["is"].startswith(name), wid)
            self.assertTrue(all(row["verified"] for row in area.load(area.AREAS / f"{wid}.json")["law"].values()), wid)

    def test_traffic_the_objection_is_computed_the_fine_and_the_licence_appeal_say_pruefen(self):
        found = self.deadlines("verkehr", {"strafbefehl_erhalten": "2026-11-06", "ordnungsbusse_erhalten": "2026-11-06", "entzug_verfuegung": "2026-11-06"},
                               {"einsprache_erhoben": False, "ordnungsbusse": True, "entzug_verfahren": True, "rechtsmittelfrist": "30 Tage"})
        self.assertEqual(found, {"einsprache_strafbefehl": "2026-11-16", "bedenkfrist": "prüfen", "beschwerde_entzug": "prüfen"})

    def test_social_insurance_objection_or_direct_appeal_by_who_decided(self):
        other = self.deadlines("sozialversicherung", {"verfuegung_erhalten": "2026-12-10"}, {"iv": False, "einsprache_erhoben": False})
        self.assertEqual(other, {"einsprache": "2027-01-25"})
        iv = self.deadlines("sozialversicherung", {"verfuegung_erhalten": "2026-12-10", "vorbescheid_erhalten": "2026-11-02"}, {"iv": True})
        self.assertEqual(iv, {"beschwerde_iv": "2027-01-25", "einwand_vorbescheid": "2026-12-02"})

    def test_private_insurance_limitation_by_kind_of_cover_and_the_claim_falls_due(self):
        found = self.deadlines("privatversicherung", {"ereignis": "2026-07-02", "angaben_vollstaendig": "2026-10-01", "klagebewilligung": "2026-11-02"},
                               {"kollektiv_taggeld": False})
        self.assertEqual(found, {"verjaehrung": "2031-07-02", "faelligkeit": "2026-10-29", "klagefrist": "prüfen"})
        self.assertEqual(self.deadlines("privatversicherung", {"ereignis": "2026-07-02"}, {"kollektiv_taggeld": True}), {"verjaehrung_taggeld": "2028-07-03"})

    def test_debt_collection_the_objection_after_service_and_the_action_after_provisional_release(self):
        found = self.deadlines("betreibung-schuldner", {"zahlungsbefehl_zugestellt": "2026-07-08", "rechtsoeffnung_eroeffnet": "2026-07-10"},
                               {"rechtsvorschlag_erhoben": False, "provisorisch": True})
        self.assertEqual(found, {"rechtsvorschlag": "2026-08-05", "aberkennungsklage": "2026-08-31"})
        served_in_holidays = self.deadlines("betreibung-schuldner", {"zahlungsbefehl_zugestellt": "2026-07-20"}, {"rechtsvorschlag_erhoben": False})
        self.assertEqual(served_in_holidays, {"rechtsvorschlag": "prüfen"})


if __name__ == "__main__":
    unittest.main()

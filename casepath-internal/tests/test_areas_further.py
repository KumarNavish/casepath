"""The further areas written from the law (damages, contract for work, inheritance, neighbours, debt collection): which statutory deadline
applies under which facts, and what is computed versus left to "prüfen"."""
import unittest

from casepath.process import area

FURTHER = ("schaden-unfall", "werkvertrag-bau", "erbrecht", "nachbarrecht", "inkasso")


def deadlines(wid, triggers, facts):
    """{deadline id: (value, rule)} for the deadlines whose condition holds under facts."""
    out = {}
    for d in area.workflow(wid)["deadlines"]:
        value = area.compute_deadline(d, triggers.get(d["trigger"]), facts)
        if value is not None:
            out[d["id"]] = value
    return out


class FurtherAreaTests(unittest.TestCase):
    def test_each_is_a_draft_from_the_law_with_every_passage_checked_and_its_near_misses_named(self):
        for wid in FURTHER:
            with self.subTest(area=wid):
                w = area.workflow(wid)
                self.assertEqual((w["status"], w["area"]["label"]), ("draft", "aus dem Gesetz abgeleitet, noch nicht freigegeben"))
                own = area.load(area.AREAS / f"{wid}.json")["law"]
                self.assertTrue(all(row["verified"] for row in own.values()))
                routing = next(f for f in w["facts"] if f["id"] == "rechtsgebiet")
                self.assertTrue(routing.get("not_this"))
                for d in w["deadlines"]:
                    self.assertIn(d["party"], ("kunde", "gegenpartei"))
                    self.assertTrue(area.cited_articles(d["basis"]) <= {(r["sr"], r["article"]) for r in w["law"].values()}, d["id"])

    def test_damages_the_long_stop_depends_on_whether_someone_was_injured(self):
        triggers = {"kenntnis": "2026-03-02", "unfalldatum": "2026-03-01"}
        things = deadlines("schaden-unfall", triggers, {"koerperverletzung": False})
        self.assertEqual(sorted(things), ["verjaehrung_absolut", "verjaehrung_relativ"])
        self.assertEqual(things["verjaehrung_relativ"][0], "2029-03-02")
        self.assertEqual(things["verjaehrung_absolut"][0], "2036-03-03")  # 1 March 2036 is a Saturday: next weekday
        people = deadlines("schaden-unfall", triggers, {"koerperverletzung": True})
        self.assertEqual(sorted(people), ["verjaehrung_absolut_koerper", "verjaehrung_relativ"])
        self.assertEqual(people["verjaehrung_absolut_koerper"][0], "2046-03-01")
        self.assertIn("Zeitpunkt der Kenntnis prüfen", people["verjaehrung_relativ"][1])

    def test_work_a_building_has_sixty_day_notices_and_five_years_a_movable_work_immediate_notice_and_two(self):
        triggers = {"abnahme": "2026-02-02", "mangel_entdeckt": "2026-05-04", "vollendung": "2026-01-30"}
        building = deadlines("werkvertrag-bau", triggers, {"unbeweglich": True, "eigentuemer": True})
        self.assertEqual({k: v[0] for k, v in building.items()},
                         {"ruege_ablieferung": "2026-04-03", "ruege_entdeckung": "2026-07-03", "verjaehrung_unbeweglich": "2031-02-03",
                          "bauhandwerkerpfand": "2026-05-30"})  # 2 Feb 2031 is a Sunday; the lien date is not moved (shift false)
        self.assertIn("fällt auf ein Wochenende, prüfen", building["bauhandwerkerpfand"][1])
        self.assertEqual(next(d for d in area.workflow("werkvertrag-bau")["deadlines"] if d["id"] == "bauhandwerkerpfand")["party"], "gegenpartei")
        movable = deadlines("werkvertrag-bau", triggers, {"unbeweglich": False, "eigentuemer": False})
        self.assertEqual({k: v[0] for k, v in movable.items()}, {"ruege_entdeckung_beweglich": "prüfen", "verjaehrung_beweglich": "2028-02-02"})

    def test_inheritance_the_disclaimer_runs_from_knowledge_of_death_or_from_the_official_notice(self):
        triggers = {"tod_bekannt": "2026-11-30", "mitteilung_verfuegung": "2026-12-15", "inventar_abschluss": None}
        legal = deadlines("erbrecht", triggers, {"eingesetzt": False, "inventar": False, "pflichtteil_verletzt": False})
        self.assertEqual({k: v[0] for k, v in legal.items()}, {"ausschlagung_gesetzlich": "2027-03-01"})  # no 30 February: the month's last day, 28 Feb 2027, a Sunday: Monday
        appointed = deadlines("erbrecht", triggers, {"eingesetzt": True, "inventar": True, "pflichtteil_verletzt": False})
        self.assertEqual(appointed["ausschlagung_eingesetzt"][0], "2027-03-15")
        self.assertEqual(appointed["ausschlagung_inventar"][0], "prüfen")  # its trigger date is not known
        self.assertNotIn("ausschlagung_gesetzlich", appointed)

    def test_neighbours_only_dispossession_has_a_federal_period(self):
        triggers = {"eingriff": "2026-06-10", "eingriff_bekannt": "2026-06-12"}
        self.assertEqual(deadlines("nachbarrecht", triggers, {"eigenmacht": False}), {})
        found = deadlines("nachbarrecht", triggers, {"eigenmacht": True})
        self.assertEqual({k: v[0] for k, v in found.items()}, {"besitz_rueckforderung": "prüfen", "besitz_klage": "2027-06-10"})

    def test_collection_limitation_runs_from_maturity_and_an_open_class_of_claim_says_pruefen(self):
        triggers = {"faelligkeit": "2026-01-31"}
        self.assertEqual({k: v[0] for k, v in deadlines("inkasso", triggers, {"fuenf_jahre": True}).items()}, {"verjaehrung_fuenf": "2031-01-31"})
        self.assertEqual({k: v[0] for k, v in deadlines("inkasso", triggers, {"fuenf_jahre": False}).items()}, {"verjaehrung_zehn": "2036-01-31"})
        both = deadlines("inkasso", triggers, {})
        self.assertEqual(sorted(both), ["verjaehrung_fuenf", "verjaehrung_zehn"])
        self.assertTrue(all("noch offenen Voraussetzung, prüfen" in rule for _, rule in both.values()))


if __name__ == "__main__":
    unittest.main()

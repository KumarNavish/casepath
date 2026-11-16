"""The claims model (casepath/process/claims.py): what a later statement does to a claimed cost, decided by code from the
relation the reader names, the scope it records and the day it was said. Words locate a candidate, never decide."""
import unittest

from casepath.process import claims


def claim(amount="CHF 85", stated="2026-09-05", **more):
    return {"what": "Stromkosten für den Bautrockner", "amount": amount, "role": "requested", "checked": True, "stated": stated,
            "citations": [{"file": "f", "quote": f"… {amount} …"}], **more}


FIRST = [claim()]


class MergeTests(unittest.TestCase):
    def one(self, statement, start=FIRST):
        return claims.merge(start, [statement])

    def test_an_amendment_named_by_the_reader_is_a_new_version_with_the_old_one_kept(self):
        out, changes = self.one(claim("CHF 120", "2026-10-05", relation="amends", claim="c1"))
        c1, = out
        self.assertEqual((c1["id"], c1["version"], c1["amount"], c1["stated"], c1["state"]), ("c1", 2, "CHF 120", "2026-10-05", "current"))
        self.assertEqual([(h["version"], h["amount"], h["until"], h["citations"][0]["quote"]) for h in c1["history"]], [(1, "CHF 85", "amended", "… CHF 85 …")])
        self.assertEqual([(c["kind"], c["before"], c["after"]) for c in changes], [("amended", "CHF 85", "CHF 120")])

    def test_a_statement_made_before_the_current_version_is_history_whatever_day_it_arrives(self):
        amended, _ = self.one(claim("CHF 120", "2026-10-05", relation="amends", claim="c1"))
        for relation in ("amends", "new"):
            out, changes = claims.merge(amended, [claim("CHF 85", "2026-09-20", relation=relation, claim="c1" if relation == "amends" else "")])
            self.assertEqual((len(out), out[0]["amount"], out[0]["version"], out[0]["history"][-1]["until"], changes[0]["kind"]), (1, "CHF 120", 2, "earlier", "earlier"))

    def test_said_again_changes_nothing(self):
        out, changes = self.one(claim("CHF 85.40", "2026-10-05"))  # within a franc: the same amount, said more exactly
        self.assertEqual((len(out), out[0]["version"], changes), (1, 1, []))

    def test_another_amount_without_a_relation_is_one_question_beside_the_claim(self):
        out, changes = self.one(claim("CHF 120", "2026-10-05"))
        self.assertEqual([(c["id"], c["state"], c.get("of"), c["amount"]) for c in out], [("c1", "current", None, "CHF 85"), ("c2", "unclear", "c1", "CHF 120")])
        self.assertEqual((list(claims.contested(out)), changes[0]["kind"]), (["c1"], "unclear"))
        again, more = claims.merge(out, [claim("CHF 120", "2026-10-06")])
        self.assertEqual((len(again), more), (2, []))  # the same unclear statement again: still one question

    def test_another_period_or_number_is_another_claim(self):
        september = [claim(period={"from": "2026-08-06", "to": "2026-09-03"}, transaction="R-1")]
        out, changes = claims.merge(september, [claim("CHF 40", "2026-10-20", period={"from": "2026-09-04", "to": "2026-10-03"})])
        self.assertEqual(([(c["id"], c["state"], c["amount"]) for c in out], changes[0]["kind"]), ([("c1", "current", "CHF 85"), ("c2", "current", "CHF 40")], "added"))
        out, _ = claims.merge(september, [claim("CHF 40", "2026-10-20", transaction="R-2")])
        self.assertEqual([c["state"] for c in out], ["current", "current"])
        # a period that began only after the first claim was made is not that claim's cost
        out, _ = claims.merge(FIRST, [claim("CHF 40", "2026-11-02", period={"from": "2026-10-01", "to": "2026-10-31"})])
        self.assertEqual([c["state"] for c in out], ["current", "current"])

    def test_a_withdrawal_keeps_the_claim_and_stops_asking_it(self):
        out, changes = self.one({"what": "Stromkosten", "relation": "withdraws", "claim": "c1", "stated": "2026-10-05", "citations": [{"file": "g", "quote": "ziehe zurück"}]})
        c1, = out
        self.assertEqual((c1["state"], c1["checked"], claims.live(c1), c1["withdrawn"]["stated"], c1["history"][0]["amount"], changes[0]["kind"]),
                         ("withdrawn", False, False, "2026-10-05", "CHF 85", "withdrawn"))
        later, _ = claims.merge(out, [claim("CHF 60", "2026-11-01")])  # claimed anew afterwards: its own claim, the withdrawn one stays
        self.assertEqual([(c["id"], c["state"]) for c in later], [("c1", "withdrawn"), ("c2", "current")])

    def test_a_further_cost_joins_the_claims(self):
        out, changes = self.one({**claim("CHF 300", "2026-10-05"), "what": "Reinigung des Teppichs"})
        self.assertEqual(([c["id"] for c in out], changes[0]["kind"]), (["c1", "c2"], "added"))


class EffectiveTests(unittest.TestCase):
    UNCLEAR = claims.merge(FIRST, [claim("CHF 120", "2026-10-05")])[0]

    def settle(self, how):
        return claims.effective(self.UNCLEAR, [{"op": "set_claim", "args": {"claim": "c2", "as": how}, "by": "N. Kumar", "at": "2026-11-16T08:00:00+00:00", "id": "ed1"}])

    def test_the_handlers_answer_settles_the_unclear_statement(self):
        c1, c2 = self.settle("amendment")
        self.assertEqual((c1["amount"], c1["version"], c1["history"][0]["amount"], c2["state"], c2["settled"]["by"]), ("CHF 120", 2, "CHF 85", "merged", "N. Kumar"))
        c1, c2 = self.settle("additional")
        self.assertEqual((c1["amount"], c1["version"], c2["state"], c2["checked"]), ("CHF 85", 1, "current", True))
        c1, c2 = self.settle("dismissed")
        self.assertEqual((c1["amount"], c2["state"], claims.contested([c1, c2])), ("CHF 85", "dismissed", {}))

    def test_an_answer_applies_once_and_an_undone_one_not_at_all(self):
        edit = {"op": "set_claim", "args": {"claim": "c2", "as": "amendment"}, "id": "ed1"}
        once = claims.effective(self.UNCLEAR, [edit])
        self.assertEqual(claims.effective(once, [edit]), once)
        self.assertEqual(claims.effective(self.UNCLEAR, [{**edit, "status": "undone"}])[1]["state"], "unclear")

    def test_a_claim_recorded_before_versions_is_version_one(self):
        old = [{"what": "Stromkosten", "amount": "CHF 85", "checked": True}]
        self.assertEqual([(c["id"], c["version"], c["state"], c["history"]) for c in claims.normalized(old)], [("c1", 1, "current", [])])
        self.assertEqual(claims.line(claims.normalized(old)[0]), "c1 · v1 · Stromkosten · CHF 85 · requested")


if __name__ == "__main__":
    unittest.main()

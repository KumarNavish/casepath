"""The lifecycle test bed as a ratchet: twelve invented whole files on the paths after the first request, labelled with
what the insurer did at each point, replayed without a model from a scripted correct reading (tests/phased.py,
quality/points.py). The counts may only go up: a rule change that prepares the handler's action at fewer points fails
here, and one that gains a point raises the floor in the same change.

What it shows: given a correct reading, how often the deciding code prepares the labelled action (its kind, and a
letter ready on the right day). What it does not show: whether a model reads a real file this way, or whether the
labels are how Protekta would act (they are the developers', from the paths seen in seven development files)."""
import json
import unittest

from casepath.quality import points
from tests import phased

NAMES = sorted(p.stem for p in phased.FIXTURES.glob("l[0-9][0-9]_*.json")) + ["mandate_course"]
# the floor: kind right, ready and follow-up dates within seven days, of the letter points
FLOOR = {"kind_ok": 63, "ready": 49, "dates": 29}


class LifecycleReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        desk = phased.Desk()
        try:
            for name in NAMES:
                case = phased.load(name)
                case_id = desk.prepare(case)
                labels = points.check_case(desk.store, desk.catalogue, case_id, {**case["labels"], "case": case_id})
                desk.store.save_labels(case_id, labels, "test")
            cls.out = points.table(desk.store, desk.catalogue)
        finally:
            desk.close()

    def test_the_set_is_whole(self):
        self.assertEqual(len(NAMES), 13)
        summary = self.out["summary"]
        self.assertEqual((summary["points"], summary["letters"], summary["errors"], self.out["model_calls"]), (83, 72, 0, 0))

    def test_the_prepared_action_is_the_labelled_one_at_no_fewer_points_than_before(self):
        summary = self.out["summary"]
        got = {"kind_ok": summary["narrow"]["kind_ok"], "ready": summary["narrow"]["ready"], "dates": summary["dates"]["within"]}
        for key, floor in FLOOR.items():
            self.assertGreaterEqual(got[key], floor, f"{key}: {got[key]} of {summary['narrow']['of']} (floor {floor})")
        self.assertEqual(got, FLOOR, "a gain: raise FLOOR with the change that made it " + json.dumps(got))

    def test_an_offer_is_put_to_the_customer_first_and_a_settled_matter_has_its_closing_letter(self):
        """Internal points: the call with the customer before the answer to the other side (it was the answer at once).
        Letters: a step the process leaves without a form is written where its content stands (process/live.py)."""
        summary = self.out["summary"]
        self.assertEqual(summary["kind_right_internal"]["A2"], [6, 9])  # it was 2 of 9
        rows = {(r["dossier"], r["n"]): r for r in self.out["rows"]}
        for key in (("L12", 3), ("L12", 5), ("L09", 4), ("L03", 6)):
            self.assertEqual((rows[key]["label"], rows[key]["kind"]), ("A2", "A2"), key)
        self.assertLessEqual(summary["accept"]["no_draft"], 23)  # it was 32 of 72 letter points without any draft
        closing = [r for r in self.out["rows"] if not r["internal"] and r["accept"].get("form") == "A12_erledigt"]
        self.assertTrue(closing and all(r["accept"]["draft"] for r in closing))

    def test_the_points_gained_by_the_ledger_rules(self):
        """A partial answer gets the question back; the follow-up is prepared on the day it falls due."""
        rows = {(r["dossier"], r["n"]): r for r in self.out["rows"]}
        for key, kind in ((("L02", 2), "A4"), (("L10", 2), "A4"), (("L01", 4), "A7"), (("L01", 5), "A12")):
            self.assertEqual((rows[key]["label"], rows[key]["kind"], rows[key]["kind_ok"]), (kind, kind, True), key)


if __name__ == "__main__":
    unittest.main()

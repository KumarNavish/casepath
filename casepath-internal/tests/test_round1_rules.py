import unittest

from casepath.agents.team import _fact_value, computed_deadline
from casepath.process import casegraph


class FactValueTests(unittest.TestCase):
    def test_a_date_keeps_the_precision_the_file_states(self):
        date = {"type": "date"}
        for value in ("2023-06-01", "2023-06", "2023"):
            self.assertEqual(_fact_value(date, value), (value, None))
        self.assertIsNone(_fact_value(date, "Juni 23")[0])
        self.assertIsNone(_fact_value(date, "none")[0])  # only a deadline may be "none"

    def test_a_deadline_may_be_none_or_a_stated_period_never_a_computed_fact(self):
        deadline = {"type": "date", "deadline": True}
        self.assertEqual(_fact_value(deadline, "None"), ("none", None))
        self.assertEqual(_fact_value(deadline, "14 days from 2024-08-14"), ("14 days from 2024-08-14", None))
        self.assertEqual(computed_deadline("14 days from 2024-08-14"), "2024-08-28")
        self.assertEqual(computed_deadline("1 months from 2024-01-31"), "2024-02-29")
        self.assertIsNone(computed_deadline("2024-08-28"))


class WholeNeedTests(unittest.TestCase):
    def test_a_need_for_all_of_something_stays_asked_and_shows_what_is_there(self):
        graph = {"documents": [{"id": "korr", "title": "Sämtliche Korrespondenz mit der Verwaltung"},
                               {"id": "vertrag", "title": "Mietvertrag"}]}
        findings = {"korr": {"status": "present", "files": ["f1"]}, "vertrag": {"status": "present", "files": ["f2"]}}
        asked, partial = casegraph.whole_findings(graph, findings)
        self.assertEqual((list(asked), list(partial)), (["vertrag"], ["korr"]))
        evaluation = casegraph.mark_partial({"documents": [{"document": "korr"}, {"document": "vertrag"}]}, partial)
        self.assertEqual(evaluation["documents"][0]["partial"]["files"], ["f1"])
        self.assertNotIn("partial", evaluation["documents"][1])


if __name__ == "__main__":
    unittest.main()

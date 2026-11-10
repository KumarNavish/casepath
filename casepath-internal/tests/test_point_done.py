import unittest


class PointDoneTests(unittest.TestCase):
    def test_the_feedback_target_accepts_a_settled_point(self):
        from casepath.web.app import Feedback
        row = Feedback(target="point:request.3", verdict="done")
        self.assertEqual(row.verdict, "done")
        with self.assertRaises(Exception):
            Feedback(target="point:has spaces", verdict="done")

    def test_the_scorecard_counts_settled_points_apart_from_ratings(self):
        from casepath.quality.scorecard import _feedback
        rows = [{"target": "point:request.3", "verdict": "done"}, {"target": "fact:frist", "verdict": "wrong"}]
        self.assertEqual(_feedback(rows), {"point": {"done": 1}, "fact": {"correct": 0, "wrong": 1}})


if __name__ == "__main__":
    unittest.main()

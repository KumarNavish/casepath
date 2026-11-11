import tempfile
import unittest
from pathlib import Path

from casepath.web.store import CaseStore


class EventLogTests(unittest.TestCase):
    def test_events_append_in_order_per_case_and_go_with_the_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CaseStore(Path(tmp))
            a, b = store.create_case("A", {}, "u"), store.create_case("B", {}, "u")
            first = store.append_case_event(a["id"], {"schema": "casepath.study.event/1", "kind": "case.opened"})
            store.append_case_event(b["id"], {"schema": "casepath.study.event/1", "kind": "case.opened"})
            second = store.append_case_event(a["id"], {"schema": "casepath.study.event/1", "kind": "note.added", "item_id": "fact:frist"})
            self.assertEqual([e["seq"] for e in store.list_case_events(a["id"])], [1, 2])
            self.assertNotEqual(first["event_id"], second["event_id"])
            self.assertTrue(all(e["schema"] == "casepath.study.event/1" for e in store.list_case_events(a["id"])))
            store.delete_case(a["id"], "u")
            self.assertEqual(len(store.list_case_events(b["id"])), 1)
            store.close()


if __name__ == "__main__":
    unittest.main()

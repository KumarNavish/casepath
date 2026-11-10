import tempfile
import unittest
from pathlib import Path

from casepath.process import casegraph, knowledge, workflows
from casepath.web.store import CaseStore


def _workflow():
    return {"format": "casepath.workflow/1", "id": "fam", "version": "1", "title": "T", "status": "draft",
            "sources": [{"id": "diagram", "kind": "process_diagram", "title": "D", "locator": "x"}], "applies_when": True,
            "facts": [{"id": "ok", "type": "boolean", "question": "Ok?", "source_refs": ["diagram#1"]}],
            "start": "a",
            "steps": [{"id": "a", "title": "A", "role": None, "source_refs": ["diagram#1"], "documents": [],
                       "next": [{"to": "b", "label": None, "when": {"fact": "ok", "is": True}}]},
                      {"id": "b", "title": "B", "role": None, "source_refs": ["diagram#2"], "documents": ["vertrag"], "next": []}],
            "documents": [{"id": "vertrag", "title": "Vertrag", "why": "w", "source_refs": ["diagram#2"]}],
            "outcomes": [], "notes": [], "summary": [], "open_questions": []}


class KnowledgeSeedTests(unittest.TestCase):
    def test_the_build_items_are_added_once_and_a_reviewers_change_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CaseStore(Path(tmp))
            first = knowledge.seed(store, {"osm-mold"})
            self.assertGreaterEqual(first, 3)
            item = store.get_knowledge("know-seed-mold-mietvertrag")
            self.assertEqual(item["status"], "active")
            store.save_knowledge({**item, "status": "retired"})
            self.assertEqual(knowledge.seed(store, {"osm-mold"}), 0)
            self.assertEqual(knowledge.seed(CaseStore(Path(tmp) / "other"), {"osm-loan"}), 0)
            self.assertEqual(store.get_knowledge("know-seed-mold-mietvertrag")["status"], "retired")
            store.close()

    def test_an_item_that_replaces_a_later_step_need_makes_it_a_need_of_the_whole_case(self):
        base = _workflow()
        before = workflows.evaluate(base, {}, {}, checked=True)
        self.assertEqual([d["required"] for d in before["documents"]], ["depends"])
        item = {"id": "k1", "family": "fam", "kind": "document_need", "status": "active", "version": 1, "origin": {},
                "applies_when": None, "content": {"title": "Vertrag inkl. AGB", "why": "w", "replaces": "vertrag"}}
        graph, applied = casegraph.build(base, knowledge=[item])
        self.assertTrue(applied["knowledge"][0]["replaced"])
        after = workflows.evaluate(graph, {}, {}, checked=True)
        self.assertEqual([(d["document"], d["required"], d["title"]) for d in after["documents"]],
                         [("vertrag", "yes", "Vertrag inkl. AGB")])

    def test_a_candidate_never_changes_the_process_own_need(self):
        item = {"id": "k1", "family": "fam", "kind": "document_need", "status": "candidate", "version": 1, "origin": {},
                "applies_when": None, "content": {"title": "X", "why": "w", "replaces": "vertrag"}}
        graph, applied = casegraph.build(_workflow(), knowledge=[item])
        self.assertFalse(applied["knowledge"][0]["applied"])
        self.assertEqual(graph["documents"][0]["title"], "Vertrag")


if __name__ == "__main__":
    unittest.main()

import unittest

from casepath.process import casegraph


def graph():
    return {"format": "casepath.workflow/1", "id": "w", "version": "1", "title": "W", "status": "draft", "start": "a", "facts": [], "outcomes": [], "sources": [{"id": "diagram", "kind": "process_diagram", "title": "d"}],
            "steps": [{"id": "a", "title": "A", "source_refs": ["diagram"], "documents": ["mietvertrag"], "next": []}],
            "documents": [{"id": "mietvertrag", "title": "Mietvertrag inkl. allgemeiner Vertragsbedingungen", "why": "w", "required_when": True,
                           "source_refs": ["diagram"]},
                          {"id": "korr", "title": "Sämtliche Korrespondenz mit der Verwaltung", "why": "w", "required_when": True,
                           "source_refs": ["diagram"]}]}


class MergeRestatedTests(unittest.TestCase):
    def test_a_need_an_edit_restates_becomes_one_row_with_both_origins(self):
        edits = [{"id": "pb1", "op": "add_document", "args": {"title": "Mietvertrag inkl. Änderungen", "why": "Art. 253 OR", "legal_basis": "Art. 253 OR", "step": "a"}},
                 {"id": "pb2", "op": "add_document", "args": {"title": "Bisherige Korrespondenz mit der Verwaltung", "why": "w"}},
                 {"id": "pb3", "op": "add_document", "args": {"title": "Messprotokoll des Experten", "why": "w"}}]
        built, report = casegraph.build(graph(), edits=edits)
        self.assertEqual([d["id"] for d in built["documents"]], ["mietvertrag", "korr", "e-pb3"])
        self.assertIn("edit#pb1", built["documents"][0]["source_refs"])
        self.assertEqual(built["documents"][0]["legal_basis"], "Art. 253 OR")
        self.assertEqual(report["merged"], [{"document": "e-pb1", "into": "mietvertrag"}, {"document": "e-pb2", "into": "korr"}])
        self.assertEqual(built["steps"][0]["documents"], ["mietvertrag"])


if __name__ == "__main__":
    unittest.main()

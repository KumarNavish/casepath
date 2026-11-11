import copy
import unittest

from casepath.process import items as it


def graph():
    return {"facts": [{"id": "login", "question": "Login?", "source_refs": ["diagram#n3"]},
                      {"id": "notified", "question": "Gemeldet?", "source_refs": ["diagram#n8"]}],
            "steps": [{"id": "n3", "title": "Login?", "role": "Entscheidung", "source_refs": ["diagram#n3"],
                       "next": [{"to": "n4", "when": {"fact": "login", "is": "Ja"}}, {"to": "n4", "when": {"fact": "login", "is": "Nein"}}]},
                      {"id": "n4", "title": "Angaben", "role": "User/VN", "source_refs": ["diagram#n4"], "next": [{"to": "n8", "when": True}]},
                      {"id": "n8", "title": "Gemeldet?", "role": "Entscheidung", "source_refs": ["diagram#n8"],
                       "next": [{"to": "n9", "when": {"fact": "notified", "is": True}}]},
                      {"id": "n9", "title": "Prüfen", "role": "KI/System", "source_refs": ["diagram#n9"], "next": []}],
            "documents": [{"id": "korr", "title": "Sämtliche Korrespondenz", "includes": ["ruege"], "legal_basis": "Art. 257g OR"},
                          {"id": "ruege", "title": "Mängelrüge"}]}


def evaluation(required="yes"):
    return {"path": [{"step": "n3", "state": "passed", "title": "Login?"}], "current": {"step": "n8"}, "outcome": None,
            "waiting_for": [{"fact": "notified", "question": "Gemeldet?"}], "next_actions": [],
            "documents": [{"document": "korr", "title": "Sämtliche Korrespondenz", "status": "missing", "required": required, "step": "n8", "citations": []},
                          {"document": "ruege", "title": "Mängelrüge", "status": "missing", "required": "yes", "step": "n8", "citations": []}]}


RESULT = {"answer": "Die Mängelrüge fehlt noch.", "facts": [{"fact": "login", "status": "unknown", "value": None},
                    {"fact": "notified", "status": "established", "value": "5 years before 2024-09-05", "verdict": "accepted", "citations": []}]}


class ItemTests(unittest.TestCase):
    def test_one_list_with_stable_ids_customer_facts_parts_and_one_request(self):
        items = {i["item_id"]: i for i in it.build_items({"process": graph(), "evaluation": evaluation()}, RESULT)}
        self.assertTrue(items["fact:login"]["chat_only"])
        self.assertFalse(items["fact:notified"]["chat_only"])
        self.assertEqual(items["fact:notified"]["stated_as"], "computed")
        self.assertEqual((items["document:ruege"]["part_of"], items["document:korr"]["legal_basis"]), ("korr", "Art. 257g OR"))
        self.assertEqual(items["next_action:0"]["label"]["de"], "1 Unterlage(n) beim Kunden anfordern")
        self.assertEqual(set(items["step:n3"]["label"]), {"de", "en"})
        self.assertFalse(items["answer:0"]["chain"])

    def test_the_hash_follows_the_assertion_not_its_explanation(self):
        state = {"process": graph(), "evaluation": evaluation()}
        base = it.items_sha256(it.build_items(state, RESULT))
        self.assertEqual(base, it.items_sha256(it.build_items(copy.deepcopy(state), RESULT)))
        self.assertNotEqual(base, it.items_sha256(it.build_items({"process": graph(), "evaluation": evaluation("optional")}, RESULT)))
        relabelled = graph()
        relabelled["documents"][0]["legal_basis"] = "anders"
        self.assertEqual(base, it.items_sha256(it.build_items({"process": relabelled, "evaluation": evaluation()}, RESULT)))


if __name__ == "__main__":
    unittest.main()

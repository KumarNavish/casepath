"""A frozen expert-study copy keeps the item list it was frozen with (web/app.py: freeze, study-copy, study-check;
agents/runner.py case_state and agents/core.py evaluate, ``study``). A live case's requests carry stable ids («r<n>.<i>»);
a study copy's account is built by the rules of the build it was frozen with (ids by place in time order, «r1», «r2» …),
and the case it was copied from is frozen and checked by the same rules, so a further copy can still be made from it.

On the frozen synthetic copy the preview seeds (tests/episode.py seed_frozen_copy): its run holds two dated requests still
open, whose ids are in the keys of their deadline items and so in the hashed item list. Scripted and model-free."""
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.web.app import create_app
from tests import episode


class FrozenRulesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(load_settings({"CASEPATH_DATA_DIR": str(Path(self.directory.name) / "data"),
                                                           "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None))
        self.store, self.runs = self.client.app.state.store, self.client.app.state.runs

    def tearDown(self):
        self.runs.shutdown()
        self.store.close()
        self.directory.cleanup()

    def test_a_study_copy_keeps_its_hash_with_the_frozen_account_rules(self):
        source, copy = episode.seed_frozen_copy(self.store, self.runs)
        frozen = next(e for e in self.store.list_case_events(source["id"]) if e["kind"] == "study.frozen")
        dated = lambda view: sorted(i["key"] for i in view["items"] if i["kind"] == "deadline" and i.get("account"))
        shown = self.client.get(f"/api/cases/{copy['id']}").json()
        self.assertEqual((shown["items_sha256"], dated(shown)), (frozen["items_sha256"], ["konto-r7", "konto-r8"]))  # the A4's two rows, by place
        self.assertTrue(self.client.get(f"/api/cases/{copy['id']}/study-check").json()["ok"])
        live = self.client.get(f"/api/cases/{source['id']}").json()
        self.assertEqual(dated(live), ["konto-r10.0", "konto-r10.1"])  # the live case: the stable ids of the A4 (entry 10)
        self.assertNotEqual(live["items_sha256"], frozen["items_sha256"])
        # the source is checked and frozen by the copies' rules: a further expert's copy is made, a new freeze hashes the same
        second = self.client.post(f"/api/cases/{source['id']}/study-copy", json={"expert": "P2"})
        self.assertEqual(second.status_code, 201, second.text)
        self.assertTrue(self.client.get(f"/api/cases/{second.json()['id']}/study-check").json()["ok"])
        self.assertEqual(self.client.post(f"/api/cases/{source['id']}/freeze").json()["items_sha256"], frozen["items_sha256"])


if __name__ == "__main__":
    unittest.main()

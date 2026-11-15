"""Before a deploy, every frozen study case keeps its item list under the build (casepath/quality/frozen.py), and the
notebook cell that runs the check for the pilot (deploy/databricks/frozen_check.py) takes the build and a copy of the case
store from the volume and changes nothing there. Scripted and model-free.

The frozen case is synthetic (tests/fixtures/replay/three_phases.json: its run holds the account's open requests), frozen
and copied by the app's own routes, as a study is set up."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from casepath import parity
from casepath.config import load_settings
from casepath.process import account
from casepath.quality import frozen
from casepath.web.app import create_app
from tests import phased

ROOT = Path(__file__).resolve().parents[1]
CELL = ROOT / "deploy" / "databricks" / "frozen_check.py"
CONTENT = ("Brunner", "Seeblick", "Schimmel", "Mängelrüge", "Thun", "2025")


def phone_notes_ask_nothing(original):
    """A deliberately changed account rule: what the insurer asked on the phone no longer counts as asked."""
    def build(entries, graph=None):
        return original([{**e, "asks": []} if e.get("phone") else e for e in entries], graph)
    return build


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


class FrozenCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desk = phased.Desk()
        cls.case_id = cls.desk.prepare(phased.load("three_phases"))
        app = create_app(load_settings({"CASEPATH_DATA_DIR": cls.desk.directory.name, "CASEPATH_DEV_USER": "dev"}), model_factory=lambda: None,
                         store=cls.desk.store, catalogue=cls.desk.catalogue)
        cls.app, cls.client = app, TestClient(app)
        cls.frozen = cls.client.post(f"/api/cases/{cls.case_id}/freeze").json()
        cls.copy = cls.client.post(f"/api/cases/{cls.case_id}/study-copy", json={"expert": "E1"}).json()

    @classmethod
    def tearDownClass(cls):
        cls.app.state.runs.shutdown()
        cls.desk.close()

    def test_a_frozen_case_and_its_copy_are_equal_under_this_build(self):
        open_rows = [i for i in self.client.get(f"/api/cases/{self.copy['id']}").json()["items"] if i["kind"] == "stand" and i.get("open")]
        self.assertTrue(open_rows)  # the frozen run's account holds an open request: an account rule shapes the item list
        self.assertEqual(frozen.check(self.desk.store, self.desk.catalogue), {self.copy["id"]: "equal", self.case_id: "equal"})
        self.assertTrue(self.client.get(f"/api/cases/{self.copy['id']}/study-check").json()["ok"])  # the app says the same
        out = frozen.receipt(self.desk.store, self.desk.catalogue, "0123456789ab")
        self.assertEqual((out["format"], out["build"], out["model_calls"], out["why"]), ("casepath.frozen-check/1", "0123456789ab", 0, {}))
        self.assertEqual(out["kinds"], {self.copy["id"]: "copy", self.case_id: "frozen"})
        self.assertEqual(out["counts"], {"cases": 2, "frozen": 1, "copies": 1, "equal": 2, "unequal": 0})
        self.assertEqual(frozen.lines(out)[-1], "deploy: the frozen study is unchanged")
        text = json.dumps(out, ensure_ascii=False)
        self.assertFalse([w for w in CONTENT if w in text])  # ids, enums and counts only

    def test_a_changed_account_rule_makes_both_unequal_and_says_why(self):
        with mock.patch.object(account, "build", phone_notes_ask_nothing(account.build)):
            self.assertEqual(frozen.check(self.desk.store, self.desk.catalogue), {self.copy["id"]: "unequal", self.case_id: "unequal"})
            self.assertFalse(self.client.get(f"/api/cases/{self.copy['id']}/study-check").json()["ok"])  # a session would not start
            out = frozen.receipt(self.desk.store, self.desk.catalogue, "0123456789ab")
        self.assertEqual(out["why"], {self.copy["id"]: "items_differ", self.case_id: "items_differ"})
        self.assertEqual(out["counts"]["unequal"], 2)
        self.assertEqual(frozen.lines(out)[-1], "deploy: no, fix the difference first")
        self.assertEqual(frozen.check(self.desk.store, self.desk.catalogue)[self.copy["id"]], "equal")  # the rule restored

    def test_another_run_or_another_process_version_is_named_as_study_mismatch_orders_them(self):
        want = self.copy["intake"]["study"]
        mismatch = lambda **changed: frozen.mismatch(self.desk.store, self.desk.catalogue, self.copy["id"], {**want, **changed})
        self.assertIsNone(mismatch())
        self.assertEqual(mismatch(frozen_run_id="run_elsewhere"), "run_missing")
        self.assertEqual(mismatch(workflow_version="2026-01-01.1"), "version_differs")
        self.assertEqual(mismatch(items_sha256="0" * 64), "items_differ")
        empty = phased.Desk()
        try:
            self.assertEqual((frozen.check(empty.store, empty.catalogue), frozen.lines(frozen.receipt(empty.store, empty.catalogue, "x1"))[-1]),
                             ({}, "no frozen case and no study copy in this store"))
        finally:
            empty.close()

    def test_the_notebook_cell_refuses_a_malformed_phrase_and_a_build_that_differs(self):
        cell = runpy.run_path(str(CELL))  # no dbutils: only its functions
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / "casepath-app-abc1234" / "casepath-app"
            build.mkdir(parents=True)
            (build / "app.yaml").write_text("filled in on deploy\n")
            (build / "x.txt").write_text("x\n")
            for phrase in ("", "deploy abc1234 1 0123456789ab", "frozen abc1234 1"):
                with self.assertRaisesRegex(AssertionError, "check must read"):
                    cell["check"](tmp, phrase)
            with self.assertRaisesRegex(AssertionError, "fill in VOLUME"):
                cell["check"](cell["VOLUME"], f"frozen abc1234 2 {cell['tree'](str(build))}")
            with self.assertRaisesRegex(AssertionError, "the volume copy differs"):
                cell["check"](tmp, "frozen abc1234 2 0123456789ab")
            identity = cell["tree"](str(build))
            (build / "app.yaml").write_text("other values\n")  # app.yaml is filled in per deployment: not part of the build's identity
            self.assertEqual(cell["tree"](str(build)), identity)
            with self.assertRaisesRegex(AssertionError, "no case store on the volume"):
                cell["check"](tmp, f"frozen abc1234 2 {cell['tree'](str(build))}")

    def test_the_notebook_cell_checks_the_build_from_the_volume_and_changes_nothing_there(self):
        """The cell as the notebook runs it, in a fresh interpreter without httpx: the package comes from the build's folder on
        the volume, the store from a copy of the volume's database; the volume's files keep their bytes."""
        cell = runpy.run_path(str(CELL))
        with tempfile.TemporaryDirectory() as tmp:
            volume = Path(tmp) / "volume"
            build = volume / "casepath-app-abc1234" / "casepath-app"
            shutil.copytree(ROOT / "casepath", build / "casepath", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (build / "app.yaml").write_text("filled in on deploy\n")
            with sqlite3.connect(Path(self.desk.directory.name) / "casepath.db") as live, sqlite3.connect(volume / "casepath.db") as target:
                live.backup(target)
            phrase = f"frozen abc1234 {len(cell['listing'](str(build)))} {cell['tree'](str(build))}"
            source = CELL.read_text(encoding="utf-8").replace('VOLUME = "FILL-IN: /Volumes/<catalog>/<schema>/<volume>"', f"VOLUME = {str(volume)!r}")
            filled = Path(tmp) / "cell.py"
            filled.write_text(source, encoding="utf-8")
            driver = "\n".join([
                "import runpy, sys",
                "class NoHttpx:",
                "    def find_spec(self, name, path=None, target=None):",
                "        if name.split('.')[0] == 'httpx':",
                "            raise ImportError('not in this notebook')",
                "sys.meta_path.insert(0, NoHttpx())",
                "class Widgets:",
                f"    def get(self, name): return {phrase!r} if name == 'check' else ''",
                "class Dbutils:",
                "    widgets = Widgets()",
                f"runpy.run_path({str(filled)!r}, init_globals={{'dbutils': Dbutils()}}, run_name='__main__')",
                "print('httpx stub left:', 'httpx' in sys.modules)"])
            before, source_tree = snapshot(volume), parity.source_tree(build / "casepath")[0][:12]
            done = subprocess.run([sys.executable, "-I", "-c", driver], cwd=tmp, capture_output=True, text=True, timeout=300,
                                  env={k: v for k, v in os.environ.items() if not k.startswith("CASEPATH_")})
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            self.assertEqual(snapshot(volume), before)
        printed = done.stdout.strip().splitlines()
        self.assertEqual(printed[-1], "httpx stub left: False")
        out = json.loads(printed[-2])
        self.assertEqual(out["cases"], {self.copy["id"]: "equal", self.case_id: "equal"})
        self.assertEqual((out["build"], out["source"]), (phrase.split()[-1], source_tree))
        self.assertIn(f"{self.case_id} frozen equal", printed)
        self.assertIn("deploy: the frozen study is unchanged", printed)


if __name__ == "__main__":
    unittest.main()

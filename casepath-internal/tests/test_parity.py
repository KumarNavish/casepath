import json
from pathlib import Path
import tempfile
import unittest

from casepath import parity
from casepath.config import load_settings


class ParityTests(unittest.TestCase):
    def test_the_tree_hash_follows_the_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.py").write_text("x = 1\n")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "a.cpython.pyc").write_bytes(b"cache")
            first, count = parity.source_tree(root)
            self.assertEqual(count, 1)
            self.assertEqual(parity.source_tree(root)[0], first)
            (root / "a.py").write_text("x = 2\n")
            self.assertNotEqual(parity.source_tree(root)[0], first)

    def test_the_manifest_names_workflows_model_and_changed_settings(self):
        settings = load_settings({"CASEPATH_ORGANISATION": "Example Insurance", "CASEPATH_RUN_WORKERS": "1",
                                  "CASEPATH_MODEL_PROVIDER": "databricks", "CASEPATH_MODEL_ENDPOINT": "https://gateway.example",
                                  "CASEPATH_MODEL": "some-model", "CASEPATH_MODEL_GATEWAY_HOSTS": "gateway.example"})
        out = parity.manifest(settings, catalogue_dir=Path(__file__).parent / "fixtures",
                              knowledge=[{"id": "know_1", "version": 2, "status": "active", "content": {"title": "x"}}])
        self.assertIn("example-defect.json", out["workflows"])
        self.assertEqual(out["model"]["name"], "some-model")
        self.assertEqual(out["settings_not_default"]["organisation"], "Example Insurance")
        self.assertEqual(out["settings_not_default"]["run_workers"], 1)
        self.assertEqual(out["knowledge"]["know_1"]["version"], 2)
        self.assertNotIn("data_dir", out["settings_not_default"])
        json.dumps(out, default=str)


if __name__ == "__main__":
    unittest.main()


class InstalledCopyTests(unittest.TestCase):
    def test_an_installed_copy_hashes_like_the_checkout(self):
        import importlib.util
        import shutil
        import subprocess
        import sys
        if importlib.util.find_spec("setuptools") is None:
            self.skipTest("setuptools is needed to build the package")
        project = Path(parity.PACKAGE).parent
        with tempfile.TemporaryDirectory() as d:
            src, site = Path(d) / "src", Path(d) / "site"
            shutil.copytree(project, src, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".git", "build", "*.egg-info"))
            done = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--no-build-isolation",
                                   "--target", str(site), str(src)], capture_output=True, text=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            installed = site / "casepath"
            self.assertTrue((installed / "web" / "ui" / "assets" / "fonts").is_dir(), "the interface fonts must be installed")
            self.assertEqual(parity.source_tree(installed), parity.source_tree())

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import uvicorn

from casepath_internal import batch
from casepath_internal.app import create_app
from casepath_internal.config import load_settings
from casepath_internal.synthetic import render_digital
from tests.test_synthetic import CASE, document

FIXTURES = Path(__file__).parent / "fixtures"


class BatchTests(unittest.TestCase):
    def test_import_and_next_against_a_running_app(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as folder:
            Path(folder, "8017.0001.0001_geschwaerzt.pdf").write_bytes(render_digital(document(), CASE))
            app = create_app(load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_WORKFLOW_CATALOGUE": str(FIXTURES), "CASEPATH_DEV_USER": "dev"}),
                             model_factory=lambda: None)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8791, log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            while not server.started:
                pass
            url = "http://127.0.0.1:8791"
            with mock.patch("sys.stdout") as out:
                batch.import_folder(url, folder)
                batch.import_folder(url, folder)
                batch.run_next(url, poll=0.05)
                batch.run_next(url, poll=0.05)
                batch.retry(url, "example-defect", poll=0.05)
            printed = [json.loads(c.args[0]) for c in out.write.call_args_list if c.args[0].strip()]
            cases = batch.call(url, "/api/cases")["cases"]
            server.should_exit = True
            thread.join(5)
            self.assertEqual(printed[0]["imported"], 1)
            self.assertEqual(printed[1]["imported"], 0)
            self.assertEqual((printed[2]["status"], printed[2]["error_kind"], printed[2]["pages"]), ("failed", "model_not_configured", 1))
            self.assertIsNone(printed[3]["next"])
            self.assertEqual(printed[4]["status"], "failed")  # retried, still without a model
            self.assertEqual(cases[0]["workflow_id"], "example-defect")
            self.assertNotIn("Badezimmer", json.dumps(printed))


class TraceTests(unittest.TestCase):
    def test_trace_breaks_a_run_down_by_agent_and_by_id_without_content(self):
        from casepath_internal.extract import extract
        from tests.scripted import ScriptedModel
        from tests.test_app import EMAIL, finder, team_script
        with tempfile.TemporaryDirectory() as data:
            app = create_app(load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_WORKFLOW_CATALOGUE": str(FIXTURES), "CASEPATH_DEV_USER": "dev"}),
                             model_factory=lambda: None)
            store = app.state.store
            case = store.create_case("Trace", {}, "dev")
            row = extract("message.eml", "message/rfc822", EMAIL)
            added = store.add_file(case["id"], "message.eml", row["media_type"], row["kind"], EMAIL, row, "dev")
            store.select_workflow(case["id"], "example-defect", "2026-01-01", "dev")
            app.state.runs.model_factory = lambda: ScriptedModel(team_script(added["id"], finder_calls=[
                finder(added["id"], "customer_message", "Ich habe den Vermieter am 2. März schriftlich informiert.")]))
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8792, log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            while not server.started:
                pass
            url = "http://127.0.0.1:8792"
            with mock.patch("sys.stdout") as out:
                batch.run_next(url, poll=0.05)
                batch.trace(url, case["id"][-8:])
                batch.prepare(url, batch.find_case(url, case["id"][-8:]), 0.05)
            server.should_exit = True
            thread.join(5)
            writes = [c.args[0] for c in out.write.call_args_list]
            card = json.loads("".join(writes[1:-2]))
            self.assertEqual(json.loads(writes[-2])["status"], "completed")  # the rerun
            self.assertEqual(card["status"], "completed")
            self.assertEqual(card["delegations"][:2], ["claim_reader", "process_builder"])
            self.assertGreaterEqual(card["agents"]["claim_reader"]["turns"], 2)
            self.assertEqual(card["agents"]["claim_reader"]["tools"].get("record_fact"), 1)
            self.assertEqual(card["documents"]["customer_message"]["origin"], "workflow")
            self.assertEqual(card["facts"]["landlord_notified"][0], "established")
            self.assertNotIn("Vermieter", json.dumps(card))


if __name__ == "__main__":
    unittest.main()

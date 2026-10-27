"""A local preview of the workspace on synthetic data, for UI work without a model.

It seeds two made-up cases of the synthetic test workflow, runs the agent team
with a paced scripted model (so the live view can be watched), lets case A teach
a Knowledge item and activates it, and serves the app. Nothing here is Mobiliar
data or a real model run.

    python deploy/preview/preview.py [port]
"""
from pathlib import Path
import io
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from casepath_internal import knowledge as kb  # noqa: E402
from casepath_internal.app import create_app  # noqa: E402
from casepath_internal.config import load_settings  # noqa: E402
from casepath_internal.synthetic import render_digital  # noqa: E402
from tests.scripted import ScriptedModel, delegate, learn, report  # noqa: E402

from casepath_internal.examples import EMAIL, LETTER, REPLY, TOLD, VENT, photo  # noqa: E402


class Paced(ScriptedModel):
    def __init__(self, turns, pause):
        super().__init__(turns)
        self.pause = pause

    def respond(self, **kwargs):
        time.sleep(self.pause)
        return super().respond(**kwargs)

    def respond_json(self, **kwargs):
        time.sleep(self.pause)
        return super().respond_json(**kwargs)


def script(email, letter, knowledge_id=None):
    finder = [("record_document", {"document": "customer_message", "status": "present", "files": [email],
                                   "citations": [{"file": email, "quote": "Im Badezimmer meiner Wohnung bildet sich seit Dezember schwarzer Schimmel."}], "note": ""}),
              ("record_document", {"document": "notice_letter", "status": "present", "files": [letter],
                                   "citations": [{"file": letter, "quote": REPLY}], "note": "The management's reply confirms the notice."})]
    if knowledge_id:
        finder.append(("record_document", {"document": f"k-{knowledge_id}", "status": "missing" if False else "absent", "files": [], "citations": [], "note": ""}))
    return [
        [delegate("claim_reader", "Read every file and brief the case.")],
        [("list_files", {})],
        [("read_file", {"file": email, "from_page": None, "to_page": None})],
        [("read_file", {"file": letter, "from_page": None, "to_page": None})],
        [report("claim_reader", summary="Tenant reports recurring mould and says the management was told in writing.",
                request="Lea Brunner wants help because mould keeps coming back in the bathroom.",
                parties=[{"role": "tenant", "name": "Lea Brunner"}, {"role": "property management", "name": "Immo Aare AG"}],
                timeline=[{"date": "03.02.2025", "event": "Tenant tells the management in writing", "citations": [{"file": email, "quote": TOLD}]},
                          {"date": "07.02.2025", "event": "Management confirms receipt", "citations": [{"file": letter, "quote": REPLY}]}])],
        [delegate("process_builder", "Build this case's process.")],
        [("open_process", {}), ("view_knowledge", {})],
        [report("process_builder", summary="Defect process; the landlord notice decides the branch.",
                questions=[{"fact": "legal_area", "plain": "Is this a rental defect?"}, {"fact": "landlord_notified", "plain": "Was the landlord told?"}])],
        [delegate("claim_reader", "Record the facts the process asks about.")],
        [("search", {"query": "Verwaltung informiert"})],
        [("record_fact", {"fact": "legal_area", "status": "established", "value": "tenancy_defect",
                          "citations": [{"file": email, "quote": "Im Badezimmer meiner Wohnung bildet sich seit Dezember schwarzer Schimmel."}]})],
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": email, "quote": TOLD}]}),
         report("claim_reader", summary="Both facts recorded with exact quotes.")],
        [delegate("document_finder", "Match each document need to a file.")],
        [("open_process", {})],
        [*finder, report("document_finder", summary="Message and notice found; no photo text.")],
        [delegate("result_checker", "Evaluate and draft.")],
        [("evaluate", {}), report("result_checker", summary="The tenant told the management in writing; the defect can be assessed. Photos are attached but not read as text.",
                                  answer="The landlord was told in writing; assess the defect with its evidence.", open_points=["Whether the ventilation claim holds"],
                                  reply={"needed": True, "subject": "Ihre Meldung: Schimmel im Badezimmer", "clauses": [
                                      {"text": "Sie haben die Verwaltung am 3. Februar schriftlich informiert.", "basis": ["fact:landlord_notified"]},
                                      {"text": "Die Verwaltung hat den Eingang Ihrer Meldung bestätigt.", "basis": ["document:notice_letter"]}]},
                                  learn=[] if knowledge_id else [learn(title="Ventilation record", why="Mould returns despite ventilation; a record shows how the flat was aired.",
                                                                       step="assess", applies_when_text="Recurring mould where ventilation is disputed",
                                                                       citations=[{"file": email, "quote": VENT}])])],
        [("complete", {"summary": "Prepared."})],
    ]


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    data = tempfile.mkdtemp(prefix="cp-preview-")
    settings = load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_WORKFLOW_CATALOGUE": str(ROOT / "tests" / "fixtures"),
                              "CASEPATH_DEV_USER": "N. Kumar"})
    app = create_app(settings, model_factory=lambda: None)
    store, runs = app.state.store, app.state.runs

    def seed(title):
        case = store.create_case(title, {"synthetic": True}, "N. Kumar")
        from casepath_internal.extract import extract
        ids = []
        for name, kind, data_bytes in (("Meldung Lea Brunner.eml", "message/rfc822", EMAIL),
                                       ("Antwort Immo Aare AG.pdf", "application/pdf", render_digital(LETTER, {"title": title})),
                                       ("Badezimmer Aussenwand.jpg", "image/jpeg", photo())):
            row = extract(name, kind, data_bytes)
            ids.append(store.add_file(case["id"], name, row["media_type"], row["kind"], data_bytes, row, "N. Kumar")["id"])
        store.select_workflow(case["id"], "example-defect", "2026-01-01", "N. Kumar")
        return case, ids

    case_a, (email_a, letter_a, _) = seed("Schimmel im Badezimmer, Kramgasse 5")
    runs.model_factory = lambda: Paced(script(email_a, letter_a), 0.01)
    run = runs.start(case_a["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.1)
    for item in store.list_knowledge(statuses={"candidate"}):
        store.save_knowledge(kb.set_status(item, "active", by="N. Kumar", reason="Seen in two defect cases"))
    item = store.list_knowledge(statuses={"active"})[0]
    case_b, (email_b, letter_b, _) = seed("Schimmel in der Küche, Lorrainestrasse 12")
    pause = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    calls = {"n": 0}

    def factory():
        # The first run plays the whole team; later ones are re-checks after an edit.
        calls["n"] += 1
        if calls["n"] == 1:
            return Paced(script(email_b, letter_b, knowledge_id=item["id"]), pause)
        def need():
            return "e-" + runs.store.list_edits(case_b["id"])[-1]["id"]
        return Paced([[("read_file", {"file": letter_b, "from_page": None, "to_page": None})],
                      [("record_document", lambda: {"document": need(), "status": "absent", "files": [], "citations": [],
                                                    "note": "No lease is among the files."}), report("document_finder", summary="No lease among the files.")]], pause)
    runs.model_factory = factory
    print(f"preview on http://127.0.0.1:{port}  case A {case_a['id']}  case B {case_b['id']}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

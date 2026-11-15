"""A local preview of the workspace on synthetic data, for UI work without a model.

It seeds two made-up cases of the synthetic test workflow, one prepared synthetic case per shipped legal area, runs the agent team
with a paced scripted model (so the live view can be watched), lets case A teach
a Knowledge item and activates it, and serves the app. Nothing here is Mobiliar
data or a real model run.

    python deploy/preview/preview.py [port]
"""
from pathlib import Path
import io
import json
import re
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from casepath.process import knowledge as kb  # noqa: E402
from casepath.web.app import create_app  # noqa: E402
from casepath.config import load_settings  # noqa: E402
from casepath.quality.synthetic import render_digital  # noqa: E402
from tests.scripted import ScriptedModel, delegate, learn, report  # noqa: E402

from casepath.quality.examples import EMAIL, LETTER, REPLY, TOLD, VENT, photo  # noqa: E402


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
                                      {"text": "Sie haben die Verwaltung am 3. Februar schriftlich informiert.", "kind": "statement", "basis": ["fact:landlord_notified"]},
                                      {"text": "Die Verwaltung hat den Eingang Ihrer Meldung bestätigt.", "kind": "statement", "basis": ["document:notice_letter"]}]},
                                  learn=[learn(action="refine", target=knowledge_id, title="Lüftungsprotokoll mit Datum",
                                               why="Der Schimmel kam wieder; erst ein Protokoll mit Daten zeigt, wann gelüftet wurde.", step="assess",
                                               applies_when_text="Wiederkehrender Schimmel, wenn das Lüften strittig ist", reason="Ein zweiter Fall brauchte die Daten.",
                                               citations=[{"file": email, "quote": VENT}])] if knowledge_id else
                                        [learn(title="Lüftungsprotokoll", why="Der Schimmel kehrt trotz Lüften zurück; ein Protokoll zeigt, wie die Wohnung gelüftet wurde.",
                                               step="assess", applies_when_text="Wiederkehrender Schimmel, wenn das Lüften strittig ist",
                                               citations=[{"file": email, "quote": VENT}])])],
        [("complete", {"summary": "Prepared."})],
    ]


def request(text):
    """The customer's request as a brief states it: the case text without its synthetic marker and its signature."""
    sentences = re.split(r"(?<=[.?!])\s+", text)[1:-1]
    out = ""
    for sentence in sentences:
        if len(out) + len(sentence) > 300:
            break
        out = f"{out} {sentence}".strip()
    return out


def area_script(case, file_id):
    """The scripted team for one synthetic area case (tests/fixtures/areas/cases.json): routing, facts with quotes, report."""
    cite = lambda quote: [{"file": file_id, "quote": quote}]
    routing = [{"fact": "rechtsgebiet", "value": case["routing"][0], "citations": cite(case["routing"][1])}] if case["routing"] else []
    return ScriptedModel([
        [*[("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
         report("claim_reader", request=request(case["text"]))],
        [report("document_finder")],
        *[[report("result_checker", answer="Die erste Anforderung ist vorbereitet.")]] * 3,
    ], routing=routing)


def seed_areas(store, runs):
    """One prepared synthetic case per shipped area, routed and prepared by the scripted team: the breadth of the product."""
    from casepath.read.extract import extract
    cases = json.loads((ROOT / "tests" / "fixtures" / "areas" / "cases.json").read_text())
    for wid, case in cases.items():
        if wid.startswith("_"):
            continue
        title = f"{case['title']} (synthetisch)"
        made = store.create_case(title, {"synthetic": True}, "N. Kumar")
        mail = (f"From: kundin@example.ch\r\nTo: schaden@example-rechtsschutz.ch\r\nSubject: {case['title']}\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n{case['text']}\r\n").encode()
        row = extract("Schadenmeldung.eml", "message/rfc822", mail)
        file_id = store.add_file(made["id"], "Schadenmeldung.eml", row["media_type"], row["kind"], mail, row, "N. Kumar")["id"]
        runs.model_factory = lambda case=case, file_id=file_id: area_script(case, file_id)
        run = runs.start(made["id"], "N. Kumar")
        while store.get_run(run["id"])["status"] in ("queued", "running"):
            time.sleep(0.05)
        if store.get_run(run["id"])["status"] != "completed":
            print(f"area case {wid} did not complete: {store.get_run(run['id']).get('error')}", flush=True)


def key_script(case, file_id):
    """The scripted team for one case of tests/fixtures/areas/key_cases.json: routing, facts and documents with their
    quotes, and a brief with the parties and the customer's own questions."""
    cite = lambda quote: [{"file": file_id, "quote": quote}]
    return ScriptedModel([
        [*[("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
         report("claim_reader", request=case["request"], parties=[{"role": r, "name": n} for r, n in case["parties"]],
                questions=[{"question": q, "citations": cite(quote)} for q, quote in case["questions"]])],
        [*[("record_document", {"document": d, "status": "present", "files": [file_id], "citations": cite(q), "note": ""}) for d, q in case["documents"]],
         report("document_finder")],
        *[[report("result_checker", answer="Vorbereitet.")]] * 3,
    ], routing=[{"fact": "rechtsgebiet", "value": case["routing"][0], "citations": cite(case["routing"][1])}])


def seed_key_cases(store, runs):
    """The cases of key_cases.json (a dismissal during sick leave, a summons to a conciliation hearing), prepared by the
    scripted team from one e-mail each."""
    from casepath.read.extract import extract
    cases = json.loads((ROOT / "tests" / "fixtures" / "areas" / "key_cases.json").read_text())
    made = {}
    for key, case in cases.items():
        if key.startswith("_"):
            continue
        row = store.create_case(f"{case['title']} (synthetisch)", {"synthetic": True}, "N. Kumar")
        mail = (f"From: kunde@example.ch\r\nTo: schaden@example-rechtsschutz.ch\r\nSubject: {case['title']}\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n{case['text']}\r\n").encode()
        extraction = extract("Schadenmeldung.eml", "message/rfc822", mail)
        file_id = store.add_file(row["id"], "Schadenmeldung.eml", extraction["media_type"], extraction["kind"], mail, extraction, "N. Kumar")["id"]
        runs.model_factory = lambda case=case, file_id=file_id: key_script(case, file_id)
        run = runs.start(row["id"], "N. Kumar")
        while store.get_run(run["id"])["status"] in ("queued", "running"):
            time.sleep(0.05)
        if store.get_run(run["id"])["status"] != "completed":
            print(f"key case {key} did not complete: {store.get_run(run['id']).get('error')}", flush=True)
        made[key] = row
    return made


def seed_historic(store):
    """A test cut of a historic file, looked at as of a past day: the case list shows it apart, never as overdue."""
    from casepath.read.extract import extract
    case = store.create_case("Historische Akte: Darlehen, Stand am 07.02.2025 (synthetisch)", {"synthetic": True}, "N. Kumar")
    text = "SYNTHETISCHE AKTE. Ich habe Max Beispiel am 1. März 2024 CHF 5'000 geliehen; er zahlt nicht zurück. Anna Muster".encode()
    row = extract("Akte.txt", "text/plain", text)
    row["cut_of"] = {"case": None, "file": None, "as_of": "2025-02-07"}
    file_id = store.add_file(case["id"], "Akte.txt", row["media_type"], row["kind"], text, row, "N. Kumar")["id"]
    run = store.create_run(case["id"], "N. Kumar")
    fact = lambda f, v, quote: {"fact": f, "status": "established", "verdict": "accepted", "value": v, "citations": [{"file": file_id, "quote": quote}]}
    store.update_run(run["id"], status="completed", workflow_id="vertrag-darlehen", finished_at="2026-11-12T10:00:00+00:00",
                     result={"facts": [fact("rechtsgebiet", "Vertragsrecht / Darlehen", "CHF 5'000 geliehen")], "documents": [],
                             "brief": {"request": "Anna Muster will ein Darlehen von CHF 5'000 zurück.",
                                       "parties": [{"role": "Darleiherin (VN)", "name": "Anna Muster"}, {"role": "Borger", "name": "Max Beispiel"}], "timeline": []}})
    return case


COST_NOTE = ("SYNTHETISCHE AKTE. Protekta Rechtsschutz an Frau Lea Beispiel, 10. September 2026: Um die Versicherungsdeckung prüfen zu können, "
             "brauchen wir noch den Mietvertrag.\n\nProtekta Rechtsschutz an Kanzlei Muster, 1. Oktober 2026: Wir erteilen Ihnen Kostengutsprache "
             "für die Abklärung der Sach- und Rechtslage sowie aussergerichtliche Bemühungen.\n\nKanzlei Muster an Protekta Rechtsschutz, "
             "5. November 2026: Für unsere Bemühungen bis 31. Oktober 2026 stellen wir Ihnen CHF 3'200 in Rechnung (Zwischenhonorar).")


def seed_cost_note(store, runs):
    """A mandated case whose firm sent a cost note that is not paid: run through the scripted team from the file, so the
    card shows the cost claim (A11) as the prepared action with its reason and source."""
    from casepath.read.extract import extract
    case = store.create_case("Mietmangel, Kostennote der Kanzlei (synthetisch) 4321.8765.2109", {"synthetic": True}, "N. Kumar")
    row = extract("Akte Kanzlei.txt", "text/plain", COST_NOTE.encode())
    row["segments"] = [  # the reading's document list, as a read dossier has it
        {"first_page": 1, "last_page": 1, "kind": "Brief", "date": "10.09.2026", "sender": "Protekta Rechtsschutz AG", "recipient": "Lea Beispiel", "title": "Anforderung", "summary": ""},
        {"first_page": 1, "last_page": 1, "kind": "Brief", "date": "01.10.2026", "sender": "Protekta Rechtsschutz AG", "recipient": "Kanzlei Muster", "title": "Mandat", "summary": ""},
        {"first_page": 1, "last_page": 1, "kind": "Honorarnote", "date": "05.11.2026", "sender": "Kanzlei Muster", "recipient": "Protekta", "title": "Zwischenhonorar", "summary": ""}]
    file_id = store.add_file(case["id"], "Akte Kanzlei.txt", row["media_type"], row["kind"], COST_NOTE.encode(), row, "N. Kumar")["id"]
    cite = lambda quote: [{"file": file_id, "quote": quote}]
    record = lambda f, v, q: ("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)})
    runs.model_factory = lambda: ScriptedModel([
        [record("handlung_a1", "2026-09-10", "Protekta Rechtsschutz an Frau Lea Beispiel, 10. September 2026"),
         record("bisherige_handlungen", "A1 2026-09-10; A10 2026-10-01", "Wir erteilen Ihnen Kostengutsprache für die Abklärung der Sach- und Rechtslage"),
         record("eingang_kostenforderung", "Kanzlei Muster: Zwischenhonorar vom 2026-11-05 über CHF 3'200 (Bemühungen bis 31.10.2026)",
                "Für unsere Bemühungen bis 31. Oktober 2026 stellen wir Ihnen CHF 3'200 in Rechnung (Zwischenhonorar)."),
         report("claim_reader", request="Frau Beispiel lässt einen Mietmangel durch die Kanzlei Muster vertreten; deren Zwischenhonorar ist eingegangen.",
                parties=[{"role": "Mieterin (VN)", "name": "Frau Lea Beispiel"}, {"role": "beauftragte Kanzlei", "name": "Kanzlei Muster"}])],
        [report("document_finder")],
        *[[report("result_checker", answer="Die Kostennote der Kanzlei ist zu prüfen und zu begleichen.")]] * 3,
    ], routing=[{"fact": "rechtsgebiet", "value": "Mietrecht / Mangel", "citations": cite("brauchen wir noch den Mietvertrag.")}])
    run = runs.start(case["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.05)
    if store.get_run(run["id"])["status"] != "completed":
        print(f"cost note case did not complete: {store.get_run(run['id']).get('error')}", flush=True)
    return case


def seed_account(store, runs):
    """A case Protekta conducts itself, eight documents with three phone notes (tests/fixtures/account/cases.json), read by
    the scripted team into the running account: «Stand» in «Der Fall», the Verlauf as a table, the payout chased."""
    case_data = json.loads((ROOT / "tests" / "fixtures" / "account" / "cases.json").read_text())["selbst"]
    case = store.create_case(case_data["title"], {"synthetic": True}, "N. Kumar")
    extraction = {"text": case_data["text"], "pages": case_data["pages"], "readable": True, "note": "", "media_type": "text/plain", "kind": "text",
                  "segments": case_data["segments"], "cut_of": {"case": None, "file": None, "as_of": case_data["as_of"]}}
    file_id = store.add_file(case["id"], case_data["name"].replace(".pdf", ".txt"), "text/plain", "text", case_data["text"].encode(), extraction, "N. Kumar")["id"]
    store.select_workflow(case["id"], case_data["workflow"], None, "N. Kumar")
    for fact_id, value in case_data["decisions"]:
        store.add_edit(case["id"], "set_fact", {"fact": fact_id, "value": value}, "N. Kumar", "Entscheid der Fallbearbeitung")
    entries = [{**e, "file": file_id} for e in case_data["entries"]]
    cite = lambda quote: [{"file": file_id, "quote": quote}]
    runs.model_factory = lambda: ScriptedModel([
        [("list_files", {})],
        [("record_steps", {"entries": entries[:5]}), ("record_steps", {"entries": entries[5:]})]
        + [("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case_data["facts"]],
        [report("claim_reader", request="Sandra Keller verlangt wegen der ausfallenden Heizung eine Entschädigung von der Verwaltung.",
                parties=[{"role": "Mieterin (VN)", "name": "Frau Sandra Keller"}, {"role": "Verwaltung (GP)", "name": "Muster Immobilien AG"}])],
        [report("document_finder")],
        *[[report("result_checker", answer="Die vereinbarte Zahlung ist fällig und nicht bestätigt.")]] * 3,
    ])
    run = runs.start(case["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.05)
    if store.get_run(run["id"])["status"] != "completed":
        print(f"account case did not complete: {store.get_run(run['id']).get('error')}", flush=True)
    return case


def _remap(value, ids):
    """A scripted turn's file ids («fa», «fb» in the update tests) replaced by the store's."""
    if isinstance(value, dict):
        return {k: _remap(v, ids) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_remap(v, ids) for v in value)
    return ids.get(value, value) if isinstance(value, str) else value


def _text_file(store, case_id, fixture, name=None):
    """A synthetic file of the update tests, stored as text with its pages and documents, so its original opens."""
    ex = fixture["extraction"]
    extraction = {**ex, "media_type": "text/plain", "kind": "text"}
    return store.add_file(case_id, (name or fixture["name"]).replace(".pdf", ".txt").replace(".eml", ".txt"), "text/plain", "text",
                          ex["text"].encode(), extraction, "N. Kumar")["id"]


def seed_update(store, runs):
    """A mandated case prepared from its file (tests/test_update.py): the firm's fee note is added in the browser
    (deploy/preview/Zwischenhonorar Kanzlei Muster.txt) and «Aktualisieren» reads it alone."""
    from tests.test_update import MANDATE_A, MANDATE_DOCS_A, MANDATE_EDITS, MANDATE_ENTRIES_A, MANDATE_FACTS_A, full_turns
    case = store.create_case("Mietmangel, Mandat Kanzlei Muster (synthetisch) 4321.5555.0001", {"synthetic": True}, "N. Kumar")
    fid = _text_file(store, case["id"], MANDATE_A)
    store.select_workflow(case["id"], "mietmangel-handler", None, "N. Kumar")
    for edit in MANDATE_EDITS:
        store.add_edit(case["id"], "set_fact", edit["args"], "N. Kumar", "Entscheid der Fallbearbeitung")
    turns = _remap(full_turns(MANDATE_ENTRIES_A, MANDATE_FACTS_A, MANDATE_DOCS_A), {"fa": fid})
    turns[0] = turns[0][:-1] + [report("claim_reader", request="Lea Beispiel lässt einen Schimmelbefall durch die Kanzlei Muster abklären.",
                                       parties=[{"role": "Mieterin (VN)", "name": "Frau Lea Beispiel"}, {"role": "Vermieterin (GP)", "name": "Muster Immobilien AG"},
                                                {"role": "beauftragte Kanzlei", "name": "Kanzlei Muster"}])]
    runs.model_factory = lambda: ScriptedModel(turns)
    run = runs.start(case["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.05)
    return case


def update_script(store, case_id, pause):
    """The scripted update of the mandated case: the fee note's entry and the cost claim it brings, cited from the file the
    handler added (one without the note's words gives the update nothing to record)."""
    from tests.test_update import MANDATE_ENTRY_B, MANDATE_FACT_B
    base = store.latest_run(case_id, "completed")
    read = set(((base or {}).get("result") or {}).get("read_files") or ())
    new = [f["id"] for f in store.list_files(case_id) if f["id"] not in read]
    fid = new[0] if new else "none"
    entry = _remap({**MANDATE_ENTRY_B, "page": None}, {"fb": fid})
    return Paced([[("record_steps", {"entries": [entry]}), _remap(MANDATE_FACT_B, {"fb": fid}),
                   report("claim_reader", summary="Die Kanzlei stellt ihr Zwischenhonorar in Rechnung.")],
                  [report("document_finder", summary="Die Kostennote erfüllt keine fehlende Unterlage.")]], pause)


def seed_offer(store, runs):
    """A case Protekta conducts itself whose other side made an offer after Protekta's letter (tests/test_update.py,
    prepared from both files): the place to enter a phone call that settles it."""
    from tests.test_update import OFFER_A, OFFER_B, OFFER_EDITS, OFFER_ENTRIES_A, OFFER_ENTRY_B, OFFER_FACTS_A, OFFER_FACT_B, full_turns
    case = store.create_case("Heizungsausfall, Angebot der Gegenpartei (synthetisch) 4321.5555.0003", {"synthetic": True}, "N. Kumar")
    ids = {"oa": _text_file(store, case["id"], OFFER_A), "ob": _text_file(store, case["id"], OFFER_B)}
    store.select_workflow(case["id"], "mietmangel-handler", None, "N. Kumar")
    for edit in OFFER_EDITS:
        store.add_edit(case["id"], "set_fact", edit["args"], "N. Kumar", "Entscheid der Fallbearbeitung")
    turns = _remap(full_turns(OFFER_ENTRIES_A + [OFFER_ENTRY_B], OFFER_FACTS_A + [OFFER_FACT_B], [],
                              request="Sandra Keller verlangt die Reparatur der Heizung; die Vermieterin bietet eine Mietzinsreduktion an."), ids)
    turns[0] = turns[0][:-1] + [report("claim_reader", request="Sandra Keller verlangt die Reparatur der Heizung; die Vermieterin bietet eine Mietzinsreduktion an.",
                                       parties=[{"role": "Mieterin (VN)", "name": "Frau Sandra Keller"}, {"role": "Vermieterin (GP)", "name": "Muster Immobilien AG"}])]
    runs.model_factory = lambda: ScriptedModel(turns)
    run = runs.start(case["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.05)
    return case


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    data = tempfile.mkdtemp(prefix="cp-preview-")
    # The fixture's workflow plus a synthetic intake, so the handler's own workflow (which supersedes the intake) joins too.
    catalogue = Path(tempfile.mkdtemp(prefix="cp-preview-catalogue-"))
    (catalogue / "example-defect.json").write_text((ROOT / "tests" / "fixtures" / "example-defect.json").read_text())
    from tests.test_handler_workflow import intake
    (catalogue / "osm-mold.json").write_text(json.dumps(intake()))
    settings = load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_WORKFLOW_CATALOGUE": str(catalogue), "CASEPATH_DEV_USER": "N. Kumar"})
    app = create_app(settings, model_factory=lambda: None)
    store, runs = app.state.store, app.state.runs

    def seed(title):
        case = store.create_case(title, {"synthetic": True}, "N. Kumar")
        from casepath.read.extract import extract
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
        store.save_knowledge(kb.set_status(item, "active", by="N. Kumar", reason="In zwei Mietmangel-Fällen gesehen"))
    item = store.list_knowledge(statuses={"active"})[0]
    case_b, (email_b, letter_b, _) = seed("Schimmel im Badezimmer, Kramgasse 5 (zweiter Fall)")
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
    # Case C: a synthetic case on the handler's workflow with a stored result (no model), so its stage actions,
    # its letter and "andere Handlung" can be tried in the browser. Case D is the same, for the gesture checks.
    from casepath.read.extract import extract

    def handler_case(title):
        case = store.create_case(title, {"synthetic": True}, "N. Kumar")
        row = extract("Meldung Lea Brunner.eml", "message/rfc822", EMAIL)
        email = store.add_file(case["id"], "Meldung Lea Brunner.eml", row["media_type"], row["kind"], EMAIL, row, "N. Kumar")["id"]
        fact = lambda f, v, quote=None: {"fact": f, "status": "established", "verdict": "accepted", "value": v,
                                          "citations": [{"file": email, "quote": quote}] if quote else []}
        run = store.create_run(case["id"], "N. Kumar")
        store.update_run(run["id"], status="completed", workflow_id="mietmangel-handler", finished_at="2026-11-12T10:00:00+00:00",
                         result={"facts": [fact("rechtsgebiet", "Mietrecht / Mangel"), fact("maengelruege_schriftlich", "ja", TOLD)], "documents": [],
                                 "brief": {"request": "Lea Brunner möchte Hilfe, weil im Badezimmer immer wieder Schimmel auftritt.",
                                           "parties": [{"role": "Mieterin (VN)", "name": "Frau Lea Brunner"}], "timeline": []}})
        return case
    case_c = handler_case("Schimmel im Bad, Handler-Prozess (synthetisch)")
    case_d = handler_case("Schimmel im Bad, zweite Meldung (synthetisch)")
    factory_b = runs.model_factory
    seed_areas(store, runs)  # after C and D, so the cases the browser checks use stay at the top of the list
    case_k = seed_cost_note(store, runs)
    keyed = seed_key_cases(store, runs)
    historic = seed_historic(store)
    case_account = seed_account(store, runs)
    case_update = seed_update(store, runs)
    case_offer = seed_offer(store, runs)
    # «Aktualisieren» in the browser runs the update's script; every other run the one case B's live view plays
    asked = {}
    start_update = runs.update

    def update(case_id, user, token=None):
        asked["update"] = case_id
        return start_update(case_id, user, token)
    runs.update = update

    def dispatch():
        if asked.get("update"):
            return update_script(store, asked.pop("update"), pause)
        return factory_b()
    runs.model_factory = dispatch
    print(f"preview on http://127.0.0.1:{port}  case A {case_a['id']}  case B {case_b['id']}  case C {case_c['id']}  case D {case_d['id']}  cost note {case_k['id']}"
          f"  dismissal {keyed['kuendigung-sperrfrist']['id']}  hearing {keyed['miete-schlichtung']['id']}  historic {historic['id']}  account {case_account['id']}"
          f"  update {case_update['id']}  offer {case_offer['id']}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

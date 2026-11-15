"""A local preview of the workspace on synthetic data, for UI work without a model.

It seeds two made-up cases of the synthetic test workflow, one prepared synthetic case per shipped legal area, runs the agent team
with a paced scripted model (so the live view can be watched), lets case A teach
a Knowledge item and activates it, and serves the app. Nothing here is Mobiliar
data or a real model run.

Every stage has an example: intake with an urgent deadline (the penalty order, one day left), intake and assessment
in every area, the mandate package, a fee note, a settlement whose payout is chased, a closed case, historic files,
a case where new files arrived, a run that failed and one to prepare live. The area cases were written for 15.11.2026;
on another day their dates move with it, so a deadline is as close as it was then.

    python deploy/preview/preview.py [port]
"""
from datetime import date, timedelta
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
        [report("claim_reader", summary="Die Mieterin meldet wiederkehrenden Schimmel und hat die Verwaltung schriftlich informiert.",
                request="Lea Brunner möchte Hilfe, weil im Badezimmer immer wieder Schimmel auftritt.",
                parties=[{"role": "Mieterin (VN)", "name": "Lea Brunner"}, {"role": "Verwaltung", "name": "Immo Aare AG"}],
                timeline=[{"date": "03.02.2025", "event": "Die Mieterin informiert die Verwaltung schriftlich", "citations": [{"file": email, "quote": TOLD}]},
                          {"date": "07.02.2025", "event": "Die Verwaltung bestätigt den Eingang", "citations": [{"file": letter, "quote": REPLY}]}])],
        [delegate("process_builder", "Build this case's process.")],
        [("open_process", {}), ("view_knowledge", {})],
        [report("process_builder", summary="Prozess für einen Mietmangel; die Meldung an die Vermieterschaft entscheidet den Weg.",
                questions=[{"fact": "legal_area", "plain": "Geht es um einen Mangel der Mietsache?"}, {"fact": "landlord_notified", "plain": "Wurde die Vermieterschaft informiert?"}])],
        [delegate("claim_reader", "Record the facts the process asks about.")],
        [("search", {"query": "Verwaltung informiert"})],
        [("record_fact", {"fact": "legal_area", "status": "established", "value": "Mietmangel",
                          "citations": [{"file": email, "quote": "Im Badezimmer meiner Wohnung bildet sich seit Dezember schwarzer Schimmel."}]})],
        [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes", "citations": [{"file": email, "quote": TOLD}]}),
         report("claim_reader", summary="Beide Angaben mit wörtlichen Zitaten festgehalten.")],
        [delegate("document_finder", "Match each document need to a file.")],
        [("open_process", {})],
        [*finder, report("document_finder", summary="Meldung und Mängelrüge gefunden; das Foto enthält keinen Text.")],
        [delegate("result_checker", "Evaluate and draft.")],
        [("evaluate", {}), report("result_checker", summary="Die Mieterin hat die Verwaltung schriftlich informiert; der Mangel lässt sich beurteilen. Die Fotos liegen bei.",
                                  answer="Die Vermieterschaft wurde schriftlich informiert; den Mangel mit seinen Belegen beurteilen.", open_points=["Ob der Einwand des Lüftens zutrifft"],
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


EXAMPLE_DE = {
    "Example: rental defect (synthetic test fixture)": "Mietmangel (Testprozess)", "Synthetic test fixture, not a Mobiliar process": "Synthetischer Testprozess, kein Prozess der Mobiliar",
    "Which legal area does the request concern?": "Welches Rechtsgebiet betrifft das Anliegen?", "Has the tenant told the landlord about the defect?": "Hat die Mieterin den Mangel gemeldet?",
    "Read the request": "Anliegen lesen", "Check whether the landlord was told": "Prüfen, ob die Vermieterschaft informiert wurde",
    "Assess the defect with its evidence": "Mangel mit seinen Belegen beurteilen", "Advise telling the landlord first": "Raten, den Mangel zuerst zu melden",
    "told": "gemeldet", "not told": "nicht gemeldet", "The customer's message": "Meldung der Kundschaft", "It states the request.": "Sie nennt das Anliegen.",
    "Photo of the defect": "Foto des Mangels", "It shows the defect.": "Es zeigt den Mangel.", "Notice to the landlord": "Mängelrüge an die Vermieterschaft",
    "It proves the landlord was told.": "Sie belegt, dass die Vermieterschaft informiert wurde.", "Case reported": "Fall gemeldet", "Advice given": "Beraten",
    "Synthetic open question for tests.": "Synthetische offene Frage für Tests.", "tenancy_defect": "Mietmangel", "loan": "Darlehen", "other": "anderes"}


def german_example(workflow):
    """The synthetic test workflow of cases A and B in the handler's language (its ids stay; the tests keep the original)."""
    if isinstance(workflow, dict):
        return {k: german_example(v) if k not in {"id", "to", "fact", "source_refs", "start", "outcome", "format", "status", "version"} else v
                for k, v in workflow.items()}
    if isinstance(workflow, list):
        return [german_example(v) for v in workflow]
    return EXAMPLE_DE.get(workflow, workflow) if isinstance(workflow, str) else workflow


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
    signed = re.search(r"([A-ZÄÖÜ][a-zäöüé]+ [A-ZÄÖÜ][a-zäöüé]+)\s*$", case["text"])  # the customer signs the report
    return ScriptedModel([
        [*[("record_fact", {"part": None, "fact": f, "status": "established", "value": v, "citations": cite(q)}) for f, v, q in case["facts"]],
         report("claim_reader", request=request(case["text"]), parties=[{"role": "Kundschaft (VN)", "name": signed.group(1)}] if signed else [])],
        [report("document_finder")],
        *[[report("result_checker", answer="Die erste Anforderung ist vorbereitet.")]] * 3,
    ], routing=routing)


WRITTEN_FOR = date(2026, 11, 15)  # the day the synthetic area cases were written for
GERMAN_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def moved(value, days=None):
    """A synthetic case with its dates moved by the days since it was written (none today): ISO dates and «6. November
    2026» alike, in the text, the quotes and the values, so a deadline is as close on any day as on the day it was written."""
    days = (date.today() - WRITTEN_FOR).days if days is None else days
    if not days:
        return value
    if isinstance(value, dict):
        return {k: moved(v, days) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(moved(v, days) for v in value)
    if not isinstance(value, str):
        return value
    shift = lambda d: d + timedelta(days=days)
    value = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: shift(date(*map(int, m.groups()))).isoformat(), value)
    long = lambda d: f"{d.day}. {GERMAN_MONTHS[d.month - 1]} {d.year}"
    return re.sub(rf"\b(\d{{1,2}})\. ({'|'.join(GERMAN_MONTHS)}) (\d{{4}})\b",
                  lambda m: long(shift(date(int(m[3]), GERMAN_MONTHS.index(m[2]) + 1, int(m[1])))), value)


def renamed(case, names):
    """A copy of a synthetic case with other made-up names, so a second example of an area reads as another case."""
    text = json.dumps(case, ensure_ascii=False)
    for old, new in names.items():
        text = text.replace(old, new)
    return json.loads(text)


def prepare_area_case(store, runs, case, title=None, decisions=(), files_after=()):
    """One synthetic area case prepared by the scripted team from one e-mail; the handler's decisions set before the run,
    files added after it (new files the run did not read)."""
    from casepath.read.extract import extract
    made = store.create_case(title or f"{case['title']} (synthetisch)", {"synthetic": True}, "N. Kumar")
    mail = (f"From: kundin@example.ch\r\nTo: schaden@example-rechtsschutz.ch\r\nSubject: {case['title']}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n{case['text']}\r\n").encode()
    row = extract("Schadenmeldung.eml", "message/rfc822", mail)
    file_id = store.add_file(made["id"], "Schadenmeldung.eml", row["media_type"], row["kind"], mail, row, "N. Kumar")["id"]
    for fact_id, value in decisions:
        store.add_edit(made["id"], "set_fact", {"fact": fact_id, "value": value}, "N. Kumar", "Entscheid der Fallbearbeitung")
    script = key_script if "request" in case else area_script
    runs.model_factory = lambda case=case, file_id=file_id: script(case, file_id)
    run = runs.start(made["id"], "N. Kumar")
    while store.get_run(run["id"])["status"] in ("queued", "running"):
        time.sleep(0.05)
    if store.get_run(run["id"])["status"] != "completed":
        print(f"case {made['title']} did not complete: {store.get_run(run['id']).get('error')}", flush=True)
    for name, text in files_after:
        data = text.encode()
        row = extract(name, "text/plain", data)
        store.add_file(made["id"], name, row["media_type"], row["kind"], data, row, "N. Kumar")
    return made


def log_event(store, case_id, kind, **fields):
    """One event in the case's log, as the app records a gesture (casepath.study.event/1)."""
    completed = store.latest_run(case_id, "completed")
    return store.append_case_event(case_id, {"schema": "casepath.study.event/1", "session_id": None, "expert": "N. Kumar", "case_copy": case_id,
                                             "source_case": None, "frozen_run_id": (completed or {}).get("id"), "kind": kind,
                                             "parity_sha": "preview", "item_id": None, **fields})


def seed_stages(store, runs):
    """The stages the area cases do not reach by themselves: a case at the mandate stage (the mandate package), a closed
    case, a case where new files came in after its preparation, and a run that failed."""
    areas = moved(json.loads((ROOT / "tests" / "fixtures" / "areas" / "cases.json").read_text()))
    keyed = moved(json.loads((ROOT / "tests" / "fixtures" / "areas" / "key_cases.json").read_text()))
    hearing = renamed(keyed["miete-schlichtung"], {"Peter Muster": "Rita Exempel", "Probegasse 7": "Lindenweg 3"})
    mandate = prepare_area_case(store, runs, hearing, "Kündigung Miete, Mandat (synthetisch)",
                                decisions=[("deckung", "bestätigt"), ("vorgehen", "Mandat an Anwaltskanzlei")])
    done = renamed(areas["arbeit-zeugnis"], {"Greta Muster": "Olga Exempel", "Exempel Treuhand AG": "Probe Treuhand AG"})
    closed = prepare_area_case(store, runs, done, "Arbeitszeugnis, erledigt (synthetisch)")
    log_event(store, closed["id"], "letter.copied", form="A1", edited=False, change_ratio=0)
    log_event(store, closed["id"], "case.closed", form="erledigt", note_present=False)
    later = renamed(areas["vertrag-kauf"], {"Ivan Muster": "Lukas Exempel", "Garage Beispiel AG": "Auto Probe AG"})
    arrived = prepare_area_case(store, runs, later, "Kauf mit Mangel, Antwort der Garage (synthetisch)",
                                files_after=[("Antwort Auto Probe AG.txt", "SYNTHETISCHE AKTE. Auto Probe AG an Lukas Exempel: Wir lehnen "
                                              "eine Rücknahme des Fahrzeugs ab; die Gewährleistung ist im Kaufvertrag ausgeschlossen.")])
    from casepath.read.extract import extract
    failed = store.create_case("Werkvertrag, Lauf abgebrochen (synthetisch)", {"synthetic": True}, "N. Kumar")
    text = areas["werkvertrag-bau"]["text"].encode()
    row = extract("Meldung.txt", "text/plain", text)
    store.add_file(failed["id"], "Meldung.txt", row["media_type"], row["kind"], text, row, "N. Kumar")
    run = store.create_run(failed["id"], "N. Kumar")
    store.update_run(run["id"], status="failed", error="transport: the model could not be reached", finished_at="2026-11-15T09:00:00+00:00")
    return {"mandate": mandate, "closed": closed, "arrived": arrived, "failed": failed}


def seed_areas(store, runs):
    """One prepared synthetic case per shipped area, routed and prepared by the scripted team: the breadth of the product."""
    from casepath.read.extract import extract
    cases = moved(json.loads((ROOT / "tests" / "fixtures" / "areas" / "cases.json").read_text()))
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
    cases = moved(json.loads((ROOT / "tests" / "fixtures" / "areas" / "key_cases.json").read_text()))
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
    (catalogue / "example-defect.json").write_text(json.dumps(german_example(json.loads((ROOT / "tests" / "fixtures" / "example-defect.json").read_text())),
                                                               ensure_ascii=False))
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
                                                    "note": "Kein Mietvertrag in den Akten."}), report("document_finder", summary="Kein Mietvertrag in den Akten.")]], pause)
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
    stages = seed_stages(store, runs)
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
          f"  update {case_update['id']}  offer {case_offer['id']}  mandate {stages['mandate']['id']}  closed {stages['closed']['id']}"
          f"  arrived {stages['arrived']['id']}  failed {stages['failed']['id']}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

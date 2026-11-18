"""One synthetic case as the handlers of the active house see it, printed as JSON for tests/test_house.py.

The house is chosen once per process (CASEPATH_HOUSE, casepath/house), so a test that wants another house starts this
probe in a process of its own:

    python -m tests.house_probe [--insurer-in-file <name>] [--claim-number <number>]

The case is tests/fixtures/replay/three_phases.json (a tenancy defect, every name invented), prepared by the scripted
team (tests/phased.py, no model) at two of its cuts, each with its own «Stand am», so nothing depends on today's date:
before the first request (the A1 letter) and after it (the account holds the insurer's own letter). The fixture is a
file of the built-in house: its documents write «Protekta» and its claim number has that house's form. A file of
another house names that house and carries its number: ``--insurer-in-file`` and ``--claim-number`` say them.

Printed: what the page's first call says about the house, and for each cut what the case view returns: the account
(«Verlauf»), the letters (the insurer's draft and the templates for the customer's own letters), the screen with the
cover points it shows, the file note, the status and the follow-up date; with them the digest of the whole view and how
often it names an insurer. Ids and clock times that differ from run to run are replaced by a mark.
"""
import argparse
import hashlib
import json
import re
import sys
import warnings

CUTS = (0, 1)
FIXTURE = "three_phases"
CLAIM_NUMBER = "2025.0001.0303"  # the fixture's
COVER_WORDS = ("title", "label", "state_text", "text", "note", "lookup")
RANDOM_ID = re.compile(r"\b(case|file|run|ed|ev|know)_[0-9a-f]{16}\b")
CLOCK_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00")


def steady(view):
    """The view without what differs from run to run: random ids, clock times and the digest made over them."""
    text = json.dumps({k: v for k, v in view.items() if k != "items_sha256"}, ensure_ascii=False, sort_keys=True)
    return json.loads(CLOCK_TIME.sub("<time>", RANDOM_ID.sub(r"\1_#", text)))


def shown(view):
    """What a handler reads of the case, by where it stands on the page."""
    items = view["items"]
    return {"account": view["verlauf"],
            "letters": {"draft": view["draft"], "for_the_customer": [i["text"] for i in items if i["kind"] == "customer_letter"]},
            "screen": {**view["screen"], "cover_points": [{k: i.get(k) for k in COVER_WORDS} for i in items if i["kind"] == "cover"]},
            "file_note": view["file_note"], "status": view["status"], "follow_up": view["follow_up"]}


def probe(insurer_in_file=None, claim_number=None):
    from fastapi.testclient import TestClient

    from casepath.config import load_settings
    from casepath.web.app import create_app
    from tests import phased

    case = json.dumps(phased.load(FIXTURE), ensure_ascii=False)
    if insurer_in_file:
        case = case.replace("Protekta", insurer_in_file)
    if claim_number:
        case = case.replace(CLAIM_NUMBER, claim_number)
    case = json.loads(case)
    desk = phased.Desk()
    app = create_app(load_settings({"CASEPATH_DATA_DIR": desk.directory.name, "CASEPATH_DEV_USER": "test"}),
                     model_factory=lambda: None, store=desk.store, catalogue=desk.catalogue)
    client = TestClient(app)
    out = {"house": client.get("/api/health").json().get("house"), "cuts": {}}
    try:
        for n in CUTS:
            cut = case["cuts"][n]
            case_id = desk.prepare(case, cut, cut["pages"], cut["as_of"])
            view = steady(client.get(f"/api/cases/{case_id}").json())
            whole = json.dumps(view, ensure_ascii=False, sort_keys=True)
            out["cuts"][cut["as_of"]] = {"shown": shown(view), "whole_view": {
                "sha256": hashlib.sha256(whole.encode()).hexdigest(), "names_protekta": whole.count("Protekta"),
                "names_insurer_in_file": whole.count(insurer_in_file) if insurer_in_file else None}}
    finally:
        app.state.runs.shutdown()
        desk.close()
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tests.house_probe")
    parser.add_argument("--insurer-in-file", default=None)
    parser.add_argument("--claim-number", default=None)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    json.dump(probe(args.insurer_in_file, args.claim_number), sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

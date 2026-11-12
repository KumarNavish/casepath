"""Replay: a Knowledge version applied to the stored runs, without a model.

    python -m casepath replay [--knowledge proposal.json] [--case ID …]

For each case with a completed run, the item list is built twice from the run as stored: with the store's active
Knowledge, and with that Knowledge plus the proposed items (a JSON list of Knowledge items, status taken as active).
The output names, per case, what the proposal changes: documents asked now, documents offered, questions, the next
action. Ids and process titles only; no case content leaves the store.
"""
import argparse
import json

from ..agents.runner import case_state
from ..process.items import build_items


def snapshot(store, catalogue, case_id, knowledge=None):
    state = case_state(store, catalogue, case_id, knowledge)
    if not state.get("process") or not state.get("run"):
        return None
    items = build_items(state, state["run"].get("result") or {}, store.list_files(case_id))
    pick = lambda kind, ask: sorted(i["key"] for i in items if i["kind"] == kind and i.get("ask") == ask)
    action = next((i for i in items if i["kind"] == "next_action"), {})
    return {"needs": sorted(i["key"] for i in items if i["kind"] == "document"), "now": pick("document", "now"), "offered": pick("document", "proposed"), "later": pick("document", "later"),
            "questions": pick("letter_question", "now"), "next_action": action.get("action")}


def replay(store, catalogue, proposal=(), case_ids=None):
    """[{case, title, before, after, changed}] for every case with a completed run (or the cases named)."""
    rows = []
    for case in store.list_cases():
        if case_ids and case["id"] not in case_ids:
            continue
        before = snapshot(store, catalogue, case["id"])
        if before is None:
            continue
        active = store.list_knowledge(None, {"active"})
        after = snapshot(store, catalogue, case["id"], active + [{**k, "status": "active"} for k in proposal])
        changed = {k: {"before": before[k], "after": after[k]} for k in before if before[k] != after[k]}
        rows.append({"case": case["id"], "title": case["title"], "before": before, "after": after, "changed": changed})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m casepath replay", description=__doc__.splitlines()[0])
    parser.add_argument("--knowledge", help="a JSON file with a list of proposed Knowledge items")
    parser.add_argument("--case", action="append", help="only this case (repeatable)")
    args = parser.parse_args(argv)
    from ..config import load_settings
    from ..process.workflows import Catalogue
    from ..web.store import CaseStore

    settings = load_settings()
    store = CaseStore(settings.data_dir)
    proposal = json.loads(open(args.knowledge).read()) if args.knowledge else []
    rows = replay(store, Catalogue.load(settings.catalogue_dir), proposal, set(args.case or ()) or None)
    for row in rows:
        print(json.dumps({"case": row["case"], "changed": row["changed"]} if proposal else {"case": row["case"], **row["before"]}, ensure_ascii=False))
    print(json.dumps({"cases": len(rows), "changed": sum(1 for r in rows if r["changed"])}))
    store.close()

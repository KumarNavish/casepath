"""The handler's truth of a benchmark suite (``truth_handler``): score results saved from the deployed product, and
check the truth against the product's own rules without a model.

    python -m casepath evaluate score-saved <results.json> <suite dir> [--catalogue <dir>]
    python -m casepath evaluate self-check <suite dir> [--catalogue <dir>]

``truth_handler`` (see the suite's AUTHORING.md) names the case's area, the next action kind, the area's documents
asked now, present, offered, not needed or depending on an open fact, the area facts the files settle, and the statutory
deadlines with the date the area's rule gives (``prüfen`` where it gives none, ``trigger_missing`` where the files do
not state the trigger, ``not_applicable`` where the rule's condition fails).

``score-saved`` reads a JSON list written by a browser script on the deployed product, one row per case: {case,
workflow, action, now, offered, letter_lines, letter_gaps, follow_up, deadlines: [{id, date}], seconds, tokens:
{non_cached, output}}. It prints one line per case, a table, totals and the failed checks grouped by area: ids and
counts only, no case content.

``self-check`` evaluates each case with the product's rules as if the reading were perfect (the truth's facts and
present documents) and prints where the documents asked now differ from ``ask_now``.
"""
import json
from pathlib import Path
import re
import sys

from .benchmark import BenchmarkError, load_suite, short_id

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKERS = {"prüfen", "trigger_missing", "not_applicable"}
LISTS = ("ask_now", "present", "offered", "not_needed")


def areas(catalogue_dir=None):
    """{id: workflow} of the catalogue (the shipped areas join by default, also with no directory)."""
    from ..process.workflows import Catalogue

    return {w["id"]: w for w in Catalogue.load(catalogue_dir).latest()}


def check_truth(case, workflows):
    """Raise BenchmarkError when the case's truth_handler names an unknown area, document, fact or deadline."""
    truth, where = case.get("truth_handler"), short_id(case)
    if not isinstance(truth, dict):
        raise BenchmarkError(f"{where}: truth_handler is missing")
    workflow = workflows.get(truth.get("area"))
    if workflow is None:
        raise BenchmarkError(f"{where}: area {truth.get('area')!r} is not in the catalogue")
    if truth.get("action") not in workflow.get("action_kinds", {}):
        raise BenchmarkError(f"{where}: action {truth.get('action')!r} is not an action kind")
    docs, facts = {d["id"] for d in workflow["documents"]}, {f["id"] for f in workflow["facts"]}
    named = [d for key in LISTS for d in truth.get(key, [])] + list(truth.get("depends", {}))
    if set(named) - docs or len(named) != len(set(named)):
        raise BenchmarkError(f"{where}: documents {sorted(set(named) - docs)} unknown, or one listed twice")
    if set(truth.get("depends", {}).values()) - facts or set(truth.get("facts", {})) - facts:
        raise BenchmarkError(f"{where}: a fact of depends or facts is not in {workflow['id']}")
    statutory = {d["id"] for d in workflow.get("deadlines", [])}
    for d in truth.get("deadline", []):
        if d.get("id") not in statutory or not (d.get("date") in MARKERS or DATE.match(str(d.get("date")))):
            raise BenchmarkError(f"{where}: deadline {d.get('id')!r} or its date is not valid")
    return truth


# -- scoring saved results ------------------------------------------------------------

def deadline_verdict(expected, given):
    """right, wrong or missing for one truth deadline against the product's {id: date}."""
    date = given.get(expected["id"])
    if expected["date"] in {"trigger_missing", "not_applicable"}:  # no date may be given
        return "right" if date is None or not DATE.match(str(date)) else "wrong"
    if date is None:
        return "missing"
    return "right" if date == expected["date"] else "wrong"


def score_row(truth, row):
    """The checks of one case: {check: verdict} plus the counts the table shows."""
    asked, expected = set(row.get("now") or []), set(truth.get("ask_now", []))
    neutral = set(truth.get("depends", {})) | set(truth.get("offered", []))
    present = set(truth.get("present", []))
    given = {d.get("id"): d.get("date") for d in row.get("deadlines") or []}
    verdicts = [deadline_verdict(d, given) for d in truth.get("deadline", [])]
    letter = None
    if truth.get("action") == "A1":  # only a first request has a letter to complete
        letter = (row.get("letter_lines") or 0) > 0 and (row.get("letter_gaps") or 0) == 0
    tokens = row.get("tokens") or {}
    return {
        "area": row.get("workflow") == truth["area"],
        "action": row.get("action") == truth["action"],
        "hit": sorted(asked & expected), "expected": len(expected),
        "extra": sorted(asked - expected - neutral - present), "present_asked": sorted(asked & present),
        "letter": letter,
        "deadline": None if not verdicts else "wrong" if "wrong" in verdicts else "missing" if "missing" in verdicts else "right",
        "deadline_failed": [d["id"] for d, v in zip(truth.get("deadline", []), verdicts) if v != "right"],
        "seconds": row.get("seconds"), "non_cached": tokens.get("non_cached"), "output": tokens.get("output"),
    }


def failures(case_id, s):
    out = [f"{case_id} {check}" for check, failed in (("area", not s["area"]), ("action", not s["action"]),
                                                      ("letter incomplete", s["letter"] is False)) if failed]
    out += [f"{case_id} not asked {d}" for d in s["missed"]] + [f"{case_id} extra {d}" for d in s["extra"]]
    out += [f"{case_id} present asked {d}" for d in s["present_asked"]]
    out += [f"{case_id} deadline {d}" for d in s["deadline_failed"]]
    return out


def score_saved(rows, cases):
    """[(case id, area, score or None)] in suite order; a case without a saved row scores None."""
    by_case = {str(r.get("case")): r for r in rows}
    scored = []
    for case in cases:
        truth, cid = case["truth_handler"], short_id(case)
        row = by_case.get(cid)
        s = score_row(truth, row) if row is not None else None
        if s is not None:
            s["missed"] = sorted(set(truth.get("ask_now", [])) - set(s["hit"]))
            s["failed"] = failures(cid, s)
        scored.append((cid, truth["area"], s))
    return scored


def _mark(value):
    return "-" if value is None else "ok" if value is True else "FAIL" if value is False else str(value)


def render(scored):
    lines, table = [], []
    head = ("case", "area", "action", "docs", "extra", "pres.asked", "letter", "deadline", "sec", "tokens")
    for cid, area_id, s in scored:
        if s is None:
            lines.append(f"{cid} no saved result")
            table.append((cid, "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            continue
        docs = f"{len(s['hit'])}/{s['expected']}"
        lines.append(f"{cid} area {_mark(s['area'])} action {_mark(s['action'])} documents {docs} extra {len(s['extra'])} "
                     f"present asked {len(s['present_asked'])} letter {_mark(s['letter'])} deadline {_mark(s['deadline'])}")
        table.append((cid, _mark(s["area"]), _mark(s["action"]), docs, str(len(s["extra"])), str(len(s["present_asked"])),
                      _mark(s["letter"]), _mark(s["deadline"]), _mark(s["seconds"]), f"{_mark(s['non_cached'])}/{_mark(s['output'])}"))
    done = [s for _, _, s in scored if s is not None]
    count = lambda key, value=True: sum(1 for s in done if s[key] == value)
    hits, expected = sum(len(s["hit"]) for s in done), sum(s["expected"] for s in done)
    total = ("total", f"{count('area')}/{len(done)}", f"{count('action')}/{len(done)}", f"{hits}/{expected}",
             str(sum(len(s["extra"]) for s in done)), str(sum(len(s["present_asked"]) for s in done)),
             f"{count('letter')}/{sum(1 for s in done if s['letter'] is not None)}",
             f"{count('deadline', 'right')}/{sum(1 for s in done if s['deadline'] is not None)}",
             str(round(sum(s["seconds"] or 0 for s in done), 1)),
             f"{sum(s['non_cached'] or 0 for s in done)}/{sum(s['output'] or 0 for s in done)}")
    widths = [max(len(r[i]) for r in [head, *table, total]) for i in range(len(head))]
    fmt = lambda r: "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
    lines += ["", fmt(head), *map(fmt, table), fmt(total), "", "failed checks by area:"]
    by_area = {}
    for cid, area_id, s in scored:
        by_area.setdefault(area_id, []).extend(s["failed"] if s else [f"{cid} no saved result"])
    lines += [f"  {a}: {', '.join(f) if f else 'none'}" for a, f in sorted(by_area.items())]
    return "\n".join(lines)


# -- self-check against the product's rules ---------------------------------------------

def _files(case):
    """The case's files as a perfect reading would list them: one segment per document, photos and measurements named."""
    def kind(d):
        if d["kind"] == "photo_sheet":
            return "Fotodokumentation"
        if d["kind"] in {"protocol", "report"} and re.search(r"mess|temperatur", d["title"], re.I):
            return "Messprotokoll"
        return d["kind"]
    segments = [{"kind": kind(d), "date": ".".join(reversed(d["date"].split("-"))), "sender": (d.get("sender") or "").split("\n")[0]}
                for d in case["documents"]]
    return [{"name": "Akte.pdf", "extraction": {"segments": segments}}]


def rules(case, workflow):
    """What the product's rules prepare for the case if the reading were perfect: documents asked now, offered and later,
    the next action and the statutory deadlines."""
    from ..agents import core
    from ..process.items import build_items

    truth = case["truth_handler"]
    facts = {"rechtsgebiet": workflow["applies_when"]["is"], **truth.get("facts", {})}
    result = {"facts": [{"fact": k, "status": "established", "verdict": "accepted", "value": v, "citations": []}
                        for k, v in facts.items() if v is not None],
              "documents": [{"document": d, "status": "present", "verdict": "accepted", "files": ["f"], "citations": []}
                            for d in truth.get("present", [])],
              "brief": {"request": "", "parties": [], "timeline": []}}
    files = _files(case)
    items = build_items(core.evaluate(workflow, [], [], result, short_id(case), files=files), result, files)
    pick = lambda ask: sorted(i["key"] for i in items if i["kind"] == "document" and i.get("ask") == ask)
    action = next((i.get("action") for i in items if i["kind"] == "next_action"), None)
    return {"now": pick("now"), "offered": pick("proposed"), "later": pick("later"), "action": action,
            "deadlines": sorted((i["key"], i["value"]) for i in items if i["kind"] == "deadline" and i.get("origin") == "law")}


def self_check(cases, workflows):
    """[(case id, area, rules, differences)]: the rules' documents asked now against ask_now, deadlines against the truth."""
    rows = []
    for case in cases:
        truth = check_truth(case, workflows)
        got = rules(case, workflows[truth["area"]])
        want = set(truth.get("ask_now", [])) if truth["action"] == "A1" else set()
        diff = {}
        if set(got["now"]) != want:
            diff["now"] = {"rules_only": sorted(set(got["now"]) - want), "truth_only": sorted(want - set(got["now"]))}
        dated = {i: d for i, d in got["deadlines"]}
        wrong = [d["id"] for d in truth.get("deadline", []) if deadline_verdict(d, dated) != "right"]
        if wrong:
            diff["deadlines"] = wrong
        if got["action"] != truth["action"]:
            diff["action"] = {"rules": got["action"], "truth": truth["action"]}
        rows.append((short_id(case), truth["area"], got, diff))
    return rows


def main(command, paths, catalogue=None):
    workflows = areas(catalogue)
    if command == "self-check":
        cases = load_suite(paths[0])
        rows = self_check(cases, workflows)
        for cid, area_id, got, diff in rows:
            print(json.dumps({"case": cid, "area": area_id, "action": got["action"], "now": got["now"], "offered": got["offered"],
                              "later": got["later"], "deadlines": got["deadlines"], **({"differs": diff} if diff else {})}, ensure_ascii=False))
        print(json.dumps({"cases": len(rows), "differ": sum(1 for r in rows if r[3])}))
        return
    if len(paths) < 2:
        sys.exit("score-saved needs <results.json> <suite dir>")
    rows = json.loads(Path(paths[0]).read_text())
    cases = load_suite(paths[1])
    for case in cases:
        check_truth(case, workflows)
    print(render(score_saved(rows, cases)))

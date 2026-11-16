"""The handler's truth of a benchmark suite (``truth_handler``): score results saved from the deployed product, and
check the truth against the product's own rules without a model.

    python -m casepath evaluate score-saved <results.json> <suite dir> [--catalogue <dir>]
    python -m casepath evaluate self-check <suite dir> [--catalogue <dir>]

``truth_handler`` (see the suite's AUTHORING.md) names the case's area, the next action kind, the area's documents
asked now, present, offered, not needed or depending on an open fact, the area facts the files settle, and the statutory
deadlines with the date the area's rule gives (``prüfen`` where it gives none, ``trigger_missing`` where the files do
not state the trigger, ``not_applicable`` where the rule's condition fails), and the key points of the area whose
condition the case's facts meet (``key_points``, ids; optional in older cases). For an assessment it may also name the
recommendation a complete letter gives (``recommendation``: the ids of the ways to proceed) and how many of the
customer's questions it answers (``answers``).

``score-saved`` reads a JSON list written by a browser script on the deployed product, one row per case: {case,
workflow, action, now, offered, letter_lines, letter_gaps, follow_up, deadlines: [{id, date}], seconds, tokens:
{non_cached, output}}, optionally letter_none (the product's reason for no draft), letter_missing (the parts of the
form the draft lacks) and key_points (the points the card shows: ids, or {id, state} where only state «applies»
counts). It prints one line per case, a table, totals and the failed checks grouped by area: ids and counts only, no
case content. A first request that is incomplete says why: 0 lines, gaps, a missing part, no draft. A letter whose form
declares the marked gaps the handler fills in (``handler_gaps``: in the assessment the reasons and the recommendation) is
scored too: when its only gaps are those, it is «ok, n gaps for the handler», distinct from a letter with an unexpected
gap or no lines. Not so where the truth names a recommendation or answers: then the letter is expected to give them, and
its declared gaps are gaps like any other. The row names its gaps' texts in ``letter_gap_texts`` (the words inside
«[bitte ergänzen: …]»); a row with a count only is read as the handler's gaps while the count does not exceed the form's
declared places.

``self-check`` evaluates each case with the product's rules as if the reading were perfect (the truth's facts, its
present documents and the part of an open-ended need it calls offered) together with the practice rules a fresh
deployment seeds (Knowledge; their needs are named "k-<item id>"), and prints where the documents asked now, the next
action, the statutory deadlines or the key points that apply differ from the truth.
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


def knowledge(workflow):
    """The practice rules a fresh deployment applies to this area (the build's seeded, active Knowledge)."""
    from ..process.knowledge import seed_items

    return seed_items({workflow["id"]})


def case_process(workflow):
    """The area's process as a case of it starts: the area plus the seeded practice rules (their needs are "k-<item id>")."""
    from ..process import casegraph

    return casegraph.build(workflow, knowledge=knowledge(workflow))[0]


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
    process = case_process(workflow)
    docs, facts = {d["id"] for d in process["documents"]}, {f["id"] for f in process["facts"]}
    named = [d for key in LISTS for d in truth.get(key, [])] + list(truth.get("depends", {}))
    if set(named) - docs or len(named) != len(set(named)):
        raise BenchmarkError(f"{where}: documents {sorted(set(named) - docs)} unknown, or one listed twice")
    if set(truth.get("depends", {}).values()) - facts or set(truth.get("facts", {})) - facts:
        raise BenchmarkError(f"{where}: a fact of depends or facts is not in {workflow['id']}")
    statutory = {d["id"] for d in workflow.get("deadlines", [])}
    for d in truth.get("deadline", []):
        if d.get("id") not in statutory or not (d.get("date") in MARKERS or DATE.match(str(d.get("date")))):
            raise BenchmarkError(f"{where}: deadline {d.get('id')!r} or its date is not valid")
    points = truth.get("key_points")
    if points is not None and (not isinstance(points, list) or set(points) - {p["id"] for p in workflow.get("key_points") or ()}
                               or len(points) != len(set(points))):
        raise BenchmarkError(f"{where}: key_points must name key points of {workflow['id']}, each once")
    if truth.get("as_of") is not None and not DATE.match(str(truth["as_of"])):
        raise BenchmarkError(f"{where}: as_of is the day the truth holds, as YYYY-MM-DD")
    named = truth.get("recommendation")
    if named is not None and (not isinstance(named, list) or not named or any(not re.match(r"^[a-z0-9][a-z0-9_]{0,59}$", str(x)) for x in named)):
        raise BenchmarkError(f"{where}: recommendation names the ways to proceed a complete assessment gives, by their ids")
    if truth.get("answers") is not None and (type(truth["answers"]) is not int or truth["answers"] < 0):
        raise BenchmarkError(f"{where}: answers is how many of the customer's questions the letter answers")
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


def shown_points(row):
    """The key points the saved card shows as applying: ids, or {id, state} rows of which only «applies» counts."""
    out = []
    for p in row.get("key_points") or ():
        if isinstance(p, dict):
            if p.get("state", "applies") == "applies" and p.get("id"):
                out.append(p["id"])
        elif p:
            out.append(str(p))
    return out


def points_verdict(truth, row):
    """The key points expected on the card against those it shows: {hit, want, missed, extra}, or None when the truth names
    none (an older case) or the row does not report them. The card shows at most two (keypoints.SHOWN), applying ones
    first, so as many expected points as fit must be shown and no point the facts do not meet may be shown as applying."""
    from ..process.keypoints import SHOWN

    expected = truth.get("key_points")
    if expected is None or "key_points" not in row:
        return None
    shown = shown_points(row)
    hit = [p for p in shown if p in expected]
    return {"hit": hit, "want": min(len(expected), SHOWN), "missed": [p for p in expected if p not in shown],
            "extra": [p for p in shown if p not in expected]}


def letter_form(truth, workflows=None):
    """The form of the case's next action in its area ({} when none): where a letter is scored, the gaps it declares."""
    workflow = (workflows or {}).get(truth.get("area"))
    if workflow is None:
        from ..process import area
        try:
            workflow = area.workflow(truth.get("area"))
        except Exception:  # an area the shipped catalogue does not hold: no form to read
            workflow = {}
    return (workflow.get("forms") or {}).get(truth.get("action")) or {}


def score_row(truth, row, workflows=None):
    """The checks of one case: {check: verdict} plus the counts the table shows. ``letter``: True (complete), "handler"
    (complete but for the gaps its form declares as the handler's), False (incomplete, ``letter_why`` says why), None (no
    letter scored for this action)."""
    asked, expected = set(row.get("now") or []), set(truth.get("ask_now", []))
    neutral = set(truth.get("depends", {})) | set(truth.get("offered", []))
    present = set(truth.get("present", []))
    given = {d.get("id"): d.get("date") for d in row.get("deadlines") or []}
    verdicts = [deadline_verdict(d, given) for d in truth.get("deadline", [])]
    letter, why, own = None, [], 0
    form = letter_form(truth, workflows)
    if truth.get("action") == "A1" or form.get("handler_gaps"):  # a first request, and a letter with the handler's gaps declared
        # where the truth names the recommendation or the answers, the letter is expected to give them: no gap is the handler's
        named = [k for k in ("recommendation", "answers") if truth.get(k)]
        why, own = letter_faults(row, None if named else form.get("handler_gaps"))
        if why and named and form.get("handler_gaps"):
            why.append("the truth names " + " and ".join(named))
        letter = False if why else "handler" if own else True
    tokens = row.get("tokens") or {}
    points = points_verdict(truth, row)
    return {
        "area": row.get("workflow") == truth["area"],
        "action": row.get("action") == truth["action"],
        "hit": sorted(asked & expected), "expected": len(expected),
        "extra": sorted(asked - expected - neutral - present), "present_asked": sorted(asked & present),
        "letter": letter, "letter_why": why, "letter_own_gaps": own,
        "deadline": None if not verdicts else "wrong" if "wrong" in verdicts else "missing" if "missing" in verdicts else "right",
        "deadline_failed": [d["id"] for d, v in zip(truth.get("deadline", []), verdicts) if v != "right"],
        "points": points, "points_ok": None if points is None else len(points["hit"]) >= points["want"] and not points["extra"],
        "seconds": row.get("seconds"), "non_cached": tokens.get("non_cached"), "output": tokens.get("output"),
    }


def letter_faults(row, handler_gaps=None):
    """Why a saved letter is incomplete, as short ids, and how many of its gaps are the handler's: (faults, own). Faults:
    "0 lines", "<n> gaps" (gaps its form does not declare as the handler's: ``handler_gaps``, by placeholder), "missing
    <part>" for each part the row names as missing (``letter_missing``), "no draft" when the product gave a reason instead
    (``letter_none``)."""
    out = []
    if row.get("letter_none"):
        out.append("no draft")
    if not (row.get("letter_lines") or 0):
        out.append("0 lines")
    texts = [str(x).strip() for x in row.get("letter_gap_texts") or ()]
    count = len(texts) if texts else int(row.get("letter_gaps") or 0)
    own = 0
    if handler_gaps and count:
        slot = {x: k for k, v in handler_gaps.items() for x in v}
        if texts:
            mine = [x for x in texts if x in slot]
            own = len(mine) if len({slot[x] for x in mine}) == len(mine) else 0  # each place of the form once
        else:
            own = count if count <= len(handler_gaps) else 0  # a count only: at most one gap per declared place
    unexpected = count - own
    if unexpected:
        out.append(f"{unexpected} gap{'' if unexpected == 1 else 's'}")
    out += [f"missing {part}" for part in row.get("letter_missing") or ()]
    return out, own


def failures(case_id, s):
    out = [f"{case_id} {check}" for check, failed in (("area", not s["area"]), ("action", not s["action"])) if failed]
    if s["letter"] is False:
        out.append(f"{case_id} letter incomplete ({', '.join(s['letter_why'])})")
    out += [f"{case_id} not asked {d}" for d in s["missed"]] + [f"{case_id} extra {d}" for d in s["extra"]]
    out += [f"{case_id} present asked {d}" for d in s["present_asked"]]
    out += [f"{case_id} deadline {d}" for d in s["deadline_failed"]]
    if s.get("points_ok") is False:
        points = s["points"]
        if len(points["hit"]) < points["want"]:
            out.append(f"{case_id} key point not shown {'/'.join(points['missed'])}")
        out += [f"{case_id} key point shown {p}" for p in points["extra"]]
    return out


def score_saved(rows, cases, workflows=None):
    """[(case id, area, score or None)] in suite order; a case without a saved row scores None."""
    by_case = {str(r.get("case")): r for r in rows}
    scored = []
    for case in cases:
        truth, cid = case["truth_handler"], short_id(case)
        row = by_case.get(cid)
        s = score_row(truth, row, workflows) if row is not None else None
        if s is not None:
            s["missed"] = sorted(set(truth.get("ask_now", [])) - set(s["hit"]))
            s["failed"] = failures(cid, s)
        scored.append((cid, truth["area"], s))
    return scored


def _mark(value):
    return "-" if value is None else "ok" if value is True else "FAIL" if value is False else str(value)


def _letter(s):
    """«ok», «ok, 2 gaps for the handler», «FAIL» or «-»."""
    if s["letter"] == "handler":
        n = s["letter_own_gaps"]
        return f"ok, {n} gap{'' if n == 1 else 's'} for the handler"
    return _mark(s["letter"])


def render(scored):
    lines, table = [], []
    head = ("case", "area", "action", "docs", "extra", "pres.asked", "letter", "deadline", "points", "sec", "tokens")
    points = lambda s: "-" if s["points"] is None else f"{len(s['points']['hit'])}/{s['points']['want']}" + ("" if s["points_ok"] else "!")
    for cid, area_id, s in scored:
        if s is None:
            lines.append(f"{cid} no saved result")
            table.append((cid, "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            continue
        docs = f"{len(s['hit'])}/{s['expected']}"
        lines.append(f"{cid} area {_mark(s['area'])} action {_mark(s['action'])} documents {docs} extra {len(s['extra'])} "
                     f"present asked {len(s['present_asked'])} letter {_letter(s)}"
                     + (f" ({', '.join(s['letter_why'])})" if s["letter"] is False else "") + f" deadline {_mark(s['deadline'])}"
                     + ("" if s["points"] is None else f" key points {points(s)}"))
        table.append((cid, _mark(s["area"]), _mark(s["action"]), docs, str(len(s["extra"])), str(len(s["present_asked"])),
                      _letter(s), _mark(s["deadline"]), points(s), _mark(s["seconds"]), f"{_mark(s['non_cached'])}/{_mark(s['output'])}"))
    done = [s for _, _, s in scored if s is not None]
    count = lambda key, value=True: sum(1 for s in done if s[key] == value)
    hits, expected = sum(len(s["hit"]) for s in done), sum(s["expected"] for s in done)
    total = ("total", f"{count('area')}/{len(done)}", f"{count('action')}/{len(done)}", f"{hits}/{expected}",
             str(sum(len(s["extra"]) for s in done)), str(sum(len(s["present_asked"]) for s in done)),
             f"{count('letter') + count('letter', 'handler')}/{sum(1 for s in done if s['letter'] is not None)}",
             f"{count('deadline', 'right')}/{sum(1 for s in done if s['deadline'] is not None)}",
             f"{count('points_ok')}/{sum(1 for s in done if s['points_ok'] is not None)}",
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

def _files(case, as_of=None):
    """The case's files as a perfect reading would list them: one segment per document, photos and measurements named;
    looked at on ``as_of`` (the truth's day: the action can depend on it, a deadline of the customer close by leads)."""
    def kind(d):
        if d["kind"] == "photo_sheet":
            return "Fotodokumentation"
        if d["kind"] in {"protocol", "report"} and re.search(r"mess|temperatur", d["title"], re.I):
            return "Messprotokoll"
        return d["kind"]
    segments = [{"kind": kind(d), "date": ".".join(reversed(d["date"].split("-"))), "sender": (d.get("sender") or "").split("\n")[0]}
                for d in case["documents"]]
    return [{"name": "Akte.pdf", "extraction": {"segments": segments, **({"cut_of": {"as_of": as_of}} if as_of else {})}}]


def rules(case, workflow):
    """What the product's rules prepare for the case if the reading were perfect: documents asked now, offered and later,
    the next action and the statutory deadlines."""
    from ..agents import core
    from ..process.items import build_items

    from ..process.casegraph import open_ended

    truth = case["truth_handler"]
    facts = {"rechtsgebiet": workflow["applies_when"]["is"], **truth.get("facts", {})}
    # an open-ended need ("Sämtliche …") the truth calls offered is one the file holds in part: the reading finds that part
    held = truth.get("present", []) + [d for d in truth.get("offered", []) if d in open_ended(case_process(workflow))]
    result = {"facts": [{"fact": k, "status": "established", "verdict": "accepted", "value": v, "citations": []}
                        for k, v in facts.items() if v is not None],
              "documents": [{"document": d, "status": "present", "verdict": "accepted", "files": ["f"], "citations": []}
                            for d in held],
              "brief": {"request": "", "parties": [], "timeline": []}}
    files = _files(case, truth.get("as_of"))
    items = build_items(core.evaluate(workflow, knowledge(workflow), [], result, short_id(case), files=files), result, files)
    pick = lambda ask: sorted(i["key"] for i in items if i["kind"] == "document" and i.get("ask") == ask)
    action = next((i.get("action") for i in items if i["kind"] == "next_action"), None)
    return {"now": pick("now"), "offered": pick("proposed"), "later": pick("later"), "action": action,
            "deadlines": sorted((i["key"], i["value"]) for i in items if i["kind"] == "deadline" and i.get("origin") == "law"),
            "key_points": sorted(i["key"] for i in items if i["kind"] == "key_point" and i.get("value") == "applies")}


def self_check(cases, workflows):
    """[(case id, area, rules, differences)]: the rules' documents asked now against ask_now, deadlines and the key points
    that apply (where the truth names them) against the truth."""
    rows = []
    for case in cases:
        truth = check_truth(case, workflows)
        got = rules(case, workflows[truth["area"]])
        # the first request asks; «Frist wahren» (A13) goes before it and the first request follows with the same list
        want = set(truth.get("ask_now", [])) if truth["action"] in ("A1", "A13") else set()
        diff = {}
        if set(got["now"]) != want:
            diff["now"] = {"rules_only": sorted(set(got["now"]) - want), "truth_only": sorted(want - set(got["now"]))}
        dated = {i: d for i, d in got["deadlines"]}
        wrong = [d["id"] for d in truth.get("deadline", []) if deadline_verdict(d, dated) != "right"]
        if wrong:
            diff["deadlines"] = wrong
        if got["action"] != truth["action"]:
            diff["action"] = {"rules": got["action"], "truth": truth["action"]}
        if truth.get("key_points") is not None and set(got["key_points"]) != set(truth["key_points"]):
            diff["key_points"] = {"rules_only": sorted(set(got["key_points"]) - set(truth["key_points"])),
                                  "truth_only": sorted(set(truth["key_points"]) - set(got["key_points"]))}
        rows.append((short_id(case), truth["area"], got, diff))
    return rows


def main(command, paths, catalogue=None):
    workflows = areas(catalogue)
    if command == "self-check":
        cases = load_suite(paths[0])
        rows = self_check(cases, workflows)
        for cid, area_id, got, diff in rows:
            print(json.dumps({"case": cid, "area": area_id, "action": got["action"], "now": got["now"], "offered": got["offered"],
                              "later": got["later"], "deadlines": got["deadlines"], "key_points": got["key_points"],
                              **({"differs": diff} if diff else {})}, ensure_ascii=False))
        print(json.dumps({"cases": len(rows), "differ": sum(1 for r in rows if r[3])}))
        return
    if len(paths) < 2:
        sys.exit("score-saved needs <results.json> <suite dir>")
    rows = json.loads(Path(paths[0]).read_text())
    cases = load_suite(paths[1])
    for case in cases:
        check_truth(case, workflows)
    print(render(score_saved(rows, cases, workflows)))

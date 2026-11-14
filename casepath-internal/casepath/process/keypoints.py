"""The legal key points of an area: what a specialist looks for first when a case of the area is opened.

Each area module lists its key points (``key_points``): an id, a short statement for the handler («Kündigung
möglicherweise nichtig: Sperrfrist»), the condition on facts under which it applies, the article it rests on (law
references of the module or the backbone, each with its verbatim passage and whether it was checked against the official
text), what follows from it (one sentence the assessment letter can use), what still has to be checked, a short question
for when the condition depends on a fact the file leaves open («Arbeitsunfähigkeit bei Kündigung? Dann Sperrfrist
prüfen»), and optionally words a customer's question about it would contain (``answers``).

A point whose condition holds on the case's facts applies; one whose condition is open is shown as its question, never
asserted; one whose condition fails is not shown. Model-free: the facts are the ones the run read or the handler set.
"""
import re

from .workflows import CatalogueError, condition_facts, evaluate_condition

SHOWN = 2  # the card shows at most two, each on one line
FIELDS = ("id", "statement", "question", "when", "law", "follows", "check")


def validate(module, law, where):
    """A key point needs a condition on facts, an article with its passage, and a statement (plus what follows from it,
    what to check and its open question). ``law``: the law entries the module may cite (its own and the backbone's)."""
    points = module.get("key_points", [])
    if not isinstance(points, list):
        raise CatalogueError(f"{where}: key_points must be a list")
    seen = set()
    for p in points:
        name = f"{where}: key point {p.get('id')!r}" if isinstance(p, dict) else f"{where}: a key point"
        if not isinstance(p, dict) or any(not p.get(f) for f in FIELDS):
            raise CatalogueError(f"{name} needs {', '.join(FIELDS)}: a condition, an article with a passage and a statement")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", p["id"]) or p["id"] in seen:
            raise CatalogueError(f"{name}: its id must be unique, lower case")
        seen.add(p["id"])
        if not isinstance(p["when"], dict) or not condition_facts(p["when"]):
            raise CatalogueError(f"{name}: the condition names facts of the case (a point that always applies is a hint)")
        if not 3 <= len(p["statement"]) <= 80 or not 3 <= len(p["question"]) <= 90:
            raise CatalogueError(f"{name}: statement and question are one short line each")
        refs = p["law"] if isinstance(p["law"], list) else [p["law"]]
        for ref in refs:
            key = str(ref).split("#", 1)[1] if str(ref).startswith("law#") else None
            if not key or not str((law.get(key) or {}).get("passage") or "").strip():
                raise CatalogueError(f"{name}: {ref!r} must name a law entry with its verbatim passage")
        if not all(isinstance(a, str) and a.strip() for a in p.get("answers", [])):
            raise CatalogueError(f"{name}: answers are words a customer's question would contain")
    return points


def _law_rows(graph, refs):
    law = graph.get("law") or {}
    rows = []
    for ref in refs if isinstance(refs, list) else [refs]:
        row = law.get(str(ref).split("#", 1)[-1])
        if row:
            rows.append({"cite": row["cite"], "passage": row["passage"], "verified": bool(row.get("verified"))})
    return rows


def evaluate(graph, facts):
    """Every key point of the area that applies or is open, in the module's order: {id, state, text, statement,
    question, law (the rows of its articles), cite, follows, check, facts, answers}."""
    out = []
    for p in (graph or {}).get("key_points") or ():
        holds = evaluate_condition(p["when"], facts or {})
        if holds is False:
            continue
        rows = _law_rows(graph, p["law"])
        out.append({"id": p["id"], "state": "applies" if holds else "open", "text": p["statement"] if holds else p["question"],
                    "statement": p["statement"], "question": p["question"], "law": rows, "cite": rows[0]["cite"] if rows else None,
                    "follows": p["follows"], "check": p["check"], "facts": sorted(condition_facts(p["when"])),
                    "answers": p.get("answers", [])})
    return out


def shown(points, limit=SHOWN):
    """The points the card shows: those that apply first, then open ones as questions, at most ``limit``."""
    return ([p for p in points if p["state"] == "applies"] + [p for p in points if p["state"] == "open"])[:limit]


def sentence(point):
    """The point as the assessment letter states it: what follows, with its article."""
    text = point["follows"].rstrip(".")
    return f"{text} ({point['cite']})." if point.get("cite") else f"{text}."


def answer_for(question, points):
    """The key point that answers a customer's question: the first that applies and whose words the question contains."""
    q = str(question or "").lower()
    return next((p for p in points if p["state"] == "applies" and any(w.lower() in q for w in p.get("answers", []))), None)

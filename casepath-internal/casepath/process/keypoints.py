"""The legal key points of an area: what a specialist looks for first when a case of the area is opened.

Each area module lists its key points (``key_points``): an id, a short statement for the handler («Kündigung
möglicherweise nichtig: Sperrfrist»), the condition on facts under which it applies, the article it rests on (law
references of the module or the backbone, each with its verbatim passage and whether it was checked against the official
text), what follows from it (one sentence the assessment letter can use), what still has to be checked, a short question
for when the condition depends on a fact the file leaves open («Arbeitsunfähigkeit bei Kündigung? Dann Sperrfrist
prüfen»), and optionally words a customer's question about it would contain (``answers``).

Each point names whether it is advice the customer can act on now (``advice``: the sentence for the first request, or
false): such a point goes into the first letter as a hint line with its article, ticked when its condition holds and
offered while it depends on an open fact. In an area observed in practice (its lines carry counts) the first request's
ticked lines are those practice supports: advice is offered unticked unless the point names a practice reference
(``source_refs``, «practice#…»), and where an observed hint says the same the hint stays as observed and the advice is
not added. Each point names the stages at which it helps (``stages``, by default
clarifying and assessing); at a later stage the card shows only the points for that stage, or none.

A point whose condition holds on the case's facts applies; one whose condition is open is shown as its question, never
asserted; one whose condition fails is not shown. Model-free: the facts are the ones the run read or the handler set.
"""
import re

from .workflows import CatalogueError, condition_facts, evaluate_condition

SHOWN = 2  # the card shows at most two, each on one line
STAGES = ("klaeren", "beurteilen")  # where a key point helps unless it names its own stages
FIELDS = ("id", "statement", "question", "when", "law", "follows", "check")


def validate(module, law, where, stages=None):
    """A key point needs a condition on facts, an article with its passage, and a statement (plus what follows from it,
    what to check and its open question), says whether it is advice the customer can act on, and names only stages of
    the backbone. ``law``: the law entries the module may cite (its own and the backbone's)."""
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
        advice = p.get("advice")
        if advice is not False and not (isinstance(advice, str) and 20 <= len(advice) <= 300 and not advice.rstrip().endswith(".")):
            raise CatalogueError(f"{name}: advice is the sentence the customer can act on (its article is added), or false")
        if "source_refs" in p and (not isinstance(p["source_refs"], list) or not all(str(r).startswith("practice#") for r in p["source_refs"])):
            raise CatalogueError(f"{name}: source_refs name what practice shows of the point («practice#…»)")
        if "stages" in p and (not isinstance(p["stages"], list) or not p["stages"] or (stages is not None and set(p["stages"]) - set(stages))):
            raise CatalogueError(f"{name}: stages must name stages of the backbone")
    return points


def _law_rows(graph, refs):
    law = graph.get("law") or {}
    rows = []
    for ref in refs if isinstance(refs, list) else [refs]:
        row = law.get(str(ref).split("#", 1)[-1])
        if row:
            rows.append({"cite": row["cite"], "passage": row["passage"], "verified": bool(row.get("verified"))})
    return rows


def evaluate(graph, facts, stage=None, failing=False, weak=frozenset()):
    """Every key point of the area that applies or is open, in the module's order: {id, state, text, statement,
    question, law (the rows of its articles), cite, follows, check, facts, answers, advice, stages, here, missing, weak,
    asks}; ``here`` says whether it helps at ``stage`` (always true without a stage). With ``failing`` a point whose
    condition fails is listed too, its state «fails». ``missing``: the facts of its condition the file leaves open;
    ``weak``: those whose value rests on a contradictory or presumed reading (``weak``, fact ids); ``asks``: each condition
    fact's question for the customer (its customer question, else its question)."""
    out = []
    defs = {f["id"]: f for f in (graph or {}).get("facts") or ()}
    for p in (graph or {}).get("key_points") or ():
        holds = evaluate_condition(p["when"], facts or {})
        if holds is False and not failing:
            continue
        rows = _law_rows(graph, p["law"])
        named = sorted(condition_facts(p["when"]))
        out.append({"id": p["id"], "state": "applies" if holds else "open" if holds is None else "fails",
                    "text": p["question"] if holds is None else p["statement"],
                    "statement": p["statement"], "question": p["question"], "law": rows, "cite": rows[0]["cite"] if rows else None,
                    "follows": p["follows"], "check": p["check"], "facts": named,
                    "answers": p.get("answers", []), "advice": p.get("advice") or None, "stages": list(p.get("stages") or STAGES),
                    "refs": list(p["law"] if isinstance(p["law"], list) else [p["law"]]), "observed": observed(p),
                    "here": stage is None or stage in (p.get("stages") or STAGES),
                    "missing": [f for f in named if (facts or {}).get(f) is None], "weak": [f for f in named if f in (weak or ())],
                    "asks": {f: (defs.get(f) or {}).get("customer_question") or (defs.get(f) or {}).get("question") or f for f in named}})
    return out


def shown(points, limit=SHOWN):
    """The points the card shows: those for the case's stage, those that apply first, then open ones as questions, at
    most ``limit``."""
    here = [p for p in points if p.get("here", True)]
    return ([p for p in here if p["state"] == "applies"] + [p for p in here if p["state"] == "open"])[:limit]


def observed(row):
    """Whether practice shows a line (a hint, a fact's question, a key point, a template): it cites a practice count."""
    return any(str(r).startswith("practice#") for r in (row or {}).get("source_refs") or ())


def advice_line(point):
    """The point's advice as the first request gives it: the sentence with its article, «… (Art. 318 OR).»"""
    return f"{point['advice']} ({point['cite']})." if point.get("cite") else f"{point['advice']}."


def covers(point, hint):
    """Whether a hint of the area says what the point's advice says: every article it cites is one of the point's."""
    refs = [r for r in hint.get("source_refs") or () if str(r).startswith("law#")]
    return bool(refs) and set(refs) <= set(point.get("refs") or ())


def sentence(point):
    """The point as the assessment letter states it: what follows, with its article."""
    text = point["follows"].rstrip(".")
    return f"{text} ({point['cite']})." if point.get("cite") else f"{text}."


def answer_for(question, points):
    """The key point that answers a customer's question: of those that apply, the one whose word in the question is the
    most specific (the longest; «Krankentaggeld» is about pay, not about being ill), the first on a tie. A word alone
    never answers a question (``status``): this is the keyword candidate the guards compare the reader's tags with."""
    q = str(question or "").lower()
    best = max(((max(len(w) for w in p.get("answers", []) if w.lower() in q), -i, p) for i, p in enumerate(points)
                if p["state"] == "applies" and any(w.lower() in q for w in p.get("answers", []))), default=None, key=lambda x: x[:2])
    return best[2] if best else None


# Whether a customer's question is answered, and by what -----------------------------------------------------------------
# The reader tags each question with the key points whose rule it asks about (``about``); code decides whether the rule
# answers it. A keyword alone never answers: the tag is checked by deterministic guards that do not trust it (a negation
# before a word of the point, a point whose wish the customer rejected, a keyword point that disagrees, mixed tags, a weak
# fact, an intent the area's answers do not know). A question a guard holds is «prüfen» with its drafted answer offered to
# the handler, never stated in the letter until taken.

NEGATIONS = frozenset({"nicht", "kein", "keine", "keinen", "keiner", "keinem", "nie", "niemals", "ohne"})
WORDS = re.compile(r"[a-zäöüß]+")
DISCUSS = "vorher mit uns besprechen"


def negated(question, words, carrying=()):
    """Whether a negation stands within three words before one of ``words`` (a point's keywords, an intent's stems) in
    the question. A negation that belongs to a word carrying it («nicht zahl», «nicht zahlen») does not count."""
    q = str(question or "").lower()
    tokens = [(m.start(), m.end(), m.group()) for m in WORDS.finditer(q)]
    own = set()
    for stem in carrying:
        for m in re.finditer(re.escape(stem), q):
            own |= {i for i, (s, e, _) in enumerate(tokens) if s < m.end() and e > m.start()}
    for word in words:
        for m in re.finditer(re.escape(word), q):
            at = next((i for i, (s, e, _) in enumerate(tokens) if s <= m.start() < e), None)
            if at is None:
                continue
            if any(tokens[j][2] in NEGATIONS and j not in own for j in range(max(0, at - 3), at)):
                return True
    return False


def status(question, points, candidate, intent, facts, wishes=None):
    """Whether a customer's question is answered: {row, state, points, intent, reason, offered, ask, next}. ``question``:
    the brief's question (its text and ``about``, the reader's tags); ``points``: the area's key points evaluated with
    ``failing``; ``candidate``: the key point its words name (answer_for); ``intent``: the area's answer row the question
    asks (options.intent), or None; ``wishes``: {wish fact: its words}. The first row of the table that applies decides
    (``row``, 1-11): no valid tag (1 a keyword proposes, 2 nothing does), 3 a negation before a word of a tagged point or of
    the intent, 4 a tagged point's wish is false, 5 a keyword point that applies is not tagged, 6 a tagged point fails, 7
    one rests on a weak fact, 8 one is open, 9-10 all apply and the intent says «bedingt» or «beantwortet», 11 no intent.
    ``offered``: the points whose answer the handler may take («prüfen»); ``ask``: the fact an open point waits for."""
    text = str((question or {}).get("question") or "")
    by_id = {p["id"]: p for p in points or ()}
    tagged = [by_id[t] for t in dict.fromkeys((question or {}).get("about") or ()) if t in by_id]
    cand = candidate if candidate and candidate.get("state") == "applies" else None
    ids = [p["id"] for p in tagged]
    applying = [p["id"] for p in tagged if p["state"] == "applies"]

    def out(row, state, reason=None, offered=(), ask=None):
        return {"row": row, "state": state, "points": ids, "intent": (intent or {}).get("intent"), "reason": reason,
                "offered": list(dict.fromkeys(offered)), "ask": ask, "next": (intent or {}).get("next") if row == 9 else None}
    if not tagged:
        return out(1, "pruefen", "Vorschlag (Stichwort)", [cand["id"]]) if cand else out(2, "offen", "keine Regel des Gebiets")
    words = [str(w).lower() for p in tagged for w in p.get("answers") or ()] + list((intent or {}).get("stems") or ())
    carrying = [w for w in words if NEGATIONS & set(WORDS.findall(w))]
    if negated(text, words, carrying):
        return out(3, "pruefen", "Verneinung: Zuordnung prüfen", applying)
    rejected = next((f for p in tagged for f in p["facts"] if f in (wishes or {}) and (facts or {}).get(f) is False), None)
    if rejected:
        return out(4, "pruefen", f"Sie möchten {wishes[rejected]} nicht: Zuordnung prüfen", applying)
    if cand and cand["id"] not in ids:
        return out(5, "pruefen", "Zuordnung prüfen", applying + [cand["id"]])
    if any(p["state"] == "fails" for p in tagged):
        others = applying + ([cand["id"]] if cand else [])
        return out(6, "pruefen", "Zuordnung prüfen", others) if others else out(6, "offen", "Regel trifft nach der Akte nicht zu")
    weak = next(((p, f) for p in tagged for f in p.get("weak") or ()), None)
    if weak:
        return out(7, "pruefen", f"beruht auf einer widersprüchlichen oder vermuteten Angabe: {weak[0]['asks'].get(weak[1], weak[1])}", applying)
    opened = next((p for p in tagged if p["state"] == "open"), None)
    if opened:
        fact = (opened.get("missing") or [None])[0]
        asked = opened["asks"].get(fact) if fact else opened["question"]
        return out(8, "bedingt", asked, ask={"fact": fact, "question": asked, "point": opened["id"]})
    if intent and intent.get("state") == "bedingt":
        return out(9, "bedingt", DISCUSS if (intent.get("next") or {}).get("kind") == "discuss" else None)
    if intent:
        return out(10, "beantwortet")
    return out(11, "pruefen", "Absicht der Frage unklar", ids)


# The short facts a handler needs at a later stage (the backbone's ``stage_lines``) ------------------------------------
# At the mandate and handling stages the card leads with what the file establishes about the mandate: the cost guarantee
# given (its date), the firm's last report (its date), open cost claims (how many), an offer awaiting an answer. Each
# line comes from facts the run already reads (the history of actions, the incoming items), with their sources; a line
# whose fact is not established is not shown.

SHOWS = {"date", "latest", "open_count", "open_latest"}


def validate_lines(backbone, steps):
    action_kinds, kinds = backbone.get("action_kinds") or {}, {k["id"] for k in backbone.get("incoming") or ()}
    seen = set()
    for row in backbone.get("stage_lines") or ():
        where = f"backbone: stage line {row.get('id')!r}"
        source = row.get("from") or {}
        if not row.get("id") or row["id"] in seen or not 3 <= len(str(row.get("label") or "")) <= 50:
            raise CatalogueError(f"{where} needs its own id and a short label")
        seen.add(row["id"])
        if not isinstance(row.get("stages"), list) or not row["stages"] or set(row["stages"]) - set(steps):
            raise CatalogueError(f"{where}: stages must name stages of the backbone")
        if source.get("show") not in SHOWS or not ((source.get("action") and f"A{source['action']}" in action_kinds and source["show"] == "date")
                                                     or (source.get("incoming") in kinds and source["show"] != "date")):
            raise CatalogueError(f"{where}: from names an action kind (show date) or an incoming kind (latest, open_count, open_latest)")


def _day(d):
    return d.strftime("%d.%m.%Y")


def stage_lines(graph, facts, rows, dated=None, stage=None):
    """The backbone's lines for the case's stage that the file establishes: [{id, label, text, facts, citations}]."""
    from . import incoming
    from .clock import parse_date
    from .workflows import done_actions
    out = []
    cites = lambda fact: ((rows or {}).get(fact) or {}).get("citations") or []
    for row in (graph or {}).get("stage_lines") or ():
        if stage not in row["stages"]:
            continue
        source = row["from"]
        if source.get("action"):
            days = sorted(d for x in done_actions(facts or {}).get(str(source["action"]), []) if (d := parse_date(x)))
            if days:
                fact = f"handlung_a{source['action']}" if (facts or {}).get(f"handlung_a{source['action']}") else "bisherige_handlungen"
                out.append({"id": row["id"], "label": row["label"], "text": f"{row['label']}: {_day(days[-1])}", "facts": [fact], "citations": cites(fact)})
            continue
        items = [r for r in incoming.items(graph, facts or {}, dated) if r["kind"]["id"] == source["incoming"]]
        open_ = [r for r in items if r["open"]]
        dated_items = sorted((r for r in (open_ if source["show"] == "open_latest" else items) if r["date"]), key=lambda r: r["date"])
        if source["show"] == "open_count" and open_:
            out.append({"id": row["id"], "label": row["label"], "text": f"{row['label']}: {len(open_)}", "facts": [r["fact"] for r in open_],
                        "citations": [c for r in open_ for c in cites(r["fact"])][:3]})
        elif source["show"] in {"latest", "open_latest"} and dated_items:
            last = dated_items[-1]
            out.append({"id": row["id"], "label": row["label"], "text": f"{row['label']}: {_day(parse_date(last['date']))}", "facts": [last["fact"]],
                        "citations": cites(last["fact"])})
    return out

"""The decision brief of the legal assessment (A5) and the parts of its letter, from what the case establishes.

The handler opens a reply and finds the assessment prepared: what the customer wants and asks, the rule each question asks
about with its conditions and how the case meets them, the ways to proceed with a recommendation to adopt or correct, what
would change it, and a residual request for only what is still missing. Code decides; the reader only tags the questions
(``about``) and reads the claims; nothing here calls a model.

- Each customer question is evaluated by the key point its tags name and the intent its words ask (keypoints.status, the
  guard table): «beantwortet» or «bedingt» (with its smallest next step) from the area's answers (options.py), «prüfen»
  with a drafted answer the handler takes with one click, or «offen». A question the handler answered so stays answered.
- The options of the area hold on established, accepted facts only; one holding, proposable option per wish is proposed;
  the handler's adoption («übernehmen») holds while its options hold and the proposal is the one adopted.
- «In Ihrem Fall» states the wish, the replies, the facts the recommendation rests on (each with its source and date) and
  the costs claimed; «Bitte reichen Sie uns noch nach» asks for the receipts of a claimed cost and what is still owed.
- Areas without an options file get the brief and the questions' evaluation; no recommendation is filled.

``build`` returns the brief; ``evaluate_questions`` gives the item list its customer questions (items.py). Model-free.
"""
import re

from . import account, customer_letters, keypoints, options, review as reviews
from .clock import parse_date

TAKEN = "beantwortet (Fallbearbeitung)"
GAP_WHAT = {"wish": "was Sie möchten", "replies_all": "Ihre Antworten auf unsere Fragen", "replies_some": "Ihre Antworten auf unsere Fragen",
            "claims": "die geltend gemachten Kosten", "claim_amount": "der genannte Betrag", "claim_line": "Belege zu den geltend gemachten Kosten",
            "join": "die weitere Empfehlung", "conditional": "was noch fehlt", "discuss": "das weitere Vorgehen"}
ANSWER = "Antwort auf diese Frage"
RECOMMENDATION = "die Empfehlung an die Kundschaft"
EMPFEHLUNG = "point:empfehlung"
PROSPECTS_LOW = "aussichten_nicht_genuegend"


def gap(what):
    from .letters import gap as letter_gap
    return letter_gap(what)


def _evidence(citations):
    return [{"file": c.get("file"), "page": c.get("page"), "quote": c.get("quote")} for c in citations or () if c]


def _day(value):
    d = parse_date(value) if value else None
    return d.strftime("%d.%m.%Y") if d else None


# What the case establishes, and how surely -----------------------------------------------------------------------------

def fact_rows(result):
    return {f["fact"]: f for f in (result or {}).get("facts") or () if f.get("fact")}


def weak_of(result, state):
    """The facts whose value rests on a presumption or on two readings that differ: {fact: "presumed" | "conflicting"}.
    A fact the handler set is never weak."""
    own = set((state or {}).get("overrides") or {})
    return {f["fact"]: f["status"] for f in (result or {}).get("facts") or ()
            if f.get("status") in ("presumed", "conflicting") and f.get("fact") not in own}


def stated(fact, result, state):
    """Whether «In Ihrem Fall» may state a fact: the handler set it, or the run established it with a quote the source
    checker accepted. A presumed or contradictory value never."""
    if fact in ((state or {}).get("overrides") or {}):
        return True
    row = fact_rows(result).get(fact) or {}
    return row.get("status") == "established" and row.get("verdict") == "accepted" and bool(row.get("citations"))


def read_of(fact, result, state):
    """How a fact was read: «Fallbearbeitung» (set by the handler), «zweimal» (a second reading agreed), «einmal gelesen»
    (one reading only), None (not established)."""
    if fact in ((state or {}).get("overrides") or {}):
        return "Fallbearbeitung"
    row = fact_rows(result).get(fact) or {}
    if row.get("status") != "established" or row.get("verdict") != "accepted":
        return None
    return "zweimal" if row.get("read_twice") else "einmal gelesen"


def fact_evidence(fact, result, state, data=None):
    """The quotes a fact rests on; an implied fact rests on the quotes of the facts that imply it."""
    rows = fact_rows(result)
    cites = (rows.get(fact) or {}).get("citations") or []
    if not cites and data:
        for source in options.implied_by(fact, (state or {}).get("facts") or {}, data):
            cites = cites + ((rows.get(source) or {}).get("citations") or [])
    return _evidence(cites)


def question_of(graph, fact):
    row = next((f for f in (graph or {}).get("facts") or () if f["id"] == fact), {})
    return re.sub(r"\s*\((Entscheid|CasePath)[^)]*\)?", "", str(row.get("question") or fact)).strip()


def quoted_day(cite, acc):
    """The date of the document a quote comes from: of the account's entries in the quote's file, the one whose own quote
    stands closest before it on the same page, else the nearest page before, else the only one. None when unknown."""
    entries = [e for e in (acc or {}).get("entries") or () if e.get("date") and e.get("file") == (cite or {}).get("file")]
    best = None
    for e in entries:
        own = next((c for c in e.get("citations") or () if c.get("file") == cite.get("file")), None)
        if own and own.get("page") == cite.get("page") and (own.get("start") or 0) <= (cite.get("start") or 0):
            if best is None or (own.get("start") or 0) > best[0]:
                best = ((own.get("start") or 0), e)
    if best:
        return best[1]["date"]
    paged = [e for e in entries if e.get("page") is not None and cite.get("page") is not None and e["page"] <= cite["page"]]
    if paged:
        return max(paged, key=lambda e: e["page"])["date"]
    return entries[0]["date"] if len(entries) == 1 else None


# The log: answers the handler took, the adoption of the recommendation ------------------------------------------------

def taken_answers(events):
    """{customer_question:i: the latest item.corrected that took an answer for it}."""
    out = {}
    for e in events or ():
        if e.get("kind") == "item.corrected" and str(e.get("item_id") or "").startswith("customer_question:") and e.get("point"):
            out[e["item_id"]] = e
    return out


def adoption_of(events):
    """The latest decision on the recommendation (item.corrected on «point:empfehlung»), or None."""
    return next((e for e in reversed(list(events or ())) if e.get("kind") == "item.corrected" and e.get("item_id") == EMPFEHLUNG), None)


def ticked(events):
    from .letters import line_state
    return line_state(events)


# Claims and the residual ------------------------------------------------------------------------------------------------

def claims_of(result):
    """The costs the customer asks to have compensated, as the reading located them: [{i, what, amount, checked,
    documented, citations, receipt}] in the brief's order (``i`` its place there)."""
    return [{**c, "i": i} for i, c in enumerate(((result or {}).get("brief") or {}).get("claims") or ())]


def _document(items, need):
    return next((i for i in items or () if i["kind"] == "document" and i["key"] == need), None)


def need_lines(data, option_id, claims, items, events=None):
    """What an option's needs still ask for: one «Belege zu: …» per claimed cost (named, its words in its quote) that no
    receipt documents, even when the need reads present; without a claim, the need's title while it is not present."""
    o = options.option(data, option_id) or {}
    lines = []
    for need in o.get("needs") or ():
        doc = _document(items, need["document"])
        present = bool(doc) and doc.get("status") == "present"
        if need.get("names_claim"):
            named = [c for c in claims if c.get("checked")]
            if named:
                for c in named:
                    if not c.get("documented"):
                        lines.append({"key": f"residual:claim.{c['i']}", "line": data["wording"]["claim_line"].replace("{posten}", c["what"]),
                                      "kind": "claim", "ref": c["i"], "evidence": _evidence(c.get("citations")), "wording": "claim_line"})
                continue
        if not present and doc is not None:
            lines.append({"key": f"residual:document.{need['document']}", "line": (doc.get("label") or {}).get("de") or need["document"],
                          "kind": "document", "ref": need["document"], "evidence": []})
    return lines


# The assessment before the cover decision -------------------------------------------------------------------------------

ASSESSING = "beurteilen"


def _conjuncts(condition):
    """The single-fact conditions a condition requires («all» parts, or itself)."""
    if not isinstance(condition, dict):
        return []
    if "all" in condition:
        return [c for part in condition["all"] for c in _conjuncts(part)]
    return [condition] if condition.get("fact") else []


def premise_assessment(graph, ev, here, facts):
    """The assessment (A5) prepared before the handler's own decision, as items.build_items plans it, or None: the case is
    at «klären», the first request went out and the customer answered, and the stage of the assessment is open only on
    decisions the handler alone takes (the cover). The action carries the premise it is written on ({"deckung":
    "bestätigt"}): the decision is the one thing the card asks, and the letter is approved only once it is taken. A
    first-request cut never qualifies; the clock, what came in and «Frist wahren» still lead over it."""
    from .workflows import done_actions
    if (here or {}).get("id") != "klaeren" or facts.get("a1_versandt") is not True or facts.get("kunde_geantwortet") is not True:
        return None
    pending = next((b for b in (ev or {}).get("beyond") or () if b["step"] == ASSESSING and b["state"] == "pending"), None)
    deciding = (pending or {}).get("depends_on") or []
    own = {f["id"] for f in (graph or {}).get("facts") or () if f.get("handler_only")}
    if not deciding or not set(deciding) <= own:
        return None
    target = next((s for s in graph["steps"] if s["id"] == ASSESSING), {}).get("action") or {}
    if not target or target["kind"][1:] in done_actions(facts):
        return None
    premise = {}
    for fact in deciding:  # the value the way to the assessment needs, from the stage's edges to it
        values = {leaf.get("is") for e in here.get("next") or () if e["to"] == ASSESSING for leaf in _conjuncts(e.get("when"))
                  if leaf.get("fact") == fact and "is" in leaf}
        if len(values) != 1:
            return None
        premise[fact] = values.pop()
    words = "nach dem Deckungsentscheid" if set(premise) == {"deckung"} else "nach dem Entscheid der Fallbearbeitung"
    return {"kind": target["kind"], "title": target["title"], "next_in_days": target.get("next_in_days"), "follow_up": target.get("follow_up"),
            "skip_if": None, "premise": premise, "reason": f"Kundschaft hat geantwortet; Einschätzung {words}"}


# The customer's questions -------------------------------------------------------------------------------------------------

def enclosed(items, events, template_id):
    """Whether a template for the customer's own letter goes out with the assessment (and the letter refers to it)."""
    return any(i["key"] == template_id and not i.get("review") for i in customer_letters.with_letter(items, events, "A5"))


def _context(state, result, items, events, marks=None):
    graph = (state or {}).get("process") or {}
    data = options.load(graph.get("id")) if graph.get("id") else None
    facts = options.implied((state or {}).get("facts") or {}, data)
    weak = weak_of(result, state)
    flagged = reviews.flags(graph, marks)
    points = [p for p in keypoints.evaluate(graph, facts, failing=True, weak=set(weak)) if not flagged.key_point(p["id"])]
    return graph, data, facts, weak, flagged, points


def applying_points(state, result, items, events, marks=None):
    """The key points that apply on the case's facts (the options file's implications applied), without those a jurist
    marked «Änderung nötig»: the rules whose answer the handler may take."""
    return [p for p in _context(state, result, items, events, marks)[5] if p["state"] == "applies"]


def _answer_row(data, intent_id):
    return next((a for a in (data or {}).get("answers") or () if a["intent"] == intent_id), None)


def _residual_named(data, option_id, claims, items, events):
    """Whether the letter's residual names what an option needs (its lines, as far as the handler left them ticked)."""
    lines = need_lines(data, option_id, claims, items, events)
    state = ticked(events)
    return any(state.get(l["key"], True) for l in lines)


def evaluate_questions(state, result, items, events, marks=None):
    """Each of the brief's customer questions, evaluated: [{i, item_id, text, about, row, state, reason, points, intent,
    answer, answered_by, offered [{point, intent, text}], ask, next, taken, held}] in the brief's order. ``items``: the
    item list built so far (the templates that go out with the assessment, the documents present)."""
    graph, data, facts, weak, flagged, points = _context(state, result, items, events, marks)
    brief = (result or {}).get("brief") or {}
    if not graph:
        return []
    by_id = {p["id"]: p for p in points}
    wishes = {w["fact"]: w["text"] for w in (data or {}).get("wishes") or ()}
    claims = claims_of(result)
    taken = taken_answers(events)

    def held(row):
        return bool(row) and flagged.answer(row["points"][0], row["intent"])

    def render(point_id, intent_row):
        """The answer of a point for one intent, as the letter would say it; the point's own sentence without an intent."""
        if intent_row is not None and data:
            nxt = intent_row.get("next") or {}
            residual = nxt.get("kind") != "residual" or _residual_named(data, nxt["option"], claims, items, events)
            template = all(enclosed(items, events, p["with_template"]) for p in intent_row["parts"] if p.get("with_template"))
            return options.answer_text(data, graph, intent_row, template=template, residual=residual)
        return keypoints.sentence(by_id[point_id])

    def offer(ids, text):
        out = []
        for pid in ids:
            row = options.intent(text, options.answers_for(data, [pid])) if data else None
            if row is not None and held(row):
                continue
            out.append({"point": pid, "intent": (row or {}).get("intent"), "text": render(pid, row)})
        return out
    out = []
    for i, q in enumerate(brief.get("questions") or ()):
        text = str(q.get("question") or "")
        item_id = f"customer_question:{i}"
        valid = [t for t in dict.fromkeys(q.get("about") or ()) if t in by_id]
        candidate = keypoints.answer_for(text, points)
        rows = options.answers_for(data, valid or ([candidate["id"]] if candidate else [])) if data else []
        intent_row = options.intent(text, rows) if data else None
        st = keypoints.status({"question": text, "about": valid}, points, candidate, intent_row, facts, wishes)
        row = {"i": i, "item_id": item_id, "text": text, "about": list(q.get("about") or ()), "row": st["row"], "state": st["state"],
               "reason": st["reason"], "points": st["points"], "intent": st["intent"], "answer": None, "answered_by": None,
               "offered": [], "ask": st["ask"], "next": st["next"], "taken": False, "held": False, "evidence": _evidence(q.get("citations"))}
        took = taken.get(item_id)
        if took and (by_id.get(took["point"]) or {}).get("state") == "applies":  # the handler took an answer: it stays while its point applies
            chosen = _answer_row(data, took.get("intent")) if took.get("intent") else None
            row.update(state="beantwortet", reason=TAKEN, row=None, taken=True, answered_by=took["point"], ask=None, next=None,
                       answer=render(took["point"], chosen), points=list(dict.fromkeys([took["point"]] + st["points"])),
                       intent=(chosen or {}).get("intent") or st["intent"], by=took.get("expert"), at=took.get("at"))
            out.append(row)
            continue
        if st["state"] in ("beantwortet", "bedingt") and not data:
            # an area without an options file: the point's sentence is offered, never stated by itself (A9)
            row.update(state="pruefen", reason=st["reason"] if st["state"] == "bedingt" else "Absicht der Frage unklar",
                       offered=offer([p for p in st["points"] if by_id[p]["state"] == "applies"], text))
        elif st["state"] in ("beantwortet", "bedingt"):
            if intent_row is not None and held(intent_row):
                row.update(state="pruefen", reason="Antwort in Prüfung", held=True)
            else:
                nxt = (intent_row or {}).get("next") or {}
                residual = nxt.get("kind") != "residual" or _residual_named(data, nxt["option"], claims, items, events)
                template = all(enclosed(items, events, p["with_template"]) for p in (intent_row or {}).get("parts") or () if p.get("with_template"))
                ask = (st["ask"] or {}).get("question")
                wording_held = bool(ask) and flagged.wording("conditional")
                answer = options.answer_text(data, graph, intent_row, template=template, residual=residual,
                                             ask=None if wording_held else ask) if (intent_row or ask) else None
                if wording_held:
                    answer = " ".join(x for x in (answer, gap(f"{GAP_WHAT['conditional']} ({reviews.IN_REVIEW})")) if x)
                if nxt.get("kind") == "residual":  # the answer points to the receipts asked below: they are asked below
                    row["next"] = nxt if residual else None
                    lines = [l for l in need_lines(data, nxt["option"], claims, items, events) if ticked(events).get(l["key"], True)]
                    if residual and lines and st["row"] == 9:
                        row["reason"] = lines[0]["line"]  # what it waits for: the first line of the residual it points to
                row.update(answer=answer, answered_by=st["points"][0] if st["state"] == "beantwortet" else None)
        else:
            row["offered"] = offer(st["offered"], text)
        out.append(row)
    return out


def account_questions(acc, questions):
    """The customer's questions the account holds that the brief does not (a question in a reply the reader did not list):
    [{request, what, first, citations}], unanswered."""
    out = []
    for r in (acc or {}).get("requests") or ():
        if r["by"] != "kunde" or r["of"] != account.INSURER or r["answered"] is not None:
            continue
        if any(account.overlap(r["what"], q["text"]) >= 0.5 for q in questions):
            continue
        out.append({"request": r["id"], "what": r["what"], "first": r["first"], "citations": r["citations"]})
    return out


def request_of(acc, text):
    """The account's row of a customer's question (the request it asked), or None."""
    rows = [r for r in (acc or {}).get("requests") or () if r["by"] == "kunde" and r["of"] == account.INSURER]
    score, _, row = account._best(rows, text) if rows else (0.0, 0, None)
    return row if row is not None and score >= 0.5 else None


# The brief ------------------------------------------------------------------------------------------------------------

def _option_facts(data, option_id, facts):
    o = options.option(data, option_id) or {}
    named = [o["wish"]] + [c["fact"] for c in o.get("when") or ()] + [c["fact"] for c in o.get("conditions") or () if c.get("fact")]
    out = []
    for f in named:
        out.append(f)
        out += options.implied_by(f, facts, data)
    return list(dict.fromkeys(out))


def _sentence(text):
    text = text.rstrip()
    return text if re.search(r"[.?!]»?$", text) else f"{text}."


def build(state, result, items, files, events, marks):
    """The decision brief of the prepared action: wishes, questions, rules with their conditions, the options with the
    proposal and the adoption, what would change it, the residual and the asks, the letter's parts (an assessment of an
    area with an options file only), what blocks the approval, the premise the letter rests on, and a summary. None for a
    case without a process."""
    graph, data, facts, weak, flagged, points = _context(state, result, items, events, marks)
    if not graph:
        return None
    case_facts = (state or {}).get("facts") or {}
    acc = (state or {}).get("account")
    area_id = graph.get("id")
    act = next((i for i in items or () if i["kind"] == "next_action"), None) or {}
    a5 = act.get("action") == "A5" and (act.get("form") or "A5") == "A5"
    premise_action = act.get("premise") or None
    questions = [i for i in items or () if i["kind"] == "customer_question"]
    claims = claims_of(result)
    lines_state = ticked(events)
    by_point = {p["id"]: p for p in points}

    # options, proposal, adoption
    intents = {q.get("intent") for q in questions if q.get("intent")}
    evaluated = options.evaluate(data, facts, weak, flagged, marks, intents=intents, area_id=area_id) if data else []
    by_option = {e["id"]: e for e in evaluated}
    proposal = options.proposal(data, facts, evaluated) if data else []
    decided = adoption_of(events)
    adopted, chosen, lapse = None, [], None
    if decided and data:
        picked = decided.get("chosen")
        if picked == PROSPECTS_LOW:
            adopted = {"chosen": PROSPECTS_LOW, "proposal": decided.get("proposal") or [], "by": decided.get("expert"), "at": decided.get("at"), "valid": True}
        else:
            picked = [x for x in picked or () if isinstance(x, str)]
            failing = [x for x in picked if (by_option.get(x) or {}).get("state") != "holds" or (by_option.get(x) or {}).get("held")]
            if failing:
                lapse = f"Empfehlung erneut bestätigen: {(options.option(data, failing[0]) or {}).get('title') or failing[0]} trifft nicht mehr zu"
            elif list(decided.get("proposal") or []) != proposal:
                lapse = "Empfehlung erneut bestätigen: Vorschlag geändert"
            adopted = {"chosen": picked, "proposal": decided.get("proposal") or [], "by": decided.get("expert"), "at": decided.get("at"),
                       "valid": lapse is None, **({"lapse": lapse} if lapse else {})}
            chosen = picked if lapse is None else []
    used = chosen or proposal  # the letter states the adopted options, else the proposed ones
    selectable = [e for e in evaluated if e["state"] == "holds" and not e["held"]]

    # questions, with the account's rows
    out_questions = []
    for q in questions:
        req = request_of(acc, q.get("value"))
        waits = (q.get("waits") or {}).get("question") if q.get("answer_state") == "bedingt" else None
        out_questions.append({"item_id": q["item_id"], "text": q.get("value"), "state": q.get("answer_state"), "reason": q.get("reason"),
                              "row": q.get("row"), "about": q.get("about") or [], "points": q.get("points") or [], "intent": q.get("intent"),
                              "answer": q.get("answer"), "offered": q.get("offered") or [], "evidence": q.get("evidence") or [],
                              "taken": bool(q.get("taken")), "entry": (req or {}).get("entries", [None])[0] if req else None,
                              "request": (req or {}).get("id"), "waits_for": waits, "next": q.get("next"), "ask": q.get("waits")})
    for extra in account_questions(acc, out_questions):
        out_questions.append({"item_id": None, "text": extra["what"], "state": "offen", "reason": "nicht beantwortet", "row": None,
                              "about": [], "points": [], "intent": None, "answer": None, "offered": [], "evidence": _evidence(extra["citations"]),
                              "taken": False, "entry": None, "request": extra["request"], "waits_for": None, "next": None, "ask": None})

    # residual: what the used options need, and what is still owed to us; the claim lines a conditional answer points to
    residual, seen_heads = [], set()
    present_heads = {account._head((i.get("label") or {}).get("de")) for i in items or () if i["kind"] == "document" and i.get("status") == "present"}
    pointed = [((q.get("next") or {}).get("option")) for q in questions if (q.get("next") or {}).get("kind") == "residual"]
    if data and acc is not None:
        candidates = [l for oid in list(dict.fromkeys(used + [p for p in pointed if p])) for l in need_lines(data, oid, claims, items, events)]
        for r in account.open_items(acc, "kunde", account.OWED_TO_US):
            candidates.append({"key": f"residual:request.{r['request']}", "line": f"{r['what']} (erstmals verlangt am {_day(r['first']) or 'ohne Datum'})",
                               "kind": "request", "ref": r["request"], "evidence": []})
        for line in candidates:
            head = account._head(line["line"])
            if line["kind"] != "claim" and (head in seen_heads or head in present_heads):
                continue
            if line["kind"] == "claim" and flagged.wording("claim_line"):
                line = {**line, "line": gap(f"{GAP_WHAT['claim_line']} ({reviews.IN_REVIEW})"), "held": True}
            seen_heads.add(head)
            residual.append({**line, "ticked": lines_state.get(line["key"], True)})
    asks = [{"key": r["key"], "what": r["line"], "kind": r["kind"], "ref": r["ref"]} for r in residual if r["ticked"]]
    for q in questions:
        ask = q.get("waits") or {}
        if q.get("answer_state") == "bedingt" and ask.get("fact") and not any(a["key"] == f"fact:{ask['fact']}" for a in asks):
            asks.append({"key": f"fact:{ask['fact']}", "what": ask.get("question"), "kind": "fact", "ref": ask["fact"]})

    # the premise the letter rests on
    premise_facts = ["deckung", "aussichten"]
    for oid in used:
        premise_facts += _option_facts(data, oid, case_facts)
    for q in questions:
        for pid in q.get("points") or ():
            premise_facts += list((by_point.get(pid) or {}).get("facts") or ())
            for f in (by_point.get(pid) or {}).get("facts") or ():
                premise_facts += options.implied_by(f, case_facts, data)

    # «In Ihrem Fall»
    in_case = []

    def say(key, text, evidence, line_key):
        if flagged.wording(key):
            in_case.append({"key": line_key, "text": gap(f"{GAP_WHAT.get(key, key)} ({reviews.IN_REVIEW})"), "evidence": [], "held": True})
        else:
            in_case.append({"key": line_key, "text": text, "evidence": evidence})
    if data:
        wished = [w for w in data["wishes"] if facts.get(w["fact"]) is True and stated(w["fact"], result, state)]
        if wished:
            say("wish", data["wording"]["wish"].replace("{wuensche}", options.joined([w["text"] for w in wished])),
                [e for w in wished for e in fact_evidence(w["fact"], result, state)][:3], "wish")
        replies = _replies(acc)
        if replies:
            key = "replies_all" if replies["all"] else "replies_some"
            text = data["wording"][key]["one" if len(replies["entries"]) == 1 else "many"].replace("{daten}", options.joined(replies["days"]))
            say(key, text, replies["evidence"], "replies")
        wanted = list(dict.fromkeys(premise_facts))
        for line in data["case_lines"]:
            fact = line["fact"]
            if fact not in wanted or not stated(fact, result, state):
                continue
            cond = {k: line[k] for k in ("fact", "is", "in", "known") if k in line}
            from .workflows import evaluate_condition
            if evaluate_condition(cond, case_facts) is not True:
                continue
            if flagged.case_line(line["id"]):
                in_case.append({"key": f"fall.{line['id']}", "text": gap(f"{question_of(graph, fact)} ({reviews.IN_REVIEW})"), "evidence": [], "held": True})
                continue
            evidence = fact_evidence(fact, result, state)
            text = line["text"].replace("{wert}", options.month_year(case_facts.get(fact)))
            if "{datum}" in text:
                when = _fact_day(fact, result, state, acc)
                if not when:
                    continue  # the day the customer said it is not known: not stated with a date it does not have
                text = text.replace("{datum}", when)
            in_case.append({"key": f"fall.{line['id']}", "text": text, "evidence": evidence, "fact": fact})
        named = [c for c in claims if c.get("checked")]
        if named:
            items_text = [c["what"] + (data["wording"]["claim_amount"].replace("{betrag}", c["amount"]) if c.get("amount") and not flagged.wording("claim_amount") else "")
                          for c in named]
            say("claims", data["wording"]["claims"].replace("{posten}", options.joined(items_text)),
                [e for c in named for e in _evidence(c.get("citations"))][:3], "claims")
        after = act.get("then") or []
        for i in items or ():
            if i["kind"] == "stand" and (i.get("incoming") or {}).get("line"):
                in_case.append({"key": i["item_id"], "text": i["incoming"]["line"], "evidence": i.get("evidence") or []})
        for t in after:
            if t.get("line"):
                in_case.append({"key": f"then:{t.get('fact')}", "text": t["line"], "evidence": []})

    # rules: the conditions of the options of the customer's wishes and of the questions' points, by article
    rules, by_rule = [], {}
    shown_options = [e for e in evaluated if facts.get(e["wish"]) is True and e["state"] != "fails"]

    def rule_for(refs):
        rows = options.rows(refs, data, graph) if data else []
        key = rows[0]["key"] if rows else "ohne"
        if key not in by_rule:
            by_rule[key] = {"id": key, "cite": rows[0]["cite"] if rows else None, "law": rows, "conditions": []}
            rules.append(by_rule[key])
        return by_rule[key]
    for e in shown_options:
        for c, spec in zip(e["conditions"], (options.option(data, e["id"]) or {}).get("conditions") or ()):
            rule = rule_for(spec.get("law"))
            same = next((x for x in rule["conditions"] if x["text"] == c["text"] and x["fact"] == c["fact"]), None)
            if same:
                same["options"].append(e["id"])
                continue
            fact = c["fact"]
            rule["conditions"].append({"text": c["text"], "kind": c["kind"], "fact": fact, "question": question_of(graph, fact) if fact else None,
                                       "value": facts.get(fact) if fact else None, "state": c["state"],
                                       "evidence": fact_evidence(fact, result, state, data) if fact else [],
                                       "read": read_of(_source_fact(fact, case_facts, data), result, state) if fact else None,
                                       "options": [e["id"]]})
    definitions = {f["id"]: f for f in graph.get("facts") or ()}
    whens = {p["id"]: p["when"] for p in graph.get("key_points") or ()}
    for q in questions:  # the conditions of the rule each tagged point states, one per fact it names
        for pid in q.get("points") or ():
            p = by_point.get(pid)
            key = f"punkt:{pid}"
            if not p or key in by_rule:
                continue
            by_rule[key] = {"id": key, "cite": p.get("cite"), "law": p.get("law") or [], "point": pid, "statement": p.get("statement"), "conditions": [
                {"text": reviews.condition_text(leaf, definitions), "kind": "punkt", "fact": leaf["fact"], "question": question_of(graph, leaf["fact"]),
                 "value": facts.get(leaf["fact"]), "state": _leaf_state(leaf, facts, weak), "evidence": fact_evidence(leaf["fact"], result, state, data),
                 "read": read_of(_source_fact(leaf["fact"], case_facts, data), result, state)} for leaf in _leaves(whens.get(pid))]}
            rules.append(by_rule[key])

    # the options as the brief shows them
    shown = []
    for e in evaluated:
        if facts.get(e["wish"]) is not True and e["id"] not in used:
            continue
        spec = options.option(data, e["id"])
        refs = [r for part in spec["advice"] for r in part.get("law") or ()]
        template = all(enclosed(items, events, p["with_template"]) for p in spec["advice"] if p.get("with_template"))
        shown.append({**{k: e[k] for k in ("id", "title", "wish", "state", "weak", "review", "observed", "practice", "propose", "held", "why_not")},
                      "cite": options.cite(refs, data, graph), "law": options.rows(refs, data, graph),
                      "advice": options.advice_text(data, graph, e["id"], template=template, weak=e["weak"]),
                      "needs": [n["document"] for n in spec.get("needs") or ()], "changes_if": spec.get("changes_if") or [],
                      "conditions": e["conditions"], "triggers": e["triggers"], "proposed": e["id"] in proposal, "chosen": e["id"] in chosen})

    # what would change it
    changes, seen = [], set()
    holding_wishes = {e["wish"] for e in selectable}
    sources = [e for e in evaluated if e["id"] in used] + [e for e in evaluated if facts.get(e["wish"]) is True and e["wish"] not in holding_wishes
                                                            and e["state"] == "open"]
    for e in sources:
        spec = options.option(data, e["id"])
        for entry in spec.get("changes_if") or ():
            kind, _, name = str(entry).partition(":")
            if not name and entry not in seen:
                seen.add(entry)
                changes.append({"fact": entry, "question": question_of(graph, entry), "value": case_facts.get(entry), "option": e["id"]})
            elif kind == "need" and entry not in seen:
                seen.add(entry)
                doc = _document(items, name)
                changes.append({"need": name, "title": ((doc or {}).get("label") or {}).get("de") or name, "option": e["id"]})
            elif kind == "condition":
                text = spec["conditions"][int(name)]["text"]
                if text not in seen:
                    seen.add(text)
                    changes.append({"condition": text, "option": e["id"]})

    # the letter's parts: only an assessment of an area with an options file
    letter = None
    if data and a5:
        im_fall = "\n".join(l["text"] for l in in_case) if in_case else None
        zu_fragen = _zu_fragen(out_questions)
        empfehlung = _recommendation(data, graph, used, by_option, items, events, flagged)
        if acc is not None:
            ticked_lines = [r["line"] for r in residual if r["ticked"]]
            nachzureichen = "\n".join(["Bitte reichen Sie uns noch nach:"] + [f"– {l}" for l in ticked_lines]) if ticked_lines else ""
        else:
            nachzureichen = None  # a run without the account: the documents still asked, as before
        letter = {"im_fall": im_fall, "zu_fragen": zu_fragen, "empfehlung": empfehlung, "nachzureichen": nachzureichen}

    # decisions that block the approval
    blocking = []
    if a5 and premise_action and case_facts.get("deckung") in (None, "offen"):
        blocking.append({"kind": "decision", "key": "deckung", "text": "Deckung"})
    if a5 and data and selectable and not chosen and not (adopted and adopted.get("chosen") == PROSPECTS_LOW):
        blocking.append({"kind": "decision", "key": "empfehlung", "text": lapse or "Empfehlung übernehmen"})

    premise = {f: facts.get(f) if f not in ("deckung", "aussichten") else case_facts.get(f) for f in dict.fromkeys(premise_facts)}
    for line in in_case:
        if line.get("fact"):
            premise.setdefault(line["fact"], case_facts.get(line["fact"]))
    if not a5:
        premise = {}

    # candidates of an area without options: the points that apply and have advice, never filled in by themselves
    candidates = [] if data else [{"id": p["id"], "text": keypoints.advice_line(p), "cite": p.get("cite"), "law": p.get("law")}
                                   for p in points if p["state"] == "applies" and p.get("advice")]
    titles = [(options.option(data, x) or {}).get("title") for x in used] if data else []
    states = [q["state"] for q in out_questions]
    review_states = [by_option[x]["review"] for x in used if x in by_option]
    return {"area": area_id, "has_options": bool(data), "assessment": a5, "under_premise": bool(a5 and premise_action),
            "premise_action": premise_action,
            "wishes": [{"fact": w["fact"], "text": w["text"], "evidence": fact_evidence(w["fact"], result, state)}
                       for w in (data or {}).get("wishes") or () if facts.get(w["fact"]) is True],
            "questions": out_questions, "rules": [r for r in rules if r["conditions"]], "options": shown,
            "proposal": proposal, "adopted": adopted, "chosen": chosen, "options_sha256": options.sha256(area_id) if data else None,
            "options_version": (data or {}).get("version"), "review": options.weakest(review_states) if review_states else None,
            "changes_if": changes, "residual": residual, "asks": asks, "in_case": in_case, "letter": letter, "blocking": blocking,
            "premise": premise, "candidates": candidates, "label": (data or {}).get("label"),
            "summary": {"answered": states.count("beantwortet"), "conditional": states.count("bedingt"), "open": states.count("offen"),
                        "check": states.count("pruefen"), "proposal": titles, "residual": sum(1 for r in residual if r["ticked"])}}


def _source_fact(fact, facts, data):
    """The fact a condition's value was read from: an implied fact's source, else the fact itself."""
    sources = options.implied_by(fact, facts, data) if data else []
    return sources[0] if sources else fact


def _leaves(condition):
    """The single-fact conditions of a key point's condition, in order (its «all» and «any» parts alike)."""
    if not isinstance(condition, dict):
        return []
    if "all" in condition or "any" in condition:
        return [leaf for c in condition.get("all") or condition.get("any") for leaf in _leaves(c)]
    if "not" in condition:
        return _leaves(condition["not"])
    return [condition] if condition.get("fact") else []


def _leaf_state(leaf, facts, weak):
    from .workflows import evaluate_condition
    if facts.get(leaf["fact"]) is None and "known" not in leaf:
        return "widersprüchlich" if weak.get(leaf["fact"]) == "conflicting" else "offen"
    holds = evaluate_condition(leaf, facts)
    return "nicht erfüllt" if holds is False else "vermutet" if weak.get(leaf["fact"]) else "erfüllt"


def _fact_day(fact, result, state, acc):
    """The day the customer said what a fact holds: the date of the document its quote comes from; the day the handler
    set it for a fact the handler set."""
    edit = ((state or {}).get("overrides") or {}).get(fact)
    if edit:
        return _day(str(edit.get("at") or "")[:10])
    for cite in (fact_rows(result).get(fact) or {}).get("citations") or ():
        day = quoted_day(cite, acc)
        if day:
            return _day(day)
    return None


def _replies(acc):
    """The customer's messages after our last action that answered what we asked: {entries, days, all, evidence}, or None."""
    if not acc:
        return None
    actions = [a for a in acc.get("actions") or () if a.get("date")]
    if not actions:
        return None
    last = max(actions, key=lambda a: (a["date"], a["n"]))
    ours = [r for r in acc["requests"] if r["by"] == account.INSURER and r["of"] == "kunde"]
    answered = {r["answered"]["n"] for r in ours if r["answered"]}
    entries = [e for e in acc["entries"] if e["from"] == "kunde" and e["n"] in answered and e.get("date")
               and (e["date"], e["n"]) > (last["date"], last["n"])]
    if not entries:
        return None
    days = list(dict.fromkeys(_day(e["date"]) for e in sorted(entries, key=lambda e: (e["date"], e["n"]))))
    return {"entries": [e["n"] for e in entries], "days": days, "all": all(r["answered"] for r in ours),
            "evidence": [c for e in entries for c in _evidence(e.get("citations"))][:2]}


def _zu_fragen(questions):
    """«Zu Ihren Fragen:» with one line per answer; questions answered alike share it («– «Q1» und «Q2»: …»); a question
    the file does not answer yet keeps its gap until the handler takes or writes an answer."""
    lines, groups = [], {}
    for q in questions:
        if q["item_id"] is None:
            continue  # a question of the account the reader did not list: shown in the brief, not in the letter
        if q["state"] in ("beantwortet", "bedingt") and q.get("answer"):
            key = (tuple(q["points"]), q["intent"], q["answer"])
            if key in groups:
                groups[key]["texts"].append(q["text"])
                continue
            groups[key] = {"texts": [q["text"]], "answer": q["answer"]}
            lines.append(groups[key])
        else:
            lines.append({"texts": [q["text"]], "answer": gap(ANSWER + (f" ({reviews.IN_REVIEW})" if q.get("reason") == "Antwort in Prüfung" else ""))})
    if not lines:
        return ""
    return "\n".join(["Zu Ihren Fragen:"] + [f"– {options.joined([f'«{t}»' for t in row['texts']])}: {row['answer']}" for row in lines])


def _recommendation(data, graph, used, by_option, items, events, flagged):
    """The recommendation as it follows «Wir empfehlen Ihnen, »: the first option's advice, then «Zudem empfehlen wir
    Ihnen, » and the next, ending with a full stop; the gap when there is none."""
    if not used:
        return gap(RECOMMENDATION)
    texts = []
    for oid in used:
        spec = options.option(data, oid)
        template = all(enclosed(items, events, p["with_template"]) for p in spec["advice"] if p.get("with_template"))
        texts.append(options.advice_text(data, graph, oid, template=template, weak=(by_option.get(oid) or {}).get("weak") or ()))
    out = texts[0]
    for text in texts[1:]:
        join = gap(f"{GAP_WHAT['join']} ({reviews.IN_REVIEW})") + " " if flagged.wording("join") else data["wording"]["join"]
        out = f"{_sentence(out)} {join}{text}"
    return _sentence(out)

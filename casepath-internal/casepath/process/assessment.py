"""The decision brief of the legal assessment (A5) and the parts of its letter, from what the case establishes.

The handler opens a reply and finds the assessment prepared: what the customer wants and asks, the rule each question asks
about with its conditions and how the case meets them, the ways to proceed with a recommendation and its alternative to
adopt or correct, what would change it, and a residual request for only what is still missing, each line naming the
judgment it would settle. Code decides; the reader only tags the questions (``about``) and reads the claims and what their
receipts document; nothing here calls a model.

- Each customer question is evaluated by the key point its tags name and the intent its words ask (keypoints.status, the
  guard table): «beantwortet» or «bedingt» (with its smallest next step) from the area's answers (options.py), «prüfen»
  with a drafted answer the handler takes with one click, or «offen». A question the handler answered so stays answered.
  A question whose answer waits for the receipts of a claimed cost is «beantwortet» once a receipt documents it.
- The options of the area hold on established, accepted facts only. A wish the customer's own words contradict, a value
  read two ways or a question that negates what an option is triggered by never carries a proposal; a presumed value
  carries it only «unter Vorbehalt», the condition named. One holding, proposable option per wish is proposed, with the
  alternative beside it; the handler's adoption («übernehmen») holds while its options hold and the proposal is the one
  adopted. The prospects of success (Art. 169 AVO) are the handler's separate decision.
- What the file leaves open is asked precisely: the customer's question for the missing fact with what its answer
  decides («davon hängt ab, ob wir Ihnen empfehlen, …»); every residual line and ask names what it blocks (``blocks``:
  the question, the option, the condition). When a later arrival settles it, the brief shows it under ``resolved``.
- «In Ihrem Fall» states the wish, the replies, the facts the recommendation rests on (each with its source and date) and
  the costs claimed; «Bitte reichen Sie uns noch nach» asks for the receipts of a claimed cost and what is still owed.
- Areas without an options file get the brief and the questions' evaluation; no recommendation is filled.

``build`` returns the brief; ``evaluate_questions`` gives the item list its customer questions (items.py). Model-free.
"""
import re

from . import account, customer_letters, keypoints, options, review as reviews
from .clock import parse_date

TAKEN = "beantwortet (Fallbearbeitung)"
DOCUMENTED = "Belege liegen vor"
GAP_WHAT = {"wish": "was Sie möchten", "replies_all": "Ihre Antworten auf unsere Fragen", "replies_some": "Ihre Antworten auf unsere Fragen",
            "claims": "die geltend gemachten Kosten", "claim_amount": "der genannte Betrag", "claim_line": "Belege zu den geltend gemachten Kosten",
            "join": "die weitere Empfehlung", "conditional": "was noch fehlt", "discuss": "das weitere Vorgehen",
            "changes": "worauf die Empfehlung beruht", "open_wish": "die Frage, von der die Empfehlung abhängt",
            "open_only": "die Frage, von der die Empfehlung abhängt"}
ANSWER = "Antwort auf diese Frage"
RECOMMENDATION = "die Empfehlung an die Kundschaft"
EMPFEHLUNG = "point:empfehlung"
UNJUDGED = (None, "", "offen", "noch nicht beurteilt")  # the prospects not judged yet
PROSPECTS = "Erfolgsaussichten"


def gap(what):
    from .letters import gap as letter_gap
    return letter_gap(what)


def _evidence(citations):
    """The quotes a line rests on, each where it stands (file, page and its place on the page, for the source to open
    at the passage)."""
    return [{k: c.get(k) for k in ("file", "page", "start", "end", "quote")} for c in citations or () if c]


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


def stated(fact, result, state, contra=None):
    """Whether «In Ihrem Fall» may state a fact: the handler set it, or the run established it with a quote the source
    checker accepted and the customer's own words do not contradict it. A presumed or contradictory value never."""
    if fact in ((state or {}).get("overrides") or {}):
        return True
    if fact in (contra or {}):
        return False
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


def values_of(graph, fact):
    """The values a fact can take, as the handler sets it: an enum's values, else yes and no for a yes/no fact."""
    row = next((f for f in (graph or {}).get("facts") or () if f["id"] == fact), {})
    if row.get("values"):
        return [v for v in row["values"] if v != "offen"]
    return [True, False] if row.get("type") == "boolean" else []


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


def contradictions(data, facts, result, state):
    """The wishes the customer's own words contradict (options.contradicted): {fact: the words}. Their own quotes and the
    customer's questions are read against them; a wish the handler set is the handler's and never contradicted."""
    if not data:
        return {}
    wishes = {w["fact"] for w in data.get("wishes") or ()}
    quotes = {f["fact"]: [c.get("quote") for c in f.get("citations") or () if c.get("quote")]
              for f in (result or {}).get("facts") or () if f.get("fact") in wishes}
    texts = [q.get("question") for q in ((result or {}).get("brief") or {}).get("questions") or () if q.get("question")]
    own = set((state or {}).get("overrides") or {})
    return {f: t for f, t in options.contradicted(data, facts, quotes, texts).items() if f not in own}


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

def documented_by(claim, files, entries, why=None):
    """The receipt that documents a claim, decided by one rule: Slice C's ``account.documented`` (C10c: a receipt record of
    an entry in the case's files agrees with the claim in what it is for, who issued it, whom it bills, the period, the
    number and the role of its amount; a shared word or amount is a candidate, never proof), where the account has it.
    Until that rule is merged, the same comparison over the entries' located receipt records stands in
    (options.agreement). {file, how, n, basis} or None; ``why`` collects each candidate set aside ({file, n, expense, why})."""
    check = getattr(account, "documented", None)
    if check is not None:
        return check(claim, files, entries, why=why)
    ids = {f["id"] for f in files or ()}
    for e in entries or ():
        rec = e.get("receipt") if isinstance(e.get("receipt"), dict) else None
        if not rec or (ids and e.get("file") not in ids):
            continue
        agree = options.agreement(claim, rec)
        if agree["documented"]:
            return {"file": e.get("file"), "how": "receipt", "n": e.get("n"), "basis": {"expense": rec.get("expense"), "amount": rec.get("amount"),
                                                                                        "role": rec.get("role"), "period": rec.get("period")}}
        if why is not None and (agree["amount"] or agree["expense"]):  # it shares the amount or the kind: a candidate, set aside
            why.append({"file": e.get("file"), "n": e.get("n"), "expense": rec.get("expense"), "why": [f"weicht ab: {options.disagreement(agree)}"]})
    return None


def receipt_evidence(hit, entries):
    """Where the receipt that documents a claim stands: its record's words (its amount), else its entry's quote."""
    entry = next((e for e in entries or () if hit and e.get("n") == hit.get("n") and e.get("file") == hit.get("file")), None) or {}
    return _evidence(((entry.get("receipt") or {}).get("citations") or entry.get("citations") or [])[:1]) or (
        [{"file": hit.get("file")}] if hit and hit.get("file") else [])


def claims_of(result, files=None, acc=None):
    """The costs the customer asks to have compensated, as the reading located them, each with whether a receipt in the
    case's files documents it (documented_by: one rule): [{i, what, amount, checked, documented, held, set_aside, receipt,
    citations, …}] in the brief's order (``i`` its place there). ``receipt``: where the documenting receipt stands."""
    entries = (acc or {}).get("entries") or (((result or {}).get("record") or {}).get("entries") or [])
    claims = []
    for i, c in enumerate(((result or {}).get("brief") or {}).get("claims") or ()):
        row = {**c, "i": i, "documented": False, "held": None, "set_aside": [], "receipt": []}
        if c.get("checked") and files is not None:
            why = []
            hit = documented_by(c, files, entries, why)
            row.update(documented=bool(hit), held=hit, set_aside=why, receipt=receipt_evidence(hit, entries) if hit else [])
        claims.append(row)
    return claims


def _document(items, need):
    return next((i for i in items or () if i["kind"] == "document" and i["key"] == need), None)


def evidence_condition(data, option_id):
    """The text of an option's condition the receipts of the claimed costs settle, or None."""
    o = options.option(data, option_id) or {}
    return next((c["text"] for c in o.get("conditions") or () if c.get("evidence") == "claims"), None)


def need_lines(data, option_id, claims, items, events=None):
    """What an option's needs still ask for: one «Belege zu: …» per claimed cost (named, its words in its quote) that no
    receipt documents, even when the need reads present; without a claim, the need's title while it is not present. Each
    line names what it blocks: the option and, for a claim, the condition the receipts settle."""
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
                                      "kind": "claim", "ref": c["i"], "evidence": _evidence(c.get("citations")), "wording": "claim_line",
                                      "blocks": {"question": None, "option": option_id, "condition": evidence_condition(data, option_id)},
                                      **({"set_aside": [_set_aside(x, items) for x in c["set_aside"]]} if c.get("set_aside") else {})})
                continue
        if not present and doc is not None:
            lines.append({"key": f"residual:document.{need['document']}", "line": (doc.get("label") or {}).get("de") or need["document"],
                          "kind": "document", "ref": need["document"], "evidence": [],
                          "blocks": {"question": None, "option": option_id, "condition": None}})
    return lines


def _set_aside(row, items):
    """A receipt the rule set aside for a claim, as the brief shows it beside the claim's line: its words, why it is not
    that cost's receipt, and its document («Quittung … · andere Ausgabe: …»)."""
    return {"file": row.get("file"), "n": row.get("n"), "expense": row.get("expense"), "why": list(row.get("why") or ())}


def documented_all(data, option_id, claims):
    """Whether the receipts are in for an option whose needs name the claimed costs: every named claim documented."""
    o = options.option(data, option_id) or {}
    if not any(n.get("names_claim") for n in o.get("needs") or ()):
        return False
    named = [c for c in claims if c.get("checked")]
    return bool(named) and all(c.get("documented") for c in named)


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
    contra = contradictions(data, facts, result, state)
    weak.update({f: "conflicting" for f in contra})  # read against the customer's own words: never relied on
    flagged = reviews.flags(graph, marks)
    points = [p for p in keypoints.evaluate(graph, facts, failing=True, weak=set(weak)) if not flagged.key_point(p["id"])]
    return graph, data, facts, weak, flagged, points, contra


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


def customer_ask(data, flagged, fact, fallback):
    """The question to the customer for an open fact: the options file's wording (direct, and indirect «ob …»), unless a
    jurist holds it; else the module's question for it."""
    ask = ((data or {}).get("asks") or {}).get(fact)
    if ask and not flagged.ask(fact):
        return ask["frage"], ask["ob"]
    return fallback, None


def wants_intent(text, intent_row):
    """Whether a question asks for what its intent names, rather than rejecting it: no negation stands before one of the
    intent's stems (a stem that carries its own negation, «nicht zahl», asks for it)."""
    if not intent_row:
        return False
    stems = list(intent_row.get("stems") or ())
    carrying = [w for w in stems if keypoints.NEGATIONS & set(keypoints.WORDS.findall(w))]
    return not keypoints.negated(text, stems, carrying)


def evaluate_questions(state, result, items, events, marks=None, files=None):
    """Each of the brief's customer questions, evaluated: [{i, item_id, text, about, row, state, reason, points, intent,
    answer, answered_by, offered [{point, intent, text}], ask, next, taken, held, wants}] in the brief's order. ``items``:
    the item list built so far (the templates that go out with the assessment, the documents present)."""
    graph, data, facts, weak, flagged, points, contra = _context(state, result, items, events, marks)
    brief = (result or {}).get("brief") or {}
    if not graph:
        return []
    by_id = {p["id"]: p for p in points}
    wishes = {w["fact"]: w["text"] for w in (data or {}).get("wishes") or ()}
    claims = claims_of(result, files, (state or {}).get("account"))
    taken = taken_answers(events)

    def held(row):
        return bool(row) and flagged.answer(row["points"][0], row["intent"])

    def parts(intent_row):
        nxt = intent_row.get("next") or {}
        residual = nxt.get("kind") != "residual" or _residual_named(data, nxt["option"], claims, items, events)
        documented = nxt.get("kind") == "residual" and documented_all(data, nxt["option"], claims)
        template = all(enclosed(items, events, p["with_template"]) for p in intent_row["parts"] if p.get("with_template"))
        return residual, documented, template

    def render(point_id, intent_row):
        """The answer of a point for one intent, as the letter would say it; the point's own sentence without an intent."""
        if intent_row is not None and data:
            residual, documented, template = parts(intent_row)
            return options.answer_text(data, graph, intent_row, template=template, residual=residual, documented=documented)
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
        ask = st["ask"]
        if ask and ask.get("fact"):  # the open fact asked in the customer's words where the area words it
            direct, indirect = customer_ask(data, flagged, ask["fact"], ask["question"])
            ask = {**ask, "question": direct, "ob": indirect}
        row = {"i": i, "item_id": item_id, "text": text, "about": list(q.get("about") or ()), "row": st["row"], "state": st["state"],
               "reason": ask["question"] if ask and st["row"] == 8 else st["reason"], "points": st["points"], "intent": st["intent"],
               "answer": None, "answered_by": None, "offered": [], "ask": ask, "next": st["next"], "taken": False, "held": False,
               "evidence": _evidence(q.get("citations")),
               # the question asks for what its intent names (not a negation of it, not a wish the customer rejected)
               "wants": bool(intent_row) and st["row"] != 4 and wants_intent(text, intent_row)}
        took = taken.get(item_id)
        if took and (by_id.get(took["point"]) or {}).get("state") == "applies":  # the handler took an answer: it stays while its point applies
            chosen = _answer_row(data, took.get("intent")) if took.get("intent") else None
            row.update(state="beantwortet", reason=TAKEN, row=None, taken=True, answered_by=took["point"], ask=None, next=None,
                       answer=render(took["point"], chosen), points=list(dict.fromkeys([took["point"]] + st["points"])),
                       intent=(chosen or {}).get("intent") or st["intent"], by=took.get("expert"), at=took.get("at"),
                       wants=bool(chosen) and wants_intent(text, chosen))
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
                residual, documented, template = parts(intent_row) if intent_row else (True, False, False)
                wording_held = bool(ask) and flagged.wording("conditional")
                answer = options.answer_text(data, graph, intent_row, template=template, residual=residual, documented=documented,
                                             ask=None if wording_held else (ask or {}).get("question")) if (intent_row or ask) else None
                if wording_held:
                    answer = " ".join(x for x in (answer, gap(f"{GAP_WHAT['conditional']} ({reviews.IN_REVIEW})")) if x)
                if nxt.get("kind") == "residual":  # the answer points to the receipts asked below: they are asked below
                    row["next"] = nxt if residual else None
                    lines = [l for l in need_lines(data, nxt["option"], claims, items, events) if ticked(events).get(l["key"], True)]
                    if residual and lines and st["row"] == 9:
                        row["reason"] = lines[0]["line"]  # what it waits for: the first line of the residual it points to
                    if documented and not residual and st["row"] == 9:
                        # the receipts the answer waited for are in: the question is answered, the evidence beside it
                        row.update(state="beantwortet", row=10, reason=DOCUMENTED, next=None,
                                   evidence_in=[e for c in claims if c.get("checked") for e in (c.get("receipt") or [])[:1]])
                state_now = row["state"]
                row.update(answer=answer, answered_by=st["points"][0] if state_now == "beantwortet" else None)
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


def _missing(evaluated_option):
    """The open fact that keeps an option from holding, and the condition it settles: (fact, condition text) or None. A
    trigger first (its fact), then a «vorher» condition with a fact."""
    for t in evaluated_option["triggers"]:
        if t["state"] == "offen":
            return t["fact"], None
    for c in evaluated_option["conditions"]:
        if c["fact"] and c["state"] == "offen" and not c.get("settled_by"):
            return c["fact"], c["text"]
    return None


def _branches(data, facts, weak, flagged, marks, intents, claims, area_id, fact, values):
    """What the answer for an open fact decides: for each value it may take, the ways proposed then (titles)."""
    out = []
    for value in values:
        trial = {**facts, fact: value}
        evaluated = options.evaluate(data, trial, weak, flagged, marks, intents=intents, area_id=area_id, claims=claims)
        out.append({"value": value, "proposal": [(options.option(data, x) or {}).get("title") for x in options.proposal(data, trial, evaluated)]})
    return out


def build(state, result, items, files, events, marks):
    """The decision brief of the prepared action: wishes, questions, rules with their conditions, the options with the
    proposal, its alternative and the adoption, what would change it, the residual and the asks (each with what it blocks
    and, for a fact, what its answer decides), what the latest arrival settled, the facts the letter rests on, the letter's
    parts (an assessment of an area with an options file only), what blocks the approval, the premise and a summary. None
    for a case without a process."""
    graph, data, facts, weak, flagged, points, contra = _context(state, result, items, events, marks)
    if not graph:
        return None
    case_facts = (state or {}).get("facts") or {}
    acc = (state or {}).get("account")
    area_id = graph.get("id")
    act = next((i for i in items or () if i["kind"] == "next_action"), None) or {}
    a5 = act.get("action") == "A5" and (act.get("form") or "A5") == "A5"
    premise_action = act.get("premise") or None
    questions = [i for i in items or () if i["kind"] == "customer_question"]
    claims = claims_of(result, files, acc)
    lines_state = ticked(events)
    by_point = {p["id"]: p for p in points}

    # options, proposal, adoption; an option a question triggers only when the question asks for it (not «keine Hinterlegung»)
    intents = {q.get("intent") for q in questions if q.get("intent") and q.get("wants", True)}
    evaluated = options.evaluate(data, facts, weak, flagged, marks, intents=intents, area_id=area_id, claims=claims) if data else []
    by_option = {e["id"]: e for e in evaluated}
    proposal = options.proposal(data, facts, evaluated) if data else []
    decided = adoption_of(events)
    adopted, chosen, lapse = None, [], None
    if decided and data and isinstance(decided.get("chosen"), list):
        picked = [x for x in decided.get("chosen") or () if isinstance(x, str)]
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
                              "request": (req or {}).get("id"), "waits_for": waits, "next": q.get("next"), "ask": q.get("waits"),
                              "evidence_in": q.get("evidence_in") or []})
    for extra in account_questions(acc, out_questions):
        out_questions.append({"item_id": None, "text": extra["what"], "state": "offen", "reason": "nicht beantwortet", "row": None,
                              "about": [], "points": [], "intent": None, "answer": None, "offered": [], "evidence": _evidence(extra["citations"]),
                              "taken": False, "entry": None, "request": extra["request"], "waits_for": None, "next": None, "ask": None,
                              "evidence_in": []})
    pointing = {}  # option id → the question whose answer points to its residual (the judgment the receipts settle)
    for q in out_questions:
        nxt = q.get("next") or {}
        option_id = nxt.get("option") or ((_answer_row(data, q["intent"]) or {}).get("next") or {}).get("option") if q.get("intent") else None
        if option_id and q["item_id"]:
            pointing.setdefault(option_id, q["item_id"])

    # residual: what the used options need, and what is still owed to us; the claim lines a conditional answer points to
    residual, seen_heads = [], set()
    present_heads = {account._head((i.get("label") or {}).get("de")) for i in items or () if i["kind"] == "document" and i.get("status") == "present"}
    pointed = [((q.get("next") or {}).get("option")) for q in questions if (q.get("next") or {}).get("kind") == "residual"]
    if data and acc is not None:
        candidates = [l for oid in list(dict.fromkeys(used + [p for p in pointed if p])) for l in need_lines(data, oid, claims, items, events)]
        for r in account.open_items(acc, "kunde", account.OWED_TO_US):
            candidates.append({"key": f"residual:request.{r['request']}", "line": f"{r['what']} (erstmals verlangt am {_day(r['first']) or 'ohne Datum'})",
                               "kind": "request", "ref": r["request"], "evidence": [],
                               "blocks": {"question": None, "option": None, "condition": None}})
        for line in candidates:
            head = account._head(line["line"])
            if line["kind"] != "claim" and (head in seen_heads or head in present_heads):
                continue
            if line["kind"] == "claim" and flagged.wording("claim_line"):
                line = {**line, "line": gap(f"{GAP_WHAT['claim_line']} ({reviews.IN_REVIEW})"), "held": True}
            seen_heads.add(head)
            blocks = dict(line.get("blocks") or {"question": None, "option": None, "condition": None})
            if blocks.get("option") and not blocks.get("question"):
                blocks["question"] = pointing.get(blocks["option"])
            residual.append({**line, "blocks": blocks, "ticked": lines_state.get(line["key"], True)})
    asks = [{"key": r["key"], "what": r["line"], "kind": r["kind"], "ref": r["ref"], "blocks": r["blocks"]} for r in residual if r["ticked"]]

    def option_of(fact):
        """An option open on this fact (of a wish the customer has, or of the wish the fact is), with the condition it
        settles: (id, text)."""
        for e in evaluated:
            if (facts.get(e["wish"]) is True or e["wish"] == fact) and e["state"] == "open":
                missing = _missing(e)
                if missing and missing[0] == fact:
                    return e["id"], missing[1] or question_of(graph, fact)
        return None, None
    for q in questions:  # a conditional answer waits for a fact: asked once, in the customer's words, with what it decides
        ask = q.get("waits") or {}
        if q.get("answer_state") == "bedingt" and ask.get("fact") and not any(a["key"] == f"fact:{ask['fact']}" for a in asks):
            option_id, condition = option_of(ask["fact"])
            asks.append({"key": f"fact:{ask['fact']}", "what": ask.get("question"), "kind": "fact", "ref": ask["fact"],
                         "decides": f"die Antwort auf die Frage «{q.get('value')}»",
                         "blocks": {"question": q["item_id"], "option": option_id, "condition": condition or question_of(graph, ask["fact"])}})

    # a wish the customer has with no way that holds, open on a fact the file leaves open: asked with what it decides
    open_wishes = []
    holding_wishes = {e["wish"] for e in selectable}
    if data and a5:
        for w in data["wishes"]:
            if facts.get(w["fact"]) is not True or w["fact"] in holding_wishes or w["fact"] in contra:
                continue
            ways = sorted([e for e in evaluated if e["wish"] == w["fact"] and e["state"] == "open" and e["propose"] and not e["held"]],
                          key=lambda e: (-(options._count(options.option(data, e["id"]).get("observed")) or (0, 0))[0],
                                         [o["id"] for o in data["options"]].index(e["id"])))
            for e in ways:
                missing = _missing(e)
                if not missing:
                    continue
                fact, condition = missing
                direct, indirect = customer_ask(data, flagged, fact, question_of(graph, fact))  # without the area's wording (held
                aim = options.aim(data, e["id"])  # by a jurist) the letter keeps a gap for it: no question is invented
                open_wishes.append({"wish": w["fact"], "option": e["id"], "fact": fact, "frage": direct, "ob": indirect, "folge": aim})
                key = f"fact:{fact}"
                blocks = {"question": next((q["item_id"] for q in questions if fact in ((by_point.get((q.get("points") or [None])[0]) or {}).get("facts") or ())), None),
                          "option": e["id"], "condition": condition or question_of(graph, fact)}
                existing = next((a for a in asks if a["key"] == key), None)
                if existing:
                    existing.setdefault("decides", f"ob wir Ihnen empfehlen, {aim}")
                    existing["blocks"] = {**blocks, **{k: v for k, v in existing["blocks"].items() if v}}
                else:
                    asks.append({"key": key, "what": direct, "kind": "fact", "ref": fact, "decides": f"ob wir Ihnen empfehlen, {aim}",
                                 "blocks": blocks})
                break
    for a in asks:
        if a["kind"] == "fact":
            a["branches"] = _branches(data, facts, weak, flagged, marks, intents, claims, area_id, a["ref"], values_of(graph, a["ref"])) if data else []

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
        wished = [w for w in data["wishes"] if facts.get(w["fact"]) is True and stated(w["fact"], result, state, contra)]
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
            if fact not in wanted or not stated(fact, result, state, contra):
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
        # the costs claimed, while the customer still wants them compensated (a withdrawn claim is not stated)
        live = any(facts.get(o["wish"]) is True and o["wish"] not in contra for o in data["options"]
                   if any(n.get("names_claim") for n in o.get("needs") or ()))
        named = [c for c in claims if c.get("checked")] if live else []
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
            if c.get("settled_by") == "claims":  # the receipts of the claimed costs: their quotes, the receipt's once it documents them
                evidence = [x for k in claims if k.get("checked") for x in ((k.get("receipt") or [])[:1] if k.get("documented") else _evidence(k.get("citations")))][:3]
            else:
                evidence = fact_evidence(fact, result, state, data) if fact else []
            rule["conditions"].append({"text": c["text"], "kind": c["kind"], "fact": fact, "question": question_of(graph, fact) if fact else None,
                                       "value": facts.get(fact) if fact else None, "state": c["state"], "evidence": evidence,
                                       "read": read_of(_source_fact(fact, case_facts, data), result, state) if fact else None,
                                       "settled_by": c.get("settled_by"), "options": [e["id"]],
                                       **({"contradicted": contra[fact]} if fact in contra else {})})
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

    # the options as the brief shows them, each wish's proposal with what it rests on «unter Vorbehalt», and its alternative
    shown = []
    for e in evaluated:
        if facts.get(e["wish"]) is not True and e["id"] not in used:
            continue
        spec = options.option(data, e["id"])
        refs = [r for part in spec["advice"] for r in part.get("law") or ()]
        template = all(enclosed(items, events, p["with_template"]) for p in spec["advice"] if p.get("with_template"))
        reserve = [{"fact": x["fact"], "question": question_of(graph, x["fact"]), "condition": x.get("text") or question_of(graph, x["fact"]),
                    "state": x["state"]} for x in e["triggers"] + e["conditions"] if x["state"] == "vermutet" and x["fact"]]
        shown.append({**{k: e[k] for k in ("id", "title", "wish", "state", "weak", "review", "observed", "practice", "propose", "held", "why_not")},
                      "cite": options.cite(refs, data, graph), "law": options.rows(refs, data, graph),
                      "advice": options.advice_text(data, graph, e["id"], template=template, weak=e["weak"]),
                      "needs": [n["document"] for n in spec.get("needs") or ()], "changes_if": spec.get("changes_if") or [],
                      "conditions": e["conditions"], "triggers": e["triggers"], "proposed": e["id"] in proposal, "chosen": e["id"] in chosen,
                      "reserve": reserve, "missing": (lambda m: {"fact": m[0], "condition": m[1] or question_of(graph, m[0])} if m else None)(_missing(e))
                      if e["state"] == "open" else None})
    alternatives = []
    for oid in used:
        first = by_option.get(oid)
        if not first:
            continue
        for e in evaluated:
            if e["wish"] != first["wish"] or e["id"] in used or e["state"] == "fails":
                continue
            why = (e.get("why_not") if e["state"] == "holds" and not e["propose"] else
                   f"in Prüfung ({e['review']})" if e["held"] else
                   f"offen: {(_missing(e) or (None, None))[1] or next((c['text'] for c in e['conditions'] if c['state'] == 'nicht geprüft' and c['kind'] == 'vorher'), '')}")
            alternatives.append({"to": oid, "id": e["id"], "title": e["title"], "state": e["state"], "selectable": e["state"] == "holds" and not e["held"],
                                 "why": why, "practice": e["practice"], "review": e["review"]})

    # what would change it
    changes, seen = [], set()
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

    # the facts that decide the prepared answers and the recommendation, each with its source and how it came: the few the
    # handler checks instead of the whole file (new from the latest arrival, set by the handler, or read once)
    newly = set(((result or {}).get("update") or {}).get("facts") or ())
    deciding, shown_facts = [], set()
    for fact in dict.fromkeys(f for f in premise_facts if f not in ("deckung", "aussichten") and a5):
        source = _source_fact(fact, case_facts, data)
        if source in shown_facts or (facts.get(fact) is None and fact not in weak):
            continue
        shown_facts.add(source)
        state_now = ("widersprüchlich" if weak.get(source) == "conflicting" else "vermutet" if weak.get(source) else "erfüllt")
        deciding.append({"fact": source, "question": question_of(graph, source), "value": facts.get(source), "state": state_now,
                         "read": read_of(source, result, state), "evidence": fact_evidence(source, result, state, data)[:1],
                         "changed": "korrigiert" if source in ((state or {}).get("overrides") or {}) else "neu" if source in newly else None,
                         "values": values_of(graph, source), **({"contradicted": contra[source]} if source in contra else {})})

    # what the latest arrival settled: a receipt that documents a claimed cost, a fact the residual or an answer waited for
    resolved = []
    if data:
        for c in claims:
            if not (c.get("checked") and c.get("documented")):
                continue
            option_id = next((o["id"] for o in data["options"] if any(n.get("names_claim") for n in o.get("needs") or ())), None)
            now = {"option": (by_option.get(option_id) or {}).get("state"), "condition": "erfüllt",
                   "question": next((q["state"] for q in out_questions if q["item_id"] == pointing.get(option_id)), None)}
            resolved.append({"key": f"residual:claim.{c['i']}", "line": data["wording"]["claim_line"].replace("{posten}", c["what"]),
                             "by": list((c.get("receipt") or [])[:1]),
                             "blocks": {"question": pointing.get(option_id), "option": option_id, "condition": evidence_condition(data, option_id)},
                             "now": now})
        for d in deciding:
            if d["changed"] != "neu":
                continue
            related = {d["fact"], *options.implies(d["fact"], data)}  # the fact and what the file settles by it
            question = next((q for q in out_questions if q["item_id"]
                             and related & {f for pid in q["points"] for f in (by_point.get(pid) or {}).get("facts") or ()}), None)
            option = next((e for e in evaluated if e["id"] in used and related & set(_option_facts(data, e["id"], case_facts))), None)
            resolved.append({"key": f"fact:{d['fact']}", "line": d["question"], "value": d["value"], "by": d["evidence"],
                             "blocks": {"question": (question or {}).get("item_id"), "option": (option or {}).get("id"),
                                        "condition": d["question"]},
                             "now": {"question": (question or {}).get("state"), "option": (option or {}).get("state"), "condition": d["state"]}})

    # the letter's parts: only an assessment of an area with an options file
    letter = None
    if data and a5:
        im_fall = "\n".join(l["text"] for l in in_case) if in_case else None
        zu_fragen = _zu_fragen(out_questions)
        empfehlung = _recommendation(data, graph, used, by_option, items, events, flagged, case_facts, open_wishes)
        if acc is not None:
            ticked_lines = [r["line"] for r in residual if r["ticked"]]
            nachzureichen = "\n".join(["Bitte reichen Sie uns noch nach:"] + [f"– {l}" for l in ticked_lines]) if ticked_lines else ""
        else:
            nachzureichen = None  # a run without the account: the documents still asked, as before
        letter = {"im_fall": im_fall, "zu_fragen": zu_fragen, "empfehlung": empfehlung, "nachzureichen": nachzureichen}

    # decisions that block the approval: the cover (while the assessment rests on it), the recommendation, the prospects
    blocking = []
    if a5 and premise_action and case_facts.get("deckung") in (None, "offen"):
        blocking.append({"kind": "decision", "key": "deckung", "text": "Deckung"})
    if a5 and data and selectable and not chosen:
        blocking.append({"kind": "decision", "key": "empfehlung", "text": lapse or "Empfehlung übernehmen"})
    if a5 and case_facts.get("aussichten") in UNJUDGED:
        blocking.append({"kind": "decision", "key": "aussichten", "text": PROSPECTS})

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
            "wishes": [{"fact": w["fact"], "text": w["text"], "evidence": fact_evidence(w["fact"], result, state),
                        **({"contradicted": contra[w["fact"]]} if w["fact"] in contra else {})}
                       for w in (data or {}).get("wishes") or () if facts.get(w["fact"]) is True],
            "questions": out_questions, "rules": [r for r in rules if r["conditions"]], "options": shown,
            "proposal": proposal, "alternatives": alternatives, "adopted": adopted, "chosen": chosen,
            "options_sha256": options.sha256(area_id) if data else None,
            "options_version": (data or {}).get("version"), "review": options.weakest(review_states) if review_states else None,
            "changes_if": changes, "residual": residual, "asks": asks, "open_wishes": open_wishes, "resolved": resolved,
            "deciding": deciding, "contradicted": contra, "in_case": in_case, "letter": letter, "blocking": blocking,
            "premise": premise, "candidates": candidates, "label": (data or {}).get("label"),
            "summary": {"answered": states.count("beantwortet"), "conditional": states.count("bedingt"), "open": states.count("offen"),
                        "check": states.count("pruefen"), "proposal": titles, "residual": sum(1 for r in residual if r["ticked"]),
                        "asked": sum(1 for a in asks if a["kind"] == "fact"), "resolved": len(resolved),
                        "decisions": [b["key"] for b in blocking if b["kind"] == "decision"]}}


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
    if weak.get(leaf["fact"]) == "conflicting":
        return "widersprüchlich"
    if facts.get(leaf["fact"]) is None and "known" not in leaf:
        return "offen"
    holds = evaluate_condition(leaf, facts)
    return "nicht erfüllt" if holds is False else "vermutet" if weak.get(leaf["fact"]) else "erfüllt"


def _fact_day(fact, result, state, acc):
    """The day the customer said what a fact holds: the date of the document its quote comes from. A fact the handler set
    (the state knows its edit, not its day) has no such date: its line is not stated with one."""
    edit = ((state or {}).get("overrides") or {}).get(fact)
    if edit:
        return _day(str(edit.get("at") or "")[:10]) if isinstance(edit, dict) else None
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


def _recommendation(data, graph, used, by_option, items, events, flagged, facts, open_wishes=()):
    """The recommendation as it follows «Wir empfehlen Ihnen, »: the first option's advice, then «Zudem empfehlen wir
    Ihnen, » and the next, ending with a full stop; then what it rests on (the facts that would change it, each in its
    «sofern» words) and, for a wish no way holds for yet, the question that decides it with what it decides. Without a way
    that holds: the question first («uns mitzuteilen, …; davon hängt ab, …»), else the gap."""
    def asked(row, key):
        if flagged.wording(key) or not row.get("ob"):
            return gap(f"{GAP_WHAT[key]} ({reviews.IN_REVIEW})")
        return data["wording"][key].replace("{frage}", row["ob"]).replace("{folge}", row["folge"])
    if not used:
        if not open_wishes:
            return gap(RECOMMENDATION)
        first, rest = open_wishes[0], open_wishes[1:]
        text = _sentence(asked(first, "open_only"))
        return " ".join([text] + [_sentence(asked(row, "open_wish")) for row in rest])
    texts = []
    for oid in used:
        spec = options.option(data, oid)
        template = all(enclosed(items, events, p["with_template"]) for p in spec["advice"] if p.get("with_template"))
        texts.append(options.advice_text(data, graph, oid, template=template, weak=(by_option.get(oid) or {}).get("weak") or ()))
    out = texts[0]
    for text in texts[1:]:
        join = gap(f"{GAP_WHAT['join']} ({reviews.IN_REVIEW})") + " " if flagged.wording("join") else data["wording"]["join"]
        out = f"{_sentence(out)} {join}{text}"
    out = _sentence(out)
    wishes = {w["fact"] for w in data["wishes"]}
    resting = []  # the facts of the case the recommendation rests on, as they hold now (never a wish: that is the customer's)
    for oid in used:
        for entry in (options.option(data, oid) or {}).get("changes_if") or ():
            if ":" in entry or entry in wishes or entry not in data["sofern"] or facts.get(entry) is None:
                continue
            weak = (by_option.get(oid) or {}).get("weak") or ()
            if entry in weak:
                continue  # already said «sofern …» in the advice
            resting.append(data["sofern"][entry])
    resting = list(dict.fromkeys(resting))
    if resting:
        out += " " + (gap(f"{GAP_WHAT['changes']} ({reviews.IN_REVIEW})") if flagged.wording("changes")
                      else data["wording"]["changes"].replace("{bedingung}", options.joined(resting)))
    for row in open_wishes:
        out += " " + _sentence(asked(row, "open_wish"))
    return out

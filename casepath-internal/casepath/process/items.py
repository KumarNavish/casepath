"""The canonical item list: everything CasePath states about a case, built in one place.

What the Übersicht shows, what the letter asks, what exports and gold labels refer to, and the list's hash all come
from build_items. The browser only draws it. Model-free; the evaluator is used as it is.

Item ids are "<kind>:<key>". Fact, document, step and deadline keys are the process's own ids and stay stable across
reloads and re-evaluations; party, open_point, summary and reply keys are positions, valid within one run.
"""
import hashlib
import json
import re

from . import account, cover, customer_letters, incoming, keypoints, mandate, review as reviews, settlement, urgent
from .area import compute_deadline, open_ended_title, period_text, set_date, statutory_period
from .clock import as_of, historic as historic_file, parse_date, silence
from .workflows import done_actions, evaluate_condition, holds_unless_done, stage_floor

CUSTOMER_ROLE = re.compile(r"^user", re.I)  # a step the customer answers in the online form or chat
DECISION_ROLE = re.compile(r"^entscheidung", re.I)
PERIOD = re.compile(r"\d{1,3} (days|weeks|months|years) (from|before) \d{4}-\d{2}-\d{2}")
UNNAMED = "Frist laut Akte, Anlass nicht gelesen"  # a date the reading gives without what it was for
# Text written for the reader (a format to fill in, a template slot) that must never reach the list or the card.
FORMAT_WORD = r"(?:DD|MM|YYYY|YY|JJJJ|JJ|TT|hh|mm)"
FORMAT = re.compile(rf"\b{FORMAT_WORD}(?:[.\-/:]{FORMAT_WORD})+\b")
SLOT = re.compile(r"\{[^{}]*\}|<[^<>]*>|«\s*·\s*»")


def placeholder(text):
    """Whether a text still holds a placeholder: a date format (DD.MM.YYYY, JJJJ-MM-TT), {…} or <…>."""
    return bool(FORMAT.search(str(text or "")) or SLOT.search(str(text or "")))


def plain(text):
    """A text as the list and the card show it: a part that holds a placeholder (in brackets, or the clause after a colon
    or semicolon) left out, never cut inside a word; None when nothing is left."""
    text = str(text or "")
    if not placeholder(text):
        return text
    # a bracket with a placeholder goes, with the preposition that only led to it («bis (DD.MM.YYYY)»)
    text = re.sub(r"(?:\s+(?:bis|am|vom|ab|per|seit|zum|zur|an|auf))?\s*\([^()]*\)", lambda m: "" if placeholder(m.group(0)) else m.group(0), text)
    parts = re.split(r"(?<=[:;,])\s+", text)
    kept = []
    for part in parts:
        if placeholder(part):
            break
        kept.append(part)
    text = SLOT.sub("", " ".join(kept)).strip(" ,;:")
    text = re.sub(r"\s{2,}", " ", text)
    return text or None


def _node_ids(refs):
    return {r.split("#", 1)[1] for r in refs or () if r.startswith("diagram#") and "#" in r}


def _condition_facts(condition, out):
    if isinstance(condition, dict):
        if "fact" in condition:
            out.add(condition["fact"])
        for key in ("all", "any"):
            for child in condition.get(key, ()):
                _condition_facts(child, out)
        if "not" in condition:
            _condition_facts(condition["not"], out)
    return out


def gating_facts(graph):
    """Facts that decide a step's way on or whether a document is needed."""
    out = set()
    for step in graph["steps"]:
        for edge in step.get("next", []):
            _condition_facts(edge.get("when"), out)
    for document in graph["documents"]:
        _condition_facts(document.get("required_when"), out)
    return out


def customer_facts(graph):
    """Facts only the customer's own answers settle: apart from the decision it gates, every step the fact refers to,
    and every step its branches lead to, is a customer step. The files cannot settle such a fact."""
    steps = {s["id"]: s for s in graph["steps"]}
    out = set()
    for fact in graph["facts"]:
        ids = _node_ids(fact.get("source_refs"))
        touched = [steps[i] for i in ids if i in steps]
        for step in graph["steps"]:
            for edge in step.get("next", []):
                if fact["id"] in _condition_facts(edge.get("when"), set()) and edge["to"] in steps:
                    touched.append(steps[edge["to"]])
        others = [s for s in touched if not DECISION_ROLE.match(s.get("role") or "")]
        if others and all(CUSTOMER_ROLE.match(s.get("role") or "") for s in others):
            out.add(fact["id"])
    return out


def _fact_node(graph, fact_id):
    """The step a fact is there for: the decision that branches on it, else the first step it refers to."""
    for step in graph["steps"]:
        if any(fact_id in _condition_facts(e.get("when"), set()) for e in step.get("next", [])):
            return step["id"]
    ids = _node_ids(next((f.get("source_refs") for f in graph["facts"] if f["id"] == fact_id), ()))
    return next((s["id"] for s in graph["steps"] if s["id"] in ids), None)


def _origin(document):
    if document.get("knowledge"):
        return f"knowledge#{document['knowledge']}"
    if document.get("edit"):
        return f"edit#{document['edit']}"
    return "workflow"


def _evidence(citations):
    return [{"file": c.get("file"), "page": c.get("page"), "quote": c.get("quote")} for c in citations or ()]


GENERIC_TITLES = {"bericht", "schreiben", "brief", "e", "email", "protokoll", "unterlagen", "dokument", "foto", "fotos", "rechnung", "beleg"}
FOLLOW_UP_TITLES = {"A6": "Dossier pendent halten mit Frist", "A7": "Statusanfrage mit Abschlussankündigung", "A12": "Dossier abschliessen"}


def kind_title(graph, kind):
    """An action kind's German title, from the process's own action kinds (the backbone), its forms, or the titles of the
    clock's follow-ups; a code ("A2") never reaches a handler as a title. None only for no kind."""
    if not kind:
        return None
    graph = graph or {}
    row = (graph.get("action_kinds") or {}).get(kind) or (graph.get("forms") or {}).get(kind) or {}
    return row.get("title") or FOLLOW_UP_TITLES.get(kind) or ("Weitere Handlung" if re.fullmatch(r"A\d{1,2}", str(kind)) else str(kind))


def _in_file(files, kinds):
    """How many documents in the case's files are of one of these kinds (from the reading's document list)."""
    return sum(1 for f in files or () for s in ((f.get("extraction") or {}).get("segments") or [])
               if any(k in (s.get("kind") or "").lower() for k in kinds))


def _day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else str(value)


def practice_tag(document):
    """The tag a practice need carries wherever the handler sees it: how often Protekta asked for it ("in 6 von 7 Fällen
    verlangt"), from a practice rule of Knowledge or the module's own practice count; None for a need from the law alone."""
    if document.get("practice"):
        return document["practice"]
    m = next((m for r in document.get("source_refs") or () if (m := re.fullmatch(r"practice#(\d+)of(\d+)", str(r)))), None)
    return f"in {m.group(1)} von {m.group(2)} Fällen verlangt" if m else None


def unsettled_trigger(result, fact_id):
    """A trigger date read but not settled: {value, why, verdict, citations} when the source checker rejected the reading or
    two readings differ; None when it was never read."""
    row = next((f for f in result.get("facts", []) if f.get("fact") == fact_id), None)
    if not row or row.get("value") in (None, ""):
        return None
    if row.get("status") == "conflicting":
        why = "zwei Lesungen der Akte widersprechen sich" + (f" (auch «{row['second_value']}»)" if row.get("second_value") else "")
    elif row.get("status") == "established" and row.get("verdict") == "rejected":
        why = "von der Quellenprüfung nicht bestätigt"
    else:
        return None
    return {"value": row["value"], "why": why, "verdict": row.get("verdict"), "citations": row.get("citations")}


def further(title):
    """An open-ended need partly in the file and still asked for: «Weitere Korrespondenz mit … (über die vorliegenden
    Schreiben hinaus)», not «Sämtliche Korrespondenz …» as if nothing were there."""
    rest = re.sub(r"^\s*(sämtliche|sämtlichen|alle|bisherige|bisherigen)\s+", "", str(title), flags=re.I)
    return f"Weitere {rest[:1].upper()}{rest[1:]} (über die vorliegenden Schreiben hinaus)"


def requested_title(d, row, ask):
    """The title a document need is asked under: an open-ended need partly in the file asks for the rest."""
    title = row.get("title") or d.get("title") or ""
    return further(title) if row.get("partial") and ask in {"now", "later", "proposed"} and open_ended_title(title) else title


def ask_of(graph, d, row, files):
    """Whether one document need of the evaluation is asked now, offered ("proposed"), asked later or not at all (None):
    the one rule the item list, the first request and the stage's way out ("nichts anzufordern") share."""
    by_stage = any(x.get("action") for x in graph["steps"])
    guess = str(d.get("edit") or "").startswith("pb") and not d.get("knowledge")  # the process builder's own addition
    if row["status"] == "present":
        return None
    if d.get("offered") and row["required"] in {"yes", "depends"}:
        return "proposed"  # practice is split: a mention of the missing document ticks it as its own line
    if row.get("partial") and d.get("when_partly_present") == "offer" and row["required"] in {"yes", "depends"}:
        return "proposed"  # an open-ended need partly in the file: offered (from the law alone, no practice says to ask again)
    if d.get("offered_when_in_file") and _in_file(files, d["offered_when_in_file"]["kinds"]):
        return "proposed"  # practice: with evidence of this kind in the file, Protekta does not ask for more (4 of 5)
    if by_stage and guess:
        return "proposed"  # an agent's guess: offered in the checklist, unticked, for the handler to tick
    if row["required"] == "yes" or (row["required"] == "depends" and not by_stage and not guess):
        return "now"  # in the handler's workflow a need whose condition nobody has established waits: it is asked later
    if row["required"] == "depends":
        return "later"
    return None


def _unless_done(condition, facts):
    """Whether a condition holds when every negated fact the file leaves open is read as "not done"."""
    return holds_unless_done(condition, facts)


def trigger_question(graph, fact_id, facts):
    """Whether the question for a deadline's trigger date is asked: "ask" when a deadline it starts applies (no condition,
    or its condition holds) or the fact starts none, or the only thing open is whether a step was already taken ("not … is true" with the fact
    unknown); "offer" when the conditions depend otherwise on a fact the file leaves open; None when every deadline it starts is established as not applying (the question does not appear)."""
    starts = [d for d in graph.get("deadlines") or () if d.get("trigger") == fact_id]
    holds = [True if not d.get("when") else evaluate_condition(d["when"], facts or {}) for d in starts]
    if not holds or True in holds:
        return "ask"
    # "not yet done" is assumed while the file does not show the step was taken: the date of a deadline that only
    # waits for that is asked, because missing it costs most
    pending = any(h is None and _unless_done(d["when"], facts or {}) for d, h in zip(starts, holds))
    return "ask" if pending else "offer" if None in holds else None


def open_customer_questions(graph, facts):
    """The questions the first request asks by default: a fact the customer is asked (``ask_customer`` true, not
    "offered") that is still open, a trigger date only while a deadline it starts applies. Offered questions wait
    unticked and never make a letter by themselves."""
    return [f for f in graph["facts"] if f.get("ask_customer") is True and facts.get(f["id"]) is None
            and trigger_question(graph, f["id"], facts) == "ask"]


def pair_set_dates(items):
    """A date the file sets for the obligation a computed statutory deadline concerns (by the customer, the other side or
    an authority: the running-deadline fact read as «date · what · who · letter») is never hidden by the computed one:
    both stand, one line each, named for what they are. The same obligation: what the set date is for shares the
    deadline's words, or it was set in the letter whose date starts the deadline. Where the set date is later, the line
    says «prüfen, welche gilt»: no verified passage of the area says which one governs."""
    computed = [i for i in items if i["kind"] == "deadline" and i.get("origin") == "law" and parse_date(i.get("value"))
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(i.get("value")))]
    given = [i for i in items if i["kind"] == "deadline" and i.get("origin") != "law" and i.get("what") and parse_date(i.get("value"))]
    for law in computed:
        start = parse_date(law.get("stated"))
        for s in given:
            in_letter = start is not None and parse_date(s.get("source")) == start
            if s.get("concerns") or not (account.overlap(s["what"], (law.get("label") or {}).get("de")) >= 0.5 or in_letter):
                continue
            later = parse_date(s["value"]) > parse_date(law["value"])
            article = "in der" if re.search(r"(ung|E-Mail|Nachricht)$", str(s.get("source") or "").split(" ")[0]) else "im"  # «in der Vorladung», «im Schreiben vom …»
            where = f"{article} {s['source']} gesetzt" if s.get("source") else f"gesetzt von {s['by']}" if s.get("by") else "in der Akte gesetzt"
            law["set_date"] = {"item": s["item_id"], "date": s["value"], "later": later,
                               "lines": [f"gesetzlich: {_day(law['value'])}", f"{where}: {_day(s['value'])}"] + (["prüfen, welche gilt"] if later else [])}
            s["concerns"] = law["item_id"]
            break


def account_dates(items, ledger, graph=None):
    """The dates by which someone must act that the running account holds (an ask, an offer, a next step) and that are
    still open, as «Fristen» lines in the same shape as a date others set (what is due, who set it, for whom, in which
    letter); a date the file's set-date reading already gives for the same obligation is not added twice."""
    given = [i for i in items if i["kind"] == "deadline" and parse_date(i.get("value"))]
    for d in account.open_dates(ledger):
        if d["date"] and any(parse_date(i["value"]) == parse_date(d["date"]) and (not i.get("what") or account.overlap(i.get("what"), d["what"]) >= 0.34
                                                                                  or i.get("unnamed")) for i in given):
            continue  # the same date, read once as a set date: one line
        set_by, for_ = account.PARTY_TITLES[d["set_by"]], account.PARTY_TITLES.get(d["for"], "Dritte")
        undated = not d["date"]  # a date the file sets in words no rule reads: said so, with the words, never guessed
        items.append({"item_id": f"deadline:{d['key']}", "kind": "deadline", "key": d["key"], "system": "casepath",
                      "label": {"de": d["what"], "en": d["what"]}, "value": "prüfen" if undated else d["date"],
                      "stated_as": "possible" if undated else "computed" if d["computed"] else "established",
                      "verdict": "accepted", "evidence": _evidence(d["citations"]), "node": None, "origin": "account", "chain": False,
                      "what": d["what"], "by": set_by, "set_by": d["set_by"], "for": for_, "party": d["for"], "source": d["source"], "account": True,
                      "set_by_others": d["set_by"] != account.INSURER,
                      **({"due_text": account.CHECK_DATE, "stated": d["text"]} if undated else {"due_text": d["text"]} if d.get("text") else {}),
                      **({"stated": d["text"], "rule": f"{d['text']} ab {d['source']}, nach Kalendertagen berechnet"} if d["computed"] else {})})


def open_condition(deadline, facts):
    """Whether a statutory deadline depends on a fact the file leaves open: its condition is unsettled even when every
    step the file does not show is read as not taken (a penalty order whose objection the file does not mention applies;
    one «nur bei einer Ordnungsbusse» while the file does not say whether there is one does not)."""
    return bool(deadline.get("when")) and evaluate_condition(deadline["when"], facts) is None and not _unless_done(deadline["when"], facts)


def worded(deadline):
    """What a deadline's data adds for the letters: how it is said where the rule reads badly, and what keeps it."""
    return {k: deadline[k] for k in ("sentence", "wahren") if deadline.get(k)}


# Every kind of item the list holds: build_items' own and the cover's (cover.items: cover, check, contact). The screen marks
# each element it shows with «kind:key», and the event route accepts exactly these kinds (and the screen's own, below), so
# nothing shown goes unmeasured; add() refuses a kind not named here, so the two never drift apart.
ITEM_KINDS = frozenset({"step", "document", "fact", "deadline", "next_action", "letter_question", "hint", "key_point", "stage_line",
                        "stand", "entry", "record_gap", "customer_letter", "customer_question", "party", "timeline", "open_point",
                        "answer", "summary", "reply", "cover", "check", "contact"})
SCREEN_KINDS = frozenset({"letter", "point", "followup"})  # beside the list: the letter, a point to settle first, the follow-up date


def build_items(state, result, files=None, events=None, review=None):
    """``events``: the case's log, for what a person did outside the facts (a letter copied, a case moved into or out of
    the historic files). ``review``: the jurists' marks that hold for the legal content as it is now (review.Model.current):
    an element marked «Änderung nötig» is offered unticked with «in Prüfung» (a hint, a key point's advice, a template);
    a deadline is never hidden or unticked by a mark, and it, like a document, a question or a cover point, shows «in Prüfung»."""
    graph, ev, result = state.get("process"), state.get("evaluation"), result or {}
    flagged = reviews.flags(graph, review)
    marked = lambda held: {"review": reviews.IN_REVIEW} if held else {}
    case = state.get("case") or {}
    study = (case.get("intake") or {}).get("study")
    created = study.get("opened") if isinstance(study, dict) else case.get("created_at")  # a study copy counts as its source, as frozen
    old = historic_file(files or [], created, events or ())
    from .completion import contacted as reached  # a letter of the insurer dispatched, or copied by a browser before this release
    contacted = reached(events)
    items = []
    def add(kind, key, label=None, **fields):
        if kind not in ITEM_KINDS:
            raise ValueError(f"item kind {kind!r} is not in ITEM_KINDS")
        text = label if isinstance(label, dict) else {"de": label, "en": label}  # the process speaks German; both keys always present
        items.append({"item_id": f"{kind}:{key}", "kind": kind, "key": key, "system": "casepath", "label": text, **fields})
    if graph and ev:
        graph = {**graph, "action_by_stage": any(x.get("action") for x in graph["steps"])}
        gating, customer = gating_facts(graph), customer_facts(graph)
        waiting = {w["fact"] for w in ev.get("waiting_for", [])}
        for row in ev.get("path", []):
            step = next((s for s in graph["steps"] if s["id"] == row["step"]), {})
            add("step", row["step"], value=row["state"], stated_as="established", verdict=None, evidence=[], node=row["step"],
                origin="workflow", chain=True, label=row.get("title") or row["step"], legal_basis=step.get("legal_basis"))
        docs = {d["id"]: d for d in graph["documents"]}
        part_of = {part: whole for whole, d in docs.items() for part in d.get("includes", ())}
        found = {d["document"]: d for d in result.get("documents", [])}
        for row in ev["documents"]:
            d = docs.get(row["document"], {})
            ask = None if ev.get("outcome") else ask_of(graph, d, row, files)
            note = (found.get(row["document"]) or {}).get("note")
            disputed = found.get(row["document"]) or {}
            if ask == "now" and disputed.get("verdict") == "rejected" and disputed.get("status") in {"absent", "unusable"}:
                # The source checker says the negative finding is not shown: asking for it may ask for what is in the file.
                ask, note = "proposed", "Die Prüfung widerspricht dem Befund «fehlt/unbrauchbar»"
            add("document", row["document"], value=row["status"], stated_as="put_to_handler" if row["required"] == "depends" else "established",
                verdict=(found.get(row["document"]) or {}).get("verdict"), evidence=_evidence(row.get("citations")),
                node=row.get("step"), origin=_origin(d), chain=True, label=requested_title(d, row, ask), status=row["status"],
                legal_basis=d.get("legal_basis") or row.get("legal_basis"),
                required=row["required"], ask=ask, part_of=part_of.get(row["document"]),
                **({"practice": practice_tag(d)} if practice_tag(d) else {}), **marked(flagged.document(row["document"])),
                reason=("liegt teilweise vor" if row.get("partial") and d.get("when_partly_present") == "offer" else
                        f'{_in_file(files, d["offered_when_in_file"]["kinds"])} Fotos/Protokolle liegen vor'
                        if d.get("offered_when_in_file") and _in_file(files, d["offered_when_in_file"]["kinds"]) else
                        note if row["status"] in {"unusable", "missing"} and note else None),
                **({"partial": row["partial"]} if row.get("partial") else {}))
        definitions = {f["id"]: f for f in graph["facts"]}
        overrides, set_by_hand = state.get("overrides") or {}, (state.get("facts") or {})
        rows = {f["id"]: {"fact": f["id"], "status": "unknown", "value": None, "citations": []} for f in graph["facts"]}  # every fact the process asks about
        rows.update({f["fact"]: f for f in result.get("facts", [])})
        for key, definition in definitions.items():  # a derived fact is computed in the evaluation, never read: list its value
            if definition.get("derived") and set_by_hand.get(key) is not None:
                rows[key] = {"fact": key, "status": "computed", "value": set_by_hand[key], "citations": [], "verdict": "derived"}
        for key in overrides:  # a fact a case worker set shows the value set, whatever the run read
            rows[key] = {**rows.get(key, {"fact": key, "citations": []}), "status": "established", "value": set_by_hand.get(key),
                         "verdict": "set_by_handler", "by_edit": overrides[key]}
        statutory = graph.get("deadlines") or []
        for key, fact in list(rows.items()):  # a statutory period read into a deadline fact is the area's own computed item
            if (definitions.get(key) or {}).get("deadline") and fact.get("verdict") != "set_by_handler" and statutory_period(statutory, fact.get("value")):
                rows[key] = {"fact": key, "status": "unknown", "value": None, "citations": []}
        for fact in rows.values():
            if fact["fact"] not in definitions:
                continue
            computed = isinstance(fact.get("value"), str) and PERIOD.fullmatch(fact["value"])
            add("fact", fact["fact"], value=fact.get("value"),
                stated_as="computed" if computed and fact["status"] == "established" else fact["status"],
                verdict=fact.get("verdict"), evidence=_evidence(fact.get("citations")), node=_fact_node(graph, fact["fact"]),
                origin=f"edit#{fact['by_edit']}" if fact.get("by_edit") else "workflow" if not str(fact["fact"]).startswith(("k-", "q-")) else "process_builder",
                chain=fact["fact"] in gating, values=definitions[fact["fact"]].get("values") or (["ja", "nein"] if definitions[fact["fact"]].get("type") == "boolean" else None),
                type=definitions[fact["fact"]].get("type"),
                **({"stages": definitions[fact["fact"]]["stages"]} if definitions[fact["fact"]].get("stages") else {}),
                label=definitions[fact["fact"]].get("question"), chat_only=fact["fact"] in customer, path=fact["fact"] in waiting,
                **({"part": fact["part"]} if fact.get("part") else {}))
        for d in result.get("deadlines", []):
            if statutory_period(statutory, d.get("stated")):
                continue  # the law's period, listed below as the area's own deadline
            # a date a court, an authority or the other side set for the customer: what is due, who set it, where it stands
            given = d.get("set") or {k: v for k, v in (set_date((rows.get(d["fact"]) or {}).get("value")) or {}).items() if k != "date" and v}
            # without what it was for, the date is named as such: the reader's question is never its title
            add("deadline", d["fact"], value=d["date"], stated_as="computed" if d.get("computed") else "established", verdict="accepted",
                evidence=_evidence((rows.get(d["fact"]) or {}).get("citations")), node=_fact_node(graph, d["fact"]), origin="workflow", chain=True,
                label=given.get("what") or UNNAMED, **({} if given.get("what") else {"unnamed": True}),
                **({"set_by_others": True, **{k: given[k] for k in ("what", "by", "source") if given.get(k)}} if given.get("what") else {}),
                **({"stated": d["stated"], "rule": d["rule"]} if d.get("computed") else {}))
        unsettled_triggers, missing_triggers = set(), []
        for d in graph.get("deadlines", []):  # the area's statutory deadlines, from the trigger date the case establishes
            trigger = (state.get("facts") or {}).get(d["trigger"])
            computed = compute_deadline(d, trigger, state.get("facts") or {}) if trigger is not None else None
            if computed:
                unsettled = open_condition(d, state.get("facts") or {})
                backwards = isinstance(d["period"], dict) and "days_before" in d["period"]
                add("deadline", d["id"], value=computed[0], stated_as="computed", verdict="accepted", evidence=[],
                    node=_fact_node(graph, d["trigger"]), origin="law", chain=True, label=d["title"], stated=str(trigger),
                    rule=computed[1], legal_basis=d["basis"], missed=d["missed"], direction=d.get("direction", "bis"),
                    party=d.get("party", "kunde"), **({"condition": d["when_text"]} if unsettled else {}),
                    **({"due_text": f"{period_text(d)} am {_day(trigger)}"} if backwards else {}), **worded(d), **marked(flagged.deadline(d["id"])))
            elif trigger is None and (doubt := unsettled_trigger(result, d["trigger"])):
                # A trigger date that was read but not settled (the checker rejected it, or two readings differ) never makes
                # its deadline disappear: it is shown as possible, with the date the reading gives, and the date is asked.
                maybe = compute_deadline(d, doubt["value"], state.get("facts") or {})
                if maybe is None:
                    continue  # its condition fails: the deadline does not apply
                unsettled_triggers.add(d["trigger"])
                candidate = maybe[0] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", maybe[0]) else None
                add("deadline", d["id"], value="prüfen", stated_as="possible", verdict=doubt["verdict"], evidence=_evidence(doubt["citations"]),
                    node=_fact_node(graph, d["trigger"]), origin="law", chain=True, label=d["title"], stated=str(doubt["value"]),
                    rule=f"Auslöser «{doubt['value']}» {doubt['why']}" + (f"; danach bis {_day(candidate)}" if candidate else "") + "; Datum prüfen",
                    legal_basis=d["basis"], missed=d["missed"], direction=d.get("direction", "bis"), party=d.get("party", "kunde"),
                    possible=True, **({"candidate": candidate} if candidate else {}),
                    **({"condition": d["when_text"]} if open_condition(d, state.get("facts") or {}) else {}),
                    **worded(d), **marked(flagged.deadline(d["id"])))
            elif trigger is None:
                # The file does not give the date that starts it: never left out while its condition holds or is open. It is
                # shown as possible with «Datum fehlt», says what starts it, and its date is asked (the trigger question).
                # Only a deadline whose condition is established as not met is absent.
                holds = evaluate_condition(d["when"], state.get("facts") or {}) if d.get("when") else True
                if holds is False:
                    continue
                missing_triggers.append(d)
                starts = d.get("from") or "ab dem auslösenden Ereignis"
                add("deadline", d["id"], value="Datum fehlt", stated_as="possible", verdict=None, evidence=[],
                    node=_fact_node(graph, d["trigger"]), origin="law", chain=True, label=d["title"], stated=None,
                    rule=f"{period_text(d)} {starts}; Datum fehlt" + (f" ({d['question']})" if d.get("question") else ""),
                    legal_basis=d["basis"], missed=d["missed"], direction=d.get("direction", "bis"), party=d.get("party", "kunde"),
                    possible=True, missing=True, starts=starts, trigger=d["trigger"], due_text="Datum fehlt",
                    **({"condition": d["when_text"]} if open_condition(d, state.get("facts") or {}) else {}), **worded(d),
                    **marked(flagged.deadline(d["id"])))
        account_dates(items, state.get("account"), graph)  # a date the account holds for an ask, an offer or a next step, still open
        pair_set_dates(items)  # a date the file sets for the same obligation stands beside the computed one
        asked =[i for i in items if i["kind"] == "document" and i["ask"] == "now"]
        lines = len([i for i in asked if not i["part_of"] or i["part_of"] not in {a["key"] for a in asked}])
        steps = {x["id"]: x for x in graph["steps"]}
        here = steps.get((ev.get("current") or {}).get("step")) or (steps.get(ev["path"][-1]["step"]) if ev.get("path") else None) or {}
        planned = here.get("action")  # the handler's workflow names the action each stage ends in
        if not planned and here.get("decision"):  # a stage that is the handler's decision: the decision is what is asked
            choice = here["decision"]
            planned = {"kind": choice["fact"], "title": choice["title"], "form": choice["form"], "next_in_days": None, "follow_up": None,
                       "skip_if": None, "choices": next((f.get("values") for f in graph["facts"] if f["id"] == choice["fact"]), None)}
        variant = next((v for v in (planned or {}).get("instead", []) if evaluate_condition(v["when"], state.get("facts") or {}) is True), None)
        if variant:  # a situation the stage answers differently (after a call: keep it pending with a deadline)
            planned = {**planned, **{k: v for k, v in variant.items() if k != "when"}, "skip_if": None}
        known_facts = state.get("facts") or {}
        floor = stage_floor(graph, known_facts)
        done = done_actions(known_facts)
        clocked = {r["then"] for r in graph.get("clock") or ()}
        by_stage = graph.get("stage_actions")  # a stage whose action is done shows its follow-up, also one the clock governs
        if planned and not variant and planned["kind"][1:] in done and not planned.get("skip_if") and (by_stage or planned.get("follow_up") not in clocked):
            # the stage's action is in the case's history already: its follow-up comes next, dated; a follow-up the clock
            # governs is shown with the date it comes due and turns into the clock's action only when nobody answered
            planned = {**planned, "skip_if": True}
            rule = next((r for r in graph.get("clock") or () if by_stage and r["then"] == planned.get("follow_up")
                         and here.get("id") in (r.get("stages") or [here.get("id")])), None)
            if rule:  # the date the clock would come due: the same day the follow-up is shown for
                planned["next_in_days"] = rule["days"]
        if planned and floor:  # placed by its history: the follow-up counts from the last action taken
            days = [d for c, ds in done.items() for d in ds if d]
            planned = {**planned, **({"since": max(days)} if days else {})}
        ledger, look = state.get("account"), as_of(files or ())
        if ledger:  # the running account: silence is read from its ledger (the party asked sent nothing since), not from any later date
            quiet = None if ev.get("outcome") else account.silence(ledger, graph.get("clock"), look, stage=here.get("id"))
        else:
            quiet = None if ev.get("outcome") else silence(graph.get("clock"), known_facts, files, stage=here.get("id"))  # nobody answered our last letter
        # The insurer conducts the case and a settlement is reached: agreement, bank details once, payout, receipt, closing
        # (settlement.py); where the case has a running account, the agreement as it stands is read from it (amount, who pays,
        # by when, paid or not), otherwise from the offer and payment the file shows.
        insured_name = customer_name(result)
        settling = settlement.state(known_facts, rows, files, events, insured_name, settlement.from_account(ledger, known_facts)) \
            if settlement.applies(here.get("id"), known_facts) and not ev.get("outcome") else None
        if settling and not quiet:
            planned = settlement.planned(settling, known_facts)
        if quiet:
            planned = {"kind": quiet["then"], **({"form": quiet["form"]} if quiet.get("form") else {}), "title": quiet.get("title") or kind_title(graph, quiet["then"]), "next_in_days": quiet.get("deadline_days"),
                       "follow_up": quiet.get("follow_up"), "skip_if": None,
                       "reason": f'keine Antwort seit {silent_since(graph, quiet["last"])} vom {".".join(reversed(quiet["since"].split("-")))} ({quiet["silent_days"]} Tage)'}
        owed = None if ev.get("outcome") else account.payout_due(ledger, look)
        if owed:  # an agreed payment whose date has passed and that the file does not show made: chase it, a letter to the
            # party that owes it (form A11_nachfragen); the settlement sequence then proposes no step of its own beside it
            planned = {"kind": "A11", "form": "A11_nachfragen",
                       "title": f"Auszahlung {account.AT.get(owed.get('payer'), 'bei der Gegenpartei')} nachfragen",
                       "next_in_days": 10, "follow_up": "A11", "skip_if": None,
                       "reason": f"vereinbart ({account._source(owed)}): {account._terms_text(owed)}; keine Zahlung in den Akten",
                       "owed": {k: owed.get(k) for k in ("amount", "what", "payer", "by", "date")}}
        # What came in after the insurer's last own step (or after the report, before any step) and is still unanswered
        # outranks the stage's own action and the clock (the customer's own statutory deadline still leads the card and caps
        # the follow-up); the others wait, in priority order. What lies before that point is a fact of the case, shown in
        # «Der Fall», never an action. At intake, clarifying and assessing (``incoming_lead``) the stage's own action leads
        # while it is due, and the open items follow it («danach»): the first request or the assessment goes out first.
        order = {"ref": incoming.reference(known_facts, ledger, files, created), "ledger": ledger}
        dated_in = incoming.document_dates(graph, result.get("facts"), files)
        open_items = incoming.pending(graph, known_facts, dated_in, order)
        in_case = incoming.case_facts(graph, known_facts, dated_in, order)
        due_here = bool(planned) and not (planned.get("skip_if") and evaluate_condition(planned["skip_if"], known_facts))
        after = []
        if open_items and here.get("id") in (graph.get("incoming_lead") or ()) and due_here and not quiet and not owed:
            after, open_items = open_items, []
        if open_items:
            act = open_items[0]["action"]
            disputed = next((f for f in result.get("facts", []) if f.get("fact") == open_items[0]["fact"]), {})
            planned = {"kind": act["kind"], "title": act["title"], "form": act["form"], "next_in_days": act.get("next_in_days"),
                       "follow_up": None, "skip_if": None, "reason": incoming.reason(open_items[0]) + (
                           f"; eine zweite Lesung der Akte ergab «{disputed['second_value']}», bitte prüfen"
                           if disputed.get("status") == "conflicting" and disputed.get("second_value") else "")}
            if settling and open_items[0]["kind"]["id"] == "zahlung":  # the payment came in: the receipt step's letter
                planned = {**planned, "form": "A11_eingang", "settlement": "eingang"}
        planned = cover.adjust(planned, known_facts, here.get("id"), ledger)  # prescribed letters: refusal for lack of prospects, demand before an ending
        if planned and not (planned.get("skip_if") and evaluate_condition(planned["skip_if"], state.get("facts") or {})):
            title = planned["title"]
            action = (planned["kind"], title, {"de": title, "en": title})
        elif planned:  # this stage's action was already taken: its follow-up comes next
            title = planned.get("follow_up_title") or kind_title(graph, planned.get("follow_up"))
            action = (planned.get("follow_up"), title, {"de": title, "en": title})
        elif ev.get("outcome"):
            title = ev["outcome"].get("title") or ev["outcome"]["id"]
            action = ("close", title, {"de": f"Fall abschliessen: {title}", "en": f"Close the case: {title}"})
        elif asked:
            action = ("request", f"{lines} documents", {"de": f"{lines} Unterlage{'' if lines == 1 else 'n'} beim Kunden anfordern", "en": f"Request {lines} document{'' if lines == 1 else 's'} from the customer"})
        elif ev.get("next_actions"):
            first = ev["next_actions"][0]
            action = ({"obtain": "request"}.get(first["kind"], first["kind"]), first["text"], first["text"])
        else:
            action = None
        # The most urgent thing leads: a deadline the customer must meet, open and ending within the backbone's threshold,
        # makes «Frist wahren» the prepared action at the stages the rule names; the stage's own action follows («danach»).
        # Done once its letter (and the template for the customer's own letter, where there is one) went out.
        rule = graph.get("urgent") or {}
        insured = customer_name(result)
        templates = customer_letters.evaluate(graph, known_facts, [i for i in items if i["kind"] == "deadline"], insured,
                                              known_facts.get("gegenpartei"), as_of(files))
        pressing = urgent.find(items, rule, look, here.get("id")) if action and not ev.get("outcome") else None
        template = next((t for t in templates if pressing and t.get("deadline") == pressing["key"]), None)
        if pressing and wahrt(events, pressing, template):
            pressing = None
        displaced = None
        if pressing:
            displaced = {"kind": "stage", "fact": None, "title": action[1], "date": None, "action": action[1], "code": action[0]}
            planned = {"kind": rule["kind"], "form": rule.get("form") or rule["kind"], "title": rule.get("title") or kind_title(graph, rule["kind"]),
                       "next_in_days": None, "follow_up": None, "skip_if": None, "reason": urgent.reason(pressing),
                       "deadline": pressing["item_id"], **({"template": f"vorlage:{template['id']}"} if template else {})}
            action = (planned["kind"], planned["title"], {"de": planned["title"], "en": planned["title"]})
        # A waiting action (pending, status inquiry, the stage's follow-up) whose party said by when it delivers what it still
        # owes («Unterlagen folgen bis 15.12.»): the case is looked at again on that day, not on the clock's
        waits = action and (action[0] in {"A6", "A7"} or (planned and action[0] == planned.get("follow_up") and planned.get("skip_if")))
        waited_for = {"A9": "gegenpartei", "A8": "gegenpartei", "A2": "kanzlei", "A10": "kanzlei"}.get(action[0] if action else None, "kunde")
        awaited = account.awaited(ledger, waited_for, look) if waits and ledger else None
        closing = None
        if action and action[0] in {"A12", "close"}:  # a closing names its reason once: «keine Rückmeldung», «Sache erledigt»
            stage_title = str(here.get("title") or "")
            outcome_title = str((ev.get("outcome") or {}).get("title") or "")
            closing = next((t.split(": ", 1)[1] for t in (stage_title, outcome_title) if t.startswith("Abschluss: ")), None) or \
                {"A12_still": "keine Rückmeldung", "A12_erledigt": "Sache erledigt"}.get((planned or {}).get("form") or "") or \
                ("fehlende Mitwirkung" if "mitwirkung" in str((planned or {}).get("form") or "") or here.get("id") == "abschluss_mitwirkung" else outcome_title or None)
        if action:
            add("next_action", "0", **({"closing": closing} if closing else {}), **({"next_in_days": planned.get("next_in_days"), "follow_up": planned.get("follow_up"),
                                        **({"reason": planned["reason"]} if planned.get("reason") else {}),
                                        **({"because": planned["because"]} if planned.get("because") else {}),
                                        **({"since": planned["since"]} if planned.get("since") else {}),
                                        **({"owed": planned["owed"]} if planned.get("owed") else {}),
                                        **({"settlement": {"step": (settling or {}).get("step", ("",))[0], "done": list((settling or {}).get("done") or []),
                                                           "terms": bool(((settling or {}).get("terms") or {}).get("amount")),
                                                           "iban": bool(((settling or {}).get("iban") or {}).get("holder"))}} if settling or owed else {}),
                                        **({"choices": planned["choices"]} if planned.get("choices") else {}),
                                        **({"until": awaited["date"], "awaits": awaited} if awaited else {}),
                                        **({"deadline": planned["deadline"], "urgency": urgent.urgency(pressing, look, rule)} if pressing else {}),
                                        **({"template": planned["template"]} if pressing and planned.get("template") else {}),
                                        **({"form": planned["form"]} if planned.get("form") and action[0] == planned["kind"] else {})} if planned else {}),
                **({"incoming": {"kind": open_items[0]["kind"]["id"], "fact": open_items[0]["fact"], "date": open_items[0]["date"],
                                 "value": open_items[0]["value"], **({"dated_by": "document"} if open_items[0]["dated_by"] == "document" else {})},
                    "then": [{"kind": r["kind"]["id"], "fact": r["fact"], "title": r["kind"]["title"], "date": r["date"], "action": r["action"]["title"]}
                             for r in open_items[1:]]} if open_items else {}),
                **({"then": ([displaced] if displaced else []) + [{"kind": r["kind"]["id"], "fact": r["fact"], "title": r["kind"]["title"], "date": r["date"],
                                                                     "action": r["action"]["title"], "line": customer_line(r)} for r in after]}
                   if after or displaced else {}),
                value=action[1], stated_as="established", verdict=None,
                evidence=_evidence((rows.get(open_items[0]["fact"]) or {}).get("citations")) if open_items else [], node=(ev.get("current") or {}).get("step"),
                origin="workflow", chain=True, label=action[2], action=action[0])
        # The first request asks, besides documents, what only the customer can say, and gives the hints the law calls for.
        known = state.get("facts") or {}
        if planned and planned.get("kind") == "A4" and action and action[0] == "A4":  # the one open point is the letter's one question
            from .casegraph import open_stage_facts
            for fid in open_stage_facts(graph, state.get("facts") or {}, ev)[:1]:
                f = next(x for x in graph["facts"] if x["id"] == fid)
                add("letter_question", fid, value=f.get("customer_question") or f["question"], stated_as="put_to_handler", verdict=None,
                    evidence=[], node=here.get("id"), origin="workflow", chain=True, label=f.get("customer_question") or f["question"], ask="now",
                    **marked(flagged.question(fid)))
        # In an area observed in practice (its lines carry counts), the first request's ticked lines are exactly those
        # practice supports: a line from another mechanism (a key point's advice, a template for the customer's letter, a
        # cover question) is offered unless the area's data cites practice for it, and an observed hint is never rewritten
        # or replaced. In an area written from the law alone, advice is ticked when its condition holds.
        practiced = bool((graph.get("area") or {}).get("practice"))
        first_request = bool(planned and planned.get("kind") == "A1" and action and action[0] == "A1") or bool(displaced and displaced["code"] == "A1")
        if first_request:
            for f in graph["facts"]:
                # a trigger date is asked only while a deadline it starts applies: offered while that depends on an open fact
                trigger = trigger_question(graph, f["id"], known)
                if f.get("ask_customer") and known.get(f["id"]) is None and trigger:
                    asked = f.get("customer_question") or f["question"]
                    # a question's default follows practice: "offered" ones Protekta rarely asks wait unticked
                    # in an area observed in practice, a question practice does not show (a cover question) is offered
                    add("letter_question", f["id"], value=asked, stated_as="put_to_handler", verdict=None, evidence=[],
                        node=here.get("id"), origin="workflow", chain=True, label=asked,
                        ask="proposed" if trigger == "offer" or f["ask_customer"] == "offered" and f["id"] not in unsettled_triggers
                        or practiced and not keypoints.observed(f) else "now", **marked(flagged.question(f["id"])))
            asked_ids = {i["key"] for i in items if i["kind"] == "letter_question"}
            for d in missing_triggers:  # a trigger date the area does not ask the customer by itself: offered with its deadline
                if d["trigger"] not in asked_ids and d.get("question") and known.get(d["trigger"]) is None:
                    asked_ids.add(d["trigger"])
                    add("letter_question", d["trigger"], value=d["question"], stated_as="put_to_handler", verdict=None, evidence=[],
                        node=here.get("id"), origin="law", chain=True, label=d["question"], ask="proposed", **marked(flagged.question(d["trigger"])))
            # A key point that is advice the customer can act on now goes into the first request with its article: ticked when
            # its condition holds, offered while it depends on an open fact. Where it applies, it stands for the area's hint
            # that says the same (every article of the hint is one of the point's); where it is open and such a hint is in
            # the letter already, the hint says it. In an area observed in practice the observed hint always stays as it is,
            # an advice point that says the same is not added, and other advice is offered unless practice shows it.
            advice = [p for p in keypoints.evaluate(graph, known) if p.get("advice")]
            # a point marked «Änderung nötig» never stands for a hint: the hint stays as itself
            replaced = set() if practiced else \
                {h["id"] for p in advice if p["state"] == "applies" and not flagged.key_point(p["id"])
                 for h in graph.get("hints", []) if keypoints.covers(p, h)}
            given = set()
            for hint in graph.get("hints", []):
                if evaluate_condition(hint["when"], known) is not True and hint["when"] is not True or hint["id"] in replaced:
                    continue
                if hint.get("trigger"):
                    continue  # a deadline whose date is open: the letter asks the date that settles it, nothing more
                given.add(hint["id"])
                held = flagged.hint(hint["id"])  # a hint marked «Änderung nötig» is offered, not ticked; a deadline's stays
                add("hint", hint["id"], value=hint["text"], stated_as="put_to_handler" if held == "untick" else "established", verdict=None,
                    evidence=[], node=here.get("id"), origin="workflow", chain=True, label=hint["text"], legal_basis=hint.get("legal_basis"),
                    **marked(held))
            for hint in graph.get("hints", []):  # a hint whose condition is still open is offered too: Protekta gives it early
                if hint["when"] is not True and evaluate_condition(hint["when"], known) is None and hint["id"] not in replaced and not hint.get("trigger"):
                    given.add(hint["id"])
                    add("hint", hint["id"], value=hint["text"], stated_as="put_to_handler", verdict=None, evidence=[], node=here.get("id"),
                        origin="workflow", chain=True, label=hint["text"], legal_basis=hint.get("legal_basis"), **marked(flagged.hint(hint["id"])))
            for p in advice:
                held = flagged.key_point(p["id"])
                if (p["state"] == "open" or practiced or held) and any(keypoints.covers(p, h) for h in graph.get("hints", []) if h["id"] in given):
                    continue
                line = keypoints.advice_line(p)
                ticked = p["state"] == "applies" and (not practiced or p.get("observed")) and not held
                add("hint", f"kp-{p['id']}", value=line, stated_as="established" if ticked else "put_to_handler", verdict=None,
                    evidence=[], node=here.get("id"), origin="law", chain=True, label=line, key_point=p["id"], with_basis=True, **marked(held))
        # the cover points, the checks a prescribed letter rests on, and the first contact (cover.py)
        # a historic file never shows a first contact, nor does a case whose letter went out (cover.first_contact)
        covered = cover.items(graph, known_facts, result, files, planned if action and planned and action[0] == planned.get("kind") else None, here.get("id"),
                              created=created, historic=bool(old) or contacted, ledger=ledger)
        for i in covered:  # a cover point, a check or the first contact whose rule a jurist marked «Änderung nötig» says «in Prüfung»
            if (i["kind"] == "cover" and i["key"] != "summary" and flagged.cover(i["key"], known_facts.get("rechtsgebiet"))) \
                    or (i["kind"] == "check" and flagged.check(i["key"])) or (i["kind"] == "contact" and flagged.contact()):
                i["review"] = reviews.IN_REVIEW
        items += covered
        # The legal key points of the area: those that apply, and those whose condition the file leaves open (as questions);
        # the card shows those that help at the case's stage
        points = keypoints.evaluate(graph, known_facts, here.get("id"))
        on_card = {p["id"] for p in keypoints.shown(points)}
        for p in points:
            cited = [c for f in p["facts"] for c in ((rows.get(f) or {}).get("citations") or [])][:3]
            add("key_point", p["id"], value=p["state"], stated_as="established" if p["state"] == "applies" else "put_to_handler", verdict=None,
                evidence=_evidence(cited), node=here.get("id"), origin="law", chain=True, label=p["text"], legal_basis=p["cite"],
                law=p["law"], follows=p["follows"], check=p["check"], facts=p["facts"], shown=p["id"] in on_card, stages=p["stages"],
                **({"advice": keypoints.advice_line(p)} if p.get("advice") else {}), **marked(flagged.key_point(p["id"])))
        # At the mandate and handling stages: the short facts the file establishes there, each with its source
        dated = incoming.document_dates(graph, result.get("facts"), files)
        # A cost claim of the mandated firm is the open item: what the file shows about the guarantee, each line with its
        # source or «nicht in der Akte», the last a question for the handler (mandate.py); the stage's own lines it repeats go
        firm_claim = open_items[0] if open_items and mandate.is_firm_claim(open_items[0]) else None
        checked = mandate.cost_check(known_facts, rows, files, firm_claim, dated, graph) if firm_claim else []
        if settling is None and owed:  # a chase outside the sequence: the agreement and the customer's IBAN, if the file has it
            chase = {"terms": settlement.agreement({}, None, settlement.from_account(ledger, known_facts)), "iban": settlement.customer_iban(files, insured_name)}
        for line in checked + (settlement.lines(settling) if settling else settlement.lines(chase) if owed else []):
            extra = {k: v for k, v in line.items() if k not in {"id", "text", "citations", "facts"}}
            add("stage_line", line["id"], value=line["text"], stated_as="established", verdict=None, evidence=_evidence(line["citations"]),
                node=here.get("id"), origin="workflow", chain=False, label=line["text"], facts=line.get("facts") or [], shown=True, **extra)
        for line in keypoints.stage_lines(graph, known_facts, rows, dated, here.get("id")):
            if checked and line["id"] in {"kostengutsprache", "bericht", "kosten"}:
                continue
            add("stage_line", line["id"], value=line["text"], stated_as="established", verdict=None, evidence=_evidence(line["citations"]),
                node=here.get("id"), origin="workflow", chain=False, label=line["text"], facts=line["facts"], shown=True)
        # What came in before the insurer's last step or before the report: a fact of the case, in «Der Fall» with its source
        for row in in_case:
            line = incoming.fact_line(row, order["ref"])
            second = next((f for f in result.get("facts", []) if f.get("fact") == row["fact"]), {})
            if second.get("status") == "conflicting" and second.get("second_value"):  # a disagreement never hides it
                line["text"] += f"; eine zweite Lesung der Akte ergab «{second['second_value']}», bitte prüfen"
            add("stand", f"eingang:{row['fact']}", value=line["text"], stated_as="established", verdict=None,
                evidence=_evidence((rows.get(row["fact"]) or {}).get("citations")), node=None, origin="claim_reader", chain=False,
                label=line["label"], open=line["open"], entries=[], incoming={"kind": row["kind"]["id"], "fact": row["fact"], "date": row["date"],
                                                                               "timing": row["timing"], "line": customer_line(row)})
        # The running account: «Stand» in «Der Fall» and one row per document in the Verlauf (a run before it has none)
        for line in account.stand(ledger, look, graph):
            add("stand", line["id"], value=line["text"], stated_as="established", verdict=None, evidence=_evidence(line["citations"]),
                node=None, origin="account", chain=False, label=line["label"], open=line["open"], entries=line["entries"],
                **({"detail": line["detail"]} if line.get("detail") else {}), **({"handler": line["handler"]} if line.get("handler") else {}),
                **({"rows": [{"text": r["text"], "evidence": _evidence(r["citations"]), "entries": r["entries"], "request": r.get("request"),
                              **({"handler": r["handler"]} if r.get("handler") else {})} for r in line["rows"]],
                    "more": line["more"], "party": line["party"]} if line.get("rows") else {}))
        # a run made before the account: the handler's own entries are listed, and count once a full preparation read the account
        listed_only = None if ledger else account.build(state.get("handler_entries") or [], graph)
        for row in account.rows(ledger or listed_only, graph):
            add("entry", str(row["n"]), value=row["what"], stated_as="established", verdict=None, evidence=_evidence(row["citations"]),
                node=None, origin="handler" if row.get("handler") else "claim_reader", chain=False, label=row["kind_title"],
                **{k: row[k] for k in ("date", "from", "to", "from_title", "to_title", "phone", "notes", "open", "open_of", "number")}, step_kind=row["kind"],
                **({"handler": row["handler"]} if row.get("handler") else {}), **({"waiting": True} if listed_only else {}))
        if ledger:  # part of the file with no entry is said, never silent: «S. 26–79 ohne Eintrag» above the Verlauf
            for gap in account.gaps(ledger["entries"], account.pages_of(files)):
                name = next((f.get("name") for f in files or () if f.get("id") == gap["file"]), None)
                add("record_gap", f"{gap['file']}:{gap['from']}", value=account.gap_text(gap), stated_as="computed", verdict=None, evidence=[],
                    node=None, origin="account", chain=False, label=account.gap_text(gap) + (f" ({name})" if name else ""),
                    file=gap["file"], pages=[gap["from"], gap["to"]])
        # Letters the customer sends in his own name, whose condition holds (customer_letters.py): offered with the
        # assessment, and with the first request when the customer's own deadline is close
        rows_by_id = {c["id"]: c for c in graph.get("customer_letters") or ()}
        for t in templates:
            offered_with = t["offered_with"] + ([rule["kind"]] if pressing and t is template else [])
            held = flagged.letter(t["id"])  # marked «Änderung nötig»: offered, never sent along by default
            if (practiced and not keypoints.observed(rows_by_id.get(t["id"])) or held) and "A1" in offered_with:
                # practice does not show this template in a first request (or a jurist asked for a change): its sentence is
                # offered there, the template goes with the letter only when the handler ticks that line
                offered_with = [k for k in offered_with if k != "A1"]
                if first_request:
                    line = customer_letters.referral({"template_kind": t["kind"], "label": {"de": t["heading"]}, "to": t["to"],
                                                      "to_dative": t["to_dative"], "due": t["due"], "posted": t.get("posted")})
                    add("hint", f"cl-{t['id']}", value=line, stated_as="put_to_handler", verdict=None, evidence=[], node=here.get("id"),
                        origin="template", chain=True, label=line, customer_letter=t["id"], **marked(held))
            add("customer_letter", t["id"], value="applies", stated_as="established", verdict=None, evidence=[], node=here.get("id"),
                origin="law", chain=False, label=t["heading"], legal_basis=", ".join(t["cites"]), title=t["title"], text=t["text"],
                to=t["to"], to_dative=t["to_dative"], template_kind=t["kind"], short=t["short"], due=t["due"], offered_with=offered_with,
                **({"deadline": t["deadline"]} if t.get("deadline") else {}), **({"posted": True} if t.get("posted") else {}),
                **marked(held))
    brief = result.get("brief") or {}
    applying = [p for p in keypoints.evaluate(graph, state.get("facts") or {}) if not flagged.key_point(p["id"])] if graph and ev else []
    for i, q in enumerate(brief.get("questions") or []):  # the customer's own questions, answered by a key point where one matches
        point = keypoints.answer_for(q.get("question"), applying)
        add("customer_question", str(i), value=q.get("question"), stated_as="established", verdict=None, evidence=_evidence(q.get("citations")),
            node=None, origin="claim_reader", chain=False, label=q.get("question"),
            **({"answered_by": point["id"], "answer": keypoints.sentence(point)} if point else {}))
    needs = {re.split(r"\W+", str((i.get("label") or {}).get("de") or "").lower())[0] for i in items if i["kind"] == "document"}
    for i, doc in enumerate(brief.get("not_enclosed") or []):  # mentioned in the file but not in it: offered as such
        head = re.split(r"\W+", doc["title"].lower())[0]
        if head in needs and head not in GENERIC_TITLES:
            continue  # the same document is already a need of the process
        # practice: of ten such mentions in the development cuts Protekta asked one, so the default is offered, not ticked
        add("document", f"mention-{i}", value="missing", stated_as="established", verdict="accepted", evidence=_evidence(doc.get("citations")),
            node=None, origin="claim_reader", chain=True, label=doc["title"], status="missing", legal_basis=None, required="yes",
            ask="proposed", part_of=None, reason=f'{"in " + doc["mentioned"] + " " if doc.get("mentioned") else ""}erwähnt, lag nicht bei')
    for i, party in enumerate(brief.get("parties") or []):
        add("party", str(i), value=party.get("name"), stated_as="established", verdict=None, evidence=[], node=None, origin="claim_reader",
            chain=False, label=party.get("role"))
    for i, event in enumerate(brief.get("timeline") or []):
        add("timeline", str(i), value=f"{event.get('date') or ''} {event.get('event') or ''}".strip(), stated_as="established",
            verdict=None, evidence=_evidence(event.get("citations")), node=None, origin="claim_reader", chain=False, label=None)
    cut = set(result.get("fitted") or [])  # what fitting the report shortened: the screen says so ("gekürzt")
    for i, point in enumerate(result.get("open_points") or []):
        add("open_point", str(i), value=point if isinstance(point, str) else json.dumps(point, ensure_ascii=False), stated_as="put_to_handler",
            verdict=None, evidence=[], node=None, origin="result_checker", chain=False, label=None,
            **({"trimmed": True} if f"$.open_points[{i}]" in cut or (i == len(result["open_points"]) - 1 and "$.open_points" in cut) else {}))
    if result.get("answer"):
        add("answer", "0", value=result["answer"], stated_as="established", verdict=None, evidence=[], node=None, origin="result_checker",
            chain=False, label=None, **({"trimmed": True} if "$.answer" in cut else {}))
    if brief.get("request") or result.get("summary"):
        add("summary", "0", value=brief.get("request") or result.get("summary"), stated_as="established", verdict=None, evidence=[],
            node=None, origin="claim_reader", chain=False, label=None)
    for i, clause in enumerate((result.get("reply") or {}).get("clauses") or []):
        add("reply", str(i), value=clause.get("text") if isinstance(clause, dict) else clause, stated_as="established", verdict=None,
            evidence=_evidence((clause or {}).get("citations") if isinstance(clause, dict) else None), node=None, origin="result_checker",
            chain=False, label=None)
    for i in items:  # what the list and the card show never holds a placeholder (a date format, {…}, <…>)
        if i["kind"] in SHOWN_KINDS:
            for lang in ("de", "en"):
                if placeholder((i.get("label") or {}).get(lang)):
                    i["label"][lang] = plain(i["label"][lang]) or "Angabe klären"
            for field in ("value", "reason"):
                if isinstance(i.get(field), str) and placeholder(i[field]):
                    i[field] = plain(i[field]) or "Angabe klären"
    return items


SINCE = {"A1": "unserer Anforderung", "A4": "unserer Rückfrage", "A5": "unserer Einschätzung", "A6": "unserem Schreiben mit Frist",
         "A7": "unserer Statusanfrage", "A8": "unserem Schreiben an die Gegenpartei", "A9": "unserer Antwort an die Gegenpartei"}


def silent_since(graph, code):
    """What nobody answered, in words (never the action's code): «unserer Anforderung»."""
    return SINCE.get(code) or f"unserem Schreiben ({kind_title(graph, code)})"


def wahrt(events, deadline, template=None):
    """Whether «Frist wahren» went out for this deadline: its letter (A13) dispatched, and, where it has one, the template
    for the customer's own letter in the same approved version. A copy is not a dispatch."""
    from .completion import sent_letters
    for sent in sent_letters(events):
        if sent["form"] == "A13" and sent.get("deadline") in (None, deadline["item_id"]) \
                and (template is None or f"vorlage:{template['id']}" in sent["also"]):
            return True
    return False


def customer_line(row):
    """The incoming item as a letter to the customer may state it; None for a third party's statement about the customer
    (the firm's report that the customer does not cooperate): its words stay in «Der Fall» and the Verlauf."""
    return None if row["kind"].get("about_customer") else incoming.assessment_line(row)


SHOWN_KINDS = {"next_action", "key_point", "stage_line", "deadline", "contact", "check"}


def customer_name(result):
    """The insured person's name as the brief states it, or None."""
    from .letters import customer
    p = customer([{"label": x.get("role"), "value": x.get("name")} for x in ((result or {}).get("brief") or {}).get("parties") or ()])
    return (p or {}).get("value") or None


# The hash covers what an expert judges: item_id, kind, key, value, stated_as, and by kind
#   document: status, required, ask, part_of · fact: part · next_action: action · deadline: stated, rule
# It leaves out label, evidence, origin, verdict, node, chain, legal_basis and reason, which explain an assertion.
# The study's integrity check rests on this list: change it only with a new hash version.
HASHED = ("item_id", "kind", "key", "value", "stated_as", "status", "required", "ask", "part_of", "part", "action", "stated", "rule")


def items_sha256(items):
    rows = sorted([[i.get(k) for k in HASHED] for i in items], key=lambda r: r[0])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def short_label(item, titles=None):
    """An item as «Was sich geändert hat» names it: what came in by its kind's title (``titles``: {fact: title}), a fact
    by its question's first clause, nothing longer than 90 characters."""
    if item["kind"] == "fact" and (titles or {}).get(item["key"]):
        return titles[item["key"]]
    text = (item.get("label") or {}).get("de") or str(item.get("value") or item["key"])
    if item["kind"] == "fact":
        text = re.split(r"(?<=\?)\s|:\s|,\s|\s\(", text, maxsplit=1)[0]
    return text if len(text) <= 90 else text[:89].rstrip() + "…"


def item_changes(before, after, titles=None):
    """What a new preparation changed, item by item: added, changed (value, status or ask) and removed. Labels only, short
    (``titles``: what came in, by its kind's title)."""
    key = lambda i: (i.get("value"), i.get("status"), i.get("ask"))
    label = lambda i: short_label(i, titles)
    old, new = {i["item_id"]: i for i in before}, {i["item_id"]: i for i in after}
    shown = {"document", "fact", "next_action", "letter_question", "hint", "deadline"}
    return {"added": [label(new[k]) for k in new if k not in old and new[k]["kind"] in shown],
            "changed": [label(new[k]) for k in new if k in old and new[k]["kind"] in shown and key(new[k]) != key(old[k])],
            "removed": [label(old[k]) for k in old if k not in new and old[k]["kind"] in shown]}

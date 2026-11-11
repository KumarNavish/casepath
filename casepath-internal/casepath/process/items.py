"""The canonical item list: everything CasePath states about a case, built in one place.

What the Übersicht shows, what the letter asks, what exports and gold labels refer to, and the list's hash all come
from build_items. The browser only draws it. Model-free; the evaluator is used as it is.

Item ids are "<kind>:<key>". Fact, document, step and deadline keys are the process's own ids and stay stable across
reloads and re-evaluations; party, open_point, summary and reply keys are positions, valid within one run.
"""
import hashlib
import json
import re

from .workflows import evaluate_condition

CUSTOMER_ROLE = re.compile(r"^user", re.I)  # a step the customer answers in the online form or chat
DECISION_ROLE = re.compile(r"^entscheidung", re.I)
PERIOD = re.compile(r"\d{1,3} (days|weeks|months|years) (from|before) \d{4}-\d{2}-\d{2}")


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


def build_items(state, result):
    graph, ev, result = state.get("process"), state.get("evaluation"), result or {}
    items = []
    def add(kind, key, label=None, **fields):
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
            if ev.get("outcome") or row["status"] == "present":
                ask = None
            elif row["required"] == "yes" or (row["required"] == "depends" and not graph.get("action_by_stage") and not (d.get("edit") and not d.get("knowledge"))):
                ask = "now"  # in the handler's workflow a need whose condition nobody has established waits: it is asked later
            elif row["required"] == "depends":
                ask = "later"
            else:
                ask = None
            note = (found.get(row["document"]) or {}).get("note")
            add("document", row["document"], value=row["status"], stated_as="put_to_handler" if row["required"] == "depends" else "established",
                verdict=(found.get(row["document"]) or {}).get("verdict"), evidence=_evidence(row.get("citations")),
                node=row.get("step"), origin=_origin(d), chain=True, label=row["title"], status=row["status"],
                legal_basis=d.get("legal_basis") or row.get("legal_basis"),
                required=row["required"], ask=ask, part_of=part_of.get(row["document"]),
                reason=note if row["status"] in {"unusable", "missing"} and note else None,
                **({"partial": row["partial"]} if row.get("partial") else {}))
        definitions = {f["id"]: f for f in graph["facts"]}
        overrides, set_by_hand = state.get("overrides") or {}, (state.get("facts") or {})
        rows = {f["id"]: {"fact": f["id"], "status": "unknown", "value": None, "citations": []} for f in graph["facts"]}  # every fact the process asks about
        rows.update({f["fact"]: f for f in result.get("facts", [])})
        for key in overrides:  # a fact a case worker set shows the value set, whatever the run read
            rows[key] = {**rows.get(key, {"fact": key, "citations": []}), "status": "established", "value": set_by_hand.get(key),
                         "verdict": "set_by_handler", "by_edit": overrides[key]}
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
                label=definitions[fact["fact"]].get("question"), chat_only=fact["fact"] in customer, path=fact["fact"] in waiting,
                **({"part": fact["part"]} if fact.get("part") else {}))
        for d in result.get("deadlines", []):
            add("deadline", d["fact"], value=d["date"], stated_as="computed" if d.get("computed") else "established", verdict="accepted",
                evidence=[], node=_fact_node(graph, d["fact"]), origin="workflow", chain=True, label=d.get("question"),
                **({"stated": d["stated"], "rule": d["rule"]} if d.get("computed") else {}))
        asked = [i for i in items if i["kind"] == "document" and i["ask"] == "now"]
        lines = len([i for i in asked if not i["part_of"] or i["part_of"] not in {a["key"] for a in asked}])
        steps = {x["id"]: x for x in graph["steps"]}
        here = steps.get((ev.get("current") or {}).get("step")) or (steps.get(ev["path"][-1]["step"]) if ev.get("path") else None) or {}
        planned = here.get("action")  # the handler's workflow names the action each stage ends in
        if planned and not (planned.get("skip_if") and evaluate_condition(planned["skip_if"], state.get("facts") or {})):
            title = planned["title"]
            action = (planned["kind"], title, {"de": title, "en": title})
        elif planned:  # this stage's action was already taken: its follow-up comes next
            title = {"A6": "Dossier pendent halten mit Frist", "A7": "Statusanfrage mit Abschlussankündigung"}.get(planned.get("follow_up"), planned.get("follow_up"))
            action = (planned.get("follow_up"), title, {"de": title, "en": title})
        elif ev.get("outcome"):
            title = ev["outcome"].get("title") or ev["outcome"]["id"]
            action = ("close", title, {"de": f"Fall abschliessen: {title}", "en": f"Close the case: {title}"})
        elif asked:
            action = ("request", f"{lines} documents", {"de": f"{lines} Unterlage(n) beim Kunden anfordern", "en": f"Request {lines} document(s) from the customer"})
        elif ev.get("next_actions"):
            first = ev["next_actions"][0]
            action = ({"obtain": "request"}.get(first["kind"], first["kind"]), first["text"], first["text"])
        else:
            action = None
        if action:
            add("next_action", "0", **({"next_in_days": planned.get("next_in_days"), "follow_up": planned.get("follow_up")} if planned else {}), value=action[1], stated_as="established", verdict=None, evidence=[], node=(ev.get("current") or {}).get("step"),
                origin="workflow", chain=True, label=action[2], action=action[0])
        # The first request asks, besides documents, what only the customer can say, and gives the hints the law calls for.
        known = state.get("facts") or {}
        if planned and planned.get("kind") == "A1" and action and action[0] == "A1":
            for f in graph["facts"]:
                if f.get("ask_customer") and known.get(f["id"]) is None:
                    add("letter_question", f["id"], value=f["question"], stated_as="put_to_handler", verdict=None, evidence=[],
                        node=here.get("id"), origin="workflow", chain=True, label=f["question"])
            for hint in graph.get("hints", []):
                if evaluate_condition(hint["when"], known) is not True and hint["when"] is not True:
                    continue
                add("hint", hint["id"], value=hint["text"], stated_as="established", verdict=None, evidence=[], node=here.get("id"),
                    origin="workflow", chain=True, label=hint["text"], legal_basis=hint.get("legal_basis"))
            for hint in graph.get("hints", []):  # a hint whose condition is still open is offered too: Protekta gives it early
                if hint["when"] is not True and evaluate_condition(hint["when"], known) is None:
                    add("hint", hint["id"], value=hint["text"], stated_as="put_to_handler", verdict=None, evidence=[], node=here.get("id"),
                        origin="workflow", chain=True, label=hint["text"], legal_basis=hint.get("legal_basis"))
    brief = result.get("brief") or {}
    for i, party in enumerate(brief.get("parties") or []):
        add("party", str(i), value=party.get("name"), stated_as="established", verdict=None, evidence=[], node=None, origin="claim_reader",
            chain=False, label=party.get("role"))
    for i, event in enumerate(brief.get("timeline") or []):
        add("timeline", str(i), value=f"{event.get('date') or ''} {event.get('event') or ''}".strip(), stated_as="established",
            verdict=None, evidence=_evidence(event.get("citations")), node=None, origin="claim_reader", chain=False, label=None)
    for i, point in enumerate(result.get("open_points") or []):
        add("open_point", str(i), value=point if isinstance(point, str) else json.dumps(point, ensure_ascii=False), stated_as="put_to_handler",
            verdict=None, evidence=[], node=None, origin="result_checker", chain=False, label=None)
    if result.get("answer"):
        add("answer", "0", value=result["answer"], stated_as="established", verdict=None, evidence=[], node=None, origin="result_checker",
            chain=False, label=None)
    if brief.get("request") or result.get("summary"):
        add("summary", "0", value=brief.get("request") or result.get("summary"), stated_as="established", verdict=None, evidence=[],
            node=None, origin="claim_reader", chain=False, label=None)
    for i, clause in enumerate((result.get("reply") or {}).get("clauses") or []):
        add("reply", str(i), value=clause.get("text") if isinstance(clause, dict) else clause, stated_as="established", verdict=None,
            evidence=_evidence((clause or {}).get("citations") if isinstance(clause, dict) else None), node=None, origin="result_checker",
            chain=False, label=None)
    return items


# The hash covers what an expert judges: item_id, kind, key, value, stated_as, and by kind
#   document: status, required, ask, part_of · fact: part · next_action: action · deadline: stated, rule
# It leaves out label, evidence, origin, verdict, node, chain, legal_basis and reason, which explain an assertion.
# The study's integrity check rests on this list: change it only with a new hash version.
HASHED = ("item_id", "kind", "key", "value", "stated_as", "status", "required", "ask", "part_of", "part", "action", "stated", "rule")


def items_sha256(items):
    rows = sorted([[i.get(k) for k in HASHED] for i in items], key=lambda r: r[0])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()

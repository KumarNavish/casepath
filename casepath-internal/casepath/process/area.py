"""A handler's process for any legal area: one backbone and one small area module, composed at load time.

The backbone (areas/backbone.json) is what every legal-protection case shares: the stages, the action kinds A0–A12 and
which handler decisions each depends on, the handler's decisions (cover, way to proceed), the derived facts, the clock,
Protekta's letter forms, and what comes in from third parties with the action it calls for (incoming.py). An area module
(areas/<id>.json) holds only what differs: the routing value, the facts with their customer questions, the documents
with their legal reason and stage, first hints, statutory deadlines, the legal frame of the assessment letter (A5) and
of the letter to the other side (A8), and the law it cites. Composition yields an
ordinary workflow (casepath.workflow/1), so routing, evaluation, items and letters are unchanged.

Every article a module cites carries a short verbatim passage of the official text (at most 40 words) and says whether it
was checked against that text; a module that cites law without a passage is refused. Practice counts ("in n von 7
Dossiers") belong to the module that was observed in practice; for every other module the backbone's practice references
are generalised and its observed counts dropped.

    python -m casepath areas [<module.json or directory> …] [--law <fedlex html> …]
"""
import argparse
import copy
from datetime import date, timedelta
import functools
import html
import json
from pathlib import Path
import re
import sys

from . import cover, customer_letters, incoming, keypoints
from .clock import parse_date
from .workflows import FORMAT, CatalogueError, _check_condition as check_condition, evaluate_condition, validate_workflow

AREA_FORMAT, BACKBONE_FORMAT = "casepath.area/1", "casepath.backbone/1"
AREAS = Path(__file__).with_name("areas")
LABELS = {(True, "draft"): "aus Praxis und Gesetz abgeleitet, noch nicht freigegeben",
          (False, "draft"): "aus dem Gesetz abgeleitet, noch nicht freigegeben"}
MAX_PASSAGE_WORDS = 40
QUALIFIER = re.compile(r"\b(?:Abs|Ziff|lit|Bst)\.\s*\w+")
FEDLEX = "https://fedlex.data.admin.ch/filestore/"
COUNTING_UNITS = ("start", "days", "weeks", "months", "end")


@functools.lru_cache(maxsize=None)
def _shipped_laws():
    """The law table and counting rules of the shipped backbone (read once, without composing anything)."""
    bb = load(AREAS / "backbone.json")
    return bb["laws"], bb.get("counting", {})


def shorts(laws=None):
    """{short name: SR number} of a law table: «OR» → 220, «ATSG» → 830.1. A law without a short name is cited by SR."""
    return {row["short"]: sr for sr, row in (laws if laws is not None else _shipped_laws()[0]).items() if row.get("short")}


@functools.lru_cache(maxsize=None)
def _cite_pattern(names):
    return re.compile(r"Art\.\s+(\d[\w.\s,–-]*?)\s*(?:ff\.\s*)?\b(" + "|".join(re.escape(n) for n in names) + r")\b")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def cited_articles(text, laws=None):
    """{(SR number, article)} for every "Art. … <law>" in a text, for every law of the table by its short name:
    "Art. 257g, 259a OR" → 257g and 259a of SR 220; "Art. 38 Abs. 4 ATSG" → 38 of SR 830.1."""
    table = shorts(laws)
    out = set()
    for m in _cite_pattern(tuple(sorted(table, key=len, reverse=True))).finditer(text):
        for number in re.findall(r"\d+[a-z]*", QUALIFIER.sub(" ", m.group(1))):
            out.add((table[m.group(2)], number))
    return out


def check_laws(laws, where):
    """A law is any official federal text, identified by its SR number and, where it has one, its short name; its
    consolidated text is the fedlex filestore HTML the passages are checked against."""
    for sr, row in laws.items():
        if not re.fullmatch(r"\d{1,3}(?:\.\d+)*", sr) or not isinstance(row, dict):
            raise CatalogueError(f"{where}: law {sr!r} must be named by its SR number")
        if not str(row.get("title") or "").strip() or not str(row.get("url") or "").startswith(FEDLEX) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row.get("consolidation"))):
            raise CatalogueError(f"{where}: law SR {sr} needs its title, the consolidation date and the fedlex filestore url of its text")
        if "short" in row and not re.fullmatch(r"[A-Za-zÄÖÜäöü]{2,12}", str(row["short"])):
            raise CatalogueError(f"{where}: law SR {sr}: the short name is one word («OR», «ATSG»)")
    named = [row["short"] for row in laws.values() if row.get("short")]
    if len(named) != len(set(named)):
        raise CatalogueError(f"{where}: two laws share a short name")


def check_counting(counting, law, where="backbone"):
    """Each procedure's counting rules: for the start, days, weeks, months and the end on a Saturday, Sunday or holiday
    either a rule resting on verified passages of the law table, or no rule and the reason (then «prüfen», no date)."""
    for cid, rule in counting.items():
        if not re.fullmatch(r"[a-z][a-z-]*", cid) or not str(rule.get("title") or "").strip():
            raise CatalogueError(f"{where}: counting rule {cid!r} needs an id and a title")
        for part in COUNTING_UNITS + ("standstill", "ferien"):
            row = rule.get(part)
            if row is None and part in ("standstill", "ferien"):
                continue
            if not isinstance(row, dict) or not str(row.get("text") or "").strip():
                raise CatalogueError(f"{where}: counting rule {cid}: {part} needs its rule or its reason in words")
            keys = row.get("law", [])
            if (row.get("rule") or part in ("standstill", "ferien")) and not keys:
                raise CatalogueError(f"{where}: counting rule {cid}: {part} must rest on a verified passage")
            for key in keys:
                if (law.get(key) or {}).get("verified") is not True:
                    raise CatalogueError(f"{where}: counting rule {cid}: {part} names {key!r}, which is not a verified passage")
            for spec in row.get("periods", []):
                if not re.fullmatch(r"(easter[+-]\d+|\d{2}-\d{2}):(easter[+-]\d+|\d{2}-\d{2})", spec):
                    raise CatalogueError(f"{where}: counting rule {cid}: {part} period {spec!r} is not «from:to»")


def _check_law(entries, laws, where):
    for key, row in entries.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", key) or not isinstance(row, dict):
            raise CatalogueError(f"{where}: law entry {key!r} is malformed")
        for field in ("cite", "sr", "article", "passage"):
            if not str(row.get(field) or "").strip():
                raise CatalogueError(f"{where}: law entry {key!r} needs {field} (a cited article needs its verbatim passage)")
        if row["sr"] not in laws:
            raise CatalogueError(f"{where}: law entry {key!r} names SR {row['sr']}, which the backbone does not list")
        if len(row["passage"].split()) > MAX_PASSAGE_WORDS:
            raise CatalogueError(f"{where}: the passage of {key!r} is longer than {MAX_PASSAGE_WORDS} words")
        if not isinstance(row.get("verified"), bool):
            raise CatalogueError(f"{where}: law entry {key!r} must say verified true or false")


def validate_backbone(backbone):
    if not isinstance(backbone, dict) or backbone.get("format") != BACKBONE_FORMAT:
        raise CatalogueError(f"backbone format must be {BACKBONE_FORMAT}")
    for key in ("id", "version", "sources", "facts", "start", "steps", "outcomes", "clock", "forms", "action_kinds", "cooperation", "laws", "law",
                "deadline_margin_days"):
        if key not in backbone:
            raise CatalogueError(f"backbone is missing {key!r}")
    check_laws(backbone["laws"], "backbone")
    _check_law(backbone["law"], backbone["laws"], "backbone")
    check_counting(backbone.get("counting") or {}, backbone["law"])
    if "or" not in (backbone.get("counting") or {}):
        raise CatalogueError("backbone: the counting rules need «or», the default of every deadline")
    facts = {f["id"] for f in backbone["facts"]}
    steps = {s["id"] for s in backbone["steps"]}
    for f in backbone["facts"]:  # a handler's decision names the stages it belongs to: only there is it asked
        if "stages" in f and (not isinstance(f["stages"], list) or not f["stages"] or set(f["stages"]) - steps):
            raise CatalogueError(f"backbone: fact {f['id']!r}: stages must name stages of the backbone")
    for kind, row in backbone["action_kinds"].items():
        if not re.fullmatch(r"A\d{1,2}", kind) or any(f not in facts for f in row.get("depends_on", [])):
            raise CatalogueError(f"backbone: action kind {kind!r} must depend only on backbone facts")
    check_stage_work(backbone)
    keypoints.validate_lines(backbone, steps)
    from . import account, review
    account.validate(backbone)
    review.check_questions(backbone.get("open_questions"), review.backbone_ids(backbone), "backbone")
    check_forms(backbone["forms"])
    return incoming.validate(backbone)


def check_forms(forms, where="backbone"):
    """A form never renders empty: it has parts or says why there is no draft (``none``), and a form that names what it
    is for (``asks``: placeholders of its parts) says why there is no draft when none of them is filled (``empty``)."""
    for kind, form in forms.items():
        if kind.startswith("_"):
            continue
        if not form.get("none") and not form.get("parts"):
            raise CatalogueError(f"{where}: form {kind} needs parts or the reason it has no draft (none)")
        asks = form.get("asks")
        if asks is not None:
            named = {n for p in form.get("parts", []) for n in re.findall(r"\{([a-z_]+)\}", p)}
            if not asks or set(asks) - named or not str(form.get("empty") or "").strip():
                raise CatalogueError(f"{where}: form {kind} asks for placeholders of its parts and says why there is no draft without them (empty)")
        gaps = form.get("handler_gaps")  # the marked gaps the handler fills in (the reasons, the recommendation), by place
        if gaps is not None:
            parts = form.get("parts", [])
            named = {n for p in parts for n in re.findall(r"\{([a-z_]+)\}", p)} | {p[1:] for p in parts if p.startswith("@")}
            literal = lambda texts: all(f"[bitte ergänzen: {x}]" in "\n".join(parts) for x in texts)  # a gap the part itself holds
            if not isinstance(gaps, dict) or not gaps or not all(isinstance(v, list) and v and all(isinstance(x, str) and x for x in v) for v in gaps.values()) \
                    or any(k not in named and not literal(v) for k, v in gaps.items()):
                raise CatalogueError(f"{where}: form {kind} names its handler's gaps by its places (a placeholder or a part), each with the gap texts")


def check_stage_work(backbone):
    """Every stage yields something a handler can do: one of the action kinds (its follow-up and its variants too), or a
    handler's decision on an enum fact only the handler sets, with a form saying what is asked. A stage that can yield
    neither would show an unnamed step; it is refused."""
    kinds, forms = backbone["action_kinds"], backbone["forms"]
    facts = {f["id"]: f for f in backbone["facts"]}
    for step in backbone["steps"]:
        where = f"backbone: stage {step.get('id')!r}"
        action, decision = step.get("action"), step.get("decision")
        if action:
            named = [action.get("kind"), action.get("follow_up")] + [v.get("kind") for v in action.get("instead", [])]
            if any(k is not None and k not in kinds for k in named) or action.get("kind") is None or not action.get("title"):
                raise CatalogueError(f"{where}: its action, follow-up and variants must be action kinds of the backbone, with a title")
        elif decision:
            fact = facts.get(decision.get("fact")) or {}
            if not (fact.get("handler_only") and fact.get("type") == "enum" and decision.get("title") and decision.get("form") in forms):
                raise CatalogueError(f"{where}: a decision names an enum fact only the handler sets, its question and a form")
        else:
            raise CatalogueError(f"{where}: yields neither an action kind nor a handler's decision")
        for edge in step.get("next", []):
            if edge.get("without_action") and not action:
                raise CatalogueError(f"{where}: without_action on a stage that has no action")
    for rule in backbone["clock"]:
        if rule["then"] not in kinds or (rule.get("follow_up") and rule["follow_up"] not in kinds):
            raise CatalogueError(f"backbone: clock rule after {rule.get('after')} names an unknown action kind")


def _domain(fact):
    if fact["type"] == "boolean":
        return [True, False, None]
    if fact["type"] == "enum":
        return list(fact["values"]) + [None]
    return ["x", None]


def satisfiable(condition, facts):
    """Whether some values of the facts a condition names make it true (yes/no, an enum's values, known or not)."""
    from itertools import product
    from .workflows import condition_facts
    names = sorted(condition_facts(condition))
    named = {}

    def values(c):
        if isinstance(c, dict):
            for k in ("all", "any"):
                for child in c.get(k, ()):
                    values(child)
            if "not" in c:
                values(c["not"])
            if c.get("fact") and ("is" in c or "in" in c):
                named.setdefault(c["fact"], []).extend(c["in"] if "in" in c else [c["is"]])
    values(condition)
    domains = [_domain(facts[n]) + [v for v in named.get(n, []) if v not in _domain(facts[n])] for n in names]
    return any(evaluate_condition(condition, dict(zip(names, combo))) is True for combo in product(*domains))


def check_dead_ends(workflow):
    """No stage from which nothing leads on: every stage that is not an ending has a way out that some answer makes
    true, and an ending is reachable from every stage. With stages that require their action, a stage whose every way
    out needs its action yields that action (it always can: check_stage_work), and an incoming item is answered by the
    action prepared for it (incoming.validate). CatalogueError names the first dead end."""
    steps = {s["id"]: s for s in workflow["steps"]}
    facts = {f["id"]: f for f in workflow["facts"]}
    ends = {sid for sid, s in steps.items() if s.get("outcome")}
    for sid, step in steps.items():
        if sid in ends:
            continue
        ways = [e for e in step.get("next", []) if satisfiable(e.get("when", True), facts)]
        if not ways:
            raise CatalogueError(f"stage {sid!r} is a dead end: no way out can hold")
    leads = set(ends)
    changed = True
    while changed:
        changed = False
        for sid, step in steps.items():
            if sid not in leads and any(e["to"] in leads for e in step.get("next", [])):
                leads.add(sid)
                changed = True
    stuck = sorted(set(steps) - leads)
    if stuck:
        raise CatalogueError(f"no ending can be reached from: {', '.join(stuck)}")
    return workflow


def validate_module(module, backbone):
    """Fail closed on a module the backbone cannot carry, and on any law cited without its verbatim passage."""
    if not isinstance(module, dict) or module.get("format") != AREA_FORMAT:
        raise CatalogueError(f"area module format must be {AREA_FORMAT}")
    where = f"area {module.get('id')}"
    for key in ("id", "version", "backbone", "short_title", "title", "status", "sources", "law", "facts", "documents", "hints",
                "assessment", "deadlines"):
        if key not in module:
            raise CatalogueError(f"{where}: missing {key!r}")
    if module["status"] not in {"draft", "reviewed"} or not 2 <= len(module["short_title"]) <= 40:
        raise CatalogueError(f"{where}: status must be draft or reviewed and short_title 2 to 40 characters")
    if not module.get("fallback") and not module.get("applies_when"):
        raise CatalogueError(f"{where}: a module needs applies_when (or is the fallback)")
    laws = {**backbone["laws"], **module.get("laws", {})}  # a module may add a federal text to the table
    check_laws(module.get("laws", {}), where)
    _check_law(module["law"], laws, where)
    law = {**backbone["law"], **module["law"]}
    have = {(row["sr"], row["article"]) for row in law.values()}
    body = {k: v for k, v in module.items() if k not in {"law", "sources", "format"}}
    for text in _strings(body):
        for ref in re.findall(r"\blaw#([\w.-]+)", text):
            if ref not in module["law"]:
                raise CatalogueError(f"{where}: law#{ref} is cited without a law entry and its passage")
        for sr, article in cited_articles(text, laws):
            if (sr, article) not in have:
                raise CatalogueError(f"{where}: Art. {article} {laws[sr].get('short') or 'SR ' + sr} is cited without a law entry "
                                     f"and its passage: {text[:80]!r}")
    if not module.get("practice") and re.search(r"\d+\s*(?:von|of)\s*\d+|\d+of\d+", json.dumps(body, ensure_ascii=False)):
        raise CatalogueError(f"{where}: practice counts belong only to a module observed in practice")
    facts = {f["id"]: f for f in module["facts"]}
    for f in module["facts"]:  # the nearest thing that does not count as the fact: one line the reader and checker are given
        if "not_this" in f and not (isinstance(f["not_this"], str) and 10 <= len(f["not_this"].strip()) <= 300):
            raise CatalogueError(f"{where}: fact {f['id']}: not_this is one line of 10 to 300 characters")
    if set(facts) & {f["id"] for f in backbone["facts"]}:
        raise CatalogueError(f"{where}: a fact repeats a backbone fact")
    stages = {s["id"] for s in backbone["steps"]}
    for document in module["documents"]:
        if document.get("stage", "klaeren") not in stages:
            raise CatalogueError(f"{where}: document {document.get('id')} names an unknown stage")
    if any(d not in {x.get("id") for x in module["documents"]} for d in module.get("assess_needs", [])):
        raise CatalogueError(f"{where}: assess_needs names a document the module does not have")
    for stage in module.get("stages", {}):
        if stage not in stages:
            raise CatalogueError(f"{where}: unknown stage {stage!r}")
    keypoints.validate(module, law, where, stages)  # a key point needs a condition, an article with its passage and a statement
    # a letter the customer sends in his own name: a condition, an article with its passage for every legal statement, and no
    # instruction the cited law does not support
    customer_letters.validate(module, law, where, set(facts) | {f["id"] for f in backbone["facts"]})
    for part in ("rights", "conditions", "demand"):
        if not str((module["assessment"].get(part) or {}).get("text") or "").strip():
            raise CatalogueError(f"{where}: the assessment needs {part}")
    for d in module["deadlines"]:
        if d.get("party") not in {"kunde", "gegenpartei"}:
            raise CatalogueError(f"{where}: deadline {d.get('id')} must say who must act (party kunde or gegenpartei)")
        if d.get("when") and not d.get("when_text"):
            raise CatalogueError(f"{where}: deadline {d.get('id')} needs its condition in words (when_text)")
        for field in ("id", "title", "trigger", "period", "basis", "missed", "question", "source_refs"):
            if not d.get(field):
                raise CatalogueError(f"{where}: deadline {d.get('id')} needs {field}")
        if (facts.get(d["trigger"]) or {}).get("type") != "date":
            raise CatalogueError(f"{where}: deadline {d['id']} needs a date fact of this module as its trigger")
        if d.get("period_from") and (facts.get(d["period_from"]) or {}).get("type") != "text":
            raise CatalogueError(f"{where}: deadline {d['id']}: period_from names a text fact of this module (the agreed period)")
        counting = d.get("counting", "or")
        if counting not in (backbone.get("counting") or {}):
            raise CatalogueError(f"{where}: deadline {d['id']} names an unknown counting rule {counting!r}")
        if d["id"] in facts or not (cited_articles(d["basis"], laws) or counting == "kantonal"):
            raise CatalogueError(f"{where}: deadline {d['id']} needs its own id and an article as its basis (a cantonal period: its basis in words)")
        period = d["period"]
        if not (period in ("sofort", "kantonal") or (isinstance(period, dict) and len(period) == 1
                                                     and next(iter(period)) in {"days", "weeks", "months", "years", "days_before"})):
            raise CatalogueError(f"{where}: deadline {d['id']} has an unknown period")
        if (period == "kantonal") != (counting == "kantonal") and period != "sofort":
            raise CatalogueError(f"{where}: deadline {d['id']}: a cantonal period is counted by the cantonal rule, and only it")
    from . import review  # an open question attached to an element names one the jurist reviews
    review.check_questions(module.get("open_questions"), review.module_ids(module), where, whole=True)
    return module


def compose(backbone, module):
    """The module's workflow in the ordinary format: the backbone's stages and forms, the module's content."""
    validate_backbone(backbone)
    validate_module(module, backbone)
    bb, m = copy.deepcopy(backbone), copy.deepcopy(module)
    practice = bool(m.get("practice"))
    if not practice:  # the chain of actions applies here, but no case of this area was observed: no counts
        general = bb["practice_elsewhere"]

        def generalise(value):
            if isinstance(value, str):
                return re.sub(r"\bpractice#\S+", general["ref"], value)
            if isinstance(value, list):
                return [generalise(v) for v in value]
            if isinstance(value, dict):
                return {k: generalise(v) for k, v in value.items() if not (k == "note" and re.search(r"\d+ von \d+", str(v)))}
            return value
        bb = {**generalise({k: v for k, v in bb.items() if k != "sources"}),
              "sources": [{**s, "title": general["title"]} if s["id"] == "practice" else s for s in bb["sources"]]}
    stages = m.get("stages", {})
    steps = []
    for step in bb["steps"]:
        extra = stages.get(step["id"], {})
        steps.append({**step, "source_refs": step["source_refs"] + extra.get("source_refs", []),
                      "documents": [d["id"] for d in m["documents"] if d.get("stage", "klaeren") == step["id"]],
                      **({"suggestions": extra["suggestions"]} if extra.get("suggestions") else {})})
    facts = m["facts"]
    set_dates = bb.get("set_dates") or {}
    for f in facts:  # the question about a running deadline also carries a date others set: what is due, who set it, where
        if f.get("deadline") and set_dates.get("question"):
            f["question"] = f"{f['question'].rstrip()} {set_dates['question']}"
    for d in m["deadlines"]:  # an open trigger date is a question in the first request
        trigger = next(f for f in facts if f["id"] == d["trigger"])
        trigger.setdefault("ask_customer", True)
        trigger.setdefault("customer_question", d["question"])
    facts = bb["facts"] + facts + cover.facts_for(m)  # the cover points' facts, in every area (cover.py)
    if m.get("fact_order"):
        order = {fid: i for i, fid in enumerate(m["fact_order"])}
        facts.sort(key=lambda f: order.get(f["id"], len(order)))
    hints = list(m["hints"])  # while a trigger date is not in the file, the first request says a deadline may be running
    for trigger in dict.fromkeys(d["trigger"] for d in m["deadlines"] if d.get("hint", True)):
        group = [d for d in m["deadlines"] if d["trigger"] == trigger and d.get("hint", True)]
        whens = [d["when"] for d in group if d.get("when")]
        unknown = {"fact": trigger, "known": False}
        hints.append({"id": f"frist-{group[0]['id']}", "trigger": trigger,
                      "when": {"all": [unknown, whens[0] if len(whens) == 1 else {"any": whens}]} if len(whens) == len(group) else unknown,
                      "text": "Möglicherweise läuft eine gesetzliche Frist: " + "; ".join(f"{d['title']}, {period_text(d)}" for d in group)
                              + f". {group[0]['missed']}",
                      "legal_basis": ", ".join(dict.fromkeys(d["basis"] for d in group)),
                      "source_refs": list(dict.fromkeys(r for d in group for r in d["source_refs"]))})
    forms = {**bb["forms"], **cover.forms(), **copy.deepcopy(m.get("forms") or {})}  # a module may add or adapt a form
    for kind, form in forms.items():  # each form names the handler decisions its action waits for (the screen's draft.needs)
        if kind in bb["action_kinds"]:
            form["needs"] = list(bb["action_kinds"][kind]["depends_on"])
        if "parts" in form:
            # a part of the module's assessment that leaves a gap for the handler (the legal basis in the general area) declares it
            own = {p[1:]: m["assessment"][p[1:]]["handler_gaps"] for p in form["parts"] if p.startswith("@") and m["assessment"][p[1:]].get("handler_gaps")}
            if own:
                form["handler_gaps"] = {**(form.get("handler_gaps") or {}), **own}
            form["parts"] = [m["assessment"][p[1:]]["text"] if p.startswith("@") else p for p in form["parts"]]
    try:
        check_forms(forms, "forms")  # every form of the area, the cover's and the module's too, never renders empty
        cover.check_forms(forms)  # a part the law or the conditions require stays in its form
    except CatalogueError as error:
        raise CatalogueError(f"area {m['id']}: {error}") from error
    version = m["version"] if m["backbone"] == bb["version"] else f"{m['version']}+{bb['version']}"
    workflow = {"format": FORMAT, "id": m["id"], "version": version, "title": m["title"], "short_title": m["short_title"],
                "status": m["status"],
                "area": {"id": m["id"], "short_title": m["short_title"], "status": m["status"], "practice": practice,
                         "label": LABELS.get((practice, m["status"]), "freigegeben"), "backbone": bb["version"]},
                **{k: m[k] for k in ("supersedes", "builds_on", "fallback", "applies_when") if k in m},
                "sources": bb["sources"] + m["sources"] + cover.sources(), "facts": facts, "start": bb["start"], "steps": steps,
                # an open-ended need partly in the file: practice says whether it is asked again; from the law alone it is offered
                "documents": [{**{k: v for k, v in d.items() if k != "stage"},
                               **({"when_partly_present": "offer"} if not practice and "when_partly_present" not in d and open_ended_title(d["title"]) else {})}
                              for d in m["documents"]],
                "outcomes": bb["outcomes"], "hints": hints,
                **{k: m.get(k, []) for k in ("notes", "summary")},
                # an open question about one element (``about``) is the jurist's, shown where the element is reviewed
                # (review.py); the case's process carries the area's own
                "open_questions": [q for q in m.get("open_questions", []) if "about" not in q],
                "clock": bb["clock"], "forms": forms, "action_kinds": bb["action_kinds"], "cooperation": bb["cooperation"], "deadline_margin_days": bb.get("deadline_margin_days", 7),
                "floor": {"actions": {k[1:]: v["stage"] for k, v in bb["action_kinds"].items() if v.get("stage")},
                          "decisions": bb.get("floor_decisions", [])},
                "assess_needs": m.get("assess_needs", []),
                "key_points": m.get("key_points", []),  # what a specialist looks for first (keypoints.py)
                "customer_letters": m.get("customer_letters", []),  # templates the customer sends in his own name (customer_letters.py)
                "stage_lines": bb.get("stage_lines", []),  # the short facts a handler needs at a later stage (keypoints.py)
                "record": bb.get("record"),  # the running account's closed lists: parties and kinds of step (account.py)
                # each deadline carries the counting rule of its procedure (the backbone's table), so a stored run keeps it
                "deadlines": [{**d, "counting": d.get("counting", "or"), "counting_rule": bb["counting"][d.get("counting", "or")]} for d in m["deadlines"]],
                "stage_actions": True,  # a stage with an action is left only once it is done or a way out says it is not needed
                "incoming": bb.get("incoming", []), "incoming_done": bb.get("incoming_done"),
                # the stages whose own action, while due, leads over an open incoming item (incoming.py)
                "incoming_lead": (bb.get("incoming_lead") or {}).get("stages", []),
                "settled": {"when": m.get("settled_when"), "claims_open_when": m.get("claims_open_when")},
                "law": {**{k: v for k, v in bb["law"].items()}, **m["law"]}, "laws": {**bb["laws"], **m.get("laws", {})}}
    try:
        validate_workflow(workflow)
        check_dead_ends(workflow)
        known = {f["id"]: f for f in workflow["facts"]}
        for key, condition in workflow["settled"].items():
            check_condition(condition, known, f"{key.replace('when', 'settled_when') if key == 'when' else key}")
        for point in workflow["key_points"]:
            check_condition(point["when"], known, f"key point {point['id']}")
        return workflow
    except CatalogueError as error:
        raise CatalogueError(f"area {m['id']}: {error}") from error


def open_ended_title(title):
    """A need for all of something ("Sämtliche Korrespondenz …"), by its first word, as casegraph.open_ended reads it."""
    return (re.findall(r"[A-Za-zÄÖÜäöüß]+", title) or [""])[0].lower() in {"sämtliche", "sämtlichen", "alle", "bisherige", "bisherigen"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _shipped():
    backbone = validate_backbone(load(AREAS / "backbone.json"))
    rows = []
    for path in sorted(AREAS.glob("*.json")):
        if path.name != "backbone.json":
            try:
                module = load(path)
                if module.get("format") == cover.COVER_FORMAT:  # the cover points (cover.py), not an area
                    continue
                rows.append(compose(backbone, module))
            except (CatalogueError, json.JSONDecodeError) as error:
                raise CatalogueError(f"{path.name}: {error}") from error
    return backbone, tuple(rows)


def backbone():
    return copy.deepcopy(_shipped()[0])


def shipped():
    """Every shipped area, composed: a fresh copy each call."""
    return [copy.deepcopy(w) for w in _shipped()[1]]


def workflow(workflow_id):
    return next((w for w in shipped() if w["id"] == workflow_id), None)


# Statutory deadlines -------------------------------------------------------------------------------------------------

def period_text(d):
    p = d["period"]
    if p == "sofort":
        return f"sofort {d.get('from', '')}".strip()
    if p == "kantonal":
        return f"innert der Frist nach kantonalem Recht {d.get('from', '')}".strip()
    unit, n = next(iter(p.items()))
    if unit == "days_before":
        return f"spätestens {n} Tage vor {d.get('from', '')}".strip()
    if n == 0:
        return d.get("from", "")
    word = {"days": ("Tag", "Tagen"), "weeks": ("Woche", "Wochen"), "months": ("Monat", "Monaten"), "years": ("Jahr", "Jahren")}[unit]
    return f"{'ab' if d.get('direction') == 'ab' else 'innert'} {n} {word[n != 1]} {d.get('from', '')}".strip()


def _add_months(start, months):
    """Art. 77 Abs. 1 Ziff. 3 OR: the day of the last month with the same number, or that month's last day."""
    year, month = start.year + (start.month - 1 + months) // 12, (start.month - 1 + months) % 12 + 1
    last = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(start.day, last))


NUMBERS = {"ein": 1, "eine": 1, "einem": 1, "einen": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
           "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "vierzehn": 14, "zwanzig": 20, "dreissig": 30, "sechzig": 60, "neunzig": 90}
UNITS = {"tag": "days", "woche": "weeks", "monat": "months", "jahr": "years"}


def agreed_period(text):
    """An agreed period in words ("sechs Wochen", "3 Monate", "einem Monat") as a period {unit: n}; None when it does not
    name exactly one number and one unit."""
    found = re.findall(r"(\d{1,3}|[a-zäöü]+)\s+(tag|woche|monat|jahr)\w*", str(text).lower())
    found = [(int(n) if n.isdigit() else NUMBERS.get(n), unit) for n, unit in found]
    found = [(n, u) for n, u in found if n]
    return {UNITS[found[0][1]]: found[0][0]} if len(found) == 1 else None


SET_DATE = re.compile(r"\s*(\d{4}-\d{2}-\d{2})\s*(?:·\s*(.*))?", re.S)


def set_date(value):
    """A date a court, an authority or the other side set for the customer, as a deadline fact records it:
    «2025-04-23 · Schlichtungsverhandlung · Schlichtungsbehörde Bern · Vorladung» → {date, what, by, source}; a bare date
    gives only the date. None for anything else (a stated period, «none»)."""
    m = SET_DATE.fullmatch(str(value or ""))
    if not m:
        return None
    parts = [p.strip() for p in (m.group(2) or "").split("·")] + ["", "", ""]
    return {"date": m.group(1), "what": parts[0] or None, "by": parts[1] or None, "source": parts[2] or None}


STATED_PERIOD = re.compile(r"(\d{1,3}) (days|weeks|months|years) (from|before) (\d{4}-\d{2}-\d{2})")


def statutory_period(deadlines, value):
    """The area's statutory deadline a recorded period restates ("1 years from 2026-05-31" for a deadline of one year), or
    None. Such a period is the law's, even when a file quotes the law: the area computes it as its own item from the
    trigger date, so it is never a reading of the deadline fact (and never a rejected one)."""
    m = STATED_PERIOD.fullmatch(str(value or "").strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return next((d for d in deadlines or () if isinstance(d.get("period"), dict) and d["period"].get(unit) == n), None)


def easter(year):
    """Easter Sunday of the Gregorian calendar (the anonymous Gregorian computus)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def _point(spec, year):
    if spec.startswith("easter"):
        return easter(year) + timedelta(days=int(spec[6:]))
    month, day = spec.split("-")
    return date(year, int(month), int(day))


def in_periods(day, specs):
    """Whether a day lies in one of the periods «from:to» (both included; «easter-7», «12-18:01-02» spans the new year)."""
    for spec in specs or ():
        a, b = spec.split(":")
        for year in (day.year - 1, day.year):
            start, end = _point(a, year), _point(b, year)
            if end < start:
                end = _point(b, year + 1)
            if start <= day <= end:
                return True
    return False


FEDERAL_HOLIDAYS = ("08-01",)  # Art. 110 Abs. 3 BV: a holiday in every canton
# Days that are public holidays in many cantons, by date and by their distance from Easter Sunday. Not taken from a
# verified text (cantonal law); a jurist reviews the list (review.py, «Fristberechnung»).
CANTONAL_DAYS = {"01-01": "1. Januar", "01-02": "2. Januar", "05-01": "1. Mai", "08-15": "15. August", "11-01": "1. November",
                 "12-08": "8. Dezember", "12-25": "25. Dezember", "12-26": "26. Dezember"}
CANTONAL_EASTER = {-2: "Karfreitag", 1: "Ostermontag", 39: "Auffahrt", 50: "Pfingstmontag"}


def maybe_cantonal_holiday(day):
    """A day that is a public holiday in many cantons (New Year, 2 January, Good Friday, Easter Monday, Ascension, Whit
    Monday, 1 May, 15 August, 1 November, 8 December, Christmas, 26 December). The cantonal holidays are not in the
    verified texts: a deadline ending on such a day is not given a date, it says «prüfen»."""
    e = easter(day.year)
    return day.strftime("%m-%d") in CANTONAL_DAYS or day in {e + timedelta(days=k) for k in CANTONAL_EASTER}


def counting_rule(d):
    """The counting rules of the deadline's procedure: carried by a composed deadline, else the shipped table's."""
    return d.get("counting_rule") or _shipped_laws()[1].get(d.get("counting", "or")) or _shipped_laws()[1]["or"]


def _off(day, end_rule, statutory=True):
    """Whether the last day moves on: a Saturday, Sunday or federal holiday as the procedure's end rule names them."""
    days = set(end_rule.get("days", ()))
    if end_rule.get("saturday_if") == "statutory" and statutory:
        days.add("saturday")
    return (day.weekday() == 5 and "saturday" in days) or (day.weekday() == 6 and "sunday" in days) or \
        ("holiday" in days and day.strftime("%m-%d") in FEDERAL_HOLIDAYS)


def compute_deadline(d, trigger_value, facts=None):
    """(value, rule) for one statutory deadline: an ISO date, or "prüfen" with the reason. None when its condition fails.

    Computed only as the verified texts of its procedure state it (counting rules in the backbone, ``counting``: «or»
    for the Code of Obligations and what refers to it, «atsg», «stpo», «zpo», «schkg» …): when the period starts, how
    days, weeks and months are counted, what happens when the last day is a Saturday, Sunday or the federal holiday,
    whether the period stands still during court holidays and whether the debt-enforcement holidays extend it. Where the
    procedure's text gives no rule (a month under the ZPO, any period of the fine procedure, a cantonal period) the
    deadline says «prüfen» with the reason, and so does a last day that is a public holiday in many cantons: cantonal
    holidays are not in the verified texts."""
    condition = d.get("when")
    holds = evaluate_condition(condition, facts or {}) if condition else True
    if holds is False:
        return None
    rule = counting_rule(d)
    raw = str(trigger_value or "")
    start = parse_date(raw) if re.fullmatch(r"\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\s*", raw) else None
    notes = []
    if holds is None:
        notes.append("gilt nur unter einer noch offenen Voraussetzung, prüfen")
    period = d["period"]
    if start is None:
        return "prüfen", "; ".join([f"Auslöser «{raw}» ohne genaues Datum, prüfen"] + notes)
    shown = start.strftime("%d.%m.%Y")
    show = lambda day: day.strftime("%d.%m.%Y")
    pruefen = lambda why: ("prüfen", "; ".join([why] + notes + ([d["check"]] if d.get("check") else [])))
    agreed = (facts or {}).get(d["period_from"]) if d.get("period_from") else None
    statutory = True
    if agreed not in (None, ""):  # a period the parties agreed or an authority stated governs instead of the default
        period, label = agreed_period(agreed), d.get("period_from_label", "vereinbarte Frist")
        if period is None:
            return "prüfen", "; ".join([f"{label} «{agreed}» ab {shown}: Dauer prüfen"] + notes)
        notes.append(f"{label} «{agreed}»")
        statutory = bool(d.get("period_from_statutory"))  # an agreed period is no statutory one (Art. 1 SR 173.110.3)
    if period == "sofort":
        return "prüfen", "; ".join([f"«sofort» ab {shown}: kein festes Datum, prüfen"] + notes)
    if period == "kantonal" or not rule["start"].get("rule"):
        return pruefen(f"ab {shown}: {rule['start']['text']}")
    unit, n = next(iter(period.items()))
    if unit == "days_before":
        return "prüfen", "; ".join([f"spätestens {n} Tage vor dem {shown}: Rückwärtsrechnung prüfen"] + notes)
    kind = {"days": "days", "weeks": "weeks", "months": "months", "years": "months"}[unit]
    if not rule[kind].get("rule"):
        return pruefen(f"{period_text({**d, 'period': {unit: n}, 'direction': 'bis'})} ab {shown}: {rule[kind]['text']}")
    ferien = rule.get("ferien") or {}
    if d.get("served") and ferien and (in_periods(start, ferien["periods"]) or start.weekday() == 6 or start.strftime("%m-%d") in FEDERAL_HOLIDAYS
                                       or maybe_cantonal_holiday(start)):
        return pruefen(f"zugestellt am {shown}, in den Betreibungsferien, an einem Sonntag oder Feiertag (Art. 56 SchKG): Wirkung der Zustellung und Fristbeginn prüfen")
    still = (rule.get("standstill") or {}).get("periods") or []
    if n == 0:
        end = start
        notes.insert(0, f"am {shown}")
    elif kind == "days":
        if still:  # the days of the standstill are not counted; served during it, the period starts after it (Art. 146 ZPO)
            end, left = start, n
            while left:
                end += timedelta(days=1)
                if not in_periods(end, still):
                    left -= 1
            notes.insert(0, f"{n} Tage ab {shown}, {rule['start']['text']}; {rule['standstill']['text']}")
        else:
            end = start + timedelta(days=n)
            notes.insert(0, f"{n} Tage ab {shown}, {rule['start']['text']}")
    elif still and any(in_periods(start + timedelta(days=k), still) for k in range(1, (_add_months(start, n * (12 if unit == "years" else 1)) - start).days + 1 if kind == "months" else 7 * n + 1)):
        return pruefen(f"{period_text({**d, 'period': {unit: n}, 'direction': 'bis'})} ab {shown} über einen Fristenstillstand: Berechnung prüfen ({rule['standstill']['text']})")
    elif kind == "weeks":
        end = start + timedelta(days=7 * n)
        notes.insert(0, f"{n} Wochen ab {shown}: {rule['weeks']['text']}")
    else:
        end = _add_months(start, n * (12 if unit == "years" else 1))
        word = {"years": ("Jahr", "Jahre"), "months": ("Monat", "Monate")}[unit][n != 1]
        notes.insert(0, f"{n} {word} ab {shown}: {rule['months']['text']}")
    end_rule = rule["end"]
    if not end_rule.get("rule"):
        return pruefen(f"letzter Tag {show(end)}: {end_rule['text']}")
    if d.get("shift", True) and d.get("direction", "bis") == "bis":
        moved = end
        while _off(moved, end_rule, statutory):
            moved += timedelta(days=1)
        if moved != end:
            notes.append(f"{show(end)} ist {'ein Samstag' if end.weekday() == 5 else 'ein Sonntag' if end.weekday() == 6 else 'der Bundesfeiertag'}: "
                         f"{end_rule['text']}")
            if still and in_periods(moved, still):
                return pruefen(f"letzter Tag {show(end)}, der nächste Werktag {show(moved)} liegt im Fristenstillstand: prüfen")
            end = moved
        elif end.weekday() == 5 and not statutory:
            return pruefen(f"vereinbarte Frist endet am Samstag {show(end)}: Art. 1 SR 173.110.3 gilt für gesetzliche und behördliche Fristen, prüfen")
        if ferien and in_periods(end, ferien["periods"]):  # Art. 63 SchKG: to the third working day after the holidays
            last = end
            while in_periods(last + timedelta(days=1), ferien["periods"]):
                last += timedelta(days=1)
            extended, left = last, ferien["extend_working_days"]
            while left:
                extended += timedelta(days=1)
                if maybe_cantonal_holiday(extended):
                    return pruefen(f"letzter Tag {show(end)} in den Betreibungsferien bis {show(last)}; die drei Werktage danach umfassen "
                                   f"den {show(extended)}, in vielen Kantonen ein Feiertag (Art. 63 SchKG): prüfen")
                if extended.weekday() < 5 and extended.strftime("%m-%d") not in FEDERAL_HOLIDAYS:
                    left -= 1
            notes.append(f"{show(end)} in den Betreibungsferien bis {show(last)}: {ferien['text']}")
            end = extended
        if maybe_cantonal_holiday(end):
            return pruefen(f"letzter Tag nach der Berechnung {show(end)}, in vielen Kantonen ein Feiertag: kantonales Recht prüfen")
    elif end.weekday() >= 5 or end.strftime("%m-%d") in FEDERAL_HOLIDAYS:
        notes.append("fällt auf ein Wochenende, prüfen" if end.weekday() >= 5 else "fällt auf den Bundesfeiertag, prüfen")
    if d.get("direction", "bis") == "bis":
        notes.append("kantonale Feiertage nicht berücksichtigt")
    if d.get("check"):
        notes.append(d["check"])
    return end.isoformat(), "; ".join(notes)


# The command line ----------------------------------------------------------------------------------------------------

def citations(workflow_or_module):
    rows = list((workflow_or_module.get("law") or {}).values())
    return sum(1 for r in rows if r.get("verified")), sum(1 for r in rows if not r.get("verified"))


def describe(workflow):
    a = workflow.get("area") or {}
    ok, unchecked = citations(workflow)
    lines = [f"{workflow['id']} {workflow['version']} · {a.get('short_title')} · {a.get('label')}"
             + (" · Auffangprozess" if workflow.get("fallback") else ""),
             f"  Weg: {json.dumps(workflow.get('applies_when'), ensure_ascii=False)}"
             + (f" · ersetzt {', '.join(workflow['supersedes'])}" if workflow.get("supersedes") else "")
             + (f" · baut auf {', '.join(workflow['builds_on'])}" if workflow.get("builds_on") else "")]
    own = [f for f in workflow["facts"] if f["id"] not in {x["id"] for x in backbone()["facts"]}]
    lines.append(f"  {len(own)} Fakten, davon gefragt: " + "; ".join(f.get("customer_question") or f["question"] for f in own if f.get("ask_customer")))
    lines.append(f"  {len(workflow['documents'])} Unterlagen: " + "; ".join(d["title"] for d in workflow["documents"]))
    lines.append(f"  {len(workflow['hints'])} Hinweise, {len(workflow.get('deadlines', []))} Fristen: "
                 + "; ".join(f"{d['title']} ({d['basis']})" for d in workflow.get("deadlines", [])))
    points = workflow.get("key_points") or []
    lines.append(f"  {len(points)} Kernpunkte: " + "; ".join(f"{p['statement']} ({(workflow['law'].get(str(p['law'][0]).split('#')[-1]) or {}).get('cite')})" for p in points))
    lines.append(f"  Zitate: {ok} am amtlichen Text geprüft, {unchecked} nicht geprüft"
                 + (": " + ", ".join(r["cite"] for r in workflow["law"].values() if not r.get("verified")) if unchecked else ""))
    return lines


def official_articles(path):
    """{article: text} from a fedlex consolidated text in HTML (its filestore manifestation)."""
    out = {}
    for m in re.finditer(r'<article id="art_([^"]+)"(.*?)</article>', Path(path).read_text(encoding="utf-8"), re.S):
        body = re.sub(r"<sup[^>]*>.*?</sup>|<div class=\"footnotes\">.*", " ", m.group(2), flags=re.S)
        body = re.sub(r"<(?:p|div|dt|dd|li|br|h\d|td|tr)\b[^>]*>|</(?:p|div|dt|dd|li|h\d|td|tr)>", " ", body)  # blocks part words
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", "", body)).split())  # inline tags (Art. 270<i>b</i>) do not
        out[m.group(1).replace("_", "")] = re.sub(r" ([,;.:])", r"\1", text)  # a footnote mark leaves a space before a comma
    return out


def verify(module, texts):
    """Each law entry whose passage occurs word for word in its article of the official text: {key: True|False}."""
    return {key: " ".join(row["passage"].split()) in (texts.get(row["sr"]) or {}).get(row["article"], "")
            for key, row in module["law"].items() if row["sr"] in texts}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m casepath areas", description="validate area modules and show what they contain")
    parser.add_argument("paths", nargs="*", help="area module files or directories (default: the shipped areas)")
    parser.add_argument("--law", nargs="*", default=[], metavar="SR=FILE",
                        help="check every passage against an official text, e.g. 220=or.html (fedlex filestore HTML)")
    parser.add_argument("--sources", metavar="FOLDER",
                        help="check every passage against the saved official texts in a folder laid out as the law table's «file» entries")
    args = parser.parse_args(argv)
    try:
        bb = backbone()
        files = [p for x in args.paths for p in (sorted(Path(x).glob("*.json")) if Path(x).is_dir() else [Path(x)])
                 if p.name != "backbone.json"] or sorted(p for p in AREAS.glob("*.json") if p.name != "backbone.json")
        texts = {sr: official_articles(f) for sr, f in (x.split("=", 1) for x in args.law)}
        if args.sources:
            texts.update({sr: official_articles(Path(args.sources) / row["file"]) for sr, row in bb["laws"].items()
                          if row.get("file") and (Path(args.sources) / row["file"]).is_file()})
            found = verify(bb, texts)
            wrong = [k for k, ok in found.items() if ok != bb["law"][k]["verified"]]
            print(f"Gesetzestabelle: {len(bb['laws'])} Erlasse ({', '.join(r.get('short') or 'SR ' + sr for sr, r in bb['laws'].items())}); "
                  f"Backbone am amtlichen Text: {sum(found.values())} von {len(found)} Passagen gefunden"
                  + (f"; Kennzeichnung «verified» stimmt nicht bei {', '.join(wrong)}" if wrong else ""))
        for path in files:
            module = load(path)
            if module.get("format") != AREA_FORMAT:
                continue
            for line in describe(compose(bb, module)):
                print(line)
            if texts:
                found = verify(module, texts)
                wrong = [k for k, ok in found.items() if ok != module["law"][k]["verified"]]
                print(f"  am amtlichen Text: {sum(found.values())} von {len(found)} Passagen gefunden"
                      + (f"; Kennzeichnung «verified» stimmt nicht bei {', '.join(wrong)}" if wrong else ""))
    except (CatalogueError, json.JSONDecodeError) as error:
        sys.exit(f"area invalid: {error}")


if __name__ == "__main__":
    main()

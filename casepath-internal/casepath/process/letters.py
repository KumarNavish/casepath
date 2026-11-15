"""The handler's letters and the file note, written from the stored result, the item list and the event log alone.

Deterministic: no model. A letter is the form the workflow names for the action kind (Protekta's wording, from the
development dossiers), filled from what the case asserts and what the handler changed (a line unticked is not asked).
A form with no draft says why ("kein Entwurf: …").
"""
import re
from datetime import date

from . import area, cover, customer_letters, mandate, review as reviews, settlement, urgent
from .clock import as_of, parse_date

# Protekta's forms, from the handler's tenancy-defect workflow: the letters of any workflow that brings none of its own.
SEED_FORMS = area.workflow("mietmangel-handler")["forms"]


def _day(value):
    d = parse_date(value) if value else None
    return d.strftime("%d.%m.%Y") if d else None


GAP = "[bitte ergänzen: "


def gap(what):
    return f"{GAP}{what}]"


def has_gap(text):
    return GAP in (text or "")


def line_state(events):
    """The handler's last word on each letter line: True ticked, False unticked."""
    state = {}
    for e in events or ():
        if e.get("kind") == "letter.line" and e.get("item_id"):
            state[e["item_id"]] = bool(e.get("included"))
    return state


def asked(items, events, kind):
    """The items of one kind that go into the letter: ticked by default unless unticked, offered ones only if ticked."""
    lines = line_state(events)
    out = []
    for i in items:
        if i["kind"] != kind:
            continue
        default = i.get("ask") == "now" or (kind == "hint" and i.get("stated_as") != "put_to_handler")
        if kind == "document" and (i.get("status") == "present" or not i.get("ask") or i.get("part_of")):
            continue
        if lines.get(i["item_id"], default):
            out.append(i)
    return out


def request_list(items, events, evaluation, process):
    """The first request's document lines, as the handler sees them: a whole names its parts ("insbesondere …"), a
    conditional need says its condition ("falls …"), a document the file mentions but lacks says so."""
    lines = line_state(events)
    by_key = {i["key"]: i for i in items if i["kind"] == "document"}
    ev_docs = (evaluation or {}).get("documents") or []
    ticked = lambda key, default: lines.get(f"document:{key}", default)
    ask = [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "now" and d.get("status") != "present" and ticked(d["document"], True)]
    ask += [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "later" and ticked(d["document"], False)]
    ask += [d for d in ev_docs if (by_key.get(d["document"]) or {}).get("ask") == "proposed" and ticked(d["document"], False)]
    ask += [{"document": i["key"], "title": f"{i['label']['de']} ({i['reason']})"} for i in items
            if i["kind"] == "document" and i["key"].startswith("mention-") and lines.get(i["item_id"], i.get("ask") != "proposed")]
    includes = {d["id"]: d.get("includes") or [] for d in (process or {}).get("documents") or []}
    part_of = lambda key: any(key in includes.get(w["document"], []) for w in ask)
    parts = lambda w: [d for d in ask if d["document"] in includes.get(w["document"], [])]
    out = []
    for d in ask:
        if part_of(d["document"]):
            continue
        line = f"– {((by_key.get(d['document']) or {}).get('label') or {}).get('de') or d['title']}"  # «Weitere …» when partly there
        if parts(d):
            line += ", insbesondere " + ", ".join(x["title"] for x in parts(d))
        if d.get("required") == "depends" and d.get("questions"):
            line += " (falls " + " / ".join(q["question"].rstrip("?") for q in d["questions"]) + ")"
        out.append(line)
    return out


INSURED = ("versichert", "vn", "kund", "mieter", "arbeitnehmer", "geschädigt", "tenant", "customer", "insured")


NAME = re.compile(r"[A-ZÄÖÜ][\w'-]+(?:\s+(?:von|van|de|di|da|del|der|du|le|la)?\s*[A-ZÄÖÜ][\w'-]+)+")
COMPANY = re.compile(r"\b(AG|GmbH|SA|Sàrl|AG\.|Genossenschaft|Verwaltung|Immobilien|Versicherung|Kanzlei|Stiftung|Verein)\b", re.I)


def customer(parties):
    """The insured person among the brief's parties (by role), or None."""
    for p in parties or ():
        role = str(p.get("label") or p.get("role") or "").lower()
        if any(word in role for word in INSURED) and "vermiet" not in role and "versicherer" not in role:
            return p
    return None


def greeting(parties):
    """The greeting Protekta's letters use: «Sehr geehrte Frau …» / «Sehr geehrter Herr …» when the file states the insured
    person's salutation and name; «Guten Tag <Vorname Nachname>» when it states the full name without a salutation;
    otherwise the generic one. A salutation is never guessed from a first name."""
    p = customer(parties)
    name = str((p or {}).get("value") or (p or {}).get("name") or "").strip()
    m = re.fullmatch(r"(Frau|Herr)\s+(?:[A-ZÄÖÜ][\w.-]*\s+)*([A-ZÄÖÜ][\w-]+)", name)
    if m:
        return f"Sehr geehrte Frau {m.group(2)}" if m.group(1) == "Frau" else f"Sehr geehrter Herr {m.group(2)}"
    if NAME.fullmatch(name) and not COMPANY.search(name) and "geschw" not in name.lower():
        return f"Guten Tag {name}"
    return "Sehr geehrte Damen und Herren"


def statutory(item):
    """A statutory deadline as a letter states it, plainly: «Die Frist für die Einsprache gegen den Strafbefehl endet am
    16.11.2026.» (its article added by the caller); never its rule's condition, never its title in quotation marks."""
    return urgent.sentence(item, with_basis=False)


def stated_in_letter(item):
    """Whether a deadline goes into a letter: the area's own, applying, its date known or not computable. One that depends
    on a fact the file leaves open, or whose date is still open, is not stated: the letter asks what settles it."""
    return (item["kind"] == "deadline" and item.get("origin") == "law" and not item.get("missing") and not item.get("possible")
            and not item.get("condition"))


def set_date_line(item, today=None):
    """A date a court, an authority or the other side set for the customer, as the first letter mentions it; None when
    it has passed or is not such a date."""
    day = parse_date(item.get("value"))
    if not item.get("set_by_others") or item.get("account") or not day or day < (today or date.today()):  # a date the account holds stays on the screen
        return None
    by = item.get("by")
    source = item.get("source")
    return (f"Wir haben vermerkt: {item.get('what')} am {day.strftime('%d.%m.%Y')}"
            + (f", angesetzt von {by}" if by else "") + (f" ({source})" if source else "")
            + ". Dieser Termin gilt unabhängig von unserer Prüfung; bitte nehmen Sie ihn wahr oder melden Sie sich umgehend, falls dies nicht möglich ist.")


def with_basis(text, basis):
    """A hint with its article, before the sentence's full stop: «… zurückzuzahlen (Art. 318 OR).»; never brackets in
    brackets."""
    text = str(text or "").strip()
    if not basis:
        return text
    basis = urgent.basis_text(basis)
    return f"{text[:-1]} ({basis})." if text.endswith(".") else f"{text} ({basis})"


def _label(item):
    return (item.get("label") or {}).get("de") or item.get("value") or item["key"]


def _summary(items):
    """The request as the reading states it (the summary item), or None."""
    return next((i["value"] for i in items if i["kind"] == "summary" and i.get("value")), None)


def _reference(case):
    """The case's reference number («4321.5555.0001») in its title or intake, as a match; None without one."""
    return re.search(r"\d{4}\.\d{4}\.\d{4}", f"{case.get('title', '')} {case.get('intake', '')}")


def _set_dates(items, day):
    """The lines of the open dates others set for the customer (set_date_line), in item order."""
    return [x for x in (set_date_line(i, day) for i in items if i["kind"] == "deadline") if x]


def context(case, items, events, follow_up, files=(), today=None, evaluation=None, process=None, facts=None, assessment=None):
    """The placeholders of Protekta's forms: from what the case asserts (``items``), what the handler did (``events``), the
    follow-up date and the files; ``evaluation`` and ``process`` give the first request its list of documents. Three parts
    are each one slice's and are merged last, so none changes the others: what the letter says about the case
    (_context_substance), the contact so far (_context_contact) and the parties (_context_parties). ``facts``: the case's
    facts as evaluated (core.evaluate's); ``assessment``: the decision brief (assessment.build). Each part gets the same
    inputs."""
    label = _label
    rows = {i["key"]: i for i in items if i["kind"] == "fact"}
    docs = asked(items, events, "document")
    missing = [i for i in items if i["kind"] == "document" and i.get("ask") == "now" and i.get("status") != "present"]
    present = [i for i in items if i["kind"] == "document" and i.get("status") == "present"]
    parties = [i for i in items if i["kind"] == "party"]
    summary = _summary(items)
    ref = _reference(case)
    lines = line_state(events)
    questions = [i for i in items if i["kind"] == "letter_question" and lines.get(i["item_id"], i.get("ask") != "proposed")]
    hints = [i for i in items if i["kind"] == "hint" and lines.get(i["item_id"], i.get("stated_as") != "put_to_handler")]
    hints += [{"value": statutory(i), "legal_basis": i.get("legal_basis")} for i in items  # a statutory deadline of the area, plainly
              if stated_in_letter(i) and lines.get(i["item_id"], True)]  # an open date or condition: the letter asks what settles it
    day = today or as_of(files)
    hints += [{"value": x} for x in _set_dates(items, day)]  # an open date others set
    hints += [{"value": x} for x in customer_letters.referrals(items, "A1")]  # a template for the customer's own letter goes with it
    listed = request_list(items, events, evaluation, process) if evaluation else [f"– {label(i)}" for i in docs]
    came = (next((i for i in items if i["kind"] == "next_action"), None) or {}).get("incoming") or {}  # what came in, as read
    # «Frist wahren»: what the customer must do by when and where, from the deadline's data and the file
    act = next((i for i in items if i["kind"] == "next_action"), None) or {}
    keep = next((i for i in items if act.get("deadline") and i["item_id"] == act["deadline"]), None)
    template = next((i for i in items if i["kind"] == "customer_letter" and act.get("template") == f"vorlage:{i['key']}"), None)
    after_this = next((t for t in act.get("then") or () if t.get("kind") == "stage"), None)
    given = {"evaluation": evaluation, "process": process, "facts": facts, "assessment": assessment}
    return {
        "wahren_frist": urgent.sentence(keep, with_basis=not keep.get("wahren")) if keep else "",
        "wahren_tun": urgent.what_to_do(keep, process, facts_values(items)) if keep else "",
        "wahren_folge": urgent.consequence(keep) if keep else "",
        "wahren_vorlage": (f"Für Ihr Schreiben an {template['to']} legen wir Ihnen eine Vorlage bei, die Sie prüfen, ergänzen und in Ihrem eigenen Namen senden."
                           if template and template.get("template_kind") != "instruction" else
                           "Wie Sie dabei vorgehen, beschreibt die beigelegte Anleitung." if template else ""),
        "wahren_danach": {"A1": "Welche Unterlagen wir für die Prüfung noch brauchen, teilen wir Ihnen separat mit.",
                          "A5": "Unsere rechtliche Einschätzung erhalten Sie separat."}.get((after_this or {}).get("code"), ""),
        "referenz": ref.group(0) if ref else gap("Referenz"),
        "referenz_kopf": f"Unsere Referenz: {ref.group(0)}\n\n" if ref else "",
        "registrierung": (f"Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist unter der Referenz {ref.group(0)} provisorisch "
                          "registriert; bitte geben Sie diese bei jeder Mitteilung an.") if ref
                         else "Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist bei uns provisorisch registriert.",
        "anrede": greeting(parties),
        "liste": "\n".join(listed),
        "fragen": "\n".join(["Weiter bitten wir Sie um die Beantwortung folgender Fragen:"] + [f"– {i['value']}" for i in questions]) if questions else "",
        "fragen_oder_offen": "\n".join(f"– {i['value']}" for i in asked(items, events, "letter_question")) or "\n".join(f"– {label(i)}" for i in missing) or "– (offener Punkt)",
        "hinweise": "\n".join(["Betreffend die geschilderte Situation erlauben wir uns bereits folgende Hinweise:"]
                              + [with_basis(i["value"], i.get("legal_basis")) for i in hints]) if hints else "",
        "frist": _day((follow_up or {}).get("due")) or "…",
        # What only the reading or the handler can say: the stored text when there is one, otherwise a marked gap that
        # blocks copying the letter until it is filled or removed; never an invented sentence.
        "anliegen": summary or gap("was in diesem Fall vorliegt"),
        "anlass": "das Telefongespräch" if (rows.get("anruf_offen") or {}).get("value") is True else "Ihre Nachricht",
        "erwartet": ("die noch fehlenden Unterlagen: " + ", ".join(label(i) for i in docs)) if docs else "Ihre Rückmeldung",
        "verlangt": "\n".join(cover.missing_lines(items, "versicherer", fallback=False) or [f"– {label(i)}" for i in missing])
                    or "– (Unterlagen gemäss unserem Schreiben)",
        "vorhanden": ", ".join(label(i) for i in present) or "gemäss Akten",
        "heute": day.strftime("%d.%m.%Y"),
        # an end of benefits on the mandated firm's report: its date and its own words on what was withheld, as read; the
        # clause of the general conditions is the handler's to fill in, never invented
        "eingang_datum": _day(came.get("date")) or gap("Datum der Meldung der Kanzlei"),
        # what was asked and not delivered, in neutral words from the requests ledger with the date first asked; never the
        # firm's own words about its client (they stay in «Der Fall» and the Verlauf)
        "vorenthalten": "\n".join(cover.missing_lines(items, fallback=False)) or gap("was trotz Aufforderung nicht eingegangen ist"),
        "avb_ziffer": gap("Ziffer der AVB"),
        # the clause by the edition of the conditions that applies, the parts only the handler can write (cover.py)
        **cover.letter_context(items),
        # the mandate package and the fee-note letters (mandate.py), the settlement's letters (settlement.py)
        **mandate.letter_context(case, items, files, day),
        **settlement.letter_context(items),
        **_context_substance(case, items, events, files, day, **given),
        **_context_contact(case, items, events, files, day, **given),
        **_context_parties(case, items, events, files, day, **given),
    }


def _context_substance(case, items, events, files, day, evaluation=None, process=None, facts=None, assessment=None):
    """What the assessment letter says about the case (Slice A: from ``assessment``): «In Ihrem Fall» (``im_fall``), the
    answers to the customer's questions (``zu_fragen``), the recommendation (``empfehlung``), what is still to be sent
    (``nachzureichen``) and the hint to the customer's own templates (``vorlage_hinweis``). So far from the key points that
    apply, the dates others set, what came in and the documents still asked."""
    summary = _summary(items)
    docs = asked(items, events, "document")
    # a point a jurist marked «Änderung nötig» (review) is not stated by itself: the handler writes it in the gap if it holds
    points = [i for i in items if i["kind"] == "key_point" and i.get("value") == "applies" and not i.get("review")]
    in_case = [f"{i['follows'].rstrip('.')} ({i['legal_basis']})." for i in points[:3]] + _set_dates(items, day)  # what applies, each with its article
    # what came in from others and is a fact of the case («Angebot der Gegenpartei vom … liegt vor: …»), and an open item
    # that waits behind the stage's own action; never a line that it was answered
    after = (next((i for i in items if i["kind"] == "next_action"), None) or {}).get("then") or []
    in_case += [i["incoming"]["line"] for i in items if i["kind"] == "stand" and (i.get("incoming") or {}).get("line")]
    in_case += [t["line"] for t in after if t.get("line")]
    stated = {i["key"] for i in points[:3]}
    questions_asked = [i for i in items if i["kind"] == "customer_question" and i.get("value")]
    return {
        # the assessment's «in your case» starts from the key points that apply, then what only the handler can say
        "im_fall": "\n".join(in_case + [gap("was in diesem Fall sonst vorliegt")]) if in_case else summary or gap("was in diesem Fall vorliegt"),
        # each of the customer's questions, answered by the key point that matches (by reference when stated above), else a gap
        "zu_fragen": "\n".join(["Zu Ihren Fragen:"] + [f"– «{i['value']}» " + (
            f"Siehe oben ({next(p['legal_basis'] for p in points if p['key'] == i['answered_by'])})." if i.get("answered_by") in stated
            else i.get("answer") or gap("Antwort auf diese Frage")) for i in questions_asked]) if questions_asked else "",
        "empfehlung": gap("die Empfehlung an die Kundschaft"),
        # the assessment does not wait for every document: what is still missing is asked for in it
        "nachzureichen": "\n".join(["Bitte reichen Sie uns noch nach:"] + [f"– {_label(i)}" for i in docs]) if docs else "",
        # the assessment refers in one sentence to each template for the customer's own letter (customer_letters.py)
        "vorlage_hinweis": " ".join(customer_letters.referrals(items, "A5")),
    }


INSURER_WORDS = re.compile(r"protekta|rechtsschutz|versicher", re.I)


def _context_contact(case, items, events, files, day, evaluation=None, process=None, facts=None, assessment=None):
    """The contact so far, from the case's facts (``facts``: the actions taken, the account's or the dispatches') and the
    log: a letter's opening after earlier contact («Vielen Dank für Ihre Nachricht», ``wahren_eingang``: an action of
    ours, a dispatch, or a copy by a browser before this release) and the day of the last contact either way
    (``letzter_kontakt``): the account's last contact, else the latest of the dispatches, our actions and the dated
    documents sent to us."""
    from .completion import contacted, dispatches
    rows = {i["key"]: i for i in items if i["kind"] == "fact"}
    acts = facts if facts is not None else {k: r.get("value") for k, r in rows.items()}
    sent = [d for d in (parse_date((acts or {}).get(f"handlung_a{n}") or (rows.get(f"handlung_a{n}") or {}).get("value")) for n in (1, 4, 5, 6, 7)) if d]
    written_before = bool(sent) or contacted(events)
    ref = _reference(case)
    registered = (f"Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist unter der Referenz {ref.group(0)} provisorisch registriert."
                  if ref else "Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist bei uns provisorisch registriert.")
    kontakt = next((i for i in items if i["kind"] == "stand" and i.get("key") == "kontakt"), None)  # the account's last contact
    last = parse_date((kontakt or {}).get("value"))
    if not last:
        received = [d for f in files or () for s in ((f.get("extraction") or {}).get("segments") or ())
                    if INSURER_WORDS.search(str(s.get("recipient") or "")) and not INSURER_WORDS.search(str(s.get("sender") or ""))
                    and (d := parse_date(s.get("date")))]
        latest = sent + [d for d in (parse_date(x["date"]) for x in dispatches(events)) if d] + received
        last = max(latest) if latest else None
    return {"wahren_eingang": "Vielen Dank für Ihre Nachricht." if written_before else registered,
            "letzter_kontakt": last.strftime("%d.%m.%Y") if last else "…"}


def _context_parties(case, items, events, files, day, evaluation=None, process=None, facts=None, assessment=None):
    """The other side as the letters name it (``gegenpartei``; Slice C: a party the handler corrected first). So far the
    first party the file names that is not the tenant."""
    parties = [i for i in items if i["kind"] == "party"]
    return {"gegenpartei": next((p["value"] for p in parties if p.get("value") and "mieter" not in str(p.get("label") or "").lower()), "…")}


def facts_values(items):
    return {i["key"]: i.get("value") for i in items if i["kind"] == "fact"}


PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
NOTHING = "kein Entwurf: der Brief hätte keinen Inhalt"


def _parts(kind, forms, ctx):
    """The draft of one action kind by part: ([(part id, text)], None), or (None, reason) when the kind has no draft. The
    frame's head (reference, greeting) is the part «head», its closing «tail», each part of the form that is kept «p<i>»,
    ``i`` its place in the form's ``parts``. A form never renders empty: a part whose placeholders all come out empty (no
    documents, no questions, no hints) is left out with its fixed words, so no empty list is announced; a form that names
    what it is for (``asks``: its placeholders) and has none of them filled has no draft and says why (``empty``);
    ``only_with`` names sentences that go when their placeholder is empty (no "send us copies" without a document list).
    Offered lines nobody ticked are not in ``ctx``."""
    form = (forms or {}).get(kind)
    if not form:
        return None, "für diese Handlung ist kein Formular hinterlegt"
    if form.get("none"):
        return None, form["none"]
    filled = lambda name: bool(str(ctx.get(name) or "").strip())
    if form.get("asks") and not any(filled(name) for name in form["asks"]):
        return None, form.get("empty") or NOTHING
    frame = forms.get("_frame") or {"head": [], "tail": []}
    if form.get("frame") is False:  # a summary or a form that is no letter: no reference, greeting or closing
        frame = {"head": [], "tail": []}
    if form.get("anrede"):  # a letter to a firm or the other side greets them, not the customer
        ctx = {**ctx, "anrede": form["anrede"]}
    fill = lambda text: text.format(**ctx)
    kept = [(i, p) for i, p in enumerate(form["parts"]) if not PLACEHOLDER.findall(p) or any(filled(n) for n in PLACEHOLDER.findall(p))]
    body = [(i, fill(p).strip(" ")) for i, p in kept]
    for name, sentences in (form.get("only_with") or {}).items():  # words that belong to a placeholder: gone when it is empty
        if not filled(name):
            for sentence in sentences:
                body = [(i, part.replace(sentence, "")) for i, part in body]
    if not any(part.strip() for _, part in body):
        return None, form.get("empty") or NOTHING
    head, tail = [fill(p) for p in frame["head"]], [fill(p) for p in frame["tail"]][1:]
    return (([("head", "\n".join(head))] if head else []) + [(f"p{i}", part) for i, part in body if part.strip()]
            + ([("tail", "\n".join(tail))] if tail else [])), None


def render_parts(kind, forms, ctx):
    """The draft of one action kind as its parts, [(part id, text)] in the letter's order: «head», «p<i>» (the form's part
    ``i``) and «tail» (see _parts); [] when the kind has no draft (``render`` says why). A part's id stays the same however
    the other parts change, so an edit is kept by its part."""
    return _parts(kind, forms, ctx)[0] or []


def join_parts(parts):
    """A letter's text from its parts, as ``render`` gives it: the head's lines, each part followed by an empty line, the
    closing's lines."""
    lines = []
    for part, text in parts:
        lines += text.split("\n") if part in ("head", "tail") else [text, ""]
    return "\n".join(lines).strip()


def render(kind, forms, ctx):
    """The draft for one action kind: the frame (reference, greeting, closing) around the form's parts (render_parts,
    joined). Returns (text, None) or (None, reason) when the kind has no draft."""
    parts, reason = _parts(kind, forms, ctx)
    return (join_parts(parts), None) if parts is not None else (None, reason)


def form_kind(action):
    """The form an action's letter is written in: the first request's for «request», the form the action names, else its
    kind; an action the handler picked instead («andere Handlung») is written in its kind's own form."""
    return "A1" if action.get("action") == "request" else (None if action.get("chosen_by_handler") else action.get("form")) or action.get("action")


def draft(current, listed, events, clock, files, forms, texts=None, held=None, assessment=None):
    """The prepared action's letter as the case view shows it, in Protekta's form, from what the case asserts and what the
    handler changed: {kind, form, title, to, text, none, needs, required, also}; None without a prepared action or forms.
    ``current``: the case's state (runner.case_state); ``listed``: its items (the next action as prepared_action set it);
    ``clock``: the follow-up; ``texts``: the files with their text where a letter quotes them; ``held``: the jurists' flags
    (review.flags); ``assessment``: the decision brief (assessment.build), for the letter's substance."""
    action = next((i for i in listed if i["kind"] == "next_action"), None)
    if not (action and forms):
        return None
    from .completion import frozen_respond_by
    held = held if held is not None else reviews.flags(current.get("process"), None)
    kind = form_kind(action)  # a closing in silence has its own (no) letter
    # a letter that sets the customer a date ({frist}) keeps the date its approval froze while that approval is open, so a
    # letter approved today is the same letter tomorrow (completion.frozen_respond_by)
    dated = "{frist}" in " ".join((forms.get(kind) or {}).get("parts") or ())
    frozen = frozen_respond_by(events, kind, as_of(files)) if dated else None
    if frozen:
        clock = {**(clock or {}), "due": frozen}
    ctx = context(current["case"], listed, events, clock, texts or files, evaluation=current["evaluation"], process=current["process"],
                  facts=current.get("facts"), assessment=assessment)
    text, none = render(kind, forms, ctx)
    # parts the law or the conditions require (copying is refused while one is missing, cover.py), each «in Prüfung»
    # while a jurist marked it «Änderung nötig»
    required = lambda k: [{**r, **({"review": reviews.IN_REVIEW} if held.required(k, r["id"]) else {})} for r in cover.required_for(k, current.get("facts"))]
    return {"kind": action.get("action"), "form": kind, "title": (forms.get(kind) or {}).get("title"), "to": (forms.get(kind) or {}).get("to"), "text": text, "none": none,
            "needs": (forms.get(kind) or {}).get("needs") or [],  # the handler decisions this action waits for
            "required": required(kind),
            # the letter by part (the handler's text is kept per part, completion.merge) and the date it sets the customer
            "base_parts": render_parts(kind, forms, ctx) if text is not None else [], "respond_by": (clock or {}).get("due") if dated else None,
            # what goes out with it, each opened and copied on its own: the mandate package, the fee-note letters, and a
            # template for the customer's own letter (marked as the customer's, never sent by the insurer)
            "also": [{"kind": k, "title": forms[k].get("title"), "text": render(k, forms, ctx)[0], "required": required(k),
                      "base_parts": render_parts(k, forms, ctx), **({"set": forms[k]["set"]} if forms[k].get("set") else {})}
                     for k in accompanying(kind, forms, listed)]
                    + [{"kind": f"vorlage:{i['key']}", "title": i["label"]["de"], "name": i.get("title"), "text": i["text"], "required": [], "template": True,
                        "base_parts": [("text", i["text"])], **({"review": i["review"]} if i.get("review") else {})}
                       for i in customer_letters.with_letter(listed, events, kind)]}


def accompanying(kind, forms, items=()):
    """The forms that go out with an action's letter, each copied on its own: the mandate package's cost guarantee, summary
    and the customer's information; the fee-note query and partial refusal while the cost check is shown (``with_item``)."""
    have = {i["item_id"] for i in items or ()}
    return [k for k, f in (forms or {}).items() if isinstance(f, dict) and f.get("accompanies") == kind
            and (not f.get("with_item") or f["with_item"] in have)]


def _adoption(events, process=None):
    """The recommendation the handler adopted (SLICE_A: «item.corrected» on «point:empfehlung»), in words, or None."""
    undone = {e.get("undoes") for e in events or () if e.get("kind") == "correction.undone"}
    row = next((e for e in reversed(events or ()) if e.get("kind") == "item.corrected" and e.get("item_id") == "point:empfehlung"
                and e.get("chosen") and e.get("event_id") not in undone), None)
    if not row or row["chosen"] == "aussichten_nicht_genuegend":
        return None
    titles = row.get("titles")
    if not titles:
        try:  # the options' titles, from the area's options file where one is shipped (SLICE_A)
            from . import options as area_options
            data = area_options.load((process or {}).get("id") or "mietmangel-handler") or {}
            named = {o["id"]: o.get("title") for o in data.get("options") or ()}
            titles = [named.get(x) or x for x in row["chosen"]]
        except Exception:  # noqa: BLE001  no options file: the ids as recorded
            titles = list(row["chosen"])
    return " · ".join(str(t) for t in titles)


def file_note(case, items, events, follow_up, files=(), runs_done=None, package=None):
    """One paragraph for the case system: received, decided and why, sent, awaited. Only from what is stored.
    ``package``: the titles of the letters that go out together (the mandate package), each with its state («freigegeben»,
    «versandt am …»). Received and entered since the last Versandpaket saved (the file note of that version is in it);
    «Versandt» only from a dispatch the handler confirmed, never from a copy."""
    from .completion import approvals, note_lines, sent_letters
    label = lambda i: (i.get("label") or {}).get("de") or i["key"]
    since = max((str(e.get("at") or "") for e in events or () if e.get("kind") == "bundle.saved"), default="")
    received = [f.get("name") for f in files or () if f.get("name") and (not since or str(f.get("created_at") or "") > since)]
    decided = []
    adopted = _adoption(events)
    for i in items:
        if i["kind"] == "fact" and i.get("verdict") == "set_by_handler" and not (adopted and i["key"] == "aussichten"):
            decided.append(f"{label(i)}: {_value(i.get('value'))} (durch die Fallbearbeitung)")
    if adopted:
        prospects = next((i.get("value") for i in items if i["kind"] == "fact" and i["key"] == "aussichten"), None)
        decided.append(f"Empfehlung übernommen: {adopted}" + (f"; Aussichten {prospects}" if prospects else ""))
    unticked = [label(i) for i in items if i["kind"] == "document" and line_state(events).get(i["item_id"]) is False]
    action = next((i for i in items if i["kind"] == "next_action"), None)
    reason = (action or {}).get("reason")
    sent = sent_letters(events)
    docs = asked(items, events, "document")
    due = _day((follow_up or {}).get("due"))
    parts = []
    if received:
        parts.append(f"Eingegangen: {', '.join(received)}.")
    # what the handler entered (a call, a conversation, a note) since the file note was last copied or saved with a
    # Versandpaket: it is not in the files
    copied_at = max([str(e.get("at") or "") for e in events or () if e.get("kind") == "filenote.copied"] + [since])
    own = [i for i in items if i["kind"] == "entry" and i.get("handler") and str(i["handler"].get("at") or "") > copied_at]
    if own:
        parts.append("Erfasst durch die Fallbearbeitung: " + "; ".join(handler_line(i) for i in own) + ".")
    # the running account (account.py), when the run recorded one: what is agreed, open at whom, the last contact
    parts += [f"{label(i)}: {i.get('detail') or i.get('value')}." for i in items if i["kind"] == "stand"]
    if decided:
        parts.append(f"Entschieden: {'; '.join(decided)}.")
    if action:
        parts.append(f"Nächster Schritt: {action.get('value')}" + (f", weil {reason}" if reason else "") + ".")
    if action and action.get("form") == "A12_still":  # a closing in silence, not an end of benefits
        last = [d for d in (parse_date(next((i.get("value") for i in items if i["kind"] == "fact" and i["key"] == f"handlung_a{n}"), None)) for n in (6, 7)) if d]
        parts.append("Abschluss ohne Rückmeldung der Kundschaft: die Schliessung war im Schreiben"
                     + (f" vom {max(last).strftime('%d.%m.%Y')}" if last else "") + " angekündigt; kein weiteres Schreiben.")
    if unticked:
        parts.append(f"Nicht verlangt (von der Fallbearbeitung gestrichen): {', '.join(unticked)}.")
    if package and len(package) > 1:  # every letter of the package, and where each stands: approved, sent to its recipient
        latest = (approvals(events) or [{}])[-1]
        approved = {k for r in latest.get("recipients") or () for k in r.get("forms") or ()}
        went = {}
        for s in sent:
            for r in next((a.get("recipients") for a in approvals(events) if a.get("version") == s["version"]), None) or ():
                if r.get("to") == s["recipient"]:
                    for k in r.get("forms") or ():
                        went[k] = s["date"]
        facts = {i["key"]: i.get("value") for i in items if i["kind"] == "fact"}
        scope, row = mandate.scope(facts)
        amount = mandate.amount_text(facts.get("kostengutsprache_betrag"))
        named = [f"{title}" + (f" (Umfang: {row['text']}; " + (f"begrenzt auf CHF {amount})" if amount else "nach den bekannten Modalitäten, ohne Betrag)")
                               if kind == "A10_kostengutsprache" else "")
                 + (f" – versandt am {_day(went[kind])}" if kind in went else " – freigegeben" if kind in approved else "") for kind, title in package]
        parts.append(f"Paket ({len(package)} Schreiben, je einzeln): {'; '.join(named)}.")
    parts += [f"{line}." for line in note_lines(events)]
    last = sent[-1] if sent else None
    went = next((e for e in reversed(events or ()) if e.get("kind") == "action.dispatched" and last and e.get("version") == last["version"]
                 and e.get("asks")), None)
    asked_then = (went or {}).get("asks")
    entry = next((i for i in items if i["kind"] == "entry" and went and went.get("n") is not None and i.get("key") == str(went["n"])), None)
    if asked_then and entry is not None:  # what the account still shows open of it: a partial reply leaves only the rest awaited
        still = [n.get("text") or "" for n in entry.get("notes") or () if n.get("kind") == "asked" and n.get("open")]
        asked_then = [a for a in asked_then if any(a in text for text in still)]
    if last and asked_then:  # what the letter that went out asked and is still awaited, by its date or the follow-up
        until = f" bis {_day(last['respond_by'])}" if last.get("respond_by") else f"; Wiedervorlage {due}" if due else ""
        parts.append(f"Erwartet: {', '.join(asked_then)}{until}.")
    elif not last and (docs or due):
        parts.append("Erwartet: " + (", ".join(label(i) for i in docs) if docs else "Rückmeldung") + (f" bis {due}" if due else "") + ".")
    return " ".join(parts)


def _value(v):
    return {True: "ja", False: "nein"}.get(v, v)


def handler_line(item):
    """A handler's entry in the file note: «Telefon mit der Gegenpartei (Herr Muster) am 15.11.2026: Einigung …;
    vereinbart: …», what was said and each structured part as the Verlauf states it."""
    from .account import FORM_KINDS, WITH
    h = item.get("handler") or {}
    with_ = "" if h.get("kind") == "notiz" and h.get("party") in (None, "andere") else f" mit {WITH.get(h.get('party'), 'Dritten')}"
    head = f"{FORM_KINDS.get(h.get('kind'), 'Eintrag')}{with_}" + (f" ({h['name']})" if h.get("name") else "") + (f" am {_day(item.get('date'))}" if item.get("date") else "")
    said = re.sub(r"\s+", " ", str(h.get("said") or "")).strip().rstrip(".")
    notes = [n["text"] for n in item.get("notes") or () if n.get("kind") in {"agreed", "asked", "next", "promised"}]
    return head + (f": {said}" if said else "") + (f" ({'; '.join(notes)})" if notes else "")


def action_options(graph, evaluation, forms):
    """The action kinds of the current stage and its neighbours (the steps it comes from and leads to): what a handler
    may pick instead of the prepared action, each with its days until the follow-up and whether it has a draft."""
    steps = {s["id"]: s for s in graph.get("steps", [])}
    here = ((evaluation or {}).get("current") or {}).get("step") or ((evaluation or {}).get("path") or [{}])[-1].get("step")
    near = [here] + [e["to"] for e in (steps.get(here) or {}).get("next", [])] + [s["id"] for s in steps.values()
                                                                                  if any(e["to"] == here for e in s.get("next", []))]
    out = {}
    for sid in near:
        action = (steps.get(sid) or {}).get("action") or {}
        for kind, days in [(action.get("kind"), action.get("next_in_days")), (action.get("follow_up"), None)] + \
                          [(v.get("kind"), v.get("next_in_days")) for v in action.get("instead", [])]:
            if kind and kind not in out and kind != "A0":  # the receipt is sent by Protekta's online form, not chosen
                form = (forms or {}).get(kind) or {}
                title = form.get("title") or ((graph.get("action_kinds") or {}).get(kind) or {}).get("title") or kind
                out[kind] = {"kind": kind, "title": title, "next_in_days": days, "has_draft": bool(form) and not form.get("none")}
    for rule in graph.get("clock", []):  # a follow-up's days come from the clock when no stage names them
        if rule["then"] in out and out[rule["then"]]["next_in_days"] is None:
            out[rule["then"]]["next_in_days"] = rule.get("deadline_days")
    return list(out.values())


def chosen_action(events):
    """The kind a handler picked instead of the prepared action ("andere Handlung"), latest first; None when none."""
    picks = [e for e in events or () if e.get("kind") == "item.corrected" and e.get("item_id") == "next_action:0" and e.get("chosen")]
    return picks[-1]["chosen"] if picks else None

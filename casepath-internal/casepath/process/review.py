"""A jurist's review of the legal content CasePath relies on: one screen per area, each element beside its passage.

The areas, their key points and deadlines, the cover check and the letters with prescribed content were written from the
law and checked word for word against the official texts, but a jurist decides whether handlers may rely on them. Every
element a handler or a customer relies on is listed here with a stable id derived from the data and the hash of its
content:

- each area module (``<module id>``): the questions to the customer (``frage.<fact>``), the documents with their legal
  reason and condition (``unterlage.<id>``), the hints (``hinweis.<id>``), the key points (``kernpunkt.<id>``), the
  statutory deadlines (``frist.<id>``), the assessment frame (``rahmen.<part>``), the templates for the customer's own
  letters (``vorlage.<id>``);
- the backbone (``backbone``): how each procedure counts a period (``zaehlung.<rule>``, ``zaehlung.feiertage``), shown
  in every area whose deadlines use it, and the letters ``schreiben.A11_teilablehnung`` and
  ``schreiben.A12_mitwirkung_kanzlei``;
- the cover check (``cover``): the cover points (``punkt.<id>``), each legal area's capacity and clauses
  (``zuordnung.<id>``), the date that stands for the cause (``ursache``), the customer's question for it
  (``frage.ursache_datum``), the rules for an end of benefits and the first contact (``regel.<id>``), and the letters
  whose content the law or the conditions prescribe, one element per required part (``schreiben.<form>.<part>``).

The hash covers the element's data and the passages it rests on (canonical JSON, SHA-256). A jurist marks an element
«geprüft», «Änderung nötig» or «Frage» (the store keeps every mark and logs it). A mark holds for the content it was
given on: once the content changes in a release the mark lapses («geändert seit Prüfung», counted as open). An area
whose elements are all «geprüft» is «freigegeben». Marks never change the data files. In a case (items.build_items) an
element marked «Änderung nötig» is offered unticked with «in Prüfung» (a key point, a hint, a template, an offered
line); a deadline is never hidden or unticked by a mark, it shows «in Prüfung». An open question in a data file that
names an element (``about``) is shown beside it. Model-free.
"""
from datetime import date, datetime
import hashlib
import html
import json
from pathlib import Path
import re

from .workflows import CatalogueError

MARKS = {"geprueft": "geprüft", "aenderung": "Änderung nötig", "frage": "Frage"}
STATES = {"offen": "offen", "geaendert": "geändert seit Prüfung", **MARKS}
IN_REVIEW = "in Prüfung"  # the quiet mark a handler sees beside an element marked «Änderung nötig»
WHOLE = "gebiet"  # an open question about an area as a whole
BACKBONE, COVER = "backbone", "cover"
COVER_ROW, LETTERS_ROW = "deckung", "schreiben"
BACKBONE_LETTERS = ("A11_teilablehnung", "A12_mitwirkung_kanzlei")
HOLIDAYS = "zaehlung.feiertage"
GROUPS = {"fragen": "Fragen an die Kundschaft", "unterlagen": "Unterlagen", "hinweise": "Hinweise", "kernpunkte": "Kernpunkte",
          "fristen": "Fristen", "rahmen": "Beurteilungsrahmen", "vorlagen": "Vorlagen für die Kundschaft", "berechnung": "Fristberechnung",
          "empfehlungen": "Empfehlungen", "antworten": "Antworten auf Fragen", "faelle": "Sätze zum Fall", "wortlaut": "Verbindende Sätze",
          "punkte": "Deckungspunkte", "zuordnung": "Zuordnung nach Rechtsgebiet", "ursache": "Datum der Ursache",
          "regeln": "Regeln", "pflichtteile": "Pflichtteile", "schreiben": "Schreiben", "ablehnung": "Deckungsablehnung (Schreiben)"}
# an area's options file (options.py) adds its recommendations, answers, sentences about the case and joining sentences
AREA_GROUPS = ("fragen", "unterlagen", "hinweise", "kernpunkte", "fristen", "rahmen", "vorlagen", "empfehlungen", "antworten", "faelle",
               "wortlaut", "berechnung")
OPTION_STATES = {"geprueft": "geprüft", "aenderung": IN_REVIEW, "frage": "Frage offen"}
UNREVIEWED = "nicht juristisch geprüft"


def state_of(key, current):
    """An element's review state as a handler sees it beside a recommendation or an answer: «geprüft», «in Prüfung»
    (Änderung nötig), «Frage offen», or «nicht juristisch geprüft» (never marked, or changed since its mark).
    ``current``: the marks that hold for the content as it is now (Model.current)."""
    return OPTION_STATES.get(((current or {}).get(key) or {}).get("mark"), UNREVIEWED)
COVER_GROUPS = ("punkte", "zuordnung", "ursache", "fragen", "regeln", "ablehnung")
LETTER_GROUPS = ("pflichtteile", "schreiben")


# Element ids: derived from the data, the same for the validator and the screen ---------------------------------------

def _asked(module):
    """The facts of a module asked of the customer in the first request (``ask_customer`` true or «offered»)."""
    return [f for f in module.get("facts") or () if f.get("ask_customer")]


def module_ids(module):
    return ([f"frage.{f['id']}" for f in _asked(module)] + [f"unterlage.{d['id']}" for d in module.get("documents") or ()]
            + [f"hinweis.{h['id']}" for h in module.get("hints") or ()] + [f"kernpunkt.{p['id']}" for p in module.get("key_points") or ()]
            + [f"frist.{d['id']}" for d in module.get("deadlines") or ()] + [f"rahmen.{k}" for k in module.get("assessment") or {}]
            + [f"vorlage.{c['id']}" for c in module.get("customer_letters") or ()])


def backbone_ids(backbone):
    return ([f"zaehlung.{k}" for k in backbone.get("counting") or {}] + [HOLIDAYS]
            + [f"schreiben.{k}" for k in BACKBONE_LETTERS if k in (backbone.get("forms") or {})])


def _required(form):
    return [p["required"] for p in form.get("parts") or () if isinstance(p, dict)]


def cover_ids(data):
    ids = [f"punkt.{p['id']}" for p in data["points"]] + [f"zuordnung.{a['id']}" for a in data["areas"]] + ["ursache"]
    ids += [f"frage.{f['id']}" for f in data["facts"] if f.get("ask_customer")] + ["regel.leistungseinstellung", "regel.erstkontakt"]
    for kind, form in data["forms"].items():
        parts = _required(form)
        ids += [f"schreiben.{kind}.{p['id']}" for p in parts] if parts else [f"schreiben.{kind}"]
    return ids


def check_questions(questions, ids, where, whole=False):
    """An open question that names what it is about (``about``: an element id, a list of them, or «gebiet» for an area
    as a whole) must name elements of its own file: it is shown beside them on the review screen."""
    ids = set(ids)
    for q in questions or ():
        if "about" not in q:
            continue
        about = q["about"] if isinstance(q["about"], list) else [q["about"]]
        if not about or not str(q.get("text") or "").strip() or any(not isinstance(a, str) or (a not in ids and not (whole and a == WHOLE)) for a in about):
            raise CatalogueError(f"{where}: the open question «{str(q.get('text'))[:60]}» is about {q['about']!r}, which is no element here")


# Building the elements ------------------------------------------------------------------------------------------------

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def _short(question):
    """A fact's question without the note in brackets that only the handler needs («(Entscheid der Fallbearbeitung)»)."""
    return re.sub(r"\s*\((?:Entscheid|Eingabe|Police geprüft)[^)]*\)\s*$", "", str(question or "")).strip()


def condition_text(condition, facts):
    """A condition on facts in words: «Wurde fristlos gekündigt?» ja; … und …; … oder …."""
    if condition is True or condition is None:
        return "immer"
    if "all" in condition or "any" in condition:
        word, parts = (" und ", condition["all"]) if "all" in condition else (" oder ", condition["any"])
        return word.join(f"({condition_text(c, facts)})" if isinstance(c, dict) and ("all" in c or "any" in c) else condition_text(c, facts)
                         for c in parts)
    if "not" in condition:
        return f"nicht: {condition_text(condition['not'], facts)}"
    name = f"«{_short((facts.get(condition.get('fact')) or {}).get('question') or condition.get('fact'))}»"
    value = lambda v: ("ja" if v else "nein") if isinstance(v, bool) else f"«{v}»"
    if "known" in condition:
        return f"{name} {'beantwortet' if condition['known'] else 'noch offen'}"
    if "is" in condition:
        return f"{name} {value(condition['is'])}"
    return f"{name} " + " oder ".join(value(v) for v in condition.get("in") or ())


def _with_basis(text, basis):
    text = str(text or "").strip()
    if not basis:
        return text
    return f"{text[:-1]} ({basis})." if text.endswith(".") else f"{text} ({basis})"


def _refs(row):
    refs = (row or {}).get("law") or []
    return refs if isinstance(refs, list) else [refs]


def _template_body(text):
    """A template for the customer's own letter without the frame every template shares (sender, address, place, date,
    greeting): its subject, its parts with their articles and the advice that goes with it."""
    lines = text.split("\n")
    if "Sehr geehrte Damen und Herren" not in lines or "Freundliche Grüsse" not in lines:
        return text  # an instruction, not a letter: as it stands
    start, end = lines.index("Sehr geehrte Damen und Herren"), lines.index("Freundliche Grüsse")
    subject = next((l for l in reversed(lines[:start]) if l.strip()), "")
    advice = lines[lines.index("Hinweise zur Vorlage:"):] if "Hinweise zur Vorlage:" in lines else []
    return "\n".join([f"Betreff: {subject}", ""] + lines[start + 1:end] + advice).strip()


def _day(at):
    """«15.11.2026» for a stored time (UTC), in Swiss time where the zone data is available."""
    try:
        moment = datetime.fromisoformat(str(at))
    except ValueError:
        return str(at)[:10]
    try:
        from zoneinfo import ZoneInfo
        moment = moment.astimezone(ZoneInfo("Europe/Zurich"))
    except Exception:  # noqa: BLE001  no zone data: the stored day
        pass
    return moment.strftime("%d.%m.%Y")


# Placeholders of the insurer's letters, as a jurist reads them on the review screen
PLACEHOLDERS = {"anliegen": "Anliegen der Kundschaft", "aussicht_gruende": "Begründung der Fallbearbeitung", "aussicht_loesung": "vorgeschlagene Erledigung",
                "frist": "Datum", "androhung_anlass": "was verlangt wurde und noch fehlt, mit dem Datum der Anforderung",
                "androhung_datum": "Datum der Aufforderung mit Androhung", "verlangt": "was verlangt wurde", "eingang_datum": "Datum der Meldung der Kanzlei",
                "vorenthalten": "was trotz Aufforderung nicht eingegangen ist", "forderung_bezug": "Bezug der Kostenforderung",
                "kg_bezug": "Datum der Kostengutsprache", "kg_umfang_text": "Umfang der Kostengutsprache", "teil_betrag": "übernommener Betrag",
                "teil_grund": "Begründung, was nicht übernommen wird", "schiedsfrist": None}
AVB_SLOTS = {"avb_ziffer": "mitwirkung", "avb_mitwirkung": "mitwirkung", "avb_aussicht": "aussicht", "avb_schied": "schied",
             "avb_anwalt": "anwalt", "avb_vergleich": "vergleich"}


class Model:
    """Every element to review, by key «<file>:<id>», and the rows of the review screen: one per area, the cover check
    and the letters with prescribed content. Built once from the data files; the marks come from the store."""

    def __init__(self, modules, backbone, cover_data, today=None):
        from . import area
        self.area = area
        self.bb, self.cov, self.modules = backbone, cover_data, modules
        self.today = today or date.today()
        self.elements, self.rows = {}, []
        for module in modules.values():
            self._module(module)
        self._backbone()
        self._cover()
        self._rows()
        self._questions()

    @classmethod
    def load(cls, catalogue=None, directory=None, today=None):
        from . import area, cover
        return cls(area_modules(catalogue, directory), area.backbone(), cover.data(), today)

    # law rows: the verbatim passage, its article and the official text it comes from
    def _law(self, refs, texts, law, laws):
        keys = [str(r).split("#", 1)[1] for r in refs or () if str(r).startswith("law#") and str(r).split("#", 1)[1] in law]
        have = {(law[k]["sr"], law[k]["article"]) for k in keys}
        for text in texts:
            for sr, article in sorted(self.area.cited_articles(str(text or ""), laws)):
                if (sr, article) not in have:
                    keys += [k for k, r in law.items() if (r["sr"], r["article"]) == (sr, article)]
                    have.add((sr, article))
        out = []
        for key in dict.fromkeys(keys):
            row, source = law[key], laws.get(law[key]["sr"]) or {}
            consolidated = str(source.get("consolidation") or "")
            version = f"Fassung vom {consolidated[8:10]}.{consolidated[5:7]}.{consolidated[:4]}" if consolidated else None
            out.append({"cite": row["cite"], "passage": row["passage"], "verified": bool(row.get("verified")),
                        "source": source.get("title") or f"SR {row['sr']}", "url": source.get("url"), "version": version,
                        "link": f"fedlex, {version}" if version else "fedlex"})
        return out

    def _clauses(self, shorts_by_edition, what=None):
        """The clauses of the conditions, each edition named, with the edition's public text as the source."""
        out = []
        for ed, shorts in (shorts_by_edition or {}).items():
            edition = self.cov["editions"][ed]
            for short in shorts:
                row = self.cov["avb"][f"{ed}:{short}"]
                out.append({"cite": f"{row['cite']} AVB {edition['value']}" + (f" ({what})" if what else ""), "passage": row["passage"],
                            "verified": True, "source": edition["title"], "url": edition.get("url"), "version": None, "link": "Text der Bedingungen"})
        return out

    def _slot(self, slot):
        return self._clauses(self.cov["letter_clauses"][slot])

    def _cover_law(self, keys):
        laws = self.cov["laws"]
        return self._law([f"law#{k}" for k in keys], (), self.cov["law"], laws)

    def _public(self, key):
        row = self.cov["public"][key]
        fetched = f"abgerufen am {_day(row['fetched'] + 'T12:00:00+00:00')}" if row.get("fetched") else None
        return {"cite": row["title"], "passage": row["passage"], "verified": bool(row.get("verified")), "source": row["title"],
                "url": row.get("url"), "version": fetched, "link": f"Webseite, {fetched}" if fetched else "Webseite"}

    def _add(self, file, eid, group, title, lines, data, law=()):
        law = list({(row["cite"], row["passage"]): row for row in law if row}.values())  # each passage once
        # a row (label, text, pre, covered): ``pre`` keeps the text's lines; ``covered``: the text shows what the element's
        # data already holds (a key point's words), so showing it changes nothing a mark holds for
        lines = [{"label": row[0], "text": str(row[1]), **({"pre": True} if len(row) > 2 and row[2] else {}),
                  **({"covered": True} if len(row) > 3 and row[3] else {})} for row in lines if row and row[1]]
        key = f"{file}:{eid}"
        self.elements[key] = {
            "key": key, "file": file, "id": eid, "group": group, "title": str(title or eid), "lines": lines, "law": law, "questions": [], "used_in": [],
            # what a mark holds for: the element's data, what the jurist reads of it (the condition in the facts' words; a
            # letter shown with today's date is covered by its data) and the passages it rests on
            "sha256": digest({"data": data, "title": str(title or eid),
                              "lines": [[l["label"], l["text"]] for l in lines if not l.get("pre") and not l.get("covered")],
                              "law": [[r["cite"], r["passage"]] for r in law]})}
        return key

    def _show(self, text):
        """A letter part as the reviewer reads it: the clause of each edition, the period, and the gaps named."""
        def one(m):
            name = m.group(1)
            if name in AVB_SLOTS:
                from .cover import cite_list
                eds = self.cov["letter_clauses"][AVB_SLOTS[name]]
                rows = {ed: cite_list([self.cov["avb"][f"{ed}:{s}"] for s in shorts]) for ed, shorts in eds.items()}
                return f"{rows.get('privat', '')} (Unternehmen: {rows.get('unternehmen', '')})"
            if name == "schiedsfrist":
                return self.cov["schiedsfrist"].get("privat") or "[Frist]"
            return f"[{PLACEHOLDERS.get(name) or name.replace('_', ' ')}]"
        return re.sub(r"\{([a-z_]+)\}", one, str(text))

    def _module(self, m):
        area, wid = self.area, m["id"]
        law, laws = {**self.bb["law"], **m["law"]}, {**self.bb["laws"], **m.get("laws", {})}
        facts = {f["id"]: f for f in self.bb["facts"] + self.cov["facts"] + m["facts"]}
        cond = lambda c: condition_text(c, facts)
        rows = lambda refs, *texts: self._law(refs, texts, law, laws)
        stages = {s["id"]: s["title"] for s in self.bb["steps"]}
        for f in _asked(m):
            asked = f.get("customer_question") or f["question"]
            self._add(wid, f"frage.{f['id']}", "fragen", asked, [
                ("Frage an die Akte", f["question"]) if f.get("customer_question") else None, ("Nicht gemeint", f.get("not_this")),
                ("Antworten", " · ".join(f.get("values") or ())) if f.get("type") == "enum" else None,
                ("Erste Anforderung", "nur angeboten, nicht angekreuzt") if f["ask_customer"] == "offered" else None],
                f, rows(f.get("source_refs"), f["question"], f.get("customer_question")))
        for d in m["documents"]:
            self._add(wid, f"unterlage.{d['id']}", "unterlagen", d["title"], [
                ("Grund", d["why"]), ("Verlangt", "immer" if "required_when" not in d else f"wenn {cond(d['required_when'])}"),
                ("Stufe", stages.get(d["stage"])) if d.get("stage", "klaeren") != "klaeren" else None,  # the clarifying stage goes without saying
                ("Erste Anforderung", "nur angeboten, nicht angekreuzt") if d.get("offered") else None,
                ("Belege in der Akte", (d.get("offered_when_in_file") or {}).get("practice"))], d, rows(d.get("source_refs"), d["why"], d["title"]))
        for h in m["hints"]:
            self._add(wid, f"hinweis.{h['id']}", "hinweise", _with_basis(h["text"], h.get("legal_basis")), [
                ("Gegeben", "immer" if h["when"] is True else f"wenn {cond(h['when'])}")], h, rows(h.get("source_refs"), h["text"], h.get("legal_basis")))
        for p in m.get("key_points") or ():
            found = rows(p["law"])
            self._add(wid, f"kernpunkt.{p['id']}", "kernpunkte", p["statement"], [
                ("Solange offen", p["question"]), ("Gilt, wenn", cond(p["when"])), ("Folge", p["follows"]), ("Zu prüfen", p["check"]),
                ("Erste Anforderung", f"{p['advice']} ({found[0]['cite']})." if p.get("advice") and found else None),
                ("Stufen", ", ".join(stages.get(s, s) for s in p["stages"])) if p.get("stages") else None,
                # the words a keyword proposal looks for in a customer's question (never an answer by themselves)
                ("Stichwörter", " · ".join(p.get("answers") or ()), False, True)], p, found)
        for d in m["deadlines"]:
            rule = self.bb["counting"][d.get("counting", "or")]
            party = "die Kundschaft" if d.get("party", "kunde") == "kunde" else "die Gegenpartei"
            self._add(wid, f"frist.{d['id']}", "fristen", d["title"], [
                ("Auslöser", _short((facts.get(d["trigger"]) or {}).get("question"))), ("Dauer", area.period_text(d)), ("Grundlage", d["basis"]),
                ("Berechnung", rule["title"]), ("Handeln muss", party), ("Versäumt", d["missed"]), ("Gilt, wenn", d.get("when_text")),
                ("Zu prüfen", d.get("check")), ("An die Kundschaft", d["question"]),
                ("Letzter Tag", "wird nicht auf den nächsten Werktag verschoben") if d.get("shift") is False else None,
                ("Richtung", "frühester Zeitpunkt («ab»)") if d.get("direction") == "ab" else None,
                ("Vereinbarte Frist", f"«{_short(facts[d['period_from']]['question'])}» geht vor, wenn die Akte sie nennt") if d.get("period_from") else None,
                ("Zustellung", "in den Betreibungsferien, an einem Sonntag oder Feiertag: «prüfen», kein Datum") if d.get("served") else None],
                d, rows(d.get("source_refs"), d["basis"]))
        names = {"rights": "Rechte", "conditions": "Voraussetzungen", "demand": "Forderung an die Gegenpartei"}
        for key, part in m["assessment"].items():
            used = [form["title"] for form in self.bb["forms"].values() if f"@{key}" in (form.get("parts") or ())]
            self._add(wid, f"rahmen.{key}", "rahmen", names.get(key, key), [
                ("Wortlaut", self._show(part["text"])), ("Im Schreiben", " · ".join(used)),
                ("Lücke für die Fallbearbeitung", " · ".join(part["handler_gaps"])) if part.get("handler_gaps") else None],
                part, rows((), part["text"]))
        from . import customer_letters
        graph = {"facts": list(facts.values()), "law": law, "deadlines": m["deadlines"]}
        for c in m.get("customer_letters") or ():
            refs = [r for part in c["parts"] for r in _refs(part)]
            refs += [r for row in [c.get("sets"), c.get("must_arrive"), c.get("send")] + list(c.get("advice") or []) for r in _refs(row)]
            self._add(wid, f"vorlage.{c['id']}", "vorlagen", c["title"], [
                ("An", c["to"]), ("Angeboten, wenn", cond(c["when"])),
                ("Text", _template_body(customer_letters.render(graph, c, {}, None, None, [], self.today)), True)], c, rows(refs))
        self._options(m, facts, cond, law, laws)

    WORDING_TITLES = {"wish": "Was die Kundschaft möchte", "replies_all": "Antworten auf alle Fragen", "replies_some": "Antworten auf einen Teil der Fragen",
                      "claims": "Geltend gemachte Kosten", "claim_amount": "Betrag nach Angaben der Kundschaft", "claim_line": "Nachzureichende Belege",
                      "join": "Weitere Empfehlung", "conditional": "Antwort, die von einer Angabe abhängt", "discuss": "Vorher besprechen",
                      "changes": "Worauf die Empfehlung beruht", "open_wish": "Offener Wunsch: Frage und was sie entscheidet",
                      "open_only": "Nur offene Wünsche: Frage und was sie entscheidet"}

    def _options(self, m, facts, cond, law, laws):
        """The area's options file (options.py), each element beside its passages: a recommendation with when it applies, its
        conditions («vorher» or «Anspruch», each with its fact or «nicht geprüft»), what would change it, the documents it
        needs, its wording, its practice count and whether it is proposed; an answer to a question about a rule; a sentence
        about the case; a joining sentence."""
        from . import options
        data = options.load(m["id"])
        if not data:
            return
        wid, workflow = m["id"], self.area.workflow(m["id"])
        law = {**law, **data["law"]}
        rows = lambda refs: self._law(refs, (), law, laws)
        points = {p["id"]: p for p in m.get("key_points") or ()}
        intents = {a["intent"]: a for a in data["answers"]}
        documents = {d["id"]: d["title"] for d in m["documents"]}
        kind = {"vorher": "vorher", "anspruch": "Anspruch"}
        for o in data["options"]:
            when = {"all": [{"fact": o["wish"], "is": True}] + list(o.get("when") or ())}
            asked = f" und eine Frage der Kundschaft zu «{intents[o['asked']]['stems'][0]}…»" if o.get("asked") else ""
            conditions = "\n".join(f"{c['text']} ({kind[c['kind']]}: {cond({k: c[k] for k in ('fact', 'is', 'in', 'known') if k in c}) if c.get('fact') else 'nicht geprüft'})"
                                   for c in o.get("conditions") or ())
            changes = []
            for entry in o.get("changes_if") or ():
                what, _, name = str(entry).partition(":")
                changes.append(f"«{_short((facts.get(entry) or {}).get('question') or entry)}»" if not name else
                               documents.get(name, name) if what == "need" else o["conditions"][int(name)]["text"])
            needs = [documents.get(n["document"], n["document"]) + (" (je geltend gemachte Kosten: «Belege zu: …»)" if n.get("names_claim") else "")
                     for n in o.get("needs") or ()]
            refs = [r for part in list(o.get("conditions") or ()) + list(o["advice"]) for r in part.get("law") or ()]
            self._add(wid, f"empfehlung.{o['id']}", "empfehlungen", o["title"], [
                ("Gilt, wenn", cond(when) + asked), ("Voraussetzungen", conditions, True), ("Ändert sich, wenn", "; ".join(changes)),
                ("Unterlagen", "; ".join(needs)), ("Wortlaut", f"Wir empfehlen Ihnen, {options.advice_text(data, workflow, o['id'], template=True)}."),
                ("Praxis", (o.get("observed") or {}).get("count") or options.NOT_RECORDED),
                ("Vorschlag", "ja" if o["propose"] else "nur wählbar" + (f" ({o['why_not']})" if o.get("why_not") else ""))],
                {"option": o, "law": [law.get(k) for k in options._keys(refs)]}, rows(refs))
        for a in data["answers"]:
            state = "beantwortet" if a["state"] == "beantwortet" else (
                "bedingt: vorher besprechen" if (a.get("next") or {}).get("kind") == "discuss" else "bedingt: die Belege, die noch fehlen")
            refs = [r for part in a["parts"] for r in part.get("law") or ()]
            self._add(wid, f"antwort.{a['points'][0]}.{a['intent']}", "antworten",
                      f"{' · '.join(points[p]['statement'] for p in a['points'])}: Frage zu «{a['stems'][0]}…»", [
                          ("Frage enthält", " · ".join(a["stems"]) + (f" (und: {' · '.join(a['with'])})" if a.get("with") else "")),
                          ("Stand", state), ("Antwort", options.answer_text(data, workflow, a, template=True))],
                      {"answer": a, "follows": {p: points[p]["follows"] for p in a["points"]}, "law": [law.get(k) for k in options._keys(refs)]},
                      rows(refs))
        for c in data["case_lines"]:
            self._add(wid, f"fall.{c['id']}", "faelle", c["text"], [
                ("Gesagt, wenn", cond({k: c[k] for k in ("fact", "is", "in", "known") if k in c}) + " (aus der Akte belegt)")], c)
        for key, value in data["wording"].items():
            text = "\n".join(f"{'eine Nachricht' if k == 'one' else 'mehrere'}: {v}" for k, v in value.items()) if isinstance(value, dict) else value
            self._add(wid, f"wortlaut.{key}", "wortlaut", self.WORDING_TITLES.get(key, key), [("Wortlaut", text, isinstance(value, dict))],
                      {"key": key, "wording": value})
        follow = options.follow_on(data)
        if follow:  # the short letter after an assessment (assessment.follow_on): each text, each step and its template
            names = {"received": "Dank für die Nachricht", "documented": "Was damit belegt ist", "question": "Antwort auf die Frage, die wartete",
                     "remainder": "Nur der Rest wird nachgefragt", "stands": "Die Einschätzung gilt im Übrigen"}
            for key, title in names.items():
                value = follow[key]
                text = "\n".join(f"{'mit Beleg' if k == 'with' else 'ohne Beleg'}: {v}" for k, v in value.items()) if isinstance(value, dict) else value
                self._add(wid, f"nachtrag.{key}", "wortlaut", f"Nachtrag: {title}", [("Wortlaut", text, isinstance(value, dict))], {"key": key, "wording": value})
            for step in follow.get("steps") or ():
                refs = [r for part in step["parts"] for r in part.get("law") or ()]
                said = " ".join(options._with_cite(p["text"], [] if p.get("basis") == "prudence" or p.get("plain") else p.get("law"), data, workflow)
                                for p in step["parts"])
                self._add(wid, f"nachtrag.schritt.{step['option']}", "empfehlungen", f"Nachtrag: nächster Schritt zu «{(options.option(data, step['option']) or {}).get('title') or step['option']}»",
                          [("Gesagt, wenn", "die verlangten Belege eingegangen sind"), ("Wortlaut", said)], {"step": step}, rows(refs))
                t = step.get("template")
                if t:
                    self._add(wid, f"nachtrag.vorlage.{t['id']}", "vorlagen", f"Nachtrag: Vorlage «{t['title']}»",
                              [("Betreff", t.get("subject") or t["title"]), ("Wortlaut", "\n".join(p["text"] for p in t["parts"]))], {"template": t},
                              rows([r for p in t["parts"] for r in p.get("law") or ()]))
        for fact, ask in (data.get("asks") or {}).items():  # the question to the customer when the file leaves a fact open
            self._add(wid, f"rueckfrage.{fact}", "fragen", ask["frage"], [
                ("Gefragt, wenn", f"«{_short((facts.get(fact) or {}).get('question') or fact)}» offen ist und eine Antwort oder Empfehlung davon abhängt"),
                ("Im Satz", ask["ob"])], {"fact": fact, "ask": ask})

    def _backbone(self):
        area, bb = self.area, self.bb
        from . import partial
        for p in partial.data()["parts"]:  # the question back after a partial answer (process/partial.py)
            self._add(BACKBONE, f"{partial.PREFIX}{p['id']}", "schreiben", f"Rückfrage nach einer Teilantwort: {p['title']}", [
                ("Gesagt, wenn", "die Kundschaft einen Teil des Verlangten geliefert hat und etwas davon noch offen ist"), ("Wortlaut", p["text"])], {"part": p})
        law, laws = bb["law"], bb["laws"]
        words = {"start": "Beginn", "days": "Tage", "weeks": "Wochen", "months": "Monate", "end": "Letzter Tag", "standstill": "Stillstand",
                 "ferien": "Betreibungsferien"}
        for rid, rule in bb["counting"].items():
            lines, refs = [], []
            for part, label in words.items():
                row = rule.get(part)
                if not row:
                    continue
                ruled = row.get("rule") or part in ("standstill", "ferien")
                lines.append((label, row["text"] if ruled else f"{row['text']}: «prüfen», kein Datum"))
                refs += [f"law#{k}" for k in list(row.get("law") or ()) + list(row.get("service_law") or ())]
            self._add(BACKBONE, f"zaehlung.{rid}", "berechnung", rule["title"], lines, rule, self._law(refs, (), law, laws))
        days = ", ".join(list(area.CANTONAL_DAYS.values()) + list(area.CANTONAL_EASTER.values()))
        self._add(BACKBONE, HOLIDAYS, "berechnung", "Feiertage am letzten Tag einer Frist", [
            ("Bundesfeiertag", "1. August: ein letzter Tag darauf wird verschoben wie ein Sonntag"),
            ("Kantonale Feiertage", f"{days}: ein letzter Tag darauf gibt «prüfen», kein Datum"),
            ("Übrige Tage", "das berechnete Datum trägt den Vermerk «kantonale Feiertage nicht berücksichtigt»")],
            {"federal": area.FEDERAL_HOLIDAYS, "cantonal": area.CANTONAL_DAYS, "easter": {str(k): v for k, v in area.CANTONAL_EASTER.items()}},
            self._law(["law#bv-110.3"], (), law, laws))
        for kind in BACKBONE_LETTERS:
            form = bb["forms"].get(kind)
            if not form:
                continue
            slots = [AVB_SLOTS[n] for p in form["parts"] for n in re.findall(r"\{([a-z_]+)\}", p) if n in AVB_SLOTS]
            self._add(BACKBONE, f"schreiben.{kind}", "schreiben", form["title"], [
                ("An", form.get("to")), ("Text", "\n\n".join(self._show(p) for p in form["parts"]), True)],
                form, [row for slot in dict.fromkeys(slots) for row in self._slot(slot)])

    def _cover(self):
        cov = self.cov
        facts = {f["id"]: f for f in cov["facts"]}
        source = {"akte": "aus der Akte", "police": "aus der Police", "beides": "aus der Akte und der Police"}
        public = cov["public"]["wartefrist"]
        for p in cov["points"]:
            law = self._clauses(p["clauses"])
            lines = [("Frage", p["question"]),
                     ("Beantwortet", source[p["source"]] + (f"; Unternehmen: {source[p['source_unternehmen']]}" if p.get("source_unternehmen") else "")),
                     ("Nachschlagen", p.get("lookup")), ("Ausgabe Unternehmen", p.get("note_unternehmen"))]
            if p["id"] == "wartefrist":
                lines.append(("Allgemein", "drei Monate nach der Produktseite, nicht nach den Bedingungen; ohne Wartefrist: " + ", ".join(public["without"])))
                law.append(self._public("wartefrist"))
            if p["id"] == "pflichten":
                lines.append(("Hinweis", "Ein Nachteil tritt nur bei Verschulden und Einfluss auf das Ereignis oder die Leistung ein: prüfen, nicht folgern."))
                law += self._cover_law(["vvg-45.1"])
            self._add(COVER, f"punkt.{p['id']}", "punkte", p["title"], lines, {"point": p, **({"public": public} if p["id"] == "wartefrist" else {})}, law)
        from . import refusal
        for p in refusal.data()["parts"]:  # the letter that tells a refused cover: approved only once every part is «geprüft»
            self._add(COVER, f"{refusal.PREFIX}{p['id']}", "ablehnung", f"Deckungsablehnung: {p['title']}", [
                ("Gesagt, wenn", "die Fallbearbeitung die Deckung abgelehnt hat"), ("Wortlaut", self._show(p["text"]) if "{" not in p["text"] else p["text"])], {"part": p})
        for a in cov["areas"]:
            label = a.get("label") and a["label"] + (f"; Unternehmen: {a['label_unternehmen']}" if a.get("label_unternehmen") else "")
            law = self._clauses(a.get("eigenschaft"), "Eigenschaft") + self._clauses(a.get("rechtsgebiet"), "Rechtsgebiet") + self._clauses(a.get("grenzen"), "Grenzen")
            self._add(COVER, f"zuordnung.{a['id']}", "zuordnung", a["prefix"] or "Übriges Recht, kein bestimmtes Gebiet", [
                ("Bezeichnung in der Police", label or "keine eigene: in der Police prüfen"),
                ("Versicherte Eigenschaft", a.get("capacity") and a["capacity"] + (f" · {a['capacity_check']}" if a.get("capacity_check") else "")),
                ("Grenzen", a.get("grenzen_text"))], a, law)
        questions = {}
        for wid, fid in cov["cause_from"].items():
            module = self.modules.get(wid) or {}
            fact = next((f for f in module.get("facts") or () if f["id"] == fid), {})
            questions[wid] = (module.get("short_title") or wid, _short(fact.get("question") or fid))
        zeitraum = next(p for p in cov["points"] if p["id"] == "zeitraum")
        self._add(COVER, "ursache", "ursache", "Datum, das als Ursache des Rechtsfalls gilt", [
            (title, f"«{question}»") for title, question in questions.values()] + [
            ("Sonst", "das Datum, das die Kundschaft auf die Frage nach der Ursache nennt"),
            ("In der Prüfung", "aus dem Datum eines Gebiets übernommen: «als Ursache prüfen»")],
            {"cause_from": cov["cause_from"], "questions": questions}, self._clauses(zeitraum["clauses"]))
        for f in cov["facts"]:
            if not f.get("ask_customer"):
                continue
            refs = {ed: [r.split("#", 1)[1]] for r in f.get("source_refs") or () if r.startswith("avb#") for ed in cov["editions"]
                    if f"{ed}:{r.split('#', 1)[1]}" in cov["avb"]}
            self._add(COVER, f"frage.{f['id']}", "fragen", f.get("customer_question") or f["question"], [
                ("Frage an die Akte", f["question"]), ("Nicht gemeint", f.get("not_this")),
                ("Erste Anforderung", "gefragt; nur angeboten, wo das Gebiet selbst ein Datum fragt, das dafür steht")], f, self._clauses(refs))
        coop, warning = cov["cooperation"], facts["mahnung_androhung"]
        self._add(COVER, "regel.leistungseinstellung", "regeln", "Leistungseinstellung wegen fehlender Mitwirkung", [
            ("Regel", "Vor einer Einstellung der Leistungen muss eine schriftliche Aufforderung von Protekta mit Frist und Androhung der "
                      f"Säumnisfolgen vorliegen. Fehlt sie, bereitet CasePath zuerst diese Aufforderung vor (Frist {coop['demand']['next_in_days']} Tage); "
                      "die Fallbearbeitung kann die Leistungen trotzdem einstellen."),
            ("Als Androhung gelesen", warning["question"]), ("Nicht als Androhung", warning.get("not_this")),
            ("Aufforderung der Kanzlei", "wird als solche gezeigt, «ob das genügt: prüfen»; sie zählt nicht als Aufforderung von Protekta"),
            ("Hinweis", "Ein Nachteil wegen verletzter Obliegenheit tritt nur bei Verschulden und Einfluss auf das Ereignis oder die Leistung ein: "
                        "als Prüfung, nicht als Schluss.")],
            {"cooperation": coop, "fact": warning}, self._cover_law(["vvg-39.2.2", "vvg-45.1"]) + self._slot("mitwirkung"))
        first = cov["first_contact"]
        self._add(COVER, "regel.erstkontakt", "regeln", "Erstkontakt mit der Kundschaft", [
            ("Regel", f"innert {first['working_days']} Arbeitstagen ab dem Eingang des Falls; {first['note']}"),
            ("Eingang des Falls", "die Eingangsbestätigung oder Registrierung der Versicherung in der Akte, sonst der Tag, an dem der Fall "
                                  "in CasePath eröffnet wurde, sonst der Eingang der ersten Datei"),
            ("Erledigt durch", "eine Handlung der Versicherung gegenüber der Kundschaft (" + ", ".join(f"A{c}" for c in first["contacts"]) + ")")],
            first, [self._public(first["public"])])
        for kind, form in cov["forms"].items():
            parts = [p for p in form["parts"] if isinstance(p, dict)]
            for part in parts:
                need = part["required"]
                law = []
                for ref in need["basis"]:
                    kind_of, _, key = ref.partition("#")
                    law += self._cover_law([key]) if kind_of == "law" else self._slot(key)
                self._add(COVER, f"schreiben.{kind}.{need['id']}", "pflichtteile", f"{form['title']}: {need['title']}", [
                    ("Wortlaut", self._show(part["text"])),
                    ("Ohne diese Worte", f"«{need['marker']}»: der Brief wird nicht kopiert, solange sie fehlen")],
                    {"form": kind, "title": form["title"], "part": part}, law)
            if not parts:
                slots = [AVB_SLOTS[n] for p in form["parts"] for n in re.findall(r"\{([a-z_]+)\}", p) if n in AVB_SLOTS]
                self._add(COVER, f"schreiben.{kind}", "schreiben", form["title"], [
                    ("An", form.get("to")), ("Text", "\n\n".join(self._show(p) for p in form["parts"]), True)],
                    form, self._cover_law(["vvg-39.2.2"]) + [row for slot in dict.fromkeys(slots) for row in self._slot(slot)])

    def _rows(self):
        def key(m):
            return (m["id"] == "allgemein", m["short_title"].casefold().replace("ä", "a").replace("ö", "o").replace("ü", "u"))
        for m in sorted(self.modules.values(), key=key):
            mine = [k for k in self.elements if k.startswith(f"{m['id']}:")]
            groups = {g: [k for k in mine if self.elements[k]["group"] == g] for g in AREA_GROUPS}
            rules = list(dict.fromkeys(d.get("counting", "or") for d in m["deadlines"]))
            groups["berechnung"] = [f"{BACKBONE}:zaehlung.{r}" for r in rules] + ([f"{BACKBONE}:{HOLIDAYS}"] if m["deadlines"] else [])
            value = (m.get("applies_when") or {}).get("is")
            self.rows.append({"id": m["id"], "kind": "area", "title": m["short_title"],
                              "subtitle": value if isinstance(value, str) else "Übriges Recht oder kein bestimmtes Gebiet",
                              "label": self.area.LABELS.get((bool(m.get("practice")), m["status"]), "freigegeben"),
                              "groups": [{"id": g, "title": GROUPS[g], "keys": groups[g]} for g in AREA_GROUPS if groups[g]], "questions": []})
        own = lambda file, groups: [{"id": g, "title": GROUPS[g], "keys": [k for k in self.elements if self.elements[k]["file"] == file and self.elements[k]["group"] == g]}
                                    for g in groups]
        self.rows.append({"id": COVER_ROW, "kind": "cover", "title": "Deckungsprüfung", "subtitle": "Deckungspunkte, Zuordnung nach Rechtsgebiet, Regeln",
                          "label": "aus den Allgemeinen Bedingungen und dem Gesetz abgeleitet, noch nicht freigegeben",
                          "groups": [g for g in own(COVER, COVER_GROUPS) if g["keys"]], "questions": []})
        letters = [k for k in self.elements if self.elements[k]["group"] in LETTER_GROUPS]
        self.rows.append({"id": LETTERS_ROW, "kind": "letters", "title": "Schreiben mit vorgeschriebenem Inhalt",
                          "subtitle": "Pflichtteile nach Gesetz und Allgemeinen Bedingungen",
                          "label": "aus dem Gesetz und den Allgemeinen Bedingungen abgeleitet, noch nicht freigegeben",
                          "groups": [{"id": g, "title": GROUPS[g], "keys": [k for k in letters if self.elements[k]["group"] == g]} for g in LETTER_GROUPS], "questions": []})
        for row in self.rows:
            for k in self.keys(row):
                self.elements[k]["used_in"].append(row["id"])

    def _questions(self):
        from . import options
        rows = {r["id"]: r for r in self.rows}
        sources = [(wid, m.get("open_questions") or ()) for wid, m in self.modules.items()]
        sources += [(wid, (options.load(wid) or {}).get("open_questions") or ()) for wid in self.modules if wid in options.areas()]
        sources += [(BACKBONE, self.bb.get("open_questions") or ()), (COVER, self.cov.get("open_questions") or ())]
        for file, questions in sources:
            for q in questions:
                about = q.get("about")
                named = about if isinstance(about, list) else [about] if about else []
                if not named or WHOLE in named:  # the area's own, or about the area as a whole
                    if file in rows:
                        rows[file]["questions"].append(q["text"])
                for eid in named:
                    if f"{file}:{eid}" in self.elements:
                        self.elements[f"{file}:{eid}"]["questions"].append(q["text"])
        from . import refusal
        for q in refusal.data().get("open_questions") or ():  # the refusal letter's own open questions, beside their part
            key = f"{COVER}:{refusal.PREFIX}{q['part']}"
            if key in self.elements:
                self.elements[key]["questions"].append(q["question"])
        for wid in self.modules:  # an options file's question linked to an element of the module stands beside that element too
            for q in (options.load(wid) or {}).get("open_questions") or () if wid in options.areas() else ():
                if q.get("linked") and f"{wid}:{q['linked']}" in self.elements:
                    self.elements[f"{wid}:{q['linked']}"]["questions"].append(q["text"])

    # Reading the marks ------------------------------------------------------------------------------------------------

    def row(self, row_id):
        return next((r for r in self.rows if r["id"] == row_id), None)

    @staticmethod
    def keys(row):
        return list(dict.fromkeys(k for g in row["groups"] for k in g["keys"]))

    def state(self, key, mark):
        """offen, geaendert (the content changed since the mark), geprueft, aenderung or frage."""
        if not mark:
            return "offen"
        return mark["mark"] if mark.get("content_sha256") == self.elements[key]["sha256"] else "geaendert"

    def current(self, latest):
        """The marks that hold for the content as it is now: {key: mark}."""
        return {k: m for k, m in (latest or {}).items() if k in self.elements and m.get("content_sha256") == self.elements[k]["sha256"]}

    def status(self, row, latest):
        """The row's state («freigegeben» once every element is «geprüft», «in Prüfung» once any is marked) and its counts."""
        keys = self.keys(row)
        states = [self.state(k, (latest or {}).get(k)) for k in keys]
        count = lambda s: sum(1 for x in states if x == s)
        counts = {"total": len(keys), "geprueft": count("geprueft"), "offen": count("offen") + count("geaendert"),
                  "aenderung": count("aenderung"), "frage": count("frage"), "geaendert": count("geaendert")}
        marks = [latest[k] for k in keys if (latest or {}).get(k)]
        if keys and counts["geprueft"] == len(keys):
            ordered = sorted(marks, key=lambda m: m["at"], reverse=True)
            names = list(dict.fromkeys(m["reviewer"] for m in ordered))
            who = ", ".join(names[:3]) + (" u. a." if len(names) > 3 else "")
            return {"state": "freigegeben", "label": f"freigegeben am {_day(ordered[0]['at'])} · {who}", "at": ordered[0]["at"],
                    "reviewers": names, "counts": counts}
        if marks:
            return {"state": "in_pruefung", "label": f"in Prüfung ({counts['geprueft']} von {len(keys)} geprüft)", "counts": counts}
        return {"state": "offen", "label": row["label"], "counts": counts}

    def area_label(self, workflow_id, latest):
        """The handler's line for a case of the area: its review state in place of «… noch nicht freigegeben»."""
        row = self.row(workflow_id)
        return self.status(row, latest) if row and row["kind"] == "area" else None

    def overview(self, latest):
        return [{k: row[k] for k in ("id", "kind", "title", "subtitle")} | {"status": self.status(row, latest)} for row in self.rows]

    def view(self, key, latest):
        element, mark = self.elements[key], (latest or {}).get(key)
        titles = {r["id"]: r["title"] for r in self.rows}
        return {**{k: element[k] for k in ("key", "file", "id", "group", "title", "lines", "law", "questions", "sha256")},
                "state": self.state(key, mark), "state_text": STATES[self.state(key, mark)], "mark": mark,
                "used_in": [titles[r] for r in element["used_in"]]}

    def detail(self, row_id, latest):
        row = self.row(row_id)
        if row is None:
            return None
        return {**{k: row[k] for k in ("id", "kind", "title", "subtitle", "label", "questions")}, "status": self.status(row, latest),
                "groups": [{"id": g["id"], "title": g["title"], "elements": [self.view(k, latest) for k in g["keys"]]} for g in row["groups"]]}

    def changes(self, latest):
        """What the jurists asked of the developers: every mark «Änderung nötig» or «Frage» that holds for the content as it
        is now, with the element's id, title, comment and suggested wording. No case content: marks are about the data."""
        titles = {r["id"]: r["title"] for r in self.rows}
        out = []
        for key, mark in sorted(self.current(latest).items()):
            if mark["mark"] not in ("aenderung", "frage"):
                continue
            element = self.elements[key]
            out.append({"element": key, "file": element["file"], "id": element["id"], "areas": [titles[r] for r in element["used_in"]],
                        "group": GROUPS[element["group"]], "title": element["title"], "mark": mark["mark"], "mark_text": MARKS[mark["mark"]],
                        "comment": mark.get("comment") or "", "suggestion": mark.get("suggestion") or "", "reviewer": mark["reviewer"],
                        "at": mark["at"], "content_sha256": element["sha256"]})
        return out


def area_modules(catalogue=None, directory=None):
    """The raw area modules behind the catalogue's areas, by id: a module in the deployment's catalogue directory wins
    over the shipped one of the same id, as it does in the catalogue."""
    from . import area
    shipped = {d["id"]: d for d in (area.load(p) for p in sorted(area.AREAS.glob("*.json"))) if d.get("format") == area.AREA_FORMAT}
    own = {}
    for path in sorted(Path(directory).glob("*.json")) if directory else ():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("format") == area.AREA_FORMAT:
            own[data["id"]] = data
    wanted = [w["id"] for w in catalogue.latest() if w.get("area")] if catalogue is not None else list(shipped)
    return {wid: own.get(wid) or shipped[wid] for wid in wanted if wid in own or wid in shipped}


# What the marks change in a case (items.build_items) ------------------------------------------------------------------

class Flags:
    """The elements of one case's area marked «Änderung nötig», asked by item: a hint, a key point or a template is then
    offered unticked; a deadline, a document, a question, a cover point, a check or a required part keeps what it does and
    shows «in Prüfung». ``current``: the marks that hold for the content as it is now (Model.current)."""

    def __init__(self, graph, current):
        self.graph = graph or {}
        self.wid = self.graph.get("id")
        self.changed = {k for k, m in (current or {}).items() if m.get("mark") == "aenderung"}
        self.asked = {k for k, m in (current or {}).items() if m.get("mark") == "frage"}

    def __bool__(self):
        return bool(self.changed)

    def _own(self, eid):
        return f"{self.wid}:{eid}" in self.changed

    def _held(self, eid):
        """An element of the area's options file marked «Änderung nötig» or «Frage»: not used until the jurist settles it."""
        return f"{self.wid}:{eid}" in self.changed or f"{self.wid}:{eid}" in self.asked

    def option(self, option_id):
        return self._held(f"empfehlung.{option_id}")

    def follow(self, key):
        """A text, a step or the template of the area's follow-on letter («nachtrag.<key>»)."""
        return self._held(f"nachtrag.{key}")

    def answer(self, point_id, intent):
        """The answer row of an intent, by the element id it is reviewed under (its first point)."""
        from . import options
        row = next((a for a in (options.load(self.wid) or {}).get("answers") or () if a["intent"] == intent), None)
        return self._held(f"antwort.{(row or {}).get('points', [point_id])[0]}.{intent}")

    def case_line(self, line_id):
        return self._held(f"fall.{line_id}")

    def wording(self, key):
        return self._held(f"wortlaut.{key}")

    def ask(self, fact):
        """The options file's question to the customer for a fact, under a jurist's «Änderung nötig» or «Frage»."""
        return self._held(f"rueckfrage.{fact}")

    def deadline(self, deadline_id):
        d = next((x for x in self.graph.get("deadlines") or () if x["id"] == deadline_id), None)
        return d is not None and (self._own(f"frist.{deadline_id}") or f"{BACKBONE}:zaehlung.{d.get('counting', 'or')}" in self.changed
                                  or f"{BACKBONE}:{HOLIDAYS}" in self.changed)

    def hint(self, hint_id):
        """«untick» for a hint of the area marked «Änderung nötig»; «mark» for the hint of a possible deadline whose deadline is
        (it stays as it is); None otherwise."""
        hint = next((h for h in self.graph.get("hints") or () if h["id"] == hint_id), {})
        if str(hint_id).startswith("frist-") and hint.get("trigger"):
            group = [d for d in self.graph.get("deadlines") or () if d["trigger"] == hint["trigger"] and d.get("hint", True)]
            return "mark" if any(self.deadline(d["id"]) for d in group) else None
        return "untick" if self._own(f"hinweis.{hint_id}") else None

    def key_point(self, point_id):
        return self._own(f"kernpunkt.{point_id}")

    def letter(self, letter_id):
        return self._own(f"vorlage.{letter_id}")

    def document(self, document_id):
        return self._own(f"unterlage.{document_id}")

    def question(self, fact_id):
        return (self._own(f"frage.{fact_id}") or f"{COVER}:frage.{fact_id}" in self.changed
                or any(self.deadline(d["id"]) for d in self.graph.get("deadlines") or () if d["trigger"] == fact_id))

    def cover(self, point_id, rechtsgebiet=None):
        if f"{COVER}:punkt.{point_id}" in self.changed:
            return True
        if point_id in ("eigenschaft", "rechtsgebiet", "grenzen"):
            from . import cover
            return f"{COVER}:zuordnung.{cover.area_row(rechtsgebiet).get('id')}" in self.changed
        return point_id in ("zeitraum", "wartefrist") and f"{COVER}:ursache" in self.changed

    def check(self, key):
        if key == "androhung":
            return f"{COVER}:regel.leistungseinstellung" in self.changed
        if key == "aussichten":
            return any(k.startswith(f"{COVER}:schreiben.A5_aussichtslos.") for k in self.changed)
        return key == "vergleich" and f"{COVER}:schreiben.A10_kunde.vergleich" in self.changed

    def contact(self):
        return f"{COVER}:regel.erstkontakt" in self.changed

    def required(self, form, part_id):
        return f"{COVER}:schreiben.{form}.{part_id}" in self.changed


def flags(graph, current):
    return Flags(graph, current)


# Export and the printable review pack -----------------------------------------------------------------------------------

def changes_markdown(rows, exported=None):
    """The requested changes and questions as a Markdown list for the developers: element id, mark, comment, wording."""
    exported = exported or date.today().strftime("%d.%m.%Y")
    lines = ["# Änderungen und Fragen aus der Prüfung", "",
             f"Stand {exported} · {sum(1 for r in rows if r['mark'] == 'aenderung')} Änderung(en) nötig · "
             f"{sum(1 for r in rows if r['mark'] == 'frage')} Frage(n). Ohne Fallinhalt: jede Zeile betrifft ein Element der Daten.", ""]
    for mark in ("aenderung", "frage"):
        chosen = [r for r in rows if r["mark"] == mark]
        if not chosen:
            continue
        lines += [f"## {MARKS[mark]}", ""]
        for r in chosen:
            lines += [f"### `{r['element']}`", "", f"{' · '.join(r['areas'])} · {r['group']} · {r['title']}", "",
                      f"- Markiert: {r['reviewer']}, {_day(r['at'])}", f"- Kommentar: {r['comment'] or '–'}"]
            if r["suggestion"]:
                lines.append(f"- Vorschlag: {r['suggestion']}")
            lines.append(f"- Inhalt (SHA-256): `{r['content_sha256'][:16]}`")
            lines.append("")
    if len(lines) == 4:
        lines.append("Keine offenen Änderungen oder Fragen.")
    return "\n".join(lines).rstrip() + "\n"


PACK_CSS = """
body{font:13.5px/1.45 "Mulish",system-ui,sans-serif;color:#141516;margin:28px auto;max-width:1000px;padding:0 24px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15.5px;margin:24px 0 2px;padding-bottom:4px;border-bottom:1px solid #d6d6d7}
.meta{color:#4c4b4d;margin:0 0 4px}.how{color:#4c4b4d;font-size:12.5px;margin:0 0 10px}
section{padding:10px 0 6px;page-break-inside:avoid;break-inside:avoid}
h3{font-size:14px;margin:0 0 4px;font-weight:700}
dl{display:grid;grid-template-columns:150px 1fr;gap:2px 12px;margin:4px 0}dt{color:#4c4b4d}dd{margin:0;white-space:pre-wrap}
.law{margin:6px 0 0;padding-left:10px;border-left:2px solid #d6d6d7}.law p{margin:0 0 5px}.law b{font-weight:600}.law sup{color:#4c4b4d}
.q{margin:6px 0 0;padding:3px 8px;background:#f2f2f3}
.marks{margin:6px 0 0;font-size:12.5px;color:#4c4b4d}.box{display:inline-block;width:10px;height:10px;border:1px solid #4c4b4d;margin:0 4px -1px 14px}
.note{border-bottom:1px dotted #9c9ba0;height:20px}
ol.sources{font-size:12px;color:#4c4b4d;padding-left:20px}ol.sources li{margin:0 0 3px;word-break:break-all}
@media print{body{margin:0;max-width:none}a{color:inherit;text-decoration:none}}
"""


def pruefpaket(detail, printed=None):
    """One plain page per area for a jurist who works on paper: each element with its content, the passages it rests on
    with the official source (numbered, each listed once at the end with its address), its open question, its state and
    boxes to mark. No case content."""
    e = html.escape
    printed = printed or date.today().strftime("%d.%m.%Y")
    count = detail["status"]["counts"]
    sources = {}  # (title, version, url) -> its number

    def source(r):
        key = (r.get("source") or "", r.get("version") or "", r.get("url") or "")
        return sources.setdefault(key, len(sources) + 1)
    out = [f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><title>Prüfpaket: {e(detail['title'])}</title>",
           f"<style>{PACK_CSS}</style></head><body>",
           f"<h1>Prüfpaket: {e(detail['title'])}</h1>",
           f"<p class=\"meta\">{e(detail['subtitle'])} · {e(detail['status']['label'])} · {count['total']} Elemente, "
           f"{count['geprueft']} geprüft · gedruckt am {printed}</p>",
           "<p class=\"how\">Je Element der Inhalt in den Worten, die Fallbearbeitung oder Kundschaft sehen, und die Gesetzesstelle im "
           "Wortlaut; die hochgestellte Zahl verweist auf die amtliche Quelle am Schluss. Bitte je Element ankreuzen; die Markierung wird "
           "im Wissen erfasst. Ohne Fallinhalt.</p>"]
    for q in detail["questions"]:
        out.append(f"<p class=\"q\">Offene Frage zum Gebiet: {e(q)}</p>")
    for group in detail["groups"]:
        out.append(f"<h2>{e(group['title'])} · {len(group['elements'])}</h2>")
        for el in group["elements"]:
            mark = el["mark"]
            state = e(el["state_text"]) + (f" ({e(mark['reviewer'])}, {_day(mark['at'])})" if mark and el["state"] != "offen" else "")
            out.append(f"<section><h3>{e(el['title'])}</h3>")
            if el["lines"]:
                out.append("<dl>" + "".join(f"<dt>{e(l['label'])}</dt><dd>{e(l['text'])}</dd>" for l in el["lines"]) + "</dl>")
            if el["law"]:
                out.append("<div class=\"law\">" + "".join(f"<p><b>{e(r['cite'])}</b><sup>{source(r)}</sup> «{e(r['passage'])}»</p>" for r in el["law"]) + "</div>")
            for q in el["questions"]:
                out.append(f"<p class=\"q\">Offene Frage: {e(q)}</p>")
            others = [t for t in el["used_in"] if t != detail["title"]]
            if others:
                out.append(f"<p class=\"marks\">Gilt auch für: {e(', '.join(others))}</p>")
            out.append(f"<p class=\"marks\">Stand: {state}<span class=\"box\"></span>geprüft"
                       f"<span class=\"box\"></span>Änderung nötig<span class=\"box\"></span>Frage</p><div class=\"note\"></div></section>")
    if sources:
        out.append("<h2>Amtliche Quellen</h2><ol class=\"sources\">" + "".join(
            f"<li>{e(title)}{', ' + e(version) if version else ''}{': ' + e(url) if url else ''}</li>" for (title, version, url) in sources) + "</ol>")
    out.append("</body></html>")
    return "\n".join(out)

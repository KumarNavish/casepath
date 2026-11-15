"""S-D11A, «D11-Analogon (synthetisch)»: the synthetic analog of the development dossier D11 for the episode «a reply
arrives → the assessment is prepared → the decision is carried through». The same shape as D11's content-free outline,
with invented content: a tenant reports mould (d0); Protekta asks for four documents and one answer the next day (A1, no
date set); the customer replies after twelve days with the forwarded correspondence with the management and a receipt;
three days later a question back (A4: one point, two questions, recorded as an «anforderung» as the reader does today);
the customer answers twice on one day (d+35); the assessment (A5) asks the receipts of the electricity cost she claims;
then silence until the status inquiry (A7), or the receipts arrive. Every name, address, amount and sentence is made up.

- Phase A: the file as it stood on d+34, one dossier of 22 pages and 11 documents, prepared by a scripted full run.
- Phase B: the two replies of d+35 (e-mails), read by a scripted update.
- Perturbations, each labelled: P-dup (a reply uploaded again), P-contra («Mangel behoben» set after approval), P-retract
  (the receipts promised, then the claim withdrawn, the promise quoted), P-refuse («Für die Stromkosten habe ich keine
  Belege»), P-fail (the update's model fails), P-restart (an update left running, the store reopened).
- Branches after the A5 is dispatched: B-silence (A5 + 91 days) and B-receipts (A5 + 20 days, the A5 quoted below).

``analog()`` builds the episode for a claim day ``d0`` (D0 by default: the replies come on 05.09.2026); ``VARIANT_B`` is
the same shape with other facts (deploy/preview's E2: the reply asks only about the deposit, promises receipts and claims
nothing yet). Each question carries the reader's tags (``about``: the key points whose rule it asks about) and Phase B of
S-D11A reads one claim: the electricity cost of the drying machine, «CHF 85» as written, with no receipt.

The store-level seeds (``seed_phase_a``, ``update_model``, ``seed_frozen_copy``) serve deploy/preview/preview.py and tests
of the case service; the core-level ones (``prepared``, ``updated``) tests of the agent core, as tests/test_update.py."""
import copy
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
import hashlib
import tempfile
import time
from types import SimpleNamespace

from casepath.agents import core
from casepath.agents.azure_model import ModelError
from casepath.process import area
from casepath.process.items import build_items, items_sha256
from casepath.read.extract import extract
from tests.scripted import ScriptedModel, claim, report

WID = "mietmangel-handler"
D0 = date(2026, 8, 1)  # the claim; the A1 on d+1, the reply on d+13, the A4 on d+16, the two replies on d+35 (05.09.2026)
A5_AFTER = 38  # the A5 of the real shape: three days after the replies
SILENCE_DAYS = 91  # B-silence: the case looked at this long after the A5's dispatch
RECEIPTS_DAYS = 20  # B-receipts: the receipts come this long after the A5's dispatch
USER = "N. Kumar"
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
INSURER_MAIL = "schaden@example-rechtsschutz.ch"
BILL = "Stromabrechnung Bautrockner.txt"  # B-receipts: the bill attached to the reply

VARIANT_A = {"variant": "A", "label": "S-D11A", "title": "D11-Analogon A (synthetisch)", "reference": "4321.6011.0001",
             "kunde": "Sara Exempel", "mail": "sara.exempel@example.ch", "salutation": "Frau", "gp": "Immo Beispiel AG",
             "gp_address": "Hauptgasse 4, 3011 Bern", "address": "Ahornweg 12", "town": "3000 Bern", "shop": "Drogerie Exempel"}
VARIANT_B = {"variant": "B", "label": "S-D11B", "title": "D11-Analogon B (synthetisch)", "reference": "4321.6011.0002",
             "kunde": "Nina Probe", "mail": "nina.probe@example.ch", "salutation": "Frau", "gp": "Exempel Liegenschaften AG",
             "gp_address": "Bahnhofplatz 2, 3011 Bern", "address": "Birkenweg 5", "town": "3000 Bern", "shop": "Drogerie Probe"}


# -- days and how the documents write them --------------------------------------------------------------------------------

def long_day(d):
    """«5. September 2026»"""
    return f"{d.day}. {MONTHS[d.month - 1]} {d.year}"


def dotted(d):
    """«05.09.2026»"""
    return d.strftime("%d.%m.%Y")


def sent_line(d, at):
    """A forwarded mail's header day: «5. September 2026 09:12»."""
    return f"{long_day(d)} {at}"


def mail_date(d, at):
    """An e-mail's Date header for a day and a time in Bern («Sat, 05 Sep 2026 09:12:00 +0200»)."""
    hour, minute = (int(x) for x in at.split(":"))
    return format_datetime(datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone(timedelta(hours=2))))


# -- the files ---------------------------------------------------------------------------------------------------------------

def paged(fid, name, pages, segments):
    """A dossier as the reading stores it: its text with page marks and its documents (segments)."""
    text = "\n\n".join(f"[page {n}]\n{body}" for n, body in enumerate(pages, 1))
    return {"id": fid, "name": name, "kind": "pdf", "media_type": "application/pdf", "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "extraction": {"text": text, "pages": len(pages), "readable": True, "note": "", "segments": segments}}


def segment(first, last, day, sender, recipient, kind, title):
    return {"first_page": first, "last_page": last, "kind": kind, "date": dotted(day) if day else None, "sender": sender,
            "recipient": recipient, "title": title, "summary": ""}


def eml(sender, to, day, at, subject, body, attachments=()):
    """An e-mail as the handler saves it from the mailbox: its bytes (``attachments``: [(name, bytes)])."""
    m = EmailMessage()
    m["From"], m["To"], m["Date"], m["Subject"] = sender, to, mail_date(day, at), subject
    m.set_content(body)
    for name, data in attachments:
        m.add_attachment(data, maintype="text", subtype="plain", filename=name)
    return bytes(m)


def mail_file(fid, name, data):
    """An e-mail as the agent core gets it: its extraction as the upload reads it (attachments are files of their own)."""
    return {"id": fid, "name": name, "kind": "email", "media_type": "message/rfc822", "sha256": hashlib.sha256(data).hexdigest(),
            "extraction": extract(name, "message/rfc822", data)}


def text_file(fid, name, data):
    """A text file as the agent core gets it (an attachment saved as its own file)."""
    return {"id": fid, "name": name, "kind": "text", "media_type": "text/plain", "sha256": hashlib.sha256(data).hexdigest(),
            "extraction": extract(name, "text/plain", data)}


# -- what the scripted reader records -----------------------------------------------------------------------------------

def entry(n, fid, page, day, sender, to, kind, what, quote, **elements):
    return {"n": n, "file": fid, "page": page, "date": day.isoformat() if day else None, "from": sender, "to": to, "kind": kind,
            "phone": False, "what": what, "quote": quote, "asks": [], "answers": [], "terms": [], "paid": [], "next": [], **elements}


def ask(what, of, quote, by_date=None):
    return {"what": what, "of": of, "by": None, "by_date": by_date.isoformat() if by_date else None, "repeats": None, "warns": False, "quote": quote}


def answer(what, n, quote):
    return {"what": what, "answers": n, "quote": quote}


def promise(what, quote, by_date=None):
    return {"what": what, "who": "kunde", "by": None, "by_date": by_date.isoformat() if by_date else None, "quote": quote}


def fact(fid, name, value, quote):
    return ("record_fact", {"part": None, "fact": name, "status": "established", "value": value, "citations": [{"file": fid, "quote": quote}]})


def document(fid, name, quote):
    return ("record_document", {"document": name, "status": "present", "files": [fid], "citations": [{"file": fid, "quote": quote}], "note": ""})


def question(fid, text, about=()):
    """A question of the customer as the reader lists it, with the sentence that asks it and the key points whose rule it
    asks about (``about``, the reader's tags)."""
    return {"question": text, "citations": [{"file": fid, "quote": text}], "about": list(about)}


def full_turns(entries, facts, documents, request, parties, questions=()):
    """A full preparation of the handler's workflow: the reader (entries, facts, brief), the document finder, the result
    checker; the second reading and the source check answer by themselves (tests/scripted.py)."""
    return [[("record_steps", {"entries": copy.deepcopy(entries)}), *facts,
             report("claim_reader", request=request, parties=parties, questions=[dict(q) for q in questions])],
            [*documents, report("document_finder")], [report("result_checker", answer="Vorbereitet.")]]


def update_turns(entries, facts, summary, questions=(), timeline=(), documents=(), claims=()):
    """An update: the reader of the new documents (entries, changed facts, what they add, the questions and the costs
    claimed they state) and the document finder."""
    return [[("record_steps", {"entries": copy.deepcopy(entries)}), *facts,
             report("claim_reader", summary=summary, questions=[dict(q) for q in questions], timeline=[dict(t) for t in timeline],
                    claims=copy.deepcopy(list(claims)))],
            [*documents, report("document_finder")]]


# -- the episode -------------------------------------------------------------------------------------------------------------

def analog(d0=D0, names=None, dated_request=False):
    """The episode for a claim on ``d0``: the files, what the reader records and the scripted turns of each phase, the
    perturbations and the branches. ``names``: VARIANT_A (S-D11A) or VARIANT_B; ``dated_request``: the A4 sets a date, so
    the run holds a dated request still open on d+34 (the frozen study copy's)."""
    v = dict(names or VARIANT_A)
    k, gp, ref = v["kunde"], v["gp"], v["reference"]
    day = lambda n: d0 + timedelta(days=n)
    onset = (d0.replace(day=1) - timedelta(days=1)).replace(day=1)  # the month before the claim: «seit Anfang Juli»
    since = MONTHS[onset.month - 1]
    due = day(30) if dated_request else None  # the A4's date in the dated variant: still open on d+34
    fa = "fa"  # the dossier's id in the agent core's tests; a store gives its own (remapped)

    pages = [
        f"MIETVERTRAG FÜR WOHNRÄUME\nabgeschlossen in Bern am 15. März 2019\nVermieterin: {gp}, {v['gp_address']}\nMieterin: {k}\n"
        f"Mietobjekt: 3-Zimmer-Wohnung, {v['address']}, {v['town']}, 2. Stock\nMietbeginn: 1. April 2019",
        "Mietzins: CHF 1'650.– netto pro Monat; Nebenkosten akonto CHF 180.–; zahlbar monatlich im Voraus.",
        "Kündigung: Der Vertrag kann unter Einhaltung einer Frist von drei Monaten auf das Ende jedes Monats ausser Dezember gekündigt werden.",
        "Allgemeine Bestimmungen: Die Mieterin meldet Mängel, die sie nicht selbst beseitigen muss, der Verwaltung umgehend schriftlich.",
        f"Unterschriften\nFür die Vermieterin: {gp}\nDie Mieterin: {k}",
        # d0: the claim, forwarded by the insurer's inbox
        f"Weitergeleitet vom Posteingang Schaden\nVon: {k} <{v['mail']}>\nGesendet: {sent_line(day(0), '10:14')}\nAn: Protekta Rechtsschutz\n"
        f"Betreff: Schimmel in meiner Wohnung\n\nGuten Tag\nIn meiner Wohnung am {v['address']} in Bern wächst seit Anfang {since} im "
        f"Schlafzimmer und im Bad schwarzer Schimmel. Ich habe es der Verwaltung gemeldet, aber es passiert nichts. Was kann ich tun?\n"
        f"Freundliche Grüsse\n{k}",
        # d+1: the A1, four documents and one question
        f"Von: Protekta Rechtsschutz <{INSURER_MAIL}>\nGesendet: {sent_line(day(1), '08:05')}\nAn: {k}\nBetreff: Ihr Schadenfall {ref}\n\n"
        f"Guten Tag {k}\nVielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist unter der Referenz {ref} provisorisch registriert.\n"
        "Um die Versicherungsdeckung prüfen und die Sach- und Rechtslage beurteilen zu können, brauchen wir insbesondere noch:\n"
        "– Mietvertrag\n– sämtliche Korrespondenz mit der Verwaltung\n– Liste der beschädigten Gegenstände\n– kurze Schilderung des Sachverhalts\n"
        "Weiter bitten wir Sie um die Beantwortung folgender Frage:\n– Haben Sie den Mangel der Verwaltung schriftlich gemeldet?\n"
        "Freundliche Grüsse\nProtekta Rechtsschutz",
        # d+13: the reply with the forwarded correspondence (and the receipt, filed as its own document)
        f"Von: {k} <{v['mail']}>\nGesendet: {sent_line(day(13), '19:22')}\nAn: Protekta Rechtsschutz\nBetreff: AW: Ihr Schadenfall {ref}\n\n"
        f"Guten Tag\nAnbei sende ich Ihnen den Mietvertrag und meine Korrespondenz mit der Verwaltung. Beiliegend finden Sie auch die Liste der "
        f"beschädigten Gegenstände. Zum Sachverhalt: Seit Anfang {since} wächst im Schlafzimmer und im Bad Schimmel; der Hauswart der Verwaltung "
        f"meint, ich lüfte zu wenig. Den Schimmel habe ich der Verwaltung am {long_day(day(-12))} schriftlich gemeldet. Ich möchte, dass der "
        f"Schimmel fachgerecht entfernt wird. Die Quittung für den Schimmelentferner liegt bei.\nFreundliche Grüsse\n{k}",
        f"---------- Weitergeleitete Nachricht ----------\nVon: {k}\nGesendet: {sent_line(day(-12), '21:05')}\nAn: {gp}, Verwaltung\n"
        f"Betreff: Schimmel {v['address']}\n\nSehr geehrte Damen und Herren\nIm Schlafzimmer und im Bad meiner Wohnung am {v['address']} bildet "
        f"sich seit Anfang {since} schwarzer Schimmel. Ich bitte Sie, den Mangel zu beheben.\nFreundliche Grüsse\n{k}",
        f"---------- Weitergeleitete Nachricht ----------\nVon: {gp}\nGesendet: {sent_line(day(-8), '11:40')}\nAn: {k}\nBetreff: AW: Schimmel\n\n"
        f"Guten Tag\nWir haben Ihre Meldung erhalten. Unser Hauswart kommt am {long_day(day(-4))} vorbei und schaut sich die Sache an.\n"
        f"Freundliche Grüsse\n{gp}",
        f"---------- Weitergeleitete Nachricht ----------\nVon: {k}\nGesendet: {sent_line(day(3), '18:02')}\nAn: {gp}, Verwaltung\nBetreff: AW: Schimmel\n\n"
        f"Guten Tag\nDer Hauswart war da, aber am Schimmel hat sich nichts geändert. Bitte teilen Sie mir mit, was Sie unternehmen.\n"
        f"Freundliche Grüsse\n{k}",
        f"---------- Weitergeleitete Nachricht ----------\nVon: {gp}\nGesendet: {sent_line(day(6), '09:15')}\nAn: {k}\nBetreff: AW: Schimmel\n\n"
        f"Guten Tag\nNach Auskunft des Hauswarts wird in der Wohnung zu wenig gelüftet. Wir stellen Ihnen einen Bautrockner zur Verfügung.\n"
        f"Freundliche Grüsse\n{gp}",
        f"---------- Weitergeleitete Nachricht ----------\nVon: {k}\nGesendet: {sent_line(day(7), '20:30')}\nAn: {gp}, Verwaltung\nBetreff: AW: Schimmel\n\n"
        f"Guten Tag\nIch lüfte täglich mehrmals. Der Schimmel kommt aus der Aussenwand. Ich erwarte, dass Sie die Ursache beheben.\n"
        f"Freundliche Grüsse\n{k}",
        "Liste der beschädigten Gegenstände\n– Duschvorhang (verschimmelt)\n– Badematte (verschimmelt)\n– Vorhang im Schlafzimmer (Stockflecken)",
        f"Lüftungsprotokoll der Mieterin, {since}\nMorgens und abends je zehn Minuten Stosslüften in allen Zimmern; auch an den Wochenenden. "
        "Der Schimmel kehrt nach dem Abwaschen innert weniger Tage zurück.",
        # d+16: the A4, one point and two questions (no date set)
        f"Von: Protekta Rechtsschutz <{INSURER_MAIL}>\nGesendet: {sent_line(day(16), '10:41')}\nAn: {k}\nBetreff: Rückfrage zu Ihrem Schadenfall {ref}\n\n"
        f"Guten Tag {k}\nVielen Dank für Ihre Unterlagen.\nDamit wir weiterfahren können, bitten wir Sie um Auskunft zu folgendem Punkt, "
        "dem heutigen Stand des Mangels:\n– Besteht der Schimmel nach den Massnahmen der Verwaltung weiterhin?\n"
        "– Wie hat die Verwaltung auf Ihre letzte Meldung reagiert?\n" + (f"Bitte antworten Sie uns bis {long_day(due)}.\n" if due else "")
        + "Freundliche Grüsse\nProtekta Rechtsschutz",
        # undated: the management's message as a screenshot, the shop's receipt, four photos
        f"[Bildschirmfoto einer Nachricht]\nVon: {gp}\nAn: {k}\nDer Bautrockner wird nächste Woche geliefert. Bitte lassen Sie ihn durchgehend laufen.",
        f"{v['shop']}, Marktgasse 9, 3011 Bern\nQuittung Nr. 4711\n1 Schimmelentferner Spray 500 ml  CHF 18.90\n1 Fugenbürste  CHF 6.50\n"
        "Total CHF 25.40\nBar bezahlt. Vielen Dank für Ihren Einkauf.",
        "[Foto] Schwarzer Schimmel in der Ecke über dem Schlafzimmerfenster.",
        "[Foto] Schimmelflecken an der Aussenwand hinter dem Bett.",
        "[Foto] Schimmel an der Silikonfuge der Badewanne.",
        "[Foto] Bautrockner im Schlafzimmer, daneben ein Feuchtigkeitsmesser.",
    ]
    segments = [segment(1, 5, date(2019, 3, 15), gp, k, "Mietvertrag", "Mietvertrag"),
                segment(6, 6, day(0), k, "Protekta", "E-Mail", "Schadenmeldung"),
                segment(7, 7, day(1), "Protekta", k, "E-Mail", "Anforderung"),
                segment(8, 15, day(13), k, "Protekta", "E-Mail", "Antwort mit weitergeleiteter Korrespondenz"),
                segment(16, 16, day(16), "Protekta", k, "E-Mail", "Rückfrage"),
                segment(17, 17, None, gp, k, "E-Mail (Bildschirmfoto)", "Nachricht der Verwaltung"),
                segment(18, 18, None, v["shop"], k, "Kaufbeleg", "Quittung"),
                *[segment(p, p, None, k, None, "Foto", "Foto") for p in range(19, 23)]]
    dossier = paged(fa, f"Akte {v['title'].split(' (')[0]}.pdf", pages, segments)

    entries_a = [
        entry(1, fa, 1, date(2019, 3, 15), "gegenpartei", "kunde", "andere", f"Mietvertrag {v['address']}", "MIETVERTRAG FÜR WOHNRÄUME"),
        entry(2, fa, 6, day(0), "kunde", "versicherer", "meldung", "Meldung: Schimmel in der Wohnung", "Betreff: Schimmel in meiner Wohnung"),
        entry(3, fa, 7, day(1), "versicherer", "kunde", "anforderung", "Unterlagen und eine Angabe verlangt", f"Betreff: Ihr Schadenfall {ref}",
              asks=[ask("Mietvertrag", "kunde", "– Mietvertrag"),
                    ask("Sämtliche Korrespondenz mit der Verwaltung", "kunde", "– sämtliche Korrespondenz mit der Verwaltung"),
                    ask("Liste der beschädigten Gegenstände", "kunde", "– Liste der beschädigten Gegenstände"),
                    ask("Kurze Schilderung des Sachverhalts", "kunde", "– kurze Schilderung des Sachverhalts"),
                    ask("Schriftliche Meldung des Mangels?", "kunde", "– Haben Sie den Mangel der Verwaltung schriftlich gemeldet?")]),
        entry(4, fa, 8, day(13), "kunde", "versicherer", "unterlagen", "Mietvertrag und Korrespondenz mit der Verwaltung zugestellt",
              f"Betreff: AW: Ihr Schadenfall {ref}",
              answers=[answer("Mietvertrag", 3, "Anbei sende ich Ihnen den Mietvertrag"),
                       answer("Korrespondenz mit der Verwaltung", 3, "Anbei sende ich Ihnen den Mietvertrag und meine Korrespondenz mit der Verwaltung."),
                       answer("Liste der beschädigten Gegenstände", 3, "Beiliegend finden Sie auch die Liste der beschädigten Gegenstände."),
                       answer("Schilderung des Sachverhalts", 3, f"Zum Sachverhalt: Seit Anfang {since} wächst im Schlafzimmer und im Bad Schimmel"),
                       answer(f"Mangel schriftlich gemeldet am {dotted(day(-12))}", 3,
                              f"Den Schimmel habe ich der Verwaltung am {long_day(day(-12))} schriftlich gemeldet.")]),
        entry(5, fa, 9, day(-12), "kunde", "gegenpartei", "andere", "Mängelrüge an die Verwaltung", f"Betreff: Schimmel {v['address']}",
              asks=[ask("Mangel beheben", "gegenpartei", "Ich bitte Sie, den Mangel zu beheben.")]),
        entry(6, fa, 10, day(-8), "gegenpartei", "kunde", "antwort", "Verwaltung kündigt den Hauswart an",
              "Wir haben Ihre Meldung erhalten. Unser Hauswart kommt"),
        entry(7, fa, 11, day(3), "kunde", "gegenpartei", "andere", "Schimmel nach dem Besuch des Hauswarts unverändert",
              "Der Hauswart war da, aber am Schimmel hat sich nichts geändert."),
        entry(8, fa, 12, day(6), "gegenpartei", "kunde", "antwort", "Verwaltung: zu wenig gelüftet; ein Bautrockner wird gestellt",
              "Wir stellen Ihnen einen Bautrockner zur Verfügung."),
        entry(9, fa, 13, day(7), "kunde", "gegenpartei", "andere", "Mieterin bestreitet, zu wenig zu lüften", "Ich lüfte täglich mehrmals."),
        entry(10, fa, 16, day(16), "versicherer", "kunde", "anforderung", "Rückfrage zum Stand des Mangels",
              f"Betreff: Rückfrage zu Ihrem Schadenfall {ref}",
              asks=[ask("Besteht der Schimmel weiterhin?", "kunde", "– Besteht der Schimmel nach den Massnahmen der Verwaltung weiterhin?", due),
                    ask("Reaktion der Verwaltung auf die letzte Meldung", "kunde", "– Wie hat die Verwaltung auf Ihre letzte Meldung reagiert?", due)]),
        entry(11, fa, 17, None, "gegenpartei", "kunde", "andere", "Nachricht der Verwaltung zum Bautrockner (Bildschirmfoto)",
              "Der Bautrockner wird nächste Woche geliefert."),
        entry(12, fa, 18, None, "andere", "kunde", "andere", f"Quittung der {v['shop']}", "Quittung Nr. 4711"),
    ]
    facts_a = [fact(fa, "rechtsgebiet", "Mietrecht / Mangel", "im Schlafzimmer und im Bad schwarzer Schimmel"),
               fact(fa, "gegenpartei", gp, f"Vermieterin: {gp}"),
               fact(fa, "mietbeginn", "2019-04-01", "Mietbeginn: 1. April 2019"),
               fact(fa, "mangel_seit", onset.strftime("%Y-%m"), f"wächst seit Anfang {since} im"),
               fact(fa, "maengelruege_schriftlich", "ja", f"Den Schimmel habe ich der Verwaltung am {long_day(day(-12))} schriftlich gemeldet."),
               fact(fa, "will_beseitigung", "ja", "Ich möchte, dass der Schimmel fachgerecht entfernt wird.")]
    documents_a = [document(fa, "mietvertrag", "MIETVERTRAG FÜR WOHNRÄUME"),
                   document(fa, "maengelruege", "Ich bitte Sie, den Mangel zu beheben."),
                   document(fa, "fotos", "[Foto] Schwarzer Schimmel in der Ecke über dem Schlafzimmerfenster.")]
    request = f"{k} möchte, dass die Verwaltung den Schimmel in ihrer Wohnung am {v['address']} fachgerecht entfernt."
    parties = [{"role": "Mieterin (VN)", "name": f"{v['salutation']} {k}"}, {"role": "Verwaltung (GP)", "name": gp}]

    # Phase B: the two replies of d+35 (A's wording follows SLICE_A «Expected for S-D11A»; B's: the deposit only, receipts promised)
    to = f"Protekta Rechtsschutz <{INSURER_MAIL}>"
    sender = f"{k} <{v['mail']}>"
    fb, fc = "fb", "fc"
    if v["variant"] == "A":
        body_1 = (f"Guten Tag\n\nGerne beantworte ich Ihre Rückfrage vom {dotted(day(16))}.\nDer Schimmel ist immer noch da. Die Verwaltung hat "
                  "einen Bautrockner aufgestellt und lehnt weitere Massnahmen ab. Ihre letzte Nachricht leite ich Ihnen unten weiter.\n"
                  "Den Mietzins zahle ich bisher vollständig. Muss ich weiterhin die volle Miete bezahlen? Darf ich die Miete hinterlegen?\n\n"
                  f"Freundliche Grüsse\n{k}\n\n"
                  f"---------- Weitergeleitete Nachricht ----------\nVon: {gp}\nGesendet: {sent_line(day(33), '16:20')}\nAn: {k}\nBetreff: AW: Schimmel\n\n"
                  "Guten Tag\nDer Bautrockner läuft seit drei Wochen. Weitere Massnahmen sind aus unserer Sicht nicht nötig; bitte lüften Sie "
                  f"regelmässig.\nFreundliche Grüsse\n{gp}")
        body_2 = ("Guten Tag\n\nNoch eine Ergänzung zu meiner Nachricht von heute Morgen: Eine Mietzinsreduktion möchte ich nicht. Die Stromkosten "
                  "für den Bautrockner von rund CHF 85 möchte ich ersetzt haben. Werden mir die Stromkosten für den Bautrockner ersetzt?\n\n"
                  f"Freundliche Grüsse\n{k}")
        questions_b = ["Muss ich weiterhin die volle Miete bezahlen?", "Darf ich die Miete hinterlegen?",
                       "Werden mir die Stromkosten für den Bautrockner ersetzt?"]
        entries_b = [
            entry(13, fb, None, day(35), "kunde", "versicherer", "antwort", "Antwort auf die Rückfrage: Schimmel besteht, Verwaltung lehnt ab",
                  f"Subject: AW: Rückfrage zu Ihrem Schadenfall {ref}",
                  answers=[answer("Schimmel besteht weiterhin", 10, "Der Schimmel ist immer noch da."),
                           answer("Reaktion der Verwaltung: Bautrockner aufgestellt, weitere Massnahmen abgelehnt", 10,
                                  "Die Verwaltung hat einen Bautrockner aufgestellt und lehnt weitere Massnahmen ab.")],
                  asks=[ask(q, "versicherer", q) for q in questions_b[:2]]),
            entry(14, fb, None, day(33), "gegenpartei", "kunde", "antwort", "Verwaltung: weitere Massnahmen nicht nötig",
                  "Der Bautrockner läuft seit drei Wochen."),
            entry(15, fc, None, day(35), "kunde", "versicherer", "antwort", "Nachtrag: keine Herabsetzung, Ersatz der Stromkosten verlangt",
                  f"Subject: Nachtrag: Rückfrage zu Ihrem Schadenfall {ref}", asks=[ask(questions_b[2], "versicherer", questions_b[2])])]
        facts_b = [fact(fb, "mangel_besteht", "ja", "Der Schimmel ist immer noch da."),
                   fact(fb, "reaktion_vermieter", "Abgelehnt / offene Punkte", "Die Verwaltung hat einen Bautrockner aufgestellt und lehnt weitere Massnahmen ab."),
                   fact(fb, "streit_mietzins", "nein", "Den Mietzins zahle ich bisher vollständig."),
                   fact(fc, "will_reduktion", "nein", "Eine Mietzinsreduktion möchte ich nicht."),
                   fact(fc, "will_schadenersatz", "ja", "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben.")]
        summary_b = ("Die Kundschaft beantwortet die Rückfrage: Der Schimmel besteht, die Verwaltung lehnt weitere Massnahmen ab; sie fragt nach "
                     "dem Mietzins, der Hinterlegung und dem Ersatz der Stromkosten.")
        asked_in = [fb, fb, fc]
        tags = [["hinterlegung"], ["hinterlegung"], ["schadenersatz"]]  # the reader's tags: the rule each question asks about
        claims_b = [claim("Stromkosten für den Bautrockner", "Die Stromkosten für den Bautrockner von rund CHF 85 möchte ich ersetzt haben.",
                          amount="CHF 85", file=fc, kind="Energie")]
    else:
        body_1 = (f"Guten Tag\n\nGerne beantworte ich Ihre Rückfrage vom {dotted(day(16))}.\nDer Schimmel ist immer noch da. Auf meine letzte Meldung "
                  "hat die Verwaltung nicht mehr reagiert.\nDen Mietzins zahle ich bisher vollständig. Darf ich die Miete hinterlegen?\n\n"
                  f"Freundliche Grüsse\n{k}")
        body_2 = ("Guten Tag\n\nNoch ein Nachtrag: Ersatz verlange ich vorerst keinen. Die Quittungen für den Luftentfeuchter reiche ich nach.\n\n"
                  f"Freundliche Grüsse\n{k}")
        questions_b = ["Darf ich die Miete hinterlegen?"]
        entries_b = [
            entry(13, fb, None, day(35), "kunde", "versicherer", "antwort", "Antwort auf die Rückfrage: Schimmel besteht, keine Reaktion der Verwaltung",
                  f"Subject: AW: Rückfrage zu Ihrem Schadenfall {ref}",
                  answers=[answer("Schimmel besteht weiterhin", 10, "Der Schimmel ist immer noch da."),
                           answer("Reaktion der Verwaltung: keine", 10, "Auf meine letzte Meldung hat die Verwaltung nicht mehr reagiert.")],
                  asks=[ask(questions_b[0], "versicherer", questions_b[0])]),
            entry(14, fc, None, day(35), "kunde", "versicherer", "antwort", "Nachtrag: Quittungen folgen",
                  f"Subject: Nachtrag: Rückfrage zu Ihrem Schadenfall {ref}",
                  next=[promise("Quittungen für den Luftentfeuchter nachreichen", "Die Quittungen für den Luftentfeuchter reiche ich nach.")])]
        facts_b = [fact(fb, "mangel_besteht", "ja", "Der Schimmel ist immer noch da."),
                   fact(fb, "reaktion_vermieter", "Keine Reaktion", "Auf meine letzte Meldung hat die Verwaltung nicht mehr reagiert."),
                   fact(fb, "streit_mietzins", "nein", "Den Mietzins zahle ich bisher vollständig."),
                   fact(fc, "will_schadenersatz", "nein", "Ersatz verlange ich vorerst keinen.")]
        summary_b = ("Die Kundschaft beantwortet die Rückfrage: Der Schimmel besteht, die Verwaltung reagiert nicht; sie fragt nach der "
                     "Hinterlegung und reicht Quittungen nach.")
        asked_in = [fb]
        tags = [["hinterlegung"]]
        claims_b = []  # she claims nothing yet («Ersatz verlange ich vorerst keinen»)
    reply_1 = ("AW Rueckfrage.eml", eml(sender, to, day(35), "09:12", f"AW: Rückfrage zu Ihrem Schadenfall {ref}", body_1))
    reply_2 = ("Nachtrag.eml", eml(sender, to, day(35), "18:40", f"Nachtrag: Rückfrage zu Ihrem Schadenfall {ref}", body_2))
    files_b = [mail_file(fb, *reply_1), mail_file(fc, *reply_2)]
    questions = [question(f, q, about) for f, q, about in zip(asked_in, questions_b, tags)]
    timeline_b = [{"date": dotted(day(35)), "event": "Antwort der Kundschaft auf die Rückfrage",
                   "citations": [{"file": fb, "quote": f"Gerne beantworte ich Ihre Rückfrage vom {dotted(day(16))}."}]}]

    a5 = day(A5_AFTER)
    ns = SimpleNamespace(
        names=v, label=v["label"], title=f"{v['title']} {ref}", reference=ref, d0=d0, day=day, a5_day=a5,
        # Phase A: the file as it stood on d+34
        dossier=dossier, entries_a=entries_a, facts_a=facts_a, documents_a=documents_a, request=request, parties=parties,
        turns_a=lambda: full_turns(entries_a, facts_a, documents_a, request, parties),
        # Phase B: the two replies of d+35
        replies=[reply_1, reply_2], reply_names={fb: reply_1[0], fc: reply_2[0]}, files_b=files_b, entries_b=entries_b, facts_b=facts_b,
        questions_b=questions, claims_b=claims_b,
        summary_b=summary_b, timeline_b=timeline_b,
        turns_b=lambda: update_turns(entries_b, facts_b, summary_b, questions, timeline_b, claims=claims_b),
    )
    ns.perturbations = perturbations(ns)
    ns.branches = branches(ns)
    return ns


def perturbations(ns):
    """The labelled perturbations of the episode, each with what a test needs to apply it."""
    v, k, ref, day = ns.names, ns.names["kunde"], ns.reference, ns.day
    sender, to = f"{k} <{v['mail']}>", f"Protekta Rechtsschutz <{INSURER_MAIL}>"
    promised = "Die Belege zu den Stromkosten für den Bautrockner reiche ich nach."
    retract_1 = ("Belege Stromkosten.eml", eml(sender, to, day(36), "08:30", f"Belege Stromkosten {ref}", f"Guten Tag\n\n{promised}\n\nFreundliche Grüsse\n{k}"))
    withdrawn = "Ich ziehe meine Forderung für die Stromkosten zurück."
    retract_2 = ("Forderung zurueckgezogen.eml", eml(sender, to, day(37), "17:05", f"AW: Belege Stromkosten {ref}",
                                                    f"Guten Tag\n\n{withdrawn} Die Verwaltung hat mir die Stromkosten für den Bautrockner inzwischen selbst "
                                                    f"vergütet.\n\nFreundliche Grüsse\n{k}\n\n> {promised}"))
    refused = "Für die Stromkosten habe ich keine Belege."
    refuse = ("Keine Belege.eml", eml(sender, to, ns.a5_day + timedelta(days=5), "07:55", f"AW: Rechtliche Einschätzung {ref}",
                                      f"Guten Tag\n\n{refused} Die Abrechnung des Elektrizitätswerks kommt erst Ende Jahr.\n\nFreundliche Grüsse\n{k}"))

    def retract_turns(first=16):
        """The two later replies, each read by its own update: the promise (a next step, no date), then the withdrawal with
        the promise quoted below it (the wish for compensation is no longer true)."""
        return (update_turns([entry(first, "fd", None, day(36), "kunde", "versicherer", "antwort", "Belege der Stromkosten angekündigt",
                                    f"Subject: Belege Stromkosten {ref}", next=[promise("Belege zu den Stromkosten nachreichen", promised)])],
                             [], "Die Kundschaft kündigt die Belege der Stromkosten an."),
                update_turns([entry(first + 1, "fe", None, day(37), "kunde", "versicherer", "antwort", "Forderung für die Stromkosten zurückgezogen",
                                    f"Subject: AW: Belege Stromkosten {ref}")],
                             [fact("fe", "will_schadenersatz", "nein", withdrawn)], "Die Kundschaft zieht die Forderung für die Stromkosten zurück."))

    def refuse_turns(first, answers_n):
        """The refusal read by an update: an answer to the entry ``answers_n`` (the A5's dispatch) that delivers nothing."""
        return update_turns([entry(first, "fr", None, ns.a5_day + timedelta(days=5), "kunde", "versicherer", "antwort", "Keine Belege der Stromkosten",
                                   f"Subject: AW: Rechtliche Einschätzung {ref}", answers=[answer("Belege zu den Stromkosten", answers_n, refused)])],
                            [], "Die Kundschaft hat keine Belege der Stromkosten.")

    return {
        "P-dup": SimpleNamespace(label="P-dup", what="the first reply of d+35 uploaded again: the same bytes", name=ns.replies[0][0],
                                 data=ns.replies[0][1]),
        "P-contra": SimpleNamespace(label="P-contra", what="«Mangel behoben» set after the approval",
                                    edit={"op": "set_fact", "args": {"fact": "mangel_besteht", "value": "nein"}, "reason": "Mangel behoben (Telefon mit der Kundin)",
                                          "reason_code": "1", "recheck": False}),
        "P-retract": SimpleNamespace(label="P-retract", what="the receipts promised («reiche ich nach»), then the claim withdrawn, the promise quoted",
                                     files=[retract_1, retract_2], ids=["fd", "fe"], quote=withdrawn, turns=retract_turns,
                                     core_files=[mail_file("fd", *retract_1), mail_file("fe", *retract_2)]),
        "P-refuse": SimpleNamespace(label="P-refuse", what="a reply after the A5 that has no receipts", files=[refuse], ids=["fr"], quote=refused,
                                    turns=refuse_turns, core_files=[mail_file("fr", *refuse)]),
        "P-fail": SimpleNamespace(label="P-fail", what="the update's model fails (ModelError)", model=Failing),
        "P-restart": SimpleNamespace(label="P-restart", what="an update left running, the store reopened", leave=leave_running, reopen=reopen),
    }


def branches(ns):
    """The two ways the case goes on after the A5 is dispatched on ``a5_day`` (the real shape's d+38 by default)."""
    v, k, ref = ns.names, ns.names["kunde"], ns.reference
    sender, to = f"{k} <{v['mail']}>", f"Protekta Rechtsschutz <{INSURER_MAIL}>"

    def receipts(a5_day=None):
        """B-receipts: the customer's reply with the electricity bill attached and the A5 quoted below it, as saved from the
        mailbox: [(name, bytes)] (the upload makes the bill a file of its own)."""
        a5_day = a5_day or ns.a5_day
        came = a5_day + timedelta(days=RECEIPTS_DAYS)
        body = (f"Guten Tag\n\nStromabrechnung anbei.\n\nFreundliche Grüsse\n{k}\n\n-----Ursprüngliche Nachricht-----\nVon: Protekta Rechtsschutz\n"
                f"Gesendet: {sent_line(a5_day, '14:05')}\nAn: {k}\nBetreff: Rechtliche Einschätzung {ref}\n\n> Bitte reichen Sie uns noch nach:\n"
                "> – Belege zu: Stromkosten für den Bautrockner")
        return [("Belege Stromkosten.eml", eml(sender, to, came, "11:20", f"AW: Rechtliche Einschätzung {ref}", body, attachments=[(BILL, bill())]))]

    def bill():
        return (f"Energie Beispiel AG\nZusatzabrechnung Zähler 08-4411, {v['address']}, {v['town']}\nVerbrauch Bautrockner "
                f"{dotted(ns.day(6))} bis {dotted(ns.day(34))}: 212 kWh\nBetrag: CHF 85.40\nZahlbar innert 30 Tagen.").encode()

    def receipts_core(a5_day=None):
        """B-receipts as the agent core gets them: the e-mail («fs») and the bill attached to it, a file of its own («ft»)."""
        (name, data), = receipts(a5_day)
        attached = text_file("ft", BILL, bill())
        attached["extraction"]["attached_to"] = name
        return [mail_file("fs", name, data), attached]

    def receipts_turns(first, answers_n, a5_day=None):
        """B-receipts read by an update: the reply (answering the entry ``answers_n``, the A5's dispatch), the A5 as quoted
        below it (an entry of Protekta dated the dispatch day), and the bill attached as its own file."""
        a5_day = a5_day or ns.a5_day
        came = a5_day + timedelta(days=RECEIPTS_DAYS)
        return update_turns([
            entry(first, "fs", None, came, "kunde", "versicherer", "unterlagen", "Stromabrechnung zugestellt", f"Subject: AW: Rechtliche Einschätzung {ref}",
                  answers=[answer("Stromabrechnung", answers_n, "Stromabrechnung anbei.")]),
            entry(first + 1, "fs", None, a5_day, "versicherer", "kunde", "einschaetzung", "Rechtliche Einschätzung (zitiert)",
                  f"Betreff: Rechtliche Einschätzung {ref}",
                  asks=[ask("Belege zu: Stromkosten für den Bautrockner", "kunde", "> – Belege zu: Stromkosten für den Bautrockner")]),
            entry(first + 2, "ft", None, None, "andere", "kunde", "andere", "Stromabrechnung Bautrockner CHF 85.40", "Betrag: CHF 85.40")],
            [], "Die Kundschaft reicht die Stromabrechnung für den Bautrockner ein.",
            # the cost claimed before, in the words of the request that asked its receipts, with the bill and what it documents
            claims=[claim("Stromkosten für den Bautrockner", "Stromabrechnung anbei.", file="fs", kind="Energie",
                          receipt={"file": "ft", "quote": "Betrag: CHF 85.40", "expense": "Verbrauch Bautrockner", "kind": "Energie",
                                   "party": "Energie Beispiel AG", "payer": "kunde", "transaction": "08-4411",
                                   "period": {"from": ns.day(6).isoformat(), "to": ns.day(34).isoformat()},
                                   "amount": "CHF 85.40", "role": "requested"})])

    return {
        "B-silence": SimpleNamespace(label="B-silence", what="nothing from the customer: the case looked at A5 + 91 days", days=SILENCE_DAYS,
                                     day=lambda a5_day=None: (a5_day or ns.a5_day) + timedelta(days=SILENCE_DAYS)),
        "B-receipts": SimpleNamespace(label="B-receipts", what="the receipts arrive A5 + 20 days, the A5 quoted below", days=RECEIPTS_DAYS,
                                      files=receipts, core_files=receipts_core, ids=["fs", "ft"], turns=receipts_turns),
    }


# -- P-fail and P-restart ---------------------------------------------------------------------------------------------------

class Failing(ScriptedModel):
    """P-fail: a model that fails on its first call, as an unreachable deployment does."""

    def __init__(self, turns=()):
        super().__init__(list(turns))

    def respond(self, **kwargs):
        raise ModelError("transport", "Das Modell war nicht erreichbar (synthetischer Fehler P-fail).")

    def respond_json(self, **kwargs):
        raise ModelError("transport", "Das Modell war nicht erreichbar (synthetischer Fehler P-fail).")


def leave_running(store, case_id, user=USER):
    """P-restart: an update of the case left «running», as a service stopped in the middle leaves it."""
    base = store.latest_run(case_id, "completed")
    run = store.create_run(case_id, user, kind="update", builds_on=base["id"])
    return store.update_run(run["id"], status="running")


def reopen(store):
    """P-restart: the store closed and opened again on its directory, as after a restart (a RunService made on it marks
    the unfinished run «interrupted»)."""
    from casepath.web.store import CaseStore
    root = store.root
    store.close()
    return CaseStore(root)


# -- in the agent core (as tests/test_update.py) -----------------------------------------------------------------------------

EPISODE = analog()  # S-D11A on the days the tests and deploy/preview/episode use


def case_row(ns=EPISODE):
    return {"id": "case_s_d11a", "title": ns.title, "intake": {"synthetic": True}, "workflow_id": WID}


def job(ns, files, edits=()):
    return {"format": core.JOB, "case": case_row(ns), "files": copy.deepcopy(files), "workflows": [area.workflow(WID)], "knowledge": [],
            "edits": list(edits), "options": {"read_scans": False}}


def prepared(ns=EPISODE, edits=()):
    """Phase A prepared by the scripted team: the prior run an update builds on, and its model."""
    model = ScriptedModel(ns.turns_a())
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.prepare(job(ns, [ns.dossier], edits), model, core.DirectoryBlobs(blobs))
    assert outcome["status"] == "completed", outcome.get("error")
    return {"id": "run_a", "workflow_id": WID, "workflow_version": outcome["workflow"]["version"], "routing": outcome["routing"],
            "result": outcome["result"]}, model


def updated(prior, files, turns, ns=EPISODE, edits=(), model=None):
    """An update of ``prior`` with ``files`` (all of the case's) by the scripted ``turns``: (outcome, model)."""
    model = model or ScriptedModel(turns)
    with tempfile.TemporaryDirectory() as blobs:
        outcome = core.update(job(ns, files, edits), prior, model, core.DirectoryBlobs(blobs))
    return outcome, model


def looked_at(files, day):
    """The files as the case view evaluates them on ``day``."""
    return [{**f, "extraction": {**f["extraction"], "cut_of": {"as_of": day.isoformat()}}} for f in files]


def view(result, files, day, edits=()):
    """The case's state and items as the case view builds them on ``day``."""
    files = looked_at(files, day)
    state = core.evaluate(area.workflow(WID), [], list(edits), result, case_row()["id"], files=files)
    return state, build_items(state, result, files)


def decided(*pairs):
    return [{"id": f"e{i}", "op": "set_fact", "args": {"fact": f, "value": v}, "by": "handler", "status": "active"} for i, (f, v) in enumerate(pairs)]


# -- in a case store (deploy/preview, tests of the case service) -------------------------------------------------------------

def _remap(value, ids):
    """A scripted turn's file ids («fa», «fb» …) replaced by the store's."""
    if isinstance(value, dict):
        return {k: _remap(x, ids) for k, x in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_remap(x, ids) for x in value)
    return ids.get(value, value) if isinstance(value, str) else value


def store_dossier(store, case_id, ns=EPISODE, user=USER):
    """The Phase A dossier stored as a text file with its pages and documents, so its original opens; returns its id."""
    ex = ns.dossier["extraction"]
    return store.add_file(case_id, ns.dossier["name"].replace(".pdf", ".txt"), "text/plain", "text", ex["text"].encode(),
                          {**ex, "media_type": "text/plain", "kind": "text"}, user)["id"]


def wait(store, run_id, seconds=30):
    end = time.time() + seconds
    while store.get_run(run_id)["status"] in ("queued", "running") and time.time() < end:
        time.sleep(0.05)
    return store.get_run(run_id)


def seed_phase_a(store, runs, ns=EPISODE, title=None, user=USER):
    """A case of the handler's workflow holding the Phase A dossier, prepared by the scripted team (the run service's model
    is set for this run only). Returns the case; its replies (``ns.replies``) are dropped on it to start Phase B."""
    case = store.create_case(title or ns.title, {"synthetic": True, "dossier": ns.label}, user)
    fid = store_dossier(store, case["id"], ns, user)
    store.select_workflow(case["id"], WID, None, user)
    before = runs.model_factory
    runs.model_factory = lambda token=None: ScriptedModel(_remap(ns.turns_a(), {"fa": fid}))
    try:
        run = wait(store, runs.start(case["id"], user)["id"])
    finally:
        runs.model_factory = before
    assert run["status"] == "completed", run.get("error")
    return store.get_case(case["id"])


def unread_ids(store, case_id):
    """The case's files its latest completed run did not read, in the order they came."""
    base = store.latest_run(case_id, "completed")
    read = set(((base or {}).get("result") or {}).get("read_files") or ())
    return [f["id"] for f in store.list_files(case_id) if f["id"] not in read]


def update_model(store, case_id, turns, names, pause=0.0):
    """The scripted model of an update of the case: ``turns`` with their file ids («fb», «fc» …) mapped to the case's unread
    files, by name (``names``: {id: file name}, as ``reply_names``), else in the order the files came. ``pause``: seconds per
    call (the preview's live view)."""
    unread = set(unread_ids(store, case_id))
    new = [f for f in store.list_files(case_id) if f["id"] in unread]
    ids = {}
    for placeholder, name in names.items():
        match = next((f["id"] for f in new if f["name"] == name and f["id"] not in ids.values()), None)
        if match:
            ids[placeholder] = match
    rest = [f["id"] for f in new if f["id"] not in ids.values()]
    for placeholder in names:
        if placeholder not in ids and rest:
            ids[placeholder] = rest.pop(0)
    model = ScriptedModel(_remap(turns, ids))
    if pause:
        respond, respond_json = model.respond, model.respond_json
        model.respond = lambda **kw: (time.sleep(pause), respond(**kw))[1]
        model.respond_json = lambda **kw: (time.sleep(pause), respond_json(**kw))[1]
    return model


def write_replies(folder, ns=EPISODE):
    """The replies of d+35 as files to drop on the case in the browser (deploy/preview/episode/<variant>/): written from
    these builders, so rewrite them after changing a reply."""
    from pathlib import Path
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in ns.replies:
        (out / name).write_bytes(data)
    return [str(out / name) for name, _ in ns.replies]


def add_replies(store, case_id, ns=EPISODE, user=USER):
    """Phase B's replies stored as files of the case, as the upload stores an e-mail without attachments; returns their ids."""
    ids = []
    for name, data in ns.replies:
        row = extract(name, "message/rfc822", data)
        ids.append(store.add_file(case_id, name, row["media_type"], row["kind"], data, row, user)["id"])
    return ids


def seed_frozen_copy(store, runs, user=USER, expert="P1"):
    """A frozen expert-study copy whose run holds a dated account request: the source (Phase A of S-D11A with the A4
    setting a date, so its two open requests are dated deadlines whose keys carry the requests' ids) is prepared, frozen as
    the service froze it before this release (the frozen event and the copy as web/app.py's freeze and study-copy write
    them), and copied for one expert. Returns (source, copy)."""
    from casepath.agents.runner import case_state
    ns = analog(names={**VARIANT_A, "title": "D11-Analogon C (synthetisch)", "reference": "4321.6011.0003"}, dated_request=True)
    source = seed_phase_a(store, runs, ns, title=f"D11-Analogon C, eingefroren (synthetisch) {ns.reference}", user=user)
    current = case_state(store, runs.catalogue, source["id"], study=True)  # as web/app.py's freeze: by the frozen account rules
    listed = build_items(current, current["run"].get("result"), store.list_files(source["id"]))
    frozen = {"frozen_run_id": current["run"]["id"], "items_sha256": items_sha256(listed),
              "workflow_version": (current.get("workflow") or {}).get("version"), "speed_trials": sorted(runs.speed_trials)}
    log = lambda case_id, kind, **fields: store.append_case_event(case_id, {
        "schema": "casepath.study.event/1", "session_id": None, "expert": user, "case_copy": case_id, "source_case": None,
        "frozen_run_id": frozen["frozen_run_id"], "kind": kind, "parity_sha": "episode", "item_id": None, **fields})
    log(source["id"], "study.frozen", **frozen)
    copied = store.create_case(f"{source['title']} · Studie {expert}"[:300],
                               {**(source.get("intake") or {}), "study": {"source_case": source["id"], "expert": expert, **frozen,
                                                                         "opened": source.get("created_at")}}, user)
    for f in store.list_files(source["id"], with_text=True):
        data, row = store.file_bytes(f["id"])
        store.add_file(copied["id"], row["name"], row["media_type"], row["kind"], data, f["extraction"], user)
    log(source["id"], "study.copied", copy=copied["id"], expert=expert)
    return store.get_case(source["id"]), store.get_case(copied["id"])

"""Settlement and payout when the insurer conducts the case itself: a short guided sequence in the handling stage.

Observed: once a settlement is reached, the handler records the agreed amount, asks the customer for bank details (in one
file three to four times), chases the payout, confirms its receipt and closes. Each step here is a prepared action with
its letter or the reason it has none, and a step completes only from evidence, never from a letter copied:

1. Einigung festhalten: amount, who pays and by when, as the file states them (each with its source); the handler
   confirms (``vergleich_bestaetigt``).
2. Bankverbindung erfragen: done once the customer's IBAN is in the file or the account (or the payment came); a request
   dispatched and not yet answered waits («Bankverbindung erfragt am … bis …») and is not sent again.
3. Auszahlung ankündigen: the payment details to the other side, a copy to the customer; done once dispatched
   («angekündigt am …») or once the payment came.
4. Zahlungseingang bestätigen: done only when the payment is shown (the file or the account) and the confirmation to the
   customer was dispatched. A payment instruction is not a payment.
5. Dossier schliessen: «Zahlungseingang bestätigt» only when paid.

Where the terms come from: ``agreement`` reads the offer and payment the file shows (the incoming items). The running
account of the case plugs in at one place: the ``account`` argument of ``agreement`` (``from_account``: amount, payer,
due, paid and their ``citations``, and an IBAN the customer gave); what it states wins over the incoming items. A letter
«went out» only as a dispatch the handler confirmed (completion.sent_letters). Model-free.
"""
from datetime import timedelta
import re

from .. import house
from .clock import parse_date

STEPS = (  # (id, kind, title, form, days to the follow-up)
    ("einigung", "A11", "Einigung festhalten", "A11_einigung", None),
    ("iban", "A11", "Bankverbindung der Kundschaft erfragen", "A11_iban", 14),
    ("auszahlung", "A11", "Auszahlung ankündigen", "A11_auszahlung", 21),
    ("eingang", "A11", "Zahlungseingang bestätigen", "A11_eingang", 14),
    ("abschluss", "A12", "Dossier schliessen", "A12_erledigt", None),
)
MANDATE = "Mandat an Anwaltskanzlei"
AMOUNT = re.compile(r"(?:CHF|Fr\.)\s*(\d[\d'’ ]*(?:[.,]\d{2}|\.[-–]{1,2})?)")
DUE = re.compile(r"\b(?:bis|spätestens|zahlbar bis|per)\s+(?:zum\s+|am\s+)?(\d{4}-\d{2}-\d{2}|\d{1,2}\.\s?\d{1,2}\.\s?\d{4})")
WITHIN = re.compile(r"\binnert\s+(\d{1,3})\s+Tagen\b")
IBAN = re.compile(r"\b([A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?)\b")
PAGE = re.compile(r"\[page (\d+)\]")


def applies(stage, facts):
    """The insurer conducts the case and a settlement is being handled."""
    return stage == "abwicklung" and (facts or {}).get("vorgehen") != MANDATE


def _citations(rows, fact):
    return ((rows or {}).get(fact) or {}).get("citations") or []


PAYERS = {"kunde": "die Kundschaft", "versicherer": house.active().name, "kanzlei": "die Kanzlei", "behoerde": "Gericht/Behörde"}


def from_account(ledger, facts=None):
    """The agreement as it stands in the case's running account (account.py), in the shape ``agreement`` takes: amount,
    who pays (the other side by its name where the file states it), by when, whether paid, and its quotes, with the IBAN
    the customer gave in an entry of the account (``iban``); None without an agreed term or such an IBAN."""
    a = (ledger or {}).get("agreement")
    iban = account_iban(ledger)
    if not a:
        return {"iban": iban} if iban else None
    payer = a.get("payer")
    name = ((facts or {}).get("gegenpartei") or "die Gegenpartei") if payer == "gegenpartei" else PAYERS.get(payer)
    payment = (ledger or {}).get("payment")
    return {"amount": a.get("amount") or a.get("what"), "payer": name, "due": a.get("by"), "date": a.get("date"),
            "citations": a.get("citations") or [], "paid": payment is not None,
            "paid_on": (payment or {}).get("date") or (payment or {}).get("entry_date"),
            # the handler entered the agreement: it is recorded by the handler, the first step of the sequence is done
            "by_handler": bool(a.get("handler")), **({"iban": iban} if iban else {})}


def account_iban(ledger):
    """An IBAN the customer gave in an entry of the account (its words or a quote of it, the checksum valid): {iban,
    holder, file, page, quote}, or None."""
    for e in reversed((ledger or {}).get("entries") or ()):
        if e.get("from") != "kunde":
            continue
        quotes = [(c.get("file"), c.get("page"), str(c.get("quote") or "")) for k in ("citations",) for c in e.get(k) or ()]
        quotes += [(c.get("file"), c.get("page"), str(c.get("quote") or "")) for x in e.get("answers") or () for c in x.get("citations") or ()]
        quotes += [(e.get("file"), e.get("page"), str(e.get("what") or ""))]
        for file_id, page, text in quotes:
            for m in IBAN.finditer(text):
                raw = m.group(1)
                while raw and not _valid_iban(raw):
                    raw = raw[:-1].rstrip()
                if len(raw.replace(" ", "")) >= 15:
                    return {"iban": raw, "holder": "Kundschaft", "file": file_id, "page": page, "quote": text[:160]}
    return None


def agreement(facts, rows=None, account=None):
    """The agreed terms as the file states them: {amount, payer, due, fact, citations}, each value None when not stated.
    ``account``: the running account of the case, where one is kept (another module); it wins over the incoming items."""
    if account and any(account.get(k) for k in ("amount", "payer", "due")):
        return {"amount": account.get("amount"), "payer": account.get("payer"), "due": account.get("due"), "fact": "account",
                "citations": account.get("citations") or [], "paid": bool(account.get("paid")), "date": account.get("date"),
                "by_handler": bool(account.get("by_handler"))}
    for fact in ("eingang_angebot", "eingang_angebot_2", "eingang_zahlung"):
        value = str((facts or {}).get(fact) or "")
        if not value or value.strip().lower() in {"keine", "nein", "-"}:
            continue
        amount = AMOUNT.search(value)
        payer = value.split(":", 1)[0].strip() if ":" in value else None
        due = DUE.search(value)
        within = WITHIN.search(value)
        return {"amount": f"CHF {amount.group(1).strip()}" if amount else None, "payer": payer or None,
                "due": (parse_date(due.group(1).replace(" ", "")).isoformat() if due and parse_date(due.group(1).replace(" ", "")) else
                        f"innert {within.group(1)} Tagen" if within else None),
                "fact": fact, "citations": _citations(rows, fact)}
    return {"amount": None, "payer": None, "due": None, "fact": None, "citations": []}


def _valid_iban(text):
    s = text.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(digits) % 97 == 1


def _pages(f):
    text = str((f.get("extraction") or {}).get("text") or f.get("text") or "")
    parts = PAGE.split(text)
    if len(parts) == 1:
        return [(None, text)]
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def customer_iban(files, customer_name):
    """An IBAN of the customer in the case's files: {iban, holder, file, page, quote}, or None. An IBAN counts as the
    customer's when the customer's name stands near it or the document it is in comes from the customer; one with no
    such sign is returned with ``holder`` None (shown, but the holder is to be checked)."""
    name = str(customer_name or "")
    last = (re.findall(r"[A-ZÄÖÜ][\w-]+", name) or [""])[-1]
    found = None
    for f in files or ():
        segments = (f.get("extraction") or {}).get("segments") or []
        for page, text in _pages(f):
            for m in IBAN.finditer(text):
                raw = m.group(1)
                while raw and not _valid_iban(raw):  # a word of four capitals may follow: trim from the end
                    raw = raw[:-1].rstrip()
                if len(raw.replace(" ", "")) < 15:
                    continue
                window = text[max(0, m.start() - 200): m.end() + 200]
                sender = next((s.get("sender") for s in segments if page and s.get("first_page", 0) <= page <= s.get("last_page", 0)), "")
                own = bool(last) and (last in window or last in str(sender or ""))
                line = next((l.strip() for l in text.splitlines() if raw[:8] in l.replace("  ", " ")), raw)
                row = {"iban": raw, "holder": name if own else None, "file": f.get("id"), "page": page, "quote": line[:160]}
                if own:
                    return row
                found = found or row
    return found


def dispatched(events, form):
    """The dispatches in force of a letter of this form, oldest first (completion.sent_letters: an approved version the
    handler confirmed as sent, not undone); a letter copied is never one."""
    from .completion import sent_letters
    return [s for s in sent_letters(events) if form == s.get("form") or form in (s.get("also") or ())]


def _day(value):
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else value


def _plus(value, days):
    d = parse_date(value)
    return (d + timedelta(days=days)).isoformat() if d and days else None


def state(facts, rows, files, events, customer_name=None, account=None):
    """Where the sequence stands: {step, done: [ids], terms, iban, paid, asked, announced, confirmed}. A step is done only
    on evidence: the agreement confirmed or entered by the handler, the customer's IBAN in the file or the account (or the
    payment made), the payout announced by a dispatched letter (or the payment made), the receipt confirmed by a
    dispatched letter once the payment is shown. ``asked``/``announced``/``confirmed``: the latest dispatch of the
    step's letter (A11_iban, A11_auszahlung, A11_eingang)."""
    facts = facts or {}
    terms = agreement(facts, rows, account)
    iban = customer_iban(files, customer_name)
    given = (account or {}).get("iban")
    if not (iban and iban["holder"]) and given:  # an IBAN the customer gave in an entry of the account
        iban = {**given, "holder": customer_name or given.get("holder")}
    paid = bool(facts.get("eingang_zahlung")) or facts.get("zahlung_erhalten") is True or bool(terms.get("paid"))
    asked, announced, confirmed = (dispatched(events, f) for f in ("A11_iban", "A11_auszahlung", "A11_eingang"))
    done = []
    if facts.get("vergleich_bestaetigt") is True or terms.get("by_handler"):  # confirmed, or entered by the handler
        done.append("einigung")
    if (iban and iban["holder"]) or paid:
        done.append("iban")
    if announced or paid:
        done.append("auszahlung")
    if paid and confirmed:
        done.append("eingang")
    step = next((s for s in STEPS if s[0] not in done), STEPS[-1])
    return {"step": step, "done": done, "terms": terms, "iban": iban, "paid": paid,
            "asked": asked[-1] if asked else None, "announced": announced[-1] if announced else None, "confirmed": confirmed[-1] if confirmed else None}


def planned(st, facts):
    """The prepared action of the current step, in the shape items.build_items uses. A step whose letter went out and
    whose answer is still missing waits from that day (``since``), its reason saying what was asked and until when."""
    sid, kind, title, form, days = st["step"]
    asked, announced, confirmed = st.get("asked"), st.get("announced"), st.get("confirmed")
    reason = {"einigung": "Einigung erzielt: Betrag, wer zahlt und bis wann aus der Akte festhalten"
                          + ("; von der Fallbearbeitung nicht bestätigt, bitte die Angaben prüfen" if (facts or {}).get("vergleich_bestaetigt") is False else ""),
              "iban": (f"Bankverbindung erfragt am {_day(asked['date'])} bis {_day(_plus(asked['date'], days))}" if asked
                       else "Einigung festgehalten; die Bankverbindung der Kundschaft fehlt in der Akte"),
              "auszahlung": "Einigung festgehalten" + ("; Bankverbindung laut Akte" if st["iban"] and st["iban"]["holder"] else ""),
              "eingang": ("Auszahlung angekündigt" + (f" am {_day(announced['date'])}" if announced else "")
                          + ("; Zahlung laut Akte eingegangen" if st["paid"] else
                             f"; Zahlungseingang erfragt am {_day(confirmed['date'])} bis {_day(_plus(confirmed['date'], days))}" if confirmed
                             else "; Eingang bei der Kundschaft erfragen")),
              "abschluss": "Zahlungseingang bestätigt"}[sid]
    waits = asked if sid == "iban" else confirmed if sid == "eingang" and not st["paid"] else None
    return {"kind": kind, "title": title, "form": form, "next_in_days": days, "follow_up": None, "skip_if": None, "reason": reason,
            "settlement": sid, **({"since": waits["date"]} if waits else {})}


def lines(st):
    """The short facts the card shows for the sequence, each with its source: the terms and the customer's IBAN."""
    t = st["terms"]
    out = []
    if t["fact"]:
        parts = [t["amount"] or "Betrag nicht in der Akte", f"zahlt: {t['payer']}" if t["payer"] else "Zahler nicht in der Akte",
                 f"bis {_day(t['due'])}" if t["due"] else "Termin nicht in der Akte"]
        if t.get("paid"):
            parts.append("bezahlt")
        out.append({"id": "vg-einigung", "text": ("Einigung laut Eintrag der Fallbearbeitung: " if t.get("by_handler") else
                                                  "Einigung laut Verlauf: " if t["fact"] == "account" else "Einigung laut Akte: ") + " · ".join(parts),
                    "citations": t["citations"][:1], "facts": [] if t["fact"] == "account" else [t["fact"]],
                    "amount": t["amount"], "payer": t["payer"], "due": t["due"], "date": t.get("date")})
    else:
        out.append({"id": "vg-einigung", "text": "Einigung: Betrag, Zahler und Termin nicht in der Akte", "citations": [], "facts": [],
                    "amount": None, "payer": None, "due": None})
    i = st["iban"]
    if i:
        out.append({"id": "vg-iban", "text": f"IBAN laut Akte: {i['iban']}" + ("" if i["holder"] else " (Kontoinhaber nicht erkennbar, prüfen)"),
                    "citations": [{"file": i["file"], "page": i["page"], "quote": i["quote"]}], "facts": [],
                    "iban": i["iban"], "holder": i["holder"]})
    return out


def letter_context(items):
    """The placeholders of the sequence's letters, from the card's lines; gaps where the file is silent."""
    from .letters import gap
    line = {i["key"]: i for i in items if i["kind"] == "stage_line"}
    t = line.get("vg-einigung") or {}
    i = line.get("vg-iban") or {}
    amount = t.get("amount")
    due = t.get("due")
    payment = next((x.get("value") for x in items if x["kind"] == "fact" and x["key"] == "eingang_zahlung" and x.get("value")), None)
    paid_amount = AMOUNT.search(str(payment or ""))
    paid_day = re.search(r"\d{4}-\d{2}-\d{2}", str(payment or ""))
    owed = next((x.get("owed") for x in items if x["kind"] == "next_action" and x.get("owed")), None) or {}
    owed_amount = owed.get("amount") or amount or owed.get("what")
    owed_by = owed.get("by") or (due if due and parse_date(due) else None)
    return {
        # the chase of an agreed payment not made (the account's next action): to the party that owes it
        "nachfrage_bezug": f"vom {_day(owed.get('date') or t.get('date'))}" if (owed.get("date") or t.get("date")) else gap("Datum der Vereinbarung"),
        "nachfrage_terms": (f"Zahlung von {owed_amount or gap('Betrag')}" + (f" bis {_day(owed_by)}" if owed_by else "")),
        "nachfrage_betrag": owed_amount or gap("Betrag"),
        "nachfrage_konto": (f"Kontoinhaberin / Kontoinhaber: {i.get('holder')}\nIBAN: {i['iban']}" if i.get("iban") and i.get("holder") else ""),
        "vergleich_satz": (f"{t.get('payer') or gap('wer zahlt')} bezahlt {amount or gap('den vereinbarten Betrag')}"
                           + (f" bis {_day(due)}." if due and parse_date(due) else f" {due}." if due else f" bis {gap('Zahlungstermin')}.")),
        "vergleich_termin_satz": (f"bis {_day(due)}" if due and parse_date(due) else due or f"bis {gap('Zahlungstermin')}"),
        "iban": i.get("iban") or gap("IBAN der Kundschaft"),
        "iban_inhaber": i.get("holder") or gap("Kontoinhaberin oder Kontoinhaber"),
        "eingang_satz": (f"Wir freuen uns, Ihnen mitzuteilen, dass die Zahlung über CHF {paid_amount.group(1).strip()}"
                         + (f" am {_day(paid_day.group(0))}" if paid_day else "") + " eingegangen ist." if paid_amount else
                         f"Gemäss unseren Unterlagen ist die Zahlung über {amount or gap('Betrag')} erfolgt. Bitte bestätigen Sie uns kurz, dass der Betrag auf Ihrem Konto eingegangen ist."),
    }
